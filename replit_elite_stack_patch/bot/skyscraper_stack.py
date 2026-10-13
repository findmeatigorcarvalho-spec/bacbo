"""
skyscraper_stack.py — build the best room+floor+camada stack from all DB data.

This is the "sky scraper" layer:
  - best floor/camada lanes
  - best room/hour/color cells
  - best floor/kind/hour/color cells
  - loss-risk cells to avoid
  - high-volume room candidates
  - Telegram discovery blueprints for new rooms

It is read-only.  It writes:
  bot/data/skyscraper_stack_report.json
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
REPORT_PATH = os.path.join(HERE, "data", "skyscraper_stack_report.json")


def _connect(db_path: str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def _rows(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def _one(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> dict[str, Any]:
    row = conn.execute(sql, params).fetchone()
    return dict(row) if row else {}


def _first_room_expr() -> str:
    return """
    lower(replace(
      CASE
        WHEN instr(coalesce(rooms_agreed,''), ',') > 0
        THEN substr(rooms_agreed, 1, instr(rooms_agreed, ',') - 1)
        ELSE coalesce(rooms_agreed, '')
      END, '@', ''))
    """


def load_floor_lanes(db_path: str) -> dict[str, Any]:
    try:
        import floor_stack_registry
        return floor_stack_registry.save_report(db_path=db_path)
    except Exception as exc:
        return {"error": str(exc), "precision": [], "balanced": [], "volume": [], "shadow": [], "blocked": []}


def top_room_cells(conn: sqlite3.Connection, days: int = 30) -> list[dict[str, Any]]:
    first_room = _first_room_expr()
    return _rows(conn, f"""
        SELECT {first_room} || ':H' || CAST(strftime('%H',fired_at) AS INT) || ':' || color cell,
               {first_room} room,
               CAST(strftime('%H',fired_at) AS INT) hour,
               color,
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
        LIMIT 160
    """, (f"-{int(days)} days",))


def top_floor_kind_cells(conn: sqlite3.Connection, days: int = 30) -> list[dict[str, Any]]:
    return _rows(conn, """
        SELECT COALESCE(source_floor,'LIVE') || ':' || signal_kind || ':H' ||
               CAST(strftime('%H',fired_at) AS INT) || ':' || color cell,
               COALESCE(source_floor,'LIVE') floor,
               signal_kind,
               CAST(strftime('%H',fired_at) AS INT) hour,
               color,
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
        LIMIT 160
    """, (f"-{int(days)} days",))


def room_profiles(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    first_room = _first_room_expr()
    return _rows(conn, f"""
        WITH fired AS (
          SELECT {first_room} room, outcome, color, fired_at
          FROM consensus_signals
          WHERE fired_at >= datetime('now','-7 days')
            AND outcome IN ('win','loss','tie')
        ),
        msg AS (
          SELECT lower(replace(handle,'@','')) room,
                 COUNT(*) msg_total,
                 MAX(sent_at) last_msg,
                 SUM(sent_at >= datetime('now','-7 days')) msg_7d
          FROM channel_messages
          GROUP BY room
        )
        SELECT fired.room,
               COUNT(*) fired_n7,
               SUM(outcome='win') wins,
               SUM(outcome='loss') losses,
               SUM(outcome='tie') ties,
               ROUND(100.0 * SUM(outcome='win') /
                     NULLIF(SUM(outcome IN ('win','loss')),0), 2) wr7,
               ROUND(100.0 * SUM(color='blue') / COUNT(*), 1) blue_pct,
               COALESCE(msg.msg_total,0) msg_total,
               COALESCE(msg.msg_7d,0) msg_7d,
               msg.last_msg
        FROM fired
        LEFT JOIN msg USING(room)
        WHERE fired.room <> ''
        GROUP BY fired.room
        HAVING fired_n7 >= 10
        ORDER BY wr7 DESC, fired_n7 DESC
    """)


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
                     NULLIF(SUM(outcome IN ('win','loss')),0), 2) wr
        FROM consensus_signals
        WHERE fired_at >= datetime('now', ?)
          AND outcome IN ('win','loss','tie')
          AND color IN ('blue','red')
        GROUP BY cell
        HAVING n >= 10 AND loss_pct >= 35
        ORDER BY loss_pct DESC, n DESC
        LIMIT 160
    """, (f"-{int(days)} days",))


def historical_volume_frontier(conn: sqlite3.Connection) -> dict[str, Any]:
    max_day = _one(conn, """
        SELECT date(fired_at) d,
               COUNT(*) total,
               ROUND(100.0 * SUM(outcome='win') /
                     NULLIF(SUM(outcome IN ('win','loss')),0), 2) wr,
               ROUND(100.0 * SUM(outcome='win' AND COALESCE(won_at_gale,0)=0) /
                     NULLIF(SUM(outcome IN ('win','loss')),0), 2) g0_wr
        FROM consensus_signals
        WHERE outcome IN ('win','loss','tie')
        GROUP BY d
        ORDER BY total DESC
        LIMIT 1
    """)
    best_high_vol = _rows(conn, """
        SELECT date(fired_at) d,
               COUNT(*) total,
               ROUND(100.0 * SUM(outcome='win') /
                     NULLIF(SUM(outcome IN ('win','loss')),0), 2) wr,
               ROUND(100.0 * SUM(outcome='win' AND COALESCE(won_at_gale,0)=0) /
                     NULLIF(SUM(outcome IN ('win','loss')),0), 2) g0_wr
        FROM consensus_signals
        WHERE outcome IN ('win','loss','tie')
        GROUP BY d
        HAVING total >= 1000
        ORDER BY wr DESC
        LIMIT 10
    """)
    return {"max_day": max_day, "best_high_volume_days": best_high_vol}


