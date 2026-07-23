import logging
import os

from flask import Flask, jsonify
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_socketio import SocketIO
from flask_wtf.csrf import CSRFProtect
from prometheus_flask_exporter import PrometheusMetrics

from .config import Config

logger = logging.getLogger(__name__)

socketio = SocketIO()
cors = CORS()
limiter = Limiter(key_func=get_remote_address)
csrf = CSRFProtect()
metrics = PrometheusMetrics.for_app_factory()
metrics.info("bi_platform_info", "BI Platform", version="2.0.0")


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    if app.config["SECRET_KEY"] == "change-me":
        raise RuntimeError("SECRET_KEY must be changed from the default value.")

    if app.config["SENTRY_DSN"]:
        import sentry_sdk
        from sentry_sdk.integrations.flask import FlaskIntegration

        sentry_sdk.init(
            dsn=app.config["SENTRY_DSN"],
            integrations=[FlaskIntegration()],
            traces_sample_rate=float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
        )

    from .models import init_db

    init_db()

    socketio.init_app(app, async_mode=app.config["SOCKETIO_ASYNC_MODE"])
    cors.init_app(app, origins=app.config.get("CORS_ORIGINS", "*"))
    limiter.init_app(app)
    csrf.init_app(app)
    metrics.init_app(app)

    from .routes import (
        api_connect_db,
        api_custom_query,
        api_custom_query2,
        api_dashboard_data,
        api_filter,
        api_list_connections,
        handle_connect,
        handle_refresh,
        api_forecast,
        api_anomalies,
        api_generate_report,
        api_nl_query,
        api_user_role,
    )

    csrf.exempt(api_dashboard_data)
    csrf.exempt(api_custom_query)
    csrf.exempt(api_custom_query2)
    csrf.exempt(api_filter)
    csrf.exempt(api_connect_db)
    csrf.exempt(api_list_connections)
    csrf.exempt(handle_connect)
    csrf.exempt(handle_refresh)
    csrf.exempt(api_forecast)
    csrf.exempt(api_anomalies)
    csrf.exempt(api_generate_report)
    csrf.exempt(api_nl_query)
    csrf.exempt(api_user_role)

    from .auth import auth_bp
    app.register_blueprint(auth_bp)

    from .admin import admin_bp
    app.register_blueprint(admin_bp)

    from .saved_views import saved_views_bp, init_saved_views_csrf
    app.register_blueprint(saved_views_bp)
    init_saved_views_csrf(csrf)

    from .routes import bp as main_bp
    app.register_blueprint(main_bp)

    from .routes import api_bp
    app.register_blueprint(api_bp)

    @app.route("/health")
    @limiter.exempt
    def health_check():
        healthy = True
        checks = {"status": "healthy", "version": "2.0.0"}

        try:
            from sqlalchemy import text
            from .models import SessionLocal

            s = SessionLocal()
            try:
                s.execute(text("SELECT 1"))
                checks["database"] = "ok"
            finally:
                s.close()
        except Exception:
            checks["database"] = "error"
            healthy = False

        try:
            from .cache import get_redis
            r = get_redis()
            if r:
                r.ping()
                checks["redis"] = "ok"
            else:
                checks["redis"] = "memory-fallback"
        except Exception:
            checks["redis"] = "unavailable"

        if not healthy:
            from flask import make_response
            resp = make_response(jsonify({"status": "unhealthy", "checks": checks}))
            resp.status_code = 503
            return resp

        return jsonify(checks)

    logger.info("Application created (debug=%s)", app.debug)
    return app
