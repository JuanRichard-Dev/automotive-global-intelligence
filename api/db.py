"""PostgreSQL access with bounded, reusable connections per serverless worker.

The Supabase transaction pooler handles connections across Vercel instances.
This small local pool avoids opening a fresh TCP/TLS connection for every
SQL statement in /bootstrap and /painel.
"""
import os
import time
import threading

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from fastapi.encoders import jsonable_encoder

DSN = os.getenv('DATABASE_URL') or os.getenv('POSTGRES_URL') or 'postgresql://automotive:automotive_local@127.0.0.1:55432/automotive'

# Bounded per function instance; min_size=0 avoids pre-opening idle sockets.
# Disable prepared statements for Supabase transaction-pooler compatibility.
_pool = ConnectionPool(
    conninfo=DSN,
    min_size=0,
    max_size=3,
    timeout=8,
    max_idle=60,
    kwargs={
        'row_factory': dict_row,
        'options': '-c statement_timeout=20000',
        'prepare_threshold': None,
        'connect_timeout': 7,
    },
    open=True,
)

_cache = {}
_lock = threading.RLock()
_pending = {}


def query(sql, params=(), one=False):
    """Execute read-only SQL with a reused connection.

    A thawed serverless function may have a stale connection. Retry once
    on connection-level failures only (never on SQL or business errors).
    """
    for attempt in range(2):
        try:
            with _pool.connection() as conn:
                rows = conn.execute(sql, params or None).fetchall()
            result = (rows[0] if rows else None) if one else rows
            return jsonable_encoder(result)
        except (psycopg.OperationalError, psycopg.InterfaceError):
            if attempt:
                raise


def cached(key, fn, ttl=60):
    """Per-instance TTL cache with per-key single-flight on misses."""
    now = time.monotonic()
    with _lock:
        value = _cache.get(key)
        if value and now - value[0] < ttl:
            return value[1]
        key_lock = _pending.setdefault(key, threading.Lock())

    with key_lock:
        with _lock:
            value = _cache.get(key)
            if value and time.monotonic() - value[0] < ttl:
                return value[1]

        result = fn()
        with _lock:
            if len(_cache) >= 256:
                _cache.clear()
                _pending.clear()
            _cache[key] = (time.monotonic(), result)
        return result


def clear_cache():
    with _lock:
        _cache.clear()
        _pending.clear()
