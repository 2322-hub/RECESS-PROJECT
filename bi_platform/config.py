import os
import secrets
from pathlib import Path


def _get_or_create_secret_key() -> str:
    """Return SECRET_KEY from env, or persist a generated one in .secret_key file."""
    env_key = os.environ.get("SECRET_KEY")
    if env_key:
        return env_key

    key_file = Path(".secret_key")
    if key_file.exists():
        return key_file.read_text().strip()

    key = secrets.token_hex(32)
    key_file.write_text(key)
    return key


class Config:
    SECRET_KEY = _get_or_create_secret_key()
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "sqlite:///bi_platform_demo.db",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    DEBUG = os.environ.get("FLASK_DEBUG", "false").lower() in ("true", "1", "yes")

    # Supported database backends
    SUPPORTED_DBS = {
        "postgresql": "postgresql+psycopg2",
        "mysql": "mysql+pymysql",
        "sqlite": "sqlite",
        "mssql": "mssql+pyodbc",
    }

    # Data processing limits
    MAX_ROWS_IN_MEMORY = 500_000
    CHUNK_SIZE = 50_000
    QUERY_TIMEOUT = 30

    # WebSocket settings
    SOCKETIO_ASYNC_MODE = "threading"
    REALTIME_INTERVAL = 5  # seconds between real-time pushes

    # SQL query restrictions
    SQL_READ_ONLY = os.environ.get("SQL_READ_ONLY", "true").lower() in ("true", "1", "yes")
    SQL_ALLOWED_TABLES = {"sales", "customers", "website_analytics"}
    SQL_MAX_ROWS = 1000

    # Rate limiting
    RATELIMIT_DEFAULT = os.environ.get("RATELIMIT_DEFAULT", "60/minute")
    RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI", "memory://")
