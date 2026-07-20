import json
import re
import time

import pandas as pd
from flask import Blueprint, Response, jsonify, render_template, request, session

from . import limiter, logger, socketio
from .auth import login_required
from .config import Config
from .core.analytics_engine import AnalyticsEngine
from .core.database_connector import DatabaseConnector
from .utils.helpers import safe_json_serialize


def _json_response(data, status=200):
    return Response(
        json.dumps(data, default=safe_json_serialize),
        status=status,
        mimetype="application/json",
    )


bp = Blueprint("main", __name__)

db_connector = DatabaseConnector()
analytics = AnalyticsEngine()

db_connector.connect_demo_sqlite()

_df_cache: dict[str, pd.DataFrame] = {}

_TABLE_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def _get_cached(name: str) -> pd.DataFrame:
    if not _TABLE_RE.match(name):
        raise ValueError(f"Invalid table name: {name}")
    if name not in _df_cache:
        _df_cache[name] = db_connector.execute_query("demo", f"SELECT * FROM {name}")  # noqa: S608
    return _df_cache[name].copy()


def _invalidate_cache():
    _df_cache.clear()


# ------------------------------------------------------------------
# Pages
# ------------------------------------------------------------------
@bp.route("/")
@login_required
def index():
    tables = db_connector.list_tables("demo")
    return render_template("dashboard.html", tables=tables)


# ------------------------------------------------------------------
# REST API
# ------------------------------------------------------------------
@bp.route("/api/dashboard-data")
@login_required
@limiter.limit("30/minute")
def api_dashboard_data():
    sales = _get_cached("sales")
    customers = _get_cached("customers")
    website = _get_cached("website_analytics")
    payload = analytics.build_dashboard_payload(sales, customers, website)
    return _json_response(payload)


@bp.route("/api/tables")
@login_required
def api_tables():
    return jsonify(db_connector.list_tables("demo"))


@bp.route("/api/table/<table_name>")
@login_required
def api_table_meta(table_name: str):
    if not _TABLE_RE.match(table_name):
        return jsonify({"error": "Invalid table name"}), 400
    return jsonify(db_connector.get_table_info("demo", table_name))


@bp.route("/api/query", methods=["POST"])
@login_required
@limiter.limit("10/minute")
def api_custom_query():
    data = request.get_json(force=True)
    sql = data.get("sql", "")
    if not sql.strip():
        return jsonify({"error": "Empty query"}), 400

    if Config.SQL_READ_ONLY:
        normalized = sql.strip().upper()
        forbidden = ("INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "TRUNCATE", "EXEC", "EXECUTE")
        for kw in forbidden:
            if normalized.startswith(kw) or f" {kw} " in normalized:
                return jsonify({"error": f"Operation '{kw}' is not allowed in read-only mode"}), 403

    try:
        df = db_connector.execute_query("demo", sql)
        limited = df.head(Config.SQL_MAX_ROWS)
        return _json_response(
            {
                "columns": list(limited.columns),
                "rows": limited.to_dict(orient="records"),
                "row_count": len(df),
                "truncated": len(df) > Config.SQL_MAX_ROWS,
            }
        )
    except Exception as exc:
        logger.warning("Query failed: %s", exc)
        return jsonify({"error": str(exc)}), 400


@bp.route("/api/data/<table_name>")
@login_required
def api_table_data(table_name: str):
    if not _TABLE_RE.match(table_name):
        return jsonify({"error": "Invalid table name"}), 400
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 100, type=int), 500)
    sort = request.args.get("sort", None)
    search = request.args.get("search", None)
    df = _get_cached(table_name)
    if search:
        mask = df.apply(lambda col: col.astype(str).str.contains(search, case=False, na=False)).any(axis=1)
        df = df[mask]
    if sort:
        desc = sort.startswith("-")
        col = sort.lstrip("-")
        if col in df.columns:
            df = df.sort_values(col, ascending=not desc)
    total = len(df)
    start = (page - 1) * per_page
    chunk = df.iloc[start : start + per_page]
    return _json_response(
        {
            "columns": list(chunk.columns),
            "rows": chunk.to_dict(orient="records"),
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": (total + per_page - 1) // per_page,
        }
    )


@bp.route("/api/connect", methods=["POST"])
@login_required
@limiter.limit("5/minute")
def api_connect_db():
    if session.get("role") != "admin":
        return jsonify({"error": "Admin access required"}), 403
    data = request.get_json(force=True)
    name = data.get("name", "")
    conn_str = data.get("connection_string", "")
    if not name or not conn_str:
        return jsonify({"error": "name and connection_string required"}), 400
    if not _TABLE_RE.match(name):
        return jsonify({"error": "Invalid connection name"}), 400
    try:
        result = db_connector.connect(name, conn_str)
        _invalidate_cache()
        logger.info("Database '%s' connected", name)
        return jsonify(result)
    except Exception as exc:
        logger.error("Connection failed: %s", exc)
        return jsonify({"error": str(exc)}), 400


@bp.route("/api/filter", methods=["POST"])
@login_required
@limiter.limit("30/minute")
def api_filter():
    data = request.get_json(force=True)
    table = data.get("table", "sales")
    filters = data.get("filters", {})
    if not _TABLE_RE.match(table):
        return jsonify({"error": "Invalid table name"}), 400
    df = _get_cached(table)
    for col, val in filters.items():
        if col in df.columns and val:
            if isinstance(val, list):
                df = df[df[col].isin(val)]
            else:
                df = df[df[col].astype(str).str.contains(str(val), case=False, na=False)]
    kpis = analytics.dp.compute_kpis(df) if "total_revenue" in df.columns else {"record_count": len(df)}
    return _json_response({"kpis": kpis, "row_count": len(df)})


# ------------------------------------------------------------------
# WebSocket events for real-time updates
# ------------------------------------------------------------------
@socketio.on("connect")
def handle_connect():
    logger.info("WebSocket client connected")


@socketio.on("request_refresh")
def handle_refresh():
    _invalidate_cache()
    sales = _get_cached("sales")
    customers = _get_cached("customers")
    website = _get_cached("website_analytics")
    payload = analytics.build_dashboard_payload(sales, customers, website)
    socketio.emit(
        "dashboard_update",
        json.loads(json.dumps(payload, default=safe_json_serialize)),
    )


def start_realtime_loop():
    """Push dashboard updates on a schedule (called from a background thread)."""
    interval = Config.REALTIME_INTERVAL
    while True:
        time.sleep(interval)
        try:
            _invalidate_cache()
            sales = _get_cached("sales")
            customers = _get_cached("customers")
            website = _get_cached("website_analytics")
            payload = analytics.build_dashboard_payload(sales, customers, website)
            socketio.emit(
                "dashboard_update",
                json.loads(json.dumps(payload, default=safe_json_serialize)),
            )
        except Exception as exc:
            logger.error("Realtime error: %s", exc)
