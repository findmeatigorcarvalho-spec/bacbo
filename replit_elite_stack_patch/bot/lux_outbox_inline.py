"""Start telegram_outbox on bacbo's TelegramClient (one session).

Prevents AuthKeyDuplicatedError from a second outbox process stealing the
StringSession and killing bot_live.
"""
from __future__ import annotations

import asyncio
import os
import threading
from typing import Any

_STARTED = False
_LOCK = threading.Lock()


def enabled() -> bool:
    return os.environ.get("TELEGRAM_OUTBOX_INLINE", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def _get_client() -> Any:
    try:
        import state as st  # type: ignore

        c = getattr(st, "client", None)
        if c is not None:
            return c
    except Exception:
        pass
    try:
        import sys

        main = sys.modules.get("__main__")
        if main is not None:
            c = getattr(main, "client", None)
            if c is not None:
                return c
            st = getattr(main, "state", None)
            if st is not None:
                c = getattr(st, "client", None)
                if c is not None:
                    return c
    except Exception:
        pass
    return None


def _schedule_on_client(client: Any) -> bool:
    global _STARTED
    loop = getattr(client, "loop", None)
    if loop is None or not getattr(loop, "is_running", lambda: False)():
        return False

    with _LOCK:
        if _STARTED:
            return True
        _STARTED = True

    async def _runner() -> None:
        for _ in range(40):
            try:
                if client.is_connected():
                    break
            except Exception:
                pass
            await asyncio.sleep(0.5)
        # Let dialogs / subscribe settle before RESULT polling
        await asyncio.sleep(5.0)
        try:
            import telegram_outbox as ob

            print("[OUTBOX-INLINE] starting on bacbo client (shared session)")
            await ob.run_inline(client)
        except Exception as exc:
            print("[OUTBOX-INLINE] stopped:", repr(exc))

    try:
        asyncio.run_coroutine_threadsafe(_runner(), loop)
        print("[OUTBOX-INLINE] scheduled on bacbo client.loop")
        return True
    except Exception as exc:
        print("[OUTBOX-INLINE] schedule fail:", repr(exc))
        with _LOCK:
            _STARTED = False
        return False


def apply() -> bool:
    if not enabled():
        print("[OUTBOX-INLINE] off")
        return False

    def _try() -> None:
        if _STARTED:
            return
        client = _get_client()
        if client is None:
            return
        _schedule_on_client(client)

    for d in (3.0, 6.0, 12.0, 20.0, 35.0, 55.0, 90.0, 120.0):
        threading.Timer(d, _try).start()
    print("[OUTBOX-INLINE] arm — attach to bacbo client when loop is running")
    return True


if enabled():
    apply()
