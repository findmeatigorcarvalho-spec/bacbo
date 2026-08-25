"""Force peak-volume free-fire. Overwrite, do not setdefault.

The live skins (SOLO / GOLDEN / SEQUENCE / PLATINUM + RESULT glue) already
have their timing. Volume died because later gates re-shrunk the propose
path: floor-gate stuck ON via setdefault(1) before setdefault(0), 90s
near-dup window collapsing distinct FIREs, catch-up cap 4–8, trust floor
blocking dispatch, PENDING_REVIEW on every family.

This module is the single switch: LUX_FREE_VOLUME=1 (default on).
It does not invent new skins. It does not disable ROUND_SYNC timing.
It does not let raw G2 ESTUDO 14-copy floods back in (coalition still
collapses those). It only removes shrink-gates on the historical FIRE+RESULT
path so UNIQUE_g1 can fill again.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DECISIONS = DATA / "signal_ledger_decisions.json"

# Overwrite — setdefault lost to stale luxury_building.env / Secrets.
FORCE_ENV: dict[str, str] = {
    "LUX_FREE_VOLUME": "1",
    "FREE_PROPOSE": "1",
    "VOLUME_MODE": "EXPLOSION",
    "V2_PROPOSERS": "1",
    "HUB_MAX": "1",
    "HUB_ORCHESTRATOR": "1",
    "HUB_NO_SHRINK_GATES": "1",
    "HUB_ORIGINAL_CARD_SKINS": "1",
    "LUXURY_NO_HOUR_BLOCKS": "1",
    "EDGE_LUXURY_FLOOR_GATE": "0",
    "ROLLING_WR_MUTE_SECS": "0",
    "AUTO_QUARANTINE_SECS": "0",
    "FALLBACK_SEND_BLOCKED": "0",
    # Every historical FIRE kind reaches UNIQUE_g1. Peer slot is always g1
    # after Mr_iv4 removal; 0 just stops a leftover 78-default from holding.
    "HUB_GUNIQUE_TRUST_MIN": "0",
    "HUB_CATCHUP_MAX_PER_TICK": "24",
    # Exact-dup only. 90s was collapsing distinct SEQUENCE/GOLDEN cards.
    # G2 ESTUDO 14-copy bursts are handled by g2_coalition, not this window.
    "LUX_SEND_DEDUP_SECS": "12",
    "HUB_OUTBOX_RESULT_CARDS": "1",
    "SEQUENCE_FAMILY_WAKE": "1",
    "SEQUENCE_OUTBOX_FIRE": "1",
    "FORENSIC_AS_FIRE": "1",
    "FORENSIC_COUNTDOWN_SECS": "28.5",
    "FIRE_RESULT_LAW": "1",
    "RESULT_ATTACH_IMMEDIATE": "1",
    "PACKER_HOLD_UNTIL_REAL": "0",
    "PRINTED_SECS_ARE_OUTCOME": "1",
    "LUX_G2_COALITION_TO_G1": "1",
}


def enabled() -> bool:
    return os.environ.get("LUX_FREE_VOLUME", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def apply_env(env: dict[str, str] | None = None) -> dict[str, str]:
    """Force volume keys onto os.environ and optionally a supervisor env dict."""
    if os.environ.get("LUX_FREE_VOLUME", "1").strip().lower() in {
        "0",
        "false",
        "no",
        "off",
    }:
        return {k: str((env or os.environ).get(k, "")) for k in FORCE_ENV}
    target = env if env is not None else os.environ
    for key, value in FORCE_ENV.items():
        target[key] = value
        os.environ[key] = value
    return {k: str(os.environ.get(k, "")) for k in FORCE_ENV}


def promote_fire_result_families(path: Path | None = None) -> dict[str, Any]:
    """Mark every FIRE_* / RESULT_* family G1_APEX unless already RETIRE.

    Does not touch OPS / ESTUDO / countdown-only rows. Routing still needs
    the engine to emit; this records the product decision so PENDING_REVIEW
    cannot be used as a reason to keep them off UNIQUE_g1.
    """
    p = path or DECISIONS
    report: dict[str, Any] = {"path": str(p), "promoted": [], "kept_retire": [], "n": 0}
    if not p.is_file():
        report["error"] = "missing"
        return report
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:
        report["error"] = repr(exc)
        return report
    families = data.get("families") or {}
    for fam, row in families.items():
        if not isinstance(row, dict):
            continue
        name = str(fam).upper()
        if not (name.startswith("FIRE_") or name.startswith("RESULT_")):
            continue
        if "ESTUDO" in name or "TRASH" in name:
            continue
        current = str(row.get("decision") or "").upper()
        if current == "RETIRE":
            report["kept_retire"].append(fam)
            continue
        if current != "G1_APEX":
            row["decision"] = "G1_APEX"
            row["shelf"] = "UNIQUE_g1"
            row["review_note"] = "LUX_FREE_VOLUME: historical FIRE/RESULT kit live on APEX"
            report["promoted"].append(fam)
        report["n"] += 1
    data["free_volume"] = True
    data["instructions"] = (
        "FIRE/RESULT families are G1_APEX under LUX_FREE_VOLUME. "
        "OPS stay OPS. RETIRE stays retired. FIRE/RESULT that already posted are live."
    )
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        report["ok"] = True
    except Exception as exc:
        report["error"] = repr(exc)
        report["ok"] = False
    return report


def boot() -> dict[str, Any]:
    env = apply_env()
    promo = promote_fire_result_families()
    hour_json: dict[str, Any] = {}
    try:
        from lux_no_hour_blocks import clear_persist_json as _clear_hours

        hour_json = _clear_hours()
        print(
            "[FREE-VOLUME] hour-blocks json",
            f"chb={hour_json.get('color_hour_blocks')}",
            f"intel={hour_json.get('intelligence_bad_hours')}",
        )
    except Exception as exc:
        print("[FREE-VOLUME] hour-blocks skip", repr(exc))
    reality: dict[str, Any] = {}
    try:
        import reality_law as _rl

        reality = _rl.boot()
    except Exception as exc:
        print("[FREE-VOLUME] reality-law skip", repr(exc))
    print(
        "[FREE-VOLUME] ON",
        f"floor_gate={env.get('EDGE_LUXURY_FLOOR_GATE')}",
        f"mute={env.get('ROLLING_WR_MUTE_SECS')}",
        f"trust_min={env.get('HUB_GUNIQUE_TRUST_MIN')}",
        f"dedup={env.get('LUX_SEND_DEDUP_SECS')}",
        f"catchup={env.get('HUB_CATCHUP_MAX_PER_TICK')}",
        f"promoted={len(promo.get('promoted') or [])}",
    )
    return {"env": env, "ledger": promo, "hour_blocks": hour_json, "reality": reality}


if __name__ == "__main__":
    boot()
