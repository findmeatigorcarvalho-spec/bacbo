"""
Runtime bind: ensure `config` exists in __main__ / bacbo globals and wrap send().

Fixes: send() failed: name 'config' is not defined
even when `import config` appears at module top (nested scope / local assignment).
"""
from __future__ import annotations

import functools
import os
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


def _extract_msg(args: tuple, kwargs: dict) -> str | None:
    if args:
        a0 = args[0]
        if isinstance(a0, str):
            return a0
    for key in ("msg", "text", "message", "body"):
        v = kwargs.get(key)
        if isinstance(v, str):
            return v
    return None


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

        msg = _extract_msg(args, kwargs)

        # Skin family gate — retire/disable Telegram skins via EngineGateRegistry
        try:
            from skin_gate import evaluate_send_gate, log_block

            decision = evaluate_send_gate(msg)
            if decision.blocked:
                log_block(decision, where="engine_send")
                return None
        except Exception as exc:
            print("[SKIN-GATE] skip:", repr(exc))

        # Round sync densifier — invest prep seconds, release at perfect TTB.
        # HOLD_* → queue for outbox releaser; never burn a late window.
        try:
            import time as _time

            from round_sync_densifier import (
                HeldFire,
                decide_fire,
                decide_result,
                enabled as _rs_on,
                get_clock,
                get_densifier,
            )

            if _rs_on() and isinstance(msg, str) and msg.strip():
                # RESULT: attach under parent FIRE immediately (force_now).
                rd = decide_result(msg, force_now=True)
                if rd.action == "HOLD_RESULT":
                    # Legacy only — should not fire when RESULT_ATTACH_IMMEDIATE=1
                    phase = get_clock().phase_at()
                    parent_chat = "UNIQUE_g1"
                    try:
                        from hub_engine_route import _load_last_target

                        last = _load_last_target()
                        if last is not None:
                            parent_chat = str(
                                getattr(last, "username", None)
                                or getattr(last, "id", None)
                                or parent_chat
                            )
                    except Exception:
                        pass
                    get_densifier()._enqueue(
                        HeldFire(
                            fire_key=f"result:{phase.round_id}:{hash(msg) & 0xFFFFFFFF:x}",
                            text=msg,
                            color="",
                            family_id="RESULT",
                            signal_kind="RESULT",
                            score=0.0,
                            chat=str(parent_chat),
                            clock_a_secs=None,
                            detected_at=_time.time(),
                            ideal_release_at=phase.next_interval_start,
                            round_id=phase.round_id + 1,
                            source="engine_result",
                            meta={"kind": "result_align"},
                        )
                    )
                    print(f"[ROUND-SYNC] HOLD_RESULT {rd.reason}")
                    return None
                fd = decide_fire(msg, source="engine")
                action = fd.action
                try:
                    from bot.config.fire_result_law import decide_fire_override

                    ov = decide_fire_override(action, msg)
                    if ov:
                        print(
                            f"[FIRE↔RESULT LAW] engine {action}→{ov} "
                            f"(result-paired must fire)"
                        )
                        action = ov
                except Exception:
                    pass
                if action in {"HOLD_PREP", "TOO_LATE", "DEDUP"}:
                    print(f"[ROUND-SYNC] {action} {fd.reason}")
                    return None
        except Exception as exc:
            print("[ROUND-SYNC] skip:", repr(exc))

        # Hub: route original engine skins to money penthouse / countdown / spill
        prev_target = None
        cfg = None
        route_reason = None
        try:
            from hub_engine_route import (
                apply_target_to_config,
                hub_route_enabled,
                pick_target_for_text,
            )

            if hub_route_enabled():
                dest, route_reason = pick_target_for_text(msg)
                if dest is not None:
                    if isinstance(g, dict) and g.get("config") is not None:
                        cfg = g.get("config")
                    elif isinstance(mod, types.ModuleType):
                        cfg = getattr(mod, "config", None)
                    if cfg is None and isinstance(main, types.ModuleType):
                        cfg = getattr(main, "config", None)
                    if cfg is None:
                        import config as cfg  # type: ignore
                    prev_target = apply_target_to_config(cfg, dest)
                    if os.environ.get("HUB_ENGINE_ROUTE_LOG", "1").strip() not in {
                        "0",
                        "false",
                        "no",
                        "off",
                    }:
                        print(f"[HUB-ROUTE] dest={dest} reason={route_reason}")
        except Exception as exc:
            print("[HUB-ROUTE] skip:", repr(exc))

        try:
            return await fn(*args, **kwargs)
        finally:
            if cfg is not None and prev_target is not None:
                try:
                    cfg.TARGET = prev_target
                except Exception:
                    pass

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
