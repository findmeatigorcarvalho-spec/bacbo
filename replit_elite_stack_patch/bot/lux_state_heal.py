#!/usr/bin/env python3
"""Heal bot/state.py so the live megafile cannot AttributeError on missing names.

The 20260819b healer only patched `_quarantine_tasks`. The 20260819c healer
scanned bacbo_royal_complete.py and defaulted unknown names to None. That still
crashed:

  async with state._lock   → AttributeError, then TypeError if _lock = None
  (the real use is in bot/signal_handler.py, not the megafile)

This healer:
  1. Scans EVERY .py under the workspace (megafile + signal_handler + bot/).
  2. Uses typed defaults — asyncio.Lock() for *lock, dict/list/set otherwise.
  3. Replaces a previous FALLBACK_ATTRS block instead of stacking None=None.
  4. Injects module ``__getattr__`` so a future unknown name cannot crash-loop.
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT_CANDIDATES = (
    Path("/home/runner/workspace"),
    Path.cwd(),
    Path(__file__).resolve().parent.parent,
)

FALLBACK_BEGIN = "# --- LUXURY_STATE_FALLBACK_ATTRS"
FALLBACK_END = "# --- end LUXURY_STATE_FALLBACK_ATTRS ---"
GETATTR_BEGIN = "# --- LUXURY_STATE_GETATTR"
GETATTR_END = "# --- end LUXURY_STATE_GETATTR ---"

STRUCTURAL = {"client", "me", "running", "engine", "learner", "bind", "on"}

# Live engine handles. A cold-start default is fine, but the runtime sweep must
# NEVER retype these: coercing them to {} every 15s wiped the prediction state
# the engine had built, so coalition never reached a decision and no consensus
# row was ever written.
NEVER_COERCE_AT_RUNTIME = {
    "_color_markov",
    "_markov_engine",
}

# Always dicts — signal_handler does state._rooms.get(chat_id).
ALWAYS_DICT = {
    "_rooms",
    "_pending",
    "_results",
    "_quarantine_tasks",
    "_room_depth",
    "_room_recency",
    "_room_rti",
    "_room_color_acc",
    "_color_markov",
    "_markov_engine",
    "_pipeline_predictions",
    "_g0_miss_insight_tracking",
    "_indep_learn_seen",
    "_resolved_auto_outcome_cids",
    "_result_dispatched_cids",
    "_result_last_outcome_by_cid",
    "_gale_chain_ids",
    "_event_seen_ids",
    "_poll_seen_ids",
    "_cid_first_mover",
    "_room_speed_history",
    "_room_color_flip_history",
    "_room_last_2_colors",
    "_room_first_mover_total",
    "_room_first_mover_wins",
    "_room_gale_exit_ts",
    "_room_last_entry_color",
    "_room_last_entry_ts",
    "_room_solo_loss_time",
    "_room_scan_time",
}

SET_NAMES = {n for n in ALWAYS_DICT if n.endswith(("_ids", "_seen", "_cids"))}

GET_RX = re.compile(r"\bstate\.([A-Za-z_][A-Za-z0-9_]*)\.get\s*\(")
ITEM_RX = re.compile(r"\bstate\.([A-Za-z_][A-Za-z0-9_]*)\[")

_MISSING = object()


def _root() -> Path:
    for cand in ROOT_CANDIDATES:
        if (cand / "bot" / "state.py").is_file() or (cand / "bacbo_royal_complete.py").is_file():
            return cand
    return Path.cwd()


def mapping_names(root: Path) -> set[str]:
    """Names used as state.X.get(...) or state.X[k] — must be dicts, never None."""
    found: set[str] = set(ALWAYS_DICT)
    for path in _iter_py_files(root):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        found.update(GET_RX.findall(text))
        found.update(ITEM_RX.findall(text))
    return found


def default_expr(name: str, dict_names: set[str] | None = None) -> str:
    if dict_names and name in dict_names:
        return "{}"
    n = name.lower()
    if name in ALWAYS_DICT or n.endswith(
        ("_rooms", "_handles", "_clients", "_peers", "_by_chat", "_by_room")
    ):
        return "{}"
    if n.endswith("_lock") or n == "lock":
        return "asyncio.Lock()"
    if n.endswith(
        (
            "_tasks",
            "_map",
            "_cache",
            "_index",
            "_counts",
            "_scores",
            "_by_id",
            "_state",
            "_tracking",
            "_buffer",
        )
    ):
        return "{}"
    if n in ALWAYS_DICT:
        return "{}"
    if n.endswith(("_ids", "_seen")):
        return "set()"
    if n.endswith("_set"):
        return "set()"
    if n.endswith(
        (
            "_sequence",
            "_history",
            "_queue",
            "_log",
            "_events",
            "_list",
        )
    ):
        return "[]"
    if n.endswith(("_count", "_total", "_n", "_len")):
        return "0"
    if n.endswith(("_flag", "_enabled", "_active", "_ready", "_scanning")):
        return "False"
    if n.endswith(("_txt", "_line", "_reason", "_kind", "_color", "_phase")):
        return "''"
    # `_room` (singular) is often a string handle; `_rooms` is the map (above).
    if n.endswith("_room"):
        return "''"
    if n.endswith(("_task", "_until", "_time", "_ts", "_wall", "_pct", "_id")):
        return "None"
    return "None"


def _iter_py_files(root: Path) -> list[Path]:
    out: list[Path] = []
    for cand in (
        root / "bacbo_royal_complete.py",
        root / "bot" / "bacbo_royal_complete.py",
        root / "bot" / "signal_handler.py",
        root / "bot" / "hotfix_signal_handler.py",
    ):
        if cand.is_file():
            out.append(cand)
    bot = root / "bot"
    if bot.is_dir():
        for p in bot.rglob("*.py"):
            if p.name == "lux_state_heal.py":
                continue
            out.append(p)
    # de-dupe, prefer longer files first (megafile / signal_handler)
    uniq: dict[str, Path] = {}
    for p in out:
        uniq[str(p.resolve())] = p
    return sorted(uniq.values(), key=lambda p: p.stat().st_size if p.exists() else 0, reverse=True)


def referenced_names(root: Path) -> set[str]:
    found: set[str] = set()
    rx = re.compile(r"\bstate\.([A-Za-z_][A-Za-z0-9_]*)")
    for path in _iter_py_files(root):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        found.update(rx.findall(text))
    return found


def _strip_block(src: str, begin: str, end: str) -> str:
    while begin in src and end in src:
        i = src.find(begin)
        j = src.find(end, i)
        if i < 0 or j < 0:
            break
        j += len(end)
        src = (src[:i] + src[j:]).rstrip() + "\n"
    return src


def _defined_names(src: str) -> set[str]:
    names = set(re.findall(r"^([A-Za-z_][A-Za-z0-9_]*)\s*[:=]", src, re.M))
    return names | STRUCTURAL


def _ensure_asyncio_import(src: str) -> str:
    if re.search(r"^import asyncio\b", src, re.M):
        return src
    if re.search(r"^from asyncio import\b", src, re.M):
        return src
    lines = src.splitlines(keepends=True)
    insert_at = 0
    for j, ln in enumerate(lines):
        if ln.startswith("from __future__"):
            insert_at = j + 1
    lines.insert(insert_at, "import asyncio\n")
    return "".join(lines)


GETATTR_BLOCK = f'''
{GETATTR_BEGIN} (auto; never AttributeError on a new megafile name) ---
def __getattr__(name):
    """PEP 562 — invent a typed default the first time a missing name is read."""
    if name.startswith("__"):
        raise AttributeError(name)
    n = name.lower()
    if n.endswith("_lock") or n == "lock":
        val = asyncio.Lock()
    elif (
        n.endswith(("_rooms", "_handles", "_clients", "_peers", "_tasks", "_map", "_cache", "_index", "_counts", "_scores", "_by_id", "_state", "_tracking", "_buffer"))
        or name in {{
            "_rooms", "_pending", "_results", "_room_depth", "_room_recency", "_room_rti",
        }}
    ):
        val = {{}}
    elif n.endswith(("_ids", "_seen", "_set")):
        val = set()
    elif n.endswith(("_sequence", "_history", "_queue", "_log", "_events", "_list")):
        val = []
    elif n.endswith(("_count", "_total", "_n", "_len")):
        val = 0
    elif n.endswith(("_flag", "_enabled", "_active", "_ready", "_scanning")):
        val = False
    elif n.endswith(("_txt", "_line", "_reason")):
        val = ""
    else:
        val = None
    globals()[name] = val
    return val
{GETATTR_END}
'''


def heal(root: Path | None = None) -> dict:
    root = root or _root()
    state_py = root / "bot" / "state.py"
    if not state_py.is_file():
        return {"ok": False, "error": f"missing {state_py}"}

    src = state_py.read_text(encoding="utf-8", errors="replace")
    src = _strip_block(src, FALLBACK_BEGIN, FALLBACK_END)
    src = _strip_block(src, GETATTR_BEGIN, GETATTR_END)
    src = _ensure_asyncio_import(src)
    dict_names = mapping_names(root)

    def _none_repl(m: re.Match[str]) -> str:
        name = m.group(1)
        expr = default_expr(name, dict_names)
        if expr != "None":
            return f"{name} = {expr}"
        return m.group(0)

    # Previous healers left `_rooms = None` / `_lock = None` in the file.
    src = re.sub(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*None\s*$", _none_repl, src, flags=re.M)

    referenced = referenced_names(root) | dict_names
    defined = _defined_names(src)
    missing = sorted(n for n in referenced if n not in defined and not n.startswith("__"))

    add: list[str] = [
        "",
        f"{FALLBACK_BEGIN} (auto; scanned {len(referenced)} refs from live .py) ---",
    ]
    for name in missing:
        add.append(f"{name} = {default_expr(name, dict_names)}")
    add.append(FALLBACK_END)
    add.append(GETATTR_BLOCK)
    new_src = src.rstrip("\n") + "\n" + "\n".join(add) + "\n"

    ast.parse(new_src)  # refuse to write a syntax error
    state_py.write_text(new_src, encoding="utf-8")

    # Prove the two crash names exist and _lock is a Lock, not None.
    ns: dict = {}
    exec(compile(new_src, str(state_py), "exec"), ns, ns)
    lock = ns.get("_lock")
    rooms = ns.get("_rooms")
    lock_ok = type(lock).__name__ == "Lock"
    rooms_ok = isinstance(rooms, dict)
    return {
        "ok": True,
        "path": str(state_py),
        "referenced": len(referenced),
        "patched": len(missing),
        "lock_type": type(lock).__name__,
        "lock_ok": lock_ok,
        "rooms_type": type(rooms).__name__,
        "rooms_ok": rooms_ok,
        "has_outcome_sequence": "_outcome_sequence" in ns,
        "has_getattr": "__getattr__" in ns,
        "sample_missing_head": missing[:12],
    }


def ensure_runtime_maps(state_mod: object | None = None, *, silent: bool = False) -> dict:
    """Fill in missing/None maps on the live state module. Call at every boot.

    Only None or absent names are healed. A live dict/set/list/engine that the
    megafile already populated is left exactly as it is — retyping it is what
    killed the propose path.
    """
    if state_mod is None:
        try:
            import state as state_mod  # type: ignore
        except Exception as exc:
            return {"ok": False, "error": repr(exc)}
    healed: list[str] = []
    kept: list[str] = []
    for name in ALWAYS_DICT:
        cur = getattr(state_mod, name, _MISSING)
        if cur is _MISSING or cur is None:
            if name in NEVER_COERCE_AT_RUNTIME:
                continue
            setattr(state_mod, name, set() if name in SET_NAMES else {})
            healed.append(name)
        elif not isinstance(cur, dict):
            kept.append(f"{name}:{type(cur).__name__}")
    rooms = getattr(state_mod, "_rooms", None)
    ok = isinstance(rooms, dict)
    if healed or not silent:
        print(
            "[STATE-MAPS]",
            "OK" if ok else "FAIL",
            f"healed={healed or 'none'}",
            f"rooms={type(rooms).__name__}(n={len(rooms) if isinstance(rooms, dict) else '?'})",
            f"kept_live={kept or 'none'}",
        )
    return {"ok": ok, "healed": healed, "kept_live": kept}


def start_maps_sweep() -> None:
    """Megafile may assign `_rooms = None` after heal. Heal that, touch nothing else."""
    try:
        import threading
        import time

        def _loop() -> None:
            for d in (0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 40.0):
                time.sleep(d)
                try:
                    ensure_runtime_maps(silent=True)
                except Exception:
                    pass
            while True:
                time.sleep(15.0)
                try:
                    ensure_runtime_maps(silent=True)
                except Exception:
                    pass

        threading.Thread(target=_loop, name="lux_state_maps_sweep", daemon=True).start()
    except Exception:
        pass


def main() -> int:
    report = heal()
    if not report.get("ok"):
        print("STATE_HEAL_FAIL", report)
        return 2
    print(
        "STATE_HEAL_OK",
        f"patched={report['patched']}",
        f"referenced={report['referenced']}",
        f"lock={report['lock_type']}",
        f"rooms={report.get('rooms_type')}",
        f"getattr={int(report['has_getattr'])}",
        f"outcome_sequence={int(report['has_outcome_sequence'])}",
    )
    if report["sample_missing_head"]:
        print("STATE_HEAL_HEAD", report["sample_missing_head"])
    if not report["lock_ok"]:
        print("STATE_HEAL_WARN _lock is not asyncio.Lock — async with will still fail")
        return 1
    if not report.get("rooms_ok"):
        print("STATE_HEAL_WARN _rooms is not a dict — signal_handler .get() will crash")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
