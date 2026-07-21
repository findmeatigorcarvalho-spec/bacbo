"""
Luxury floor tagging rotator.

DEFAULT MODE = tag (safe):
  - Engines keep ContextVar / wrap_floor behavior (usually LIVE).
  - database.get_floor (rebound) returns rotator floor for source_floor column.
  - get_floor_badge restored/works.
  - Does NOT call set_floor() and does NOT wrap floor_tracker.get_floor
    (wrapping/set_floor was desyncing the LIVE engine → quiet fires).

MODE = override (env LUXURY_FLOOR_ROTATE_MODE=override):
  - Also wraps floor_tracker.get_floor + set_floor sync (old behavior).
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
from pathlib import Path
from typing import Any

_DIR = Path(__file__).resolve().parent
_JSON = _DIR / "data" / "luxury_live_floors.json"

_LOCK = threading.RLock()
_IDX = 0
_FLOOR = "LIVE"
_LAST_ADV = 0.0
_APPLIED = False

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


def _mode() -> str:
    m = (os.environ.get("LUXURY_FLOOR_ROTATE_MODE") or "tag").strip().lower()
    return m if m in {"tag", "override"} else "tag"


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
        _sync_tag_state_unlocked(_FLOOR)
        print(f"[LUXURY] floor-rotate → {_FLOOR} ({reason}) idx={_IDX}/{len(floors)} mode={_mode()}")
        return _FLOOR


def _maybe_advance_unlocked() -> None:
    global _IDX, _FLOOR, _LAST_ADV
    floors = _rotation_list()
    if _FLOOR not in floors:
        _FLOOR = floors[0]
        _IDX = 0
        _LAST_ADV = time.time()
        _sync_tag_state_unlocked(_FLOOR)
        return
    now = time.time()
    if _LAST_ADV <= 0:
        _LAST_ADV = now
        _sync_tag_state_unlocked(_FLOOR)
        return
    if now - _LAST_ADV >= _interval():
        _IDX = (_IDX + 1) % max(1, len(floors))
        _FLOOR = floors[_IDX]
        _LAST_ADV = now
        _sync_tag_state_unlocked(_FLOOR)
        print(f"[LUXURY] floor-rotate → {_FLOOR} (timer) idx={_IDX}/{len(floors)} mode={_mode()}")


def tag_floor() -> str:
    """Floor name for DB source_floor / cards (rotator)."""
    if not _enabled():
        return "LIVE"
    return current_floor()


def _get_floor_impl() -> str:
    """Used by database.py rebind for source_floor writes."""
    return tag_floor()


def _get_floor_badge_impl() -> str:
    fid = tag_floor()
    meta = _FLOOR_META.get(fid) or {}
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


def _sync_tag_state_unlocked(floor: str) -> None:
    # Tag-only: do NOT call set_floor() — that desyncs LIVE engine ContextVar.
    for name in ("state", "__main__", "bacbo_royal_complete"):
        mod = sys.modules.get(name)
        if mod is None:
            continue
        try:
            setattr(mod, "_current_source_floor", floor)
            setattr(mod, "_lux_tag_floor", floor)
        except Exception:
            pass
        st = getattr(mod, "state", None)
        if st is not None:
            try:
                setattr(st, "_current_source_floor", floor)
                setattr(st, "_lux_tag_floor", floor)
            except Exception:
                pass
    if _mode() == "override":
        try:
            import floor_tracker as ft  # type: ignore

            sf = getattr(ft, "set_floor", None)
            if callable(sf):
                sf(floor)
        except Exception:
            pass


def restore_floor_tracker_api() -> int:
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
        meta = ft.FLOOR_META
        for k, v in _FLOOR_META.items():
            if k not in meta:
                meta[k] = v
                n += 1

    # Always provide badge (AccumHold needs it)
    def _wrapped_badge() -> str:
        return _get_floor_badge_impl()

    _wrapped_badge._lux_floor_rotate = True  # type: ignore[attr-defined]
    ft.get_floor_badge = _wrapped_badge  # type: ignore[attr-defined]
    n += 1

    # tag_floor helper for DB / callers
    ft.tag_floor = tag_floor  # type: ignore[attr-defined]
    ft.lux_tag_floor = tag_floor  # type: ignore[attr-defined]

    if _mode() == "override":
        if not hasattr(ft, "_lux_orig_get_floor"):
            orig = getattr(ft, "get_floor", None)
            if callable(orig) and not getattr(orig, "_lux_floor_rotate", False):
                ft._lux_orig_get_floor = orig  # type: ignore[attr-defined]

        def _wrapped_get() -> str:
            return _get_floor_impl()

        _wrapped_get._lux_floor_rotate = True  # type: ignore[attr-defined]
        ft.get_floor = _wrapped_get  # type: ignore[assignment]
        n += 1
    else:
        # tag mode: leave engine get_floor alone (ContextVar / wrap_floor)
        # undo prior override wrap if we installed it
        orig = getattr(ft, "_lux_orig_get_floor", None)
        if callable(orig):
            ft.get_floor = orig  # type: ignore[assignment]
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


def rebind_database_tag_floor() -> int:
    """Ensure database.get_floor returns tag_floor() for source_floor writes."""
    n = 0
    for mod_name in ("database", "bot.database"):
        mod = sys.modules.get(mod_name)
        if mod is None:
            continue
        try:
            mod.get_floor = _get_floor_impl  # type: ignore[attr-defined]
            mod.get_floor_badge = _get_floor_badge_impl  # type: ignore[attr-defined]
            n += 1
        except Exception:
            pass
    return n


def _timer_loop() -> None:
    while True:
        try:
            if _enabled():
                with _LOCK:
                    _maybe_advance_unlocked()
                rebind_database_tag_floor()
        except Exception:
            pass
        time.sleep(15.0)


def apply() -> None:
    global _APPLIED, _FLOOR, _IDX, _LAST_ADV
    floors = _rotation_list()
    with _LOCK:
        if not _APPLIED:
            _FLOOR = floors[0]
            _IDX = 0
            _LAST_ADV = time.time()
        _sync_tag_state_unlocked(_FLOOR)
    n = restore_floor_tracker_api()
    rb = rebind_database_tag_floor()
    if not _APPLIED:
        # Defer timer so import during bacbo boot cannot race subscribe/DB.
        def _start_timer() -> None:
            try:
                time.sleep(5.0)
                t = threading.Thread(target=_timer_loop, name="lux-floor-rotate", daemon=True)
                t.start()
            except Exception as exc:
                print("[LUXURY] floor-rotate timer failed:", exc)

        try:
            threading.Thread(target=_start_timer, name="lux-floor-rotate-boot", daemon=True).start()
        except Exception as exc:
            print("[LUXURY] floor-rotate timer schedule failed:", exc)
        _APPLIED = True
    _get_floor_impl._lux_floor_rotate = True  # type: ignore[attr-defined]
    _get_floor_badge_impl._lux_floor_rotate = True  # type: ignore[attr-defined]
    print(
        f"[LUXURY] floor-rotate ON start={_FLOOR} floors={len(floors)} "
        f"mode={_mode()} api_patches={n} db_rebinds={rb} every={_interval():.0f}s badge=OK"
    )


# Only auto-apply when not deferred
if os.environ.get("LUXURY_FLOOR_ROTATE_DEFER_APPLY", "0").strip() not in {"1", "true", "yes"}:
    apply()
