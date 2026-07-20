import pytest

from bi_platform.core.query_builder import QueryBuilder


class TestQueryBuilder:
    def test_select_basic(self):
        sql, params = QueryBuilder.select("sales")
        assert sql == "SELECT * FROM sales"
        assert params == {}

    def test_select_columns(self):
        sql, params = QueryBuilder.select("sales", columns=["region", "total_revenue"])
        assert "region" in sql
        assert "total_revenue" in sql

    def test_select_with_limit(self):
        sql, params = QueryBuilder.select("sales", limit=10)
        assert "LIMIT" in sql
        assert params["limit"] == 10

    def test_select_with_order(self):
        sql, params = QueryBuilder.select("sales", order_by="-total_revenue")
        assert "DESC" in sql

    def test_select_invalid_table(self):
        with pytest.raises(ValueError, match="Invalid identifier"):
            QueryBuilder.select("sales; DROP TABLE users")

    def test_aggregate(self):
        sql, params = QueryBuilder.aggregate("sales", "region", "total_revenue", "SUM")
        assert "GROUP BY region" in sql
        assert "SUM(total_revenue)" in sql

    def test_aggregate_invalid_func(self):
        with pytest.raises(ValueError, match="Unsupported aggregate"):
            QueryBuilder.aggregate("sales", "region", "total_revenue", "HACK")

    def test_date_filter(self):
        where = QueryBuilder.date_filter("date", start="2024-01-01", end="2024-12-31")
        assert "date >= :date_start" in where
        assert "date <= :date_end" in where

    def test_date_filter_params(self):
        params = QueryBuilder.date_filter_params(start="2024-01-01", end="2024-12-31")
        assert params["date_start"] == "2024-01-01"
        assert params["date_end"] == "2024-12-31"
