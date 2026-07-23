import json
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request, session
from sqlalchemy import select

from . import limiter, logger
from .auth import login_required
from .models import SavedView, SessionLocal

saved_views_bp = Blueprint("saved_views", __name__, url_prefix="/api/v1/views")

_MAX_VIEW_NAME_LEN = 200

_ALLOWED_SECTIONS = {
    "overview", "revenue", "products", "website", "customers",
    "data-explorer", "sql-query", "forecasting", "anomalies", "admin", "nl-query",
}


def _get_user_id():
    from .models import User
    username = session.get("user", "")
    if not username:
        return None
    s = SessionLocal()
    try:
        user = s.execute(select(User).where(User.username == username)).scalar_one_or_none()
        return user.id if user else None
    finally:
        s.close()


@saved_views_bp.route("", methods=["GET"])
@login_required
@limiter.limit("30/minute")
def list_views():
    user_id = _get_user_id()
    if user_id is None:
        return jsonify({"error": "Unauthorized"}), 401
    s = SessionLocal()
    try:
        views = s.execute(
            select(SavedView).where(SavedView.user_id == user_id).order_by(SavedView.updated_at.desc())
        ).scalars().all()
        result = []
        for v in views:
            d = v.to_dict()
            d.pop("user_id", None)
            result.append(d)
        return jsonify(result)
    finally:
        s.close()


@saved_views_bp.route("", methods=["POST"])
@login_required
@limiter.limit("20/minute")
def create_view():
    data = request.get_json(force=True)
    if not data:
        return jsonify({"error": "Request body required"}), 400

    name = data.get("name", "").strip()
    if not name:
        return jsonify({"error": "Name required"}), 400
    if len(name) > _MAX_VIEW_NAME_LEN:
        return jsonify({"error": f"Name must be {_MAX_VIEW_NAME_LEN} characters or fewer"}), 400

    section = data.get("section", "overview")
    if section not in _ALLOWED_SECTIONS:
        section = "overview"

    filters = data.get("filters", {})
    if not isinstance(filters, dict):
        return jsonify({"error": "filters must be an object"}), 400

    user_id = _get_user_id()
    if user_id is None:
        return jsonify({"error": "Unauthorized"}), 401

    s = SessionLocal()
    try:
        view = SavedView(
            user_id=user_id,
            name=name,
            view_type=data.get("view_type", "filter"),
            filters_json=json.dumps(filters),
            sql_query=data.get("sql_query"),
            connection=data.get("connection", "demo"),
            section=section,
        )
        s.add(view)
        s.commit()
        logger.info("User '%s' created view '%s'", session.get("user"), name)
        d = view.to_dict()
        d.pop("user_id", None)
        return jsonify({"status": "ok", "view": d})
    finally:
        s.close()


@saved_views_bp.route("/<int:view_id>", methods=["GET"])
@login_required
@limiter.limit("30/minute")
def get_view(view_id: int):
    user_id = _get_user_id()
    if user_id is None:
        return jsonify({"error": "Unauthorized"}), 401
    s = SessionLocal()
    try:
        view = s.execute(
            select(SavedView).where(SavedView.id == view_id, SavedView.user_id == user_id)
        ).scalar_one_or_none()
        if not view:
            return jsonify({"error": "View not found"}), 404
        d = view.to_dict()
        d.pop("user_id", None)
        return jsonify(d)
    finally:
        s.close()


@saved_views_bp.route("/<int:view_id>", methods=["PUT"])
@login_required
@limiter.limit("20/minute")
def update_view(view_id: int):
    data = request.get_json(force=True)
    if not data:
        return jsonify({"error": "Request body required"}), 400

    user_id = _get_user_id()
    if user_id is None:
        return jsonify({"error": "Unauthorized"}), 401

    s = SessionLocal()
    try:
        view = s.execute(
            select(SavedView).where(SavedView.id == view_id, SavedView.user_id == user_id)
        ).scalar_one_or_none()
        if not view:
            return jsonify({"error": "View not found"}), 404

        if "name" in data:
            name = data["name"].strip()
            if not name:
                return jsonify({"error": "Name cannot be empty"}), 400
            if len(name) > _MAX_VIEW_NAME_LEN:
                return jsonify({"error": f"Name must be {_MAX_VIEW_NAME_LEN} characters or fewer"}), 400
            view.name = name
        if "filters" in data:
            filters = data["filters"]
            if not isinstance(filters, dict):
                return jsonify({"error": "filters must be an object"}), 400
            view.filters_json = json.dumps(filters)
        if "sql_query" in data:
            view.sql_query = data["sql_query"]
        if "connection" in data:
            view.connection = data["connection"]
        if "section" in data:
            section = data["section"]
            if section in _ALLOWED_SECTIONS:
                view.section = section
        view.updated_at = datetime.now(timezone.utc)
        s.commit()
        d = view.to_dict()
        d.pop("user_id", None)
        return jsonify({"status": "ok", "view": d})
    finally:
        s.close()


@saved_views_bp.route("/<int:view_id>", methods=["DELETE"])
@login_required
@limiter.limit("20/minute")
def delete_view(view_id: int):
    user_id = _get_user_id()
    if user_id is None:
        return jsonify({"error": "Unauthorized"}), 401
    s = SessionLocal()
    try:
        view = s.execute(
            select(SavedView).where(SavedView.id == view_id, SavedView.user_id == user_id)
        ).scalar_one_or_none()
        if not view:
            return jsonify({"error": "View not found"}), 404
        s.delete(view)
        s.commit()
        return jsonify({"status": "ok"})
    finally:
        s.close()


def init_saved_views_csrf(app_csrf):
    """Register CSRF exemptions after the app is created."""
    app_csrf.exempt(create_view)
    app_csrf.exempt(update_view)
    app_csrf.exempt(delete_view)
