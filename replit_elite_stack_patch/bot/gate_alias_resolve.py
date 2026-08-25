"""Resolve logical floor names to peak gate stems for bot/_gates_<stem>.py.

IMPORTANT:
- EdgePolicy / floor_tracker keep the LOGICAL floor name (LIVE, JUN19, MAY10, …)
- Only gate *file load* uses the alias stem (ELITE_V2, JUN19_peak, …)

Do NOT overwrite floor_tracker.get_floor() with the gate stem — that breaks
EdgePolicy floor allowlists (JUN19 would become JUN19_peak and get DENY_FLOOR).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

_PATH = Path(__file__).resolve().parent / "data" / "luxury_live_floors.json"

# Fallback if luxury_live_floors.json is missing
GATE_ALIASES = {
    "LIVE": "ELITE_V2",
    "APR19": "APR19_golden",
    "APR20": "APR20_perfect",
    "APR20_MAX": "APR20_perfect",
    "APR22": "APR22",
    "APR26": "APR27",
    "APR27": "APR27",
    "APR28": "APR28_complex",
    "APR29": "APR29",
    "APR30": "APR30_peak",
    "ELITE_V2": "ELITE_V2",
    "ELITE_V2_PEAK": "ELITE_V2_PEAK",
    "JUN06": "JUN06_peak",
    "JUN08": "JUN08_peak",
    "JUN10": "JUN10_peak",
    "JUN12A": "JUN12_avalanche",
    "JUN12B": "JUN12_eliteguard",
    "JUN19": "JUN19_peak",
    "JUN20": "JUN20_peak",
    "JUN26": "JUN26",
    "JUN27": "JUN27_peak",
    "MAR19": "MAR19",
    "MAR20": "MAR20",
    "MAR21": "MAR21",
    "MAY01": "MAY01_peak",
    "MAY04": "MAY04",
    "MAY10": "MAY10_peak",
    "MAY11": "MAY11_peak",
    "MAY19": "MAY19_peak",
    "MAY20": "MAY20_peak",
    "MAY21": "MAY21_peak",
    "MAY22": "MAY22_peak",
    "MAY23": "MAY23_peak",
    "MAY24": "MAY24_peak",
    "MAY25": "MAY25_peak",
    "MAY26": "MAY26_peak",
    "MAY27": "MAY27_peak",
    "ULTIMATE": "ULTIMATE",
    "AITEST_ULTIMATE": "ULTIMATE",
    "AITEST_APR20_MAX": "APR20_perfect",
    "AITEST_LIVE": "ELITE_V2",
    "AITEST_APR20": "APR20_perfect",
    "AITEST_MAR21": "MAR21",
}


def _aliases() -> dict:
    try:
        data = json.loads(_PATH.read_text(encoding="utf-8"))
        raw = data.get("gate_aliases") or {}
        if isinstance(raw, dict) and raw:
            return {str(k).upper(): str(v) for k, v in raw.items()}
    except Exception:
        pass
    return dict(GATE_ALIASES)


def resolve_gate(floor: Optional[str]) -> str:
    """Logical floor -> gate stem used in bot/_gates_<stem>.py."""
    name = (floor or "LIVE").strip().upper()
    try:
        data = json.loads(_PATH.read_text(encoding="utf-8"))
        blocked = {str(x).upper() for x in (data.get("blocked") or [])}
        if name in blocked:
            return name
    except Exception:
        pass
    aliases = _aliases()
    return str(aliases.get(name, name)).strip() or name


# Back-compat alias
resolve_gate_stem = resolve_gate


def live_floors():
    try:
        data = json.loads(_PATH.read_text(encoding="utf-8"))
        return [str(x).upper() for x in (data.get("live_floors") or [])]
    except Exception:
        return ["LIVE"]
