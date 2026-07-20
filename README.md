# BI Platform

A modern Business Intelligence platform with real-time dashboards, multi-database support, and interactive data exploration.

## Features

- **Real-time Dashboard** — Live-updating charts via WebSocket (Socket.IO)
- **Multi-database Support** — Connect to PostgreSQL, MySQL, SQLite, or MSSQL
- **Interactive Charts** — Revenue trends, regional breakdowns, product performance (Chart.js)
- **Data Explorer** — Browse, search, sort, and paginate any connected table
- **SQL Query Editor** — Run read-only SQL queries with results displayed inline
- **Dark Theme** — Modern responsive UI with CSS custom properties
- **Authentication** — Flask-Login with role-based access control
- **Rate Limiting** — Flask-Limiter on all API endpoints
- **CORS Support** — Configurable cross-origin resource sharing

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.10+, Flask 3.x, Flask-SocketIO |
| Database ORM | SQLAlchemy 2.0 |
| Data Processing | pandas, NumPy |
| Frontend | Vanilla JS, Chart.js 4, Socket.IO 4 |
| Authentication | Flask-Login, Werkzeug |
| Rate Limiting | Flask-Limiter |
| Testing | pytest, pytest-cov |
| Linting | Ruff, mypy |
| CI/CD | GitHub Actions |
| Containerization | Docker, Docker Compose |

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
# Edit .env with your settings (at minimum, set SECRET_KEY)

# Run the application
python run.py
```

Open http://localhost:5000 in your browser.

**Default credentials:** `admin` / `admin123`

### Docker

```bash
# Production
docker compose up -d

# Development (with hot-reload)
docker compose --profile development up dev
```

## Configuration

| Variable | Default | Description |
|---|---|---|
| `SECRET_KEY` | random | Flask secret key (required in production) |
| `FLASK_DEBUG` | `false` | Enable debug mode |
| `DATABASE_URL` | `sqlite:///bi_platform_demo.db` | Default database URL |
| `ADMIN_USERNAME` | `admin` | Default admin username |
| `ADMIN_PASSWORD` | `admin123` | Default admin password |
| `SQL_READ_ONLY` | `true` | Restrict SQL queries to read-only |
| `RATELIMIT_DEFAULT` | `60/minute` | Default rate limit |

## Project Structure

```
bi-platform/
├── bi_platform/
│   ├── __init__.py          # App factory with Flask extensions
│   ├── auth.py              # Authentication routes and logic
│   ├── config.py            # Configuration classes
│   ├── routes.py            # Main API routes and WebSocket handlers
│   ├── core/
│   │   ├── analytics_engine.py   # Higher-level analytics
│   │   ├── database_connector.py # Multi-DB connector
│   │   ├── data_processor.py     # DataFrame transformations
│   │   └── query_builder.py      # Safe SQL query builder
│   ├── utils/
│   │   └── helpers.py       # Utility functions
│   ├── templates/
│   │   ├── dashboard.html   # Main dashboard page
│   │   └── login.html       # Login page
│   └── static/
│       ├── css/dashboard.css
│       └── js/dashboard.js
├── tests/                   # Test suite
├── .github/workflows/ci.yml # CI/CD pipeline
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml           # Project metadata and tool configs
├── requirements.txt         # Production dependencies
└── requirements-dev.txt     # Development dependencies
```

## Testing

```bash
pytest -v
pytest --cov=bi_platform --cov-report=term-missing
```

## Linting

```bash
ruff check .
ruff format --check .
mypy bi_platform/
```

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/` | Dashboard (requires auth) |
| POST | `/login` | User login |
| GET | `/logout` | User logout |
| GET | `/api/dashboard-data` | Full dashboard payload |
| GET | `/api/tables` | List all tables |
| GET | `/api/table/<name>` | Table metadata |
| GET | `/api/data/<name>` | Paginated table data |
| POST | `/api/query` | Execute read-only SQL |
| POST | `/api/filter` | Filter data by columns |
| POST | `/api/connect` | Connect new database (admin only) |
| POST | `/api/register` | Register new user |

## License

MIT
