"""
early_result_audit.py — prove whether signals arrive before the live round result.

This does NOT claim an oracle exists. It measures timing from the data already
stored in ``consensus_signals``:

* fired_at      — when the bot fired the signal
* resolved_at   — when the bot matched the result
* secs_to_result — measured time between fire and resolution

The key buckets:
* oracle_safe: secs_to_result >= 20s  (enough time to plausibly bet before result)
* fast:        5s <= secs_to_result < 20s
* late_risk:   secs_to_result < 5s    (could be after/at-result, needs caution)

Use this report to identify which floors/kinds/rooms have true timing edge.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Optional


HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(HERE, "bacbo.db")
REPORT_PATH = os.path.join(HERE, "data", "early_result_audit.json")


ORACLE_SAFE_SECS = 20.0
FAST_SECS = 5.0


@dataclass
class TimingCell:
    group_key: str
    n: int
    wins: int
    losses: int
    ties: int
    wr: Optional[float]
    avg_secs: Optional[float]
    min_secs: Optional[float]
    max_secs: Optional[float]
    oracle_safe_n: int
    fast_n: int
    late_risk_n: int
    oracle_safe_pct: float


def _connect(db_path: str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=20)
    conn.row_factory = sqlite3.Row
    return conn


def _first_room_expr() -> str:
    return """
    lower(replace(
      CASE
        WHEN instr(coalesce(rooms_agreed,''), ',') > 0
        THEN substr(rooms_agreed, 1, instr(rooms_agreed, ',') - 1)
        ELSE coalesce(rooms_agreed, '')
      END, '@', ''))
    """


def _group_expr(group_by: str) -> str:
    first_room = _first_room_expr()
    if group_by == "kind":
        return "signal_kind"
    if group_by == "floor":
        return "COALESCE(source_floor,'LIVE')"
    if group_by == "room":
        return first_room
    if group_by == "color":
        return "color"
    if group_by == "kind_floor":
        return "signal_kind || ':' || COALESCE(source_floor,'LIVE')"
    if group_by == "room_color":
        return f"{first_room} || ':' || color"
    raise ValueError(f"unsupported group_by: {group_by}")


def timing_cells(
    db_path: str = DB_PATH,
    days: int = 7,
    group_by: str = "kind_floor",
    min_n: int = 10,
) -> list[TimingCell]:
    expr = _group_expr(group_by)
    query = f"""
    SELECT {expr} AS group_key,
           COUNT(*) n,
           SUM(outcome='win') wins,
           SUM(outcome='loss') losses,
           SUM(outcome='tie') ties,
           ROUND(100.0 * SUM(outcome='win') /
                 NULLIF(SUM(outcome IN ('win','loss')), 0), 1) wr,
           ROUND(AVG(secs_to_result), 1) avg_secs,
           ROUND(MIN(secs_to_result), 1) min_secs,
           ROUND(MAX(secs_to_result), 1) max_secs,
           SUM(secs_to_result >= ?) oracle_safe_n,
           SUM(secs_to_result >= ? AND secs_to_result < ?) fast_n,
           SUM(secs_to_result < ?) late_risk_n
    FROM consensus_signals
    WHERE fired_at >= datetime('now', ?)
      AND outcome IN ('win','loss','tie')
      AND secs_to_result IS NOT NULL
      AND {expr} IS NOT NULL
      AND TRIM({expr}) <> ''
    GROUP BY group_key
    HAVING n >= ?
    ORDER BY oracle_safe_n DESC, wr DESC, n DESC
    """
    params = (
        ORACLE_SAFE_SECS,
        FAST_SECS,
        ORACLE_SAFE_SECS,
        FAST_SECS,
        f"-{int(days)} days",
        int(min_n),
    )
    with _connect(db_path) as conn:
        rows = conn.execute(query, params).fetchall()
    out: list[TimingCell] = []
    for row in rows:
        n = int(row["n"] or 0)
        oracle_safe_n = int(row["oracle_safe_n"] or 0)
        out.append(
            TimingCell(
                group_key=row["group_key"],
                n=n,
                wins=int(row["wins"] or 0),
                losses=int(row["losses"] or 0),
                ties=int(row["ties"] or 0),
                wr=row["wr"],
                avg_secs=row["avg_secs"],
                min_secs=row["min_secs"],
                max_secs=row["max_secs"],
                oracle_safe_n=oracle_safe_n,
                fast_n=int(row["fast_n"] or 0),
                late_risk_n=int(row["late_risk_n"] or 0),
                oracle_safe_pct=round(100.0 * oracle_safe_n / max(n, 1), 1),
            )
        )
    return out


def overall(db_path: str = DB_PATH, days: int = 7) -> dict:
    with _connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) n,
                   SUM(outcome='win') wins,
                   SUM(outcome='loss') losses,
                   SUM(outcome='tie') ties,
                   ROUND(100.0 * SUM(outcome='win') /
                         NULLIF(SUM(outcome IN ('win','loss')), 0), 1) wr,
                   ROUND(AVG(secs_to_result), 1) avg_secs,
                   ROUND(MIN(secs_to_result), 1) min_secs,
                   ROUND(MAX(secs_to_result), 1) max_secs,
                   SUM(secs_to_result >= ?) oracle_safe_n,
                   SUM(secs_to_result >= ? AND secs_to_result < ?) fast_n,
                   SUM(secs_to_result < ?) late_risk_n
            FROM consensus_signals
            WHERE fired_at >= datetime('now', ?)
              AND outcome IN ('win','loss','tie')
              AND secs_to_result IS NOT NULL
            """,
            (ORACLE_SAFE_SECS, FAST_SECS, ORACLE_SAFE_SECS, FAST_SECS, f"-{int(days)} days"),
        ).fetchone()
    n = int(row["n"] or 0)
    safe = int(row["oracle_safe_n"] or 0)
    return {
        "days": int(days),
        "n": n,
        "wins": int(row["wins"] or 0),
        "losses": int(row["losses"] or 0),
        "ties": int(row["ties"] or 0),
        "wr": row["wr"],
        "avg_secs": row["avg_secs"],
        "min_secs": row["min_secs"],
        "max_secs": row["max_secs"],
        "oracle_safe_n": safe,
        "oracle_safe_pct": round(100.0 * safe / max(n, 1), 1),
        "fast_n": int(row["fast_n"] or 0),
        "late_risk_n": int(row["late_risk_n"] or 0),
        "thresholds": {
            "oracle_safe_secs": ORACLE_SAFE_SECS,
            "fast_secs": FAST_SECS,
        },
    }


