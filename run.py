import logging
import os

from bi_platform import create_app, socketio

app = create_app()

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    debug = app.config.get("DEBUG", False)
    socketio.run(
        app,
        host="0.0.0.0",  # noqa: S104
        port=int(os.environ.get("PORT", 5000)),
        debug=debug,
        allow_unsafe_werkzeug=True,  # werkzeug is acceptable for this demo project
    )
