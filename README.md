# BI Platform

[![CI](https://github.com/2322-hub/RECESS-PROJECT/actions/workflows/ci.yml/badge.svg)](https://github.com/2322-hub/RECESS-PROJECT/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

A modern Business Intelligence platform with real-time dashboards, multi-database support, and interactive data exploration.

## Features

- **Real-time Dashboard** — Live-updating charts via WebSocket (Socket.IO)
- **Multi-database Support** — Connect to PostgreSQL, MySQL, SQLite, or MSSQL
- **Interactive Charts** — Revenue trends, regional breakdowns, product performance (Chart.js)
- **Data Explorer** — Browse, search, sort, and paginate any connected table
- **SQL Query Editor** — Run read-only SQL queries with results displayed inline
- **Dark Theme** — Modern responsive UI with CSS custom properties and WCAG accessibility
- **Authentication** — Session-based auth with role-based access control
- **Rate Limiting** — Flask-Limiter on all API endpoints (brute-force protection on login)
- **CSRF Protection** — Flask-WTF tokens on all form submissions
- **Security Hardened** — CSP headers, CORS restrictions, SQL injection prevention, Docker non-root

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.10+, Flask 3.x, Flask-SocketIO |
| Database ORM | SQLAlchemy 2.0 |
| Data Processing | pandas, NumPy |
| Frontend | Vanilla JS, Chart.js 4, Socket.IO 4 |
| Authentication | Custom session-based, Werkzeug password hashing |
| Security | Flask-WTF (CSRF), Flask-Limiter, Flask-CORS |
| Testing | pytest, pytest-cov |
| Linting | Ruff, mypy |
| CI/CD | GitHub Actions (lint, test matrix, security audit, Docker) |
| Containerization | Docker (multi-stage), Docker Compose |

## Quick Start

### Local Development

```bash
# Clone the repository
git clone https://github.com/2322-hub/RECESS-PROJECT.git
cd RECESS-PROJECT

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Set up environment
cp .env.example .env
# Edit .env — at minimum, set SECRET_KEY and ADMIN_PASSWORD to secure values

# Run the application
python run.py
```

Open http://localhost:5000 in your browser.

**Default credentials:** `admin` / `admin123` (change in production!)

### Docker

```bash
# Set environment variables (required)
export SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
export ADMIN_PASSWORD=$(python -c "import secrets; print(secrets.token_hex(16))")

# Production
docker compose up -d

# Development (with hot-reload)
docker compose --profile development up dev
```

## Configuration

| Variable | Default | Description |
|---|---|---|
| `SECRET_KEY` | random | Flask secret key (**required in production**) |
| `FLASK_DEBUG` | `false` | Enable debug mode |
| `PORT` | `5000` | Server port |
| `DATABASE_URL` | `sqlite:///bi_platform_demo.db` | Default database URL |
| `ADMIN_USERNAME` | `admin` | Default admin username |
| `ADMIN_PASSWORD` | `admin123` | Default admin password (**change in production**) |
| `SQL_READ_ONLY` | `true` | Restrict SQL queries to read-only |
| `CORS_ORIGINS` | `*` | Allowed CORS origins (restrict in production) |
| `RATELIMIT_DEFAULT` | `60/minute` | Default rate limit |
| `RATELIMIT_STORAGE_URI` | `memory://` | Rate limit backend |

## Project Structure

```
bi-platform/
├── bi_platform/
│   ├── __init__.py          # App factory, CSRF, CORS, health check
│   ├── auth.py              # Authentication routes and logic
│   ├── config.py            # Configuration with security defaults
│   ├── routes.py            # Main API routes and WebSocket handlers
│   ├── core/
│   │   ├── analytics_engine.py   # Higher-level analytics
│   │   ├── database_connector.py # Multi-DB connector
│   │   ├── data_processor.py     # DataFrame transformations
│   │   └── query_builder.py      # Safe SQL query builder
│   ├── utils/
│   │   └── helpers.py       # Utility functions
│   ├── templates/           # Jinja2 templates (CSRF-protected)
│   └── static/              # CSS, JS (accessibility-compliant)
├── tests/                   # Test suite (46+ tests)
├── .github/workflows/ci.yml # CI/CD (lint, test, security, Docker)
├── Dockerfile               # Multi-stage, non-root
├── docker-compose.yml       # Production + dev profiles
├── SECURITY.md              # Security policy
├── LICENSE                  # MIT License
├── pyproject.toml           # Project metadata and tool configs
├── requirements.txt         # Production dependencies (pinned)
└── requirements-dev.txt     # Development dependencies
```

## Testing

```bash
pytest -v
pytest --cov=bi_platform --cov-report=term-missing
```

## Linting & Type Checking

```bash
ruff check .
ruff format --check .
mypy bi_platform/ --ignore-missing-imports
```

## Security

See [SECURITY.md](SECURITY.md) for details on security measures and vulnerability reporting.

## API Endpoints

| Method | Endpoint | Auth | Rate Limit | Description |
|---|---|---|---|---|
| GET | `/health` | No | None | Health check |
| GET | `/` | Yes | — | Dashboard |
| POST | `/login` | No | 20/min | User login |
| POST | `/register` | No | 5/min | User registration |
| GET | `/logout` | Yes | — | User logout |
| GET | `/api/dashboard-data` | Yes | 30/min | Full dashboard payload |
| GET | `/api/tables` | Yes | — | List all tables |
| GET | `/api/table/<name>` | Yes | — | Table metadata |
| GET | `/api/data/<name>` | Yes | — | Paginated table data |
| POST | `/api/query` | Yes | 10/min | Execute read-only SQL |
| POST | `/api/filter` | Yes | 30/min | Filter data by columns |
| POST | `/api/connect` | Yes (admin) | 5/min | Connect new database |

## License

MIT — see [LICENSE](LICENSE)
