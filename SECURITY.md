# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability, please report it responsibly:

1. **Do NOT** open a public GitHub issue
2. Email the maintainers or use GitHub's private vulnerability reporting
3. Include a description of the vulnerability and steps to reproduce
4. Allow reasonable time for a fix before public disclosure

## Security Measures

This application implements the following security controls:

- **CSRF Protection** — Flask-WTF CSRF tokens on all form submissions
- **Rate Limiting** — Flask-Limiter on all endpoints (login: 20/min, registration: 5/min, API: 10-30/min)
- **Session Security** — HttpOnly cookies, SameSite=Lax, session regeneration on login
- **Password Hashing** — Werkzeug's `generate_password_hash` with PBKDF2
- **SQL Injection Prevention** — Table name regex validation, read-only query enforcement, parameterized queries via SQLAlchemy
- **XSS Prevention** — HTML escaping on all dynamic content (Jinja2 auto-escaping + client-side `escapeHtml()`)
- **WebSocket Authentication** — Session-based authentication required for all WebSocket connections
- **CORS** — Configurable origins via `CORS_ORIGINS` environment variable
- **Content Security Policy** — CSP headers on all HTML pages
- **Docker Security** — Multi-stage build, non-root user, read-only filesystem, no-new-privileges
- **Dependency Auditing** — pip-audit in CI pipeline

## Authentication

- Default admin credentials must be changed via `ADMIN_USERNAME` and `ADMIN_PASSWORD` environment variables
- Passwords require a minimum of 8 characters
- User sessions expire after 1 hour of inactivity

## Supported Versions

| Version | Supported |
|---------|-----------|
| 1.0.x   | Yes       |
| < 1.0   | No        |
