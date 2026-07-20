"""
Global sqlite3.connect harden for Replit multi-process bacbo.

Raises short lock timeouts, sets busy_timeout, enables WAL on writers.
Import once at process start (bacbo / fallbacks / supervisor children).
"""
from __future__ import annotations

import sqlite3
from typing import Any


_ORIG = sqlite3.connect
_APPLIED = False


def _is_readonly(database: Any, uri: bool) -> bool:
    s = str(database or "")
    if uri or s.startswith("file:"):
        return "mode=ro" in s
    return False


def connect(*args: Any, **kwargs: Any) -> sqlite3.Connection:
    timeout = kwargs.get("timeout", 60.0)
    try:
        t = float(timeout if timeout is not None else 60.0)
    except Exception:
        t = 60.0
    if t < 30.0:
        kwargs["timeout"] = 60.0
    else:
        kwargs.setdefault("timeout", 60.0)

    conn = _ORIG(*args, **kwargs)
    database = args[0] if args else kwargs.get("database")
    uri = bool(kwargs.get("uri"))
    try:
        conn.execute("PRAGMA busy_timeout=60000")
        if not _is_readonly(database, uri):
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA temp_store=MEMORY")
    except Exception:
        pass
    return conn


def apply() -> None:
    global _APPLIED
    if _APPLIED:
        return
    sqlite3.connect = connect  # type: ignore[assignment]
    _APPLIED = True


apply()
