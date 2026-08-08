"""Start telegram_outbox on bacbo's TelegramClient (one session).

Never touch ``client.loop`` from a Timer/thread — Telethon's ``.loop``
property calls ``get_running_loop()`` and raises in non-async threads
(that traceback storm was killing stability).

We patch ``TelegramClient.connect`` / ``start`` so the outbox task is
scheduled with ``asyncio.create_task`` *inside* bacbo's running loop.
"""
from __future__ import annotations

import asyncio
import functools
import os
from typing import Any

_STARTED = False
_PATCHED = False
_ARMED = False


def enabled() -> bool:
    return os.environ.get("TELEGRAM_OUTBOX_INLINE", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


async def _boot_outbox(client: Any) -> None:
    global _STARTED
    if _STARTED:
        return
    _STARTED = True
    # Let auth / dialogs / subscribe settle
    await asyncio.sleep(8.0)
    try:
        import telegram_outbox as ob

        print("[OUTBOX-INLINE] starting on bacbo client (shared session)")
        await ob.run_inline(client)
    except Exception as exc:
        print("[OUTBOX-INLINE] stopped:", repr(exc))
        # allow one retry path on next connect if this was early
        # (keep _STARTED True to avoid task storms)


def _spawn(client: Any) -> None:
    if _STARTED:
        return
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    try:
        loop.create_task(_boot_outbox(client))
        print("[OUTBOX-INLINE] scheduled create_task on running loop")
    except Exception as exc:
        print("[OUTBOX-INLINE] create_task fail:", repr(exc))


def _wrap_async(orig):
    if getattr(orig, "_lux_outbox_inline_wrapped", False):
        return orig

    @functools.wraps(orig)
    async def _wrapped(self, *args, **kwargs):
        result = await orig(self, *args, **kwargs)
        try:
            _spawn(self)
        except Exception as exc:
            print("[OUTBOX-INLINE] spawn after connect skip:", repr(exc))
        return result

    _wrapped._lux_outbox_inline_wrapped = True  # type: ignore[attr-defined]
    return _wrapped


def patch_telethon() -> bool:
    global _PATCHED
    if _PATCHED:
        return True
    try:
        from telethon import TelegramClient  # type: ignore
    except Exception as exc:
        print("[OUTBOX-INLINE] telethon missing:", repr(exc))
        return False
    try:
        if hasattr(TelegramClient, "connect"):
            TelegramClient.connect = _wrap_async(TelegramClient.connect)  # type: ignore
        if hasattr(TelegramClient, "start"):
            # start may be sync or async depending on version — only wrap if coroutine
            st = getattr(TelegramClient, "start")
            if asyncio.iscoroutinefunction(st):
                TelegramClient.start = _wrap_async(st)  # type: ignore
        _PATCHED = True
        print("[OUTBOX-INLINE] patched TelegramClient.connect")
        return True
    except Exception as exc:
        print("[OUTBOX-INLINE] patch fail:", repr(exc))
        return False


def apply() -> bool:
    global _ARMED
    if not enabled():
        if not _ARMED:
            print("[OUTBOX-INLINE] off")
            _ARMED = True
        return False
    ok = patch_telethon()
    if not _ARMED:
        _ARMED = True
        print("[OUTBOX-INLINE] arm — will start after client.connect() on bacbo loop")
    return ok


if enabled():
    apply()
