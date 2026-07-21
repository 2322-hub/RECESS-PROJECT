import os
import re

import pytest

os.environ["DATABASE_URL"] = "sqlite:///test_bi_platform.db"
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["ADMIN_USERNAME"] = "admin"
os.environ["ADMIN_PASSWORD"] = "admin123"
os.environ["LOG_FORMAT"] = "text"

from sqlalchemy.orm import close_all_sessions  # noqa: E402

from bi_platform import create_app  # noqa: E402
from bi_platform.models import Base, Engine, _seed_default_user  # noqa: E402


@pytest.fixture(autouse=True)
def _setup_test_db():
    Base.metadata.create_all(Engine)
    _seed_default_user()
    yield
    close_all_sessions()
    Base.metadata.drop_all(Engine)


@pytest.fixture
def app():
    app = create_app()
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False  # disable CSRF in tests
    with app.app_context():
        yield app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def authenticated_client(client, app):
    app.config["WTF_CSRF_ENABLED"] = False
    client.post(
        "/login",
        data={"username": "admin", "password": "admin123"},
        follow_redirects=False,
    )
    return client


def _extract_csrf(html: bytes) -> str:
    match = re.search(r'name="csrf_token"\s+value="([^"]+)"', html.decode())
    assert match, "CSRF token not found in HTML"
    return match.group(1)
