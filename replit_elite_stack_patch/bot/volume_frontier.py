"""
volume_frontier.py — volume vs WR frontier for BacBo Royal.

This report answers the user's key question:
    "What has to be true to reach 1200-3500+ signals/day without hurting WR?"

It uses the full DB, fired signals, blocked signals, rooms, and floors/camadas.
It is read-only and writes bot/data/volume_frontier_report.json.

Important conclusion this module makes explicit:
    Historical data can support 1200-3500/day only in ~70-84% regimes unless a
    new DIRECT_CASINO_VERIFIED early-result oracle is added.  The DB does not
    show 1200+/day at 98% WR.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
from datetime import datetime, timezone
from typing import Any


HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(HERE, "bacbo.db")
REPORT_PATH = os.path.join(HERE, "data", "volume_frontier_report.json")


def _connect(db_path: str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def _rows(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(sql, params).fetchall()]


def _one(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> dict[str, Any]:
    row = conn.execute(sql, params).fetchone()
    return dict(row) if row else {}


def daily_fired(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    return _rows(conn, """
        SELECT date(fired_at) d,
               COUNT(*) total,
               SUM(outcome='win') wins,
               SUM(outcome='loss') losses,
               SUM(outcome='tie') ties,
               ROUND(100.0 * SUM(outcome='win') /
                     NULLIF(SUM(outcome IN ('win','loss')), 0), 2) wr,
               ROUND(100.0 * SUM(outcome='win' AND COALESCE(won_at_gale,0)=0) /
                     NULLIF(SUM(outcome IN ('win','loss')), 0), 2) g0_wr
        FROM consensus_signals
        WHERE outcome IN ('win','loss','tie')
        GROUP BY d
        ORDER BY d
    """)


def fired_blocked_supply(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    return _rows(conn, """
        WITH fired AS (
          SELECT date(fired_at) d,
                 COUNT(*) fired,
                 SUM(outcome='win') fw,
                 SUM(outcome='loss') fl,
                 SUM(outcome='tie') ft
          FROM consensus_signals
          WHERE outcome IN ('win','loss','tie')
          GROUP BY d
        ),
        blocked AS (
          SELECT date(blocked_at) d,
                 COUNT(*) blocked,
                 SUM(outcome='win') bw,
                 SUM(outcome='loss') bl,
                 SUM(outcome='tie') bt
          FROM blocked_signals
          WHERE outcome IN ('win','loss','tie')
          GROUP BY d
        )
        SELECT COALESCE(f.d,b.d) d,
               COALESCE(fired,0) fired,
               COALESCE(blocked,0) blocked,
               COALESCE(fired,0)+COALESCE(blocked,0) supply,
               ROUND(100.0 * COALESCE(fw,0) /
                     NULLIF(COALESCE(fw,0)+COALESCE(fl,0), 0), 2) fired_wr,
               ROUND(100.0 * COALESCE(bw,0) /
                     NULLIF(COALESCE(bw,0)+COALESCE(bl,0), 0), 2) blocked_wr,
               ROUND(100.0 * (COALESCE(fw,0)+COALESCE(bw,0)) /
                     NULLIF(COALESCE(fw,0)+COALESCE(fl,0)+COALESCE(bw,0)+COALESCE(bl,0), 0), 2) supply_wr
        FROM fired f
        FULL OUTER JOIN blocked b ON f.d = b.d
        ORDER BY supply DESC
    """)


def threshold_frontier(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for threshold in (70, 75, 80, 85, 90, 95, 98):
        row = _one(conn, f"""
            SELECT MAX(total) max_daily, COUNT(*) days
            FROM (
              SELECT date(fired_at) d,
                     COUNT(*) total,
                     ROUND(100.0 * SUM(outcome='win') /
                           NULLIF(SUM(outcome IN ('win','loss')), 0), 2) wr
              FROM consensus_signals
              WHERE outcome IN ('win','loss','tie')
              GROUP BY d
            )
            WHERE wr >= {threshold}
        """)
        out.append({"wr_threshold": threshold, **row})
    return out


def floor_frontier(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    return _rows(conn, """
        SELECT source_floor floor,
               date(fired_at) d,
               COUNT(*) total,
               SUM(outcome='win') wins,
               SUM(outcome='loss') losses,
               SUM(outcome='tie') ties,
               ROUND(100.0 * SUM(outcome='win') /
                     NULLIF(SUM(outcome IN ('win','loss')), 0), 2) wr,
               ROUND(100.0 * SUM(outcome='win' AND COALESCE(won_at_gale,0)=0) /
                     NULLIF(SUM(outcome IN ('win','loss')), 0), 2) g0_wr
        FROM consensus_signals
        WHERE outcome IN ('win','loss','tie')
          AND source_floor IS NOT NULL
        GROUP BY floor, d
        HAVING total >= 50
        ORDER BY total DESC, wr DESC
        LIMIT 100
    """)


def high_volume_good_floors(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    return _rows(conn, """
        SELECT source_floor floor,
               date(fired_at) d,
               COUNT(*) total,
               SUM(outcome='win') wins,
               SUM(outcome='loss') losses,
               SUM(outcome='tie') ties,
               ROUND(100.0 * SUM(outcome='win') /
                     NULLIF(SUM(outcome IN ('win','loss')), 0), 2) wr,
               ROUND(100.0 * SUM(outcome='win' AND COALESCE(won_at_gale,0)=0) /
                     NULLIF(SUM(outcome IN ('win','loss')), 0), 2) g0_wr
        FROM consensus_signals
        WHERE outcome IN ('win','loss','tie')
          AND source_floor IS NOT NULL
        GROUP BY floor, d
        HAVING total >= 50 AND wr >= 78
        ORDER BY total DESC, wr DESC
        LIMIT 100
    """)


def recent_room_candidates(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    return _rows(conn, """
        WITH sig AS (
          SELECT lower(replace(
                   CASE
                     WHEN instr(coalesce(rooms_agreed,''), ',') > 0
                     THEN substr(rooms_agreed, 1, instr(rooms_agreed, ',') - 1)
                     ELSE coalesce(rooms_agreed, '')
                   END, '@', '')) room,
                 outcome, color
          FROM consensus_signals
          WHERE fired_at >= datetime('now','-7 days')
            AND outcome IN ('win','loss','tie')
        )
        SELECT room,
               COUNT(*) total,
               SUM(outcome='win') wins,
               SUM(outcome='loss') losses,
               SUM(outcome='tie') ties,
               ROUND(100.0 * SUM(outcome='win') /
                     NULLIF(SUM(outcome IN ('win','loss')), 0), 2) wr,
               ROUND(100.0 * SUM(color='blue') / COUNT(*), 1) blue_pct
        FROM sig
        WHERE room <> ''
        GROUP BY room
        HAVING total >= 10
        ORDER BY wr DESC, total DESC
    """)


def gate_release_candidates(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    return _rows(conn, """
        SELECT gate_reason,
               COUNT(*) n,
               SUM(outcome='win') blocked_wins,
               SUM(outcome='loss') losses_saved,
               SUM(outcome='tie') ties,
               ROUND(100.0 * SUM(outcome='win') /
                     NULLIF(SUM(outcome IN ('win','loss')), 0), 1) blocked_wr,
               SUM(outcome='win') - SUM(outcome='loss') net_bad_if_positive
        FROM blocked_signals
        WHERE outcome IN ('win','loss','tie')
        GROUP BY gate_reason
        HAVING n >= 20
        ORDER BY net_bad_if_positive DESC
        LIMIT 80
    """)


def build_report(db_path: str = DB_PATH) -> dict[str, Any]:
    with _connect(db_path) as conn:
        daily = daily_fired(conn)
        supply = fired_blocked_supply(conn)
        frontier = threshold_frontier(conn)
        floors = floor_frontier(conn)
        high_floors = high_volume_good_floors(conn)
        rooms = recent_room_candidates(conn)
        gates = gate_release_candidates(conn)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "max_fired_day": max(daily, key=lambda r: r.get("total") or 0) if daily else None,
            "best_wr_day_n100": max(
                [r for r in daily if (r.get("total") or 0) >= 100],
                key=lambda r: r.get("wr") or 0,
            ) if daily else None,
            "threshold_frontier": frontier,
            "historic_truth": (
                "DB does not show 1200+/day at 98% WR. "
                "1200-3500/day exists in 70-84% regimes unless a new direct early-result oracle is proven."
            ),
        },
        "daily_fired": daily,
        "fired_plus_blocked_supply": supply[:80],
        "floor_frontier": floors,
        "high_volume_good_floors": high_floors,
        "recent_room_candidates": rooms,
        "gate_release_candidates": gates,
        "recommended_system_changes": [
            "Replace blanket hour hard-blocks with scored hour risk/advisory where possible.",
            "Do not let every blocked signal fire; blocked-supply WR is usually far below fired WR.",
            "Use floor-local dedup for independent floors, but keep same-round opposite-color safety lock.",
            "Favor LIVE, ELITE_V2, MAY20-MAY27 peak stack, and current 7d LIVE/MAY19/MAY10/MAR21 cells.",
            "Use room whitelist weighted by recent performance: robobacbodados, isadados, sinaisbacboangola, dadosbacbobr, rigosinais, martinswinbacbo, rqdados/rqdados1.",
            "Downgrade weak current rooms: bacbob2xbet, sinal_bac_bo, weak m8sinais cells.",
            "Keep martingale disabled unless room/color/floor recovery report says ALLOW_MARTINGALE.",
            "Build direct Twin225 result capture; without direct truth, 98% claims remain unverified.",
        ],
    }


def save_report(db_path: str = DB_PATH, path: str = REPORT_PATH) -> dict[str, Any]:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    report = build_report(db_path)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)
        fh.write("\\n")
    os.replace(tmp, path)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit volume/WR frontier")
    parser.add_argument("--db", default=DB_PATH)
    parser.add_argument("--report", default=REPORT_PATH)
    args = parser.parse_args()
    report = save_report(args.db, args.report)
    print(json.dumps(
        {
            "generated_at": report["generated_at"],
            "summary": report["summary"],
            "top_supply_days": report["fired_plus_blocked_supply"][:10],
            "top_high_volume_good_floors": report["high_volume_good_floors"][:10],
            "top_rooms": report["recent_room_candidates"][:10],
            "top_gate_release_candidates": report["gate_release_candidates"][:10],
        },
        indent=2,
        ensure_ascii=False,
    ))
    print(f"report={args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
