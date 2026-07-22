import pandas as pd
from sqlalchemy import create_engine, inspect, text

from ..config import Config


class DatabaseConnector:
    """Handles connections to multiple database backends and metadata discovery."""

    def __init__(self):
        self._engines: dict[str, object] = {}
        self._inspector_cache: dict[str, object] = {}

    def connect(self, name: str, connection_string: str) -> dict:
        """Register a named database connection via SQLAlchemy URL."""
        engine = create_engine(
            connection_string,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
        )
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        self._engines[name] = engine
        return {"status": "ok", "name": name, "dialect": engine.dialect.name}

    def connect_demo_sqlite(self, path: str | None = None) -> dict:
        """Create / open the built-in SQLite demo database and seed it."""
        path = path or "bi_platform_demo.db"
        engine = create_engine(f"sqlite:///{path}")
        self._engines["demo"] = engine
        self._seed_demo_data(engine)
        return {"status": "ok", "name": "demo", "dialect": "sqlite"}

    # ------------------------------------------------------------------
    # Metadata helpers
    # ------------------------------------------------------------------
    def list_connections(self) -> list[str]:
        return list(self._engines.keys())

    def disconnect(self, name: str) -> bool:
        """Remove a named connection and dispose its engine. Returns True if found."""
        engine = self._engines.pop(name, None)
        if engine is None:
            return False
        engine.dispose()
        return True

    def list_tables(self, conn_name: str) -> list[str]:
        engine = self._engines.get(conn_name)
        if engine is None:
            raise ValueError(f"No connection named '{conn_name}'")
        return inspect(engine).get_table_names()

    def get_columns(self, conn_name: str, table: str) -> list[dict]:
        engine = self._engines[conn_name]
        cols = inspect(engine).get_columns(table)
        return [{"name": c["name"], "type": str(c["type"])} for c in cols]

    def get_table_info(self, conn_name: str, table: str) -> dict:
        engine = self._engines[conn_name]
        with engine.connect() as conn:
            count = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()  # noqa: S608
        columns = self.get_columns(conn_name, table)
        return {"table": table, "row_count": count, "columns": columns}

    # ------------------------------------------------------------------
    # Query execution
    # ------------------------------------------------------------------
    def execute_query(self, conn_name: str, sql: str, params: dict | None = None) -> pd.DataFrame:
        engine = self._engines.get(conn_name)
        if engine is None:
            raise ValueError(f"No connection named '{conn_name}'")
        with engine.connect() as conn:
            result = conn.execution_options(timeout=Config.QUERY_TIMEOUT).execute(text(sql), params or {})
            df = pd.DataFrame(result.fetchall(), columns=result.keys())
        return df

    def execute_query_chunked(self, conn_name: str, sql: str, params: dict | None = None):
        """Yield DataFrame chunks for large result sets."""
        engine = self._engines[conn_name]
        with engine.connect() as conn:
            result = conn.execution_options(stream_results=True).execute(text(sql), params or {})
            while True:
                chunk = result.fetchmany(Config.CHUNK_SIZE)
                if not chunk:
                    break
                yield pd.DataFrame(chunk, columns=result.keys())

    # ------------------------------------------------------------------
    # SQL-side aggregation helpers (for large datasets)
    # ------------------------------------------------------------------
    def sql_kpis(self, conn_name: str, table: str = "sales") -> dict:
        """Compute KPIs entirely in SQL — never loads full table into memory."""
        engine = self._engines.get(conn_name)
        if engine is None:
            raise ValueError(f"No connection named '{conn_name}'")
        sql = text(f"""
            SELECT
                COUNT(*)                           AS record_count,
                COALESCE(SUM(total_revenue), 0)    AS total_revenue,
                COALESCE(AVG(total_revenue), 0)    AS avg_revenue,
                COALESCE(SUM(cost), 0)             AS total_cost,
                COALESCE(SUM(profit), 0)           AS total_profit,
                CASE WHEN SUM(total_revenue) > 0
                     THEN ROUND(CAST(SUM(profit) / SUM(total_revenue) * 100 AS NUMERIC), 2)
                     ELSE 0 END                    AS profit_margin
            FROM {table}
        """)  # noqa: S608
        with engine.connect() as conn:
            row = conn.execute(sql).fetchone()
        return {
            "record_count": int(row[0]),
            "total_revenue": round(float(row[1]), 2),
            "avg_revenue": round(float(row[2]), 2),
            "total_cost": round(float(row[3]), 2),
            "total_profit": round(float(row[4]), 2),
            "profit_margin": round(float(row[5]), 2),
        }

    def sql_group_by_sum(self, conn_name: str, group_col: str, value_col: str, table: str = "sales") -> list[dict]:
        """GROUP BY aggregation in SQL."""
        engine = self._engines[conn_name]
        allowed = {
            "region", "product_category", "product_name", "customer_segment",
            "date", "cost", "profit", "quantity", "total_revenue",
        }
        if group_col not in allowed or value_col not in allowed:
            raise ValueError(f"Column not allowed: {group_col} or {value_col}")
        sql = text(f"""
            SELECT {group_col} AS label, SUM({value_col}) AS value
            FROM {table}
            GROUP BY {group_col}
            ORDER BY value DESC
        """)  # noqa: S608
        with engine.connect() as conn:
            rows = conn.execute(sql).fetchall()
        return [{"label": str(r[0]), "value": round(float(r[1]), 2)} for r in rows]

    def sql_top_n(
        self, conn_name: str, group_col: str, value_col: str, n: int = 10, table: str = "sales"
    ) -> list[dict]:
        """Top-N by value using SQL."""
        engine = self._engines[conn_name]
        sql = text(f"""
            SELECT {group_col} AS label, SUM({value_col}) AS value
            FROM {table}
            GROUP BY {group_col}
            ORDER BY value DESC
            LIMIT :n
        """)  # noqa: S608
        with engine.connect() as conn:
            rows = conn.execute(sql, {"n": n}).fetchall()
        return [{"label": str(r[0]), "value": round(float(r[1]), 2)} for r in rows]

    def sql_monthly_trends(self, conn_name: str, table: str = "sales") -> list[dict]:
        """Monthly revenue/profit trends computed in SQL."""
        engine = self._engines[conn_name]
        sql = text(f"""
            SELECT
                SUBSTR(date, 1, 7)                 AS date,
                SUM(total_revenue)                  AS revenue,
                COALESCE(SUM(profit), 0)            AS profit,
                COALESCE(SUM(quantity), 0)          AS quantity
            FROM {table}
            GROUP BY SUBSTR(date, 1, 7)
            ORDER BY date
        """)  # noqa: S608
        with engine.connect() as conn:
            rows = conn.execute(sql).fetchall()
        return [
            {"date": str(r[0]), "revenue": round(float(r[1]), 2),
             "profit": round(float(r[2]), 2), "quantity": int(r[3])}
            for r in rows
        ]

    def sql_regional_comparison(self, conn_name: str, table: str = "sales") -> list[dict]:
        """Regional comparison in SQL."""
        engine = self._engines[conn_name]
        sql = text(f"""
            SELECT
                region,
                SUM(profit)                        AS profit,
                COUNT(*)                           AS orders,
                SUM(total_revenue)                 AS revenue,
                AVG(total_revenue)                 AS avg_order_value
            FROM {table}
            GROUP BY region
            ORDER BY revenue DESC
        """)  # noqa: S608
        with engine.connect() as conn:
            rows = conn.execute(sql).fetchall()
        return [
            {
                "region": str(r[0]),
                "profit": round(float(r[1]), 2),
                "orders": int(r[2]),
                "revenue": round(float(r[3]), 2),
                "avg_order_value": round(float(r[4]), 2),
            }
            for r in rows
        ]

    def sql_product_performance(self, conn_name: str, table: str = "sales") -> list[dict]:
        """Product performance in SQL."""
        engine = self._engines[conn_name]
        sql = text(f"""
            SELECT
                product_category,
                product_name,
                SUM(total_revenue)                 AS total_revenue,
                COALESCE(SUM(profit), 0)           AS profit,
                COALESCE(SUM(quantity), 0)         AS quantity
            FROM {table}
            GROUP BY product_category, product_name
            ORDER BY total_revenue DESC
        """)  # noqa: S608
        with engine.connect() as conn:
            rows = conn.execute(sql).fetchall()
        return [
            {
                "product_category": str(r[0]),
                "product_name": str(r[1]),
                "total_revenue": round(float(r[2]), 2),
                "profit": round(float(r[3]), 2),
                "quantity": int(r[4]),
            }
            for r in rows
        ]

    def sql_website_summary(self, conn_name: str, table: str = "website_analytics") -> dict:
        """Website analytics summary in SQL."""
        engine = self._engines[conn_name]
        sql = text(f"""
            SELECT
                COALESCE(SUM(page_views), 0)              AS total_page_views,
                COALESCE(SUM(unique_visitors), 0)         AS total_unique_visitors,
                COALESCE(AVG(bounce_rate), 0)              AS avg_bounce_rate,
                COALESCE(AVG(avg_session_duration), 0)     AS avg_session_duration,
                COALESCE(SUM(conversions), 0)              AS total_conversions,
                COALESCE(SUM(revenue), 0)                  AS total_revenue,
                CASE WHEN SUM(unique_visitors) > 0
                     THEN ROUND(CAST(SUM(conversions) AS NUMERIC) / SUM(unique_visitors) * 100, 2)
                     ELSE 0 END                            AS conversion_rate
            FROM {table}
        """)  # noqa: S608
        with engine.connect() as conn:
            row = conn.execute(sql).fetchone()
        trend_sql = text(f"""
            SELECT date,
                   SUM(page_views)    AS page_views,
                   SUM(unique_visitors) AS visitors,
                   SUM(revenue)       AS revenue
            FROM {table}
            GROUP BY date
            ORDER BY date
        """)  # noqa: S608
        with engine.connect() as conn:
            trend_rows = conn.execute(trend_sql).fetchall()
        return {
            "total_page_views": int(row[0]),
            "total_unique_visitors": int(row[1]),
            "avg_bounce_rate": round(float(row[2]) * 100, 2),
            "avg_session_duration": round(float(row[3]), 2),
            "total_conversions": int(row[4]),
            "total_revenue": round(float(row[5]), 2),
            "conversion_rate": round(float(row[6]), 2),
            "daily_trend": [
                {"date": str(r[0]), "page_views": int(r[1]),
                 "visitors": int(r[2]), "revenue": round(float(r[3]), 2)}
                for r in trend_rows
            ],
        }

    def sql_customer_insights(self, conn_name: str, table: str = "customers") -> dict:
        """Customer insights in SQL."""
        engine = self._engines[conn_name]
        sql = text(f"""
            SELECT
                COUNT(*)                           AS total_customers,
                COALESCE(AVG(lifetime_value), 0)   AS avg_lifetime_value,
                COALESCE(SUM(lifetime_value), 0)   AS total_lifetime_value,
                COALESCE(AVG(orders_count), 0)     AS avg_orders
            FROM {table}
        """)  # noqa: S608
        with engine.connect() as conn:
            row = conn.execute(sql).fetchone()
        result = {
            "total_customers": int(row[0]),
            "avg_lifetime_value": round(float(row[1]), 2),
            "total_lifetime_value": round(float(row[2]), 2),
            "avg_orders": round(float(row[3]), 2),
        }
        seg_sql = text(f"""
            SELECT segment, COUNT(*) AS count,
                   AVG(lifetime_value) AS avg_ltv,
                   SUM(lifetime_value) AS total_ltv
            FROM {table}
            GROUP BY segment
        """)  # noqa: S608
        with engine.connect() as conn:
            seg_rows = conn.execute(seg_sql).fetchall()
        result["by_segment"] = [
            {"segment": str(r[0]), "count": int(r[1]),
             "avg_ltv": round(float(r[2]), 2), "total_ltv": round(float(r[3]), 2)}
            for r in seg_rows
        ]
        reg_sql = text(f"""
            SELECT region, COUNT(*) AS count,
                   AVG(lifetime_value) AS avg_ltv
            FROM {table}
            GROUP BY region
        """)  # noqa: S608
        with engine.connect() as conn:
            reg_rows = conn.execute(reg_sql).fetchall()
        result["by_region"] = [
            {"region": str(r[0]), "count": int(r[1]),
             "avg_ltv": round(float(r[2]), 2)}
            for r in reg_rows
        ]
        return result

    def sql_revenue_breakdown(self, conn_name: str, table: str = "sales") -> dict:
        """Revenue breakdown by region/category/segment in SQL."""
        engine = self._engines[conn_name]
        result = {}
        for group in ("region", "product_category", "customer_segment"):
            sql = text(f"""
                SELECT {group} AS label, SUM(total_revenue) AS value
                FROM {table}
                GROUP BY {group}
                ORDER BY value DESC
            """)  # noqa: S608
            with engine.connect() as conn:
                rows = conn.execute(sql).fetchall()
            result[group] = [{"label": str(r[0]), "value": round(float(r[1]), 2)} for r in rows]
        return result

    def sql_correlation_matrix(self, df: "pd.DataFrame") -> dict:
        """Compute correlation matrix from a sample DataFrame."""
        numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
        if len(numeric_cols) < 2:
            return {}
        corr = df[numeric_cols].corr().round(4)
        return {
            "columns": numeric_cols,
            "matrix": corr.values.tolist(),
        }

    # ------------------------------------------------------------------
    # Demo data seeding
    # ------------------------------------------------------------------
    @staticmethod
    def _seed_demo_data(engine):
        import numpy as np

        with engine.begin() as conn:
            # Check if already seeded
            try:
                cnt = conn.execute(text("SELECT COUNT(*) FROM sales")).scalar()
                if cnt > 0:
                    return
            except Exception:  # noqa: S110
                pass

            conn.execute(
                text("""
                CREATE TABLE IF NOT EXISTS sales (
                    id INTEGER PRIMARY KEY,
                    date TEXT,
                    region TEXT,
                    product_category TEXT,
                    product_name TEXT,
                    quantity INTEGER,
                    unit_price REAL,
                    total_revenue REAL,
                    cost REAL,
                    profit REAL,
                    customer_segment TEXT
                )
            """)
            )
            conn.execute(
                text("""
                CREATE TABLE IF NOT EXISTS customers (
                    id INTEGER PRIMARY KEY,
                    name TEXT,
                    email TEXT,
                    region TEXT,
                    signup_date TEXT,
                    lifetime_value REAL,
                    orders_count INTEGER,
                    segment TEXT
                )
            """)
            )
            conn.execute(
                text("""
                CREATE TABLE IF NOT EXISTS website_analytics (
                    id INTEGER PRIMARY KEY,
                    date TEXT,
                    page_views INTEGER,
                    unique_visitors INTEGER,
                    bounce_rate REAL,
                    avg_session_duration REAL,
                    conversions INTEGER,
                    revenue REAL
                )
            """)
            )

        rng = np.random.default_rng(42)
        regions = ["North", "South", "East", "West"]
        categories = ["Electronics", "Clothing", "Food", "Furniture"]
        products = ["Widget A", "Widget B", "Gadget X", "Gadget Y", "Service Pro", "Basic Plan"]
        segments = ["Enterprise", "SMB", "Consumer"]

        # Sales
        n_sales = 5000
        dates = pd.date_range("2024-01-01", periods=365, freq="D")
        sales_rows = []
        for i in range(1, n_sales + 1):
            d = str(dates[rng.integers(0, len(dates))].date())
            cat = rng.choice(categories)
            prod = rng.choice(products)
            qty = int(rng.integers(1, 50))
            price = round(float(rng.uniform(5000, 500000)), 2)
            total = round(qty * price, 2)
            cost = round(total * rng.uniform(0.3, 0.8), 2)
            sales_rows.append(
                (
                    i,
                    d,
                    rng.choice(regions),
                    cat,
                    prod,
                    qty,
                    price,
                    total,
                    cost,
                    round(total - cost, 2),
                    rng.choice(segments),
                )
            )
        with engine.begin() as conn:
            conn.execute(
                text("""
                INSERT INTO sales (id, date, region, product_category, product_name,
                    quantity, unit_price, total_revenue, cost, profit, customer_segment)
                VALUES (:id, :date, :region, :category, :product, :qty, :price, :total, :cost, :profit, :segment)
            """),
                [
                    {
                        "id": r[0],
                        "date": r[1],
                        "region": r[2],
                        "category": r[3],
                        "product": r[4],
                        "qty": r[5],
                        "price": r[6],
                        "total": r[7],
                        "cost": r[8],
                        "profit": r[9],
                        "segment": r[10],
                    }
                    for r in sales_rows
                ],
            )

        # Customers
        cust_rows = []
        for i in range(1, 201):
            sd = str(dates[rng.integers(0, len(dates))].date())
            cust_rows.append(
                {
                    "id": i,
                    "name": f"Customer_{i}",
                    "email": f"customer{i}@example.com",
                    "region": rng.choice(regions),
                    "signup_date": sd,
                    "ltv": round(float(rng.uniform(500000, 50000000)), 2),
                    "orders": int(rng.integers(1, 100)),
                    "segment": rng.choice(segments),
                }
            )
        with engine.begin() as conn:
            conn.execute(
                text("""
                INSERT INTO customers (id, name, email, region, signup_date, lifetime_value, orders_count, segment)
                VALUES (:id, :name, :email, :region, :signup_date, :ltv, :orders, :segment)
            """),
                cust_rows,
            )

        # Website analytics
        analytics_rows = []
        for i, d in enumerate(dates[:180], 1):
            pv = int(rng.integers(500, 5000))
            uv = int(pv * rng.uniform(0.5, 0.9))
            analytics_rows.append(
                {
                    "id": i,
                    "date": str(d.date()),
                    "page_views": pv,
                    "unique_visitors": uv,
                    "bounce_rate": round(float(rng.uniform(0.2, 0.7)), 4),
                    "avg_session_duration": round(float(rng.uniform(30, 300)), 2),
                    "conversions": int(rng.integers(0, 50)),
                    "revenue": round(float(rng.uniform(0, 20000000)), 2),
                }
            )
        with engine.begin() as conn:
            conn.execute(
                text("""
                INSERT INTO website_analytics
                    (id, date, page_views, unique_visitors,
                     bounce_rate, avg_session_duration, conversions, revenue)
                VALUES (:id, :date, :page_views, :unique_visitors,
                        :bounce_rate, :avg_session_duration,
                        :conversions, :revenue)
            """),
                analytics_rows,
            )
