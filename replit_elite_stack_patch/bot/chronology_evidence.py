"""Durable FIRE/RESULT chronology and provenance evidence.

This module does not infer chronology from card text.  It stores distinct facts:
DB fire/resolve times, Telegram delivery times/IDs, and direct casino round
close/result times when available.  Claims are classified by the strongest
evidence actually present, so future agents do not depend on chat memory.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DB_PATH = HERE / "bacbo.db"
EVENTS = DATA / "chronology_evidence.jsonl"
REPORT = DATA / "chronology_evidence_report.json"
PAIR_PACK = DATA / "museum_chrono_all_pairs.json"


def _iso(value: Any) -> Optional[str]:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        raw = str(value).strip()
        if not raw:
            return None
        # DB UTC-naive and Telegram aware ISO values are both accepted.
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            try:
                dt = datetime.strptime(raw[:19], "%Y-%m-%d %H:%M:%S")
            except ValueError:
                return raw
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def _epoch(value: Any) -> Optional[float]:
    normalized = _iso(value)
    if not normalized:
        return None
    try:
        return datetime.fromisoformat(normalized.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def append_event(event_type: str, **facts: Any) -> dict[str, Any]:
    """Append one immutable evidence event."""
    DATA.mkdir(parents=True, exist_ok=True)
    row = {
        "schema_version": 1,
        "event_type": event_type,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "pid": os.getpid(),
        **facts,
    }
    stable = json.dumps(
        {k: v for k, v in row.items() if k not in {"recorded_at", "pid", "event_hash"}},
        sort_keys=True,
        ensure_ascii=False,
        default=str,
    )
    row["event_hash"] = hashlib.sha256(stable.encode("utf-8")).hexdigest()
    with EVENTS.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
    return row


def record_result_delivery(
    *,
    signal_id: int,
    telegram_message_id: int | None,
    telegram_date: Any,
    fired_at: Any,
    resolved_at: Any,
    outcome: str,
    predicted_color: str,
    actual_color: str,
    peer: str,
    reply_to: int | None,
) -> dict[str, Any]:
    """Record the actual Telegram RESULT delivery separately from DB resolution."""
    result_post = _iso(telegram_date)
    resolved = _iso(resolved_at)
    post_ts, resolve_ts = _epoch(result_post), _epoch(resolved)
    post_minus_resolve = (
        round(post_ts - resolve_ts, 3)
        if post_ts is not None and resolve_ts is not None
        else None
    )
    return append_event(
        "result_delivery",
        signal_id=int(signal_id),
        telegram_message_id=int(telegram_message_id) if telegram_message_id else None,
        telegram_post_at=result_post,
        db_fired_at=_iso(fired_at),
        db_resolved_at=resolved,
        post_minus_resolve_secs=post_minus_resolve,
        outcome=outcome,
        predicted_color=predicted_color,
        actual_color=actual_color,
        peer=peer,
        reply_to=int(reply_to) if reply_to else None,
        evidence_level="TELEGRAM_DELIVERY_PLUS_BOT_DB",
    )


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    return bool(
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
        ).fetchone()
    )


def _db_report(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"available": False, "path": str(path)}
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        tables = {
            r[0]
            for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        out: dict[str, Any] = {
            "available": True,
            "path": str(path),
            "tables": sorted(tables),
        }
        if "consensus_signals" in tables:
            row = conn.execute(
                """
                SELECT COUNT(*) total,
                       SUM(outcome IN ('win','loss','tie')) resolved,
                       SUM(outcome='win') wins,
                       SUM(outcome='loss') losses,
                       SUM(outcome='tie') ties,
                       SUM(secs_to_result >= 20) fire_lead_ge_20s,
                       SUM(secs_to_result >= 5 AND secs_to_result < 20) fire_lead_5_20s,
                       SUM(secs_to_result < 5) fire_lead_lt_5s,
                       ROUND(AVG(secs_to_result),3) avg_fire_to_resolve_secs
                FROM consensus_signals
                """
            ).fetchone()
            out["consensus_signals"] = dict(row)
        direct = 0
        if "casino_round_results" in tables:
            direct = int(
                conn.execute("SELECT COUNT(*) FROM casino_round_results").fetchone()[0]
            )
        matches = 0
        if "signal_truth_matches" in tables:
            matches = int(
                conn.execute("SELECT COUNT(*) FROM signal_truth_matches").fetchone()[0]
            )
        out["direct_casino_rows"] = direct
        out["direct_signal_matches"] = matches
        return out
    finally:
        conn.close()


def _pair_report(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"available": False, "path": str(path)}
    pack = json.loads(path.read_text(encoding="utf-8"))
    pairs = pack.get("pairs") or []
    gaps = [float(p["gap_secs"]) for p in pairs if p.get("gap_secs") is not None]
    return {
        "available": True,
        "path": str(path),
        "total_complete_pairs_claimed": int(pack.get("total_complete_pairs") or 0),
        "pairs_materialized_in_pack": len(pairs),
        "pre_stack_complete_pairs": int(pack.get("pre_stack_complete_pairs") or 0),
        "first_stack_marker_at": pack.get("first_stack_marker_at"),
        "telegram_pair_gap": {
            "min_secs": min(gaps) if gaps else None,
            "max_secs": max(gaps) if gaps else None,
            "avg_secs": round(sum(gaps) / len(gaps), 3) if gaps else None,
            "nonpositive_count": sum(1 for x in gaps if x <= 0),
        },
        "note": (
            "FIRE and RESULT Telegram message chronology; not direct casino "
            "betting-close chronology unless matched to casino_round_results."
        ),
    }


def _delivery_report(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"available": False, "events": 0}
    rows = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        try:
            row = json.loads(line)
        except Exception:
            continue
        if row.get("event_type") == "result_delivery":
            rows.append(row)
    deltas = [
        float(r["post_minus_resolve_secs"])
        for r in rows
        if r.get("post_minus_resolve_secs") is not None
    ]
    return {
        "available": True,
        "events": len(rows),
        "result_post_before_db_resolve": sum(1 for x in deltas if x < 0),
        "result_post_at_or_after_db_resolve": sum(1 for x in deltas if x >= 0),
        "min_post_minus_resolve_secs": min(deltas) if deltas else None,
        "max_post_minus_resolve_secs": max(deltas) if deltas else None,
    }


def build_report(db_path: Path = DB_PATH) -> dict[str, Any]:
    db = _db_report(db_path)
    pairs = _pair_report(PAIR_PACK)
    deliveries = _delivery_report(EVENTS)
    direct = int(db.get("direct_casino_rows") or 0)
    matched = int(db.get("direct_signal_matches") or 0)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "purpose": "Durable chronology proof; facts separated by source and timestamp.",
        "sources": {
            "bot_database": db,
            "historical_telegram_pairs": pairs,
            "live_telegram_delivery_ledger": deliveries,
        },
        "strongest_current_evidence": (
            "DIRECT_CASINO_MATCHED"
            if direct and matched
            else "BOT_DB_AND_TELEGRAM_CHRONOLOGY"
        ),
        "claims": {
            "fire_precedes_bot_resolution": (
                "MEASURED_BY_SECS_TO_RESULT"
                if db.get("consensus_signals")
                else "NOT_AVAILABLE_LOCALLY"
            ),
            "result_card_delivery_precedes_db_resolution": (
                "OBSERVED"
                if deliveries.get("result_post_before_db_resolve")
                else "NOT_OBSERVED_IN_DELIVERY_LEDGER"
            ),
            "signal_precedes_direct_casino_betting_close": (
                "MEASURABLE" if direct and matched else "DIRECT_CAPTURE_NOT_POPULATED"
            ),
        },
        "required_next_capture": [
            "Direct casino round_id, betting_closed_at, and actual result.",
            "Telegram FIRE delivery message_id/date for every canonical signal.",
            "Telegram RESULT delivery message_id/date for every canonical signal.",
            "One canonical (peer, round_key) call, not duplicate DB/message rows.",
        ],
    }


def save_report(db_path: Path = DB_PATH, path: Path = REPORT) -> dict[str, Any]:
    DATA.mkdir(parents=True, exist_ok=True)
    report = build_report(db_path)
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Build chronology evidence report")
    parser.add_argument("--db", default=str(DB_PATH))
    parser.add_argument("--report", default=str(REPORT))
    args = parser.parse_args()
    report = save_report(Path(args.db), Path(args.report))
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
