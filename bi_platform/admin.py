from functools import wraps

from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for
from sqlalchemy import select
from werkzeug.security import generate_password_hash

from . import csrf, limiter, logger
from .models import SessionLocal, User

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("auth.login"))
        if session.get("role") != "admin":
            return jsonify({"error": "Admin access required"}), 403
        return f(*args, **kwargs)
    return decorated


@admin_bp.route("/users")
@admin_required
@limiter.limit("30/minute")
def list_users():
    session_local = SessionLocal()
    try:
        users = session_local.execute(select(User).order_by(User.id)).scalars().all()
        return render_template("admin_users.html", users=[u.to_dict() for u in users])
    finally:
        session_local.close()


@admin_bp.route("/api/users", methods=["GET"])
@admin_required
@limiter.limit("30/minute")
def api_list_users():
    session_local = SessionLocal()
    try:
        users = session_local.execute(select(User).order_by(User.id)).scalars().all()
        return jsonify([u.to_dict() for u in users])
    finally:
        session_local.close()


@admin_bp.route("/api/users", methods=["POST"])
@admin_required
@limiter.limit("10/minute")
def api_create_user():
    data = request.get_json(force=True)
    username = data.get("username", "").strip()
    password = data.get("password", "")
    role = data.get("role", "viewer")

    if not username or not password:
        return jsonify({"error": "Username and password required"}), 400
    if len(username) < 3:
        return jsonify({"error": "Username must be at least 3 characters"}), 400
    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters"}), 400
    if role not in ("admin", "viewer"):
        return jsonify({"error": "Role must be 'admin' or 'viewer'"}), 400

    session_local = SessionLocal()
    try:
        existing = session_local.execute(select(User).where(User.username == username)).scalar_one_or_none()
        if existing:
            return jsonify({"error": "Username already exists"}), 409
        user = User(
            username=username,
            password_hash=generate_password_hash(password),
            role=role,
        )
        session_local.add(user)
        session_local.commit()
        logger.info("Admin created user '%s' with role '%s'", username, role)
        return jsonify({"status": "ok", "user": user.to_dict()})
    finally:
        session_local.close()


@admin_bp.route("/api/users/<int:user_id>", methods=["PUT"])
@admin_required
@limiter.limit("20/minute")
def api_update_user(user_id: int):
    data = request.get_json(force=True)
    session_local = SessionLocal()
    try:
        user = session_local.get(User, user_id)
        if not user:
            return jsonify({"error": "User not found"}), 404

        if "role" in data:
            new_role = data["role"]
            if new_role not in ("admin", "viewer"):
                return jsonify({"error": "Invalid role"}), 400
            user.role = new_role

        if "password" in data and data["password"]:
            if len(data["password"]) < 8:
                return jsonify({"error": "Password must be at least 8 characters"}), 400
            user.password_hash = generate_password_hash(data["password"])

        session_local.commit()
        logger.info("Admin updated user '%s' (id=%d)", user.username, user_id)
        return jsonify({"status": "ok", "user": user.to_dict()})
    finally:
        session_local.close()


@admin_bp.route("/api/users/<int:user_id>", methods=["DELETE"])
@admin_required
@limiter.limit("10/minute")
def api_delete_user(user_id: int):
    session_local = SessionLocal()
    try:
        user = session_local.get(User, user_id)
        if not user:
            return jsonify({"error": "User not found"}), 404

        if user.username == session.get("user"):
            return jsonify({"error": "Cannot delete yourself"}), 400

        username = user.username
        session_local.delete(user)
        session_local.commit()
        logger.info("Admin deleted user '%s' (id=%d)", username, user_id)
        return jsonify({"status": "ok", "message": f"User '{username}' deleted"})
    finally:
        session_local.close()


csrf.exempt(api_create_user)
csrf.exempt(api_update_user)
csrf.exempt(api_delete_user)
