"""
edge_live_policy.py — live/shadow policy for Edge Whitelist Engine.

Modes:
  shadow    = observe only; never blocks
  precision = SNIPER/ELITE cells fire; non-whitelist and loss-risk block
  volume    = SNIPER/ELITE + WATCH cells fire; loss-risk blocks

Set with:
  EDGE_POLICY_MODE=shadow|precision|volume
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Iterable


_DIR = Path(__file__).resolve().parent
_REPORT = _DIR / "data" / "edge_whitelist_engine.json"
_CACHE = {"ts": 0.0, "data": None}


def _norm_room(room: str) -> str:
    return (room or "").strip().lstrip("@").lower()


def _load() -> dict:
    now = time.time()
    if _CACHE["data"] is not None and now - float(_CACHE["ts"]) < 30:
        return _CACHE["data"] or {}
    try:
        with open(_REPORT, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = {}
    _CACHE["data"] = data
    _CACHE["ts"] = now
    return data


def _mode() -> str:
    mode = os.environ.get("EDGE_POLICY_MODE", "shadow").strip().lower()
    return mode if mode in {"shadow", "precision", "volume"} else "shadow"


def _cell_sets(data: dict) -> tuple[set[str], set[str], set[str]]:
    elite: set[str] = set()
    watch: set[str] = set()
    loss: set[str] = set()

    for item in data.get("elite_edges", []):
        key = item.get("key")
        if key:
            elite.add(str(key))

    for item in data.get("watch_edges", []):
        key = item.get("key")
        if key:
            watch.add(str(key))

    for item in data.get("loss_risk_cells", []):
        key = item.get("cell")
        if key:
            loss.add(str(key))

    return elite, watch, loss


def evaluate(
    kind: str,
    color: str,
    agreeing_rooms: Iterable[str] | None,
    source_floor: str = "LIVE",
    hour_utc: int | None = None,
) -> dict:
    """Return a live policy verdict for one candidate signal."""
    data = _load()
    mode = _mode()
    kind = (kind or "").strip().upper()
    color = (color or "").strip().lower()
    floor = (source_floor or "LIVE").strip().upper()

    try:
        hour = int(hour_utc) if hour_utc is not None else time.gmtime().tm_hour
    except Exception:
        hour = time.gmtime().tm_hour

    rooms = [_norm_room(str(r)) for r in (agreeing_rooms or []) if _norm_room(str(r))]

    elite, watch, loss = _cell_sets(data)

    candidates: list[str] = [
        f"{floor}:{kind}:H{hour}:{color}",
        f"{kind}:{floor}:{color}",
    ]

    for room in rooms:
        candidates.append(f"{room}:H{hour}:{color}")
        candidates.append(f"{room}:{floor}:{kind}:H{hour}:{color}")

    matched_elite = [c for c in candidates if c in elite]
    matched_watch = [c for c in candidates if c in watch]
    matched_loss = [c for c in candidates if c in loss]

    if mode == "shadow":
        if matched_loss:
            return {
                "action": "SHADOW_BLOCK",
                "reason": "EDGE_LOSS_RISK " + ", ".join(matched_loss[:3]),
                "matched": matched_loss,
                "mode": mode,
            }
        if matched_elite:
            return {
                "action": "SHADOW_ALLOW",
                "reason": "EDGE_SNIPER " + ", ".join(matched_elite[:3]),
                "matched": matched_elite,
                "mode": mode,
            }
        if matched_watch:
            return {
                "action": "SHADOW_ALLOW",
                "reason": "EDGE_WATCH " + ", ".join(matched_watch[:3]),
                "matched": matched_watch,
                "mode": mode,
            }
        return {"action": "SHADOW_ALLOW", "reason": "EDGE_NO_MATCH", "matched": [], "mode": mode}

    if matched_loss:
        return {
            "action": "BLOCK",
            "reason": "EDGE_LOSS_RISK " + ", ".join(matched_loss[:3]),
            "matched": matched_loss,
            "mode": mode,
        }

    if matched_elite:
        return {
            "action": "ALLOW",
            "reason": "EDGE_SNIPER " + ", ".join(matched_elite[:3]),
            "matched": matched_elite,
            "mode": mode,
        }

    if matched_watch:
        if mode == "volume":
            return {
                "action": "ALLOW",
                "reason": "EDGE_WATCH_VOLUME " + ", ".join(matched_watch[:3]),
                "matched": matched_watch,
                "mode": mode,
            }
        return {
            "action": "BLOCK",
            "reason": "EDGE_WATCH_SHADOW " + ", ".join(matched_watch[:3]),
            "matched": matched_watch,
            "mode": mode,
        }

    if mode == "precision":
        return {"action": "BLOCK", "reason": "EDGE_NOT_WHITELISTED", "matched": [], "mode": mode}

    return {"action": "ALLOW", "reason": "EDGE_NO_MATCH_VOLUME", "matched": [], "mode": mode}
