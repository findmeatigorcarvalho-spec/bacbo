"""
legacy_peak_355.py - Pawtucket 3:55am legacy/oracle window miner.

This keeps the special old config visible without blindly trusting it.
It mines signals fired around 3:30-3:59am America/New_York time and emits
candidate keys that the live policy can tag with a special warning.

Output:
  bot/data/legacy_peak_355_report.json
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, time as dtime, timezone
from typing import Any
from zoneinfo import ZoneInfo


HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(HERE, "bacbo.db")
REPORT_PATH = os.path.join(HERE, "data", "legacy_peak_355_report.json")
TZ_NAME = "America/New_York"


@dataclass
class LegacyCell:
    key_type: str
    key: str
    source_floor: str
    signal_kind: str
    color: str
    room: str | None
    n: int
    wins: int
    losses: int
    ties: int
    wr: float | None
    g0_wr: float | None
    avg_secs: float | None
    legacy_tier: str
    warning: str


def _connect(db_path: str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def _norm_room(raw: str | None) -> str:
    room = (raw or "").split(",")[0].strip().lstrip("@").lower()
    return room


def _parse_utc(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).strip().replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _in_window(local_dt: datetime, start: dtime, end: dtime) -> bool:
    current = local_dt.time().replace(second=0, microsecond=0)
    return start <= current <= end


def _pct(num: int, den: int) -> float | None:
    if den <= 0:
        return None
    return round(100.0 * num / den, 2)


def _tier(n: int, wr: float | None, g0_wr: float | None, avg_secs: float | None) -> str:
    wr = wr or 0.0
    g0 = g0_wr if g0_wr is not None else wr
    secs = avg_secs if avg_secs is not None else 999999.0
    if n >= 20 and wr >= 92 and g0 >= 90 and secs <= 120:
        return "LEGACY_ORACLE_CANDIDATE"
    if n >= 10 and wr >= 85 and g0 >= 80:
        return "LEGACY_WATCH"
    if n >= 5 and wr >= 75:
        return "LEGACY_SHADOW"
    return "LEGACY_ARCHIVE"


def _warning(tier: str) -> str:
    if tier == "LEGACY_ORACLE_CANDIDATE":
        return (
            "LEGACY_355_PAWTUCKET: old 3:55am config match; possible early G0/offset edge. "
            "Use G0-only unless direct Twin225 truth confirms pre-bet timing."
        )
    if tier == "LEGACY_WATCH":
        return (
            "LEGACY_355_PAWTUCKET WATCH: similar to old 3:55am config, but not fully proven. "
            "Treat as warning/boost, not guaranteed truth."
        )
    return "LEGACY_355_PAWTUCKET SHADOW: archived old-window pattern; learn only."


def _make_cell(key_type: str, key: str, rows: list[sqlite3.Row]) -> LegacyCell:
    wins = sum(1 for r in rows if r["outcome"] == "win")
    losses = sum(1 for r in rows if r["outcome"] == "loss")
    ties = sum(1 for r in rows if r["outcome"] == "tie")
    resolved = wins + losses
    g0 = sum(1 for r in rows if r["outcome"] == "win" and int(r["won_at_gale"] or 0) == 0)
    secs_values = [float(r["secs_to_result"]) for r in rows if r["secs_to_result"] is not None]
    avg_secs = round(sum(secs_values) / len(secs_values), 1) if secs_values else None
    wr = _pct(wins, resolved)
    g0_wr = _pct(g0, resolved)
    first = rows[0]
    tier = _tier(len(rows), wr, g0_wr, avg_secs)
    return LegacyCell(
        key_type=key_type,
        key=key,
        source_floor=str(first["source_floor"] or "LIVE").upper(),
        signal_kind=str(first["signal_kind"] or "").upper(),
        color=str(first["color"] or "").lower(),
        room=_norm_room(first["rooms_agreed"]) or None,
        n=len(rows),
        wins=wins,
        losses=losses,
        ties=ties,
        wr=wr,
        g0_wr=g0_wr,
        avg_secs=avg_secs,
        legacy_tier=tier,
        warning=_warning(tier),
    )


def build_report(
    db_path: str = DB_PATH,
    start: str = "03:30",
    end: str = "03:59",
    tz_name: str = TZ_NAME,
    min_n: int = 5,
) -> dict[str, Any]:
    start_time = dtime.fromisoformat(start)
    end_time = dtime.fromisoformat(end)
    tz = ZoneInfo(tz_name)

    # Pull only likely UTC hours for the local 03:xx window. This handles both
    # daylight saving and standard time without scanning the whole table.
    with _connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT source_floor, signal_kind, color, rooms_agreed, fired_at,
                   outcome, won_at_gale, secs_to_result
            FROM consensus_signals
            WHERE outcome IN ('win','loss','tie')
              AND color IN ('blue','red')
              AND CAST(strftime('%H', fired_at) AS INT) IN (7, 8)
            ORDER BY fired_at DESC
            """
        ).fetchall()

    grouped: dict[tuple[str, str], list[sqlite3.Row]] = {}
    total_window_rows = 0
    for row in rows:
        fired_utc = _parse_utc(row["fired_at"])
        if fired_utc is None:
            continue
        local_dt = fired_utc.astimezone(tz)
        if not _in_window(local_dt, start_time, end_time):
            continue

        total_window_rows += 1
        floor = str(row["source_floor"] or "LIVE").upper()
        kind = str(row["signal_kind"] or "").upper()
        color = str(row["color"] or "").lower()
        room = _norm_room(row["rooms_agreed"])
        keys = [
            ("floor_kind_color", f"{floor}:{kind}:{color}"),
        ]
        if room:
            keys.append(("room_floor_kind_color", f"{room}:{floor}:{kind}:{color}"))
        for key_type, key in keys:
            grouped.setdefault((key_type, key), []).append(row)

    cells = [
        _make_cell(key_type, key, cell_rows)
        for (key_type, key), cell_rows in grouped.items()
        if len(cell_rows) >= int(min_n)
    ]
    cells.sort(key=lambda c: (
        c.legacy_tier != "LEGACY_ORACLE_CANDIDATE",
        c.legacy_tier != "LEGACY_WATCH",
        -(c.wr or 0.0),
        -(c.g0_wr or 0.0),
        -c.n,
    ))

    live_keys = [
        asdict(c)
        for c in cells
        if c.legacy_tier in {"LEGACY_ORACLE_CANDIDATE", "LEGACY_WATCH"}
    ][:80]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "timezone": tz_name,
        "window_local": {"start": start, "end": end},
        "summary": {
            "window_rows": total_window_rows,
            "candidate_cells": len(cells),
            "oracle_candidates": sum(1 for c in cells if c.legacy_tier == "LEGACY_ORACLE_CANDIDATE"),
            "watch_candidates": sum(1 for c in cells if c.legacy_tier == "LEGACY_WATCH"),
        },
        "legacy_warning": (
            "SPECIAL LEGACY 3:55 PAWTUCKET WARNING: this signal matches the old config/time-window "
            "that may have produced G0 wins before the casino result. Treat as G0-only and verify timing."
        ),
        "live_warning_keys": live_keys,
        "top_cells": [asdict(c) for c in cells[:80]],
    }


def save_report(
    db_path: str = DB_PATH,
    start: str = "03:30",
    end: str = "03:59",
    tz_name: str = TZ_NAME,
    min_n: int = 5,
    path: str = REPORT_PATH,
) -> dict[str, Any]:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    report = build_report(db_path, start=start, end=end, tz_name=tz_name, min_n=min_n)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    os.replace(tmp, path)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Mine old 3:55am Pawtucket legacy config warnings")
    parser.add_argument("--db", default=DB_PATH)
    parser.add_argument("--start", default="03:30")
    parser.add_argument("--end", default="03:59")
    parser.add_argument("--tz", default=TZ_NAME)
    parser.add_argument("--min-n", type=int, default=5)
    parser.add_argument("--report", default=REPORT_PATH)
    args = parser.parse_args()
    report = save_report(args.db, args.start, args.end, args.tz, args.min_n, args.report)
    print(json.dumps({
        "generated_at": report["generated_at"],
        "timezone": report["timezone"],
        "window_local": report["window_local"],
        "summary": report["summary"],
        "top_cells": report["top_cells"][:20],
    }, indent=2, ensure_ascii=False))
    print(f"report={args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
