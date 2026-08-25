"""
early_source_audit.py — find HOW the bot appears to know results early.

This module audits timing and matching behavior.  It does not assume the early
edge is real.  It classifies every resolved signal by:

* instant:        secs_to_result < 1
* late_risk:      secs_to_result < 5
* fast:           5 <= secs_to_result < 20
* early_safe:     20 <= secs_to_result < 90
* stale_or_wrong: secs_to_result >= 90, null, or absurdly high

It also measures which kind/floor/room/color cells produce each timing class,
and flags likely matching artifacts:

* null timing but resolved
* very large secs_to_result
* high WR with sub-second result timing
* floors/kinds whose "edge" is mostly instant results

Output: bot/data/early_source_audit.json
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any


HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(HERE, "bacbo.db")
REPORT_PATH = os.path.join(HERE, "data", "early_source_audit.json")


@dataclass
class TimingCell:
    cell: str
    n: int
    wins: int
    losses: int
    ties: int
    wr: float | None
    avg_secs: float | None
    instant_n: int
    late_risk_n: int
    fast_n: int
    early_safe_n: int
    stale_or_wrong_n: int
    instant_pct: float
    early_safe_pct: float
    stale_or_wrong_pct: float
    diagnosis: str


def _connect(db_path: str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=30)
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


GROUPS = {
    "kind": "signal_kind",
    "floor": "COALESCE(source_floor,'LIVE')",
    "kind_floor": "signal_kind || ':' || COALESCE(source_floor,'LIVE')",
    "room": _first_room_expr(),
    "room_color": _first_room_expr() + " || ':' || color",
    "kind_floor_color": "signal_kind || ':' || COALESCE(source_floor,'LIVE') || ':' || color",
}


def _diagnosis(n: int, instant_pct: float, early_safe_pct: float, stale_pct: float, wr: float | None) -> str:
    if n < 20:
        return "INSUFFICIENT"
    if stale_pct >= 25:
        return "WRONG_ROUND_OR_STALE_RISK"
    if instant_pct >= 60 and (wr or 0) >= 80:
        return "INSTANT_MATCH_EDGE_OR_ARTIFACT"
    if early_safe_pct >= 30 and (wr or 0) >= 75:
        return "EARLY_SAFE_CANDIDATE"
    if instant_pct >= 40:
        return "MOSTLY_INSTANT_VERIFY"
    return "NORMAL_OR_MIXED"


def audit_group(
    db_path: str = DB_PATH,
    days: int = 9999,
    group_by: str = "kind_floor",
    min_n: int = 10,
) -> list[TimingCell]:
    expr = GROUPS[group_by]
    where = "" if days >= 9999 else "AND fired_at >= datetime('now', ?)"
    params = () if days >= 9999 else (f"-{int(days)} days",)
    sql = f"""
    SELECT {expr} cell,
           COUNT(*) n,
           SUM(outcome='win') wins,
           SUM(outcome='loss') losses,
           SUM(outcome='tie') ties,
           ROUND(100.0 * SUM(outcome='win') /
                 NULLIF(SUM(outcome IN ('win','loss')), 0), 2) wr,
           ROUND(AVG(secs_to_result), 2) avg_secs,
           SUM(secs_to_result IS NOT NULL AND secs_to_result < 1) instant_n,
           SUM(secs_to_result IS NOT NULL AND secs_to_result < 5) late_risk_n,
           SUM(secs_to_result IS NOT NULL AND secs_to_result >= 5 AND secs_to_result < 20) fast_n,
           SUM(secs_to_result IS NOT NULL AND secs_to_result >= 20 AND secs_to_result < 90) early_safe_n,
           SUM(secs_to_result IS NULL OR secs_to_result >= 90) stale_or_wrong_n
    FROM consensus_signals
    WHERE outcome IN ('win','loss','tie')
      {where}
      AND {expr} IS NOT NULL
      AND TRIM({expr}) <> ''
    GROUP BY cell
    HAVING n >= ?
    """
    with _connect(db_path) as conn:
        rows = conn.execute(sql, (*params, int(min_n))).fetchall()
    out: list[TimingCell] = []
    for row in rows:
        n = int(row["n"] or 0)
        instant_pct = round(100.0 * int(row["instant_n"] or 0) / max(n, 1), 2)
        early_safe_pct = round(100.0 * int(row["early_safe_n"] or 0) / max(n, 1), 2)
        stale_pct = round(100.0 * int(row["stale_or_wrong_n"] or 0) / max(n, 1), 2)
        wr = row["wr"]
        out.append(
            TimingCell(
                cell=row["cell"],
                n=n,
                wins=int(row["wins"] or 0),
                losses=int(row["losses"] or 0),
                ties=int(row["ties"] or 0),
                wr=wr,
                avg_secs=row["avg_secs"],
                instant_n=int(row["instant_n"] or 0),
                late_risk_n=int(row["late_risk_n"] or 0),
                fast_n=int(row["fast_n"] or 0),
                early_safe_n=int(row["early_safe_n"] or 0),
                stale_or_wrong_n=int(row["stale_or_wrong_n"] or 0),
                instant_pct=instant_pct,
                early_safe_pct=early_safe_pct,
                stale_or_wrong_pct=stale_pct,
                diagnosis=_diagnosis(n, instant_pct, early_safe_pct, stale_pct, wr),
            )
        )
    out.sort(key=lambda r: (
        r.diagnosis != "EARLY_SAFE_CANDIDATE",
        r.diagnosis != "INSTANT_MATCH_EDGE_OR_ARTIFACT",
        -r.wr if r.wr is not None else 999,
        -r.early_safe_pct,
        -r.instant_pct,
        -r.n,
    ))
    return out


def suspicious_examples(db_path: str = DB_PATH, days: int = 30, limit: int = 80) -> dict[str, list[dict[str, Any]]]:
    where = "" if days >= 9999 else "AND fired_at >= datetime('now', ?)"
    params = () if days >= 9999 else (f"-{int(days)} days",)
    first_room = _first_room_expr()
    with _connect(db_path) as conn:
        instant = [
            dict(r) for r in conn.execute(
                f"""
                SELECT id, fired_at, resolved_at, secs_to_result, outcome, signal_kind,
                       COALESCE(source_floor,'LIVE') source_floor, color, {first_room} room
                FROM consensus_signals
                WHERE outcome IN ('win','loss','tie')
                  {where}
                  AND secs_to_result IS NOT NULL AND secs_to_result < 1
                ORDER BY fired_at DESC
                LIMIT ?
                """,
                (*params, int(limit)),
            ).fetchall()
        ]
        stale = [
            dict(r) for r in conn.execute(
                f"""
                SELECT id, fired_at, resolved_at, secs_to_result, outcome, signal_kind,
                       COALESCE(source_floor,'LIVE') source_floor, color, {first_room} room
                FROM consensus_signals
                WHERE outcome IN ('win','loss','tie')
                  {where}
                  AND (secs_to_result IS NULL OR secs_to_result >= 90)
                ORDER BY fired_at DESC
                LIMIT ?
                """,
                (*params, int(limit)),
            ).fetchall()
        ]
    return {"instant_examples": instant, "stale_or_wrong_examples": stale}


def build_report(db_path: str = DB_PATH, days: int = 9999) -> dict[str, Any]:
    groups = {
        name: [asdict(cell) for cell in audit_group(db_path, days, name, min_n=20)[:80]]
        for name in GROUPS
    }
    # Count diagnosis totals over kind_floor_color because it is the most actionable.
    action_cells = audit_group(db_path, days, "kind_floor_color", min_n=20)
    diagnosis_counts: dict[str, int] = {}
    for cell in action_cells:
        diagnosis_counts[cell.diagnosis] = diagnosis_counts.get(cell.diagnosis, 0) + 1
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "days": int(days),
        "diagnosis_counts": diagnosis_counts,
        "groups": groups,
        "examples": suspicious_examples(db_path, days=30),
        "interpretation": {
            "instant": "May be true same-round fast confirmation OR after-result/matching artifact. Needs direct casino truth.",
            "early_safe": "20-90s timing: best current candidate for pre-result edge.",
            "stale_or_wrong": "Likely wrong-round, delayed, null timing, or long-running match artifact.",
        },
        "next_steps": [
            "Directly capture Twin225 round results to distinguish true early knowledge from matching artifacts.",
            "Only use EARLY_SAFE_CANDIDATE cells as possible early oracle candidates.",
            "Use INSTANT_MATCH_EDGE_OR_ARTIFACT cells in shadow until direct casino timing proves they are bettable.",
            "Do not trust cells whose WR depends mostly on stale_or_wrong timing.",
        ],
    }


def save_report(db_path: str = DB_PATH, days: int = 9999, path: str = REPORT_PATH) -> dict[str, Any]:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    report = build_report(db_path, days)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    os.replace(tmp, path)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit source of apparent early result edge")
    parser.add_argument("--db", default=DB_PATH)
    parser.add_argument("--days", type=int, default=9999)
    parser.add_argument("--report", default=REPORT_PATH)
    args = parser.parse_args()
    report = save_report(args.db, args.days, args.report)
    print(json.dumps(
        {
            "generated_at": report["generated_at"],
            "days": report["days"],
            "diagnosis_counts": report["diagnosis_counts"],
            "top_kind_floor": report["groups"]["kind_floor"][:20],
            "top_kind_floor_color": report["groups"]["kind_floor_color"][:20],
        },
        indent=2,
        ensure_ascii=False,
    ))
    print(f"report={args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
