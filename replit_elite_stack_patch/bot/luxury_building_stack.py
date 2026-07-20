"""
luxury_building_stack.py — freeze every good floor (WR>=60%, n>=10) into the live building.

Writes:
  bot/data/luxury_building_stack.json

Can rebuild from:
  1) live bacbo.db via floor_stack_registry, or
  2) an existing floor_stack_registry_report.json (offline reclassify)
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from typing import Any


HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(HERE, "bacbo.db")
REGISTRY_PATH = os.path.join(HERE, "data", "floor_stack_registry_report.json")
REPORT_PATH = os.path.join(HERE, "data", "luxury_building_stack.json")

# Card templates allowed in Telegram outbox for luxury fire.
KEEP_CARD_TYPES = [
    "CD_FIRE_TIMER_BRT_EDT_APOSTAR",
    "CD_RES_GREEN_G_BRT",
    "CD_RES_RODADAS_TEMPO",
    "CD_RES_BELL_GANHOU",
    "RES_WIN_KIND",
    "FIRE_GOLDEN",
    "RES_GREEN_G0",
]
KILL_CARD_TYPES = [
    "RES_AUTO_WIN",
    "RES_AUTO_LOSS",
    "RES_AUTO_TIE",
    "CD_FIRE_DO_NOT_BET_PASSED",
    "RES_LOSS_KIND",
    "FIRE_SEQUENCIA_STREAK",
    "FIRE_SINAL_RETIDO",
]


def _reclassify_from_registry(path: str = REGISTRY_PATH) -> dict[str, Any]:
    import floor_stack_registry as fsr

    with open(path, "r", encoding="utf-8") as fh:
        raw = json.load(fh)

    floors_in = raw.get("all_floors") or []
    out_floors: list[dict[str, Any]] = []
    for item in floors_in:
        floor = str(item.get("floor") or "LIVE")
        family = fsr.classify_family(floor)
        lane = fsr.choose_lane(
            family,
            int(item.get("total") or 0),
            item.get("final_wr"),
            int(item.get("recent_n7") or 0),
            item.get("recent_wr7"),
            floor=floor,
        )
        weight = fsr.lane_weight(lane, family, item.get("final_wr"))
        row = dict(item)
        row.update(
            {
                "family": family,
                "lane": lane,
                "weight": weight,
                "recommendation": fsr.recommendation(lane),
            }
        )
        out_floors.append(row)

    lane_counts: dict[str, int] = {}
    for f in out_floors:
        lane_counts[f["lane"]] = lane_counts.get(f["lane"], 0) + 1

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_floors": len(out_floors),
        "lane_counts": lane_counts,
        "precision": [f for f in out_floors if f["lane"] == "PRECISION"],
        "balanced": [f for f in out_floors if f["lane"] == "BALANCED"],
        "volume": [f for f in out_floors if f["lane"] == "VOLUME"],
        "shadow": [f for f in out_floors if f["lane"] == "SHADOW"],
        "blocked": [f for f in out_floors if f["lane"] == "BLOCK"],
        "all_floors": out_floors,
        "live_building": [f for f in out_floors if f["lane"] in {"PRECISION", "BALANCED", "VOLUME"}],
        "stack_policy": {
            "luxury_rule": (
                f"Promote every floor with lifetime WR>={fsr.LUXURY_MIN_WR} "
                f"and n>={fsr.LUXURY_MIN_N}; hard-block {sorted(fsr.HARD_BLOCK_FLOORS)}."
            ),
        },
        "source": f"reclassified:{path}",
    }


def load_registry(db_path: str = DB_PATH, registry_path: str = REGISTRY_PATH) -> dict[str, Any]:
    if os.path.exists(db_path):
        try:
            import floor_stack_registry as fsr
            return fsr.save_report(db_path=db_path, path=registry_path)
        except Exception as exc:
            # Fall back to offline reclassify if DB is unusable.
            if os.path.exists(registry_path):
                report = _reclassify_from_registry(registry_path)
                report["db_error"] = str(exc)
                return report
            raise
    if os.path.exists(registry_path):
        return _reclassify_from_registry(registry_path)
    raise FileNotFoundError(f"Need {db_path} or {registry_path}")


def build_report(db_path: str = DB_PATH, registry_path: str = REGISTRY_PATH) -> dict[str, Any]:
    import floor_stack_registry as fsr

    reg = load_registry(db_path=db_path, registry_path=registry_path)
    # Persist reclassified registry so other tools see the luxury lanes.
    if reg.get("all_floors"):
        os.makedirs(os.path.dirname(registry_path), exist_ok=True)
        tmp = registry_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(reg, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        os.replace(tmp, registry_path)

    live = reg.get("live_building") or [
        f for f in (reg.get("all_floors") or [])
        if f.get("lane") in {"PRECISION", "BALANCED", "VOLUME"}
    ]
    blocked = reg.get("blocked") or []
    shadow = reg.get("shadow") or []

    live_names = [f["floor"] for f in sorted(live, key=lambda x: (-(x.get("final_wr") or 0), -int(x.get("total") or 0)))]
    blocked_names = [f["floor"] for f in blocked]
    shadow_names = [f["floor"] for f in shadow]

    by_lane = {
        "PRECISION": [f["floor"] for f in reg.get("precision", [])],
        "BALANCED": [f["floor"] for f in reg.get("balanced", [])],
        "VOLUME": [f["floor"] for f in reg.get("volume", [])],
    }

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "rule": {
            "min_wr": fsr.LUXURY_MIN_WR,
            "min_n": fsr.LUXURY_MIN_N,
            "hard_block": sorted(fsr.HARD_BLOCK_FLOORS),
            "note": "Early result cards before live round ⇒ WR>=60 volume is money.",
        },
        "counts": {
            "live_building": len(live_names),
            "precision": len(by_lane["PRECISION"]),
            "balanced": len(by_lane["BALANCED"]),
            "volume": len(by_lane["VOLUME"]),
            "shadow": len(shadow_names),
            "blocked": len(blocked_names),
            "total_floors": reg.get("total_floors"),
        },
        "live_building_floors": live_names,
        "lanes": by_lane,
        "blocked_floors": blocked_names,
        "shadow_floors": shadow_names,
        "live_building_detail": live,
        "blocked_detail": blocked,
        "card_policy": {
            "keep": KEEP_CARD_TYPES,
            "kill": KILL_CARD_TYPES,
            "glue": "countdown_fire_to_countdown_result_same_signal",
            "kinds_bias": ["SOLO_ELITE", "SEQUENCE", "GOLDEN", "PLATINUM"],
            "color_bias": "blue",
        },
        "runtime": {
            "EDGE_POLICY_MODE": "luxury",
            "EDGE_LUXURY_FLOOR_GATE": "1",
            "FALLBACK_SEND_BLOCKED": "0",
            "opposite_color_lock": True,
            "single_outbox": True,
            "g0_only_money": True,
        },
        "architecture": "peak_locked_parallel_towers",
        "next_replit_steps": [
            "Run install_luxury_building.py on Replit",
            "Upload luxury_export_light.zip + may_jul_export.zip via YDRAY for peak-lock freeze",
            "Start Twin225 casino_round_results capture for direct truth",
        ],
    }


def save_report(
    db_path: str = DB_PATH,
    registry_path: str = REGISTRY_PATH,
    path: str = REPORT_PATH,
) -> dict[str, Any]:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    report = build_report(db_path=db_path, registry_path=registry_path)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    os.replace(tmp, path)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Build luxury building stack (all WR>=60 floors)")
    parser.add_argument("--db", default=DB_PATH)
    parser.add_argument("--registry", default=REGISTRY_PATH)
    parser.add_argument("--report", default=REPORT_PATH)
    args = parser.parse_args()
    report = save_report(args.db, args.registry, args.report)
    print(json.dumps(
        {
            "generated_at": report["generated_at"],
            "counts": report["counts"],
            "live_building_floors": report["live_building_floors"],
            "lanes": report["lanes"],
            "blocked_floors": report["blocked_floors"],
            "runtime": report["runtime"],
        },
        indent=2,
        ensure_ascii=False,
    ))
    print(f"report={args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
