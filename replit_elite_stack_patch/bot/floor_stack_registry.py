"""
floor_stack_registry.py — classify every known floor/camada into 3-mode lanes.

Lanes:
  PRECISION  = highest WR, lower volume, use as quality anchor
  BALANCED   = best blend of WR and signal count
  VOLUME     = positive-edge volume expansion
  SHADOW     = learn silently / not enough current proof
  BLOCK      = currently weak; do not live-fire

Read-only. Writes bot/data/floor_stack_registry_report.json.
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
REPORT_PATH = os.path.join(HERE, "data", "floor_stack_registry_report.json")

BASE_18 = {
    "LIVE", "MAR19", "MAR20", "MAR21",
    "APR19", "APR20", "APR21", "APR22", "APR24", "APR25", "APR26", "APR27", "APR28", "APR29", "APR30",
    "MAY01", "MAY02", "MAY04",
}
PEAK_VOLUME = {
    "MAY10", "MAY11", "MAY15", "MAY17", "MAY19", "MAY20", "MAY21", "MAY22", "MAY24", "MAY26", "MAY27",
    "JUN08", "JUN09", "JUN10", "JUN12A", "JUN12B",
}
ELITE_CORE = {"ELITE_V2", "ULTIMATE"}

# Hard-blocked floors — never live-fire regardless of sample WR.
HARD_BLOCK_FLOORS = {"JUN12A", "JUN12B"}

# Luxury building rule: early result cards fire before the live round, so
# lifetime WR >= 60% with n >= 10 is worth stacking (not only recent_wr7).
LUXURY_MIN_N = 10
LUXURY_MIN_WR = 60.0


@dataclass
class FloorCell:
    floor: str
    family: str
    lane: str
    total: int
    active_days: int
    first_seen: str | None
    last_seen: str | None
    wins: int
    losses: int
    ties: int
    g0_wins: int
    final_wr: float | None
    g0_wr: float | None
    recent_n7: int
    recent_wr7: float | None
    recent_g0_wr7: float | None
    max_day: str | None
    max_day_signals: int | None
    max_day_wr: float | None
    weight: float
    recommendation: str


def _connect(db_path: str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def classify_family(floor: str) -> str:
    if floor == "LIVE":
        return "LIVE"
    if floor in ELITE_CORE:
        return "ELITE_CORE"
    if floor in BASE_18:
        return "BASE_18"
    if floor in PEAK_VOLUME:
        return "PEAK_VOLUME"
    if floor.startswith("AITEST_") and floor.endswith("_MAX"):
        return "AITEST_MAX"
    if floor.startswith("AITEST_"):
        return "AITEST"
    if floor.endswith("_MAX"):
        return "MAX_VARIANT"
    if floor.endswith("_PEAK") or "PEAK" in floor:
        return "PEAK_VARIANT"
    return "OTHER"


def choose_lane(
    family: str,
    total: int,
    final_wr: float | None,
    recent_n7: int,
    recent_wr7: float | None,
    floor: str | None = None,
) -> str:
    """Lane selection for the luxury building.

    Uses lifetime WR as the promotion signal (early-result edge rule).
    recent_wr7 only demotes into BLOCK when it is clearly broken (<55% on n>=20).
    """
    name = (floor or "").strip().upper()
    if name in HARD_BLOCK_FLOORS:
        return "BLOCK"

    wr = float(final_wr or 0.0)
    recent = float(recent_wr7) if recent_n7 >= 10 and recent_wr7 is not None else None

    # Actively bleeding floors — quarantine even if lifetime looked fine.
    if recent is not None and recent_n7 >= 20 and recent < 55.0:
        return "BLOCK"

    # Lifetime too weak for luxury stack.
    if total >= LUXURY_MIN_N and wr < LUXURY_MIN_WR:
        return "BLOCK" if total >= 20 else "SHADOW"

    # Precision quality anchors.
    if total >= 30 and wr >= 88.0:
        return "PRECISION"

    # Stable quality/volume blend (lower n bar so APR20/MAY01 stay balanced).
    if total >= 50 and wr >= 80.0:
        return "BALANCED"

    # Luxury volume: every good floor (WR>=60, n>=10) enters the live building.
    if total >= LUXURY_MIN_N and wr >= LUXURY_MIN_WR:
        return "VOLUME"

    return "SHADOW"


def lane_weight(lane: str, family: str, final_wr: float | None) -> float:
    wr = final_wr or 0.0
    if lane == "PRECISION":
        return 3.0
    if lane == "BALANCED":
        if family in {"LIVE", "ELITE_CORE"}:
            return 2.5
        return 2.0
    if lane == "VOLUME":
        return 1.25 if wr >= 76 else 1.0
    if lane == "SHADOW":
        return 0.0
    return -1.0


def recommendation(lane: str) -> str:
    return {
        "PRECISION": "quality_anchor_live",
        "BALANCED": "main_stack_live",
        "VOLUME": "volume_stack_live_if_tri_brain_ok",
        "SHADOW": "shadow_learn_only",
        "BLOCK": "block_or_shadow_until_repaired",
    }.get(lane, "shadow_learn_only")


def load_floors(db_path: str = DB_PATH) -> list[FloorCell]:
    with _connect(db_path) as conn:
        rows = conn.execute("""
            WITH base AS (
              SELECT COALESCE(source_floor,'LIVE') floor,
                     date(fired_at) d,
                     fired_at,
                     outcome,
                     COALESCE(won_at_gale,0) won_at_gale
              FROM consensus_signals
              WHERE outcome IN ('win','loss','tie')
            ),
            agg AS (
              SELECT floor,
                     COUNT(*) total,
                     COUNT(DISTINCT d) active_days,
                     MIN(fired_at) first_seen,
                     MAX(fired_at) last_seen,
                     SUM(outcome='win') wins,
                     SUM(outcome='loss') losses,
                     SUM(outcome='tie') ties,
                     SUM(outcome='win' AND won_at_gale=0) g0_wins,
                     ROUND(100.0 * SUM(outcome='win') /
                           NULLIF(SUM(outcome IN ('win','loss')), 0), 2) final_wr,
                     ROUND(100.0 * SUM(outcome='win' AND won_at_gale=0) /
                           NULLIF(SUM(outcome IN ('win','loss')), 0), 2) g0_wr
              FROM base GROUP BY floor
            ),
            recent AS (
              SELECT COALESCE(source_floor,'LIVE') floor,
                     COUNT(*) recent_n7,
                     ROUND(100.0 * SUM(outcome='win') /
                           NULLIF(SUM(outcome IN ('win','loss')), 0), 2) recent_wr7,
                     ROUND(100.0 * SUM(outcome='win' AND COALESCE(won_at_gale,0)=0) /
                           NULLIF(SUM(outcome IN ('win','loss')), 0), 2) recent_g0_wr7
              FROM consensus_signals
              WHERE fired_at >= datetime('now','-7 days')
                AND outcome IN ('win','loss','tie')
              GROUP BY floor
            ),
            maxday AS (
              SELECT floor, d max_day, total max_day_signals, wr max_day_wr FROM (
                SELECT floor, d, COUNT(*) total,
                       ROUND(100.0 * SUM(outcome='win') /
                             NULLIF(SUM(outcome IN ('win','loss')), 0), 2) wr,
                       ROW_NUMBER() OVER (PARTITION BY floor ORDER BY COUNT(*) DESC) rn
                FROM base GROUP BY floor, d
              ) WHERE rn = 1
            )
            SELECT agg.*, COALESCE(recent.recent_n7,0) recent_n7, recent.recent_wr7, recent.recent_g0_wr7,
                   maxday.max_day, maxday.max_day_signals, maxday.max_day_wr
            FROM agg
            LEFT JOIN recent USING(floor)
            LEFT JOIN maxday USING(floor)
            ORDER BY total DESC, final_wr DESC
        """).fetchall()

    out: list[FloorCell] = []
    for r in rows:
        floor = r["floor"]
        family = classify_family(floor)
        lane = choose_lane(
            family,
            int(r["total"] or 0),
            r["final_wr"],
            int(r["recent_n7"] or 0),
            r["recent_wr7"],
            floor=floor,
        )
        weight = lane_weight(lane, family, r["final_wr"])
        out.append(
            FloorCell(
                floor=floor,
                family=family,
                lane=lane,
                total=int(r["total"] or 0),
                active_days=int(r["active_days"] or 0),
                first_seen=r["first_seen"],
                last_seen=r["last_seen"],
                wins=int(r["wins"] or 0),
                losses=int(r["losses"] or 0),
                ties=int(r["ties"] or 0),
                g0_wins=int(r["g0_wins"] or 0),
                final_wr=r["final_wr"],
                g0_wr=r["g0_wr"],
                recent_n7=int(r["recent_n7"] or 0),
                recent_wr7=r["recent_wr7"],
                recent_g0_wr7=r["recent_g0_wr7"],
                max_day=r["max_day"],
                max_day_signals=r["max_day_signals"],
                max_day_wr=r["max_day_wr"],
                weight=weight,
                recommendation=recommendation(lane),
            )
        )
    return out


def build_report(db_path: str = DB_PATH) -> dict[str, Any]:
    floors = load_floors(db_path)
    lane_counts: dict[str, int] = {}
    family_counts: dict[str, int] = {}
    for f in floors:
        lane_counts[f.lane] = lane_counts.get(f.lane, 0) + 1
        family_counts[f.family] = family_counts.get(f.family, 0) + 1

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_floors": len(floors),
        "lane_counts": lane_counts,
        "family_counts": family_counts,
        "precision": [asdict(f) for f in floors if f.lane == "PRECISION"],
        "balanced": [asdict(f) for f in floors if f.lane == "BALANCED"],
        "volume": [asdict(f) for f in floors if f.lane == "VOLUME"],
        "shadow": [asdict(f) for f in floors if f.lane == "SHADOW"],
        "blocked": [asdict(f) for f in floors if f.lane == "BLOCK"],
        "all_floors": [asdict(f) for f in floors],
        "live_building": [
            asdict(f) for f in floors if f.lane in {"PRECISION", "BALANCED", "VOLUME"}
        ],
        "stack_policy": {
            "precision": "High-WR anchors; can approve only if edge and Tri-Brain agree.",
            "balanced": "Main production stack; strong mix of volume and WR.",
            "volume": "Luxury WR>=60% early-result floors; live-fire in EDGE_POLICY_MODE=luxury|volume.",
            "shadow": "Learn only; no live fire until promoted.",
            "blocked": "Do not live-fire (JUN12* hard-block + actively bleeding floors).",
            "luxury_rule": f"Promote every floor with lifetime WR>={LUXURY_MIN_WR} and n>={LUXURY_MIN_N}; hard-block {sorted(HARD_BLOCK_FLOORS)}.",
        },
    }


def save_report(db_path: str = DB_PATH, path: str = REPORT_PATH) -> dict[str, Any]:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    report = build_report(db_path)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    os.replace(tmp, path)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Build floor/camada 3-lane registry")
    parser.add_argument("--db", default=DB_PATH)
    parser.add_argument("--report", default=REPORT_PATH)
    args = parser.parse_args()
    report = save_report(args.db, args.report)
    print(json.dumps(
        {
            "generated_at": report["generated_at"],
            "total_floors": report["total_floors"],
            "lane_counts": report["lane_counts"],
            "family_counts": report["family_counts"],
            "precision": report["precision"],
            "balanced": report["balanced"],
            "volume": report["volume"],
            "blocked": report["blocked"],
        },
        indent=2,
        ensure_ascii=False,
    ))
    print(f"report={args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
