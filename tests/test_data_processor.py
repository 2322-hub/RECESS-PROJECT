import pandas as pd
import pytest

from bi_platform.core.data_processor import DataProcessor


@pytest.fixture
def sample_df():
    return pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=100, freq="D").astype(str),
        "region": ["North", "South", "East", "West"] * 25,
        "product_category": ["Electronics", "Clothing", "Food", "Furniture"] * 25,
        "product_name": ["Widget A", "Widget B", "Gadget X", "Gadget Y"] * 25,
        "quantity": list(range(1, 101)),
        "unit_price": [10.0] * 100,
        "total_revenue": [1000.0] * 100,
        "cost": [500.0] * 100,
        "profit": [500.0] * 100,
        "customer_segment": ["Enterprise", "SMB", "Consumer", "Enterprise"] * 25,
    })


@pytest.fixture
def dp():
    return DataProcessor()


class TestDataProcessor:
    def test_time_series(self, dp, sample_df):
        result = dp.time_series(sample_df, "date", "total_revenue", freq="M")
        assert "date" in result.columns
        assert "value" in result.columns
        assert len(result) > 0

    def test_group_by_sum(self, dp, sample_df):
        result = dp.group_by_sum(sample_df, "region", "total_revenue")
        assert "label" in result.columns
        assert "value" in result.columns
        assert len(result) == 4

    def test_correlation_matrix(self, dp, sample_df):
        result = dp.correlation_matrix(sample_df)
        assert "columns" in result
        assert "values" in result
        assert len(result["columns"]) > 0

    def test_profile(self, dp, sample_df):
        result = dp.profile(sample_df)
        assert "date" in result
        assert "total_revenue" in result
        assert "dtype" in result["total_revenue"]
        assert "mean" in result["total_revenue"]

    def test_compute_kpis(self, dp, sample_df):
        kpis = dp.compute_kpis(sample_df)
        assert "total_revenue" in kpis
        assert "total_profit" in kpis
        assert "profit_margin" in kpis
        assert "record_count" in kpis
        assert kpis["record_count"] == 100

    def test_top_n(self, dp, sample_df):
        result = dp.top_n(sample_df, "region", "total_revenue", n=2)
        assert len(result) == 2
        assert "label" in result[0]
        assert "value" in result[0]

    def test_bottom_n(self, dp, sample_df):
        result = dp.bottom_n(sample_df, "region", "total_revenue", n=2)
        assert len(result) == 2

    def test_rolling_average(self, dp, sample_df):
        result = dp.rolling_average(sample_df, "date", "total_revenue", window=7)
        assert "rolling_avg" in result.columns
        assert len(result) == 100
