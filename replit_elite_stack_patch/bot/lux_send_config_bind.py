"""
Runtime bind: ensure `config` exists in __main__ / bacbo globals and wrap send().

Fixes: send() failed: name 'config' is not defined
even when `import config` appears at module top (nested scope / local assignment).
"""
from __future__ import annotations

import functools
import sys
import types
from typing import Any, Callable, Optional


def _ensure_config(ns: dict) -> Any:
    cfg = ns.get("config")
    if cfg is not None and hasattr(cfg, "TARGET"):
        return cfg
    try:
        import config as cfg  # type: ignore
    except Exception as exc:
        print("[LUXURY] send-config-bind: import config failed:", exc)
        raise
    ns["config"] = cfg
    return cfg


def _wrap_send(fn: Callable) -> Callable:
    if getattr(fn, "_lux_send_config_wrapped", False):
        return fn

    @functools.wraps(fn)
    async def _wrapped(*args, **kwargs):
        # Bind into the defining module AND the function globals
        g = getattr(fn, "__globals__", None)
        if isinstance(g, dict):
            _ensure_config(g)
        mod = sys.modules.get(getattr(fn, "__module__", "") or "")
        if isinstance(mod, types.ModuleType):
            _ensure_config(mod.__dict__)
        main = sys.modules.get("__main__")
        if isinstance(main, types.ModuleType):
            _ensure_config(main.__dict__)
        return await fn(*args, **kwargs)

    _wrapped._lux_send_config_wrapped = True  # type: ignore[attr-defined]
    return _wrapped


def patch_module(mod: Any) -> int:
    if mod is None:
        return 0
    n = 0
    try:
        _ensure_config(mod.__dict__)
        n += 1
    except Exception:
        pass
    send = getattr(mod, "send", None)
    if callable(send) and not getattr(send, "_lux_send_config_wrapped", False):
        try:
            setattr(mod, "send", _wrap_send(send))
            n += 1
        except Exception as exc:
            print("[LUXURY] send wrap failed:", exc)
    return n


def apply(silent: bool = False) -> int:
    patched = 0
    for name in ("__main__", "bacbo_royal_complete", "bacbo"):
        mod = sys.modules.get(name)
        if mod is not None:
            patched += patch_module(mod)
    for name, mod in list(sys.modules.items()):
        if mod is None or not hasattr(mod, "send"):
            continue
        if name.startswith("_gates_") or "bacbo" in name.lower() or name == "__main__":
            patched += patch_module(mod)
    if not silent:
        print(f"[LUXURY] send-config-bind applied patches={patched}")
    return patched


def _schedule_retries() -> None:
    """send() is often defined later in the mega-module — re-bind a few times."""
    try:
        import threading

        delays = (0.2, 1.0, 3.0, 8.0, 20.0)
        for d in delays:
            threading.Timer(d, lambda: apply(silent=True)).start()
    except Exception:
        pass


apply()
_schedule_retries()
