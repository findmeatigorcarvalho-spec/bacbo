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
import sqlite3
import time
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
DB_PATH = HERE / "bacbo.db"


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(errors="ignore"))


def _save_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def _backup(path: Path, backup_dir: Path) -> None:
    backup_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, backup_dir / path.name)


def _clear_blockish_keys(data: Any) -> tuple[Any, list[str]]:
    """Clear nested JSON keys that represent stale hour/schedule blockers."""
    changed: list[str] = []
    block_key_parts = (
        "autochb",
        "auto_chb",
        "dynamic_block",
        "dynamic_blocks",
        "blocked_hour",
        "blocked_hours",
        "bad_hour",
        "bad_hours",
        "hour_block",
        "hour_blocks",
        "suspended_kind",
        "suspended_kinds",
    )

    def walk(obj: Any, path: str = "") -> Any:
        if isinstance(obj, dict):
            out = {}
            for key, value in obj.items():
                lk = str(key).lower()
                current = f"{path}.{key}" if path else str(key)
                if any(part in lk for part in block_key_parts):
                    if value:
                        size = len(value) if hasattr(value, "__len__") else 1
                        changed.append(f"{current}:{size}")
                    out[key] = [] if isinstance(value, list) else {} if isinstance(value, dict) else None
                else:
                    out[key] = walk(value, current)
            return out
        if isinstance(obj, list):
            return [walk(item, f"{path}[]") for item in obj]
        return obj

    return walk(data), changed


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


def clear_deep_json_blocks(backup_dir: Path, dry_run: bool = False) -> list[str]:
    changed: list[str] = []
    candidates = list(HERE.glob("*.json")) + list((HERE / "data").glob("*.json"))
    skip_names = {
        "edge_whitelist_engine.json",
        "skyscraper_floor_factory_report.json",
        "skyscraper_stack_report.json",
        "floor_stack_registry_report.json",
        "legacy_peak_355_report.json",
        "system_health_audit.json",
        "volume_frontier_report.json",
        "truth_verification_report.json",
        "martingale_audit.json",
    }
    for path in candidates:
        if path.name in skip_names:
            continue
        try:
            data = _load_json(path)
        except Exception:
            continue
        new_data, sub_changes = _clear_blockish_keys(data)
        if not sub_changes:
            continue
        changed.extend([f"{path.name}:{item}" for item in sub_changes])
        if not dry_run:
            _backup(path, backup_dir)
            if isinstance(new_data, dict):
                new_data["_disabled_by_unlock_signal_flow_deep"] = "nested stale hour/schedule blockers cleared; backup saved"
            _save_json(path, new_data)
    return changed


def clear_bot_state_blocks(backup_dir: Path, dry_run: bool = False) -> list[str]:
    if not DB_PATH.exists():
        return []
    changed: list[str] = []
    keys = [
        "blocked_hours_json",
        "auto_chb_blocks",
        "autochb_blocks",
        "dynamic_blocks",
        "bad_hours",
        "suspended_kinds",
    ]
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='bot_state'"
        ).fetchone()
        if not exists:
            return []
        rows = conn.execute(
            "SELECT key, value FROM bot_state WHERE lower(key) LIKE '%block%' OR lower(key) LIKE '%hour%' OR lower(key) LIKE '%suspend%'"
        ).fetchall()
        backup_path = backup_dir / "bot_state_block_keys.json"
        to_clear = []
        for row in rows:
            key = str(row["key"])
            lower = key.lower()
            if key in keys or "blocked_hour" in lower or "dynamic_block" in lower or "autochb" in lower or "auto_chb" in lower:
                to_clear.append({"key": key, "value": row["value"]})
                changed.append(f"bot_state:{key}")
        if to_clear and not dry_run:
            backup_dir.mkdir(parents=True, exist_ok=True)
            backup_path.write_text(json.dumps(to_clear, indent=2, ensure_ascii=False) + "\n")
            for item in to_clear:
                conn.execute("UPDATE bot_state SET value=? WHERE key=?", ("[]", item["key"]))
            conn.commit()
    except Exception as exc:
        changed.append(f"bot_state_error:{exc}")
    finally:
        try:
            conn.close()
        except Exception:
            pass
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description="Clear stale learned hour/schedule blockers")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    backup_dir = HERE / "data" / f"unlock_backups_{int(time.time())}"
    changes = []
    changes.extend(clear_accuracy_blocks(backup_dir, dry_run=args.dry_run))
    changes.extend(clear_ai_learned_rules(backup_dir, dry_run=args.dry_run))
    changes.extend(clear_deep_json_blocks(backup_dir, dry_run=args.dry_run))
    changes.extend(clear_bot_state_blocks(backup_dir, dry_run=args.dry_run))

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
