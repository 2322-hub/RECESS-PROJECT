import json
import re
import time

import pandas as pd
from flask import Blueprint, Response, jsonify, redirect, render_template, request, session
from flask_socketio import disconnect, emit

from . import limiter, logger, socketio
from .auth import login_required
from .cache import CacheLayer
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
api_bp = Blueprint("api", __name__, url_prefix="/api/v1")

db_connector = DatabaseConnector()
analytics = AnalyticsEngine()

db_connector.connect_demo_sqlite()

_default_conn = "demo"
_db_url = Config.SQLALCHEMY_DATABASE_URI
if _db_url and not _db_url.startswith("sqlite"):
    try:
        db_connector.connect("bi_platform", _db_url)
        _default_conn = "bi_platform"
    except Exception as _e:
        logger.warning("Could not auto-connect DATABASE_URL: %s", _e)

_df_cache: dict[str, pd.DataFrame] = {}
_active_conn: dict[str, str] = {}
_row_count_cache: dict[str, int] = {}
_data_dirty: bool = True

_TABLE_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")
_DANGEROUS_SQL_RE = re.compile(
    r"(;|\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|EXEC|EXECUTE|INTO|GRANT|REVOKE)\b)",
    re.IGNORECASE,
)

_COLUMN_MAP = {
    "date": ("date", "created_at", "order_date", "sale_date", "transaction_date", "timestamp"),
    "total_revenue": ("total_revenue", "amount", "total", "revenue", "sales_amount", "sale_amount", "net_sales"),
    "cost": ("cost", "total_cost", "unit_cost", "cogs"),
    "profit": ("profit", "net_profit", "gross_profit", "earnings"),
    "quantity": ("quantity", "qty", "units", "count"),
    "region": ("region", "area", "territory", "location", "country", "state", "city"),
    "product_category": ("product_category", "category", "product_type", "type"),
    "product_name": ("product_name", "product", "name", "item_name", "product_name"),
    "customer_segment": ("customer_segment", "segment", "customer_type", "client_type"),
}

# Online users for collaborative features
_online_users: dict[str, dict] = {}


def _normalize_columns(df: pd.DataFrame, table_type: str = "sales") -> pd.DataFrame:
    if df.empty:
        return df
    df = df.copy()
    lower_cols = {c.lower().strip(): c for c in df.columns}
    for target, candidates in _COLUMN_MAP.items():
        if target in df.columns:
            continue
        for candidate in candidates:
            if candidate in lower_cols:
                df = df.rename(columns={lower_cols[candidate]: target})
                break
    if table_type == "sales":
        if "total_revenue" not in df.columns:
            if "quantity" in df.columns and "unit_price" in df.columns:
                df["total_revenue"] = df["quantity"].astype(float) * df["unit_price"].astype(float)
            elif "qty" in df.columns and "price" in df.columns:
                df["total_revenue"] = df["qty"].astype(float) * df["price"].astype(float)
        if "profit" not in df.columns and "total_revenue" in df.columns:
            if "cost" in df.columns:
                df["profit"] = df["total_revenue"].astype(float) - df["cost"].astype(float)
            else:
                df["profit"] = df["total_revenue"].astype(float)
        if "cost" not in df.columns and "total_revenue" in df.columns and "profit" in df.columns:
            df["cost"] = df["total_revenue"].astype(float) - df["profit"].astype(float)
        for col in ("region", "product_category", "product_name", "customer_segment"):
            if col not in df.columns:
                df[col] = "All"
        if "date" not in df.columns:
            for candidate in ("created_at", "order_date", "sale_date", "transaction_date", "timestamp"):
                if candidate in lower_cols:
                    df["date"] = df[lower_cols[candidate]]
                    break
            if "date" not in df.columns:
                df["date"] = pd.Timestamp.now().strftime("%Y-%m-%d")
        if "quantity" not in df.columns:
            df["quantity"] = 1
    return df


def _get_cached(name: str, conn: str = "demo") -> pd.DataFrame:
    cache_key = f"{conn}:{name}"
    if not _TABLE_RE.match(name):
        raise ValueError(f"Invalid table name: {name}")
    if cache_key not in _df_cache:
        _df_cache[cache_key] = db_connector.execute_query(conn, f"SELECT * FROM {name}")  # noqa: S608
    return _df_cache[cache_key].copy()


def _invalidate_cache():
    global _data_dirty
    _df_cache.clear()
    _data_dirty = True
    CacheLayer.invalidate("*")


