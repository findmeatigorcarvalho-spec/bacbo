"""
Global sqlite3.connect harden for Replit multi-process bacbo.

- Raises short lock timeouts to >=60s
- Sets busy_timeout / WAL on writers
- Retries connect + execute/commit on 'database is locked'
Import once at process start (bacbo / fallbacks / supervisor children).
"""
from __future__ import annotations

import sqlite3
import time
from typing import Any, Callable


_ORIG = sqlite3.connect
_APPLIED = False
_MAX_RETRIES = 12


def _is_lock_err(exc: BaseException) -> bool:
    s = str(exc).lower()
    return "database is locked" in s or "database is busy" in s


def _is_readonly(database: Any, uri: bool) -> bool:
    s = str(database or "")
    if uri or s.startswith("file:"):
        return "mode=ro" in s
    return False


def _retry(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    last: BaseException | None = None
    for i in range(_MAX_RETRIES):
        try:
            return fn(*args, **kwargs)
        except sqlite3.OperationalError as exc:
            last = exc
            if not _is_lock_err(exc):
                raise
            time.sleep(min(0.05 * (2 ** min(i, 6)), 2.0))
    assert last is not None
    raise last


class _RetryConnection:
    """Thin proxy: retry execute/executemany/commit on lock errors."""

    def __init__(self, conn: sqlite3.Connection):
        object.__setattr__(self, "_conn", conn)

    def execute(self, *a: Any, **k: Any) -> Any:
        return _retry(self._conn.execute, *a, **k)

    def executemany(self, *a: Any, **k: Any) -> Any:
        return _retry(self._conn.executemany, *a, **k)

    def executescript(self, *a: Any, **k: Any) -> Any:
        return _retry(self._conn.executescript, *a, **k)

    def commit(self) -> None:
        return _retry(self._conn.commit)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._conn, name)

    def __setattr__(self, name: str, value: Any) -> None:
        if name == "_conn":
            object.__setattr__(self, name, value)
        else:
            setattr(self._conn, name, value)

    def __enter__(self) -> "_RetryConnection":
        self._conn.__enter__()
        return self

    def __exit__(self, *exc: Any) -> Any:
        return self._conn.__exit__(*exc)


def connect(*args: Any, **kwargs: Any) -> Any:
    timeout = kwargs.get("timeout", 60.0)
    try:
        t = float(timeout if timeout is not None else 60.0)
    except Exception:
        t = 60.0
    if t < 60.0:
        kwargs["timeout"] = 60.0
    else:
        kwargs.setdefault("timeout", 60.0)

    conn = _retry(_ORIG, *args, **kwargs)
    database = args[0] if args else kwargs.get("database")
    uri = bool(kwargs.get("uri"))
    try:
        conn.execute("PRAGMA busy_timeout=60000")
        if not _is_readonly(database, uri):
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA temp_store=MEMORY")
            conn.execute("PRAGMA wal_autocheckpoint=1000")
    except Exception:
        pass
    return _RetryConnection(conn)


def apply() -> None:
    global _APPLIED
    if _APPLIED:
        return
    sqlite3.connect = connect  # type: ignore[assignment]
    _APPLIED = True


apply()
