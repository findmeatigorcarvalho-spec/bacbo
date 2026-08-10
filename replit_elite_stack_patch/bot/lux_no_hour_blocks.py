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
    "_SOLO_GLOBAL_BAD_UTC",
    "_SOLO_BAD_UTC",
    "_SOLO_BAD_UTC_HOURS",
    "_GLOBAL_BAD_UTC",
    "_ROOM_HOUR_BLOCK",
    "_PLATINUM_HOUR_BLOCK",
    "_PLATINUM_COLOR_HOUR_BLOCK",
    "_CORINGA_HOUR_BLOCK",
    "_SOLO_BAD_HOURS",
    "_PLATINUM_BAD_HOURS",
)

# Name fragments that must stay set-like (never float/str) for `x in ATTR` checks
_SETISH_FRAGMENTS = (
    "BAD_UTC",
    "BAD_HOURS",
    "HOUR_BLOCK",
    "BLOCKED_HOURS",
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
    # Corrupted bindings (float/str/None) break `hour in ATTR` → TypeError
    return frozenset()


def _is_setish_name(name: str) -> bool:
    u = (name or "").upper()
    return any(frag in u for frag in _SETISH_FRAGMENTS)


def neutralize_module(mod: Any) -> int:
    n = 0
    d = getattr(mod, "__dict__", None)
    names = set(_ATTRS)
    if isinstance(d, dict):
        for name in list(d.keys()):
            if isinstance(name, str) and _is_setish_name(name):
                names.add(name)
    for name in names:
        if not hasattr(mod, name):
            continue
        val = getattr(mod, name)
        if isinstance(val, set):
            if val:
                val.clear()
                n += 1
            continue
        if isinstance(val, frozenset):
            if val:
                setattr(mod, name, frozenset())
                n += 1
            continue
        if isinstance(val, list):
            if val:
                setattr(mod, name, [])
                n += 1
            continue
        if isinstance(val, dict):
            if val:
                setattr(mod, name, {})
                n += 1
            continue
        # float/int/str/None — force empty frozenset so `in` never TypeErrors
        if not callable(val):
            setattr(mod, name, _empty_like(val))
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
        lname = (name or "").lower()
        interesting = (
            "_gates_" in lname
            or "gates" in lname
            or name in {"__main__", "signal_handler", "config", "bacbo_royal_complete", "bacbo"}
            or hasattr(mod, "_SOLO_COLOR_HOUR_BLOCK")
            or hasattr(mod, "_GOLDEN_BAD_UTC_HOURS")
            or hasattr(mod, "_SOLO_GLOBAL_BAD_UTC")
            or hasattr(mod, "_get_blocked_hours")
            or hasattr(mod, "_COLOR_HOUR_BLOCK")
        )
        if interesting:
            total += neutralize_module(mod)
    return total


def patch_database() -> None:
    try:
        import database as db  # type: ignore

        if hasattr(db, "auto_evaluate_hour_blocks"):
            db.auto_evaluate_hour_blocks = lambda *a, **k: set()  # type: ignore
    except Exception:
        pass


def _start_forever_sweep() -> None:
    try:
        import threading

        def _loop() -> None:
            for d in (2.0, 8.0, 20.0, 45.0):
                time.sleep(d)
                try:
                    sweep_loaded_gates()
                except Exception:
                    pass
            while True:
                time.sleep(20.0)
                try:
                    sweep_loaded_gates()
                except Exception:
                    pass

        threading.Thread(target=_loop, name="lux_no_hour_blocks_sweep", daemon=True).start()
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
    _start_forever_sweep()
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
