import logging
import math
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

_MIN_SEASONAL_PERIODS = 24


def _safe_metric(value: float) -> float:
    """Round a metric, replacing NaN/Inf with 0."""
    if value is None or (isinstance(value, float) and (math.isnan(value) or math.isinf(value))):
        return 0.0
    return round(float(value), 2)


class ForecastEngine:
    """Time-series forecasting using statsmodels (Holt-Winters / Exponential Smoothing)."""

    @staticmethod
    def forecast_revenue(
        monthly_trends: list[dict],
        periods: int = 6,
    ) -> dict[str, Any]:
        if not monthly_trends or len(monthly_trends) < 6:
            return {"forecast": [], "lower_bound": [], "upper_bound": [], "historical": monthly_trends or []}

        try:
            from statsmodels.tsa.holtwinters import ExponentialSmoothing

            dates = []
            values = []
            for m in monthly_trends:
                rev = m.get("revenue")
                if rev is None:
                    continue
                try:
                    val = float(rev)
                except (TypeError, ValueError):
                    continue
                if math.isnan(val) or math.isinf(val):
                    continue
                dates.append(m["date"])
                values.append(val)

            if len(values) < 6:
                return {"forecast": [], "lower_bound": [], "upper_bound": [], "historical": monthly_trends}

            ts = pd.Series(values, index=pd.to_datetime(dates))
            ts = ts.sort_index()

            seasonal = "add" if len(ts) >= _MIN_SEASONAL_PERIODS else None
            trend = "add"

            model = ExponentialSmoothing(
                ts,
                trend=trend,
                seasonal=seasonal,
                seasonal_periods=12 if seasonal else None,
                initialization_method="estimated",
            )
            fitted = model.fit(optimized=True, use_brute=False)
            pred = fitted.forecast(periods)

            residuals = fitted.resid.dropna()
            std_err = float(residuals.std()) if len(residuals) > 1 else 0
            z = 1.96

            forecast_dates = pd.date_range(
                start=ts.index[-1] + pd.offsets.MonthBegin(1),
                periods=periods,
                freq="MS",
            )

            forecast = [
                {"date": d.strftime("%Y-%m"), "value": round(float(v), 2)}
                for d, v in zip(forecast_dates, pred, strict=False)
            ]
            lower = [
                {"date": d.strftime("%Y-%m"), "value": round(max(float(v) - z * std_err, 0), 2)}
                for d, v in zip(forecast_dates, pred, strict=False)
            ]
            upper = [
                {"date": d.strftime("%Y-%m"), "value": round(float(v) + z * std_err, 2)}
                for d, v in zip(forecast_dates, pred, strict=False)
            ]

            historical = [
                {"date": m["date"], "revenue": m.get("revenue", 0), "profit": m.get("profit", 0)}
                for m in monthly_trends
            ]

            return {
                "forecast": forecast,
                "lower_bound": lower,
                "upper_bound": upper,
                "historical": historical,
                "metrics": {
                    "aic": _safe_metric(fitted.aic),
                    "bic": _safe_metric(fitted.bic),
                    "mae": _safe_metric(float(np.mean(np.abs(residuals))) if len(residuals) > 0 else 0),
                    "rmse": _safe_metric(float(np.sqrt(np.mean(residuals**2))) if len(residuals) > 0 else 0),
                },
            }
        except Exception as e:
            logger.error("Forecasting failed: %s", e, exc_info=True)
            return {"forecast": [], "lower_bound": [], "upper_bound": [], "historical": monthly_trends, "error": str(e)}

    @staticmethod
    def forecast_metric(values: list[float], periods: int = 6, freq: str = "MS") -> dict[str, Any]:
        if not values or len(values) < 4:
            return {"forecast": [], "lower_bound": [], "upper_bound": []}

        cleaned = [float(v) for v in values if v is not None and not math.isnan(float(v))]
        if len(cleaned) < 4:
            return {"forecast": [], "lower_bound": [], "upper_bound": []}

        try:
            from statsmodels.tsa.holtwinters import ExponentialSmoothing

            ts = pd.Series(cleaned)
            seasonal = "add" if len(ts) >= _MIN_SEASONAL_PERIODS else None

            model = ExponentialSmoothing(
                ts,
                trend="add",
                seasonal=seasonal,
                seasonal_periods=12 if seasonal else None,
                initialization_method="estimated",
            )
            fitted = model.fit(optimized=True, use_brute=False)
            pred = fitted.forecast(periods)

            residuals = fitted.resid.dropna()
            std_err = float(residuals.std()) if len(residuals) > 1 else 0
            z = 1.96

            return {
                "forecast": [round(float(v), 2) for v in pred],
                "lower_bound": [round(max(float(v) - z * std_err, 0), 2) for v in pred],
                "upper_bound": [round(float(v) + z * std_err, 2) for v in pred],
            }
        except Exception as e:
            logger.error("Metric forecast failed: %s", e)
            return {"forecast": [], "lower_bound": [], "upper_bound": [], "error": str(e)}
