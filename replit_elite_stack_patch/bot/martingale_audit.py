"""
martingale_audit.py — audit G0/G1/G2/G3 recovery value.

This report answers:
* how often G0 wins
* how much G1/G2/G3 actually recover
* which rooms/kinds/floors should allow martingale
* where martingale should be blocked or inverted/shadow-tested

Read-only. Writes bot/data/martingale_audit.json.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone


HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(HERE, "bacbo.db")
REPORT_PATH = os.path.join(HERE, "data", "martingale_audit.json")


@dataclass
class GaleCell:
    key: str
    total: int
    g0: int
    g1: int
    g2: int
    g3: int
    losses: int
    ties: int
    g0_wr: float
    final_wr: float
    recovery_wr: float
    verdict: str


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
    if group_by == "overall":
        return "'overall'"
    if group_by == "room":
        return first_room
    if group_by == "kind":
        return "signal_kind"
    if group_by == "floor":
        return "COALESCE(source_floor,'LIVE')"
    if group_by == "room_color":
        return f"{first_room} || ':' || color"
    if group_by == "kind_floor":
        return "signal_kind || ':' || COALESCE(source_floor,'LIVE')"
    raise ValueError(f"unsupported group_by: {group_by}")


def _verdict(total: int, recovery_wr: float, final_wr: float) -> str:
    if total < 20:
        return "INSUFFICIENT"
    if recovery_wr >= 45.0 and final_wr >= 78.0:
        return "ALLOW_MARTINGALE"
    if recovery_wr >= 35.0 and final_wr >= 72.0:
        return "SHADOW_MARTINGALE"
    return "G0_ONLY_OR_BLOCK"


def audit_group(
    db_path: str = DB_PATH,
    days: int = 7,
    group_by: str = "room",
    min_n: int = 10,
) -> list[GaleCell]:
    expr = _group_expr(group_by)
    query = f"""
    SELECT {expr} AS key,
           COUNT(*) total,
           SUM(outcome='win' AND COALESCE(won_at_gale,0)=0) g0,
           SUM(outcome='win' AND COALESCE(won_at_gale,0)=1) g1,
           SUM(outcome='win' AND COALESCE(won_at_gale,0)=2) g2,
           SUM(outcome='win' AND COALESCE(won_at_gale,0)>=3) g3,
           SUM(outcome='loss') losses,
           SUM(outcome='tie') ties
    FROM consensus_signals
    WHERE fired_at >= datetime('now', ?)
      AND outcome IN ('win','loss','tie')
      AND {expr} IS NOT NULL
      AND TRIM({expr}) <> ''
    GROUP BY key
    HAVING total >= ?
    """
    with _connect(db_path) as conn:
        rows = conn.execute(query, (f"-{int(days)} days", int(min_n))).fetchall()

    cells: list[GaleCell] = []
    for row in rows:
        total = int(row["total"] or 0)
        g0 = int(row["g0"] or 0)
        g1 = int(row["g1"] or 0)
        g2 = int(row["g2"] or 0)
        g3 = int(row["g3"] or 0)
        losses = int(row["losses"] or 0)
        ties = int(row["ties"] or 0)
        non_tie = g0 + g1 + g2 + g3 + losses
        recovery_denom = g1 + g2 + g3 + losses
        g0_wr = round(100.0 * g0 / max(non_tie, 1), 2)
        final_wr = round(100.0 * (g0 + g1 + g2 + g3) / max(non_tie, 1), 2)
        recovery_wr = round(100.0 * (g1 + g2 + g3) / max(recovery_denom, 1), 2)
        cells.append(
            GaleCell(
                key=row["key"],
                total=total,
                g0=g0,
                g1=g1,
                g2=g2,
                g3=g3,
                losses=losses,
                ties=ties,
                g0_wr=g0_wr,
                final_wr=final_wr,
                recovery_wr=recovery_wr,
                verdict=_verdict(total, recovery_wr, final_wr),
            )
        )
    cells.sort(key=lambda c: (c.verdict != "ALLOW_MARTINGALE", -c.final_wr, -c.recovery_wr, -c.total))
    return cells


def save_report(db_path: str = DB_PATH, days: int = 7, path: str = REPORT_PATH) -> dict:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    overall = audit_group(db_path, days, "overall", 1)[0]
    by_room = audit_group(db_path, days, "room", 20)
    by_kind = audit_group(db_path, days, "kind", 20)
    by_floor = audit_group(db_path, days, "floor", 20)
    by_room_color = audit_group(db_path, days, "room_color", 15)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "days": int(days),
        "overall": asdict(overall),
        "by_room": [asdict(c) for c in by_room],
        "by_kind": [asdict(c) for c in by_kind],
        "by_floor": [asdict(c) for c in by_floor],
        "by_room_color": [asdict(c) for c in by_room_color],
        "rules": {
            "ALLOW_MARTINGALE": "recovery_wr>=45 and final_wr>=78",
            "SHADOW_MARTINGALE": "recovery_wr>=35 and final_wr>=72",
            "G0_ONLY_OR_BLOCK": "martingale not adding enough recovery edge",
        },
    }
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    os.replace(tmp, path)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit Bac Bo martingale recovery")
    parser.add_argument("--db", default=DB_PATH)
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--report", default=REPORT_PATH)
    args = parser.parse_args()
    report = save_report(args.db, args.days, args.report)
    print(json.dumps(
        {
            "generated_at": report["generated_at"],
            "days": report["days"],
            "overall": report["overall"],
            "top_rooms": report["by_room"][:10],
            "top_room_color": report["by_room_color"][:10],
        },
        indent=2,
        ensure_ascii=False,
    ))
    print(f"report={args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
