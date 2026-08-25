"""
room_cleaner.py — validate, clean, and retest Bac Bo signal rooms.

This module turns the existing room history into conservative actions:

* MUTE_STALE: active room has no 7-day message history.
* DOWNGRADE_WEAK: active room has enough recent fired signals but weak WR.
* RETEST_MUTED: muted room still has recent activity or useful fired WR.
* KEEP: room has fresh data and no obvious weakness.

Default mode is read-only. Use ``python room_cleaner.py --apply`` only after
reviewing the dry-run report.
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
REPORT_PATH = os.path.join(HERE, "data", "room_cleaner_report.json")


MIN_FIRED_N = 20
WEAK_FIRED_WR = 70.0
RETEST_FIRED_WR = 70.0
RETEST_MIN_FIRED_N = 20
STALE_DAYS = 7

WRONG_GAME_NAME_TOKENS = (
    "football",
    "speedbaccarat",
    "sicbo",
)


@dataclass
class RoomHealth:
    handle: str
    is_muted: int
    gale_tier: str
    quarantine_until: Optional[str]
    msg_n: int
    last_msg: Optional[str]
    msg_7d: int
    msg_30d: int
    raw_n30: int
    raw_wr30: Optional[float]
    fired_n7: int
    fired_wr7: Optional[float]
    flags: list[str]
    action: str
    reason: str


def _connect(db_path: str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=20)
    conn.row_factory = sqlite3.Row
    return conn


def _write_connect(db_path: str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, timeout=20)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=12000")
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _room_rows(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """
        WITH r AS (
          SELECT lower(replace(handle,'@','')) room,
                 handle, is_muted, gale_tier, quarantine_until
          FROM rooms
        ),
        msg AS (
          SELECT lower(replace(handle,'@','')) room,
                 COUNT(*) msg_n,
                 MAX(sent_at) last_msg,
                 SUM(sent_at >= datetime('now','-7 days')) msg_7d,
                 SUM(sent_at >= datetime('now','-30 days')) msg_30d
          FROM channel_messages
          GROUP BY room
        ),
        raw AS (
          SELECT lower(replace(handle,'@','')) room,
                 COUNT(*) n30,
                 SUM(outcome='win') w30,
                 SUM(outcome='loss') l30,
                 ROUND(100.0 * SUM(outcome='win') /
                       NULLIF(SUM(outcome IN ('win','loss')), 0), 1) raw_wr30
          FROM room_color_outcomes
          WHERE msg_ts >= datetime('now','-30 days')
            AND outcome IN ('win','loss')
            AND color IN ('red','blue')
          GROUP BY room
        ),
        fired AS (
          SELECT lower(replace(
                   CASE
                     WHEN instr(coalesce(rooms_agreed,''), ',') > 0
                     THEN substr(rooms_agreed, 1, instr(rooms_agreed, ',') - 1)
                     ELSE coalesce(rooms_agreed, '')
                   END, '@', '')) room,
                 COUNT(*) f7,
                 SUM(outcome='win') fw7,
                 SUM(outcome='loss') fl7,
                 SUM(outcome='tie') ft7,
                 ROUND(100.0 * SUM(outcome='win') /
                       NULLIF(SUM(outcome IN ('win','loss')), 0), 1) fired_wr7
          FROM consensus_signals
          WHERE fired_at >= datetime('now','-7 days')
            AND outcome IN ('win','loss','tie')
          GROUP BY room
        )
        SELECT r.handle, r.is_muted, r.gale_tier, r.quarantine_until,
               COALESCE(msg.msg_n, 0) msg_n,
               msg.last_msg,
               COALESCE(msg.msg_7d, 0) msg_7d,
               COALESCE(msg.msg_30d, 0) msg_30d,
               COALESCE(raw.n30, 0) raw_n30,
               raw.raw_wr30,
               COALESCE(fired.f7, 0) fired_n7,
               fired.fired_wr7
        FROM r
        LEFT JOIN msg USING(room)
        LEFT JOIN raw USING(room)
        LEFT JOIN fired USING(room)
        ORDER BY r.is_muted, r.gale_tier, r.handle
        """
    ).fetchall()


def _classify(row: sqlite3.Row) -> RoomHealth:
    handle = row["handle"]
    handle_l = (handle or "").lower()
    flags: list[str] = []

    if not row["last_msg"] or int(row["msg_7d"] or 0) == 0:
        flags.append("STALE_NO_7D_MSG")
    if int(row["raw_n30"] or 0) >= 1000 and row["raw_wr30"] is not None and row["raw_wr30"] < 50:
        flags.append("RAW_30D_LT50")
    if int(row["fired_n7"] or 0) >= MIN_FIRED_N and row["fired_wr7"] is not None and row["fired_wr7"] < WEAK_FIRED_WR:
        flags.append("FIRED_7D_LT70")
    if any(token in handle_l for token in WRONG_GAME_NAME_TOKENS) and "bacbo" not in handle_l:
        flags.append("WRONG_GAME_NAME_RISK")

    is_muted = int(row["is_muted"] or 0)
    action = "KEEP"
    reason = "fresh_or_insufficient_negative_evidence"

    if is_muted:
        if (
            int(row["fired_n7"] or 0) >= RETEST_MIN_FIRED_N
            and row["fired_wr7"] is not None
            and row["fired_wr7"] >= RETEST_FIRED_WR
        ):
            action = "RETEST_MUTED"
            reason = f"muted_but_recent_fired_wr={row['fired_wr7']} n={row['fired_n7']}"
        elif int(row["msg_7d"] or 0) > 0 and row["raw_wr30"] is not None and row["raw_wr30"] >= 52:
            action = "RETEST_MUTED"
            reason = f"muted_but_fresh_raw_wr={row['raw_wr30']} n={row['raw_n30']}"
    else:
        if "WRONG_GAME_NAME_RISK" in flags:
            action = "MUTE_WRONG_GAME_RISK"
            reason = "handle_name_indicates_non_bacbo_game"
        elif "STALE_NO_7D_MSG" in flags:
            action = "MUTE_STALE"
            reason = f"no_messages_in_last_{STALE_DAYS}d"
        elif "FIRED_7D_LT70" in flags:
            action = "DOWNGRADE_WEAK"
            reason = f"fired_wr7={row['fired_wr7']} n={row['fired_n7']}"
        elif "RAW_30D_LT50" in flags and int(row["fired_n7"] or 0) < MIN_FIRED_N:
            action = "MUTE_RAW_WEAK"
            reason = f"raw_wr30={row['raw_wr30']} n={row['raw_n30']}"

    return RoomHealth(
        handle=handle,
        is_muted=is_muted,
        gale_tier=row["gale_tier"] or "",
        quarantine_until=row["quarantine_until"],
        msg_n=int(row["msg_n"] or 0),
        last_msg=row["last_msg"],
        msg_7d=int(row["msg_7d"] or 0),
        msg_30d=int(row["msg_30d"] or 0),
        raw_n30=int(row["raw_n30"] or 0),
        raw_wr30=row["raw_wr30"],
        fired_n7=int(row["fired_n7"] or 0),
        fired_wr7=row["fired_wr7"],
        flags=flags,
        action=action,
        reason=reason,
    )


def analyze_rooms(db_path: str = DB_PATH) -> list[RoomHealth]:
    with _connect(db_path) as conn:
        return [_classify(row) for row in _room_rows(conn)]


def summarize(rooms: Iterable[RoomHealth]) -> dict:
    rows = list(rooms)
    by_action: dict[str, int] = {}
    by_tier: dict[str, int] = {}
    for row in rows:
        by_action[row.action] = by_action.get(row.action, 0) + 1
        by_tier[row.gale_tier] = by_tier.get(row.gale_tier, 0) + 1
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_rooms": len(rows),
        "active_unmuted": sum(1 for row in rows if not row.is_muted),
        "muted": sum(1 for row in rows if row.is_muted),
        "by_action": dict(sorted(by_action.items())),
        "by_tier": dict(sorted(by_tier.items())),
    }


def save_report(rooms: list[RoomHealth], path: str = REPORT_PATH) -> dict:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    report = {
        "summary": summarize(rooms),
        "rooms": [asdict(row) for row in rooms],
    }
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    os.replace(tmp, path)
    return report


def apply_recommendations(rooms: list[RoomHealth], db_path: str = DB_PATH) -> dict:
    """Apply only conservative room-table changes.

    This does not delete anything. It mutes stale/wrong/weak active rooms and
    un-mutes RETEST_MUTED rooms into G3 shadow tier.
    """
    changed: list[dict] = []
    with _write_connect(db_path) as conn:
        for row in rooms:
            if row.action in {"MUTE_STALE", "MUTE_WRONG_GAME_RISK", "MUTE_RAW_WEAK"}:
                conn.execute("UPDATE rooms SET is_muted=1 WHERE handle=?", (row.handle,))
                changed.append({"handle": row.handle, "action": row.action, "reason": row.reason})
            elif row.action == "DOWNGRADE_WEAK":
                conn.execute(
                    "UPDATE rooms SET gale_tier='G3' WHERE handle=?",
                    (row.handle,),
                )
                changed.append({"handle": row.handle, "action": row.action, "reason": row.reason})
            elif row.action == "RETEST_MUTED":
                conn.execute(
                    "UPDATE rooms SET is_muted=0, gale_tier='G3', quarantine_until=NULL WHERE handle=?",
                    (row.handle,),
                )
                changed.append({"handle": row.handle, "action": row.action, "reason": row.reason})
        conn.commit()
    return {"changed": changed, "changed_count": len(changed)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate and clean Bac Bo rooms")
    parser.add_argument("--db", default=DB_PATH)
    parser.add_argument("--report", default=REPORT_PATH)
    parser.add_argument("--apply", action="store_true", help="apply conservative changes")
    args = parser.parse_args()

    rooms = analyze_rooms(args.db)
    report = save_report(rooms, args.report)
    print(json.dumps(report["summary"], indent=2))
    print(f"report={args.report}")

    if args.apply:
        result = apply_recommendations(rooms, args.db)
        print(json.dumps(result, indent=2))
    else:
        print("dry_run=true (use --apply to update rooms table)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
