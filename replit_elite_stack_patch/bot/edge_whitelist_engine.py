"""
edge_whitelist_engine.py — day-one elite edge whitelist.

This is the "use everything we found" layer:

1. Mines exact high-WR cells from the full DB:
   - room × hour × color
   - floor × kind × hour × color
   - kind × floor × color
2. Pulls the G0 future-offset oracle edge.
3. Pulls the Tri-Brain FIRE/SHADOW/BLOCK performance.
4. Emits one conservative policy:
   - FIRE_COLOR_G0 only for exact elite cells or Tri-Brain fire buckets.
   - BOOST for G0 offset oracle cells, especially SEQUENCE/LIVE/BLUE.
   - SHADOW everything promising but not proven.
   - BLOCK known loss-risk cells.

Read-only. Writes bot/data/edge_whitelist_engine.json.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any


HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(HERE, "bacbo.db")
REPORT_PATH = os.path.join(HERE, "data", "edge_whitelist_engine.json")


@dataclass
class EdgeCell:
    cell_type: str
    key: str
    n: int
    wins: int
    losses: int
    ties: int
    wr: float
    g0_wr: float | None
    avg_secs: float | None
    tier: str
    action: str


def _connect(db_path: str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def _rows(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def _first_room_expr() -> str:
    return """
    lower(replace(
      CASE
        WHEN instr(coalesce(rooms_agreed,''), ',') > 0
        THEN substr(rooms_agreed, 1, instr(rooms_agreed, ',') - 1)
        ELSE coalesce(rooms_agreed, '')
      END, '@', ''))
    """


def _tier(n: int, wr: float, g0_wr: float | None = None) -> str:
    g = g0_wr if g0_wr is not None else wr
    if n >= 100 and wr >= 90 and g >= 88:
        return "ELITE"
    if n >= 30 and wr >= 92 and g >= 88:
        return "SNIPER"
    if n >= 15 and wr >= 90:
        return "WATCH"
    if n >= 15 and wr >= 85:
        return "SHADOW"
    return "IGNORE"


def _action(tier: str) -> str:
    if tier in {"ELITE", "SNIPER"}:
        return "FIRE_IF_TRI_BRAIN_OK"
    if tier == "WATCH":
        return "SHADOW_THEN_PROMOTE"
    if tier == "SHADOW":
        return "SHADOW_ONLY"
    return "IGNORE"


def _cell_from_row(cell_type: str, r: dict[str, Any]) -> EdgeCell:
    n = int(r["n"] or 0)
    wr = float(r["wr"] or 0.0)
    g0 = r.get("g0_wr")
    g0_wr = float(g0) if g0 is not None else None
    tier = _tier(n, wr, g0_wr)
    return EdgeCell(
        cell_type=cell_type,
        key=str(r["cell"]),
        n=n,
        wins=int(r["wins"] or 0),
        losses=int(r["losses"] or 0),
        ties=int(r["ties"] or 0),
        wr=wr,
        g0_wr=g0_wr,
        avg_secs=r.get("avg_secs"),
        tier=tier,
        action=_action(tier),
    )


def mine_room_hour_color(conn: sqlite3.Connection, days: int = 30) -> list[EdgeCell]:
    first_room = _first_room_expr()
    rows = _rows(conn, f"""
        SELECT {first_room} || ':H' || CAST(strftime('%H',fired_at) AS INT) || ':' || color cell,
               COUNT(*) n,
               SUM(outcome='win') wins,
               SUM(outcome='loss') losses,
               SUM(outcome='tie') ties,
               ROUND(100.0 * SUM(outcome='win') /
                     NULLIF(SUM(outcome IN ('win','loss')), 0), 2) wr,
               ROUND(100.0 * SUM(outcome='win' AND COALESCE(won_at_gale,0)=0) /
                     NULLIF(SUM(outcome IN ('win','loss')), 0), 2) g0_wr,
               ROUND(AVG(secs_to_result), 1) avg_secs
        FROM consensus_signals
        WHERE fired_at >= datetime('now', ?)
          AND outcome IN ('win','loss','tie')
          AND color IN ('blue','red')
        GROUP BY cell
        HAVING n >= 15 AND wr >= 85
        ORDER BY wr DESC, n DESC
        LIMIT 200
    """, (f"-{int(days)} days",))
    return [_cell_from_row("room_hour_color", r) for r in rows]


def mine_floor_kind_hour_color(conn: sqlite3.Connection, days: int = 30) -> list[EdgeCell]:
    rows = _rows(conn, """
        SELECT COALESCE(source_floor,'LIVE') || ':' || signal_kind || ':H' ||
               CAST(strftime('%H',fired_at) AS INT) || ':' || color cell,
               COUNT(*) n,
               SUM(outcome='win') wins,
               SUM(outcome='loss') losses,
               SUM(outcome='tie') ties,
               ROUND(100.0 * SUM(outcome='win') /
                     NULLIF(SUM(outcome IN ('win','loss')), 0), 2) wr,
               ROUND(100.0 * SUM(outcome='win' AND COALESCE(won_at_gale,0)=0) /
                     NULLIF(SUM(outcome IN ('win','loss')), 0), 2) g0_wr,
               ROUND(AVG(secs_to_result), 1) avg_secs
        FROM consensus_signals
        WHERE fired_at >= datetime('now', ?)
          AND outcome IN ('win','loss','tie')
          AND color IN ('blue','red')
        GROUP BY cell
        HAVING n >= 15 AND wr >= 85
        ORDER BY wr DESC, n DESC
        LIMIT 200
    """, (f"-{int(days)} days",))
    return [_cell_from_row("floor_kind_hour_color", r) for r in rows]


def mine_kind_floor_color(conn: sqlite3.Connection, days: int = 30) -> list[EdgeCell]:
    rows = _rows(conn, """
        SELECT signal_kind || ':' || COALESCE(source_floor,'LIVE') || ':' || color cell,
               COUNT(*) n,
               SUM(outcome='win') wins,
               SUM(outcome='loss') losses,
               SUM(outcome='tie') ties,
               ROUND(100.0 * SUM(outcome='win') /
                     NULLIF(SUM(outcome IN ('win','loss')), 0), 2) wr,
               ROUND(100.0 * SUM(outcome='win' AND COALESCE(won_at_gale,0)=0) /
                     NULLIF(SUM(outcome IN ('win','loss')), 0), 2) g0_wr,
               ROUND(AVG(secs_to_result), 1) avg_secs
        FROM consensus_signals
        WHERE fired_at >= datetime('now', ?)
          AND outcome IN ('win','loss','tie')
          AND color IN ('blue','red')
        GROUP BY cell
        HAVING n >= 15 AND wr >= 85
        ORDER BY wr DESC, n DESC
        LIMIT 100
    """, (f"-{int(days)} days",))
    return [_cell_from_row("kind_floor_color", r) for r in rows]


def loss_risk_cells(conn: sqlite3.Connection, days: int = 30) -> list[dict[str, Any]]:
    first_room = _first_room_expr()
    return _rows(conn, f"""
        SELECT {first_room} || ':' || COALESCE(source_floor,'LIVE') || ':' ||
               signal_kind || ':H' || CAST(strftime('%H',fired_at) AS INT) || ':' || color cell,
               COUNT(*) n,
               SUM(outcome='win') wins,
               SUM(outcome='loss') losses,
               SUM(outcome='tie') ties,
               ROUND(100.0 * SUM(outcome='loss') / COUNT(*), 2) loss_pct,
               ROUND(100.0 * SUM(outcome='win') /
                     NULLIF(SUM(outcome IN ('win','loss')), 0), 2) wr
        FROM consensus_signals
        WHERE fired_at >= datetime('now', ?)
          AND outcome IN ('win','loss','tie')
          AND color IN ('blue','red')
        GROUP BY cell
        HAVING n >= 10 AND loss_pct >= 35
        ORDER BY loss_pct DESC, n DESC
        LIMIT 120
    """, (f"-{int(days)} days",))


def g0_offset_summary(db_path: str, days: int = 9999) -> dict[str, Any]:
    try:
        import g0_offset_oracle
        report = g0_offset_oracle.save_report(db_path=db_path, days=days)
        return {
            "summary": report["summary"],
            "top_cells": report["top_cells"][:20],
        }
    except Exception as exc:
        return {"error": str(exc)}


def tri_brain_summary(db_path: str, limit: int = 500) -> dict[str, Any]:
    try:
        import tri_brain_score
        report = tri_brain_score.save_report(db_path=db_path, limit=limit)
        return {
            "scored_n": report["scored_n"],
            "verdict_counts": report["verdict_counts"],
            "verdict_stats": report["verdict_stats"],
            "top_fire_candidates": report["top_fire_candidates"][:20],
        }
    except Exception as exc:
        return {"error": str(exc)}


def build_report(db_path: str = DB_PATH, days: int = 30) -> dict[str, Any]:
    with _connect(db_path) as conn:
        rhc = mine_room_hour_color(conn, days)
        fkhc = mine_floor_kind_hour_color(conn, days)
        kfc = mine_kind_floor_color(conn, days)
        loss = loss_risk_cells(conn, days)

    all_edges = rhc + fkhc + kfc
    all_edges.sort(key=lambda c: (
        c.tier != "ELITE",
        c.tier != "SNIPER",
        c.tier != "WATCH",
        -c.wr,
        -c.n,
    ))

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "days": int(days),
        "policy": {
            "FIRE_IF_TRI_BRAIN_OK": "Only live-fire if cell is ELITE/SNIPER and Tri-Brain is not BLOCK_LOSS_RISK.",
            "SHADOW_THEN_PROMOTE": "Track silently; promote only after recent live shadow proof.",
            "SHADOW_ONLY": "Useful signal intelligence but not enough for live fire.",
            "IGNORE": "Do not use for live decisions.",
        },
        "summary": {
            "elite_cells": sum(1 for c in all_edges if c.tier == "ELITE"),
            "sniper_cells": sum(1 for c in all_edges if c.tier == "SNIPER"),
            "watch_cells": sum(1 for c in all_edges if c.tier == "WATCH"),
            "shadow_cells": sum(1 for c in all_edges if c.tier == "SHADOW"),
            "loss_risk_cells": len(loss),
        },
        "elite_edges": [asdict(c) for c in all_edges if c.tier in {"ELITE", "SNIPER"}][:120],
        "watch_edges": [asdict(c) for c in all_edges if c.tier == "WATCH"][:120],
        "shadow_edges": [asdict(c) for c in all_edges if c.tier == "SHADOW"][:120],
        "loss_risk_cells": loss,
        "g0_offset_oracle": g0_offset_summary(db_path),
        "tri_brain": tri_brain_summary(db_path),
        "live_fire_recipe": [
            "1. Candidate must match elite_edges or Tri-Brain FIRE_COLOR_G0.",
            "2. If it matches loss_risk_cells, block unless direct early casino truth confirms.",
            "3. Apply G0 offset boost for SEQUENCE/LIVE/BLUE and other ELITE_OFFSET cells.",
            "4. Keep martingale G0_ONLY unless martingale_audit says ALLOW_MARTINGALE.",
            "5. Treat all results as BOT_DB_INFERRED until truth_verifier has direct casino rows.",
        ],
    }


def save_report(db_path: str = DB_PATH, days: int = 30, path: str = REPORT_PATH) -> dict[str, Any]:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    report = build_report(db_path, days)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    os.replace(tmp, path)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Build elite edge whitelist policy")
    parser.add_argument("--db", default=DB_PATH)
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--report", default=REPORT_PATH)
    args = parser.parse_args()
    report = save_report(args.db, args.days, args.report)
    print(json.dumps({
        "generated_at": report["generated_at"],
        "summary": report["summary"],
        "top_elite_edges": report["elite_edges"][:20],
        "top_watch_edges": report["watch_edges"][:20],
        "tri_brain": report["tri_brain"].get("verdict_stats"),
        "g0_offset_top": report["g0_offset_oracle"].get("top_cells", [])[:8],
    }, indent=2, ensure_ascii=False))
    print(f"report={args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
