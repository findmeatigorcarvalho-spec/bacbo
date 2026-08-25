"""
truth_verifier.py — distinguish DB/Telegram truth from direct casino truth.

Current app reality:
* consensus_signals outcomes are verified against the bot's parsed outcome flow.
* there is no active direct Twin225 dice-result table in the extracted DB.
* actual color can be reconstructed from signal color + win/loss, but that is
  still inferred from Telegram/bot reconciliation unless direct casino rows exist.

This module creates a direct-casino schema for future capture and writes a report
showing exactly how much of the current data is direct vs inferred.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
from datetime import datetime, timezone


HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(HERE, "bacbo.db")
REPORT_PATH = os.path.join(HERE, "data", "truth_verification_report.json")


DIRECT_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS casino_round_results (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    source              TEXT DEFAULT 'twin225',
    round_id            TEXT,
    observed_at         TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    betting_closed_at   TEXT,
    resolved_at         TEXT,
    player_total        INTEGER,
    banker_total        INTEGER,
    actual_color        TEXT CHECK(actual_color IN ('blue','red','tie')),
    raw_payload         TEXT,
    UNIQUE(source, round_id)
)
"""


MATCH_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS signal_truth_matches (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    consensus_id        INTEGER NOT NULL,
    casino_round_id     TEXT,
    match_method        TEXT NOT NULL,
    signal_color        TEXT,
    casino_actual_color TEXT CHECK(casino_actual_color IN ('blue','red','tie')),
    bot_outcome         TEXT,
    verified_outcome    TEXT CHECK(verified_outcome IN ('win','loss','tie','unknown')),
    signal_before_close_secs REAL,
    matched_at          TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(consensus_id, match_method)
)
"""


def _connect(db_path: str = DB_PATH, write: bool = False) -> sqlite3.Connection:
    if write:
        conn = sqlite3.connect(db_path, timeout=20)
    else:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=20)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=12000")
    return conn


def ensure_schema(db_path: str = DB_PATH) -> None:
    with _connect(db_path, write=True) as conn:
        conn.execute(DIRECT_TABLE_SQL)
        conn.execute(MATCH_TABLE_SQL)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_casino_round_observed ON casino_round_results(observed_at DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_truth_matches_consensus ON signal_truth_matches(consensus_id)")
        conn.commit()


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (name,),
    ).fetchone()
    return bool(row)


def build_report(db_path: str = DB_PATH, days: int = 7) -> dict:
    # Create schema if possible; do not fail report if DB is read-only.
    try:
        ensure_schema(db_path)
    except Exception:
        pass

    with _connect(db_path, write=False) as conn:
        direct_exists = _table_exists(conn, "casino_round_results")
        match_exists = _table_exists(conn, "signal_truth_matches")

        direct_count = 0
        direct_recent = 0
        if direct_exists:
            direct_count = conn.execute("SELECT COUNT(*) FROM casino_round_results").fetchone()[0]
            direct_recent = conn.execute(
                "SELECT COUNT(*) FROM casino_round_results WHERE observed_at >= datetime('now', ?)",
                (f"-{int(days)} days",),
            ).fetchone()[0]

        match_count = 0
        if match_exists:
            match_count = conn.execute("SELECT COUNT(*) FROM signal_truth_matches").fetchone()[0]

        sig = conn.execute(
            """
            SELECT COUNT(*) total,
                   SUM(outcome='win') wins,
                   SUM(outcome='loss') losses,
                   SUM(outcome='tie') ties,
                   SUM(outcome='pending') pending,
                   SUM(secs_to_result >= 20) early_20s,
                   ROUND(AVG(secs_to_result), 1) avg_secs
            FROM consensus_signals
            WHERE fired_at >= datetime('now', ?)
            """,
            (f"-{int(days)} days",),
        ).fetchone()

        inferred_actual = conn.execute(
            """
            SELECT COUNT(*) n
            FROM consensus_signals
            WHERE fired_at >= datetime('now', ?)
              AND outcome IN ('win','loss','tie')
              AND color IN ('red','blue')
            """,
            (f"-{int(days)} days",),
        ).fetchone()["n"]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "days": int(days),
        "truth_levels": {
            "direct_casino_rows_total": int(direct_count or 0),
            "direct_casino_rows_recent": int(direct_recent or 0),
            "signal_truth_matches_total": int(match_count or 0),
            "inferred_from_bot_db_recent": int(inferred_actual or 0),
        },
        "consensus_recent": {
            "total": int(sig["total"] or 0),
            "wins": int(sig["wins"] or 0),
            "losses": int(sig["losses"] or 0),
            "ties": int(sig["ties"] or 0),
            "pending": int(sig["pending"] or 0),
            "early_20s": int(sig["early_20s"] or 0),
            "avg_secs_to_result": sig["avg_secs"],
        },
        "verdict": (
            "DIRECT_CASINO_VERIFIED"
            if direct_recent
            else "BOT_DB_INFERRED_ONLY"
        ),
        "required_to_confirm_100pct_claim": [
            "Capture Twin225 round_id/player_total/banker_total/actual_color directly.",
            "Store every direct result in casino_round_results.",
            "Match consensus_signals.id to casino_round_results.round_id before counting verified WR.",
            "Require signal_time < betting_closed_at for early-result oracle claims.",
        ],
    }


def save_report(db_path: str = DB_PATH, days: int = 7, path: str = REPORT_PATH) -> dict:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    report = build_report(db_path, days)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    os.replace(tmp, path)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Report direct-vs-inferred truth status")
    parser.add_argument("--db", default=DB_PATH)
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--report", default=REPORT_PATH)
    parser.add_argument("--ensure-schema", action="store_true")
    args = parser.parse_args()
    if args.ensure_schema:
        ensure_schema(args.db)
    report = save_report(args.db, args.days, args.report)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"report={args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
