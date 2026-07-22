import math


def format_number(n: float | int | None, decimals: int = 0) -> str:
    if n is None:
        return "N/A"
    if abs(n) >= 1_000_000:
        return f"{n / 1_000_000:,.{decimals}f}M"
    if abs(n) >= 1_000:
        return f"{n / 1_000:,.{decimals}f}K"
    return f"{n:,.{decimals}f}"


def generate_color_palette(n: int) -> list[str]:
    """Generate *n* visually distinct hex colours."""
    palette = [
        "#2563eb",
        "#10b981",
        "#f59e0b",
        "#ef4444",
        "#8b5cf6",
        "#ec4899",
        "#14b8a6",
        "#f97316",
        "#6366f1",
        "#06b6d4",
        "#84cc16",
        "#e11d48",
        "#0ea5e9",
        "#a855f7",
        "#d946ef",
        "#facc15",
        "#22d3ee",
        "#fb923c",
        "#4ade80",
        "#f43f5e",
    ]
    return palette[:n] if n <= len(palette) else palette * math.ceil(n / len(palette))


def chunk_dataframe(df, chunk_size: int = 50_000):
    """Yield DataFrame chunks."""
    for i in range(0, len(df), chunk_size):
        yield df.iloc[i : i + chunk_size]


def safe_json_serialize(obj):
    """Make objects JSON-serialisable (handles numpy types)."""
    from datetime import date, datetime
    from decimal import Decimal

    import numpy as np
    import pandas as pd

    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, (np.ndarray,)):
        return obj.tolist()
    if isinstance(obj, (pd.Timestamp,)):
        return obj.isoformat()
    if isinstance(obj, pd.Period):
        return str(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