def _use_sql_mode(conn: str) -> bool:
    if conn == "demo":
        cache_key = f"{conn}:sales"
        if cache_key in _row_count_cache:
            return _row_count_cache[cache_key] > Config.MAX_ROWS_IN_MEMORY
        try:
            from sqlalchemy import text

            engine = db_connector._engines.get(conn)
            if engine is None:
                return False
            with engine.connect() as c:
                count = c.execute(text("SELECT COUNT(*) FROM sales")).scalar() or 0
            _row_count_cache[cache_key] = count
            return count > Config.MAX_ROWS_IN_MEMORY
        except Exception:
            return False
    return True


# ------------------------------------------------------------------
# Role-based access helper
# ------------------------------------------------------------------
_ROLE_SECTIONS = {
    "admin": {
        "overview",
        "revenue",
        "products",
        "website",
        "customers",
        "data-explorer",
        "sql-query",
        "forecasting",
        "anomalies",
        "admin",
    },
    "viewer": {"overview", "revenue", "products", "website", "customers"},
}


@bp.route("/")
@login_required
def index():
    tables = db_connector.list_tables(_default_conn)
    role = session.get("role", "viewer")
    allowed_sections = list(_ROLE_SECTIONS.get(role, _ROLE_SECTIONS["viewer"]))
    return render_template(
        "dashboard.html",
        tables=tables,
        default_conn=_default_conn,
        user_role=role,
        allowed_sections=allowed_sections,
        user=session.get("user", ""),
    )


# ------------------------------------------------------------------
# API v1 routes
# ------------------------------------------------------------------
def _load_dashboard_data(conn: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if conn == "demo":
        return _get_cached("sales"), _get_cached("customers"), _get_cached("website_analytics")

    tables = db_connector.list_tables(conn)
    logger.info("Tables in '%s': %s", conn, tables)

    sales = pd.DataFrame()
    customers = pd.DataFrame()
    website = pd.DataFrame()

    if "products" in tables and "sales" in tables:
        products_df = db_connector.execute_query(conn, "SELECT * FROM products")
        sales = db_connector.execute_query(conn, "SELECT * FROM sales")
        sales = sales.merge(products_df, left_on="product_id", right_on="id", suffixes=("", "_prod"))
        sales = sales.rename(
            columns={
                "sale_date": "date",
                "total": "total_revenue",
                "price": "unit_price",
                "category": "product_category",
                "name": "product_name",
            }
        )
        sales["cost"] = 0.0
        sales["profit"] = sales["total_revenue"].astype(float)
        sales["region"] = "All"
        sales["customer_segment"] = "All"
        sales["total_revenue"] = sales["total_revenue"].astype(float)
    elif "sales" in tables:
        sales = db_connector.execute_query(conn, "SELECT * FROM sales")
        sales = _normalize_columns(sales, "sales")
    else:
        for tbl in tables:
            raw = db_connector.execute_query(conn, f"SELECT * FROM {tbl}")  # noqa: S608
            if not raw.empty:
                sales = _normalize_columns(raw, "sales")
                break

    if "customers" in tables:
        customers = db_connector.execute_query(conn, "SELECT * FROM customers")
        customers = _normalize_columns(customers, "customers")
    if "website_analytics" in tables:
        website = db_connector.execute_query(conn, "SELECT * FROM website_analytics")

    logger.info("Loaded '%s': sales=%d, customers=%d, website=%d", conn, len(sales), len(customers), len(website))
    return sales, customers, website


@api_bp.route("/dashboard-data")
@login_required
@limiter.limit("30/minute")
def api_dashboard_data():
    conn = request.args.get("conn", "demo")
    _active_conn[session.get("user", "anonymous")] = conn

    cache_key = f"dashboard:{conn}"
    cached = CacheLayer.get(cache_key)
    if cached:
        cached["_conn"] = conn
        return _json_response(cached)

    if _use_sql_mode(conn):
        try:
            payload = analytics.build_dashboard_payload_sql(db_connector, conn)
            payload["_conn"] = conn
            payload["_mode"] = "sql"
            cache_key_count = f"{conn}:sales"
            payload["_sales_rows"] = _row_count_cache.get(cache_key_count, 0)
            CacheLayer.set(cache_key, payload, ttl=30)
            return _json_response(payload)
        except Exception as e:
            logger.error("SQL dashboard error for '%s': %s", conn, e, exc_info=True)
            return jsonify({"error": str(e), "conn": conn}), 400

    try:
        sales, customers, website = _load_dashboard_data(conn)
    except Exception as e:
        logger.error("Dashboard data error for '%s': %s", conn, e, exc_info=True)
        return jsonify({"error": str(e), "conn": conn}), 400
    payload = analytics.build_dashboard_payload(sales, customers, website)
    payload["_conn"] = conn
    payload["_mode"] = "dataframe"
    payload["_sales_rows"] = len(sales)
    CacheLayer.set(cache_key, payload, ttl=30)
    return _json_response(payload)


@api_bp.route("/tables")
@login_required
def api_tables():
    conn_name = request.args.get("conn", "demo")
    try:
        return jsonify(db_connector.list_tables(conn_name))
    except ValueError:
        return jsonify([])


@api_bp.route("/table/<table_name>")
@login_required
def api_table_meta(table_name: str):
    if not _TABLE_RE.match(table_name):
        return jsonify({"error": "Invalid table name"}), 400
    conn = request.args.get("conn", "demo")
    return jsonify(db_connector.get_table_info(conn, table_name))


@api_bp.route("/query", methods=["POST"])
@login_required
@limiter.limit("10/minute")
def api_custom_query():
    data = request.get_json(force=True)
    conn = data.get("connection", "demo")
    sql = data.get("sql", "")
    if not sql.strip():
        return jsonify({"error": "Empty query"}), 400

    if Config.SQL_READ_ONLY and _DANGEROUS_SQL_RE.search(sql):
        return jsonify({"error": "Write operations are not allowed in read-only mode"}), 403

    try:
        df = db_connector.execute_query(conn, sql)
        limited = df.head(Config.SQL_MAX_ROWS)
        return _json_response(
            {
                "columns": list(limited.columns),
                "rows": limited.to_dict(orient="records"),
                "row_count": len(df),
                "truncated": len(df) > Config.SQL_MAX_ROWS,
            }
        )
    except Exception:
        logger.warning("Query failed")
        return jsonify({"error": "Query execution failed"}), 400


@api_bp.route("/data/<table_name>")
@login_required
def api_table_data(table_name: str):
    if not _TABLE_RE.match(table_name):
        return jsonify({"error": "Invalid table name"}), 400
    conn = request.args.get("conn", "demo")
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 100, type=int), 500)
    sort = request.args.get("sort", None)
    search = request.args.get("search", None)
    if conn == "demo":
        df = _get_cached(table_name)
    else:
        try:
            df = db_connector.execute_query(conn, f"SELECT * FROM {table_name}")  # noqa: S608
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
    if search:
        escaped = re.escape(search)
        mask = df.apply(lambda col: col.astype(str).str.contains(escaped, case=False, na=False)).any(axis=1)
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


