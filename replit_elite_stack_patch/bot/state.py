"""Shared bot state module (imported as `import state`).

bacbo_royal_complete.py binds TelegramClient onto `state.client`.
commands.py may decorate handlers with `@state.client.on` at import time,
so we install a proxy until the real client is assigned.
"""
from __future__ import annotations

import asyncio

# Set by bacbo_royal_complete after session load
client = None
me = None
running = True
engine = None
learner = None
# Some megafile / signal_handler code paths read these without a hasattr
# guard. `_lock` is used as `async with state._lock` — it MUST be a real
# asyncio.Lock, never None.
_quarantine_tasks: dict = {}
_lock = asyncio.Lock()
_outcome_sequence: list = []
_pending: dict = {}
_results: dict = {}
_rooms: dict = {}

# --- LUXURY_CLIENT_PROXY (auto) ---
class _LuxClientProxy:
    """Placeholder so @state.client.on works before TelegramClient is assigned."""

    def __init__(self):
        self._client = None
        self._pending = []  # (event, func)

    def bind(self, real_client):
        self._client = real_client
        pending = list(self._pending)
        self._pending.clear()
        for event, func in pending:
            try:
                real_client.add_event_handler(func, event)
            except Exception as e:
                print("[LUXURY] pending handler bind failed:", e)
        return real_client

    def on(self, event):
        def deco(func):
            if self._client is not None:
                self._client.add_event_handler(func, event)
            else:
                self._pending.append((event, func))
            return func

        return deco

    def __bool__(self):
        return self._client is not None

    def __getattr__(self, name):
        if name in ("_client", "_pending", "bind", "on"):
            raise AttributeError(name)
        if self._client is None:
            raise AttributeError(f"Telegram client not ready yet (getattr {name})")
        return getattr(self._client, name)


if client is None or not hasattr(client, "on"):
    client = _LuxClientProxy()
# --- end LUXURY_CLIENT_PROXY ---

# --- LUXURY_STATE_GETATTR (auto; never AttributeError on a new megafile name) ---
def __getattr__(name):
    """PEP 562 — invent a typed default the first time a missing name is read."""
    if name.startswith("__"):
        raise AttributeError(name)
    n = name.lower()
    if n.endswith("_lock") or n == "lock":
        val = asyncio.Lock()
    elif (
        n.endswith(
            ("_rooms", "_handles", "_tasks", "_map", "_cache", "_index", "_counts", "_scores", "_by_id", "_state", "_tracking", "_buffer")
        )
        or name in {"_pending", "_results", "_rooms", "_room_depth", "_room_recency", "_room_rti"}
    ):
        val = {}
    elif n.endswith(("_ids", "_seen", "_set")):
        val = set()
    elif n.endswith(("_sequence", "_history", "_queue", "_log", "_events", "_list")):
        val = []
    elif n.endswith(("_count", "_total", "_n", "_len")):
        val = 0
    elif n.endswith(("_flag", "_enabled", "_active", "_ready", "_scanning")):
        val = False
    elif n.endswith(("_txt", "_line", "_reason")):
        val = ""
    else:
        val = None
    globals()[name] = val
    return val
# --- end LUXURY_STATE_GETATTR ---
