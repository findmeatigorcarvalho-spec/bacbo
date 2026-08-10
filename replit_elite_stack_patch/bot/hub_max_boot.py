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

# Profit Chat Bundle: UNIQUE_g1 APEX #1 (Mr_iv4 removed)
CHAT_PRIORITY = [
    "UNIQUE_g1",  # #1 APEX — money + countdown + gale
    "UNIQUE_g2",  # PRECISION
    "UNIQUE_g3",  # VOLUME
    "UNIQUE_g4",  # ASSERTIVE
    "UNIQUE_g5",  # IMPACT
    "SOLO",
    "GOLDEN",
    "SEQUENCE",
    "MIX",
    "OPS",
]

ENV_KEYS = {
    "HUB_MAX": "1",
    "HUB_ORCHESTRATOR": "1",
    "VOLUME_MODE": "EXPLOSION",
    "V2_PROPOSERS": "1",
    "FREE_PROPOSE": "1",
    # No hour / WR / volume mute on propose path (24/7 into hub)
    "LUXURY_NO_HOUR_BLOCKS": "1",
    "EDGE_LUXURY_FLOOR_GATE": "0",
    "ROLLING_WR_MUTE_SECS": "0",
    "AUTO_QUARANTINE_SECS": "0",
    "TELEGRAM_MIRROR_MONEY_TO_GUNIQUE": "0",
    "TELEGRAM_SINGLE_OUTBOX": "1",
    "TELEGRAM_PRIMARY_PEER": "UNIQUE_g1",
    "TELEGRAM_PRIMARY_PEER_ID": "5855678138",
    "TELEGRAM_TARGET_PEER": "UNIQUE_g1",
    "TELEGRAM_COUNTDOWN_PEER": "UNIQUE_g1",
    "GUNIQUE_PEER": "UNIQUE_g1",
    # @UNIQUE_g1 numeric — avoids ResolveUsername / MONEY_FALLBACK race
    "TELEGRAM_GUNIQUE_PEER_ID": "5855678138",
    "GUNIQUE_PEER_ID": "5855678138",
    "TELEGRAM_EXCLUDE_PEERS": "Mr_iv4,6774605259",
    "PROFIT_CHAT_BUNDLE": "1",
    "HUB_G1_APEX_FIRST": "1",
    "HUB_MONEY_FIRST": "0",
    "PACKER_REAL_COUNTDOWN_MAX": "12",
    "PACKER_HUB_CHAT": "APEX",
    "HUB_CHAT_PRIORITY": "UNIQUE_g1,UNIQUE_g2,UNIQUE_g3,UNIQUE_g4,UNIQUE_g5,SOLO,GOLDEN,SEQUENCE,MIX,OPS",
    "HUB_GUNIQUE_FIRST": "1",
    "HUB_CONFIG_SEPARATE": "1",
    "HUB_NO_SHRINK_GATES": "1",
    "HUB_ORIGINAL_CARD_SKINS": "1",
    "HUB_STRIP_NOISE_ONLY": "1",
    "HUB_GUNIQUE_TRUST_MIN": "50",
    "HUB_CATCHUP_MAX_PER_TICK": "8",
    "HUB_ENGINE_ROUTE": "1",
    "HUB_OUTBOX_FIRE_CARDS": "0",
    # FIRE↔RESULT law: every FIRE gets RESULT card template skin (outbox guarantee).
    "HUB_OUTBOX_RESULT_CARDS": "1",
    "FIRE_RESULT_LAW": "1",
    "RESULT_ATTACH_IMMEDIATE": "1",
    "LUXURY_TOWER_MERGE": "1",
    "FALLBACKS_ENABLED": "1",
    "BACBO_READY_SECS": "12",
    "FALLBACK_START_DELAY_SECS": "15",
    # Outbox MUST share bacbo's client — standalone steals AuthKey and kills bot_live
    "TELEGRAM_OUTBOX_INLINE": "1",
    "TELEGRAM_OUTBOX_STARTUP_PING": "0",
    "OUTBOX_INLINE_SETTLE_SECS": "70",
    "LUX_SESSION_GUARD": "1",
    "LUX_SESSION_RECONNECTS": "12",
    "BACBO_SESSION_SETTLE_SECS": "28",
    "BACBO_AUTHKEY_SETTLE_SECS": "40",
    # Skip heavy iter_dialogs warm when cache already hot (cuts boot RSS / OOM -9)
    "LUX_DIALOG_WARM": "cache",
    "LUX_FLASK_GUARD": "1",
    "LUX_KEEPALIVE_OFF": "1",
    "FLASK_DEBUG": "0",
    "BUNDLE_ORGANIZER": "1",
    "LUX_CHAT_WATCHDOG": "1",
    "LUX_BLOCK_ESTUDO": "1",
    "LUX_CHAT_WATCH_CALL": "0",
    "LUX_CHAT_WATCH_CALL_ON_CONNECT": "1",
    "LUX_CHAT_WATCH_CALL_EARLY_SECS": "12",
    "LUX_CHAT_WATCH_CALL_AFTER_SETTLE": "1",
    # EMANATION LAWS — factual color, vertical signal#, hermetic chats
    "EMANATION_LAWS": "1",
    "COLOR_TRUTH_FACTUAL": "1",
    "SIGNAL_BUNDLE_VERTICAL": "1",
    "CHAT_HERMETIC": "1",
    "RESULT_REPLY_TO_FIRE": "1",
}