def discovery_blueprints() -> list[dict[str, Any]]:
    return [
        {
            "family": "robobacbodados clones",
            "queries": ["robo bacbo dados", "robô bac bo dados", "bacbo dados robo", "bac bo robo dados"],
            "reason": "robobacbodados is the best recent high-volume room and dominates blue cells",
        },
        {
            "family": "sinaisbacboangola variants",
            "queries": ["sinais bacbo angola", "bac bo angola sinais", "dados bacbo angola"],
            "reason": "sinaisbacboangola owns multiple 90%+ room/hour/color cells",
        },
        {
            "family": "rqdados/rqdados1 variants",
            "queries": ["rqdados", "rq dados bacbo", "rqdados bac bo", "dados rq bacbo"],
            "reason": "rqdados1 has strong blue H7/H14 and useful timing",
        },
        {
            "family": "martinswinbacbo variants",
            "queries": ["martins win bacbo", "martins bac bo", "win bacbo martins"],
            "reason": "martinswinbacbo has 96%+ H14/H15 blue cells",
        },
        {
            "family": "sem gale/G0 specialists",
            "queries": ["bac bo sem gale", "bacbo g0", "bac bo zero gale", "sinais bacbo sem gale"],
            "reason": "G0-only is the best money profile; find rooms that publish direct G0 calls",
        },
    ]


def build_report(db_path: str = DB_PATH, days: int = 30) -> dict[str, Any]:
    floor_report = {}
    try:
        import floor_stack_registry
        floor_report = floor_stack_registry.save_report(db_path=db_path)
    except Exception as exc:
        floor_report = {"error": str(exc)}

    with _connect(db_path) as conn:
        room_cells = top_room_cells(conn, days)
        floor_cells = top_floor_kind_cells(conn, days)
        rooms = room_profiles(conn)
        loss = loss_risk_cells(conn, days)
        frontier = historical_volume_frontier(conn)

    precision_rooms = [r for r in rooms if (r.get("wr7") or 0) >= 82][:20]
    balanced_rooms = [r for r in rooms if 75 <= (r.get("wr7") or 0) < 82][:30]
    volume_rooms = [r for r in rooms if 70 <= (r.get("wr7") or 0) < 75][:30]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "days": int(days),
        "floor_stack": {
            "precision": floor_report.get("precision", []),
            "balanced": floor_report.get("balanced", []),
            "volume": floor_report.get("volume", []),
            "blocked": floor_report.get("blocked", []),
            "lane_counts": floor_report.get("lane_counts", {}),
        },
        "room_stack": {
            "precision_rooms": precision_rooms,
            "balanced_rooms": balanced_rooms,
            "volume_rooms": volume_rooms,
        },
        "edge_stack": {
            "room_hour_color": room_cells[:80],
            "floor_kind_hour_color": floor_cells[:80],
            "loss_risk_cells": loss[:80],
        },
        "volume_frontier": frontier,
        "new_room_discovery_blueprints": discovery_blueprints(),
        "skyscraper_policy": {
            "precision": " + ".join(
                [f["floor"] for f in floor_report.get("precision", [])] or ["AITEST_APR20_MAX", "AITEST_ULTIMATE"]
            ) + " + SNIPER cells + Tri-Brain FIRE",
            "balanced": " + ".join(
                [f["floor"] for f in floor_report.get("balanced", [])]
                or ["LIVE", "ELITE_V2", "ULTIMATE", "APR20", "MAY01"]
            ) + " + strong room cells",
            "volume": " + ".join(
                [f["floor"] for f in floor_report.get("volume", [])]
                or ["MAR19", "MAR20", "AITEST_LIVE", "MAR21", "MAY10", "APR26"]
            ) + " + non-loss-risk WATCH cells (luxury WR>=60)",
            "live_building": [
                f["floor"]
                for f in (
                    floor_report.get("live_building")
                    or (
                        list(floor_report.get("precision", []))
                        + list(floor_report.get("balanced", []))
                        + list(floor_report.get("volume", []))
                    )
                )
            ],
            "shadow": "All thin/stale/new rooms and floors until they prove themselves",
            "block": "JUN12A/JUN12B + actively bleeding floors + loss-risk cells",
            "mode": "EDGE_POLICY_MODE=luxury",
        },
        "expected": {
            "precision": "lower volume, highest WR",
            "balanced": "medium volume, strong WR",
            "volume": "max volume, lower WR but still positive-edge",
            "max_g0_only": "historically 2000-3500/day at ~75-84% unless direct early oracle is proven",
        },
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
    parser = argparse.ArgumentParser(description="Build Super Ultra Skyscraper Stack report")
    parser.add_argument("--db", default=DB_PATH)
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--report", default=REPORT_PATH)
    args = parser.parse_args()
    report = save_report(args.db, args.days, args.report)
    print(json.dumps(
        {
            "generated_at": report["generated_at"],
            "floor_lane_counts": report["floor_stack"].get("lane_counts"),
            "precision_floors": [f["floor"] for f in report["floor_stack"].get("precision", [])],
            "balanced_floors": [f["floor"] for f in report["floor_stack"].get("balanced", [])],
            "volume_floors": [f["floor"] for f in report["floor_stack"].get("volume", [])],
            "precision_rooms": report["room_stack"]["precision_rooms"][:10],
            "top_room_cells": report["edge_stack"]["room_hour_color"][:12],
            "top_floor_cells": report["edge_stack"]["floor_kind_hour_color"][:12],
            "expected": report["expected"],
        },
        indent=2,
        ensure_ascii=False,
    ))
    print(f"report={args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
