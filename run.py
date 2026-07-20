import logging
import os
import threading

from bi_platform import create_app, socketio
from bi_platform.routes import start_realtime_loop

app = create_app()

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    rt_thread = threading.Thread(target=start_realtime_loop, daemon=True)
    rt_thread.start()

    debug = app.config.get("DEBUG", False)
    socketio.run(
        app,
        host="0.0.0.0",  # noqa: S104
        port=int(os.environ.get("PORT", 5000)),
        debug=debug,
        allow_unsafe_werkzeug=True,  # werkzeug is acceptable for this demo project
    )
