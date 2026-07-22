from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest

from bi_platform.core.analytics_engine import AnalyticsEngine
from bi_platform.core.database_connector import DatabaseConnector


@pytest.fixture
def sample_sales():
    rng = np.random.default_rng(42)
    n = 200
    dates = pd.date_range("2024-01-01", periods=365, freq="D")
    return pd.DataFrame(
        {
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
        }
    )


@pytest.fixture
def sample_customers():
    return pd.DataFrame(
        {
            "id": range(1, 51),
            "name": [f"Customer_{i}" for i in range(1, 51)],
            "email": [f"cust{i}@test.com" for i in range(1, 51)],
            "region": ["North"] * 25 + ["South"] * 25,
            "signup_date": ["2024-01-01"] * 50,
            "lifetime_value": np.linspace(100, 10000, 50).tolist(),
            "orders_count": list(range(1, 51)),
            "segment": ["Enterprise"] * 25 + ["SMB"] * 25,
        }
    )


@pytest.fixture
def sample_website():
    return pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=90, freq="D").astype(str),
            "page_views": np.random.randint(500, 5000, 90).tolist(),
            "unique_visitors": np.random.randint(200, 3000, 90).tolist(),
            "bounce_rate": np.random.uniform(0.2, 0.7, 90).tolist(),
            "avg_session_duration": np.random.uniform(30, 300, 90).tolist(),
            "conversions": np.random.randint(0, 50, 90).tolist(),
            "revenue": np.random.uniform(0, 5000, 90).tolist(),
        }
    )


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


class TestSQLModeAnalytics:
    """Tests for the SQL-mode analytics path (build_dashboard_payload_sql)."""

    @pytest.fixture
    def mock_db(self):
        db = MagicMock(spec=DatabaseConnector)
        db.sql_kpis.return_value = {
            "total_revenue": 500000,
            "total_profit": 100000,
            "total_orders": 5000,
            "avg_order_value": 100,
        }
        db.sql_revenue_breakdown.return_value = [
            {"region": "North", "total_revenue": 125000},
            {"region": "South", "total_revenue": 125000},
            {"region": "East", "total_revenue": 125000},
            {"region": "West", "total_revenue": 125000},
        ]
        db.sql_monthly_trends.return_value = [
            {"date": "2024-01", "revenue": 40000},
            {"date": "2024-02", "revenue": 45000},
        ]
        db.sql_regional_comparison.return_value = [
            {"region": "North", "revenue": 125000, "orders": 1250, "avg_order": 100},
        ]
        db.sql_product_performance.return_value = [
            {"product_category": "Electronics", "total_revenue": 200000},
        ]
        db.sql_top_n.return_value = [
            {"label": "Widget A", "value": 50000},
        ]
        db.sql_website_summary.return_value = {
            "total_page_views": 100000,
            "avg_bounce_rate": 0.35,
        }
        db.sql_customer_insights.return_value = {
            "total_customers": 500,
            "avg_lifetime_value": 2000,
        }
        db.execute_query.return_value = pd.DataFrame(
            {
                "total_revenue": np.random.uniform(100, 10000, 5000),
                "cost": np.random.uniform(50, 5000, 5000),
                "profit": np.random.uniform(50, 5000, 5000),
                "quantity": np.random.randint(1, 50, 5000),
                "unit_price": np.random.uniform(5, 500, 5000),
            }
        )
        db.sql_correlation_matrix.return_value = {
            "columns": ["total_revenue", "cost", "profit", "quantity", "unit_price"],
            "matrix": [[1.0, 0.5, 0.5, 0.3, 0.2]] * 5,
        }
        return db

    def test_build_dashboard_payload_sql_returns_all_keys(self, engine, mock_db):
        payload = engine.build_dashboard_payload_sql(mock_db, "test_conn")
        assert "kpis" in payload
        assert "revenue_breakdown" in payload
        assert "monthly_trends" in payload
        assert "regional_comparison" in payload
        assert "product_performance" in payload
        assert "top_products" in payload
        assert "website_analytics" in payload
        assert "customer_insights" in payload
        assert "correlation" in payload
        assert "profile" in payload

    def test_build_dashboard_payload_sql_calls_correct_methods(self, engine, mock_db):
        engine.build_dashboard_payload_sql(mock_db, "test_conn")
        mock_db.sql_kpis.assert_called_once_with("test_conn")
        mock_db.sql_revenue_breakdown.assert_called_once_with("test_conn")
        mock_db.sql_monthly_trends.assert_called_once_with("test_conn")
        mock_db.sql_regional_comparison.assert_called_once_with("test_conn")
        mock_db.sql_product_performance.assert_called_once_with("test_conn")
        mock_db.sql_top_n.assert_called_once()
        mock_db.sql_website_summary.assert_called_once_with("test_conn")
        mock_db.sql_customer_insights.assert_called_once_with("test_conn")

    def test_build_dashboard_payload_sql_has_correlation(self, engine, mock_db):
        payload = engine.build_dashboard_payload_sql(mock_db, "test_conn")
        assert len(payload["correlation"]["columns"]) == 5
        assert len(payload["correlation"]["matrix"]) == 5

    def test_build_dashboard_payload_sql_has_profile(self, engine, mock_db):
        payload = engine.build_dashboard_payload_sql(mock_db, "test_conn")
        assert len(payload["profile"]) > 0
        first_col = list(payload["profile"].keys())[0]
        assert "mean" in payload["profile"][first_col]

    def test_build_dashboard_payload_sql_correlation_error_handled(self, engine, mock_db):
        db = mock_db
        db.execute_query.side_effect = Exception("query failed")
        payload = engine.build_dashboard_payload_sql(db, "test_conn")
        assert payload["correlation"] == {}
        assert payload["profile"] == {}


class TestExportEndpoint:
    """Tests for the CSV export endpoints."""

    def test_csv_export_headers(self, authenticated_client):
        resp = authenticated_client.get("/api/v1/export/sales")
        assert resp.status_code == 200
        assert b"date" in resp.data
        assert b"region" in resp.data

    def test_csv_export_bad_table_name(self, authenticated_client):
        resp = authenticated_client.get("/api/v1/export/evil%3B%20DROP%20TABLE")
        assert resp.status_code == 400
