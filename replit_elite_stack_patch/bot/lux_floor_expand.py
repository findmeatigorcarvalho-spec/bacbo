"""
Expand floor_tracker allowlists with luxury live floors (logical names).

Keeps get_floor() logical — does NOT remap to peak gate stems.
Import once from bacbo / peak-lock path.
"""
from __future__ import annotations

import sys
from typing import Any


def _live() -> list[str]:
    try:
        from gate_alias_resolve import live_floors as _lf  # type: ignore

        return [str(x).upper() for x in (_lf() or [])]
    except Exception:
        try:
            import json
            from pathlib import Path

            p = Path(__file__).resolve().parent / "data" / "luxury_live_floors.json"
            d = json.loads(p.read_text(encoding="utf-8"))
            return [
                str(x).upper()
                for x in (d.get("live_floors") or d.get("live_building_floors") or [])
            ]
        except Exception:
            return []


def expand_module(mod: Any, lux: set[str]) -> int:
    n = 0
    if mod is None or not lux:
        return 0
    g = getattr(mod, "__dict__", {})
    for name in ("ENABLED_FLOORS", "LIVE_FLOORS", "ACTIVE_FLOORS", "FLOOR_ALLOWLIST", "FLOORS"):
        if name not in g:
            continue
        cur = g[name]
        if isinstance(cur, set):
            before = len(cur)
            cur |= lux
            n += max(0, len(cur) - before)
        elif isinstance(cur, list):
            merged = list(dict.fromkeys([str(x).upper() for x in cur] + list(lux)))
            if merged != [str(x).upper() for x in cur]:
                setattr(mod, name, merged)
                n += len(lux)
        elif isinstance(cur, tuple):
            merged = tuple(dict.fromkeys([str(x).upper() for x in cur] + list(lux)))
            if merged != tuple(str(x).upper() for x in cur):
                setattr(mod, name, merged)
                n += len(lux)
    # Optional: widen get_enabled_floors helper
    fn = g.get("get_enabled_floors")
    if callable(fn) and not getattr(fn, "_lux_floor_expanded", False):

        def _wrapped(*a, **k):
            try:
                base = list(fn(*a, **k) or [])
            except Exception:
                base = []
            return list(dict.fromkeys([str(x).upper() for x in base] + list(lux)))

        _wrapped._lux_floor_expanded = True  # type: ignore[attr-defined]
        setattr(mod, "get_enabled_floors", _wrapped)
        n += 1
    return n


def apply() -> None:
    lux = set(_live())
    if not lux:
        print("[LUXURY] floor-expand: no live floors found")
        return
    total = 0
    for name in ("floor_tracker", "bot.floor_tracker"):
        mod = sys.modules.get(name)
        if mod is not None:
            total += expand_module(mod, lux)
    # Also try import
    try:
        import floor_tracker as ft  # type: ignore

        total += expand_module(ft, lux)
    except Exception:
        pass
    print(f"[LUXURY] floor-expand: lux={len(lux)} patches={total}")


apply()
