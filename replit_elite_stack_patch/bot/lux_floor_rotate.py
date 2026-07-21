"""
Rotate logical source floors across the luxury live building.

Problem: get_floor() / _current_source_floor stuck on LIVE → all consensus
rows and Telegram cards show FLOOR: LIVE even when 32 floors are allowlisted.

This module:
  1) Wraps floor_tracker.get_floor / set_floor (if present)
  2) Keeps state._current_source_floor in sync
  3) Advances through peak-day floors first, then other live floors

Env:
  LUXURY_FLOOR_ROTATE_SECS  seconds between advances (default 180)
  LUXURY_FLOOR_ROTATE=0     disable
"""
from __future__ import annotations

import json
import os
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
_ORIG_GET: Optional[Callable] = None
_APPLIED = False


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
    # Peak days first (user policy), then remaining live floors, LIVE last among non-peaks.
    ordered: list[str] = []
    for name in peaks + live:
        if name not in ordered:
            ordered.append(name)
    if not ordered:
        ordered = ["LIVE"]
    # Prefer not starting forever on LIVE if peaks exist
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
        _sync_state_unlocked(_FLOOR)
        print(f"[LUXURY] floor-rotate → {_FLOOR} ({reason}) idx={_IDX}/{len(floors)}")
        return _FLOOR


def _maybe_advance_unlocked() -> None:
    global _IDX, _FLOOR, _LAST_ADV
    floors = _rotation_list()
    if _FLOOR not in floors:
        _FLOOR = floors[0]
        _IDX = 0
        _sync_state_unlocked(_FLOOR)
        _LAST_ADV = time.time()
        return
    now = time.time()
    if _LAST_ADV <= 0:
        _LAST_ADV = now
        _sync_state_unlocked(_FLOOR)
        return
    if now - _LAST_ADV >= _interval():
        _IDX = (_IDX + 1) % max(1, len(floors))
        _FLOOR = floors[_IDX]
        _LAST_ADV = now
        _sync_state_unlocked(_FLOOR)
        print(f"[LUXURY] floor-rotate → {_FLOOR} (timer) idx={_IDX}/{len(floors)}")


def _sync_state_unlocked(floor: str) -> None:
    # floor_tracker.set_floor if present
    try:
        import floor_tracker as ft  # type: ignore

        if callable(getattr(ft, "set_floor", None)):
            try:
                ft.set_floor(floor)
            except Exception:
                pass
        # common attribute names
        for attr in ("CURRENT_FLOOR", "_CURRENT_FLOOR", "active_floor", "ACTIVE_FLOOR"):
            if hasattr(ft, attr):
                try:
                    setattr(ft, attr, floor)
                except Exception:
                    pass
    except Exception:
        pass
    # state module / __main__
    for name in ("state", "__main__"):
        mod = __import__("sys").modules.get(name)
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


def _wrap_get_floor(orig: Callable) -> Callable:
    def _wrapped(*a, **k):
        if not _enabled():
            return orig(*a, **k)
        return current_floor()

    _wrapped._lux_floor_rotate = True  # type: ignore[attr-defined]
    return _wrapped


def patch_floor_tracker() -> int:
    global _ORIG_GET
    n = 0
    try:
        import floor_tracker as ft  # type: ignore
    except Exception as exc:
        print("[LUXURY] floor-rotate: floor_tracker import failed:", exc)
        return 0
    get = getattr(ft, "get_floor", None)
    if callable(get) and not getattr(get, "_lux_floor_rotate", False):
        _ORIG_GET = get
        ft.get_floor = _wrap_get_floor(get)  # type: ignore[attr-defined]
        n += 1
    # ensure set_floor exists for sync
    if not callable(getattr(ft, "set_floor", None)):

        def _set_floor(name: str) -> str:
            global _FLOOR, _IDX, _LAST_ADV
            floors = _rotation_list()
            name = (name or "LIVE").strip().upper()
            with _LOCK:
                if name in floors:
                    _FLOOR = name
                    _IDX = floors.index(name)
                else:
                    _FLOOR = name
                _LAST_ADV = time.time()
                _sync_state_unlocked(_FLOOR)
            return _FLOOR

        ft.set_floor = _set_floor  # type: ignore[attr-defined]
        n += 1
    return n


def _timer_loop() -> None:
    while True:
        try:
            if _enabled():
                with _LOCK:
                    _maybe_advance_unlocked()
        except Exception:
            pass
        time.sleep(15.0)


def apply() -> None:
    global _APPLIED, _FLOOR, _IDX, _LAST_ADV
    if _APPLIED:
        return
    if not _enabled():
        print("[LUXURY] floor-rotate disabled")
        _APPLIED = True
        return
    floors = _rotation_list()
    with _LOCK:
        # Start on first peak floor (not LIVE)
        _FLOOR = floors[0]
        _IDX = 0
        _LAST_ADV = time.time()
        _sync_state_unlocked(_FLOOR)
    n = patch_floor_tracker()
    try:
        t = threading.Thread(target=_timer_loop, name="lux-floor-rotate", daemon=True)
        t.start()
    except Exception as exc:
        print("[LUXURY] floor-rotate timer failed:", exc)
    _APPLIED = True
    print(f"[LUXURY] floor-rotate ON start={_FLOOR} floors={len(floors)} patched={n} every={_interval():.0f}s")


apply()
