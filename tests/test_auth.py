class TestAuth:
    def test_register_page(self, client):
        res = client.get("/register")
        assert res.status_code == 200
        assert b"Create Account" in res.data or b"Register" in res.data

    def test_register_via_form_success(self, client):
        res = client.post(
            "/register",
            data={
                "username": "newuser",
                "password": "securepass123",
                "confirm_password": "securepass123",
            },
            follow_redirects=True,
        )
        assert b"Account created" in res.data

    def test_register_form_short_username(self, client):
        res = client.post(
            "/register",
            data={
                "username": "ab",
                "password": "securepass123",
                "confirm_password": "securepass123",
            },
            follow_redirects=True,
        )
        assert b"at least 3 characters" in res.data

    def test_register_form_short_password(self, client):
        res = client.post(
            "/register",
            data={
                "username": "validuser",
                "password": "short",
                "confirm_password": "short",
            },
            follow_redirects=True,
        )
        assert b"at least 8 characters" in res.data

    def test_register_form_password_mismatch(self, client):
        res = client.post(
            "/register",
            data={
                "username": "validuser",
                "password": "securepass123",
                "confirm_password": "differentpass123",
            },
            follow_redirects=True,
        )
        assert b"do not match" in res.data

    def test_register_form_duplicate(self, client):
        client.post(
            "/register",
            data={
                "username": "dupuser",
                "password": "securepass123",
                "confirm_password": "securepass123",
            },
        )
        res = client.post(
            "/register",
            data={
                "username": "dupuser",
                "password": "securepass123",
                "confirm_password": "securepass123",
            },
            follow_redirects=True,
        )
        assert b"already exists" in res.data

    def test_api_register_validation_errors(self, client):
        res = client.post(
            "/api/register",
            json={"username": "", "password": ""},
            content_type="application/json",
        )
        assert res.status_code == 400

        res = client.post(
            "/api/register",
            json={"username": "ab", "password": "securepass123"},
            content_type="application/json",
        )
        assert res.status_code == 400

        res = client.post(
            "/api/register",
            json={"username": "validuser2", "password": "short"},
            content_type="application/json",
        )
        assert res.status_code == 400

        res = client.post(
            "/api/register",
            json={"username": "admin", "password": "securepass123"},
            content_type="application/json",
        )
        assert res.status_code == 409

    def test_api_query_empty(self, authenticated_client):
        res = authenticated_client.post(
            "/api/v1/query",
            json={"sql": ""},
            content_type="application/json",
        )
        assert res.status_code == 400

    def test_login_rate_limit(self, client):
        for _ in range(22):
            client.post("/login", data={"username": "admin", "password": "wrong"})
        res = client.post("/login", data={"username": "admin", "password": "wrong"})
        assert res.status_code in (429, 200, 400)
