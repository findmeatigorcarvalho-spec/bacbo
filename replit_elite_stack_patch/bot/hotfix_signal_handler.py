"""
hotfix_signal_handler.py - small runtime hotfixes for known handler crashes.

Current fixes:
  - Prevent UnboundLocalError for `_remaining` in signal_handler.py
  - Guard `state._rooms.get(...)` when `_rooms` is None
"""
from __future__ import annotations

import argparse
import re
import shutil
import time
from pathlib import Path


HERE = Path(__file__).resolve().parent
SIGNAL_HANDLER = HERE / "signal_handler.py"


def patch_rooms(path: Path = SIGNAL_HANDLER, dry_run: bool = False) -> list[str]:
    """state._rooms was None → AttributeError on .get(chat_id). Tolerate None."""
    if not path.exists():
        return ["missing signal_handler.py"]
    source = path.read_text(encoding="utf-8", errors="replace")
    changes: list[str] = []
    new = source
    guard = "(state._rooms if isinstance(getattr(state, '_rooms', None), dict) else {}).get("
    if "state._rooms.get(" in new and guard not in new:
        new, n = re.subn(r"state\._rooms\.get\(", guard, new)
        if n:
            changes.append(f"rooms_get_guard={n}")
    if re.search(r"state\._rooms\s*=\s*None", new):
        new, n = re.subn(r"state\._rooms\s*=\s*None", "state._rooms = {}", new)
        if n:
            changes.append(f"rooms_none_to_dict={n}")
    if changes and new != source and not dry_run:
        backup = path.with_suffix(path.suffix + f".bak_rooms_{int(time.time())}")
        shutil.copy2(path, backup)
        path.write_text(new, encoding="utf-8")
        changes.append(f"backup={backup}")
    return changes


def patch_remaining(path: Path = SIGNAL_HANDLER, dry_run: bool = False) -> list[str]:
    if not path.exists():
        return ["missing signal_handler.py"]
    source = path.read_text(errors="ignore")
    changes: list[str] = []

    if "_remaining = locals().get('_remaining', 0.0)  # hotfix default" in source:
        return changes

    lines = [
        line for line in source.splitlines()
        if "_remaining = 0.0  # hotfix default" not in line
    ]

    needle = "_post_hold_window = _remaining - _ACCUM_HOLD_SECS"
    out: list[str] = []
    inserted = False
    for line in lines:
        if not inserted and needle in line:
            indent = line[:len(line) - len(line.lstrip())]
            out.append(f"{indent}_remaining = locals().get('_remaining', 0.0)  # hotfix default")
            inserted = True
            changes.append("inserted _remaining default before _post_hold_window")
        out.append(line)

    if not inserted:
        return changes
    source = "\n".join(out) + "\n"

    if changes and not dry_run:
        backup = path.with_suffix(path.suffix + f".bak_hotfix_{int(time.time())}")
        shutil.copy2(path, backup)
        path.write_text(source)
        changes.append(f"backup={backup}")
    return changes


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply signal_handler hotfixes")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    rooms = patch_rooms(dry_run=args.dry_run)
    remaining = patch_remaining(dry_run=args.dry_run)
    print({
        "dry_run": args.dry_run,
        "rooms": rooms,
        "remaining": remaining,
        "restart_required": bool((rooms or remaining) and not args.dry_run),
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
