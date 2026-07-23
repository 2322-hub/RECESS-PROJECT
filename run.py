import logging
import os
import threading

from dotenv import load_dotenv

load_dotenv(override=True)

from bi_platform import create_app, socketio
from bi_platform.config import Config
from bi_platform.routes import start_realtime_loop

app = create_app()

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    debug = app.config.get("DEBUG", False)

    t = threading.Thread(target=start_realtime_loop, daemon=True)
    t.start()
    logger.info("Real-time push loop started (interval=%ss)", Config.REALTIME_INTERVAL)

    try:
        from bi_platform.tasks import get_celery_app
        celery = get_celery_app()
        if celery:
            logger.info("Celery app initialized")
    except Exception as e:
        logger.warning("Celery not available: %s", e)

    socketio.run(
        app,
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=debug,
        allow_unsafe_werkzeug=debug,
    )
