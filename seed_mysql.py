import os

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv(override=True)

engine = create_engine(os.environ.get("DATABASE_URL", "mysql+pymysql://root@localhost:3306/bi_platform"))

with engine.begin() as conn:
    conn.execute(text("DROP TABLE IF EXISTS sales"))
    conn.execute(text("DROP TABLE IF EXISTS customers"))
    conn.execute(text("DROP TABLE IF EXISTS website_analytics"))
    conn.execute(text("DROP TABLE IF EXISTS products"))
    conn.execute(
        text("""
        CREATE TABLE sales (
            id INTEGER PRIMARY KEY AUTO_INCREMENT,
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
            id INTEGER PRIMARY KEY AUTO_INCREMENT,
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
            id INTEGER PRIMARY KEY AUTO_INCREMENT,
            date TEXT,
            page_views INTEGER,
            unique_visitors INTEGER,
            bounce_rate REAL,
            avg_session_duration REAL,
            revenue REAL
        )
    """)
    )

rng = np.random.default_rng(42)
regions = ["North", "South", "East", "West"]
categories = ["Electronics", "Clothing", "Food", "Furniture"]
products = ["Widget A", "Widget B", "Gadget X", "Gadget Y", "Service Pro", "Basic Plan"]
segments = ["Enterprise", "SMB", "Consumer"]

n_sales = 5000
dates = pd.date_range("2024-01-01", periods=365, freq="D")
sales_rows = []
for _i in range(1, n_sales + 1):
    d = str(dates[rng.integers(0, len(dates))].date())
    cat = rng.choice(categories)
    prod = rng.choice(products)
    qty = int(rng.integers(1, 50))
    price = round(float(rng.uniform(5000, 500000)), 2)
    total = round(qty * price, 2)
    cost = round(total * rng.uniform(0.3, 0.8), 2)
    sales_rows.append(
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
pd.DataFrame(sales_rows).to_sql("sales", engine, if_exists="append", index=False)

cust_rows = []
for i in range(1, 201):
    sd = str(dates[rng.integers(0, len(dates))].date())
    cust_rows.append(
        {
            "name": f"Customer_{i}",
            "email": f"customer{i}@example.com",
            "region": rng.choice(regions),
            "signup_date": sd,
            "lifetime_value": round(float(rng.uniform(500000, 50000000)), 2),
            "orders_count": int(rng.integers(1, 100)),
            "segment": rng.choice(segments),
        }
    )
pd.DataFrame(cust_rows).to_sql("customers", engine, if_exists="append", index=False)

wa_rows = []
for _i, d in enumerate(dates[:180], 1):
    pv = int(rng.integers(500, 5000))
    uv = int(pv * rng.uniform(0.5, 0.9))
    wa_rows.append(
        {
            "date": str(d.date()),
            "page_views": pv,
            "unique_visitors": uv,
            "bounce_rate": round(float(rng.uniform(0.2, 0.7)), 4),
            "avg_session_duration": round(float(rng.uniform(30, 300)), 2),
            "revenue": round(float(rng.uniform(0, 20000000)), 2),
        }
    )
pd.DataFrame(wa_rows).to_sql("website_analytics", engine, if_exists="append", index=False)

print("Done - 3 tables (sales, customers, website_analytics) recreated and seeded in MySQL")