@api_bp.route("/connect", methods=["POST"])
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
    except Exception as e:
        logger.error("Connection failed for '%s': %s", name, e)
        return jsonify({"error": f"Database connection failed: {e}"}), 400


@api_bp.route("/disconnect", methods=["POST"])
@login_required
@limiter.limit("10/minute")
def api_disconnect():
    data = request.get_json(force=True)
    name = data.get("name", "")
    if not name:
        return jsonify({"error": "name required"}), 400
    if name == "demo":
        return jsonify({"error": "Cannot disconnect demo database"}), 400
    removed = db_connector.disconnect(name)
    _invalidate_cache()
    if removed:
        logger.info("Database '%s' disconnected", name)
        return jsonify({"success": True, "message": f"Disconnected from '{name}'"})
    return jsonify({"error": f"Connection '{name}' not found"}), 404


@api_bp.route("/connections", methods=["GET"])
@login_required
def api_list_connections():
    return jsonify(db_connector.list_connections())


@api_bp.route("/custom-query", methods=["POST"])
@login_required
@limiter.limit("30/minute")
def api_custom_query2():
    data = request.get_json(force=True)
    conn = data.get("connection", "demo")
    sql = data.get("sql", "")
    if not sql:
        return jsonify({"error": "SQL query required"}), 400
    if _DANGEROUS_SQL_RE.search(sql):
        return jsonify({"error": "Only SELECT queries are allowed"}), 403
    if Config.SQL_READ_ONLY and not sql.strip().upper().startswith("SELECT"):
        return jsonify({"error": "Only SELECT queries are allowed in read-only mode"}), 403
    try:
        df = db_connector.execute_query(conn, sql)
        return jsonify({"columns": list(df.columns), "rows": df.to_dict(orient="records")})
    except Exception as e:
        logger.error("Query error: %s", e)
        return jsonify({"error": str(e)}), 400