def _upsert_env(path: Path, keys: dict[str, str]) -> None:
    """Upsert keys; drop duplicate bare/export lines for the same key."""
    lines: list[str] = []
    if path.exists():
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    seen: set[str] = set()
    out: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            out.append(line)
            continue
        body = stripped
        if body.startswith("export "):
            body = body[len("export ") :].strip()
        k = body.split("=", 1)[0].strip()
        if k in keys:
            if k in seen:
                continue  # drop duplicate
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
    peer = (
        os.environ.get("TELEGRAM_PRIMARY_PEER")
        or os.environ.get("TELEGRAM_TARGET_PEER")
        or "UNIQUE_g1"
    ).strip().strip('"').strip("'").lstrip("@")
    if peer in {"6774605259", "Mr_iv4", "mr_iv4"}:
        peer = "UNIQUE_g1"
    cd = (
        os.environ.get("TELEGRAM_COUNTDOWN_PEER")
        or os.environ.get("TELEGRAM_PRIMARY_PEER")
        or os.environ.get("GUNIQUE_PEER")
        or "UNIQUE_g1"
    ).strip().strip('"').strip("'").lstrip("@")
    if cd in {"6774605259", "Mr_iv4", "mr_iv4"}:
        cd = "UNIQUE_g1"
    keys = dict(ENV_KEYS)
    keys["TELEGRAM_PRIMARY_PEER"] = peer
    keys["TELEGRAM_TARGET_PEER"] = peer
    keys["TELEGRAM_COUNTDOWN_PEER"] = cd
    keys["GUNIQUE_PEER"] = cd
    keys["TELEGRAM_EXCLUDE_PEERS"] = "Mr_iv4,6774605259"
    keys["HUB_CHAT_PRIORITY"] = (
        f"{cd},UNIQUE_g2,UNIQUE_g3,UNIQUE_g4,UNIQUE_g5,SOLO,GOLDEN,SEQUENCE,MIX,OPS"
    )
    # Numeric id bypasses ResolveUsername FloodWait / UsernameNotOccupied
    gid = ""
    for id_key in (
        "TELEGRAM_GUNIQUE_PEER_ID",
        "GUNIQUE_PEER_ID",
        "TELEGRAM_COUNTDOWN_PEER_ID",
    ):
        raw = (os.environ.get(id_key) or keys.get(id_key) or "").strip().strip('"').strip("'")
        if raw and raw.lstrip("-").isdigit():
            gid = raw
            keys["TELEGRAM_GUNIQUE_PEER_ID"] = raw
            keys["GUNIQUE_PEER_ID"] = raw
            break
    if not gid:
        gid = "5855678138"
        keys["TELEGRAM_GUNIQUE_PEER_ID"] = gid
        keys["GUNIQUE_PEER_ID"] = gid

    _upsert_env(ENV_PATH, keys)
    for k, v in keys.items():
        os.environ[k] = v

    # Seed entity cache so outbox / engine route hit numeric id immediately
    try:
        cache = DATA / "telegram_gunique_entity.json"
        cache.write_text(
            json.dumps(
                {
                    "target": cd,
                    "id": int(gid),
                    "username": cd,
                    "title": "Gunique",
                }
            )
            + "\n",
            encoding="utf-8",
        )
    except Exception as exc:
        print("[hub_max_boot] gunique cache seed skip:", repr(exc))

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
        "chat_priority": list(CHAT_PRIORITY),
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
