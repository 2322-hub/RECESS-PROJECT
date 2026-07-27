class TestRoutes:
    def test_login_page(self, client):
        res = client.get("/login")
        assert res.status_code == 200
        assert b"BI Platform" in res.data

    def test_unauthenticated_redirect(self, client):
        res = client.get("/")
        assert res.status_code == 302
        assert "/login" in res.headers["Location"]

    def test_login_success(self, client):
        res = client.post(
            "/login",
            data={"username": "admin", "password": "admin123"},
            follow_redirects=False,
        )
        assert res.status_code == 302

    def test_login_failure(self, client):
        res = client.post(
            "/login",
            data={"username": "admin", "password": "wrong"},
            follow_redirects=True,
        )
        assert b"Invalid username or password" in res.data

    def test_dashboard_authenticated(self, authenticated_client):
        res = authenticated_client.get("/")
        assert res.status_code == 200

    def test_api_dashboard_data(self, authenticated_client):
        res = authenticated_client.get("/api/v1/dashboard-data")
        assert res.status_code == 200
        data = res.get_json()
        assert "kpis" in data
        assert "alerts" in data

    def test_api_tables(self, authenticated_client):
        res = authenticated_client.get("/api/v1/tables")
        assert res.status_code == 200
        tables = res.get_json()
        assert "sales" in tables

    def test_api_table_meta(self, authenticated_client):
        res = authenticated_client.get("/api/v1/table/sales")
        assert res.status_code == 200
        data = res.get_json()
        assert data["table"] == "sales"

    def test_api_query_read_only(self, authenticated_client):
        res = authenticated_client.post(
            "/api/v1/query",
            json={"sql": "SELECT * FROM sales LIMIT 5"},
            content_type="application/json",
        )
        assert res.status_code == 200
        data = res.get_json()
        assert "columns" in data

    def test_api_query_block_write(self, authenticated_client):
        res = authenticated_client.post(
            "/api/v1/query",
            json={"sql": "DROP TABLE sales"},
            content_type="application/json",
        )
        assert res.status_code == 403

    def test_api_query_block_semicolon(self, authenticated_client):
        res = authenticated_client.post(
            "/api/v1/query",
            json={"sql": "SELECT * FROM sales; DROP TABLE sales"},
            content_type="application/json",
        )
        assert res.status_code == 403

    def test_api_filter(self, authenticated_client):
        res = authenticated_client.post(
            "/api/v1/filter",
            json={"table": "sales", "filters": {"region": "North"}},
            content_type="application/json",
        )
        assert res.status_code == 200
        data = res.get_json()
        assert "kpis" in data
        assert "monthly_trends" in data
        assert "revenue_breakdown" in data
        assert data["row_count"] == data["kpis"]["record_count"]
        assert {row["region"] for row in data["regional_comparison"]} == {"North"}

    def test_api_filter_no_matches_returns_valid_payload(self, authenticated_client):
        res = authenticated_client.post(
            "/api/v1/filter",
            json={"table": "sales", "filters": {"region": "Nowhere"}},
            content_type="application/json",
        )
        assert res.status_code == 200
        data = res.get_json()
        assert data["row_count"] == 0
        assert data["kpis"]["record_count"] == 0
        assert data["monthly_trends"] == []

    def test_api_table_data(self, authenticated_client):
        res = authenticated_client.get("/api/v1/data/sales?page=1&per_page=10")
        assert res.status_code == 200
        data = res.get_json()
        assert "columns" in data
        assert "rows" in data
        assert data["per_page"] == 10
        assert len(data["rows"]) == 10

    def test_api_table_data_search_and_sort(self, authenticated_client):
        res = authenticated_client.get("/api/v1/data/sales?page=1&per_page=5&search=North&sort=-total_revenue")
        assert res.status_code == 200
        data = res.get_json()
        assert data["total"] > 0
        assert len(data["rows"]) <= 5
        assert all(row["region"] == "North" for row in data["rows"])
        revenues = [row["total_revenue"] for row in data["rows"]]
        assert revenues == sorted(revenues, reverse=True)

    def test_api_report_export_pdf(self, authenticated_client):
        res = authenticated_client.post(
            "/api/v1/report/pdf",
            json={"conn": "demo"},
            content_type="application/json",
        )
        assert res.status_code == 200
        assert res.mimetype == "application/pdf"

    def test_api_report_export_excel(self, authenticated_client):
        res = authenticated_client.post(
            "/api/v1/report/excel",
            json={"conn": "demo"},
            content_type="application/json",
        )
        assert res.status_code == 200
        assert res.mimetype == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    def test_api_report_invalid_format(self, authenticated_client):
        res = authenticated_client.post(
            "/api/v1/report/csv",
            json={"conn": "demo"},
            content_type="application/json",
        )
        assert res.status_code == 400

    def test_invalid_table_name(self, authenticated_client):
        res = authenticated_client.get("/api/v1/table/invalid;DROP")
        assert res.status_code == 400

    def test_logout(self, authenticated_client):
        res = authenticated_client.get("/logout", follow_redirects=False)
        assert res.status_code == 302

    def test_connect_db_requires_admin(self, client):
        client.post(
            "/api/register",
            json={"username": "viewer1", "password": "password123"},
            content_type="application/json",
        )
        client.post(
            "/login",
            data={"username": "viewer1", "password": "password123"},
            follow_redirects=False,
        )
        res = client.post(
            "/api/v1/connect",
            json={"name": "test", "connection_string": "sqlite:///test.db"},
            content_type="application/json",
        )
        assert res.status_code == 403

    def test_health_check(self, client):
        res = client.get("/health")
        assert res.status_code == 200
        data = res.get_json()
        assert data["status"] == "healthy"

    def test_api_redirect_backward_compat(self, authenticated_client):
        res = authenticated_client.get("/api/tables")
        assert res.status_code == 302
        assert "/api/v1/tables" in res.headers["Location"]
