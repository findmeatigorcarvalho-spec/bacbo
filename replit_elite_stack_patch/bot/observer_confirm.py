"""Record human-observed live round truth as first-class evidence.

The bot does not and must not attach itself to the live casino.  The human
operator watching the table is the legitimate observer for round truth, so this
module gives those confirmations the same schema, hashing, and audit weight as
any machine-captured source.

Usage (Pawtucket time is used for anything you type as local):

    python3 bot/observer_confirm.py --signal 2679 --actual blue \\
        --closed "2026-08-11 19:37:30" --card-before-round yes

    python3 bot/observer_confirm.py --signal 2680 --actual red --card-before-round no
"""
from __future__ import annotations

import argparse
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from card_timezone import PAWTUCKET_TZ
from chronology_evidence import append_event
from truth_verifier import ensure_schema

HERE = Path(__file__).resolve().parent
DB_PATH = HERE / "bacbo.db"

OBSERVER_SOURCE = "observer_human"
MATCH_METHOD = "observer_confirmed"
COLORS = ("blue", "red", "tie")


def _to_utc_iso(value: Optional[str]) -> Optional[str]:
    """Accept Pawtucket local text or ISO input; store UTC."""
    raw = (value or "").strip()
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        dt = datetime.strptime(raw[:19], "%Y-%m-%d %H:%M:%S")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=PAWTUCKET_TZ)
    return dt.astimezone(timezone.utc).isoformat()


def confirm(
    *,
    signal_id: int,
    actual_color: str,
    betting_closed_at: Optional[str] = None,
    resolved_at: Optional[str] = None,
    card_before_round: Optional[bool] = None,
    round_id: Optional[str] = None,
    note: str = "",
    db_path: Path = DB_PATH,
) -> dict[str, Any]:
    """Persist one human-confirmed round outcome and link it to a signal."""
    color = (actual_color or "").strip().lower()
    if color not in COLORS:
        raise ValueError(f"actual_color must be one of {COLORS}, got {actual_color!r}")

    round_key = round_id or f"observer:{int(signal_id)}"
    closed = _to_utc_iso(betting_closed_at)
    resolved = _to_utc_iso(resolved_at)

    event = append_event(
        "observer_round_confirmed",
        signal_id=int(signal_id),
        round_id=round_key,
        actual_color=color,
        betting_closed_at=closed,
        casino_resolved_at=resolved,
        card_before_round=card_before_round,
        note=note,
        observed_by="human_operator",
        evidence_level="HUMAN_OBSERVER_CONFIRMED",
    )

    if db_path.exists():
        ensure_schema(str(db_path))
        conn = sqlite3.connect(str(db_path), timeout=60)
        try:
            conn.execute(
                """
                INSERT INTO casino_round_results
                    (source, round_id, betting_closed_at, resolved_at, actual_color, raw_payload)
                VALUES (?,?,?,?,?,?)
                ON CONFLICT(source, round_id) DO UPDATE SET
                    betting_closed_at=COALESCE(excluded.betting_closed_at, betting_closed_at),
                    resolved_at=COALESCE(excluded.resolved_at, resolved_at),
                    actual_color=excluded.actual_color,
                    raw_payload=excluded.raw_payload
                """,
                (OBSERVER_SOURCE, round_key, closed, resolved, color, event["event_hash"]),
            )
            conn.execute(
                """
                INSERT INTO signal_truth_matches
                    (consensus_id, casino_round_id, match_method, casino_actual_color,
                     verified_outcome)
                VALUES (?,?,?,?,?)
                ON CONFLICT(consensus_id, match_method) DO UPDATE SET
                    casino_round_id=excluded.casino_round_id,
                    casino_actual_color=excluded.casino_actual_color,
                    verified_outcome=excluded.verified_outcome,
                    matched_at=CURRENT_TIMESTAMP
                """,
                (int(signal_id), round_key, MATCH_METHOD, color, "unknown"),
            )
            conn.commit()
        finally:
            conn.close()
        event["persisted_to_db"] = True
    else:
        event["persisted_to_db"] = False
    return event


def main() -> int:
    parser = argparse.ArgumentParser(description="Record human-observed round truth")
    parser.add_argument("--signal", type=int, required=True)
    parser.add_argument("--actual", required=True, choices=list(COLORS))
    parser.add_argument("--closed", help="Betting close time (Pawtucket local or ISO)")
    parser.add_argument("--resolved", help="Round result time (Pawtucket local or ISO)")
    parser.add_argument("--round-id")
    parser.add_argument("--card-before-round", choices=["yes", "no"])
    parser.add_argument("--note", default="")
    parser.add_argument("--db", default=str(DB_PATH))
    args = parser.parse_args()

    before = None
    if args.card_before_round:
        before = args.card_before_round == "yes"

    event = confirm(
        signal_id=args.signal,
        actual_color=args.actual,
        betting_closed_at=args.closed,
        resolved_at=args.resolved,
        card_before_round=before,
        round_id=args.round_id,
        note=args.note,
        db_path=Path(args.db),
    )
    print(
        "OBSERVER_CONFIRMED",
        f"signal={event['signal_id']}",
        f"actual={event['actual_color']}",
        f"db={event['persisted_to_db']}",
        f"hash={event['event_hash'][:12]}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
