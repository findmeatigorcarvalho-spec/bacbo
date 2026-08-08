"""Minimal early ESTUDO + duplicate kill for Telethon send_message.

Import this BEFORE bacbo main runs (see run_bacbo_live.py).
"""
from __future__ import annotations

import functools
import hashlib
import os
import re
import time
from typing import Any, Optional

_RECENT: dict[str, float] = {}
_PATCHED = False
_ESTUDO_RE = re.compile(
    r"(?:G[0-9]+\s*ESTUDO|\bESTUDO\b\s*[|:]|🔷\s*G[0-9]+\s*ESTUDO)",
    re.IGNORECASE,
)
_SCORE_TAIL_RE = re.compile(r"\b\d+\.\d{1,3}\b\s*$")


def estudo_blocked(msg: Optional[str]) -> bool:
    if not msg:
        return False
    if os.environ.get("LUX_BLOCK_ESTUDO", "1").strip().lower() in {
        "0",
        "false",
        "no",
        "off",
    }:
        return False
    u = msg.upper()
    if any(
        n in u
        for n in (
            "G2 ESTUDO",
            "G1 ESTUDO",
            "G3 ESTUDO",
            "G0 ESTUDO",
            "ESTUDO |",
            "ESTUDO :",
        )
    ):
        return True
    first = msg.splitlines()[0] if msg else ""
    return bool(_ESTUDO_RE.search(first) or _ESTUDO_RE.search(msg[:160]))


def _norm(msg: str) -> str:
    lines = [_SCORE_TAIL_RE.sub("", ln).rstrip() for ln in msg.strip().splitlines()]
    return "\n".join(lines).casefold()


def dedup_hit(msg: Optional[str]) -> bool:
    if not msg or not msg.strip():
        return False
    try:
        secs = float(os.environ.get("LUX_SEND_DEDUP_SECS", "90") or "90")
    except Exception:
        secs = 90.0
    if secs <= 0:
        return False
    key = hashlib.sha1(_norm(msg).encode("utf-8", "ignore")).hexdigest()
    now = time.monotonic()
    if len(_RECENT) > 400:
        cutoff = now - max(secs, 60.0)
        for k, t in list(_RECENT.items()):
            if t < cutoff:
                _RECENT.pop(k, None)
    prev = _RECENT.get(key)
    if prev is not None and (now - prev) < secs:
        return True
    _RECENT[key] = now
    return False


def _msg_from(args: tuple, kwargs: dict) -> Optional[str]:
    if len(args) >= 2 and isinstance(args[1], str):
        return args[1]
    for key in ("message", "msg", "text", "body"):
        v = kwargs.get(key)
        if isinstance(v, str):
            return v
    return None


def patch_telethon(*, force: bool = False) -> bool:
    global _PATCHED
    if _PATCHED and not force:
        return True
    try:
        from telethon.client.messages import MessageMethods  # type: ignore
    except Exception as exc:
        print("[ESTUDO-KILL] telethon not ready:", repr(exc))
        return False
    orig = getattr(MessageMethods, "send_message", None)
    if not callable(orig):
        return False
    if getattr(orig, "_lux_estudo_kill_wrapped", False) and not force:
        _PATCHED = True
        return True

    @functools.wraps(orig)
    async def _wrapped(self: Any, *args: Any, **kwargs: Any):
        msg = _msg_from(args, kwargs)
        if estudo_blocked(msg):
            print("[ESTUDO-KILL] drop ESTUDO send_message")
            return None
        if dedup_hit(msg):
            print("[ESTUDO-KILL] drop duplicate send_message")
            return None
        return await orig(self, *args, **kwargs)

    _wrapped._lux_estudo_kill_wrapped = True  # type: ignore[attr-defined]
    MessageMethods.send_message = _wrapped  # type: ignore[method-assign]
    _PATCHED = True
    print("[ESTUDO-KILL] telethon send_message gate ON")
    return True


def apply() -> bool:
    """Import telethon if needed, then patch."""
    try:
        import telethon.client.messages  # noqa: F401
    except Exception as exc:
        print("[ESTUDO-KILL] cannot import telethon:", repr(exc))
        return False
    return patch_telethon(force=True)


apply()
