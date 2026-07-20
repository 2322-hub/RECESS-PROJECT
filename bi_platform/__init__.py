import os
import logging

from flask import Flask
from flask_socketio import SocketIO
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from .config import Config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

socketio = SocketIO()
cors = CORS()
limiter = Limiter(key_func=get_remote_address)


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Validate SECRET_KEY in production
    if not app.debug and app.config["SECRET_KEY"] == "change-me":
        raise RuntimeError(
            "SECRET_KEY must be set to a secure value in production. "
            "Set the SECRET_KEY environment variable."
        )

    socketio.init_app(app, async_mode=app.config["SOCKETIO_ASYNC_MODE"])
    cors.init_app(app)
    limiter.init_app(app)

    from .auth import auth_bp
    app.register_blueprint(auth_bp)

    from .routes import bp as main_bp
    app.register_blueprint(main_bp)

    logger.info("Application created (debug=%s)", app.debug)
    return app
