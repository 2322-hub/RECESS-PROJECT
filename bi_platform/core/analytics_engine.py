from typing import Any

import pandas as pd

from .data_processor import DataProcessor


class AnalyticsEngine:
    """Higher-level analytics built on top of DataProcessor.

    Supports two modes:
    - DataFrame-based (small datasets, loads full data into pandas)
    - SQL-based (large datasets, all aggregations pushed to database)
    """

    dp = DataProcessor()

    # ------------------------------------------------------------------
    # Revenue breakdown analysis
    # ------------------------------------------------------------------
    @staticmethod
    def revenue_breakdown(df: pd.DataFrame) -> dict[str, Any]:
        if df.empty:
            return {}
        result: dict[str, Any] = {}
        for group in ("region", "product_category", "customer_segment"):
            if group in df.columns and "total_revenue" in df.columns:
                agg = df.groupby(group)["total_revenue"].sum().sort_values(ascending=False).reset_index()
                agg.columns = ["label", "value"]
                result[group] = agg.to_dict(orient="records")
        return result

    # ------------------------------------------------------------------
    # Monthly trends
    # ------------------------------------------------------------------
    @staticmethod
    def monthly_trends(df: pd.DataFrame) -> list[dict]:
        if df.empty or "date" not in df.columns or "total_revenue" not in df.columns:
            return []
        tmp = df.copy()
        tmp["date"] = pd.to_datetime(tmp["date"], errors="coerce")
        tmp = tmp.dropna(subset=["date"])
        if tmp.empty:
            return []
        agg_dict: dict[str, Any] = {"total_revenue": "sum"}
        if "profit" in tmp.columns:
            agg_dict["profit"] = "sum"
        if "quantity" in tmp.columns:
            agg_dict["quantity"] = "sum"
        monthly = tmp.groupby(tmp["date"].dt.to_period("M")).agg(agg_dict).reset_index()
        monthly["date"] = monthly["date"].astype(str)
        monthly = monthly.rename(columns={"total_revenue": "revenue"})
        if "profit" not in monthly.columns:
            monthly["profit"] = 0
        if "quantity" not in monthly.columns:
            monthly["quantity"] = 0
        return monthly.to_dict(orient="records")

    # ------------------------------------------------------------------
    # Regional comparison
    # ------------------------------------------------------------------
    @staticmethod
    def regional_comparison(df: pd.DataFrame) -> list[dict]:
        if df.empty or "region" not in df.columns or "total_revenue" not in df.columns:
            return []
        agg_dict: dict[str, Any] = {}
        if "profit" in df.columns:
            agg_dict["profit"] = ("profit", "sum")
        if "quantity" in df.columns:
            agg_dict["orders"] = ("quantity", "count")
        agg_dict["revenue"] = ("total_revenue", "sum")
        agg_dict["avg_order_value"] = ("total_revenue", "mean")
        result = df.groupby("region").agg(**agg_dict).round(2).reset_index()
        return result.to_dict(orient="records")

    # ------------------------------------------------------------------
    # Product performance
    # ------------------------------------------------------------------
    @staticmethod
    def product_performance(df: pd.DataFrame) -> list[dict]:
        if df.empty:
            return []
        group_cols = [c for c in ("product_category", "product_name") if c in df.columns]
        if not group_cols or "total_revenue" not in df.columns:
            return []
        agg_dict = {"total_revenue": "sum"}
        if "profit" in df.columns:
            agg_dict["profit"] = "sum"
        if "quantity" in df.columns:
            agg_dict["quantity"] = "sum"
        agg = df.groupby(group_cols).agg(agg_dict).round(2).sort_values("total_revenue", ascending=False).reset_index()
        return agg.to_dict(orient="records")

    # ------------------------------------------------------------------
    # Website analytics summary
    # ------------------------------------------------------------------
    @staticmethod
    def website_summary(wa_df: pd.DataFrame) -> dict[str, Any]:
        empty = {
            "total_page_views": 0,
            "total_unique_visitors": 0,
            "avg_bounce_rate": 0,
            "avg_session_duration": 0,
            "total_conversions": 0,
            "total_revenue": 0,
            "conversion_rate": 0,
            "daily_trend": [],
        }
        if wa_df.empty or "date" not in wa_df.columns:
            return empty
        tmp = wa_df.copy()
        tmp["date"] = pd.to_datetime(tmp["date"], errors="coerce")
        tmp = tmp.dropna(subset=["date"])
        if tmp.empty:
            return empty
        summary: dict[str, Any] = {}
        for col, key in [
            ("page_views", "total_page_views"),
            ("unique_visitors", "total_unique_visitors"),
            ("conversions", "total_conversions"),
            ("revenue", "total_revenue"),
        ]:
            summary[key] = int(tmp[col].sum()) if col in tmp.columns else 0
        if "bounce_rate" in tmp.columns:
            summary["avg_bounce_rate"] = round(float(tmp["bounce_rate"].mean()) * 100, 2)
        else:
            summary["avg_bounce_rate"] = 0
        if "avg_session_duration" in tmp.columns:
            summary["avg_session_duration"] = round(float(tmp["avg_session_duration"].mean()), 2)
        else:
            summary["avg_session_duration"] = 0
        uv = summary["total_unique_visitors"]
        summary["conversion_rate"] = round(float(summary["total_conversions"] / max(uv, 1) * 100), 2)
        trend_cols: dict[str, tuple[str, str]] = {
            "page_views": ("page_views", "sum"),
        }
        if "unique_visitors" in tmp.columns:
            trend_cols["visitors"] = ("unique_visitors", "sum")
        if "revenue" in tmp.columns:
            trend_cols["revenue"] = ("revenue", "sum")
        daily = tmp.groupby("date").agg(**{k: (v[0], v[1]) for k, v in trend_cols.items()}).reset_index()
        daily["date"] = daily["date"].astype(str)
        summary["daily_trend"] = daily.to_dict(orient="records")
        return summary

    # ------------------------------------------------------------------
    # Cohort-style customer analysis
    # ------------------------------------------------------------------
    @staticmethod
    def customer_insights(cust_df: pd.DataFrame) -> dict[str, Any]:
        empty = {
            "total_customers": 0,
            "avg_lifetime_value": 0,
            "total_lifetime_value": 0,
            "avg_orders": 0,
            "by_segment": [],
            "by_region": [],
        }
        if cust_df.empty:
            return empty
        ltv_col = "lifetime_value" if "lifetime_value" in cust_df.columns else None
        if ltv_col is None:
            return {**empty, "total_customers": len(cust_df)}
        result: dict[str, Any] = {
            "total_customers": len(cust_df),
            "avg_lifetime_value": round(float(cust_df[ltv_col].mean()), 2),
            "total_lifetime_value": round(float(cust_df[ltv_col].sum()), 2),
        }
        if "orders_count" in cust_df.columns:
            result["avg_orders"] = round(float(cust_df["orders_count"].mean()), 2)
        else:
            result["avg_orders"] = 0
        if "segment" in cust_df.columns:
            by_seg = (
                cust_df.groupby("segment")
                .agg(
                    count=("id", "count"),
                    avg_ltv=(ltv_col, "mean"),
                    total_ltv=(ltv_col, "sum"),
                )
                .round(2)
                .reset_index()
            )
            result["by_segment"] = by_seg.to_dict(orient="records")
        else:
            result["by_segment"] = []
        if "region" in cust_df.columns:
            by_reg = (
                cust_df.groupby("region").agg(count=("id", "count"), avg_ltv=(ltv_col, "mean")).round(2).reset_index()
            )
            result["by_region"] = by_reg.to_dict(orient="records")
        else:
            result["by_region"] = []
        return result

    # ------------------------------------------------------------------
    # Full dashboard payload
    # ------------------------------------------------------------------
    def build_dashboard_payload(self, sales_df: pd.DataFrame, cust_df: pd.DataFrame, wa_df: pd.DataFrame) -> dict:
        kpis = self.dp.compute_kpis(sales_df)
        top_products = (
            self.dp.top_n(sales_df, "product_name", "total_revenue")
            if "product_name" in sales_df.columns and "total_revenue" in sales_df.columns
            else []
        )
        return {
            "kpis": kpis,
            "revenue_breakdown": self.revenue_breakdown(sales_df),
            "monthly_trends": self.monthly_trends(sales_df),
            "regional_comparison": self.regional_comparison(sales_df),
            "product_performance": self.product_performance(sales_df),
            "top_products": top_products,
            "website_analytics": self.website_summary(wa_df),
            "customer_insights": self.customer_insights(cust_df),
            "correlation": self.dp.correlation_matrix(sales_df),
            "profile": self.dp.profile(sales_df),
        }

    # ------------------------------------------------------------------
    # SQL-backed dashboard (for large datasets — no full-table loads)
    # ------------------------------------------------------------------
    def build_dashboard_payload_sql(self, db_connector, conn: str) -> dict:
        """Build full dashboard payload using only SQL aggregations.

        Never loads the full table into Python memory.
        Suitable for datasets with millions of rows.
        """
        kpis = db_connector.sql_kpis(conn)
        revenue_breakdown = db_connector.sql_revenue_breakdown(conn)
        monthly_trends = db_connector.sql_monthly_trends(conn)
        regional_comparison = db_connector.sql_regional_comparison(conn)
        product_performance = db_connector.sql_product_performance(conn)
        top_products = db_connector.sql_top_n(conn, "product_name", "total_revenue", n=10)
        website_analytics = db_connector.sql_website_summary(conn)
        customer_insights = db_connector.sql_customer_insights(conn)

        correlation = {}
        profile = {}
        try:
            sample = db_connector.execute_query(
                conn,
                "SELECT total_revenue, cost, profit, quantity, unit_price "
                "FROM sales TABLESAMPLE BERNOULLI(1) LIMIT 5000",
            )
            if not sample.empty:
                correlation = db_connector.sql_correlation_matrix(sample)
                profile = self.dp.profile(sample)
        except Exception:  # noqa: BLE001, S110
            pass  # profiling is best-effort

        return {
            "kpis": kpis,
            "revenue_breakdown": revenue_breakdown,
            "monthly_trends": monthly_trends,
            "regional_comparison": regional_comparison,
            "product_performance": product_performance,
            "top_products": top_products,
            "website_analytics": website_analytics,
            "customer_insights": customer_insights,
            "correlation": correlation,
            "profile": profile,
        }
