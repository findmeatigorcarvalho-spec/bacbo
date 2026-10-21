"""
luxury_building_stack.py — freeze every good floor into the live building.

Merges:
  1) live bacbo.db floor registry (when present)
  2) historical_luxury_seed.json (day-one / full-dump floors + JUN19/JUN20 peaks)

IMPORTANT: Live Replit DBs are often truncated. Thin recent samples must NOT
demote historically good floors (e.g. MAR19, ELITE_V2, JUN20).
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
SEED_PATH = os.path.join(HERE, "data", "historical_luxury_seed.json")
REPORT_PATH = os.path.join(HERE, "data", "luxury_building_stack.json")

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

# If live DB has fewer resolved rows than this for a seeded floor, prefer seed lane/stats.
THIN_LIVE_N = 200


def _load_json(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _seed_floor_row(item: dict[str, Any]) -> dict[str, Any]:
    import floor_stack_registry as fsr

    floor = str(item.get("floor") or "").strip().upper()
    family = item.get("family") or fsr.classify_family(floor)
    total = int(item.get("total") or item.get("n") or 0)
    wr = item.get("final_wr") if item.get("final_wr") is not None else item.get("wr")
    lane = item.get("lane")
    if lane not in {"PRECISION", "BALANCED", "VOLUME", "SHADOW", "BLOCK"}:
        lane = fsr.choose_lane(family, total, wr, 0, None, floor=floor)
        # Seed force-live floors never land in SHADOW/BLOCK unless hard-blocked.
        if item.get("force_live") and lane in {"SHADOW", "BLOCK"} and floor not in fsr.HARD_BLOCK_FLOORS:
            if total >= 30 and (wr or 0) >= 88:
                lane = "PRECISION"
            elif total >= 50 and (wr or 0) >= 80:
                lane = "BALANCED"
            else:
                lane = "VOLUME"
    return {
        "floor": floor,
        "family": family,
        "lane": lane,
        "total": total,
        "active_days": item.get("active_days"),
        "first_seen": item.get("first_seen"),
        "last_seen": item.get("last_seen"),
        "wins": item.get("wins"),
        "losses": item.get("losses"),
        "ties": item.get("ties"),
        "g0_wins": item.get("g0_wins"),
        "final_wr": wr,
        "g0_wr": item.get("g0_wr"),
        "recent_n7": item.get("recent_n7") or 0,
        "recent_wr7": item.get("recent_wr7"),
        "recent_g0_wr7": item.get("recent_g0_wr7"),
        "max_day": item.get("max_day") or item.get("date"),
        "max_day_signals": item.get("max_day_signals") or item.get("n"),
        "max_day_wr": item.get("max_day_wr") or wr,
        "weight": fsr.lane_weight(lane, family, wr),
        "recommendation": fsr.recommendation(lane),
        "seeded": True,
        "seed_source": item.get("source"),
        "peak_day_lock": bool(item.get("peak_day_lock") or item.get("date")),
        "force_live": bool(item.get("force_live", True)),
    }


def load_seed(path: str = SEED_PATH) -> dict[str, Any]:
    if not os.path.exists(path):
        return {"floors": [], "peak_day_floors": [], "virtual_setups": [], "hard_block": ["JUN12A", "JUN12B"]}
    return _load_json(path)


def load_registry_floors(db_path: str = DB_PATH, registry_path: str = REGISTRY_PATH) -> list[dict[str, Any]]:
    import floor_stack_registry as fsr

    if os.path.exists(db_path):
        try:
            report = fsr.save_report(db_path=db_path, path=registry_path)
            return list(report.get("all_floors") or [])
        except Exception:
            pass
    if os.path.exists(registry_path):
        raw = _load_json(registry_path)
        # Reclassify with current rules
        out = []
        for item in raw.get("all_floors") or []:
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
            row = dict(item)
            row.update(
                {
                    "family": family,
                    "lane": lane,
                    "weight": fsr.lane_weight(lane, family, item.get("final_wr")),
                    "recommendation": fsr.recommendation(lane),
                    "seeded": False,
                }
            )
            out.append(row)
        return out
    return []


def merge_floors(live_floors: list[dict[str, Any]], seed: dict[str, Any]) -> list[dict[str, Any]]:
    import floor_stack_registry as fsr

    hard_block = set(seed.get("hard_block") or list(fsr.HARD_BLOCK_FLOORS))
    by: dict[str, dict[str, Any]] = {}

    # Always materialize hard-blocks even if absent from thin live DB / seed floors.
    for name in sorted(hard_block):
        by[name] = {
            "floor": name,
            "family": fsr.classify_family(name),
            "lane": "BLOCK",
            "total": 0,
            "final_wr": None,
            "g0_wr": None,
            "weight": -1.0,
            "recommendation": fsr.recommendation("BLOCK"),
            "seeded": True,
            "force_live": False,
            "seed_source": "hard_block",
        }

    for item in live_floors:
        name = str(item.get("floor") or "").strip().upper()
        if not name:
            continue
        row = dict(item)
        row["floor"] = name
        row["seeded"] = False
        if name in hard_block:
            row["lane"] = "BLOCK"
            row["recommendation"] = fsr.recommendation("BLOCK")
            row["weight"] = -1.0
        by[name] = row

    seed_rows = list(seed.get("floors") or [])
    # Peak-day named floors (JUN19/JUN20/…) also act as force-live floors.
    for p in seed.get("peak_day_floors") or []:
        fname = str(p.get("floor") or "").strip().upper()
        if not fname or fname in hard_block:
            continue
        if fname in {r.get("floor") for r in seed_rows}:
            continue
        seed_rows.append(
            {
                **p,
                "floor": fname,
                "total": p.get("n") or p.get("total"),
                "final_wr": p.get("wr") or p.get("final_wr"),
                "force_live": True,
                "peak_day_lock": True,
                "family": "PEAK_VOLUME",
                "lane": p.get("lane") or "VOLUME",
            }
        )

    for s in seed_rows:
        seeded = _seed_floor_row(s)
        name = seeded["floor"]
        if not name or name in hard_block:
            if name in hard_block:
                by[name] = seeded | {"lane": "BLOCK", "force_live": False}
            continue

        live = by.get(name)
        if live is None:
            by[name] = seeded
            continue

        live_n = int(live.get("total") or 0)
        seed_wr = float(seeded.get("final_wr") or 0)
        # Truncated / thin live reactivation must not demote historical good floors.
        if seeded.get("force_live") and (live_n < THIN_LIVE_N or live.get("lane") in {"SHADOW", "BLOCK"}):
            if seed_wr >= fsr.LUXURY_MIN_WR or seeded.get("peak_day_lock"):
                merged = dict(live)
                merged.update(
                    {
                        "lane": seeded["lane"],
                        "family": seeded.get("family") or live.get("family"),
                        "weight": seeded["weight"],
                        "recommendation": seeded["recommendation"],
                        "seeded": True,
                        "seed_override": True,
                        "seed_source": seeded.get("seed_source"),
                        "historical_total": seeded.get("total"),
                        "historical_wr": seeded.get("final_wr"),
                        "historical_g0_wr": seeded.get("g0_wr"),
                        "max_day": seeded.get("max_day") or live.get("max_day"),
                        "max_day_signals": seeded.get("max_day_signals") or live.get("max_day_signals"),
                        "max_day_wr": seeded.get("max_day_wr") or live.get("max_day_wr"),
                        "peak_day_lock": seeded.get("peak_day_lock"),
                        "force_live": True,
                    }
                )
                by[name] = merged
                continue

        # Live has enough data — keep live lane, annotate seed comparison.
        live["historical_total"] = seeded.get("total")
        live["historical_wr"] = seeded.get("final_wr")
        live["force_live"] = bool(seeded.get("force_live"))
        by[name] = live

    return list(by.values())


def build_report(
    db_path: str = DB_PATH,
    registry_path: str = REGISTRY_PATH,
    seed_path: str = SEED_PATH,
) -> dict[str, Any]:
    import floor_stack_registry as fsr

    seed = load_seed(seed_path)
    live_floors = load_registry_floors(db_path=db_path, registry_path=registry_path)
    floors = merge_floors(live_floors, seed)

    # Persist merged registry view for other tools.
    lane_counts: dict[str, int] = {}
    for f in floors:
        lane_counts[f["lane"]] = lane_counts.get(f["lane"], 0) + 1
    reg_out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_floors": len(floors),
        "lane_counts": lane_counts,
        "precision": [f for f in floors if f["lane"] == "PRECISION"],
        "balanced": [f for f in floors if f["lane"] == "BALANCED"],
        "volume": [f for f in floors if f["lane"] == "VOLUME"],
        "shadow": [f for f in floors if f["lane"] == "SHADOW"],
        "blocked": [f for f in floors if f["lane"] == "BLOCK"],
        "all_floors": floors,
        "live_building": [f for f in floors if f["lane"] in {"PRECISION", "BALANCED", "VOLUME"}],
        "stack_policy": {
            "luxury_rule": (
                f"Promote every floor with lifetime/historical WR>={fsr.LUXURY_MIN_WR} "
                f"and n>={fsr.LUXURY_MIN_N}; hard-block {sorted(fsr.HARD_BLOCK_FLOORS)}; "
                "seed overrides thin truncated live DB."
            ),
        },
        "source": "merged_live_db_plus_historical_seed",
    }
    os.makedirs(os.path.dirname(registry_path), exist_ok=True)
    tmp = registry_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(reg_out, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    os.replace(tmp, registry_path)

    live = [f for f in floors if f.get("lane") in {"PRECISION", "BALANCED", "VOLUME"}]
    blocked = [f for f in floors if f.get("lane") == "BLOCK"]
    shadow = [f for f in floors if f.get("lane") == "SHADOW"]
    live_names = [
        f["floor"]
        for f in sorted(live, key=lambda x: (-(float(x.get("final_wr") or x.get("historical_wr") or 0)), -int(x.get("total") or x.get("historical_total") or 0)))
    ]

    by_lane = {
        "PRECISION": [f["floor"] for f in reg_out["precision"]],
        "BALANCED": [f["floor"] for f in reg_out["balanced"]],
        "VOLUME": [f["floor"] for f in reg_out["volume"]],
    }

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "rule": {
            "min_wr": fsr.LUXURY_MIN_WR,
            "min_n": fsr.LUXURY_MIN_N,
            "hard_block": sorted(fsr.HARD_BLOCK_FLOORS),
            "thin_live_n": THIN_LIVE_N,
            "note": "Seed + peak-day floors survive truncated Replit DBs.",
        },
        "counts": {
            "live_building": len(live_names),
            "precision": len(by_lane["PRECISION"]),
            "balanced": len(by_lane["BALANCED"]),
            "volume": len(by_lane["VOLUME"]),
            "shadow": len(shadow),
            "blocked": len(blocked),
            "total_floors": len(floors),
            "seed_floors": len(seed.get("floors") or []),
            "peak_day_floors": len(seed.get("peak_day_floors") or []),
        },
        "live_building_floors": live_names,
        "lanes": by_lane,
        "blocked_floors": [f["floor"] for f in blocked],
        "shadow_floors": [f["floor"] for f in shadow],
        "peak_day_floors": seed.get("peak_day_floors") or [],
        "virtual_setups": seed.get("virtual_setups") or [],
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
        "db_warning": (
            "Live Replit bacbo.db looks truncated if live_building << seed. "
            "Upload bacbo_db_only.zip / luxury_full_pack.zip via YDRAY for full peak-lock."
            if len(live_names) < max(20, len(seed.get("floors") or []) // 2)
            else None
        ),
    }


def save_report(
    db_path: str = DB_PATH,
    registry_path: str = REGISTRY_PATH,
    seed_path: str = SEED_PATH,
    path: str = REPORT_PATH,
) -> dict[str, Any]:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    report = build_report(db_path=db_path, registry_path=registry_path, seed_path=seed_path)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    os.replace(tmp, path)

    # Always write allowlist for floor_tracker / policy
    seed = load_seed(seed_path)
    allow = {
        "live_floors": report["live_building_floors"],
        "blocked": report["blocked_floors"] or list(seed.get("hard_block") or ["JUN12A", "JUN12B"]),
        "peak_day_floors": [p.get("floor") for p in (report.get("peak_day_floors") or [])],
        "virtual_setups": [v.get("key") for v in (report.get("virtual_setups") or [])],
        "gate_aliases": seed.get("gate_aliases") or {},
    }
    allow_path = os.path.join(os.path.dirname(path), "luxury_live_floors.json")
    with open(allow_path, "w", encoding="utf-8") as fh:
        json.dump(allow, fh, indent=2)
        fh.write("\n")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Build luxury building stack (seed + live DB)")
    parser.add_argument("--db", default=DB_PATH)
    parser.add_argument("--registry", default=REGISTRY_PATH)
    parser.add_argument("--seed", default=SEED_PATH)
    parser.add_argument("--report", default=REPORT_PATH)
    args = parser.parse_args()
    report = save_report(args.db, args.registry, args.seed, args.report)
    print(json.dumps(
        {
            "generated_at": report["generated_at"],
            "counts": report["counts"],
            "live_building_floors": report["live_building_floors"],
            "lanes": report["lanes"],
            "blocked_floors": report["blocked_floors"],
            "peak_day_floors": [p.get("floor") for p in report.get("peak_day_floors") or []],
            "virtual_setups": [v.get("key") for v in report.get("virtual_setups") or []],
            "db_warning": report.get("db_warning"),
            "runtime": report["runtime"],
        },
        indent=2,
        ensure_ascii=False,
    ))
    print(f"report={args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
