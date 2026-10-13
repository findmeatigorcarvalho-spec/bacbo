"""
hotfix_signal_flow_dampers.py - disable stale score dampers that suppress flow.

Use after unlock_signal_flow.py when the bot is receiving Telegram messages and
reaches "► Signal kind=..." but no Telegram/website signal is sent because old
hour/danger/probation/weak-trap dampers drag the score down.

This is a source patcher for the live Replit bot/signal_handler.py. It backs up
the file and applies conservative text patches around known log signatures:
  - [GameCoach] Blocked-hour card
  - [Rev6.4.3.1] DAMP
  - [DangerZone/DF]
  - [Probation] Capping
  - [PairIntel/DF] WeakTrap penalty
"""
from __future__ import annotations

import argparse
import shutil
import time
from pathlib import Path


HERE = Path(__file__).resolve().parent
SIGNAL_HANDLER = HERE / "signal_handler.py"


def _line_indent(line: str) -> str:
    return line[:len(line) - len(line.lstrip())]


def _comment_block_around(lines: list[str], idx: int, label: str) -> tuple[list[str], bool]:
    """Disable a small local statement block by wrapping it in if False."""
    if idx < 0 or idx >= len(lines):
        return lines, False
    indent = _line_indent(lines[idx])
    start = idx
    # Back up to the start of the local block/comment group.
    while start > 0:
        prev = lines[start - 1]
        if not prev.strip():
            break
        if _line_indent(prev) != indent:
            break
        if prev.lstrip().startswith(("log.", "if ", "score", "total", "trust", "effective", "raw", "_")):
            start -= 1
            continue
        break

    end = idx + 1
    while end < len(lines):
        cur = lines[end]
        if not cur.strip():
            break
        cur_indent = _line_indent(cur)
        if len(cur_indent) < len(indent):
            break
        # Keep the disabled patch tight; do not consume huge branches.
        if end - start > 12:
            break
        end += 1

    block = lines[start:end]
    if any(f"hotfix disabled {label}" in line for line in block):
        return lines, False
    replacement = [
        f"{indent}if False:  # hotfix disabled {label}",
        *[f"{indent}    {line[len(indent):]}" if line.startswith(indent) else f"{indent}    {line}" for line in block],
    ]
    return lines[:start] + replacement + lines[end:], True


def patch_dampers(path: Path = SIGNAL_HANDLER, dry_run: bool = False) -> list[str]:
    if not path.exists():
        raise SystemExit(f"missing {path}")
    source = path.read_text(errors="ignore")
    lines = source.splitlines()
    changes: list[str] = []

    signatures = [
        ("blocked_hour_card", "[GameCoach] Blocked-hour card"),
        ("rev6431_damp", "[Rev6.4.3.1] DAMP"),
        ("danger_zone", "[DangerZone/DF]"),
        ("probation_cap", "[Probation] Capping"),
        ("weaktrap_penalty", "WeakTrap penalty"),
    ]

    for label, sig in signatures:
        # Repeat because disabling one block shifts later indices.
        idx = next((i for i, line in enumerate(lines) if sig in line and f"hotfix disabled {label}" not in line), -1)
        if idx == -1:
            continue
        lines, changed = _comment_block_around(lines, idx, label)
        if changed:
            changes.append(label)

    if changes and not dry_run:
        backup = path.with_suffix(path.suffix + f".bak_damper_hotfix_{int(time.time())}")
        shutil.copy2(path, backup)
        path.write_text("\n".join(lines) + "\n")
        changes.append(f"backup={backup}")
    return changes


def main() -> int:
    parser = argparse.ArgumentParser(description="Disable stale DirectFire dampers in signal_handler.py")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    changes = patch_dampers(dry_run=args.dry_run)
    print({
        "dry_run": args.dry_run,
        "changes": changes,
        "restart_required": bool(changes and not args.dry_run),
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
