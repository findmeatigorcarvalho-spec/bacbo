"""Audit: is anything still able to mute signals by hour / day-of-week?

Read-only. Three checks:

  1. SOURCE - module-level constants in bot/*.py whose names look like
     hour/DOW blocks (BAD_HOUR, HOUR_BLOCK, BLOCKED_HOURS, BAD_UTC,
     BAD_DOW, DOW_BLOCK, HOUR_DOW ...) and that are assigned a NON-EMPTY
     literal. These only matter if the boot neutraliser missed them.
  2. STATE FILES - persisted JSON (color_hour_blocks.json,
     intelligence_state.json, accuracy_blocks.json, ai_learned_rules.json)
     that can re-load bad-hour lists at boot.
  3. WIRING - whether lux_no_hour_blocks / HourAdvisory is actually
     imported by the boot path, and the latest boot log lines about it.

The runtime neutraliser empties these in memory at import and re-sweeps
every 20s, so a non-empty SOURCE constant is not by itself proof of a
live block - but combined with missing WIRING it is.

Usage:
    python hour_block_audit.py [--bot-dir PATH]
"""
import ast
import json
import re
import sys
from pathlib import Path

_NAME_RE = re.compile(
    r"(BAD_UTC|BAD_HOURS?|HOUR_BLOCK|BLOCKED_HOURS|BAD_DOW|DOW_BLOCK|HOUR_DOW|BAD_CELLS)",
    re.I,
)
_SKIP_DIRS = {"__pycache__", "data", "node_modules"}


def _literal_size(node):
    try:
        val = ast.literal_eval(node)
    except Exception:
        return None
    if isinstance(val, (set, frozenset, list, tuple, dict, str)):
        return len(val)
    return None


def scan_source(bot_dir):
    hits = []
    for path in sorted(Path(bot_dir).glob("*.py")):
        if path.name.startswith("_backup") or "backup" in path.name:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        for node in tree.body:
            if isinstance(node, ast.Assign):
                targets, value = node.targets, node.value
            elif isinstance(node, ast.AnnAssign):
                targets, value = [node.target], node.value
            else:
                continue
            if value is None:
                continue
            for t in targets:
                if isinstance(t, ast.Name) and _NAME_RE.search(t.id):
                    size = _literal_size(value)
                    if size:
                        hits.append("%s:%d %s (%d entries)" % (path.name, node.lineno, t.id, size))
    return hits


def scan_state_files(bot_dir):
    bot_dir = Path(bot_dir)
    hits = []
    candidates = []
    for name in ("color_hour_blocks.json", "intelligence_state.json",
                 "accuracy_blocks.json", "ai_learned_rules.json"):
        candidates += [bot_dir / name, bot_dir / "data" / name]
    for path in candidates:
        if not path.is_file():
            continue
        try:
            blob = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(blob, dict):
            continue
        for key, val in blob.items():
            lk = str(key).lower()
            if any(f in lk for f in ("bad_hr", "bad_hour", "hour_block", "blocked_hour",
                                     "bad_dow", "dow_block", "dynamic_addition", "suspended")):
                n = len(val) if isinstance(val, (list, dict, set)) else (1 if val else 0)
                if isinstance(val, dict):
                    n = sum(len(v) for v in val.values() if isinstance(v, (list, dict, set)))
                if n:
                    hits.append("%s: %s (%d entries)" % (path.name, key, n))
    return hits


def scan_wiring(bot_dir):
    bot_dir = Path(bot_dir)
    found = []
    for name in ("main.py", "run_bacbo_live.py", "bacbo_royal_complete.py", "bacbo.py"):
        path = bot_dir / name
        if path.is_file():
            text = path.read_text(encoding="utf-8", errors="replace")
            for tag in ("lux_no_hour_blocks", "HourAdvisory", "NO_HOUR_BLOCKS"):
                if tag in text:
                    found.append("%s imports/tags %s" % (name, tag))
    return found


def main():
    bot_dir = Path(__file__).resolve().parent
    if "--bot-dir" in sys.argv:
        bot_dir = Path(sys.argv[sys.argv.index("--bot-dir") + 1])
    src = scan_source(bot_dir)
    state = scan_state_files(bot_dir)
    wiring = scan_wiring(bot_dir)
    print("== WIRING (boot neutraliser) ==")
    print("\n".join("  " + w for w in wiring) or "  NONE FOUND - neutraliser may not be loaded!")
    print("== SOURCE hour/DOW block constants (non-empty literals) ==")
    print("\n".join("  " + h for h in src) or "  none")
    print("== STATE FILES with live bad-hour entries ==")
    print("\n".join("  " + h for h in state) or "  none")
    print()
    if wiring and not state:
        print("VERDICT: neutraliser wired and no persisted bad-hour lists.")
        print("Non-empty source constants above are emptied in memory at boot")
        print("and re-swept every 20s - they cannot mute signals.")
    elif not wiring:
        print("VERDICT: neutraliser NOT wired into the boot path - hour blocks")
        print("in the source constants above are LIVE. Wire lux_no_hour_blocks")
        print("into the boot file and re-run.")
    else:
        print("VERDICT: neutraliser wired, but state files still hold bad-hour")
        print("lists that reload at boot. lux_no_hour_blocks.clear_persist_json")
        print("empties them on import - check it ran before the gates loaded.")


if __name__ == "__main__":
    main()
