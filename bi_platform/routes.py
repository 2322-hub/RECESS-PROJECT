import json
import re
import time
from io import BytesIO

import pandas as pd
from flask import Blueprint, Response, jsonify, redirect, render_template, request, session
from flask_socketio import disconnect

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


def _get_dashboard_payload(conn: str) -> dict:
    """Build the same dashboard payload used by the UI for report exports."""
    if _use_sql_mode(conn):
        payload = analytics.build_dashboard_payload_sql(db_connector, conn)
        payload["_conn"] = conn
        payload["_mode"] = "sql"
        payload["_sales_rows"] = _row_count_cache.get(f"{conn}:sales", 0)
        return payload

    sales, customers, website = _load_dashboard_data(conn)
    payload = analytics.build_dashboard_payload(sales, customers, website)
    payload["_conn"] = conn
    payload["_mode"] = "dataframe"
    payload["_sales_rows"] = len(sales)
    return payload


def _build_report_dataframe(payload: dict) -> pd.DataFrame:
    rows = []
    kpis = payload.get("kpis", {}) or {}
    rows.extend(
        [
            {"section": "Metadata", "metric": "Connection", "value": payload.get("_conn", "demo")},
            {"section": "Metadata", "metric": "Mode", "value": payload.get("_mode", "dataframe")},
            {"section": "Metadata", "metric": "Sales Rows", "value": payload.get("_sales_rows", 0)},
            {"section": "KPI", "metric": "Total Revenue", "value": kpis.get("total_revenue")},
            {"section": "KPI", "metric": "Total Profit", "value": kpis.get("total_profit")},
            {"section": "KPI", "metric": "Profit Margin", "value": kpis.get("profit_margin")},
            {"section": "KPI", "metric": "Total Cost", "value": kpis.get("total_cost")},
            {"section": "KPI", "metric": "Record Count", "value": kpis.get("record_count")},
        ]
    )

    for item in payload.get("revenue_breakdown", {}).get("region", []) or []:
        rows.append({"section": "Revenue Breakdown", "metric": f"Region: {item.get('label', '')}", "value": item.get("value")})
    for item in payload.get("revenue_breakdown", {}).get("product_category", []) or []:
        rows.append({"section": "Revenue Breakdown", "metric": f"Category: {item.get('label', '')}", "value": item.get("value")})
    for item in payload.get("revenue_breakdown", {}).get("customer_segment", []) or []:
        rows.append({"section": "Revenue Breakdown", "metric": f"Segment: {item.get('label', '')}", "value": item.get("value")})

    return pd.DataFrame(rows)


bp = Blueprint("main", __name__)
api_bp = Blueprint("api", __name__, url_prefix="/api/v1")

db_connector = DatabaseConnector()
analytics = AnalyticsEngine()

db_connector.connect_demo_sqlite()

# Auto-connect MySQL/external DB from DATABASE_URL if configured
_default_conn = "demo"
_db_url = Config.SQLALCHEMY_DATABASE_URI
if _db_url and not _db_url.startswith("sqlite"):
    try:
        db_connector.connect("bi_platform", _db_url)
        _default_conn = "bi_platform"
    except Exception as _e:
        logger.warning("Could not auto-connect DATABASE_URL: %s", _e)

_df_cache: dict[str, pd.DataFrame] = {}
_active_conn: dict[str, str] = {}  # session_id -> connection name
_row_count_cache: dict[str, int] = {}  # conn -> row count
_data_dirty: bool = True  # flag for realtime loop to push updates

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


def _normalize_columns(df: pd.DataFrame, table_type: str = "sales") -> pd.DataFrame:
    """Map real-DB column names to the schema expected by AnalyticsEngine."""
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


def _use_sql_mode(conn: str) -> bool:
    """Check if the connection should use SQL-only aggregation (no full DataFrame load).

    Always returns True for non-SQLite connections (PostgreSQL, MySQL, etc.)
    to avoid loading millions of rows into memory.
    For SQLite demo, checks if sales table exceeds MAX_ROWS_IN_MEMORY.
    """
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
# Page routes (unchanged)
# ------------------------------------------------------------------
@bp.route("/")
@login_required
def index():
    tables = db_connector.list_tables(_default_conn)
    return render_template("dashboard.html", tables=tables, default_conn=_default_conn)


# ------------------------------------------------------------------
# API v1 routes
# ------------------------------------------------------------------
def _load_dashboard_data(conn: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load sales, customers, and website DataFrames for a given connection.

    Raises on failure so the caller can return an appropriate error response.
    """
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

    logger.info(
        "Loaded '%s': sales=%d rows, customers=%d rows, website=%d rows, sales_cols=%s",
        conn,
        len(sales),
        len(customers),
        len(website),
        list(sales.columns) if not sales.empty else [],
    )
    return sales, customers, website


@api_bp.route("/dashboard-data")
@login_required
@limiter.limit("30/minute")
def api_dashboard_data():
    conn = request.args.get("conn", "demo")
    _active_conn[session.get("user", "anonymous")] = conn

    try:
        payload = _get_dashboard_payload(conn)
        return _json_response(payload)
    except Exception as e:
        logger.error("Dashboard data error for '%s': %s", conn, e, exc_info=True)
        return jsonify({"error": str(e), "conn": conn}), 400


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


@api_bp.route("/connect", methods=["POST"])
@login_required
@limiter.limit("5/minute")
def api_connect_db():
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
    from .config import Config

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


@api_bp.route("/report/export/csv")
@login_required
def api_report_export_csv():
    conn = request.args.get("conn", _active_conn.get(session.get("user", "anonymous"), "demo"))
    try:
        payload = _get_dashboard_payload(conn)
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    csv_data = _build_report_dataframe(payload).to_csv(index=False)
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=report_export.csv"},
    )


@api_bp.route("/report/export/excel")
@login_required
def api_report_export_excel():
    conn = request.args.get("conn", _active_conn.get(session.get("user", "anonymous"), "demo"))
    try:
        payload = _get_dashboard_payload(conn)
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        _build_report_dataframe(payload).to_excel(writer, sheet_name="Report", index=False)
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=report_export.xlsx"},
    )


@api_bp.route("/report/export/pdf")
@login_required
def api_report_export_pdf():
    conn = request.args.get("conn", _active_conn.get(session.get("user", "anonymous"), "demo"))
    return redirect(f"/api/v1/report/preview?conn={conn}&print=1")


@api_bp.route("/report/preview")
@login_required
def api_report_preview():
    conn = request.args.get("conn", _active_conn.get(session.get("user", "anonymous"), "demo"))
    print_mode = request.args.get("print", "0") == "1"
    try:
        payload = _get_dashboard_payload(conn)
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    report_rows = _build_report_dataframe(payload).to_dict(orient="records")
    return render_template("report_preview.html", report_rows=report_rows, conn=conn, print_mode=print_mode)


# ------------------------------------------------------------------
# Backward-compat redirects (old /api/ paths -> /api/v1/)
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
# WebSocket events for real-time updates
# ------------------------------------------------------------------
def _ws_auth():
    """Verify WebSocket client is authenticated."""
    if "user" not in session:
        disconnect()
        return False
    return True


@socketio.on("connect")
def handle_connect():
    if not _ws_auth():
        return
    logger.info("WebSocket client connected")


@socketio.on("request_refresh")
def handle_refresh():
    if not _ws_auth():
        return
    conn = _active_conn.get(session.get("user", "anonymous"), "demo")
    _invalidate_cache()

    # SQL-only mode for large datasets
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
    """Push dashboard updates on a schedule (called from a background thread)."""
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
                    # SQL-only mode for large datasets
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
