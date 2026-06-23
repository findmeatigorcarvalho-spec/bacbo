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
_FLOOR_FACTORY_REPORT = _DIR / "data" / "skyscraper_floor_factory_report.json"
_CACHE = {"ts": 0.0, "data": None}
_JSON_CACHE: dict[str, dict] = {}


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


def _load_json(path: Path) -> dict:
    now = time.time()
    cache_key = str(path)
    cached = _JSON_CACHE.get(cache_key)
    if cached and now - float(cached.get("ts", 0.0)) < 30:
        return cached.get("data") or {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = {}
    _JSON_CACHE[cache_key] = {"ts": now, "data": data}
    return data


def _mode() -> str:
    mode = os.environ.get("EDGE_POLICY_MODE", "shadow").strip().lower()
    return mode if mode in {"shadow", "precision", "volume"} else "shadow"


def _key_from_floor_rule(item: dict) -> str | None:
    family = str(item.get("family") or "").upper()
    rule = item.get("rule") or {}
    if not isinstance(rule, dict):
        return None

    color = str(rule.get("color") or "").strip().lower()
    if not color:
        return None

    if family == "ROOM_HOUR_COLOR":
        room = _norm_room(str(rule.get("room") or ""))
        hour = rule.get("hour")
        return f"{room}:H{int(hour)}:{color}" if room and hour is not None else None

    if family == "FLOOR_KIND_HOUR_COLOR":
        floor = str(rule.get("floor") or "LIVE").strip().upper()
        kind = str(rule.get("kind") or "").strip().upper()
        hour = rule.get("hour")
        return f"{floor}:{kind}:H{int(hour)}:{color}" if kind and hour is not None else None

    if family == "G0_OFFSET":
        kind = str(rule.get("kind") or "").strip().upper()
        floor = str(rule.get("floor") or "LIVE").strip().upper()
        return f"{kind}:{floor}:{color}" if kind else None

    if family == "LOSS_RISK":
        room = _norm_room(str(rule.get("room") or ""))
        floor = str(rule.get("floor") or "LIVE").strip().upper()
        kind = str(rule.get("kind") or "").strip().upper()
        hour = rule.get("hour")
        if room and kind and hour is not None:
            return f"{room}:{floor}:{kind}:H{int(hour)}:{color}"
    return None


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

    factory = _load_json(_FLOOR_FACTORY_REPORT)
    for section in ("precision", "balanced"):
        for item in factory.get(section, []):
            key = _key_from_floor_rule(item)
            if key:
                elite.add(key)

    for item in factory.get("volume", []):
        key = _key_from_floor_rule(item)
        if key:
            watch.add(key)

    for item in factory.get("blocked", []):
        key = _key_from_floor_rule(item)
        if key:
            loss.add(key)

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
