"""
Luxury peak-pure mode: neutralize hour-block layers that suppress fires.

Peak floors stay peak-locked for strategy; dynamic/static UTC hour blocks
are emptied so winning windows are not silenced (esp. H22 / AutoCHB / AutoIntel).

Import once at process start (bacbo). Safe no-op if attrs missing.
"""
from __future__ import annotations

import sys
import time
from typing import Any


_APPLIED = False
_LAST_SWEEP = 0.0

_ATTRS = (
    "_BLOCKED_HOURS_CACHE",
    "_COLOR_HOUR_BLOCK",
    "_SOLO_COLOR_HOUR_BLOCK",
    "_GOLDEN_COLOR_HOUR_BLOCK",
    "_FLASH_COLOR_HOUR_BLOCK",
    "_GOLDEN_BAD_UTC_HOURS",
    "_ROOM_HOUR_BLOCK",
    "_PLATINUM_HOUR_BLOCK",
    "_PLATINUM_COLOR_HOUR_BLOCK",
    "_CORINGA_HOUR_BLOCK",
    "_SOLO_BAD_HOURS",
    "_PLATINUM_BAD_HOURS",
)


def _empty_like(val: Any) -> Any:
    if isinstance(val, frozenset):
        return frozenset()
    if isinstance(val, set):
        return set()
    if isinstance(val, list):
        return []
    if isinstance(val, dict):
        return {}
    return val


def neutralize_module(mod: Any) -> int:
    n = 0
    for name in _ATTRS:
        if not hasattr(mod, name):
            continue
        val = getattr(mod, name)
        if isinstance(val, set):
            val.clear()
            n += 1
        elif isinstance(val, frozenset):
            setattr(mod, name, frozenset())
            n += 1
        elif isinstance(val, list):
            setattr(mod, name, [])
            n += 1
    if hasattr(mod, "_get_blocked_hours"):
        setattr(mod, "_get_blocked_hours", lambda: set())
        n += 1
    ag = getattr(mod, "_AG_CACHE", None)
    if isinstance(ag, dict) and "blocked_hours" in ag:
        ag["blocked_hours"] = set()
        n += 1
    agl = getattr(mod, "_AG_LAST_GOOD", None)
    if isinstance(agl, dict) and "blocked_hours" in agl:
        agl["blocked_hours"] = set()
        n += 1
    return n


def sweep_loaded_gates() -> int:
    total = 0
    for name, mod in list(sys.modules.items()):
        if mod is None:
            continue
        if "_gates_" in name or hasattr(mod, "_SOLO_COLOR_HOUR_BLOCK") or hasattr(mod, "_get_blocked_hours"):
            total += neutralize_module(mod)
    return total


def patch_database() -> None:
    try:
        import database as db  # type: ignore

        if hasattr(db, "auto_evaluate_hour_blocks"):
            db.auto_evaluate_hour_blocks = lambda *a, **k: set()  # type: ignore
    except Exception:
        pass


def apply() -> None:
    global _APPLIED, _LAST_SWEEP
    if _APPLIED:
        # light re-sweep (gates may load later)
        now = time.time()
        if now - _LAST_SWEEP > 15:
            sweep_loaded_gates()
            _LAST_SWEEP = now
        return
    patch_database()
    n = sweep_loaded_gates()
    _APPLIED = True
    _LAST_SWEEP = time.time()
    print(f"[LUXURY] NO_HOUR_BLOCKS on — neutralized {n} gate attrs; hour blocks disabled")


# Keep sweeping as new gate modules appear
class _GateSweepFinder:
    def find_module(self, fullname, path=None):  # py<3.4 API still consulted by some loaders
        return None

    def find_spec(self, fullname, path=None, target=None):
        if "_gates_" in fullname:
            # defer: schedule sweep after import completes
            try:
                import threading

                threading.Timer(0.05, sweep_loaded_gates).start()
            except Exception:
                pass
        return None


if not any(isinstance(x, _GateSweepFinder) for x in sys.meta_path):
    sys.meta_path.insert(0, _GateSweepFinder())

apply()
