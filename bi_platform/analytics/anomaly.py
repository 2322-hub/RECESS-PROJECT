import logging
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class AnomalyDetector:
    """Detect anomalies in time-series data using Z-score and IQR methods."""

    @staticmethod
    def detect_revenue_anomalies(
        monthly_trends: list[dict],
        z_threshold: float = 2.0,
    ) -> dict[str, Any]:
        if not monthly_trends or len(monthly_trends) < 4:
            return {"anomalies": [], "summary": {}}

        try:
            dates = [m["date"] for m in monthly_trends]
            revenues = [float(m.get("revenue", 0)) for m in monthly_trends]
            ts = pd.Series(revenues, index=pd.to_datetime(dates))

            mean = ts.mean()
            std = ts.std()

            if std == 0:
                return {"anomalies": [], "summary": {"mean": float(mean), "std": 0}}

            z_scores = (ts - mean) / std
            anomaly_mask = z_scores.abs() > z_threshold

            anomalies = []
            for date, val, z in zip(dates, revenues, z_scores):
                if abs(z) > z_threshold:
                    anomalies.append({
                        "date": date,
                        "value": round(val, 2),
                        "z_score": round(float(z), 3),
                        "type": "spike" if z > 0 else "drop",
                        "deviation_pct": round(float((val - mean) / mean * 100), 1),
                    })

            q1 = ts.quantile(0.25)
            q3 = ts.quantile(0.75)
            iqr = q3 - q1

            trend = "increasing" if len(revenues) >= 3 and revenues[-1] > revenues[0] else "decreasing"
            if len(revenues) >= 3:
                diffs = [revenues[i] - revenues[i - 1] for i in range(1, len(revenues))]
                avg_change = sum(diffs) / len(diffs)
                trend = "increasing" if avg_change > 0 else "decreasing" if avg_change < 0 else "stable"

            return {
                "anomalies": anomalies,
                "summary": {
                    "mean": round(float(mean), 2),
                    "std": round(float(std), 2),
                    "q1": round(float(q1), 2),
                    "q3": round(float(q3), 2),
                    "iqr": round(float(iqr), 2),
                    "trend": trend,
                    "total_points": len(revenues),
                    "anomaly_count": len(anomalies),
                    "anomaly_pct": round(len(anomalies) / len(revenues) * 100, 1),
                },
            }
        except Exception as e:
            logger.error("Anomaly detection failed: %s", e, exc_info=True)
            return {"anomalies": [], "summary": {}, "error": str(e)}

    @staticmethod
    def detect_website_anomalies(daily_trend: list[dict]) -> dict[str, Any]:
        if not daily_trend or len(daily_trend) < 7:
            return {"anomalies": []}

        try:
            df = pd.DataFrame(daily_trend)
            results = {}

            for metric in ["page_views", "visitors", "revenue"]:
                if metric not in df.columns:
                    continue
                vals = df[metric].astype(float)
                mean = vals.mean()
                std = vals.std()
                if std == 0:
                    continue
                z = (vals - mean) / std
                mask = z.abs() > 2.5
                anomalies = []
                for idx in df.index[mask]:
                    anomalies.append({
                        "date": str(df.loc[idx, "date"]),
                        "metric": metric,
                        "value": round(float(df.loc[idx, metric]), 2),
                        "z_score": round(float(z[idx]), 3),
                    })
                results[metric] = anomalies

            return {"anomalies": results}
        except Exception as e:
            logger.error("Website anomaly detection failed: %s", e)
            return {"anomalies": {}}
