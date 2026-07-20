import pandas as pd
import numpy as np
from typing import Any

from .data_processor import DataProcessor


class AnalyticsEngine:
    """Higher-level analytics built on top of DataProcessor."""

    dp = DataProcessor()

    # ------------------------------------------------------------------
    # Revenue breakdown analysis
    # ------------------------------------------------------------------
    @staticmethod
    def revenue_breakdown(df: pd.DataFrame) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for group in ("region", "product_category", "customer_segment"):
            if group in df.columns:
                agg = df.groupby(group)["total_revenue"].sum().sort_values(ascending=False).reset_index()
                agg.columns = ["label", "value"]
                result[group] = agg.to_dict(orient="records")
        return result

    # ------------------------------------------------------------------
    # Monthly trends
    # ------------------------------------------------------------------
    @staticmethod
    def monthly_trends(df: pd.DataFrame) -> list[dict]:
        tmp = df.copy()
        tmp["date"] = pd.to_datetime(tmp["date"])
        monthly = tmp.groupby(tmp["date"].dt.to_period("M")).agg(
            revenue=("total_revenue", "sum"),
            profit=("profit", "sum"),
            quantity=("quantity", "sum"),
        ).reset_index()
        monthly["date"] = monthly["date"].astype(str)
        return monthly.to_dict(orient="records")

    # ------------------------------------------------------------------
    # Regional comparison
    # ------------------------------------------------------------------
    @staticmethod
    def regional_comparison(df: pd.DataFrame) -> list[dict]:
        agg = df.groupby("region").agg(
            revenue=("total_revenue", "sum"),
            profit=("profit", "sum"),
            orders=("quantity", "count"),
            avg_order_value=("total_revenue", "mean"),
        ).round(2).reset_index()
        return agg.to_dict(orient="records")

    # ------------------------------------------------------------------
    # Product performance
    # ------------------------------------------------------------------
    @staticmethod
    def product_performance(df: pd.DataFrame) -> list[dict]:
        agg = df.groupby(["product_category", "product_name"]).agg(
            revenue=("total_revenue", "sum"),
            profit=("profit", "sum"),
            quantity=("quantity", "sum"),
        ).round(2).sort_values("revenue", ascending=False).reset_index()
        return agg.to_dict(orient="records")

    # ------------------------------------------------------------------
    # Website analytics summary
    # ------------------------------------------------------------------
    @staticmethod
    def website_summary(wa_df: pd.DataFrame) -> dict[str, Any]:
        tmp = wa_df.copy()
        tmp["date"] = pd.to_datetime(tmp["date"])
        summary = {
            "total_page_views": int(tmp["page_views"].sum()),
            "total_unique_visitors": int(tmp["unique_visitors"].sum()),
            "avg_bounce_rate": round(float(tmp["bounce_rate"].mean()) * 100, 2),
            "avg_session_duration": round(float(tmp["avg_session_duration"].mean()), 2),
            "total_conversions": int(tmp["conversions"].sum()),
            "total_revenue": round(float(tmp["revenue"].sum()), 2),
            "conversion_rate": round(float(tmp["conversions"].sum() / max(tmp["unique_visitors"].sum(), 1) * 100), 2),
        }
        daily = tmp.groupby("date").agg(
            page_views=("page_views", "sum"),
            visitors=("unique_visitors", "sum"),
            revenue=("revenue", "sum"),
        ).reset_index()
        daily["date"] = daily["date"].astype(str)
        summary["daily_trend"] = daily.to_dict(orient="records")
        return summary

    # ------------------------------------------------------------------
    # Cohort-style customer analysis
    # ------------------------------------------------------------------
    @staticmethod
    def customer_insights(cust_df: pd.DataFrame) -> dict[str, Any]:
        return {
            "total_customers": len(cust_df),
            "avg_lifetime_value": round(float(cust_df["lifetime_value"].mean()), 2),
            "total_lifetime_value": round(float(cust_df["lifetime_value"].sum()), 2),
            "avg_orders": round(float(cust_df["orders_count"].mean()), 2),
            "by_segment": cust_df.groupby("segment").agg(
                count=("id", "count"),
                avg_ltv=("lifetime_value", "mean"),
                total_ltv=("lifetime_value", "sum"),
            ).round(2).reset_index().to_dict(orient="records"),
            "by_region": cust_df.groupby("region").agg(
                count=("id", "count"),
                avg_ltv=("lifetime_value", "mean"),
            ).round(2).reset_index().to_dict(orient="records"),
        }

    # ------------------------------------------------------------------
    # Full dashboard payload
    # ------------------------------------------------------------------
    def build_dashboard_payload(self, sales_df: pd.DataFrame, cust_df: pd.DataFrame, wa_df: pd.DataFrame) -> dict:
        kpis = self.dp.compute_kpis(sales_df)
        return {
            "kpis": kpis,
            "revenue_breakdown": self.revenue_breakdown(sales_df),
            "monthly_trends": self.monthly_trends(sales_df),
            "regional_comparison": self.regional_comparison(sales_df),
            "product_performance": self.product_performance(sales_df),
            "top_products": self.dp.top_n(sales_df, "product_name", "total_revenue"),
            "website_analytics": self.website_summary(wa_df),
            "customer_insights": self.customer_insights(cust_df),
            "correlation": self.dp.correlation_matrix(sales_df),
            "profile": self.dp.profile(sales_df),
        }