@api_bp.route("/filter", methods=["POST"])
@login_required
@limiter.limit("30/minute")
def api_filter():
    data = request.get_json(force=True)
    table = data.get("table", "sales")
    filters = data.get("filters", {})
    date_start = data.get("date_start")
    date_end = data.get("date_end")
    conn = data.get("conn", _active_conn.get(session.get("user", "anonymous"), "demo"))
    if not _TABLE_RE.match(table):
        return jsonify({"error": "Invalid table name"}), 400
    if conn == "demo":
        df = _get_cached(table)
    else:
        try:
            df = db_connector.execute_query(conn, f"SELECT * FROM {table}")  # noqa: S608
            df = _normalize_columns(df, "sales")
        except (ValueError, KeyError):
            df = _get_cached(table, "demo")
    for col, val in filters.items():
        if col in df.columns and val:
            if isinstance(val, list):
                df = df[df[col].isin(val)]
            else:
                df = df[df[col].astype(str).str.contains(str(val), case=False, na=False)]
    if "date" in df.columns:
        if date_start:
            df = df[df["date"].astype(str) >= str(date_start)]
        if date_end:
            df = df[df["date"].astype(str) <= str(date_end)]
    kpis = analytics.dp.compute_kpis(df) if "total_revenue" in df.columns else {"record_count": len(df)}
    return _json_response({"kpis": kpis, "row_count": len(df)})


@api_bp.route("/export/<table_name>", methods=["GET"])
@login_required
@limiter.limit("10/minute")
def api_export_csv(table_name: str):
    if not _TABLE_RE.match(table_name):
        return jsonify({"error": "Invalid table name"}), 400
    conn = request.args.get("conn", _active_conn.get(session.get("user", "anonymous"), "demo"))
    try:
        if conn == "demo":
            df = _get_cached(table_name)
        else:
            df = db_connector.execute_query(conn, f"SELECT * FROM {table_name}")  # noqa: S608
            df = _normalize_columns(df, table_name)
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    csv_data = df.to_csv(index=False)
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={table_name}_export.csv"},
    )


@api_bp.route("/export-query", methods=["POST"])
@login_required
@limiter.limit("10/minute")
def api_export_query_csv():
    data = request.get_json(force=True)
    conn = data.get("connection", "demo")
    sql = data.get("sql", "")
    if not sql.strip():
        return jsonify({"error": "Empty query"}), 400
    if _DANGEROUS_SQL_RE.search(sql):
        return jsonify({"error": "Export only supports SELECT queries"}), 400
    try:
        df = db_connector.execute_query(conn, sql)
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    csv_data = df.to_csv(index=False)
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=query_result.csv"},
    )


# ------------------------------------------------------------------
# NEW: Forecasting API
# ------------------------------------------------------------------
@api_bp.route("/forecast", methods=["POST"])
@login_required
@limiter.limit("10/minute")
def api_forecast():
    from .analytics.forecasting import ForecastEngine

    data = request.get_json(force=True)
    if not data:
        return jsonify({"error": "Request body required"}), 400

    conn = data.get("conn", "demo")
    if not isinstance(conn, str) or not conn.strip():
        conn = "demo"

    try:
        periods = int(data.get("periods", 6))
    except (TypeError, ValueError):
        periods = 6
    periods = max(1, min(periods, 24))

    cache_key = f"forecast:{conn}:{periods}"
    cached = CacheLayer.get(cache_key)
    if cached:
        return _json_response(cached)

    try:
        if _use_sql_mode(conn):
            monthly = db_connector.sql_monthly_trends(conn)
        else:
            sales, _, _ = _load_dashboard_data(conn)
            monthly = analytics.monthly_trends(sales)

        result = ForecastEngine.forecast_revenue(monthly, periods)
        CacheLayer.set(cache_key, result, ttl=120)
        return _json_response(result)
    except Exception as e:
        logger.error("Forecast error: %s", e, exc_info=True)
        return jsonify({"error": str(e)}), 400


