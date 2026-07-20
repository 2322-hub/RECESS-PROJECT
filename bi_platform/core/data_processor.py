from typing import Any

import numpy as np
import pandas as pd


class DataProcessor:
    """Transform, aggregate, and profile DataFrames for dashboard consumption."""

    # ------------------------------------------------------------------
    # Aggregation helpers
    # ------------------------------------------------------------------
    @staticmethod
    def time_series(df: pd.DataFrame, date_col: str, value_col: str, freq: str = "D") -> pd.DataFrame:
        tmp = df.copy()
        tmp[date_col] = pd.to_datetime(tmp[date_col])
        agg = tmp.groupby(pd.Grouper(key=date_col, freq=freq))[value_col].sum().reset_index()
        agg.columns = ["date", "value"]
        return agg

    @staticmethod
    def group_by_sum(df: pd.DataFrame, group_col: str, value_col: str) -> pd.DataFrame:
        agg = df.groupby(group_col)[value_col].sum().reset_index()
        agg.columns = ["label", "value"]
        return agg.sort_values("value", ascending=False)

    @staticmethod
    def pivot_table(
        df: pd.DataFrame,
        index_col: str,
        columns_col: str,
        value_col: str,
        aggfunc: str = "sum",
    ) -> pd.DataFrame:
        return pd.pivot_table(df, index=index_col, columns=columns_col, values=value_col, aggfunc=aggfunc)

    @staticmethod
    def correlation_matrix(df: pd.DataFrame, numeric_cols: list[str] | None = None) -> dict:
        nums = df.select_dtypes(include=[np.number]) if numeric_cols is None else df[numeric_cols]
        corr = nums.corr()
        return {
            "columns": list(corr.columns),
            "values": corr.values.tolist(),
        }

    # ------------------------------------------------------------------
    # Statistical profiling
    # ------------------------------------------------------------------
    @staticmethod
    def profile(df: pd.DataFrame) -> dict:
        """Return a column-level statistical summary."""
        profile: dict[str, Any] = {}
        for col in df.columns:
            info: dict[str, Any] = {
                "dtype": str(df[col].dtype),
                "null_count": int(df[col].isnull().sum()),
                "null_pct": round(df[col].isnull().mean() * 100, 2),
                "unique_count": int(df[col].nunique()),
            }
            if pd.api.types.is_numeric_dtype(df[col]):
                desc = df[col].describe()
                info.update(
                    {
                        "mean": round(float(desc["mean"]), 4),
                        "std": round(float(desc["std"]), 4),
                        "min": round(float(desc["min"]), 4),
                        "25%": round(float(desc["25%"]), 4),
                        "50%": round(float(desc["50%"]), 4),
                        "75%": round(float(desc["75%"]), 4),
                        "max": round(float(desc["max"]), 4),
                    }
                )
            profile[col] = info
        return profile

    # ------------------------------------------------------------------
    # KPI calculations
    # ------------------------------------------------------------------
    @staticmethod
    def compute_kpis(
        df: pd.DataFrame,
        revenue_col: str = "total_revenue",
        cost_col: str = "cost",
        profit_col: str = "profit",
    ) -> dict:
        kpis: dict[str, Any] = {}
        if revenue_col in df.columns:
            kpis["total_revenue"] = round(float(df[revenue_col].sum()), 2)
            kpis["avg_revenue"] = round(float(df[revenue_col].mean()), 2)
        if cost_col in df.columns:
            kpis["total_cost"] = round(float(df[cost_col].sum()), 2)
        if profit_col in df.columns:
            kpis["total_profit"] = round(float(df[profit_col].sum()), 2)
            if revenue_col in df.columns and kpis.get("total_revenue"):
                kpis["profit_margin"] = round(kpis["total_profit"] / kpis["total_revenue"] * 100, 2)
        kpis["record_count"] = len(df)
        return kpis

    # ------------------------------------------------------------------
    # Top-N / Bottom-N
    # ------------------------------------------------------------------
    @staticmethod
    def top_n(df: pd.DataFrame, group_col: str, value_col: str, n: int = 10) -> list[dict]:
        agg = df.groupby(group_col)[value_col].sum().nlargest(n).reset_index()
        agg.columns = ["label", "value"]
        return agg.to_dict(orient="records")

    @staticmethod
    def bottom_n(df: pd.DataFrame, group_col: str, value_col: str, n: int = 10) -> list[dict]:
        agg = df.groupby(group_col)[value_col].sum().nsmallest(n).reset_index()
        agg.columns = ["label", "value"]
        return agg.to_dict(orient="records")

    # ------------------------------------------------------------------
    # Moving average / rolling stats
    # ------------------------------------------------------------------
    @staticmethod
    def rolling_average(df: pd.DataFrame, date_col: str, value_col: str, window: int = 7) -> pd.DataFrame:
        tmp = df.copy()
        tmp[date_col] = pd.to_datetime(tmp[date_col])
        tmp = tmp.sort_values(date_col)
        tmp["rolling_avg"] = tmp[value_col].rolling(window=window, min_periods=1).mean()
        return tmp[[date_col, value_col, "rolling_avg"]]
