"""Minimal early ESTUDO + duplicate kill — delegates to lux_chat_watchdog.

Import this BEFORE bacbo main runs (see run_bacbo_live.py).
The nuclear gate lives in lux_chat_watchdog (send_message + send_file + __call__).
"""
from __future__ import annotations

from typing import Optional


def estudo_blocked(msg: Optional[str]) -> bool:
    try:
        from lux_chat_watchdog import estudo_blocked as _eb

        return bool(_eb(msg))
    except Exception:
        if not msg:
            return False
        u = msg.upper()
        return "ESTUDO" in u and (
            "G2" in u or "G1" in u or "G0" in u or "G3" in u or "🔷" in msg
        )


def dedup_hit(msg: Optional[str]) -> bool:
    try:
        from lux_chat_watchdog import dedup_hit as _dh

        return bool(_dh(msg))
    except Exception:
        return False


def patch_telethon(*, force: bool = False) -> bool:
    try:
        from lux_chat_watchdog import patch

        return bool(patch(force=force))
    except Exception as exc:
        print("[ESTUDO-KILL] chat_watchdog unavailable:", repr(exc))
        return False


def apply() -> bool:
    try:
        import lux_chat_watchdog as _cw  # noqa: F401

        return bool(_cw.apply())
    except Exception as exc:
        print("[ESTUDO-KILL] cannot boot chat_watchdog:", repr(exc))
        return False


apply()
