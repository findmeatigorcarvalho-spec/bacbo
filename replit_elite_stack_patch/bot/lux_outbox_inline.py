"""Start telegram_outbox on bacbo's TelegramClient (one session).

Never touch ``client.loop`` from a Timer/thread.
Wait until subscribe has had time to finish before starting RESULT polling
(starting too early during room-subscribe correlates with disconnect exits).
"""
from __future__ import annotations

import asyncio
import functools
import os
from typing import Any

_STARTED = False
_SCHEDULED = False
_PATCHED = False
_ARMED = False


def enabled() -> bool:
    return os.environ.get("TELEGRAM_OUTBOX_INLINE", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def _settle_secs() -> float:
    try:
        return float(os.environ.get("OUTBOX_INLINE_SETTLE_SECS", "55") or "55")
    except Exception:
        return 55.0


async def _boot_outbox(client: Any) -> None:
    global _STARTED
    if _STARTED:
        return
    _STARTED = True
    settle = _settle_secs()
    print(
        f"[OUTBOX-INLINE] boot task alive — waiting {settle:.0f}s "
        f"for subscribe settle"
    )
    await asyncio.sleep(settle)
    try:
        if not client.is_connected():
            print("[OUTBOX-INLINE] client disconnected during settle — abort")
            return
    except Exception as exc:
        print("[OUTBOX-INLINE] connected check:", repr(exc))
        return
    # Never spam UNIQUE_g1 with OUTBOX ONLINE during live boot
    os.environ.setdefault("TELEGRAM_OUTBOX_STARTUP_PING", "0")
    try:
        import telegram_outbox as ob

        print("[OUTBOX-INLINE] starting on bacbo client (shared session)")
        await ob.run_inline(client)
    except Exception as exc:
        print("[OUTBOX-INLINE] stopped:", repr(exc))


def _spawn(client: Any) -> None:
    global _SCHEDULED
    if _STARTED or _SCHEDULED:
        return
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    try:
        _SCHEDULED = True
        try:
            loop.create_task(_boot_outbox(client), name="lux_outbox_inline")
        except TypeError:
            loop.create_task(_boot_outbox(client))
        print("[OUTBOX-INLINE] scheduled create_task on running loop")
    except Exception as exc:
        _SCHEDULED = False
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
        st = getattr(TelegramClient, "start", None)
        if st is not None and asyncio.iscoroutinefunction(st):
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
    if not ok:
        try:
            import threading

            threading.Timer(1.0, patch_telethon).start()
            threading.Timer(3.0, patch_telethon).start()
        except Exception:
            pass
    if not _ARMED:
        _ARMED = True
        print("[OUTBOX-INLINE] arm — will start after client.connect() on bacbo loop")
    return True


if enabled():
    apply()
