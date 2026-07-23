import json
import logging
import os
import time
from typing import Any

logger = logging.getLogger(__name__)

_redis_client = None
_redis_last_attempt = 0
_REDIS_RETRY_INTERVAL = 30


def get_redis():
    global _redis_client, _redis_last_attempt
    if _redis_client is not None:
        return _redis_client
    now = time.time()
    if now - _redis_last_attempt < _REDIS_RETRY_INTERVAL:
        return None
    _redis_last_attempt = now
    try:
        import redis as redis_lib

        url = os.environ.get("REDIS_URL", "redis://redis:6379/0")
        _redis_client = redis_lib.Redis.from_url(url, decode_responses=True, socket_connect_timeout=3)
        _redis_client.ping()
        logger.info("Redis cache connected: %s", url)
        return _redis_client
    except Exception:
        logger.debug("Redis unavailable, using in-memory fallback")
        _redis_client = None
        return None


_memory_cache: dict[str, tuple[float, Any]] = {}
MEMORY_TTL = 30
_MAX_MEMORY_CACHE_ENTRIES = 500


def _evict_stale():
    """Remove expired entries and enforce max size."""
    now = time.time()
    expired = [k for k, (ts, _) in _memory_cache.items() if (now - ts) >= MEMORY_TTL]
    for k in expired:
        del _memory_cache[k]
    if len(_memory_cache) > _MAX_MEMORY_CACHE_ENTRIES:
        sorted_keys = sorted(_memory_cache, key=lambda k: _memory_cache[k][0])
        to_remove = sorted_keys[: len(sorted_keys) - _MAX_MEMORY_CACHE_ENTRIES]
        for k in to_remove:
            del _memory_cache[k]


class CacheLayer:
    TTL = 60

    @staticmethod
    def get(key: str) -> Any | None:
        r = get_redis()
        if r:
            try:
                val = r.get(f"bi:{key}")
                if val:
                    return json.loads(val)
            except Exception:
                logger.debug("Redis GET failed for key: %s", key)
            return None

        now = time.time()
        entry = _memory_cache.get(key)
        if entry and (now - entry[0]) < MEMORY_TTL:
            return entry[1]
        if entry:
            del _memory_cache[key]
        return None

    @staticmethod
    def set(key: str, value: Any, ttl: int | None = None):
        ttl = ttl or CacheLayer.TTL
        r = get_redis()
        if r:
            try:
                r.setex(f"bi:{key}", ttl, json.dumps(value, default=str))
                return
            except Exception:
                logger.debug("Redis SET failed for key: %s", key)

        _memory_cache[key] = (time.time(), value)
        _evict_stale()

    @staticmethod
    def invalidate(pattern: str = "*"):
        r = get_redis()
        if r:
            try:
                keys = r.keys(f"bi:{pattern}")
                if keys:
                    r.delete(*keys)
            except Exception:
                logger.debug("Redis DELETE failed for pattern: %s", pattern)
        if not pattern or pattern == "*":
            _memory_cache.clear()
        else:
            to_del = [k for k in _memory_cache if pattern in k]
            for k in to_del:
                del _memory_cache[k]

    @staticmethod
    def get_or_set(key: str, factory, ttl: int | None = None) -> Any:
        cached = CacheLayer.get(key)
        if cached is not None:
            return cached
        value = factory()
        CacheLayer.set(key, value, ttl)
        return value
