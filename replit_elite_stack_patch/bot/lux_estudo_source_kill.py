"""
Source-side ESTUDO kill — neutralize study/ESTUDO emitters before they fire.

Why: TL/send wrappers catch most paths, but some modules build study posts via
helpers that still enqueue. This patches common emitter names + send-ish
functions that hardcode ESTUDO/ESTUDO MODE strings.

Never patches lux_* / hub_* guard modules (those DROP ESTUDO).
"""
from __future__ import annotations

import logging
import os
import sys
import threading
from typing import Any, Callable, Optional

log = logging.getLogger("lux.estudo_src")

_ARMED = False
_LOCK = threading.Lock()
_NOOPED: set[str] = set()

_PROTECTED_MOD_PARTS = (
    "lux_chat_watchdog",
    "lux_estudo_source_kill",
    "lux_estudo_kill",
    "lux_stayup",
    "lux_babysitter",
    "engine_gate_registry",
    "hub_max_boot",
    "hub_engine_route",
    "hub_outbox_bridge",
    "keep_allowlist",
)

_EMIT_NAME_PARTS = (
    "send_estudo",
    "emit_estudo",
    "post_estudo",
    "publish_estudo",
    "estudo_emit",
    "estudo_send",
    "estudo_post",
    "estudo_signal",
    "estudo_alert",
    "estudo_card",
    "estudo_mode",
    "study_emit",
    "study_send",
    "study_post",
    "study_signal",
    "study_alert",
    "study_card",
    "emit_study",
    "send_study",
    "post_study",
    "publish_study",
)

_SENDISH = ("send", "emit", "post", "publish", "dispatch", "broadcast", "push", "enqueue")
_GUARDISH = (
    "block",
    "drop",
    "filter",
    "guard",
    "deny",
    "reject",
    "scrub",
    "strip",
    "has_",
    "is_",
    "detect",
    "check",
    "kill",
    "noop",
    "estudo_blocked",
    "should_block",
)


def _protected_mod(mod_name: str) -> bool:
    ml = (mod_name or "").lower()
    return any(p in ml for p in _PROTECTED_MOD_PARTS)


def _wrap_fn(fn: Callable[..., Any], tag: str) -> Callable[..., Any]:
    import inspect

    if inspect.iscoroutinefunction(fn):

        async def _a(*_a: Any, **_k: Any) -> None:
            log.info("ESTUDO-SRC noop %s", tag)
            return None

        _a._lux_estudo_source_killed = True  # type: ignore[attr-defined]
        return _a

    def _s(*_a: Any, **_k: Any) -> None:
        log.info("ESTUDO-SRC noop %s", tag)
        return None

    _s._lux_estudo_source_killed = True  # type: ignore[attr-defined]
    return _s


def _should_noop_name(name: str) -> bool:
    n = (name or "").lower()
    if any(p in n for p in _GUARDISH):
        return False
    if any(p in n for p in _EMIT_NAME_PARTS):
        return True
    if "estudo" in n and any(s in n for s in _SENDISH):
        return True
    if "study" in n and any(s in n for s in _SENDISH):
        return True
    return False


def _should_noop_const_sender(fn: Any, name: str) -> bool:
    """Only send-ish fns that hardcode ESTUDO in string constants — never guards."""
    n = (name or "").lower()
    if any(p in n for p in _GUARDISH):
        return False
    if not any(s in n for s in _SENDISH):
        return False
    try:
        code = getattr(fn, "__code__", None)
        if code is None:
            return False
        for c in (code.co_consts or ()):
            if isinstance(c, str):
                u = c.upper()
                if "ESTUDO MODE" in u or "\nESTUDO" in u or u.strip() == "ESTUDO":
                    return True
                if "MODO ESTUDO" in u or "STUDY MODE" in u:
                    return True
    except Exception:
        return False
    return False


def neutralize_module(mod: Any, label: str = "") -> int:
    """No-op ESTUDO emitters on one module. Returns count patched."""
    if mod is None:
        return 0
    mod_name = label or getattr(mod, "__name__", type(mod).__name__)
    if _protected_mod(str(mod_name)):
        return 0
    n = 0
    try:
        names = dir(mod)
    except Exception:
        return 0
    for name in names:
        try:
            fn = getattr(mod, name, None)
        except Exception:
            continue
        if not callable(fn):
            continue
        if getattr(fn, "_lux_estudo_source_killed", False):
            continue
        key = f"{mod_name}:{name}"
        if key in _NOOPED:
            continue
        try:
            hit = _should_noop_name(name) or _should_noop_const_sender(fn, name)
        except Exception:
            hit = False
        if not hit:
            continue
        try:
            setattr(mod, name, _wrap_fn(fn, key))
            _NOOPED.add(key)
            n += 1
            log.warning("ESTUDO-SRC patched %s", key)
        except Exception:
            continue
    return n


def sweep_modules() -> int:
    total = 0
    for mod_name, mod in list(sys.modules.items()):
        if mod is None or _protected_mod(mod_name):
            continue
        try:
            total += neutralize_module(mod, label=mod_name)
        except Exception:
            continue
    return total


def arm_forever(interval_s: float = 8.0) -> None:
    global _ARMED
    with _LOCK:
        if _ARMED:
            return
        _ARMED = True

    def _loop() -> None:
        while True:
            try:
                sweep_modules()
            except Exception:
                pass
            import time

            time.sleep(max(3.0, float(interval_s)))

    threading.Thread(target=_loop, name="lux-estudo-src", daemon=True).start()
    log.warning("ESTUDO-SRC forever armed")
    print("[ESTUDO-SRC] forever armed", flush=True)


def apply() -> dict[str, Any]:
    """Boot source kill (env-gated). Returns status dict."""
    if os.getenv("LUX_ESTUDO_SOURCE_KILL", "1").strip().lower() in {
        "0",
        "false",
        "no",
        "off",
    }:
        return {"ok": False, "why": "disabled", "patched": 0}
    n = sweep_modules()
    arm_forever(float(os.getenv("LUX_ESTUDO_SRC_SWEEP_S", "8") or 8))
    print(f"[ESTUDO-SRC] boot patched={n}", flush=True)
    return {"ok": True, "patched": n, "armed": True}


def boot() -> Optional[dict[str, Any]]:
    return apply()


__all__ = ["apply", "boot", "sweep_modules", "arm_forever", "neutralize_module"]

# Auto-arm on import (same pattern as lux_estudo_kill) when env allows.
try:
    if os.getenv("LUX_ESTUDO_SOURCE_KILL", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }:
        apply()
except Exception as _exc:
    print("[ESTUDO-SRC] import apply skip:", repr(_exc), flush=True)
