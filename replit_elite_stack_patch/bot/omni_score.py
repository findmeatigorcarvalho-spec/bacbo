"""
omni_score.py — multi-dimensional signal scoring for BacBo Royal.

The goal is to stop treating "confidence" as one magic number.  A signal gets
graded from independent dimensions:

* recent fired WR for the anchor room
* raw room color outcome WR
* room/hour/color cell WR
* signal kind WR
* source floor WR
* color bias
* blocked-winner rescue value
* room DNA edge score
* freshness / stale penalties

This module is intentionally side-effect free.  It can be called from
signal_handler.py later, but it is also useful as a CLI audit tool now.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Iterable, Optional


HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(HERE, "bacbo.db")
REPORT_PATH = os.path.join(HERE, "data", "omni_score_report.json")


FIRE_THRESHOLD = 82.0
SHADOW_THRESHOLD = 72.0
BLOCK_THRESHOLD = 60.0


@dataclass
class Dimension:
    name: str
    points: float
    weight: float
    evidence: str


@dataclass
class OmniScoreResult:
    score: float
    verdict: str
    room: str
    color: str
    signal_kind: str
    source_floor: str
    dimensions: list[Dimension]
    penalties: list[Dimension]


def _connect(db_path: str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=20)
    conn.row_factory = sqlite3.Row
    return conn


def _norm_room(room: str) -> str:
    return (room or "").strip().lstrip("@").lower()


def _first_room(rooms: Iterable[str] | str | None) -> str:
    if rooms is None:
        return ""
    if isinstance(rooms, str):
        parts = [p.strip() for p in rooms.split(",") if p.strip()]
    else:
        parts = [str(p).strip() for p in rooms if str(p).strip()]
    return _norm_room(parts[0]) if parts else ""


def _pct_to_points(wr: Optional[float], neutral: float = 50.0, scale: float = 1.0) -> float:
    if wr is None:
        return 0.0
    return max(-20.0, min(25.0, (float(wr) - neutral) * scale))


def _scalar(row: Optional[sqlite3.Row], key: str, default=None):
    if row is None:
        return default
    return row[key] if key in row.keys() else default


def _room_recent_fired(conn: sqlite3.Connection, room: str) -> tuple[Optional[float], int]:
    row = conn.execute(
        """
        WITH sig AS (
          SELECT outcome
          FROM consensus_signals
          WHERE fired_at >= datetime('now','-7 days')
            AND outcome IN ('win','loss','tie')
            AND lower(replace(
              CASE
                WHEN instr(coalesce(rooms_agreed,''), ',') > 0
                THEN substr(rooms_agreed, 1, instr(rooms_agreed, ',') - 1)
                ELSE coalesce(rooms_agreed, '')
              END, '@', '')) = ?
        )
        SELECT COUNT(*) n,
               ROUND(100.0 * SUM(outcome='win') /
                     NULLIF(SUM(outcome IN ('win','loss')), 0), 1) wr
        FROM sig
        """,
        (room,),
    ).fetchone()
    return _scalar(row, "wr"), int(_scalar(row, "n", 0) or 0)


def _raw_room_color(conn: sqlite3.Connection, room: str, color: str) -> tuple[Optional[float], int]:
    row = conn.execute(
        """
        SELECT COUNT(*) n,
               ROUND(100.0 * SUM(outcome='win') /
                     NULLIF(SUM(outcome IN ('win','loss')), 0), 1) wr
        FROM room_color_outcomes
        WHERE msg_ts >= datetime('now','-30 days')
          AND outcome IN ('win','loss')
          AND color = ?
          AND lower(replace(handle,'@','')) = ?
        """,
        (color, room),
    ).fetchone()
    return _scalar(row, "wr"), int(_scalar(row, "n", 0) or 0)


def _room_hour_color(conn: sqlite3.Connection, room: str, color: str, hour: int) -> tuple[Optional[float], int]:
    row = conn.execute(
        """
        SELECT COUNT(*) n,
               ROUND(100.0 * SUM(outcome='win') /
                     NULLIF(SUM(outcome IN ('win','loss')), 0), 1) wr
        FROM room_color_outcomes
        WHERE msg_ts >= datetime('now','-30 days')
          AND outcome IN ('win','loss')
          AND color = ?
          AND lower(replace(handle,'@','')) = ?
          AND CAST(strftime('%H', msg_ts) AS INT) = ?
        """,
        (color, room, int(hour)),
    ).fetchone()
    return _scalar(row, "wr"), int(_scalar(row, "n", 0) or 0)


def _kind_wr(conn: sqlite3.Connection, signal_kind: str) -> tuple[Optional[float], int]:
    row = conn.execute(
        """
        SELECT COUNT(*) n,
               ROUND(100.0 * SUM(outcome='win') /
                     NULLIF(SUM(outcome IN ('win','loss')), 0), 1) wr,
               ROUND(100.0 * SUM(CASE WHEN outcome='win' AND won_at_gale=0 THEN 1 ELSE 0 END) /
                     NULLIF(SUM(outcome IN ('win','loss')), 0), 1) g0_wr
        FROM consensus_signals
        WHERE fired_at >= datetime('now','-7 days')
          AND outcome IN ('win','loss','tie')
          AND signal_kind = ?
        """,
        (signal_kind,),
    ).fetchone()
    wr = _scalar(row, "g0_wr")
    if wr is None:
        wr = _scalar(row, "wr")
    return wr, int(_scalar(row, "n", 0) or 0)


def _floor_wr(conn: sqlite3.Connection, source_floor: str) -> tuple[Optional[float], int]:
    row = conn.execute(
        """
        SELECT COUNT(*) n,
               ROUND(100.0 * SUM(outcome='win') /
                     NULLIF(SUM(outcome IN ('win','loss')), 0), 1) wr
        FROM consensus_signals
        WHERE fired_at >= datetime('now','-7 days')
          AND outcome IN ('win','loss','tie')
          AND COALESCE(source_floor,'LIVE') = ?
        """,
        (source_floor or "LIVE",),
    ).fetchone()
    return _scalar(row, "wr"), int(_scalar(row, "n", 0) or 0)


def _color_bias(conn: sqlite3.Connection, color: str) -> tuple[Optional[float], int]:
    row = conn.execute(
        """
        SELECT COUNT(*) n,
               ROUND(100.0 * SUM(outcome='win') /
                     NULLIF(SUM(outcome IN ('win','loss')), 0), 1) wr
        FROM consensus_signals
        WHERE fired_at >= datetime('now','-7 days')
          AND outcome IN ('win','loss','tie')
          AND color = ?
        """,
        (color,),
    ).fetchone()
    return _scalar(row, "wr"), int(_scalar(row, "n", 0) or 0)


def _blocked_rescue(conn: sqlite3.Connection, room: str, color: str, hour: int) -> tuple[Optional[float], int, str]:
    row = conn.execute(
        """
        WITH blk AS (
          SELECT outcome, gate_reason
          FROM blocked_signals
          WHERE blocked_at >= datetime('now','-7 days')
            AND outcome IN ('win','loss')
            AND color = ?
            AND CAST(strftime('%H', blocked_at) AS INT) = ?
            AND lower(replace(
              CASE
                WHEN instr(coalesce(rooms_agreed,''), ',') > 0
                THEN substr(rooms_agreed, 1, instr(rooms_agreed, ',') - 1)
                ELSE coalesce(rooms_agreed, '')
              END, '@', '')) = ?
        )
        SELECT COUNT(*) n,
               ROUND(100.0 * SUM(outcome='win') /
                     NULLIF(SUM(outcome IN ('win','loss')), 0), 1) wr,
               GROUP_CONCAT(DISTINCT gate_reason) gates
        FROM blk
        """,
        (color, int(hour), room),
    ).fetchone()
    return _scalar(row, "wr"), int(_scalar(row, "n", 0) or 0), _scalar(row, "gates", "") or ""


def _room_dna(conn: sqlite3.Connection, room: str) -> tuple[float, str]:
    row = conn.execute(
        "SELECT edge_score, top_insight FROM room_dna WHERE handle=? LIMIT 1",
        (room,),
    ).fetchone()
    if not row:
        return 0.0, "no_dna"
    return float(row["edge_score"] or 0.0), row["top_insight"] or ""


def _freshness(conn: sqlite3.Connection, room: str) -> tuple[bool, str]:
    row = conn.execute(
        """
        SELECT MAX(sent_at) last_msg,
               SUM(sent_at >= datetime('now','-7 days')) msg_7d
        FROM channel_messages
        WHERE lower(replace(handle,'@','')) = ?
        """,
        (room,),
    ).fetchone()
    msg_7d = int(_scalar(row, "msg_7d", 0) or 0)
    last_msg = _scalar(row, "last_msg", None)
    return msg_7d > 0, f"last={last_msg} msg7d={msg_7d}"


def score_signal(
    room: str = "",
    color: str = "",
    signal_kind: str = "SOLO_ELITE",
    source_floor: str = "LIVE",
    rooms_agreed: Iterable[str] | str | None = None,
    hour_utc: Optional[int] = None,
    db_path: str = DB_PATH,
) -> OmniScoreResult:
    """Score one candidate signal using all available dimensions."""
    color = (color or "").strip().lower()
    anchor = _norm_room(room) or _first_room(rooms_agreed)
    signal_kind = (signal_kind or "SOLO_ELITE").strip().upper()
    source_floor = (source_floor or "LIVE").strip().upper()
    if hour_utc is None:
        hour_utc = datetime.now(timezone.utc).hour

    dims: list[Dimension] = []
    penalties: list[Dimension] = []

    with _connect(db_path) as conn:
        if not anchor or color not in {"red", "blue"}:
            penalties.append(Dimension("input", -100.0, 1.0, "missing room or invalid color"))
        else:
            wr, n = _room_recent_fired(conn, anchor)
            pts = _pct_to_points(wr, neutral=70.0, scale=1.1) if n >= 20 else 0.0
            dims.append(Dimension("room_recent_fired_wr", pts, 1.2, f"{wr}% n={n}"))

            wr, n = _raw_room_color(conn, anchor, color)
            pts = _pct_to_points(wr, neutral=52.0, scale=0.8) if n >= 100 else 0.0
            dims.append(Dimension("room_color_raw_wr30", pts, 0.8, f"{wr}% n={n}"))

            wr, n = _room_hour_color(conn, anchor, color, int(hour_utc))
            pts = _pct_to_points(wr, neutral=55.0, scale=1.4) if n >= 20 else 0.0
            dims.append(Dimension("room_hour_color_wr30", pts, 1.3, f"H{int(hour_utc):02d} {wr}% n={n}"))

            wr, n = _kind_wr(conn, signal_kind)
            pts = _pct_to_points(wr, neutral=70.0, scale=1.0) if n >= 20 else 0.0
            dims.append(Dimension("signal_kind_g0_wr7", pts, 1.0, f"{signal_kind} {wr}% n={n}"))

            wr, n = _floor_wr(conn, source_floor)
            pts = _pct_to_points(wr, neutral=72.0, scale=1.0) if n >= 20 else 0.0
            dims.append(Dimension("source_floor_wr7", pts, 1.0, f"{source_floor} {wr}% n={n}"))

            wr, n = _color_bias(conn, color)
            pts = _pct_to_points(wr, neutral=72.0, scale=0.6) if n >= 100 else 0.0
            dims.append(Dimension("global_color_bias7", pts, 0.5, f"{color} {wr}% n={n}"))

            wr, n, gates = _blocked_rescue(conn, anchor, color, int(hour_utc))
            pts = _pct_to_points(wr, neutral=70.0, scale=1.2) if n >= 5 else 0.0
            dims.append(Dimension("blocked_rescue_shadow_wr", pts, 1.1, f"{wr}% n={n} gates={gates}"))

            edge, insight = _room_dna(conn, anchor)
            pts = min(6.0, max(0.0, edge * 2.0))
            dims.append(Dimension("room_dna_edge", pts, 0.7, f"edge={edge:.2f} {insight}"))

            fresh, evidence = _freshness(conn, anchor)
            if fresh:
                dims.append(Dimension("freshness", 5.0, 0.8, evidence))
            else:
                penalties.append(Dimension("stale_room", -25.0, 1.0, evidence))

    weighted = sum(d.points * d.weight for d in dims) + sum(p.points * p.weight for p in penalties)
    # Base 70 means a neutral candidate lands in SHADOW, not FIRE.
    score = max(0.0, min(100.0, 70.0 + weighted))

    if score >= FIRE_THRESHOLD:
        verdict = "FIRE"
    elif score >= SHADOW_THRESHOLD:
        verdict = "SHADOW"
    elif score < BLOCK_THRESHOLD:
        verdict = "BLOCK"
    else:
        verdict = "WAIT"

    return OmniScoreResult(
        score=round(score, 2),
        verdict=verdict,
        room=anchor,
        color=color,
        signal_kind=signal_kind,
        source_floor=source_floor,
        dimensions=dims,
        penalties=penalties,
    )


def score_recent_fired(limit: int = 50, db_path: str = DB_PATH) -> list[OmniScoreResult]:
    """Rescore recent fired signals to calibrate what OmniScore would have done."""
    with _connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT rooms_agreed, color, signal_kind, COALESCE(source_floor,'LIVE') source_floor,
                   CAST(strftime('%H', fired_at) AS INT) hour_utc
            FROM consensus_signals
            WHERE outcome IN ('win','loss','tie')
            ORDER BY fired_at DESC
            LIMIT ?
            """,
            (int(limit),),
        ).fetchall()
    return [
        score_signal(
            color=row["color"],
            signal_kind=row["signal_kind"],
            source_floor=row["source_floor"],
            rooms_agreed=row["rooms_agreed"],
            hour_utc=row["hour_utc"],
            db_path=db_path,
        )
        for row in rows
    ]


