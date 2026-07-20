import pytest

from bi_platform.core.database_connector import DatabaseConnector


@pytest.fixture
def connector():
    return DatabaseConnector()


class TestDatabaseConnector:
    def test_connect_demo_sqlite(self, connector):
        result = connector.connect_demo_sqlite()
        assert result["status"] == "ok"
        assert result["dialect"] == "sqlite"
        assert "demo" in connector.list_connections()

    def test_list_tables(self, connector):
        connector.connect_demo_sqlite()
        tables = connector.list_tables("demo")
        assert "sales" in tables
        assert "customers" in tables
        assert "website_analytics" in tables

    def test_get_columns(self, connector):
        connector.connect_demo_sqlite()
        cols = connector.get_columns("demo", "sales")
        assert len(cols) > 0
        assert cols[0]["name"] == "id"

    def test_get_table_info(self, connector):
        connector.connect_demo_sqlite()
        info = connector.get_table_info("demo", "sales")
        assert "table" in info
        assert "row_count" in info
        assert "columns" in info
        assert info["row_count"] > 0

    def test_execute_query(self, connector):
        connector.connect_demo_sqlite()
        df = connector.execute_query("demo", "SELECT COUNT(*) as cnt FROM sales")
        assert len(df) == 1
        assert df["cnt"].iloc[0] > 0

    def test_invalid_connection(self, connector):
        with pytest.raises(ValueError, match="No connection named"):
            connector.list_tables("nonexistent")

    def test_seed_idempotent(self, connector):
        connector.connect_demo_sqlite()
        info1 = connector.get_table_info("demo", "sales")
        connector.connect_demo_sqlite()
        info2 = connector.get_table_info("demo", "sales")
        assert info1["row_count"] == info2["row_count"]
