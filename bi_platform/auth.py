import logging
import os
import re
import secrets
import sqlite3
from functools import wraps

from flask import (
    Blueprint,
    current_app,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
    Response,
)
import json

import pandas as pd
from werkzeug.security import check_password_hash, generate_password_hash

from . import limiter, logger
from .core.analytics_engine import AnalyticsEngine
from .core.database_connector import DatabaseConnector
from .core.query_builder import QueryBuilder
from .utils.helpers import safe_json_serialize

auth_bp = Blueprint("auth", __name__)

_users_db: dict[str, dict] = {}

DEFAULT_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
DEFAULT_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")


def _init_default_user():
    if DEFAULT_USERNAME not in _users_db:
        _users_db[DEFAULT_USERNAME] = {
            "username": DEFAULT_USERNAME,
            "password": generate_password_hash(DEFAULT_PASSWORD),
            "role": "admin",
        }
        logger.info("Default user '%s' created", DEFAULT_USERNAME)


_init_default_user()


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated_function


@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.exempt
def login():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        user = _users_db.get(username)
        if user and check_password_hash(user["password"], password):
            session["user"] = username
            session["role"] = user["role"]
            logger.info("User '%s' logged in", username)
            return redirect(url_for("main.index"))
        error = "Invalid username or password"
    return render_template("login.html", error=error)


@auth_bp.route("/logout")
@limiter.exempt
def logout():
    user = session.pop("user", None)
    session.pop("role", None)
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
    if username in _users_db:
        return jsonify({"error": "Username already exists"}), 409

    _users_db[username] = {
        "username": username,
        "password": generate_password_hash(password),
        "role": "viewer",
    }
    logger.info("New user '%s' registered", username)
    return jsonify({"status": "ok", "message": "Registration successful"})
