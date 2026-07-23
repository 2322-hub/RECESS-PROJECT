import logging
import os

logger = logging.getLogger(__name__)

_celery_app = None


def get_celery_app():
    global _celery_app
    if _celery_app is not None:
        return _celery_app
    try:
        from celery import Celery

        redis_url = os.environ.get("REDIS_URL", "redis://redis:6379/0")
        _celery_app = Celery(
            "bi_platform",
            broker=redis_url,
            backend=redis_url,
        )
        _celery_app.conf.update(
            task_serializer="json",
            accept_content=["json"],
            result_serializer="json",
            timezone="UTC",
            enable_utc=True,
            task_track_started=True,
            task_time_limit=300,
            task_soft_time_limit=240,
            worker_prefetch_multiplier=1,
            worker_max_tasks_per_child=100,
        )
        logger.info("Celery app created with broker: %s", redis_url)
        return _celery_app
    except Exception as e:
        logger.warning("Celery not available: %s", e)
        return None


def init_celery(app):
    celery = get_celery_app()
    if celery:
        celery.conf.update(
            broker_url=app.config.get("REDIS_URL", os.environ.get("REDIS_URL", "redis://redis:6379/0")),
            result_backend=app.config.get("REDIS_URL", os.environ.get("REDIS_URL", "redis://redis:6379/0")),
        )
    return celery
