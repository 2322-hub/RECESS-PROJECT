
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
            connect_args={"timeout": Config.QUERY_TIMEOUT},
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
            result = conn.execute(text(sql), params or {})
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

            conn.execute(text("""
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
            """))
            conn.execute(text("""
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
            """))
            conn.execute(text("""
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
            """))

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
            price = round(float(rng.uniform(5, 500)), 2)
            total = round(qty * price, 2)
            cost = round(total * rng.uniform(0.3, 0.8), 2)
            sales_rows.append((
                i, d, rng.choice(regions), cat, prod, qty, price,
                total, cost, round(total - cost, 2), rng.choice(segments),
            ))
        with engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO sales (id, date, region, product_category, product_name,
                    quantity, unit_price, total_revenue, cost, profit, customer_segment)
                VALUES (:id, :date, :region, :category, :product, :qty, :price, :total, :cost, :profit, :segment)
            """), [
                {"id": r[0], "date": r[1], "region": r[2], "category": r[3], "product": r[4],
                 "qty": r[5], "price": r[6], "total": r[7], "cost": r[8], "profit": r[9], "segment": r[10]}
                for r in sales_rows
            ])

        # Customers
        cust_rows = []
        for i in range(1, 201):
            sd = str(dates[rng.integers(0, len(dates))].date())
            cust_rows.append({
                "id": i,
                "name": f"Customer_{i}",
                "email": f"customer{i}@example.com",
                "region": rng.choice(regions),
                "signup_date": sd,
                "ltv": round(float(rng.uniform(100, 10000)), 2),
                "orders": int(rng.integers(1, 100)),
                "segment": rng.choice(segments),
            })
        with engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO customers (id, name, email, region, signup_date, lifetime_value, orders_count, segment)
                VALUES (:id, :name, :email, :region, :signup_date, :ltv, :orders, :segment)
            """), cust_rows)

        # Website analytics
        analytics_rows = []
        for i, d in enumerate(dates[:180], 1):
            pv = int(rng.integers(500, 5000))
            uv = int(pv * rng.uniform(0.5, 0.9))
            analytics_rows.append({
                "id": i,
                "date": str(d.date()),
                "page_views": pv,
                "unique_visitors": uv,
                "bounce_rate": round(float(rng.uniform(0.2, 0.7)), 4),
                "avg_session_duration": round(float(rng.uniform(30, 300)), 2),
                "conversions": int(rng.integers(0, 50)),
                "revenue": round(float(rng.uniform(0, 5000)), 2),
            })
        with engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO website_analytics
                    (id, date, page_views, unique_visitors,
                     bounce_rate, avg_session_duration, conversions, revenue)
                VALUES (:id, :date, :page_views, :unique_visitors,
                        :bounce_rate, :avg_session_duration,
                        :conversions, :revenue)
            """), analytics_rows)