def save_report(results: list[OmniScoreResult], path: str = REPORT_PATH) -> dict:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(results),
        "verdict_counts": {
            verdict: sum(1 for result in results if result.verdict == verdict)
            for verdict in ("FIRE", "SHADOW", "WAIT", "BLOCK")
        },
        "results": [
            {
                **asdict(result),
                "dimensions": [asdict(d) for d in result.dimensions],
                "penalties": [asdict(p) for p in result.penalties],
            }
            for result in results
        ],
    }
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    os.replace(tmp, path)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Score Bac Bo signals with OmniScore")
    parser.add_argument("--db", default=DB_PATH)
    parser.add_argument("--room", default="")
    parser.add_argument("--color", default="")
    parser.add_argument("--kind", default="SOLO_ELITE")
    parser.add_argument("--floor", default="LIVE")
    parser.add_argument("--rooms-agreed", default="")
    parser.add_argument("--hour", type=int, default=None)
    parser.add_argument("--recent", type=int, default=0, help="rescore N recent fired signals")
    parser.add_argument("--report", default=REPORT_PATH)
    args = parser.parse_args()

    if args.recent:
        results = score_recent_fired(args.recent, args.db)
        report = save_report(results, args.report)
        print(json.dumps({k: report[k] for k in ("generated_at", "count", "verdict_counts")}, indent=2))
        print(f"report={args.report}")
    else:
        result = score_signal(
            room=args.room,
            color=args.color,
            signal_kind=args.kind,
            source_floor=args.floor,
            rooms_agreed=args.rooms_agreed,
            hour_utc=args.hour,
            db_path=args.db,
        )
        print(json.dumps(asdict(result), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
