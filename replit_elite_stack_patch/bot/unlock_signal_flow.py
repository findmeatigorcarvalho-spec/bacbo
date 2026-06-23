"""
unlock_signal_flow.py - remove stale learned hour/schedule blockers.

Use this when the bot is connected and receiving Telegram messages but no new
signals are firing because old dynamic blocks/schedules are still active.

It backs up edited JSON files under bot/data/unlock_backups_<timestamp>/.
By default it clears:
  - accuracy_blocks.json suspended_kinds
  - accuracy_blocks.json blocked_hours
  - ai_learned_rules.json hour/day/post-loss block lists

It does not delete historical reports or DB rows.
"""
from __future__ import annotations

import argparse
import json
import shutil
import time
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(errors="ignore"))


def _save_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def _backup(path: Path, backup_dir: Path) -> None:
    backup_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, backup_dir / path.name)


def clear_accuracy_blocks(backup_dir: Path, dry_run: bool = False) -> list[str]:
    path = HERE / "accuracy_blocks.json"
    if not path.exists():
        return []
    data = _load_json(path)
    if not isinstance(data, dict):
        return []

    changed: list[str] = []
    for key in ("suspended_kinds", "blocked_hours"):
        if data.get(key):
            changed.append(f"{path.name}:{key}:{len(data.get(key, []))}")
            data[key] = []

    if changed and not dry_run:
        _backup(path, backup_dir)
        data["_disabled_by_unlock_signal_flow"] = "stale learned hour/kind blocks cleared; backup saved"
        data["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        _save_json(path, data)
    return changed


def clear_ai_learned_rules(backup_dir: Path, dry_run: bool = False) -> list[str]:
    path = HERE / "ai_learned_rules.json"
    if not path.exists():
        return []
    data = _load_json(path)
    if not isinstance(data, dict):
        return []

    keys_to_clear = [
        "hour_rules_golden",
        "hour_rules_solo_elite",
        "day_of_week_block",
        "post_loss_cooldown_signals",
    ]
    changed: list[str] = []
    for key in keys_to_clear:
        value = data.get(key)
        if value:
            size = len(value) if hasattr(value, "__len__") else 1
            changed.append(f"{path.name}:{key}:{size}")
            data[key] = [] if isinstance(value, list) else {}

    # Keep whitelists, triplets, and confidence boosts. Only neutralize block lists.
    if changed and not dry_run:
        _backup(path, backup_dir)
        data["_disabled_by_unlock_signal_flow"] = "stale learned schedule/hour blocks cleared; backup saved"
        data["generated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        _save_json(path, data)
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description="Clear stale learned hour/schedule blockers")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    backup_dir = HERE / "data" / f"unlock_backups_{int(time.time())}"
    changes = []
    changes.extend(clear_accuracy_blocks(backup_dir, dry_run=args.dry_run))
    changes.extend(clear_ai_learned_rules(backup_dir, dry_run=args.dry_run))

    print(json.dumps({
        "dry_run": args.dry_run,
        "backup_dir": str(backup_dir),
        "changes": changes,
        "restart_required": bool(changes and not args.dry_run),
        "note": "Restart bacbo_royal_complete.py after applying changes.",
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
