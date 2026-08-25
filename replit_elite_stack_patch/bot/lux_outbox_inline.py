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
_CLIENT_ID: int | None = None


def enabled() -> bool:
    return os.environ.get("TELEGRAM_OUTBOX_INLINE", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def _settle_secs() -> float:
    try:
        return float(os.environ.get("OUTBOX_INLINE_SETTLE_SECS", "70") or "70")
    except Exception:
        return 70.0


def _reset_for_retry(reason: str) -> None:
    """Allow a later connect/reconnect to re-arm the outbox boot task."""
    global _STARTED, _SCHEDULED
    _STARTED = False
    _SCHEDULED = False
    print(f"[OUTBOX-INLINE] reset for retry ({reason})", flush=True)


async def _boot_outbox(client: Any) -> None:
    global _STARTED
    if _STARTED:
        return
    _STARTED = True
    # Arm ESTUDO-only __call__ IMMEDIATELY on connect — do not wait 70s settle.
    # (Full gate with dedup on __call__ was unsafe; ESTUDO/trash-only is fine.)
    try:
        import lux_chat_watchdog as _cw

        if _cw.arm_call_wrap_immediate(reason="outbox_connect"):
            print("[OUTBOX-INLINE] CHAT-WATCH __call__ armed IMMEDIATE", flush=True)
    except Exception as exc:
        print("[OUTBOX-INLINE] CHAT-WATCH immediate arm skip:", repr(exc), flush=True)
    settle = _settle_secs()
    print(
        f"[OUTBOX-INLINE] boot task alive — waiting {settle:.0f}s "
        f"for subscribe settle",
        flush=True,
    )
    # Heartbeat so logs prove we are still alive during settle
    left = settle
    while left > 0:
        step = min(10.0, left)
        await asyncio.sleep(step)
        left -= step
        try:
            ok = bool(client.is_connected())
        except Exception:
            ok = False
        print(
            f"[OUTBOX-INLINE] settle heartbeat left={left:.0f}s connected={int(ok)}",
            flush=True,
        )
        if not ok:
            print(
                "[OUTBOX-INLINE] client disconnected during settle — abort",
                flush=True,
            )
            _reset_for_retry("disconnect-during-settle")
            return
    try:
        if not client.is_connected():
            print(
                "[OUTBOX-INLINE] client disconnected during settle — abort",
                flush=True,
            )
            _reset_for_retry("disconnect-after-settle")
            return
    except Exception as exc:
        print("[OUTBOX-INLINE] connected check:", repr(exc), flush=True)
        _reset_for_retry("connected-check-fail")
        return
    # Never spam UNIQUE_g1 with OUTBOX ONLINE during live boot
    os.environ.setdefault("TELEGRAM_OUTBOX_STARTUP_PING", "0")
    # Post-settle: install __call__ ESTUDO gate (unsafe during subscribe).
    try:
        import lux_chat_watchdog as _cw

        os.environ["LUX_CHAT_WATCH_CALL"] = "1"
        if _cw.install_call_wrap(force_env=True):
            print("[OUTBOX-INLINE] CHAT-WATCH __call__ gate armed", flush=True)
        _cw.patch(force=True)
    except Exception as exc:
        print("[OUTBOX-INLINE] CHAT-WATCH CALL arm skip:", repr(exc), flush=True)
    try:
        import telegram_outbox as ob

        print("[OUTBOX-INLINE] starting on bacbo client (shared session)", flush=True)
        await ob.run_inline(client)
    except asyncio.CancelledError:
        print("[OUTBOX-INLINE] cancelled", flush=True)
        _reset_for_retry("cancelled")
        raise
    except Exception as exc:
        print("[OUTBOX-INLINE] stopped:", repr(exc), flush=True)
        _reset_for_retry("stopped")


def _spawn(client: Any) -> None:
    global _SCHEDULED, _CLIENT_ID
    if _STARTED or _SCHEDULED:
        return
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    try:
        _SCHEDULED = True
        _CLIENT_ID = id(client)
        try:
            import lux_chat_watchdog as _cw

            _cw.harden_client_instance(client)
        except Exception as exc:
            print("[OUTBOX-INLINE] instance ESTUDO harden skip:", repr(exc), flush=True)
        try:
            loop.create_task(_boot_outbox(client), name="lux_outbox_inline")
        except TypeError:
            loop.create_task(_boot_outbox(client))
        print("[OUTBOX-INLINE] scheduled create_task on running loop", flush=True)
    except Exception as exc:
        _SCHEDULED = False
        print("[OUTBOX-INLINE] create_task fail:", repr(exc), flush=True)


def _wrap_async(orig):
    if getattr(orig, "_lux_outbox_inline_wrapped", False):
        return orig

    @functools.wraps(orig)
    async def _wrapped(self, *args, **kwargs):
        result = await orig(self, *args, **kwargs)
        try:
            _spawn(self)
        except Exception as exc:
            print("[OUTBOX-INLINE] spawn after connect skip:", repr(exc), flush=True)
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
        print("[OUTBOX-INLINE] telethon missing:", repr(exc), flush=True)
        return False
    try:
        if hasattr(TelegramClient, "connect"):
            TelegramClient.connect = _wrap_async(TelegramClient.connect)  # type: ignore
        st = getattr(TelegramClient, "start", None)
        if st is not None and asyncio.iscoroutinefunction(st):
            TelegramClient.start = _wrap_async(st)  # type: ignore
        _PATCHED = True
        print("[OUTBOX-INLINE] patched TelegramClient.connect", flush=True)
        return True
    except Exception as exc:
        print("[OUTBOX-INLINE] patch fail:", repr(exc), flush=True)
        return False


def apply() -> bool:
    global _ARMED
    if not enabled():
        if not _ARMED:
            print("[OUTBOX-INLINE] off", flush=True)
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
        print(
            "[OUTBOX-INLINE] arm — will start after client.connect() on bacbo loop",
            flush=True,
        )
    return True


if enabled():
    apply()
