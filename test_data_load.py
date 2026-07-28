from dotenv import load_dotenv
load_dotenv(override=True)

from bi_platform.routes import _load_dashboard_data, _normalize_columns
from bi_platform.core.analytics_engine import AnalyticsEngine
from bi_platform.core.database_connector import DatabaseConnector
import os, pandas as pd

ae = AnalyticsEngine()
dc = DatabaseConnector()
dc.connect("bi_platform", os.environ["DATABASE_URL"])
dc.connect("countrysales", os.environ["DATABASE_URL"])

for conn in ["bi_platform", "countrysales", "demo"]:
    print(f"\n{'='*40}")
    print(f"CONNECTION: {conn}")
    print('='*40)
    try:
        sales, customers, website = _load_dashboard_data(conn)
        print(f"  sales      : {len(sales)} rows | cols: {list(sales.columns)}")
        print(f"  customers  : {len(customers)} rows")
        print(f"  website    : {len(website)} rows")

        if not sales.empty:
            kpis = ae.dp.compute_kpis(sales)
            print(f"  KPIs       : {kpis}")
            trends = ae.monthly_trends(sales)
            print(f"  trends     : {len(trends)} months | sample: {trends[:1]}")
            regional = ae.regional_comparison(sales)
            print(f"  regional   : {len(regional)} regions")
            products = ae.product_performance(sales)
            print(f"  products   : {len(products)} rows")
        else:
            print("  WARNING: sales DataFrame is EMPTY")

        if not customers.empty:
            ci = ae.customer_insights(customers)
            print(f"  cust KPIs  : total={ci.get('total_customers')}, avg_ltv={ci.get('avg_lifetime_value')}")
        else:
            print("  WARNING: customers DataFrame is EMPTY")

        if not website.empty:
            ws = ae.website_summary(website)
            print(f"  website KPIs: page_views={ws.get('total_page_views')}, visitors={ws.get('total_unique_visitors')}")
        else:
            print("  NOTE: no website_analytics for this connection")

    except Exception as e:
        import traceback
        print(f"  ERROR: {e}")
        traceback.print_exc()

print("\nDone.")
