import os
from functools import wraps

from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for
from sqlalchemy import select
from werkzeug.security import check_password_hash, generate_password_hash

from . import csrf, limiter, logger
from .models import SessionLocal, User

auth_bp = Blueprint("auth", __name__)

DEFAULT_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
DEFAULT_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user" not in session:
            if request.is_json or request.accept_mimetypes.best == "application/json":
                return jsonify({"error": "Authentication required"}), 401
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)

    return decorated_function


@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("20/minute")
def login():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        session_local = SessionLocal()
        try:
            user = session_local.execute(select(User).where(User.username == username)).scalar_one_or_none()
            if user and check_password_hash(str(user.password_hash), password):
                session["user"] = username
                session["role"] = user.role
                logger.info("User '%s' logged in", username)
                return redirect(url_for("main.index"))
            error = "Invalid username or password"
        finally:
            session_local.close()
    return render_template("login.html", error=error)


@auth_bp.route("/register", methods=["GET", "POST"])
@limiter.limit("5/minute")
def register_page():
    error = None
    success = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        if not username or not password:
            error = "Username and password are required"
        elif len(username) < 3:
            error = "Username must be at least 3 characters"
        elif len(password) < 8:
            error = "Password must be at least 8 characters"
        elif password != confirm:
            error = "Passwords do not match"
        else:
            session_local = SessionLocal()
            try:
                existing = session_local.execute(select(User).where(User.username == username)).scalar_one_or_none()
                if existing:
                    error = "Username already exists"
                else:
                    user = User(
                        username=username,
                        password_hash=generate_password_hash(password),
                        role="viewer",
                    )
                    session_local.add(user)
                    session_local.commit()
                    logger.info("New user '%s' registered", username)
                    success = "Account created! You can now sign in."
            finally:
                session_local.close()

    return render_template("register.html", error=error, success=success)


@auth_bp.route("/logout")
@limiter.exempt
def logout():
    user = session.pop("user", None)
    session.pop("role", None)
    session.clear()
    logger.info("User '%s' logged out", user)
    return redirect(url_for("auth.login"))


@auth_bp.route("/api/register", methods=["POST"])
@limiter.limit("5/minute")
def register():
    data = request.get_json(force=True)
    username = data.get("username", "").strip()
    password = data.get("password", "")

    if not username or not password:
        return jsonify({"error": "Username and password required"}), 400
    if len(username) < 3:
        return jsonify({"error": "Username must be at least 3 characters"}), 400
    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters"}), 400

    session_local = SessionLocal()
    try:
        existing = session_local.execute(select(User).where(User.username == username)).scalar_one_or_none()
        if existing:
            return jsonify({"error": "Username already exists"}), 409

        user = User(
            username=username,
            password_hash=generate_password_hash(password),
            role="viewer",
        )
        session_local.add(user)
        session_local.commit()
        logger.info("New user '%s' registered", username)
        return jsonify({"status": "ok", "message": "Registration successful"})
    finally:
        session_local.close()


csrf.exempt(register)
csrf.exempt(register_page)
