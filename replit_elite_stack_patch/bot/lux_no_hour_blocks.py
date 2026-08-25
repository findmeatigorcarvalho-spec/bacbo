"""
Luxury peak-pure mode: neutralize hour-block layers that suppress fires.

Peak floors stay peak-locked for strategy; dynamic/static UTC hour blocks
are emptied so winning windows are not silenced (esp. H22 / AutoCHB / AutoIntel).

Import once at process start (bacbo). Safe no-op if attrs missing.
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_APPLIED = False
_LAST_SWEEP = 0.0
_JSON_CLEARED = False

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
_AUDITOR_CLS_MARK = "_lux_nhb_patched"

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


_INSTANCE_ATTR_FRAGMENTS = (
    "dynamic_block",
    "dynamic_addition",
    "color_hour",
    "bad_hr",
    "bad_hour",
    "blocked_hour",
    "hour_block",
)

_AUDITOR_NAME_FRAGMENTS = (
    "autocolor",
    "autochb",
    "autointel",
    "colorauditor",
    "hourblock",
)


def _is_auditor_class(cls: type) -> bool:
    name = (getattr(cls, "__name__", "") or "").lower()
    return any(frag in name for frag in _AUDITOR_NAME_FRAGMENTS)


def _empty_block_value(val: Any) -> Any:
    if isinstance(val, frozenset):
        return frozenset()
    if isinstance(val, set):
        val.clear()
        return val
    if isinstance(val, list):
        return []
    if isinstance(val, dict):
        # Keep skin keys (GOLDEN/SOLO_ELITE/…) so restore code still iterates.
        return {k: ([] if isinstance(v, list) else {}) for k, v in val.items()}
    if isinstance(val, tuple):
        return ()
    return val


def neutralize_object(obj: Any) -> int:
    d = getattr(obj, "__dict__", None)
    if not isinstance(d, dict):
        return 0
    n = 0
    for name, val in list(d.items()):
        lk = str(name).lower()
        if not any(frag in lk for frag in _INSTANCE_ATTR_FRAGMENTS):
            continue
        emptied = _empty_block_value(val)
        if emptied is not val or (isinstance(val, (list, dict, set, frozenset, tuple)) and val):
            try:
                setattr(obj, name, emptied)
                n += 1
            except Exception:
                try:
                    d[name] = emptied
                    n += 1
                except Exception:
                    pass
    return n


def _iter_auditor_classes() -> list[type]:
    found: list[type] = []
    seen: set[int] = set()
    for _name, mod in list(sys.modules.items()):
        if mod is None:
            continue
        d = getattr(mod, "__dict__", None)
        if not isinstance(d, dict):
            continue
        for obj in list(d.values()):
            if not isinstance(obj, type):
                continue
            if id(obj) in seen:
                continue
            if _is_auditor_class(obj):
                seen.add(id(obj))
                found.append(obj)
    return found


def _noop_method(self, *a, **k):  # noqa: ANN001
    return None


def patch_auditor_classes() -> int:
    """Make AutoCHB / AutoIntel restore+save hour-block methods no-ops."""
    n = 0
    for cls in _iter_auditor_classes():
        if getattr(cls, _AUDITOR_CLS_MARK, False):
            continue
        for name in dir(cls):
            if name.startswith("__"):
                continue
            lu = name.lower()
            cls_l = (getattr(cls, "__name__", "") or "").lower()
            is_intel = "intel" in cls_l
            # Keep AutoIntel good-pair restore; only mute hour/block methods.
            if "restore" in lu and is_intel and not any(
                x in lu for x in ("block", "hour", "bad", "chb")
            ):
                continue
            interesting = (
                "restore" in lu
                or "dynamic_block" in lu
                or "hour_block" in lu
                or (
                    lu.startswith(("save", "persist", "write", "add", "load"))
                    and any(x in lu for x in ("block", "hour", "dynamic"))
                )
            )
            if not interesting:
                continue
            try:
                current = getattr(cls, name)
            except Exception:
                continue
            if not callable(current):
                continue
            try:
                setattr(cls, name, _noop_method)
                n += 1
            except Exception:
                pass
        try:
            setattr(cls, _AUDITOR_CLS_MARK, True)
        except Exception:
            pass
    return n


def neutralize_auditor_instances() -> int:
    """Clear in-memory AutoCHB / AutoIntel blocks after they restore from JSON."""
    try:
        import gc
    except Exception:
        return 0
    n = 0
    try:
        objects = gc.get_objects()
    except Exception:
        return 0
    for obj in objects:
        try:
            cls = type(obj)
            if not _is_auditor_class(cls):
                continue
        except Exception:
            continue
        try:
            n += neutralize_object(obj)
        except Exception:
            pass
    return n


def clear_persist_json(data_dir: Path | None = None) -> dict[str, Any]:
    """Empty AutoCHB / AutoIntel JSON so the next boot cannot restore hour mutes.

    Keeps AutoIntel good-pairs. Only wipes bad-hour / dynamic-block lists.
    """
    root = data_dir or DATA
    root.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {"dir": str(root), "files": []}

    chb_path = root / "color_hour_blocks.json"
    chb = {
        "rev": "luxury-no-hour-blocks",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "note": "Hour blocks disabled for peak-volume FIRE. Dynamic AutoCHB lists emptied.",
        "dynamic_additions": {
            "GOLDEN": [],
            "SOLO_ELITE": [],
            "FLASH": [],
            "PLATINUM": [],
        },
    }
    try:
        chb_path.write_text(json.dumps(chb, indent=2) + "\n", encoding="utf-8")
        report["files"].append(str(chb_path.name))
        report["color_hour_blocks"] = "emptied"
    except Exception as exc:
        report["color_hour_blocks"] = repr(exc)

    intel_path = root / "intelligence_state.json"
    if intel_path.is_file():
        try:
            raw = json.loads(intel_path.read_text(encoding="utf-8"))
        except Exception:
            raw = {}
        if not isinstance(raw, dict):
            raw = {}
        cleared: list[str] = []
        for key in (
            "dynamic_platinum_bad_hrs",
            "dynamic_solo_bad_hrs",
            "dynamic_golden_bad_hrs",
            "dynamic_flash_bad_hrs",
            "platinum_bad_hrs",
            "solo_bad_hrs",
            "golden_bad_hrs",
        ):
            if key in raw and raw[key]:
                cleared.append(key)
            if isinstance(raw.get(key), dict):
                raw[key] = {}
            elif key in raw:
                raw[key] = []
        for key in list(raw.keys()):
            lk = str(key).lower()
            if "bad_hr" in lk or "bad_hour" in lk or "hour_block" in lk:
                val = raw[key]
                if val:
                    cleared.append(str(key))
                if isinstance(val, dict):
                    raw[key] = {}
                elif isinstance(val, list):
                    raw[key] = []
        raw["lux_no_hour_blocks"] = True
        raw["lux_no_hour_blocks_at"] = datetime.now(timezone.utc).isoformat()
        try:
            intel_path.write_text(json.dumps(raw, indent=2) + "\n", encoding="utf-8")
            report["files"].append(intel_path.name)
            report["intelligence_bad_hours"] = cleared
        except Exception as extra:
            report["intelligence_bad_hours"] = repr(extra)
    else:
        report["intelligence_bad_hours"] = "missing"

    for extra_name, extra_keys in (
        ("accuracy_blocks.json", ("suspended_kinds", "blocked_hours")),
        ("ai_learned_rules.json", ("hour_rules_golden", "hour_rules_solo_elite", "day_of_week_block")),
    ):
        extra_path = HERE / extra_name
        if not extra_path.is_file():
            extra_path = root / extra_name
        if not extra_path.is_file():
            continue
        try:
            blob = json.loads(extra_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(blob, dict):
            continue
        changed = False
        for key in extra_keys:
            if blob.get(key):
                blob[key] = [] if not isinstance(blob.get(key), dict) else {}
                changed = True
        if changed:
            try:
                extra_path.write_text(json.dumps(blob, indent=2) + "\n", encoding="utf-8")
                report["files"].append(extra_path.name)
            except Exception:
                pass
    return report


def full_sweep() -> dict[str, int]:
    gates = sweep_loaded_gates()
    patched = patch_auditor_classes()
    inst = neutralize_auditor_instances()
    return {"gates": gates, "patched": patched, "instances": inst}


def _start_forever_sweep() -> None:
    try:
        import threading

        def _loop() -> None:
            # AutoCHB restores from JSON during bot __init__, after this module
            # already imported. Hit that window hard, then keep the lists empty.
            for d in (0.4, 1.0, 2.0, 4.0, 8.0, 15.0, 30.0):
                time.sleep(d)
                try:
                    full_sweep()
                except Exception:
                    pass
            while True:
                time.sleep(20.0)
                try:
                    full_sweep()
                    clear_persist_json()
                except Exception:
                    pass

        threading.Thread(target=_loop, name="lux_no_hour_blocks_sweep", daemon=True).start()
    except Exception:
        pass


def apply(*, force: bool = False) -> dict[str, Any]:
    global _APPLIED, _LAST_SWEEP, _JSON_CLEARED
    json_report: dict[str, Any] = {}
    if not _JSON_CLEARED or force:
        json_report = clear_persist_json()
        _JSON_CLEARED = True
        print(
            "[LUXURY] NO_HOUR_BLOCKS json",
            f"chb={json_report.get('color_hour_blocks')}",
            f"intel={json_report.get('intelligence_bad_hours')}",
        )
    if _APPLIED and not force:
        now = time.time()
        if now - _LAST_SWEEP > 5:
            full_sweep()
            _LAST_SWEEP = now
        return {"json": json_report, "already": True}
    patch_database()
    counts = full_sweep()
    _APPLIED = True
    _LAST_SWEEP = time.time()
    _start_forever_sweep()
    print(
        "[LUXURY] NO_HOUR_BLOCKS on —",
        f"gates={counts['gates']} patched={counts['patched']} instances={counts['instances']}",
        "hour blocks disabled",
    )
    return {"json": json_report, "sweep": counts}


# Keep sweeping as new gate modules appear
class _GateSweepFinder:
    def find_module(self, fullname, path=None):  # py<3.4 API still consulted by some loaders
        return None

    def find_spec(self, fullname, path=None, target=None):
        lname = (fullname or "").lower()
        if "_gates_" in lname or "bacbo" in lname:
            try:
                import threading

                threading.Timer(0.05, full_sweep).start()
            except Exception:
                pass
        return None


if not any(isinstance(x, _GateSweepFinder) for x in sys.meta_path):
    sys.meta_path.insert(0, _GateSweepFinder())

apply()


if __name__ == "__main__":
    import tempfile

    tmp = Path(tempfile.mkdtemp(prefix="lux_nhb_"))
    intel = {
        "good_pairs": [["a", "b"]],
        "dynamic_solo_bad_hrs": [10, 12, 20],
        "dynamic_platinum_bad_hrs": [0, 7],
        "probation_caps": {"baccarat_b": 0.7},
    }
    (tmp / "intelligence_state.json").write_text(json.dumps(intel), encoding="utf-8")
    report = clear_persist_json(tmp)
    intel2 = json.loads((tmp / "intelligence_state.json").read_text(encoding="utf-8"))
    chb2 = json.loads((tmp / "color_hour_blocks.json").read_text(encoding="utf-8"))
    assert intel2["dynamic_solo_bad_hrs"] == [], intel2
    assert intel2["dynamic_platinum_bad_hrs"] == [], intel2
    assert intel2["good_pairs"] == [["a", "b"]], intel2
    assert intel2["probation_caps"] == {"baccarat_b": 0.7}, intel2
    assert chb2["dynamic_additions"]["GOLDEN"] == []
    assert chb2["dynamic_additions"]["SOLO_ELITE"] == []

    class AutoColorAuditor:
        def restore_dynamic_blocks(self):
            self.dynamic_additions = {"GOLDEN": [(12, "red")]}

        def save_dynamic_blocks(self):
            return "saved"

    class AutoIntelligence:
        def restore_state(self):
            return "good-pairs-kept"

        def restore_bad_hours(self):
            self.dynamic_solo_bad_hrs = [10, 12]

    inst = AutoColorAuditor()
    inst.dynamic_additions = {"GOLDEN": [(12, "red")], "SOLO_ELITE": [(10, "blue")]}
    intel_inst = AutoIntelligence()
    intel_inst.dynamic_solo_bad_hrs = [10, 12, 20]
    intel_inst.good_pairs = [("x", "y")]
    sys.modules[__name__].AutoColorAuditor = AutoColorAuditor  # type: ignore[attr-defined]
    sys.modules[__name__].AutoIntelligence = AutoIntelligence  # type: ignore[attr-defined]
    patched = patch_auditor_classes()
    assert patched >= 2, patched
    assert AutoColorAuditor().restore_dynamic_blocks() is None
    assert AutoIntelligence().restore_state() == "good-pairs-kept"
    n_obj = neutralize_object(inst) + neutralize_object(intel_inst)
    assert inst.dynamic_additions["GOLDEN"] == [], inst.dynamic_additions
    assert intel_inst.dynamic_solo_bad_hrs == [], intel_inst.dynamic_solo_bad_hrs
    assert intel_inst.good_pairs == [("x", "y")]
    print("NO_HOUR_BLOCKS_SELFTEST_OK", report, "patched", patched, "n_obj", n_obj)
