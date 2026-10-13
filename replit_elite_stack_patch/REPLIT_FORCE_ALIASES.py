#!/usr/bin/env python3
"""Run on Replit: python3 REPLIT_FORCE_ALIASES.py"""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path("/home/runner/workspace")
BOT = ROOT / "bot"
DATA = BOT / "data"
DATA.mkdir(parents=True, exist_ok=True)

ALIASES = {
    "JUN19": "JUN19_peak",
    "JUN20": "JUN20_peak",
    "JUN08": "JUN08_peak",
    "JUN10": "JUN10_peak",
    "JUN26": "JUN26",
    "JUN27": "JUN27_peak",
    "MAY19": "MAY19_peak",
    "MAY10": "MAY10_peak",
    "MAY11": "MAY11_peak",
    "MAY01": "MAY01_peak",
    "APR19": "APR19_golden",
    "APR20": "APR20_perfect",
    "APR30": "APR30_peak",
    "JUN12A": "JUN12_avalanche",
    "JUN12B": "JUN12_eliteguard",
    "ELITE_V2_PEAK": "ELITE_V2_PEAK",
    "ELITE_V2": "ELITE_V2",
    "ULTIMATE": "ULTIMATE",
    "MAR19": "MAR19",
    "MAR20": "MAR20",
    "MAR21": "MAR21",
}
LIVE = [
    "ELITE_V2_PEAK","ELITE_V2","APR20","APR26","APR27","APR29","JUN10",
    "AITEST_ULTIMATE","AITEST_APR20_MAX","LIVE","MAY01","JUN20","AITEST_LIVE",
    "APR22","JUN19","APR20_MAX","JUN26","MAY19","MAY10","JUN27","APR28",
    "MAY11","AITEST_APR20","AITEST_MAR21","JUN08","APR30","MAY04","APR19",
    "ULTIMATE","MAR19","MAR21","MAR20",
]
BLOCKED = ["JUN12A", "JUN12B"]
PEAKS = ["JUN19","JUN20","JUN08","JUN10","JUN26","JUN27","MAY19","MAY10"]

seed_path = DATA / "historical_luxury_seed.json"
seed = {}
if seed_path.exists():
    try:
        seed = json.loads(seed_path.read_text())
    except Exception:
        seed = {}
seed["hard_block"] = BLOCKED
seed["gate_aliases"] = ALIASES
if "floors" not in seed:
    seed["floors"] = [{"floor": f, "force_live": True, "lane": "VOLUME"} for f in LIVE]
seed_path.write_text(json.dumps(seed, indent=2) + "\n")

lux_path = DATA / "luxury_building_stack.json"
lux = {}
if lux_path.exists():
    try:
        lux = json.loads(lux_path.read_text())
    except Exception:
        lux = {}
live_floors = lux.get("live_building_floors") or LIVE
allow = {
    "live_floors": live_floors,
    "blocked": BLOCKED,
    "peak_day_floors": PEAKS,
    "virtual_setups": ["SOLO_ELITE|BLUE","GOLDEN|BLUE","SEQUENCE|BLUE","PLATINUM|BLUE","SEQUENCE"],
    "gate_aliases": ALIASES,
}
(DATA / "luxury_live_floors.json").write_text(json.dumps(allow, indent=2) + "\n")
(ROOT / "luxury_building.env").write_text(
    "export EDGE_POLICY_MODE=luxury\n"
    "export EDGE_LUXURY_FLOOR_GATE=1\n"
    "export FALLBACK_SEND_BLOCKED=0\n"
)

print("live_floors", len(live_floors))
print("blocked", BLOCKED)
print("aliases")
ok = miss = 0
for k, v in sorted(ALIASES.items()):
    g = BOT / f"_gates_{v}.py"
    st = "OK" if g.exists() else "MISSING_GATE"
    ok += int(g.exists())
    miss += int(not g.exists())
    print(f"  {k} -> {v}  {st}")
print(f"alias_gates_ok={ok} missing={miss}")
print("MODE=luxury")
print("NEXT: Stop/Start Replit Run button, then upload the 4 zips via YDRAY")
