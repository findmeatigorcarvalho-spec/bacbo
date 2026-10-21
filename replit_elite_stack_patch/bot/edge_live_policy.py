"""
edge_live_policy.py — live/shadow policy for Edge Whitelist Engine.

Modes:
  shadow    = observe only; never blocks
  precision = SNIPER/ELITE cells fire; non-whitelist and loss-risk block
  volume    = SNIPER/ELITE + WATCH cells fire; loss-risk blocks
  luxury    = all WR>=60 live-building floors fire; blocked floors + loss-risk block

Set with:
  EDGE_POLICY_MODE=shadow|precision|volume|luxury
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from zoneinfo import ZoneInfo


_DIR = Path(__file__).resolve().parent
_REPORT = _DIR / "data" / "edge_whitelist_engine.json"
_FLOOR_FACTORY_REPORT = _DIR / "data" / "skyscraper_floor_factory_report.json"
_LEGACY_355_REPORT = _DIR / "data" / "legacy_peak_355_report.json"
_LUXURY_STACK_REPORT = _DIR / "data" / "luxury_building_stack.json"
_FLOOR_REGISTRY_REPORT = _DIR / "data" / "floor_stack_registry_report.json"
_HISTORICAL_SEED = _DIR / "data" / "historical_luxury_seed.json"
_LUXURY_LIVE_FLOORS = _DIR / "data" / "luxury_live_floors.json"
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
    if mode not in {"shadow", "precision", "volume", "luxury"}:
        mode = "shadow"
    # Never stay observe-only when luxury building is installed on disk.
    if mode == "shadow" and (
        _LUXURY_LIVE_FLOORS.exists()
        or (_DIR.parent / "luxury_building.env").exists()
        or (Path("/home/runner/workspace") / "luxury_building.env").exists()
    ):
        return "luxury"
    return mode


def _luxury_sets() -> tuple[set[str], set[str]]:
    """Return (live_building floors, blocked floors) for luxury gate."""
    live: set[str] = set()
    blocked: set[str] = {"JUN12A", "JUN12B"}

    lux = _load_json(_LUXURY_STACK_REPORT)
    for name in lux.get("live_building_floors") or []:
        if name:
            live.add(str(name).strip().upper())
    for name in lux.get("blocked_floors") or []:
        if name:
            blocked.add(str(name).strip().upper())

    allow = _load_json(_LUXURY_LIVE_FLOORS)
    for name in allow.get("live_floors") or []:
        if name:
            live.add(str(name).strip().upper())
    for name in allow.get("blocked") or []:
        if name:
            blocked.add(str(name).strip().upper())
    for name in allow.get("peak_day_floors") or []:
        if name:
            live.add(str(name).strip().upper())

    # Historical seed always contributes force-live floors (survives truncated DB).
    seed = _load_json(_HISTORICAL_SEED)
    for name in seed.get("hard_block") or []:
        if name:
            blocked.add(str(name).strip().upper())
    for item in seed.get("floors") or []:
        if isinstance(item, dict) and item.get("floor") and item.get("force_live", True):
            live.add(str(item["floor"]).strip().upper())
    for item in seed.get("peak_day_floors") or []:
        if isinstance(item, dict) and item.get("floor"):
            live.add(str(item["floor"]).strip().upper())
        elif isinstance(item, str):
            live.add(item.strip().upper())

    # Fallback to registry lanes if luxury stack not generated yet.
    if len(live) < 5:
        reg = _load_json(_FLOOR_REGISTRY_REPORT)
        for section in ("precision", "balanced", "volume", "live_building"):
            for item in reg.get(section, []) or []:
                if isinstance(item, dict) and item.get("floor"):
                    live.add(str(item["floor"]).strip().upper())
                elif isinstance(item, str):
                    live.add(item.strip().upper())
        for item in reg.get("blocked", []) or []:
            if isinstance(item, dict) and item.get("floor"):
                blocked.add(str(item["floor"]).strip().upper())

    # Always keep core production floors if reports are empty.
    if not live:
        live.update({"LIVE", "ELITE_V2", "ULTIMATE"})

    # Hard blocks win.
    live -= blocked
    return live, blocked


def _minutes(value: str) -> int | None:
    try:
        hour, minute = str(value).split(":", 1)
        return int(hour) * 60 + int(minute)
    except Exception:
        return None


def _active_legacy_window(item: dict, report: dict) -> bool:
    if os.environ.get("EDGE_LEGACY_355_ALWAYS_WARN", "").strip() == "1":
        return True
    start = _minutes(str(item.get("window_start") or ""))
    end = _minutes(str(item.get("window_end") or ""))
    if start is None or end is None:
        # Compatibility with older fixed 3:55 reports.
        start = _minutes((report.get("window_local") or {}).get("start", "03:30"))
        end = _minutes((report.get("window_local") or {}).get("end", "03:59"))
    if start is None or end is None:
        return False
    try:
        tz_name = str(report.get("timezone") or "America/New_York")
        local = datetime.now(timezone.utc).astimezone(ZoneInfo(tz_name))
        current = local.hour * 60 + local.minute
    except Exception:
        return False
    if start <= end:
        return start <= current <= end
    return current >= start or current <= end


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


def _legacy_355_warning(kind: str, color: str, floor: str, rooms: list[str]) -> str | None:
    if os.environ.get("EDGE_LEGACY_355_WARN", "1").strip().lower() in {"0", "false", "no"}:
        return None

    report = _load_json(_LEGACY_355_REPORT)
    live_keys = report.get("live_warning_keys", [])
    if not isinstance(live_keys, list):
        return None

    candidates = {f"{floor}:{kind}:{color}"}
    for room in rooms:
        candidates.add(f"{room}:{floor}:{kind}:{color}")

    for item in live_keys:
        if not isinstance(item, dict):
            continue
        key = str(item.get("key") or "")
        if key not in candidates:
            continue
        if not _active_legacy_window(item, report):
            continue
        warning = str(item.get("warning") or report.get("legacy_warning") or "")
        tier = str(item.get("legacy_tier") or "LEGACY_355_PAWTUCKET")
        wr = item.get("wr")
        g0_wr = item.get("g0_wr")
        n = item.get("n")
        window = f"{item.get('window_start', '?')}-{item.get('window_end', '?')} {report.get('timezone', 'America/New_York')}"
        stats = f"{tier} key={key} window={window} n={n} wr={wr} g0={g0_wr}"
        return f"{warning} | {stats}".strip()
    return None


def _verdict(action: str, reason: str, matched: list[str], mode: str, legacy_warning: str | None) -> dict:
    out = {"action": action, "reason": reason, "matched": matched, "mode": mode}
    if legacy_warning:
        out["legacy_warning"] = legacy_warning
    return out


def evaluate_one(
    kind: str,
    color: str,
    agreeing_rooms: Iterable[str] | None,
    source_floor: str = "LIVE",
    hour_utc: int | None = None,
) -> dict:
    """Return a live policy verdict for ONE floor (no tower merge)."""
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
    legacy_warning = _legacy_355_warning(kind, color, floor, rooms)
    live_floors, blocked_floors = _luxury_sets()
    floor_gate = os.environ.get("EDGE_LUXURY_FLOOR_GATE", "1").strip() not in {"0", "false", "no"}

    if mode == "shadow":
        if floor in blocked_floors:
            return _verdict(
                "SHADOW_BLOCK",
                f"EDGE_FLOOR_BLOCKED {floor}",
                [floor],
                mode,
                legacy_warning,
            )
        if matched_loss:
            return _verdict(
                "SHADOW_BLOCK",
                "EDGE_LOSS_RISK " + ", ".join(matched_loss[:3]),
                matched_loss,
                mode,
                legacy_warning,
            )
        if matched_elite:
            return _verdict(
                "SHADOW_ALLOW",
                "EDGE_SNIPER " + ", ".join(matched_elite[:3]),
                matched_elite,
                mode,
                legacy_warning,
            )
        if matched_watch:
            return _verdict(
                "SHADOW_ALLOW",
                "EDGE_WATCH " + ", ".join(matched_watch[:3]),
                matched_watch,
                mode,
                legacy_warning,
            )
        return _verdict("SHADOW_ALLOW", "EDGE_NO_MATCH", [], mode, legacy_warning)

    # Hard floor blocks always apply outside shadow (toxic JUN12A/B only).
    if floor in blocked_floors:
        return _verdict(
            "BLOCK",
            f"EDGE_FLOOR_BLOCKED {floor}",
            [floor],
            mode,
            legacy_warning,
        )

    free_propose = os.environ.get("FREE_PROPOSE", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }
    # FREE_PROPOSE: no WR/loss/volume mute on propose path — hub orchestrates output.
    if free_propose:
        floor_gate = False
        matched_loss = []  # do not BLOCK propose for loss-risk cells

    if matched_loss:
        return _verdict(
            "BLOCK",
            "EDGE_LOSS_RISK " + ", ".join(matched_loss[:3]),
            matched_loss,
            mode,
            legacy_warning,
        )

    # Luxury mode: every WR>=60 live-building floor can fire (plus sniper/watch cells).
    if mode == "luxury":
        if floor_gate and floor not in live_floors:
            return _verdict(
                "BLOCK",
                f"EDGE_FLOOR_NOT_IN_LUXURY {floor}",
                [floor],
                mode,
                legacy_warning,
            )
        if matched_elite:
            return _verdict(
                "ALLOW",
                "EDGE_LUXURY_SNIPER " + ", ".join(matched_elite[:3]),
                matched_elite,
                mode,
                legacy_warning,
            )
        if matched_watch:
            return _verdict(
                "ALLOW",
                "EDGE_LUXURY_WATCH " + ", ".join(matched_watch[:3]),
                matched_watch,
                mode,
                legacy_warning,
            )
        return _verdict(
            "ALLOW",
            f"EDGE_LUXURY_FLOOR {floor}",
            [floor],
            mode,
            legacy_warning,
        )

    if matched_elite:
        return _verdict(
            "ALLOW",
            "EDGE_SNIPER " + ", ".join(matched_elite[:3]),
            matched_elite,
            mode,
            legacy_warning,
        )

    if matched_watch:
        if mode == "volume":
            return _verdict(
                "ALLOW",
                "EDGE_WATCH_VOLUME " + ", ".join(matched_watch[:3]),
                matched_watch,
                mode,
                legacy_warning,
            )
        return _verdict(
            "BLOCK",
            "EDGE_WATCH_SHADOW " + ", ".join(matched_watch[:3]),
            matched_watch,
            mode,
            legacy_warning,
        )

    if mode == "precision":
        return _verdict("BLOCK", "EDGE_NOT_WHITELISTED", [], mode, legacy_warning)

    # volume mode also respects luxury floor allowlist when gate is on.
    if floor_gate and live_floors and floor not in live_floors:
        return _verdict(
            "BLOCK",
            f"EDGE_FLOOR_NOT_IN_LUXURY {floor}",
            [floor],
            mode,
            legacy_warning,
        )

    return _verdict("ALLOW", "EDGE_NO_MATCH_VOLUME", [], mode, legacy_warning)


def evaluate(
    kind: str,
    color: str,
    agreeing_rooms: Iterable[str] | None,
    source_floor: str = "LIVE",
    hour_utc: int | None = None,
) -> dict:
    """Public EdgePolicy entry — tower-merge when LUXURY_TOWER_MERGE=1."""
    merge_on = os.environ.get("LUXURY_TOWER_MERGE", "1").strip() not in {"0", "false", "no"}
    if merge_on:
        try:
            from lux_tower_merge import apply_winner_to_state, merge_candidate

            verdict = merge_candidate(
                kind=kind,
                color=color,
                agreeing_rooms=agreeing_rooms,
                engine_floor=source_floor or "LIVE",
                hour_utc=hour_utc,
            )
            wf = verdict.get("winner_floor") or source_floor or "LIVE"
            try:
                apply_winner_to_state(str(wf))
            except Exception:
                pass
            return verdict
        except Exception:
            pass
    return evaluate_one(
        kind=kind,
        color=color,
        agreeing_rooms=agreeing_rooms,
        source_floor=source_floor,
        hour_utc=hour_utc,
    )
