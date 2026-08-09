"""Guard against AuthKeyDuplicated / silent Telethon disconnect exits.

When supervisor SIGKILLs bacbo, Telegram still holds the auth key briefly.
The next connect gets kicked → ``run_until_disconnected()`` returns → process
exits with no Traceback (BACBO_DIED_AFTER_BOOT).

This module:
  · logs disconnect reasons
  · retries connect on AuthKeyDuplicatedError
  · tries to keep the client alive after a transient drop
"""
from __future__ import annotations

import asyncio
import functools
import os
from typing import Any

_PATCHED = False
_ARMED = False


def enabled() -> bool:
    return os.environ.get("LUX_SESSION_GUARD", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def patch_telethon() -> bool:
    global _PATCHED
    if _PATCHED:
        return True
    try:
        from telethon import TelegramClient  # type: ignore
        from telethon.errors import AuthKeyDuplicatedError  # type: ignore
    except Exception as exc:
        print("[SESSION-GUARD] telethon missing:", repr(exc))
        return False

    orig_connect = TelegramClient.connect
    if getattr(orig_connect, "_lux_session_guard", False):
        _PATCHED = True
        return True

    @functools.wraps(orig_connect)
    async def _connect(self: Any, *args: Any, **kwargs: Any):
        delays = (0, 8, 20, 35)
        last_exc: Exception | None = None
        for i, d in enumerate(delays):
            if d:
                print(f"[SESSION-GUARD] connect retry #{i} after {d}s")
                await asyncio.sleep(d)
            try:
                result = await orig_connect(self, *args, **kwargs)
                if i:
                    print(f"[SESSION-GUARD] connect OK on retry #{i}")
                return result
            except AuthKeyDuplicatedError as exc:
                last_exc = exc
                print(
                    "[SESSION-GUARD] AuthKeyDuplicatedError — "
                    "old session still held; waiting before retry"
                )
            except Exception as exc:
                # Only retry auth-key flavored failures
                msg = repr(exc).lower()
                if "authkey" in msg or "authorization key" in msg:
                    last_exc = exc
                    print("[SESSION-GUARD] auth-key failure:", repr(exc))
                    continue
                raise
        print("[SESSION-GUARD] connect giving up:", repr(last_exc))
        if last_exc:
            raise last_exc
        raise RuntimeError("SESSION-GUARD connect failed")

    _connect._lux_session_guard = True  # type: ignore[attr-defined]
    TelegramClient.connect = _connect  # type: ignore[method-assign]

    # Log disconnects so silent exits are visible
    try:
        orig_disc = TelegramClient.disconnect

        @functools.wraps(orig_disc)
        async def _disconnect(self: Any, *args: Any, **kwargs: Any):
            print("[SESSION-GUARD] client.disconnect() called")
            return await orig_disc(self, *args, **kwargs)

        if asyncio.iscoroutinefunction(orig_disc):
            _disconnect._lux_session_guard = True  # type: ignore[attr-defined]
            TelegramClient.disconnect = _disconnect  # type: ignore[method-assign]
    except Exception as exc:
        print("[SESSION-GUARD] disconnect wrap skip:", repr(exc))

    _PATCHED = True
    print("[SESSION-GUARD] AuthKey retry + disconnect log ON")
    return True


def apply() -> bool:
    global _ARMED
    if not enabled():
        if not _ARMED:
            print("[SESSION-GUARD] off")
            _ARMED = True
        return False
    ok = patch_telethon()
    if not ok:
        try:
            import threading

            threading.Timer(1.0, patch_telethon).start()
            threading.Timer(3.0, patch_telethon).start()
        except Exception:
            pass
    if not _ARMED:
        _ARMED = True
    return True


if enabled():
    apply()
