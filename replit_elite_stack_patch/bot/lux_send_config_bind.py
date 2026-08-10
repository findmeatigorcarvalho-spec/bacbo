"""
Runtime bind: ensure `config` exists in __main__ / bacbo globals and wrap send().

Fixes: send() failed: name 'config' is not defined
even when `import config` appears at module top (nested scope / local assignment).

Also:
  - trash G2 ESTUDO / study spam (engine send + Telethon send_message)
  - dedupe identical / near-identical bodies within a short window (stop 14× floods)
"""
from __future__ import annotations

import functools
import hashlib
import os
import re
import sys
import time
import types
from typing import Any, Callable, Optional

# body_hash → last_sent_monotonic
_RECENT_SENDS: dict[str, float] = {}
_DEDUP_SECS = float(os.environ.get("LUX_SEND_DEDUP_SECS", "90") or "90")
_ESTUDO_RE = re.compile(
    r"(?:G[0-9]+\s*ESTUDO|\bESTUDO\b\s*[|:]|🔷\s*G[0-9]+\s*ESTUDO)",
    re.IGNORECASE,
)
_SCORE_TAIL_RE = re.compile(r"\b\d+\.\d{1,3}\b\s*$")
_TG_SEND_PATCHED = False


def _estudo_blocked(msg: str | None) -> bool:
    """Hard-drop engine study spam (G2 ESTUDO floods on UNIQUE_g1)."""
    try:
        from lux_chat_watchdog import estudo_blocked as _eb

        return bool(_eb(msg))
    except Exception:
        pass
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
    if (
        "G2 ESTUDO" in u
        or "G1 ESTUDO" in u
        or "G3 ESTUDO" in u
        or "G0 ESTUDO" in u
        or "ESTUDO |" in u
        or "ESTUDO :" in u
        or ("ESTUDO" in u and ("🔴" in msg or "🔵" in msg or "NEUTRO" in u))
    ):
        return True
    # First line often: "🔷 G2 ESTUDO | @channel"
    first = msg.splitlines()[0] if msg else ""
    if _ESTUDO_RE.search(first) or _ESTUDO_RE.search(msg[:160]):
        return True
    if "ESTUDO" in first.upper():
        return True
    return False


def _norm_dedup_key(msg: str) -> str:
    """Normalize so score flicker (1.07 vs 0.81) still counts as one flood."""
    t = msg.strip()
    # Drop trailing decimal scores on each line
    lines = []
    for ln in t.splitlines():
        lines.append(_SCORE_TAIL_RE.sub("", ln).rstrip())
    return "\n".join(lines).casefold()


def _dedup_hit(msg: str | None) -> bool:
    if not msg or not msg.strip():
        return False
    try:
        secs = float(os.environ.get("LUX_SEND_DEDUP_SECS", str(_DEDUP_SECS)) or "90")
    except Exception:
        secs = 90.0
    if secs <= 0:
        return False
    key = hashlib.sha1(_norm_dedup_key(msg).encode("utf-8", "ignore")).hexdigest()
    now = time.monotonic()
    # prune
    if len(_RECENT_SENDS) > 400:
        cutoff = now - max(secs, 60.0)
        for k, t in list(_RECENT_SENDS.items()):
            if t < cutoff:
                _RECENT_SENDS.pop(k, None)
    prev = _RECENT_SENDS.get(key)
    if prev is not None and (now - prev) < secs:
        return True
    _RECENT_SENDS[key] = now
    return False


def _tg_message_text(args: tuple, kwargs: dict) -> str | None:
    # Telethon: send_message(entity, message, ...)
    if len(args) >= 2 and isinstance(args[1], str):
        return args[1]
    for key in ("message", "msg", "text", "body"):
        v = kwargs.get(key)
        if isinstance(v, str):
            return v
    return None


def _send_already_gated(fn: Any) -> bool:
    """True if fn or its __wrapped__ chain already has our ESTUDO gate."""
    cur: Any = fn
    seen: set[int] = set()
    while cur is not None and id(cur) not in seen:
        seen.add(id(cur))
        if getattr(cur, "_lux_estudo_wrapped", False):
            return True
        if getattr(cur, "_lux_chat_watchdog", False):
            return True
        cur = getattr(cur, "__wrapped__", None)
    return False


def _patch_telethon_send_message(*, force: bool = False) -> bool:
    """Nuclear ESTUDO/dedup gate — catches paths that bypass engine send()."""
    global _TG_SEND_PATCHED
    if _TG_SEND_PATCHED and not force:
        return True
    try:
        from telethon.client.messages import MessageMethods  # type: ignore
    except Exception as exc:
        print("[LUXURY] telethon send_message patch skip:", repr(exc))
        return False
    orig = getattr(MessageMethods, "send_message", None)
    if not callable(orig):
        return False
    # Never nest wraps — forever-repatch + chat_watchdog would stack forever.
    if _send_already_gated(orig):
        _TG_SEND_PATCHED = True
        return True

    @functools.wraps(orig)
    async def _wrapped(self, *args, **kwargs):
        msg = _tg_message_text(args, kwargs)
        if _estudo_blocked(msg):
            print("[LUXURY] drop ESTUDO via telethon send_message")
            return None
        if _dedup_hit(msg):
            print("[LUXURY] drop duplicate via telethon send_message")
            return None
        return await orig(self, *args, **kwargs)

    _wrapped._lux_estudo_wrapped = True  # type: ignore[attr-defined]
    MessageMethods.send_message = _wrapped  # type: ignore[method-assign]
    _TG_SEND_PATCHED = True
    print("[LUXURY] telethon send_message ESTUDO/dedup gate ON")
    return True


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

        # Nuclear chat watchdog + ESTUDO / trash / dedup (before any routing)
        try:
            from lux_chat_watchdog import gate_outbound

            # pre-check only — Telethon edge commits dedup / sent ledger
            ok, why = gate_outbound(
                msg=msg, entity=None, path="engine_send", final=False
            )
            if not ok:
                print(f"[LUXURY] drop via chat_watchdog: {why}")
                return None
        except Exception:
            if _estudo_blocked(msg):
                print("[LUXURY] drop ESTUDO study spam")
                return None
            if _dedup_hit(msg):
                print("[LUXURY] drop duplicate send (dedup window)")
                return None
            try:
                from config.keep_allowlist import should_block_as_trash

                hit, why = should_block_as_trash(text=msg or "")
                if hit:
                    print(f"[LUXURY] drop trash: {why}")
                    return None
            except Exception:
                pass

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
    # Minimal ESTUDO kill first (import hook + telethon patch)
    try:
        import lux_estudo_kill as _ek

        if _ek.patch_telethon():
            pass
    except Exception:
        pass
    # Repair *_RE string bindings before/while send wraps (CrashGuard fix).
    try:
        from lux_re_harden import apply as _re_harden

        _re_harden(silent=True)
    except Exception:
        try:
            from bot.lux_re_harden import apply as _re_harden  # type: ignore

            _re_harden(silent=True)
        except Exception:
            pass
    patched = 0
    if _patch_telethon_send_message():
        patched += 1
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

        delays = (0.2, 1.0, 3.0, 8.0, 20.0, 45.0)
        for d in delays:
            threading.Timer(d, lambda: apply(silent=True)).start()
    except Exception:
        pass


apply()
_schedule_retries()