def save_report(
    db_path: str = DB_PATH,
    days: int = 7,
    group_by: str = "kind_floor",
    min_n: int = 10,
    path: str = REPORT_PATH,
) -> dict:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    cells = timing_cells(db_path=db_path, days=days, group_by=group_by, min_n=min_n)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "overall": overall(db_path=db_path, days=days),
        "group_by": group_by,
        "min_n": min_n,
        "cells": [asdict(cell) for cell in cells],
    }
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    os.replace(tmp, path)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit early-result timing edge")
    parser.add_argument("--db", default=DB_PATH)
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument(
        "--group-by",
        default="kind_floor",
        choices=["kind", "floor", "room", "color", "kind_floor", "room_color"],
    )
    parser.add_argument("--min-n", type=int, default=10)
    parser.add_argument("--report", default=REPORT_PATH)
    args = parser.parse_args()
    report = save_report(
        db_path=args.db,
        days=args.days,
        group_by=args.group_by,
        min_n=args.min_n,
        path=args.report,
    )
    print(json.dumps(
        {
            "generated_at": report["generated_at"],
            "overall": report["overall"],
            "group_by": report["group_by"],
            "cells": len(report["cells"]),
            "top_cells": report["cells"][:10],
        },
        indent=2,
        ensure_ascii=False,
    ))
    print(f"report={args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
