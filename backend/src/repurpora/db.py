"""Postgres (Supabase) access via a small psycopg connection pool."""

from __future__ import annotations

import logging
from contextlib import contextmanager
from functools import lru_cache

from repurpora.settings import get_settings

log = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _pool():
    from psycopg_pool import ConnectionPool

    s = get_settings()
    url = s.app_database_url or s.database_url
    if not url:
        return None
    pool = ConnectionPool(url, min_size=0, max_size=3, timeout=8,
                          kwargs={"autocommit": True, "prepare_threshold": None}, open=False)
    pool.open(wait=False)
    return pool


@contextmanager
def conn():
    p = _pool()
    if p is None:
        raise RuntimeError("DATABASE_URL not configured")
    with p.connection() as c:
        yield c


def db_available() -> bool:
    try:
        with conn() as c:
            c.execute("select 1")
        return True
    except Exception as exc:
        log.info("db unavailable: %s", type(exc).__name__)
        return False


def vec_literal(v: list[float]) -> str:
    return "[" + ",".join(f"{x:.6f}" for x in v) + "]"
