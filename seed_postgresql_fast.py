"""Seed PostgreSQL with large-scale data for BI Platform demo (fast version).

Generates:
- 2,000,000 sales rows
- 50,000 customer rows
- 1,000 days of website analytics

Usage: python seed_postgresql_fast.py
"""

import time

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text

DB_URL = "postgresql+psycopg2://postgres:root@localhost:5432/bi_platform"
engine = create_engine(DB_URL, pool_size=5)

N_SALES = 2_000_000
N_CUSTOMERS = 50_000
N_WEB_DAYS = 1_000

regions = np.array(["North", "South", "East", "West", "Central", "Pacific", "Mountain"])
categories = np.array(["Electronics", "Clothing", "Food", "Furniture", "Software", "Hardware"])
products = np.array(
    [
        "Widget A",
        "Widget B",
        "Gadget X",
        "Gadget Y",
        "Service Pro",
        "Basic Plan",
        "Enterprise Suite",
        "Cloud Storage",
        "Analytics Tool",
        "Security Shield",
        "Dev Toolkit",
        "Mobile App",
    ]
)
segments = np.array(["Enterprise", "SMB", "Consumer", "Government", "Education"])

rng = np.random.default_rng(42)
dates = pd.date_range("2020-01-01", "2025-12-31", freq="D")

print("Dropping existing tables...")
with engine.begin() as conn:
    for tbl in ("sales", "customers", "website_analytics"):
        conn.execute(text(f"DROP TABLE IF EXISTS {tbl}"))  # noqa: S608

print("Creating tables...")
with engine.begin() as conn:
    conn.execute(
        text("""
        CREATE TABLE sales (
            id SERIAL PRIMARY KEY,
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
        CREATE TABLE customers (
            id SERIAL PRIMARY KEY,
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
        CREATE TABLE website_analytics (
            id SERIAL PRIMARY KEY,
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


def seed_sales(n: int):
    print(f"Seeding {n:,} sales rows (vectorized)...")
    start = time.time()

    date_arr = np.array([str(d.date()) for d in dates])
    sale_dates = rng.choice(date_arr, size=n)

    sale_regions = rng.choice(regions, size=n)
    sale_categories = rng.choice(categories, size=n)
    sale_products = rng.choice(products, size=n)
    sale_segments = rng.choice(segments, size=n)
    sale_qty = rng.integers(1, 100, size=n)
    sale_price = np.round(rng.uniform(10, 50000, size=n), 2)
    sale_total = np.round(sale_qty * sale_price, 2)
    sale_cost_pct = rng.uniform(0.3, 0.85, size=n)
    sale_cost = np.round(sale_total * sale_cost_pct, 2)
    sale_profit = np.round(sale_total - sale_cost, 2)

    df = pd.DataFrame(
        {
            "date": sale_dates,
            "region": sale_regions,
            "product_category": sale_categories,
            "product_name": sale_products,
            "quantity": sale_qty.astype(int),
            "unit_price": sale_price,
            "total_revenue": sale_total,
            "cost": sale_cost,
            "profit": sale_profit,
            "customer_segment": sale_segments,
        }
    )

    chunk = 200_000
    for i in range(0, n, chunk):
        df.iloc[i : i + chunk].to_sql("sales", engine, if_exists="append", index=False)
        print(f"  {min(i + chunk, n):>10,} / {n:,} rows")

    print(f"Sales done in {time.time() - start:.1f}s")


def seed_customers(n: int):
    print(f"Seeding {n:,} customers (vectorized)...")
    start = time.time()

    date_arr = np.array([str(d.date()) for d in dates])
    cust_dates = rng.choice(date_arr, size=n)

    df = pd.DataFrame(
        {
            "name": [f"Customer_{i}" for i in range(1, n + 1)],
            "email": [f"customer{i}@example.com" for i in range(1, n + 1)],
            "region": rng.choice(regions, size=n),
            "signup_date": cust_dates,
            "lifetime_value": np.round(rng.uniform(100, 5_000_000, size=n), 2),
            "orders_count": rng.integers(1, 500, size=n).astype(int),
            "segment": rng.choice(segments, size=n),
        }
    )

    chunk = 200_000
    for i in range(0, n, chunk):
        df.iloc[i : i + chunk].to_sql("customers", engine, if_exists="append", index=False)
        print(f"  {min(i + chunk, n):>10,} / {n:,} customers")

    print(f"Customers done in {time.time() - start:.1f}s")


def seed_website_analytics(n_days: int):
    print(f"Seeding {n_days} days of website analytics (vectorized)...")
    start = time.time()

    wa_dates = pd.date_range("2020-01-01", periods=n_days, freq="D")
    page_views = rng.integers(1000, 100_000, size=n_days)
    unique_visitors = (page_views * rng.uniform(0.4, 0.85, size=n_days)).astype(int)
    conversions = np.minimum(rng.integers(0, 500, size=n_days), unique_visitors)

    df = pd.DataFrame(
        {
            "date": [str(d.date()) for d in wa_dates],
            "page_views": page_views.astype(int),
            "unique_visitors": unique_visitors.astype(int),
            "bounce_rate": np.round(rng.uniform(0.15, 0.75, size=n_days), 4),
            "avg_session_duration": np.round(rng.uniform(20, 600, size=n_days), 2),
            "conversions": conversions.astype(int),
            "revenue": np.round(rng.uniform(0, 50_000_000, size=n_days), 2),
        }
    )

    df.to_sql("website_analytics", engine, if_exists="append", index=False)
    print(f"Website analytics done in {time.time() - start:.1f}s")


seed_sales(N_SALES)
seed_customers(N_CUSTOMERS)
seed_website_analytics(N_WEB_DAYS)

print("Creating indexes...")
with engine.begin() as conn:
    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_sales_date ON sales(date)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_sales_region ON sales(region)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_sales_category ON sales(product_category)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_customers_region ON customers(region)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_wa_date ON website_analytics(date)"))

print("\nVerification:")
with engine.connect() as conn:
    for tbl in ("sales", "customers", "website_analytics"):
        cnt = conn.execute(text(f"SELECT COUNT(*) FROM {tbl}")).scalar()  # noqa: S608
        print(f"  {tbl}: {cnt:,} rows")

print("\nDone! PostgreSQL seeded with large-scale data.")