# ------------------------------------------------------------------
# NEW: Anomaly Detection API
# ------------------------------------------------------------------
@api_bp.route("/anomalies", methods=["POST"])
@login_required
@limiter.limit("10/minute")
def api_anomalies():
    from .analytics.anomaly import AnomalyDetector

    data = request.get_json(force=True)
    conn = data.get("conn", "demo")

    cache_key = f"anomalies:{conn}"
    cached = CacheLayer.get(cache_key)
    if cached:
        return _json_response(cached)

    try:
        if _use_sql_mode(conn):
            monthly = db_connector.sql_monthly_trends(conn)
        else:
            sales, _, _ = _load_dashboard_data(conn)
            monthly = analytics.monthly_trends(sales)

        revenue_anomalies = AnomalyDetector.detect_revenue_anomalies(monthly)

        website_anomalies = {}
        try:
            if _use_sql_mode(conn):
                wa = db_connector.sql_website_summary(conn)
                daily_trend = wa.get("daily_trend", [])
            else:
                _, _, website = _load_dashboard_data(conn)
                wa_summary = analytics.website_summary(website)
                daily_trend = wa_summary.get("daily_trend", [])
            website_anomalies = AnomalyDetector.detect_website_anomalies(daily_trend)
        except Exception:
            logger.debug("Website anomaly detection skipped")

        result = {
            "revenue": revenue_anomalies,
            "website": website_anomalies,
        }
        CacheLayer.set(cache_key, result, ttl=120)
        return _json_response(result)
    except Exception as e:
        logger.error("Anomaly detection error: %s", e, exc_info=True)
        return jsonify({"error": str(e)}), 400


# ------------------------------------------------------------------
# NEW: Report Generation API
# ------------------------------------------------------------------
@api_bp.route("/report/<fmt>", methods=["POST"])
@login_required
@limiter.limit("5/minute")
def api_generate_report(fmt: str):
    if fmt not in ("pdf", "excel"):
        return jsonify({"error": "Format must be 'pdf' or 'excel'"}), 400

    data = request.get_json(force=True) if request.is_json else {}
    conn = data.get("conn", "demo")

    cache_key = f"dashboard:{conn}"
    dashboard_data = CacheLayer.get(cache_key)
    if not dashboard_data:
        try:
            if _use_sql_mode(conn):
                dashboard_data = analytics.build_dashboard_payload_sql(db_connector, conn)
            else:
                sales, customers, website = _load_dashboard_data(conn)
                dashboard_data = analytics.build_dashboard_payload(sales, customers, website)
        except Exception as e:
            return jsonify({"error": str(e)}), 400

    try:
        if fmt == "pdf":
            from .reports.pdf_report import PDFReportGenerator

            pdf_bytes = PDFReportGenerator.generate(dashboard_data)
            return Response(
                pdf_bytes,
                mimetype="application/pdf",
                headers={"Content-Disposition": f"attachment; filename=bi_report_{conn}.pdf"},
            )
        else:
            from .reports.excel_report import ExcelReportGenerator

            excel_bytes = ExcelReportGenerator.generate(dashboard_data)
            return Response(
                excel_bytes,
                mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={"Content-Disposition": f"attachment; filename=bi_report_{conn}.xlsx"},
            )
    except Exception as e:
        logger.error("Report generation error: %s", e, exc_info=True)
        return jsonify({"error": str(e)}), 500


# ------------------------------------------------------------------
# NEW: Natural Language Query API
# ------------------------------------------------------------------
@api_bp.route("/nl-query", methods=["POST"])
@login_required
@limiter.limit("15/minute")
def api_nl_query():
    from .nl_query import NLQueryEngine

    data = request.get_json(force=True)
    query = data.get("query", "").strip()
    conn = data.get("connection", "demo")

    if not query:
        return jsonify({"error": "Query required"}), 400

    result = NLQueryEngine.nl_to_sql(query)

    if result.get("error") and not result.get("sql"):
        return jsonify(result), 400

    if result.get("sql"):
        try:
            df = db_connector.execute_query(conn, result["sql"])
            result["columns"] = list(df.columns)
            result["rows"] = df.head(Config.SQL_MAX_ROWS).to_dict(orient="records")
            result["row_count"] = len(df)
        except Exception as e:
            result["error"] = f"SQL execution failed: {e}"
            return jsonify(result), 400

    return jsonify(result)


# ------------------------------------------------------------------
# NEW: User role API (for frontend role-based rendering)
# ------------------------------------------------------------------
@api_bp.route("/user-role")
@login_required
def api_user_role():
    return jsonify(
        {
            "username": session.get("user", ""),
            "role": session.get("role", "viewer"),
        }
    )


