"""Two-tier TTL cache for tool calls (Redis if configured, in-process otherwise).

Also exposes hit/miss counters so the evaluation suite can report cache hit rate.
"""

from __future__ import annotations

import functools
import hashlib
import json
import logging
import time
from collections.abc import Callable
from typing import Any

from repurpora.settings import get_settings

log = logging.getLogger(__name__)
STATS = {"hits": 0, "misses": 0}
_LOCAL: dict[str, tuple[float, Any]] = {}
_redis = None
_redis_checked = False


def _get_redis():
    global _redis, _redis_checked
    if _redis_checked:
        return _redis
    _redis_checked = True
    url = get_settings().redis_url
    if not url:
        return None
    try:
        import redis

        client = redis.Redis.from_url(url, socket_timeout=1.5)
        client.ping()
        _redis = client
    except Exception as exc:
        log.warning("redis unavailable (%s) - using in-process cache", type(exc).__name__)
    return _redis


def _key(ns: str, args: tuple, kwargs: dict) -> str:
    raw = json.dumps([args, kwargs], sort_keys=True, default=str)
    return f"repurpora:{ns}:{hashlib.sha256(raw.encode()).hexdigest()[:24]}"


def cached(ns: str, ttl: int | None = None) -> Callable:
    def deco(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            t = ttl or get_settings().tool_cache_ttl_s
            k = _key(ns, args, kwargs)
            r = _get_redis()
            if r is not None:
                try:
                    hit = r.get(k)
                    if hit is not None:
                        STATS["hits"] += 1
                        return json.loads(hit)
                except Exception:
                    pass
            else:
                hit = _LOCAL.get(k)
                if hit and hit[0] > time.time():
                    STATS["hits"] += 1
                    return hit[1]
            STATS["misses"] += 1
            val = fn(*args, **kwargs)
            try:
                if r is not None:
                    r.setex(k, t, json.dumps(val, default=str))
                else:
                    _LOCAL[k] = (time.time() + t, val)
            except Exception:
                pass
            return val

        return wrapper

    return deco


def hit_rate() -> float:
    total = STATS["hits"] + STATS["misses"]
    return STATS["hits"] / total if total else 0.0
