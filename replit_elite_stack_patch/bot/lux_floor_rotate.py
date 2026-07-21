"""
Rotate logical source floors + restore missing floor_tracker API.

Replit often has a stripped floor_tracker (no get_floor_badge) and database.py
does `from floor_tracker import get_floor` (bound name). Wrapping only
floor_tracker.get_floor is not enough — we rebind get_floor in every loaded
module and keep ContextVar set_floor() in sync.
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
from pathlib import Path
from typing import Any, Callable, Optional

_DIR = Path(__file__).resolve().parent
_JSON = _DIR / "data" / "luxury_live_floors.json"

_LOCK = threading.RLock()
_IDX = 0
_FLOOR = "LIVE"
_LAST_ADV = 0.0
_APPLIED = False

# Minimal badge meta for peak / live floors (full postcard optional).
_FLOOR_META = {
    "LIVE": {"label": "Live Engine", "peak_wr": None},
    "JUN19": {"label": "JUN 19 Peak", "peak_wr": 76.0},
    "JUN20": {"label": "JUN 20 Peak", "peak_wr": 75.0},
    "JUN08": {"label": "JUN 08 Peak", "peak_wr": 65.9},
    "JUN10": {"label": "JUN 10 Peak", "peak_wr": 71.4},
    "JUN26": {"label": "JUN 26 Peak", "peak_wr": 70.0},
    "JUN27": {"label": "JUN 27 Peak", "peak_wr": 70.0},
    "MAY19": {"label": "MAY 19 MaxPeak", "peak_wr": 76.8},
    "MAY10": {"label": "MAY 10 Peak", "peak_wr": 69.0},
    "MAY11": {"label": "MAY 11 Peak", "peak_wr": 68.6},
    "ELITE_V2": {"label": "Elite V2", "peak_wr": 80.0},
    "ELITE_V2_PEAK": {"label": "Elite V2 Peak", "peak_wr": 82.0},
    "ULTIMATE": {"label": "Ultimate", "peak_wr": 85.0},
    "APR20": {"label": "APR 20 Perfect", "peak_wr": 100.0},
    "MAR19": {"label": "MAR 19 Origin", "peak_wr": 89.5},
    "MAR20": {"label": "MAR 20 Volume", "peak_wr": 83.1},
    "MAR21": {"label": "MAR 21 Best WR", "peak_wr": 93.6},
}


def _enabled() -> bool:
    return os.environ.get("LUXURY_FLOOR_ROTATE", "1").strip() not in {"0", "false", "no"}


def _interval() -> float:
    try:
        return max(30.0, float(os.environ.get("LUXURY_FLOOR_ROTATE_SECS", "180")))
    except Exception:
        return 180.0


def _rotation_list() -> list[str]:
    try:
        data = json.loads(_JSON.read_text(encoding="utf-8"))
    except Exception:
        data = {}
    blocked = {str(x).upper() for x in (data.get("blocked") or [])}
    peaks = [str(x).upper() for x in (data.get("peak_day_floors") or []) if str(x).upper() not in blocked]
    live = [
        str(x).upper()
        for x in (data.get("live_floors") or data.get("live_building_floors") or [])
        if str(x).upper() not in blocked
    ]
    ordered: list[str] = []
    for name in peaks + live:
        if name not in ordered:
            ordered.append(name)
    if not ordered:
        ordered = ["LIVE"]
    if ordered[0] == "LIVE" and len(ordered) > 1:
        ordered = ordered[1:] + ["LIVE"]
    return ordered


def current_floor() -> str:
    with _LOCK:
        _maybe_advance_unlocked()
        return _FLOOR


def advance(reason: str = "manual") -> str:
    global _IDX, _FLOOR, _LAST_ADV
    with _LOCK:
        floors = _rotation_list()
        _IDX = (_IDX + 1) % max(1, len(floors))
        _FLOOR = floors[_IDX]
        _LAST_ADV = time.time()
        _sync_all_unlocked(_FLOOR)
        print(f"[LUXURY] floor-rotate → {_FLOOR} ({reason}) idx={_IDX}/{len(floors)}")
        return _FLOOR


def _maybe_advance_unlocked() -> None:
    global _IDX, _FLOOR, _LAST_ADV
    floors = _rotation_list()
    if _FLOOR not in floors:
        _FLOOR = floors[0]
        _IDX = 0
        _sync_all_unlocked(_FLOOR)
        _LAST_ADV = time.time()
        return
    now = time.time()
    if _LAST_ADV <= 0:
        _LAST_ADV = now
        _sync_all_unlocked(_FLOOR)
        return
    if now - _LAST_ADV >= _interval():
        _IDX = (_IDX + 1) % max(1, len(floors))
        _FLOOR = floors[_IDX]
        _LAST_ADV = now
        _sync_all_unlocked(_FLOOR)
        print(f"[LUXURY] floor-rotate → {_FLOOR} (timer) idx={_IDX}/{len(floors)}")


def _get_floor_impl() -> str:
    if not _enabled():
        try:
            import floor_tracker as ft  # type: ignore

            orig = getattr(ft, "_lux_orig_get_floor", None)
            if callable(orig):
                return str(orig() or "LIVE")
        except Exception:
            pass
        return "LIVE"
    return current_floor()


def _get_floor_badge_impl() -> str:
    fid = _get_floor_impl()
    meta = _FLOOR_META.get(fid) or {}
    # Prefer module FLOOR_META if restored
    try:
        import floor_tracker as ft  # type: ignore

        meta = (getattr(ft, "FLOOR_META", None) or {}).get(fid) or meta
    except Exception:
        pass
    label = meta.get("label", fid)
    peak_wr = meta.get("peak_wr")
    if peak_wr is not None:
        try:
            return f"🏛️ **{fid} — {label}** · Pico {float(peak_wr):.1f}%"
        except Exception:
            pass
    if fid == "LIVE":
        return "🏛️ **Motor Live** · configuração dinâmica"
    return f"🏛️ **{fid} — {label}**"


def _sync_all_unlocked(floor: str) -> None:
    # Keep ContextVar / set_floor in sync so native get_floor() also works.
    try:
        import floor_tracker as ft  # type: ignore

        sf = getattr(ft, "set_floor", None)
        if callable(sf):
            try:
                sf(floor)
            except Exception:
                pass
        for attr in ("CURRENT_FLOOR", "_CURRENT_FLOOR", "active_floor", "ACTIVE_FLOOR"):
            if hasattr(ft, attr):
                try:
                    setattr(ft, attr, floor)
                except Exception:
                    pass
    except Exception:
        pass
    for name in ("state", "__main__", "bacbo_royal_complete"):
        mod = sys.modules.get(name)
        if mod is None:
            continue
        try:
            setattr(mod, "_current_source_floor", floor)
        except Exception:
            pass
        st = getattr(mod, "state", None)
        if st is not None:
            try:
                setattr(st, "_current_source_floor", floor)
            except Exception:
                pass


def _rebind_get_floor_everywhere() -> int:
    """Rebind get_floor in modules that did `from floor_tracker import get_floor`."""
    n = 0
    for mod in list(sys.modules.values()):
        if mod is None:
            continue
        g = getattr(mod, "__dict__", None)
        if not isinstance(g, dict):
            continue
        if "get_floor" in g and callable(g.get("get_floor")):
            # Only rebind if it looks like floor get_floor (no args / from floor_tracker)
            fn = g["get_floor"]
            if getattr(fn, "_lux_floor_rotate", False):
                continue
            name = getattr(fn, "__module__", "") or ""
            qn = getattr(fn, "__qualname__", "") or ""
            if "floor_tracker" in name or qn in {"get_floor", "_get_floor_impl"} or name in {
                "floor_tracker",
                "bot.floor_tracker",
            }:
                g["get_floor"] = _get_floor_impl
                n += 1
        if "get_floor_badge" in g and callable(g.get("get_floor_badge")):
            fnb = g["get_floor_badge"]
            if not getattr(fnb, "_lux_floor_rotate", False):
                g["get_floor_badge"] = _get_floor_badge_impl
                n += 1
    return n


def restore_floor_tracker_api() -> int:
    """Add missing get_floor_badge / FLOOR_META on stripped Replit stubs."""
    n = 0
    try:
        import floor_tracker as ft  # type: ignore
    except Exception as exc:
        print("[LUXURY] floor-rotate: cannot import floor_tracker:", exc)
        return 0

    if not hasattr(ft, "FLOOR_META") or not isinstance(getattr(ft, "FLOOR_META", None), dict):
        ft.FLOOR_META = dict(_FLOOR_META)  # type: ignore[attr-defined]
        n += 1
    else:
        # merge missing keys
        meta = ft.FLOOR_META
        for k, v in _FLOOR_META.items():
            if k not in meta:
                meta[k] = v
                n += 1

    # Preserve original get_floor before wrap
    if not hasattr(ft, "_lux_orig_get_floor"):
        orig = getattr(ft, "get_floor", None)
        if callable(orig) and not getattr(orig, "_lux_floor_rotate", False):
            ft._lux_orig_get_floor = orig  # type: ignore[attr-defined]

    def _wrapped_get() -> str:
        return _get_floor_impl()

    _wrapped_get._lux_floor_rotate = True  # type: ignore[attr-defined]
    ft.get_floor = _wrapped_get  # type: ignore[assignment]

    def _wrapped_badge() -> str:
        return _get_floor_badge_impl()

    _wrapped_badge._lux_floor_rotate = True  # type: ignore[attr-defined]
    ft.get_floor_badge = _wrapped_badge  # type: ignore[attr-defined]
    n += 1

    # Expand allowlists if present
    lux = set(_rotation_list())
    for name in ("ENABLED_FLOORS", "LIVE_FLOORS", "ACTIVE_FLOORS", "FLOOR_ALLOWLIST", "FLOORS"):
        if not hasattr(ft, name):
            continue
        cur = getattr(ft, name)
        if isinstance(cur, set):
            cur |= lux
            n += 1
        elif isinstance(cur, list):
            setattr(ft, name, list(dict.fromkeys([str(x).upper() for x in cur] + list(lux))))
            n += 1
    return n


def _timer_loop() -> None:
    while True:
        try:
            if _enabled():
                with _LOCK:
                    _maybe_advance_unlocked()
                # Rebind periodically — modules may import late
                _rebind_get_floor_everywhere()
        except Exception:
            pass
        time.sleep(15.0)


def apply() -> None:
    global _APPLIED, _FLOOR, _IDX, _LAST_ADV
    if _APPLIED:
        restore_floor_tracker_api()
        _rebind_get_floor_everywhere()
        return
    floors = _rotation_list()
    with _LOCK:
        _FLOOR = floors[0]
        _IDX = 0
        _LAST_ADV = time.time()
    n = restore_floor_tracker_api()
    with _LOCK:
        _sync_all_unlocked(_FLOOR)
    rb = _rebind_get_floor_everywhere()
    try:
        t = threading.Thread(target=_timer_loop, name="lux-floor-rotate", daemon=True)
        t.start()
    except Exception as exc:
        print("[LUXURY] floor-rotate timer failed:", exc)
    _APPLIED = True
    # mark wrapped helpers
    _get_floor_impl._lux_floor_rotate = True  # type: ignore[attr-defined]
    _get_floor_badge_impl._lux_floor_rotate = True  # type: ignore[attr-defined]
    print(
        f"[LUXURY] floor-rotate ON start={_FLOOR} floors={len(floors)} "
        f"api_patches={n} rebinds={rb} every={_interval():.0f}s badge=OK"
    )


apply()
