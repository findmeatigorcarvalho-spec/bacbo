"""
hotfix_signal_handler.py - small runtime hotfixes for known handler crashes.

Current fix:
  - Prevent UnboundLocalError for `_remaining` in signal_handler.py when a
    candidate reaches DirectFire/post-hold logic without the accumulator branch
    initializing `_remaining`.

The script backs up bot/signal_handler.py before editing.
"""
from __future__ import annotations

import argparse
import shutil
import time
from pathlib import Path


HERE = Path(__file__).resolve().parent
SIGNAL_HANDLER = HERE / "signal_handler.py"


def patch_remaining(path: Path = SIGNAL_HANDLER, dry_run: bool = False) -> list[str]:
    if not path.exists():
        raise SystemExit(f"missing {path}")
    source = path.read_text(errors="ignore")
    changes: list[str] = []

    if "_remaining = 0.0  # hotfix default" in source:
        return changes

    fn_marker = "async def _on_message_inner(event):"
    if fn_marker in source:
        source = source.replace(
            fn_marker,
            fn_marker + "\n    _remaining = 0.0  # hotfix default; accumulator branch may overwrite",
            1,
        )
        changes.append("inserted _remaining default at _on_message_inner start")
    else:
        needle = "_post_hold_window = _remaining - _ACCUM_HOLD_SECS"
        if needle not in source:
            raise SystemExit("could not find _on_message_inner marker or _post_hold_window needle")
        source = source.replace(
            needle,
            "_remaining = locals().get('_remaining', 0.0)  # hotfix default\n    " + needle,
            1,
        )
        changes.append("inserted _remaining default before _post_hold_window")

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
    changes = patch_remaining(dry_run=args.dry_run)
    print({
        "dry_run": args.dry_run,
        "changes": changes,
        "restart_required": bool(changes and not args.dry_run),
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
