#!/usr/bin/env python3
"""
zero_miss_ledger.py — never lose a winning opportunity silently.

Append-only JSONL ledger + summary report.
Every candidate should flow: sensed → proposed → routed → sent|held|blocked → resolved → truth.

A MISS is: at least one floor proposed (or blocked row later won) and chat never got it.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
LEDGER = DATA / "zero_miss_ledger.jsonl"
REPORT = DATA / "zero_miss_report.json"
_EXPORT_DB = Path("/workspace/replit_exports/db/bot/bacbo.db")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def append_event(event: dict[str, Any], path: Path = LEDGER) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    row = dict(event)
    row.setdefault("ts", _now())
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def record_proposal(
    *,
    signal_id: Any,
    floors: list[str],
    color: str,
    kind: str,
    lane: str,
    decision: str,
    reason: str = "",
) -> None:
    append_event(
        {
            "type": "proposal",
            "signal_id": signal_id,
            "floors": floors,
            "color": color,
            "kind": kind,
            "lane": lane,
            "decision": decision,  # SENT | HELD | BLOCKED | MERGED
            "reason": reason,
        }
    )


def record_resolve(
    *,
    signal_id: Any,
    outcome: str,
    predicted: str,
    actual: str,
    g0: bool = False,
) -> None:
    append_event(
        {
            "type": "resolve",
            "signal_id": signal_id,
            "outcome": outcome,
            "predicted": predicted,
            "actual": actual,
            "g0": g0,
        }
    )


def audit_db_misses(db_path: Path) -> dict[str, Any]:
    """Scan blocked_signals for wins that never became consensus fires (= capture leaks)."""
    if not db_path.exists():
        return {"error": f"no db {db_path}", "blocked_wins": [], "counts": {}}
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=60)
    conn.row_factory = sqlite3.Row
    blocked_wins = conn.execute(
        """
        SELECT id, signal_kind, color, source_floor, gate_reason, score, blocked_at, outcome
        FROM blocked_signals
        WHERE outcome='win'
        ORDER BY blocked_at DESC
        LIMIT 500
        """
    ).fetchall()
    blocked_losses = conn.execute(
        "SELECT COUNT(*) FROM blocked_signals WHERE outcome='loss'"
    ).fetchone()[0]
    blocked_total = conn.execute("SELECT COUNT(*) FROM blocked_signals").fetchone()[0]
    fired = conn.execute(
        "SELECT COUNT(*) FROM consensus_signals WHERE outcome IN ('win','loss','tie')"
    ).fetchone()[0]
    fired_wins = conn.execute(
        "SELECT COUNT(*) FROM consensus_signals WHERE outcome='win'"
    ).fetchone()[0]
    g0 = conn.execute(
        "SELECT COUNT(*) FROM consensus_signals WHERE outcome='win' AND COALESCE(won_at_gale,0)=0"
    ).fetchone()[0]

    # Group blocked wins by floor / reason
    by_floor: dict[str, int] = {}
    by_reason: dict[str, int] = {}
    rows = []
    for r in blocked_wins:
        fl = (r["source_floor"] or "UNATTRIBUTED").upper()
        reason = (r["gate_reason"] or "?")[:80]
        by_floor[fl] = by_floor.get(fl, 0) + 1
        by_reason[reason] = by_reason.get(reason, 0) + 1
        rows.append(
            {
                "id": r["id"],
                "kind": r["signal_kind"],
                "color": r["color"],
                "floor": fl,
                "gate_reason": reason,
                "blocked_at": r["blocked_at"],
                "score": r["score"],
            }
        )
        append_event(
            {
                "type": "db_blocked_win",
                "signal_id": r["id"],
                "floors": [fl],
                "color": r["color"],
                "kind": r["signal_kind"],
                "decision": "BLOCKED",
                "reason": reason,
                "outcome": "win",
                "miss": True,
            }
        )

    conn.close()
    miss_n = len(rows)
    capture_rate = (
        round(100.0 * fired_wins / (fired_wins + miss_n), 2) if (fired_wins + miss_n) else None
    )
    return {
        "generated_at": _now(),
        "db_path": str(db_path),
        "counts": {
            "fired_resolved": fired,
            "fired_wins": fired_wins,
            "fired_g0": g0,
            "blocked_total": blocked_total,
            "blocked_wins_misses": miss_n,
            "blocked_losses": blocked_losses,
            "win_capture_rate_pct": capture_rate,
        },
        "blocked_wins_by_floor": dict(sorted(by_floor.items(), key=lambda x: -x[1])),
        "blocked_wins_by_reason": dict(sorted(by_reason.items(), key=lambda x: -x[1])[:30]),
        "blocked_wins_sample": rows[:50],
        "law": "blocked_win = missed user-facing opportunity unless intentionally hard-blocked",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="")
    ap.add_argument("--out", default=str(REPORT))
    args = ap.parse_args()
    db = Path(args.db) if args.db else (HERE / "bacbo.db")
    if not db.exists() and _EXPORT_DB.exists():
        db = _EXPORT_DB
    report = audit_db_misses(db)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("[zero_miss] wrote", out)
    print("[zero_miss] counts", json.dumps(report.get("counts", {})))
    top = list((report.get("blocked_wins_by_floor") or {}).items())[:8]
    print("[zero_miss] top miss floors", top)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
