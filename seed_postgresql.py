"""Seed PostgreSQL with large-scale data for BI Platform demo.

Generates:
- 2,000,000 sales rows
- 50,000 customer rows
- 1,000 days of website analytics

Usage: python seed_postgresql.py
"""

import os
import time

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv(override=True)

DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg2://postgres:root@localhost:5432/bi_platform",
)
engine = create_engine(DB_URL, pool_size=5)

N_SALES = 2_000_000
N_CUSTOMERS = 50_000
N_WEB_DAYS = 1_000

regions = ["North", "South", "East", "West", "Central", "Pacific", "Mountain"]
categories = ["Electronics", "Clothing", "Food", "Furniture", "Software", "Hardware"]
products = [
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
segments = ["Enterprise", "SMB", "Consumer", "Government", "Education"]

rng = np.random.default_rng(42)

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

# --- Seed sales in chunks ---
print(f"Seeding {N_SALES:,} sales rows...")
dates = pd.date_range("2020-01-01", "2025-12-31", freq="D")
start = time.time()
chunk_size = 100_000

for offset in range(0, N_SALES, chunk_size):
    n = min(chunk_size, N_SALES - offset)
    rows = []
    for _ in range(n):
        d = str(dates[rng.integers(0, len(dates))].date())
        cat = rng.choice(categories)
        prod = rng.choice(products)
        qty = int(rng.integers(1, 100))
        price = round(float(rng.uniform(10, 50000)), 2)
        total = round(qty * price, 2)
        cost = round(total * rng.uniform(0.3, 0.85), 2)
        rows.append(
            {
                "date": d,
                "region": rng.choice(regions),
                "product_category": cat,
                "product_name": prod,
                "quantity": qty,
                "unit_price": price,
                "total_revenue": total,
                "cost": cost,
                "profit": round(total - cost, 2),
                "customer_segment": rng.choice(segments),
            }
        )
    pd.DataFrame(rows).to_sql("sales", engine, if_exists="append", index=False)
    elapsed = time.time() - start
    rate = (offset + n) / elapsed if elapsed > 0 else 0
    print(f"  {offset + n:>10,} / {N_SALES:,} rows  ({rate:,.0f} rows/sec)")

print(f"Sales done in {time.time() - start:.1f}s")

# --- Seed customers in chunks ---
print(f"Seeding {N_CUSTOMERS:,} customers...")
start = time.time()
for offset in range(0, N_CUSTOMERS, chunk_size):
    n = min(chunk_size, N_CUSTOMERS - offset)
    rows = []
    for i in range(offset + 1, offset + n + 1):
        sd = str(dates[rng.integers(0, len(dates))].date())
        rows.append(
            {
                "name": f"Customer_{i}",
                "email": f"customer{i}@example.com",
                "region": rng.choice(regions),
                "signup_date": sd,
                "lifetime_value": round(float(rng.uniform(100, 5000000)), 2),
                "orders_count": int(rng.integers(1, 500)),
                "segment": rng.choice(segments),
            }
        )
    pd.DataFrame(rows).to_sql("customers", engine, if_exists="append", index=False)
    print(f"  {offset + n:>10,} / {N_CUSTOMERS:,} customers")

print(f"Customers done in {time.time() - start:.1f}s")

# --- Seed website analytics in chunks ---
print(f"Seeding {N_WEB_DAYS} days of website analytics...")
start = time.time()
wa_dates = pd.date_range("2020-01-01", periods=N_WEB_DAYS, freq="D")
for offset in range(0, N_WEB_DAYS, chunk_size):
    n = min(chunk_size, N_WEB_DAYS - offset)
    rows = []
    for i in range(offset, offset + n):
        pv = int(rng.integers(1000, 100000))
        uv = int(pv * rng.uniform(0.4, 0.85))
        conv = int(rng.integers(0, min(uv, 500)))
        rows.append(
            {
                "date": str(wa_dates[i].date()),
                "page_views": pv,
                "unique_visitors": uv,
                "bounce_rate": round(float(rng.uniform(0.15, 0.75)), 4),
                "avg_session_duration": round(float(rng.uniform(20, 600)), 2),
                "conversions": conv,
                "revenue": round(float(rng.uniform(0, 50000000)), 2),
            }
        )
    pd.DataFrame(rows).to_sql("website_analytics", engine, if_exists="append", index=False)
    print(f"  {offset + n:>6} / {N_WEB_DAYS} days")

print(f"Website analytics done in {time.time() - start:.1f}s")

# --- Create indexes for performance ---
print("Creating indexes...")
with engine.begin() as conn:
    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_sales_date ON sales(date)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_sales_region ON sales(region)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_sales_category ON sales(product_category)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_customers_region ON customers(region)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_wa_date ON website_analytics(date)"))

# --- Verify ---
print("\nVerification:")
with engine.connect() as conn:
    for tbl in ("sales", "customers", "website_analytics"):
        cnt = conn.execute(text(f"SELECT COUNT(*) FROM {tbl}")).scalar()  # noqa: S608
        print(f"  {tbl}: {cnt:,} rows")

print("\nDone! PostgreSQL is seeded with large-scale data.")
