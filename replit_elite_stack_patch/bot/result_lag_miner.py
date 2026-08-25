"""
result_lag_miner.py — mine repeat/lag patterns from resolved Bac Bo outcomes.

User-observed hypothesis:
    "the same exact result often comes ~5 rounds later, and most times the
     opposite color appears right before that result."

This module converts resolved consensus signals into an actual-color stream:

    signal BLUE + win  -> actual BLUE
    signal BLUE + loss -> actual RED
    signal RED  + win  -> actual RED
    signal RED  + loss -> actual BLUE
    tie outcome        -> TIE

Then it measures lags 1..12:
    base[i] == base[i + lag]
    and base[i + lag - 1] == opposite(base[i + lag])

It writes bot/data/result_lag_patterns.json and is safe/read-only.
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
REPORT_PATH = os.path.join(HERE, "data", "result_lag_patterns.json")

OPP = {"blue": "red", "red": "blue"}


@dataclass
class LagPattern:
    lag: int
    samples: int
    repeat_count: int
    repeat_pct: float
    opposite_before_repeat_count: int
    opposite_before_repeat_pct: float
    repeat_wr_if_bet_repeat: float
    examples: list[dict]


def _connect(db_path: str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=20)
    conn.row_factory = sqlite3.Row
    return conn


def _actual_color(signal_color: str, outcome: str) -> Optional[str]:
    color = (signal_color or "").lower()
    outcome = (outcome or "").lower()
    if outcome == "tie":
        return "tie"
    if color not in OPP:
        return None
    if outcome == "win":
        return color
    if outcome == "loss":
        return OPP[color]
    return None


def load_actual_stream(db_path: str = DB_PATH, days: int = 30, limit: int = 20000) -> list[dict]:
    with _connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT id, color, outcome, signal_kind, COALESCE(source_floor,'LIVE') source_floor,
                   COALESCE(resolved_at, fired_at) ts
            FROM consensus_signals
            WHERE fired_at >= datetime('now', ?)
              AND outcome IN ('win','loss','tie')
              AND color IN ('red','blue')
            ORDER BY COALESCE(resolved_at, fired_at) ASC, id ASC
            LIMIT ?
            """,
            (f"-{int(days)} days", int(limit)),
        ).fetchall()
    stream: list[dict] = []
    for row in rows:
        actual = _actual_color(row["color"], row["outcome"])
        if actual is None:
            continue
        stream.append(
            {
                "id": row["id"],
                "ts": row["ts"],
                "signal_color": row["color"],
                "outcome": row["outcome"],
                "actual": actual,
                "signal_kind": row["signal_kind"],
                "source_floor": row["source_floor"],
            }
        )
    return stream


def mine_lags(
    db_path: str = DB_PATH,
    days: int = 30,
    max_lag: int = 12,
    include_tie: bool = False,
) -> list[LagPattern]:
    stream = load_actual_stream(db_path=db_path, days=days)
    if not include_tie:
        stream = [row for row in stream if row["actual"] in OPP]

    out: list[LagPattern] = []
    n = len(stream)
    for lag in range(1, int(max_lag) + 1):
        samples = max(0, n - lag)
        if samples <= 0:
            out.append(LagPattern(lag, 0, 0, 0.0, 0, 0.0, 0.0, []))
            continue

        repeat = 0
        opposite_before_repeat = 0
        examples: list[dict] = []

        for i in range(samples):
            base = stream[i]
            target = stream[i + lag]
            if base["actual"] == target["actual"]:
                repeat += 1
                prev = stream[i + lag - 1] if lag >= 1 else None
                if (
                    prev
                    and target["actual"] in OPP
                    and prev["actual"] == OPP[target["actual"]]
                ):
                    opposite_before_repeat += 1
                    if len(examples) < 10:
                        examples.append(
                            {
                                "base_id": base["id"],
                                "target_id": target["id"],
                                "base_ts": base["ts"],
                                "target_ts": target["ts"],
                                "actual": target["actual"],
                                "previous_actual": prev["actual"],
                                "lag": lag,
                            }
                        )

        repeat_pct = round(100.0 * repeat / samples, 2)
        opposite_pct = round(100.0 * opposite_before_repeat / max(repeat, 1), 2)
        out.append(
            LagPattern(
                lag=lag,
                samples=samples,
                repeat_count=repeat,
                repeat_pct=repeat_pct,
                opposite_before_repeat_count=opposite_before_repeat,
                opposite_before_repeat_pct=opposite_pct,
                repeat_wr_if_bet_repeat=repeat_pct,
                examples=examples,
            )
        )

    out.sort(key=lambda row: (row.lag != 5, -row.opposite_before_repeat_pct, -row.repeat_pct))
    return out


def save_report(
    db_path: str = DB_PATH,
    days: int = 30,
    max_lag: int = 12,
    path: str = REPORT_PATH,
) -> dict:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    stream = load_actual_stream(db_path=db_path, days=days)
    patterns = mine_lags(db_path=db_path, days=days, max_lag=max_lag)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "days": int(days),
        "stream_n": len(stream),
        "hypothesis": "same actual color repeats around lag 5, often with opposite color immediately before target",
        "patterns": [asdict(row) for row in patterns],
        "best_lag": asdict(max(patterns, key=lambda row: (row.repeat_pct, row.opposite_before_repeat_pct))) if patterns else None,
        "lag5": asdict(next((row for row in patterns if row.lag == 5), patterns[0])) if patterns else None,
    }
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    os.replace(tmp, path)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Mine Bac Bo result lag/repeat patterns")
    parser.add_argument("--db", default=DB_PATH)
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--max-lag", type=int, default=12)
    parser.add_argument("--report", default=REPORT_PATH)
    args = parser.parse_args()
    report = save_report(args.db, args.days, args.max_lag, args.report)
    print(json.dumps(
        {
            "generated_at": report["generated_at"],
            "days": report["days"],
            "stream_n": report["stream_n"],
            "lag5": report["lag5"],
            "best_lag": report["best_lag"],
        },
        indent=2,
        ensure_ascii=False,
    ))
    print(f"report={args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
