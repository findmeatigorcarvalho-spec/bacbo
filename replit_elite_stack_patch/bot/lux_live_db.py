"""Pick the live bacbo SQLite file that actually has consensus_signals.

telegram_outbox previously sorted candidate bacbo.db files by mtime and used
the newest. If anything created an empty sibling (sqlite3.connect on a missing
path creates a 0-row file), outbox then crashed with:

    OperationalError('no such table: consensus_signals')

and RESULT/FIRE delivery stopped even though the real history DB was still on
disk. This resolver scores candidates by schema + row count, never by mtime
alone, and never creates a new empty file as a side effect of looking.
"""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def _candidates() -> list[Path]:
    env = (os.environ.get("BACBO_DB") or os.environ.get("DB_PATH") or "").strip()
    out: list[Path] = []
    if env:
        out.append(Path(env))
    out.extend(
        [
            HERE / "bacbo.db",
            ROOT / "bacbo.db",
            HERE / "data" / "bacbo.db",
            Path("/home/runner/workspace/bot/bacbo.db"),
            Path("/home/runner/workspace/bacbo.db"),
            Path("/home/runner/workspace/bot/data/bacbo.db"),
        ]
    )
    seen: set[str] = set()
    uniq: list[Path] = []
    for p in out:
        try:
            key = str(p.resolve()) if p.exists() else str(p)
        except Exception:
            key = str(p)
        if key in seen:
            continue
        seen.add(key)
        uniq.append(p)
    return uniq


def _score(path: Path) -> dict[str, Any]:
    info: dict[str, Any] = {
        "path": str(path),
        "exists": False,
        "size": 0,
        "has_consensus": False,
        "n_consensus": 0,
        "max_id": None,
        "max_fired": None,
        "error": None,
    }
    try:
        if not path.is_file():
            return info
        info["exists"] = True
        info["size"] = int(path.stat().st_size)
        if info["size"] < 64:
            info["error"] = "too_small"
            return info
        try:
            conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=8)
        except Exception as exc:
            info["error"] = repr(exc)
            return info
        try:
            tables = {
                r[0]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            if "consensus_signals" not in tables:
                info["error"] = "no_consensus_signals_table"
                info["tables"] = sorted(tables)[:20]
                return info
            info["has_consensus"] = True
            row = conn.execute(
                "SELECT COUNT(*), MAX(id), MAX(fired_at) FROM consensus_signals"
            ).fetchone()
            info["n_consensus"] = int(row[0] or 0)
            info["max_id"] = row[1]
            info["max_fired"] = row[2]
        finally:
            conn.close()
    except Exception as exc:
        info["error"] = repr(exc)
    return info


def resolve_db(*, log: bool = True) -> Path:
    scored = [_score(p) for p in _candidates()]
    viable = [s for s in scored if s.get("has_consensus")]
    viable.sort(key=lambda s: (int(s["n_consensus"]), int(s["size"])), reverse=True)
    if log:
        for s in scored:
            flag = "LIVE" if viable and s["path"] == viable[0]["path"] else "skip"
            print(
                f"[LIVE-DB] {flag} {s['path']} size={s['size']} "
                f"consensus={s['n_consensus']} max_id={s['max_id']} "
                f"max_fired={s['max_fired']} err={s['error']}"
            )
    if viable:
        return Path(viable[0]["path"])
    existing = [s for s in scored if s.get("exists")]
    existing.sort(key=lambda s: int(s["size"]), reverse=True)
    if existing:
        return Path(existing[0]["path"])
    return HERE / "bacbo.db"


def diagnose() -> list[dict[str, Any]]:
    return [_score(p) for p in _candidates()]


if __name__ == "__main__":
    picked = resolve_db(log=True)
    print("LIVE_DB", picked)
