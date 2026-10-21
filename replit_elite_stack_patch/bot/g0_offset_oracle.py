"""
g0_offset_oracle.py — mine future-round edges after G0 wins.

User hypothesis:
    Some G0 WIN signals predict not only the current hit, but the colour a few
    resolved outcomes later.  Example: G0 WIN BLUE may imply BLUE around the
    3rd future outcome.

This module turns that into measured cells:
    signal_kind + source_floor + signal_color + offset -> match %

It is read-only and writes bot/data/g0_offset_oracle_report.json.
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
REPORT_PATH = os.path.join(HERE, "data", "g0_offset_oracle_report.json")
OPP = {"blue": "red", "red": "blue"}


@dataclass
class OffsetCell:
    signal_kind: str
    source_floor: str
    color: str
    offset: int
    n: int
    match_count: int
    opposite_count: int
    tie_count: int
    match_pct: float
    opposite_pct: float
    tie_pct: float
    quality: str


def _connect(db_path: str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def _actual(signal_color: str, outcome: str) -> Optional[str]:
    signal_color = (signal_color or "").lower()
    outcome = (outcome or "").lower()
    if outcome == "tie":
        return "tie"
    if signal_color not in OPP:
        return None
    if outcome == "win":
        return signal_color
    if outcome == "loss":
        return OPP[signal_color]
    return None


def _quality(n: int, match_pct: float) -> str:
    if n >= 500 and match_pct >= 75:
        return "ELITE_OFFSET"
    if n >= 100 and match_pct >= 70:
        return "STRONG_OFFSET"
    if n >= 50 and match_pct >= 65:
        return "WATCH_OFFSET"
    return "WEAK_OR_INSUFFICIENT"


def load_stream(db_path: str = DB_PATH, days: int = 9999) -> list[dict]:
    where = "" if days >= 9999 else "AND fired_at >= datetime('now', ?)"
    params = () if days >= 9999 else (f"-{int(days)} days",)
    with _connect(db_path) as conn:
        rows = conn.execute(
            f"""
            SELECT id, color, outcome, signal_kind, COALESCE(source_floor,'LIVE') source_floor,
                   COALESCE(won_at_gale,0) won_at_gale,
                   COALESCE(resolved_at,fired_at) ts
            FROM consensus_signals
            WHERE outcome IN ('win','loss','tie')
              AND color IN ('red','blue')
              {where}
            ORDER BY COALESCE(resolved_at,fired_at), id
            """,
            params,
        ).fetchall()
    out: list[dict] = []
    for row in rows:
        actual = _actual(row["color"], row["outcome"])
        if actual:
            out.append({**dict(row), "actual": actual})
    return out


def mine_offsets(
    db_path: str = DB_PATH,
    days: int = 9999,
    max_offset: int = 6,
    min_n: int = 50,
) -> list[OffsetCell]:
    stream = load_stream(db_path=db_path, days=days)
    cells: dict[tuple[str, str, str, int], dict] = {}
    for i, sig in enumerate(stream):
        if sig["outcome"] != "win" or int(sig["won_at_gale"] or 0) != 0:
            continue
        if sig["color"] not in OPP:
            continue
        for offset in range(1, int(max_offset) + 1):
            j = i + offset
            if j >= len(stream):
                continue
            target = stream[j]["actual"]
            key = (sig["signal_kind"] or "", sig["source_floor"] or "LIVE", sig["color"], offset)
            cell = cells.setdefault(key, {"n": 0, "match": 0, "opp": 0, "tie": 0})
            cell["n"] += 1
            if target == sig["color"]:
                cell["match"] += 1
            elif target == OPP[sig["color"]]:
                cell["opp"] += 1
            elif target == "tie":
                cell["tie"] += 1

    result: list[OffsetCell] = []
    for (kind, floor, color, offset), c in cells.items():
        n = c["n"]
        if n < min_n:
            continue
        match_pct = round(100.0 * c["match"] / max(n - c["tie"], 1), 2)
        opposite_pct = round(100.0 * c["opp"] / max(n - c["tie"], 1), 2)
        tie_pct = round(100.0 * c["tie"] / max(n, 1), 2)
        result.append(
            OffsetCell(
                signal_kind=kind,
                source_floor=floor,
                color=color,
                offset=offset,
                n=n,
                match_count=c["match"],
                opposite_count=c["opp"],
                tie_count=c["tie"],
                match_pct=match_pct,
                opposite_pct=opposite_pct,
                tie_pct=tie_pct,
                quality=_quality(n, match_pct),
            )
        )
    result.sort(key=lambda x: (x.quality != "ELITE_OFFSET", x.quality != "STRONG_OFFSET", -x.match_pct, -x.n))
    return result


def save_report(
    db_path: str = DB_PATH,
    days: int = 9999,
    max_offset: int = 6,
    path: str = REPORT_PATH,
) -> dict:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    cells = mine_offsets(db_path=db_path, days=days, max_offset=max_offset)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "days": int(days),
        "max_offset": int(max_offset),
        "summary": {
            "cells": len(cells),
            "elite": sum(1 for c in cells if c.quality == "ELITE_OFFSET"),
            "strong": sum(1 for c in cells if c.quality == "STRONG_OFFSET"),
            "watch": sum(1 for c in cells if c.quality == "WATCH_OFFSET"),
        },
        "top_cells": [asdict(c) for c in cells[:50]],
        "all_cells": [asdict(c) for c in cells],
        "live_recommendation": [
            "Use only STRONG/ELITE offset cells as score boosts, not standalone fire rules.",
            "SEQUENCE/LIVE/BLUE offset3 has historically been one of the strongest future-blue cells.",
            "Revalidate by recent window before promoting live.",
        ],
    }
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    os.replace(tmp, path)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Mine G0 future-offset oracle cells")
    parser.add_argument("--db", default=DB_PATH)
    parser.add_argument("--days", type=int, default=9999)
    parser.add_argument("--max-offset", type=int, default=6)
    parser.add_argument("--report", default=REPORT_PATH)
    args = parser.parse_args()
    report = save_report(args.db, args.days, args.max_offset, args.report)
    print(json.dumps({
        "generated_at": report["generated_at"],
        "summary": report["summary"],
        "top_cells": report["top_cells"][:15],
    }, indent=2, ensure_ascii=False))
    print(f"report={args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
