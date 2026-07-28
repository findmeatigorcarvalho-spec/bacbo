#!/usr/bin/env python3
"""
hub_max_boot.py — apply HUB MAX locks on Replit.

Locks:
  1) Every config decides/analyzes/fires SEPARATE at its own peak-volume day (no shrink gates)
  2) Original card skins — strip noise, refresh facts only
  3) Gunique (@UNIQUE_g1) = priority #1, 24/7 fill-first; money chat #2; rest cascade

Writes bot/data/hub_max_status.json and merges keys into luxury_building.env
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path


HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
STATUS = DATA / "hub_max_status.json"


def _workspace_root() -> Path:
    candidates = [
        Path("/home/runner/workspace"),
        HERE.parent.parent,  # repo root when nested
        HERE.parent,
        Path.cwd(),
    ]
    for c in candidates:
        if (c / "bacbo_royal_complete.py").exists() or (c / "luxury_building.env").exists():
            return c
    # Replit default even if engine file name differs
    if Path("/home/runner/workspace").is_dir():
        return Path("/home/runner/workspace")
    return Path.cwd()


ROOT = _workspace_root()
ENV_PATH = ROOT / "luxury_building.env"

# Gunique first, then money, then specialists
CHAT_PRIORITY = [
    "UNIQUE_g1",  # #1 — 24/7
    "6774605259",  # #2 — Mr_iv4 / PLAY
    "SOLO",
    "GOLDEN",
    "SEQUENCE",
    "MIX",
    "OPS",
]

ENV_KEYS = {
    "HUB_MAX": "1",
    "VOLUME_MODE": "EXPLOSION",
    "V2_PROPOSERS": "1",
    "TELEGRAM_MIRROR_MONEY_TO_GUNIQUE": "0",
    "TELEGRAM_SINGLE_OUTBOX": "1",
    "TELEGRAM_COUNTDOWN_PEER": "UNIQUE_g1",
    "GUNIQUE_PEER": "UNIQUE_g1",
    "PACKER_REAL_COUNTDOWN_MAX": "30",
    "PACKER_HUB_CHAT": "PLAY",
    "HUB_CHAT_PRIORITY": "UNIQUE_g1,6774605259,SOLO,GOLDEN,SEQUENCE,MIX,OPS",
    "HUB_GUNIQUE_FIRST": "1",
    "HUB_CONFIG_SEPARATE": "1",
    "HUB_NO_SHRINK_GATES": "1",
    "HUB_ORIGINAL_CARD_SKINS": "1",
    "HUB_STRIP_NOISE_ONLY": "1",
    "HUB_GUNIQUE_TRUST_MIN": "78",
    "HUB_CATCHUP_MAX_PER_TICK": "4",
    "HUB_ENGINE_ROUTE": "1",
    "HUB_OUTBOX_FIRE_CARDS": "0",
    "HUB_OUTBOX_RESULT_CARDS": "0",
    "LUXURY_TOWER_MERGE": "1",
    "FALLBACKS_ENABLED": "1",
}


def _upsert_env(path: Path, keys: dict[str, str]) -> None:
    lines: list[str] = []
    if path.exists():
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    seen: set[str] = set()
    out: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("export ") and "=" in stripped:
            k = stripped[len("export ") :].split("=", 1)[0].strip()
            if k in keys:
                out.append(f"export {k}={keys[k]}")
                seen.add(k)
                continue
        out.append(line)
    for k, v in keys.items():
        if k not in seen:
            out.append(f"export {k}={v}")
    path.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")


def apply() -> dict:
    DATA.mkdir(parents=True, exist_ok=True)
    peer = os.environ.get("TELEGRAM_TARGET_PEER", "6774605259")
    cd = (
        os.environ.get("TELEGRAM_COUNTDOWN_PEER")
        or os.environ.get("GUNIQUE_PEER")
        or "UNIQUE_g1"
    ).strip().strip('"').strip("'").lstrip("@")
    keys = dict(ENV_KEYS)
    keys["TELEGRAM_TARGET_PEER"] = peer
    keys["TELEGRAM_COUNTDOWN_PEER"] = cd
    keys["GUNIQUE_PEER"] = cd
    keys["HUB_CHAT_PRIORITY"] = f"{cd},{peer},SOLO,GOLDEN,SEQUENCE,MIX,OPS"
    # Numeric id bypasses ResolveUsername FloodWait / UsernameNotOccupied
    for id_key in (
        "TELEGRAM_GUNIQUE_PEER_ID",
        "GUNIQUE_PEER_ID",
        "TELEGRAM_COUNTDOWN_PEER_ID",
    ):
        raw = (os.environ.get(id_key) or "").strip().strip('"').strip("'")
        if raw and raw.lstrip("-").isdigit():
            keys[id_key] = raw
            break

    _upsert_env(ENV_PATH, keys)
    for k, v in keys.items():
        os.environ[k] = v

    # smoke packer
    packer_ok = False
    packer_demo = None
    try:
        from window_packer import SignalCandidate, WindowPacker

        p = WindowPacker()
        t0 = time.time()
        d1 = p.intake(
            SignalCandidate("boot_long", "COUNTDOWN", "red", 87, 5, 78, detected_at=t0),
            now=t0,
        )
        d2 = p.intake(
            SignalCandidate("boot_solo", "SOLO_ELITE", "blue", None, 4, 80, detected_at=t0 + 1),
            now=t0 + 1,
        )
        packer_ok = d1.action == "HOLD_UNTIL_REAL" and d2.action == "ALLOW"
        packer_demo = {"long": d1.action, "solo": d2.action}
    except Exception as exc:
        packer_demo = {"error": repr(exc)}

    status = {
        "applied_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "locks": {
            "config_separate_peak_volume": True,
            "no_shrink_gates": True,
            "original_card_skins": True,
            "gunique_first_24_7": True,
            "real_countdown_release_lte_30s": True,
        },
        "chat_priority": [cd, peer, "SOLO", "GOLDEN", "SEQUENCE", "MIX", "OPS"],
        "env_path": str(ENV_PATH),
        "env_keys": keys,
        "packer_ok": packer_ok,
        "packer_demo": packer_demo,
        "next": [
            "Gunique (#1) fills first 24/7",
            "Money chat (#2) next",
            "Specialists cascade — elastic spawn if >~3/min",
            "Each config fires like its own best volume day",
        ],
    }
    STATUS.write_text(json.dumps(status, indent=2), encoding="utf-8")
    return status


if __name__ == "__main__":
    st = apply()
    print(json.dumps({
        "HUB_MAX": "APPLIED",
        "gunique_first": st["chat_priority"][0],
        "money_second": st["chat_priority"][1],
        "packer_ok": st["packer_ok"],
        "packer_demo": st["packer_demo"],
        "env": str(ENV_PATH),
    }, indent=2))
