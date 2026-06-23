"""
skyscraper_floor_factory.py — generate new virtual floors/camadas from DB edges.

This is a floor/camada factory, not a blind live-fire switch.

It mines:
  1. Peak-day floors from the best historical high-volume days.
  2. Room-hour-color sniper floors.
  3. Floor-kind-hour-color sniper floors.
  4. G0 future-offset floors.
  5. Early-safe timing floors.
  6. Volume flood floors.

Each generated floor is assigned:
  PRECISION / BALANCED / VOLUME / SHADOW / BLOCK

Timing:
  DIRECT_PRE_BET is impossible to prove without direct Twin225 result capture.
  This factory therefore labels timing with the best available DB evidence:
    - EARLY_SAFE_CANDIDATE: 20-90s to result in bot DB
    - INSTANT_EDGE_OR_ARTIFACT: <5s-heavy; likely too late unless direct truth proves otherwise
    - STALE_OR_WRONG_ROUND_RISK: >=90s/null-heavy

Output:
  bot/data/skyscraper_floor_factory_report.json
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any


HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(HERE, "bacbo.db")
REPORT_PATH = os.path.join(HERE, "data", "skyscraper_floor_factory_report.json")


@dataclass
class GeneratedFloor:
    id: str
    family: str
    lane: str
    source: str
    rule: dict[str, Any]
    n: int
    wr: float | None
    g0_wr: float | None
    avg_secs: float | None
    early_safe_pct: float | None
    instant_pct: float | None
    stale_or_wrong_pct: float | None
    weight: float
    action: str
    warning: str


def _connect(db_path: str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def _rows(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def _first_room_expr() -> str:
    return """
    lower(replace(
      CASE
        WHEN instr(coalesce(rooms_agreed,''), ',') > 0
        THEN substr(rooms_agreed, 1, instr(rooms_agreed, ',') - 1)
        ELSE coalesce(rooms_agreed, '')
      END, '@', ''))
    """


def _timing_label(early_pct: float | None, instant_pct: float | None, stale_pct: float | None) -> str:
    early = early_pct or 0.0
    instant = instant_pct or 0.0
    stale = stale_pct or 0.0
    if stale >= 25:
        return "STALE_OR_WRONG_ROUND_RISK"
    if early >= 30:
        return "EARLY_SAFE_CANDIDATE"
    if instant >= 40:
        return "INSTANT_EDGE_OR_ARTIFACT"
    return "MIXED_TIMING"


def _lane(n: int, wr: float | None, g0_wr: float | None, family: str, timing: str) -> str:
    wr = wr or 0.0
    g0 = g0_wr if g0_wr is not None else wr
    if timing == "STALE_OR_WRONG_ROUND_RISK":
        return "SHADOW"
    if n >= 50 and wr >= 92 and g0 >= 90:
        return "PRECISION"
    if n >= 100 and wr >= 85 and g0 >= 83:
        return "BALANCED"
    if n >= 30 and wr >= 85:
        return "BALANCED"
    if n >= 20 and wr >= 78:
        return "VOLUME"
    if n >= 10 and wr >= 70:
        return "SHADOW"
    return "BLOCK"


def _weight(lane: str, wr: float | None, timing: str) -> float:
    wr = wr or 0.0
    base = {
        "PRECISION": 3.0,
        "BALANCED": 2.0,
        "VOLUME": 1.15,
        "SHADOW": 0.0,
        "BLOCK": -1.0,
    }.get(lane, 0.0)
    if timing == "EARLY_SAFE_CANDIDATE":
        base += 0.25
    if timing == "INSTANT_EDGE_OR_ARTIFACT":
        base -= 0.25
    if wr >= 95:
        base += 0.25
    return round(base, 2)


def _action(lane: str, timing: str) -> str:
    if lane == "PRECISION":
        return "FIRE_IF_TRI_BRAIN_OK_AND_NO_LOSS_RISK"
    if lane == "BALANCED":
        return "FIRE_IF_TRI_BRAIN_OK"
    if lane == "VOLUME":
        return "FIRE_IN_VOLUME_MODE_IF_NO_LOSS_RISK"
    if lane == "SHADOW":
        return "SHADOW_LEARN"
    return "BLOCK"


def _warning(timing: str) -> str:
    if timing == "EARLY_SAFE_CANDIDATE":
        return "best available pre-result timing evidence; still not direct Twin225 truth"
    if timing == "INSTANT_EDGE_OR_ARTIFACT":
        return "strong but may be after-result/instant-match; require direct truth before treating as pre-bet"
    if timing == "STALE_OR_WRONG_ROUND_RISK":
        return "do not live-fire; likely wrong-round/stale matching risk"
    return "mixed timing; use scoring and shadow validation"


def _mk(
    family: str,
    source: str,
    rule: dict[str, Any],
    n: int,
    wr: float | None,
    g0_wr: float | None,
    avg_secs: float | None,
    early_safe_pct: float | None = None,
    instant_pct: float | None = None,
    stale_or_wrong_pct: float | None = None,
) -> GeneratedFloor:
    timing = _timing_label(early_safe_pct, instant_pct, stale_or_wrong_pct)
    lane = _lane(n, wr, g0_wr, family, timing)
    gid = f"{family}:{source}:{rule}".replace(" ", "")
    return GeneratedFloor(
        id=gid[:180],
        family=family,
        lane=lane,
        source=source,
        rule=rule,
        n=int(n or 0),
        wr=wr,
        g0_wr=g0_wr,
        avg_secs=avg_secs,
        early_safe_pct=early_safe_pct,
        instant_pct=instant_pct,
        stale_or_wrong_pct=stale_or_wrong_pct,
        weight=_weight(lane, wr, timing),
        action=_action(lane, timing),
        warning=_warning(timing),
    )


def peak_day_floors(conn: sqlite3.Connection) -> list[GeneratedFloor]:
    rows = _rows(conn, """
        SELECT date(fired_at) d,
               COUNT(*) n,
               SUM(outcome='win') wins,
               SUM(outcome='loss') losses,
               SUM(outcome='tie') ties,
               ROUND(100.0 * SUM(outcome='win') /
                     NULLIF(SUM(outcome IN ('win','loss')),0), 2) wr,
               ROUND(100.0 * SUM(outcome='win' AND COALESCE(won_at_gale,0)=0) /
                     NULLIF(SUM(outcome IN ('win','loss')),0), 2) g0_wr,
               ROUND(AVG(secs_to_result), 1) avg_secs
        FROM consensus_signals
        WHERE outcome IN ('win','loss','tie')
        GROUP BY d
        HAVING n >= 500 AND wr >= 78
        ORDER BY n DESC
        LIMIT 25
    """)
    return [
        _mk("PEAK_DAY", "daily", {"date": r["d"]}, r["n"], r["wr"], r["g0_wr"], r["avg_secs"])
        for r in rows
    ]


def room_hour_color_floors(conn: sqlite3.Connection, days: int) -> list[GeneratedFloor]:
    first_room = _first_room_expr()
    rows = _rows(conn, f"""
        SELECT {first_room} room,
               CAST(strftime('%H',fired_at) AS INT) hour,
               color,
               COUNT(*) n,
               ROUND(100.0 * SUM(outcome='win') /
                     NULLIF(SUM(outcome IN ('win','loss')),0), 2) wr,
               ROUND(100.0 * SUM(outcome='win' AND COALESCE(won_at_gale,0)=0) /
                     NULLIF(SUM(outcome IN ('win','loss')),0), 2) g0_wr,
               ROUND(AVG(secs_to_result), 1) avg_secs,
               ROUND(100.0 * SUM(secs_to_result IS NOT NULL AND secs_to_result < 1) / COUNT(*), 2) instant_pct,
               ROUND(100.0 * SUM(secs_to_result IS NOT NULL AND secs_to_result >= 20 AND secs_to_result < 90) / COUNT(*), 2) early_safe_pct,
               ROUND(100.0 * SUM(secs_to_result IS NULL OR secs_to_result >= 90) / COUNT(*), 2) stale_pct
        FROM consensus_signals
        WHERE fired_at >= datetime('now', ?)
          AND outcome IN ('win','loss','tie')
          AND color IN ('blue','red')
        GROUP BY room, hour, color
        HAVING n >= 15 AND wr >= 85
        ORDER BY wr DESC, n DESC
        LIMIT 200
    """, (f"-{int(days)} days",))
    return [
        _mk(
            "ROOM_HOUR_COLOR",
            "recent",
            {"room": r["room"], "hour": r["hour"], "color": r["color"]},
            r["n"], r["wr"], r["g0_wr"], r["avg_secs"], r["early_safe_pct"], r["instant_pct"], r["stale_pct"],
        )
        for r in rows
    ]


def floor_kind_hour_color_floors(conn: sqlite3.Connection, days: int) -> list[GeneratedFloor]:
    rows = _rows(conn, """
        SELECT COALESCE(source_floor,'LIVE') floor,
               signal_kind,
               CAST(strftime('%H',fired_at) AS INT) hour,
               color,
               COUNT(*) n,
               ROUND(100.0 * SUM(outcome='win') /
                     NULLIF(SUM(outcome IN ('win','loss')),0), 2) wr,
               ROUND(100.0 * SUM(outcome='win' AND COALESCE(won_at_gale,0)=0) /
                     NULLIF(SUM(outcome IN ('win','loss')),0), 2) g0_wr,
               ROUND(AVG(secs_to_result), 1) avg_secs,
               ROUND(100.0 * SUM(secs_to_result IS NOT NULL AND secs_to_result < 1) / COUNT(*), 2) instant_pct,
               ROUND(100.0 * SUM(secs_to_result IS NOT NULL AND secs_to_result >= 20 AND secs_to_result < 90) / COUNT(*), 2) early_safe_pct,
               ROUND(100.0 * SUM(secs_to_result IS NULL OR secs_to_result >= 90) / COUNT(*), 2) stale_pct
        FROM consensus_signals
        WHERE fired_at >= datetime('now', ?)
          AND outcome IN ('win','loss','tie')
          AND color IN ('blue','red')
        GROUP BY floor, signal_kind, hour, color
        HAVING n >= 15 AND wr >= 85
        ORDER BY wr DESC, n DESC
        LIMIT 200
    """, (f"-{int(days)} days",))
    return [
        _mk(
            "FLOOR_KIND_HOUR_COLOR",
            "recent",
            {"floor": r["floor"], "kind": r["signal_kind"], "hour": r["hour"], "color": r["color"]},
            r["n"], r["wr"], r["g0_wr"], r["avg_secs"], r["early_safe_pct"], r["instant_pct"], r["stale_pct"],
        )
        for r in rows
    ]


def g0_offset_floors(db_path: str) -> list[GeneratedFloor]:
    try:
        import g0_offset_oracle
        report = g0_offset_oracle.save_report(db_path=db_path)
        cells = report.get("top_cells", [])[:80]
    except Exception:
        cells = []
    out = []
    for c in cells:
        if c.get("quality") not in {"ELITE_OFFSET", "STRONG_OFFSET"}:
            continue
        out.append(
            _mk(
                "G0_OFFSET",
                "future_offset",
                {
                    "kind": c["signal_kind"],
                    "floor": c["source_floor"],
                    "color": c["color"],
                    "offset": c["offset"],
                },
                c["n"], c["match_pct"], c["match_pct"], None, None, None, None,
            )
        )
    return out


def legacy_peak_355_floors(db_path: str) -> list[GeneratedFloor]:
    try:
        import legacy_peak_355
        report = legacy_peak_355.save_report(db_path=db_path)
        cells = report.get("live_warning_keys", [])[:80]
    except Exception:
        cells = []

    out = []
    for c in cells:
        rule = {
            "floor": c.get("source_floor"),
            "kind": c.get("signal_kind"),
            "color": c.get("color"),
            "room": c.get("room"),
            "window_start": c.get("window_start"),
            "window_end": c.get("window_end"),
            "timezone": "America/New_York",
            "legacy_tier": c.get("legacy_tier"),
        }
        f = _mk(
            "LEGACY_355_PAWTUCKET",
            "legacy_window",
            rule,
            int(c.get("n") or 0),
            c.get("wr"),
            c.get("g0_wr"),
            c.get("avg_secs"),
            None,
            None,
            None,
        )
        f.lane = "SHADOW"
        f.weight = 0.75 if c.get("legacy_tier") == "LEGACY_ORACLE_CANDIDATE" else 0.25
        f.action = "WARN_G0_ONLY_SHADOW_VALIDATE"
        f.warning = str(c.get("warning") or "legacy 3:55 Pawtucket warning")
        out.append(f)
    return out


def loss_risk_floors(conn: sqlite3.Connection, days: int) -> list[GeneratedFloor]:
    first_room = _first_room_expr()
    rows = _rows(conn, f"""
        SELECT {first_room} room,
               COALESCE(source_floor,'LIVE') floor,
               signal_kind,
               CAST(strftime('%H',fired_at) AS INT) hour,
               color,
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
        GROUP BY room, floor, signal_kind, hour, color
        HAVING n >= 10 AND loss_pct >= 35
        ORDER BY loss_pct DESC, n DESC
        LIMIT 160
    """, (f"-{int(days)} days",))
    return [
        _mk(
            "LOSS_RISK",
            "recent",
            {"room": r["room"], "floor": r["floor"], "kind": r["signal_kind"], "hour": r["hour"], "color": r["color"], "loss_pct": r["loss_pct"]},
            r["n"], r["wr"], r["wr"], None, None, None, 100.0,
        )
        for r in rows
    ]


def build_report(db_path: str = DB_PATH, days: int = 30) -> dict[str, Any]:
    with _connect(db_path) as conn:
        generated = []
        generated += peak_day_floors(conn)
        generated += room_hour_color_floors(conn, days)
        generated += floor_kind_hour_color_floors(conn, days)
        generated += g0_offset_floors(db_path)
        generated += legacy_peak_355_floors(db_path)
        loss = loss_risk_floors(conn, days)

    # Force loss-risk family to BLOCK.
    for f in loss:
        f.lane = "BLOCK"
        f.weight = -1.0
        f.action = "BLOCK"
        f.warning = "recent high loss-risk cell"

    generated.sort(key=lambda f: (f.lane != "PRECISION", f.lane != "BALANCED", f.lane != "VOLUME", -f.weight, -(f.wr or 0), -f.n))

    lane_counts: dict[str, int] = {}
    family_counts: dict[str, int] = {}
    for f in generated:
        lane_counts[f.lane] = lane_counts.get(f.lane, 0) + 1
        family_counts[f.family] = family_counts.get(f.family, 0) + 1

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "days": int(days),
        "summary": {
            "generated_floors": len(generated),
            "loss_risk_floors": len(loss),
            "lane_counts": lane_counts,
            "family_counts": family_counts,
        },
        "precision": [asdict(f) for f in generated if f.lane == "PRECISION"],
        "balanced": [asdict(f) for f in generated if f.lane == "BALANCED"],
        "volume": [asdict(f) for f in generated if f.lane == "VOLUME"],
        "shadow": [asdict(f) for f in generated if f.lane == "SHADOW"],
        "blocked": [asdict(f) for f in loss],
        "all_generated": [asdict(f) for f in generated],
        "policy": {
            "precision": "fire if Tri-Brain OK and no loss-risk conflict",
            "balanced": "fire in Good-Fire Max when Tri-Brain OK",
            "volume": "fire in Volume Max if no loss-risk and no opposite conflict",
            "shadow": "learn only until promoted; LEGACY_355_PAWTUCKET only adds a signal warning",
            "block": "never fire unless direct casino truth overrides",
        },
        "direct_truth_warning": "All WR here is BOT_DB_INFERRED unless casino_round_results has direct Twin225 rows.",
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
    parser = argparse.ArgumentParser(description="Generate many virtual skyscraper floors from DB edges")
    parser.add_argument("--db", default=DB_PATH)
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--report", default=REPORT_PATH)
    args = parser.parse_args()
    report = save_report(args.db, args.days, args.report)
    print(json.dumps(
        {
            "generated_at": report["generated_at"],
            "summary": report["summary"],
            "precision_top": report["precision"][:15],
            "balanced_top": report["balanced"][:15],
            "volume_top": report["volume"][:15],
            "blocked_top": report["blocked"][:10],
        },
        indent=2,
        ensure_ascii=False,
    ))
    print(f"report={args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
