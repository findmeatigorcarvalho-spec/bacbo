"""Materialize four-clock chronology evidence per consensus signal.

Clocks remain separate:
  A source observation → DB FIRE
  B DB FIRE → bot resolution
  C Telegram FIRE → Telegram RESULT delivery
  D casino betting close / actual result

The decisive pre-close metric is Clock C RESULT delivery minus Clock D betting
close.  Missing Clock D yields INCONCLUSIVE_NO_CASINO, never a guessed verdict.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from chronology_evidence import EVENTS, _epoch, _iso

HERE = Path(__file__).resolve().parent
DB_PATH = HERE / "bacbo.db"
REPORT = HERE / "data" / "chronology_integrity_audit.json"

SCHEMA = """
CREATE TABLE IF NOT EXISTS chrono_audit_signals (
    consensus_id INTEGER PRIMARY KEY,
    signal_kind TEXT,
    source_floor TEXT,
    predicted_color TEXT,
    bot_outcome TEXT,
    inferred_actual_color TEXT,
    rooms_agreed TEXT,
    db_fired_at TEXT,
    db_resolved_at TEXT,
    db_fire_to_resolve_secs REAL,
    tg_fire_peer TEXT,
    tg_fire_message_id INTEGER,
    tg_fire_post_at TEXT,
    tg_result_peer TEXT,
    tg_result_message_id INTEGER,
    tg_result_post_at TEXT,
    tg_fire_to_result_secs REAL,
    tg_result_minus_resolve_secs REAL,
    casino_source TEXT,
    casino_round_id TEXT,
    casino_betting_closed_at TEXT,
    casino_resolved_at TEXT,
    casino_actual_color TEXT,
    tg_result_minus_close_secs REAL,
    db_resolve_minus_close_secs REAL,
    evidence_tier TEXT NOT NULL,
    integrity_class TEXT NOT NULL,
    integrity_reason TEXT,
    matched_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_chrono_integrity
ON chrono_audit_signals(integrity_class, evidence_tier);
CREATE INDEX IF NOT EXISTS idx_chrono_casino_round
ON chrono_audit_signals(casino_round_id);
"""


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    return bool(
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
        ).fetchone()
    )


def _actual(predicted: str, outcome: str) -> str:
    p, o = (predicted or "").lower(), (outcome or "").lower()
    if o == "tie":
        return "tie"
    if o == "win":
        return p
    if o == "loss":
        return "red" if p == "blue" else "blue" if p == "red" else "unknown"
    return "unknown"


def _events_by_signal(path: Path) -> dict[int, dict[str, dict[str, Any]]]:
    out: dict[int, dict[str, dict[str, Any]]] = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        try:
            row = json.loads(line)
            sid = int(row.get("signal_id"))
        except Exception:
            continue
        slot = out.setdefault(sid, {})
        event_type = str(row.get("event_type") or "")
        if event_type == "result_delivery":
            slot["result"] = row
        elif event_type == "telegram_outgoing_observed":
            role = str(row.get("role") or "").upper()
            if role == "FIRE":
                slot["fire"] = row
            elif role == "RESULT":
                slot["result_observed"] = row
    return out


def _truth_by_signal(conn: sqlite3.Connection) -> dict[int, dict[str, Any]]:
    if not (
        _table_exists(conn, "signal_truth_matches")
        and _table_exists(conn, "casino_round_results")
    ):
        return {}
    rows = conn.execute(
        """
        SELECT m.consensus_id, m.casino_round_id, m.match_method,
               c.source casino_source, c.betting_closed_at,
               c.resolved_at casino_resolved_at, c.actual_color casino_actual_color
        FROM signal_truth_matches m
        JOIN casino_round_results c ON c.round_id = m.casino_round_id
        """
    ).fetchall()
    return {int(r["consensus_id"]): dict(r) for r in rows}


def _delta(a: Any, b: Any) -> Optional[float]:
    aa, bb = _epoch(a), _epoch(b)
    if aa is None or bb is None:
        return None
    return round(aa - bb, 3)


def _classify(row: dict[str, Any], grace: float) -> tuple[str, str, str]:
    has_db = bool(row.get("db_fired_at"))
    has_tg = bool(row.get("tg_fire_post_at") or row.get("tg_result_post_at"))
    has_casino = bool(row.get("casino_betting_closed_at"))
    matched = bool(row.get("casino_round_id"))
    tier = (
        "E5_CASINO_MATCHED"
        if matched
        else "E4_CASINO_DIRECT"
        if has_casino
        else "E2_BOT_DB_PLUS_TG"
        if has_db and has_tg
        else "E1_BOT_DB_ONLY"
        if has_db
        else "E0_INCOMPLETE"
    )
    if not has_casino:
        return tier, "INCONCLUSIVE_NO_CASINO", "No matched direct casino betting-close time."
    if not row.get("tg_result_post_at"):
        return tier, "INCONCLUSIVE_NO_TG_RESULT", "No Telegram RESULT delivery timestamp."
    tg_close = row.get("tg_result_minus_close_secs")
    db_close = row.get("db_resolve_minus_close_secs")
    tg_resolve = row.get("tg_result_minus_resolve_secs")
    if tg_close is not None and tg_close < -grace:
        return tier, "RESULT_DELIVERED_BEFORE_CLOSE", f"RESULT delivery {abs(tg_close):.3f}s before close."
    if db_close is not None and db_close < -grace:
        return tier, "DB_RESOLVED_BEFORE_CLOSE", f"Bot resolved {abs(db_close):.3f}s before close."
    if tg_resolve is not None and tg_resolve < -grace:
        return tier, "RESULT_DELIVERED_BEFORE_DB_RESOLVE", f"Telegram RESULT {abs(tg_resolve):.3f}s before DB resolve."
    return tier, "RESULT_AT_OR_AFTER_CLOSE", "No pre-close RESULT delivery at configured grace."


def materialize(db_path: Path, grace: float = 2.0) -> dict[str, Any]:
    if not db_path.exists():
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "db_available": False,
            "db_path": str(db_path),
            "rows": 0,
        }
    conn = sqlite3.connect(str(db_path), timeout=60)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    events = _events_by_signal(EVENTS)
    truth = _truth_by_signal(conn)
    signals = conn.execute(
        """
        SELECT id, fired_at, resolved_at, secs_to_result, outcome, color,
               signal_kind, source_floor, rooms_agreed
        FROM consensus_signals
        WHERE outcome IN ('win','loss','tie')
        """
    ).fetchall()
    counts: Counter[str] = Counter()
    tiers: Counter[str] = Counter()
    examples: list[dict[str, Any]] = []
    for signal in signals:
        sid = int(signal["id"])
        ev = events.get(sid, {})
        fire = ev.get("fire") or {}
        result = ev.get("result") or ev.get("result_observed") or {}
        direct = truth.get(sid, {})
        row: dict[str, Any] = {
            "consensus_id": sid,
            "signal_kind": signal["signal_kind"],
            "source_floor": signal["source_floor"],
            "predicted_color": signal["color"],
            "bot_outcome": signal["outcome"],
            "inferred_actual_color": _actual(signal["color"], signal["outcome"]),
            "rooms_agreed": signal["rooms_agreed"],
            "db_fired_at": _iso(signal["fired_at"]),
            "db_resolved_at": _iso(signal["resolved_at"]),
            "db_fire_to_resolve_secs": signal["secs_to_result"],
            "tg_fire_peer": fire.get("peer"),
            "tg_fire_message_id": fire.get("telegram_message_id"),
            "tg_fire_post_at": _iso(fire.get("telegram_post_at")),
            "tg_result_peer": result.get("peer"),
            "tg_result_message_id": result.get("telegram_message_id"),
            "tg_result_post_at": _iso(result.get("telegram_post_at")),
            "casino_source": direct.get("casino_source"),
            "casino_round_id": direct.get("casino_round_id"),
            "casino_betting_closed_at": _iso(direct.get("betting_closed_at")),
            "casino_resolved_at": _iso(direct.get("casino_resolved_at")),
            "casino_actual_color": direct.get("casino_actual_color"),
        }
        row["tg_fire_to_result_secs"] = _delta(
            row["tg_result_post_at"], row["tg_fire_post_at"]
        )
        row["tg_result_minus_resolve_secs"] = _delta(
            row["tg_result_post_at"], row["db_resolved_at"]
        )
        row["tg_result_minus_close_secs"] = _delta(
            row["tg_result_post_at"], row["casino_betting_closed_at"]
        )
        row["db_resolve_minus_close_secs"] = _delta(
            row["db_resolved_at"], row["casino_betting_closed_at"]
        )
        tier, integrity, reason = _classify(row, grace)
        row.update(
            evidence_tier=tier,
            integrity_class=integrity,
            integrity_reason=reason,
        )
        counts[integrity] += 1
        tiers[tier] += 1
        if integrity not in {"INCONCLUSIVE_NO_CASINO", "RESULT_AT_OR_AFTER_CLOSE"}:
            examples.append({k: row[k] for k in (
                "consensus_id", "signal_kind", "predicted_color", "bot_outcome",
                "db_fired_at", "db_resolved_at", "tg_fire_post_at",
                "tg_result_post_at", "casino_round_id",
                "casino_betting_closed_at", "tg_result_minus_close_secs",
                "integrity_class", "integrity_reason",
            )})
        columns = list(row)
        conn.execute(
            f"""
            INSERT INTO chrono_audit_signals ({','.join(columns)})
            VALUES ({','.join('?' for _ in columns)})
            ON CONFLICT(consensus_id) DO UPDATE SET
            {','.join(f'{c}=excluded.{c}' for c in columns if c != 'consensus_id')},
            matched_at=CURRENT_TIMESTAMP
            """,
            [row[c] for c in columns],
        )
    conn.commit()
    conn.close()
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "db_available": True,
        "db_path": str(db_path),
        "rows": len(signals),
        "grace_secs": grace,
        "counts_by_evidence_tier": dict(tiers),
        "counts_by_integrity_class": dict(counts),
        "notable_examples": examples[:100],
        "decisive_metric": "tg_result_post_at - casino_betting_closed_at",
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Materialize chronology integrity evidence")
    parser.add_argument("--db", default=str(DB_PATH))
    parser.add_argument("--grace", type=float, default=2.0)
    args = parser.parse_args()
    print(json.dumps(materialize(Path(args.db), args.grace), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
