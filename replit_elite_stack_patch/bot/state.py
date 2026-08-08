"""Shared bot state module (imported as `import state`).

bacbo_royal_complete.py binds TelegramClient onto `state.client`.
commands.py may decorate handlers with `@state.client.on` at import time,
so we install a proxy until the real client is assigned.
"""
from __future__ import annotations

# Set by bacbo_royal_complete after session load
client = None
me = None
running = True
engine = None
learner = None

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
