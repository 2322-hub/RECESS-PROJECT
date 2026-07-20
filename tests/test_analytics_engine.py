import pytest

from bi_platform.core.analytics_engine import AnalyticsEngine
from bi_platform.core.data_processor import DataProcessor
import pandas as pd
import numpy as np


@pytest.fixture
def sample_sales():
    rng = np.random.default_rng(42)
    n = 200
    dates = pd.date_range("2024-01-01", periods=365, freq="D")
    return pd.DataFrame({
        "date": [str(dates[rng.integers(0, len(dates))].date()) for _ in range(n)],
        "region": rng.choice(["North", "South", "East", "West"], n).tolist(),
        "product_category": rng.choice(["Electronics", "Clothing", "Food"], n).tolist(),
        "product_name": rng.choice(["Widget A", "Widget B", "Gadget X"], n).tolist(),
        "quantity": rng.integers(1, 50, n).tolist(),
        "unit_price": rng.uniform(5, 500, n).tolist(),
        "total_revenue": rng.uniform(100, 10000, n).tolist(),
        "cost": rng.uniform(50, 5000, n).tolist(),
        "profit": rng.uniform(50, 5000, n).tolist(),
        "customer_segment": rng.choice(["Enterprise", "SMB"], n).tolist(),
    })


@pytest.fixture
def sample_customers():
    return pd.DataFrame({
        "id": range(1, 51),
        "name": [f"Customer_{i}" for i in range(1, 51)],
        "email": [f"cust{i}@test.com" for i in range(1, 51)],
        "region": ["North"] * 25 + ["South"] * 25,
        "signup_date": ["2024-01-01"] * 50,
        "lifetime_value": np.linspace(100, 10000, 50).tolist(),
        "orders_count": list(range(1, 51)),
        "segment": ["Enterprise"] * 25 + ["SMB"] * 25,
    })


@pytest.fixture
def sample_website():
    return pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=90, freq="D").astype(str),
        "page_views": np.random.randint(500, 5000, 90).tolist(),
        "unique_visitors": np.random.randint(200, 3000, 90).tolist(),
        "bounce_rate": np.random.uniform(0.2, 0.7, 90).tolist(),
        "avg_session_duration": np.random.uniform(30, 300, 90).tolist(),
        "conversions": np.random.randint(0, 50, 90).tolist(),
        "revenue": np.random.uniform(0, 5000, 90).tolist(),
    })


@pytest.fixture
def engine():
    return AnalyticsEngine()


class TestAnalyticsEngine:
    def test_revenue_breakdown(self, engine, sample_sales):
        result = engine.revenue_breakdown(sample_sales)
        assert "region" in result
        assert "product_category" in result
        assert "customer_segment" in result

    def test_monthly_trends(self, engine, sample_sales):
        result = engine.monthly_trends(sample_sales)
        assert len(result) > 0
        assert "date" in result[0]
        assert "revenue" in result[0]

    def test_regional_comparison(self, engine, sample_sales):
        result = engine.regional_comparison(sample_sales)
        assert len(result) == 4
        assert "region" in result[0]

    def test_product_performance(self, engine, sample_sales):
        result = engine.product_performance(sample_sales)
        assert len(result) > 0
        assert "product_category" in result[0]

    def test_website_summary(self, engine, sample_website):
        result = engine.website_summary(sample_website)
        assert "total_page_views" in result
        assert "avg_bounce_rate" in result
        assert "daily_trend" in result

    def test_customer_insights(self, engine, sample_customers):
        result = engine.customer_insights(sample_customers)
        assert "total_customers" in result
        assert "avg_lifetime_value" in result
        assert "by_segment" in result

    def test_build_dashboard_payload(self, engine, sample_sales, sample_customers, sample_website):
        payload = engine.build_dashboard_payload(sample_sales, sample_customers, sample_website)
        assert "kpis" in payload
        assert "revenue_breakdown" in payload
        assert "monthly_trends" in payload
        assert "customer_insights" in payload
        assert "website_analytics" in payload