# ------------------------------------------------------------------
# Backward-compat redirects
# ------------------------------------------------------------------
@bp.route("/api/<path:old_path>")
@login_required
def api_redirect(old_path: str):
    return redirect(f"/api/v1/{old_path}")


@bp.route("/api/<path:old_path>", methods=["POST"])
@login_required
def api_redirect_post(old_path: str):
    return redirect(f"/api/v1/{old_path}")


# ------------------------------------------------------------------
# WebSocket events
# ------------------------------------------------------------------
def _ws_auth():
    if "user" not in session:
        disconnect()
        return False
    return True


@socketio.on("connect")
def handle_connect():
    if not _ws_auth():
        return False
    username = session.get("user", "anonymous")
    _online_users[username] = {
        "username": username,
        "role": session.get("role", "viewer"),
        "cursor": None,
    }
    emit("online_users", list(_online_users.values()), broadcast=True)
    logger.info("WebSocket client connected: %s", username)


@socketio.on("disconnect")
def handle_disconnect():
    username = session.get("user", "anonymous")
    _online_users.pop(username, None)
    emit("online_users", list(_online_users.values()), broadcast=True)
    logger.info("WebSocket client disconnected: %s", username)


@socketio.on("cursor_move")
def handle_cursor_move(data):
    if not _ws_auth():
        return
    username = session.get("user", "anonymous")
    if username in _online_users:
        _online_users[username]["cursor"] = data
    emit("cursor_update", {"username": username, "cursor": data}, broadcast=True, include_self=False)


@socketio.on("request_refresh")
def handle_refresh():
    if not _ws_auth():
        return
    conn = _active_conn.get(session.get("user", "anonymous"), "demo")
    _invalidate_cache()

    if _use_sql_mode(conn):
        try:
            payload = analytics.build_dashboard_payload_sql(db_connector, conn)
            payload["_conn"] = conn
            payload["_mode"] = "sql"
        except Exception as e:
            logger.error("WS SQL refresh error for '%s': %s", conn, e, exc_info=True)
            return
    else:
        try:
            sales, customers, website = _load_dashboard_data(conn)
        except Exception as e:
            logger.error("WS refresh error for '%s': %s", conn, e, exc_info=True)
            return
        payload = analytics.build_dashboard_payload(sales, customers, website)
        payload["_conn"] = conn
        payload["_mode"] = "dataframe"

    socketio.emit(
        "dashboard_update",
        json.loads(json.dumps(payload, default=safe_json_serialize)),
    )


def start_realtime_loop():
    global _data_dirty
    interval = Config.REALTIME_INTERVAL
    while True:
        time.sleep(interval)
        if not _data_dirty:
            continue
        _data_dirty = False
        try:
            for user, conn in list(_active_conn.items()):
                try:
                    if _use_sql_mode(conn):
                        payload = analytics.build_dashboard_payload_sql(db_connector, conn)
                        payload["_conn"] = conn
                        payload["_mode"] = "sql"
                    elif conn == "demo":
                        sales = _get_cached("sales")
                        customers = _get_cached("customers")
                        website = _get_cached("website_analytics")
                        payload = analytics.build_dashboard_payload(sales, customers, website)
                        payload["_conn"] = conn
                        payload["_mode"] = "dataframe"
                    else:
                        tables = db_connector.list_tables(conn)
                        sales_qry = "SELECT * FROM sales" if "sales" in tables else None
                        sales = _normalize_columns(
                            db_connector.execute_query(conn, sales_qry) if sales_qry else pd.DataFrame(),
                            "sales",
                        )
                        cust_qry = "SELECT * FROM customers" if "customers" in tables else None
                        customers = _normalize_columns(
                            db_connector.execute_query(conn, cust_qry) if cust_qry else pd.DataFrame(),
                            "customers",
                        )
                        wa_qry = "SELECT * FROM website_analytics" if "website_analytics" in tables else None
                        website = db_connector.execute_query(conn, wa_qry) if wa_qry else pd.DataFrame()
                        payload = analytics.build_dashboard_payload(sales, customers, website)
                        payload["_conn"] = conn
                        payload["_mode"] = "dataframe"
                    socketio.emit(
                        "dashboard_update",
                        json.loads(json.dumps(payload, default=safe_json_serialize)),
                    )
                except Exception as exc:
                    logger.error("Realtime error for '%s' (%s): %s", user, conn, exc)
        except Exception as exc:
            logger.error("Realtime loop error: %s", exc)
