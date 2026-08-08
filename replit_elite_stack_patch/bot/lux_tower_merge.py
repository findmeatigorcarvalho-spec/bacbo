"""
lux_tower_merge.py — multi-floor EdgePolicy merge (v1).

Goal (LUXURY_GOAL.md):
  Every good live floor can ALLOW a candidate; we pick the best tower
  to stamp on the fire so no WR>=60 floor is silently ignored.

v1 scope (safe, shippable):
  - Still ONE engine fire path (LIVE brain decides the signal exists)
  - EdgePolicy is evaluated for ALL live-building floors (not just LIVE)
  - Winner floor is stamped onto source_floor / state for cards+DB
  - Opposite-color lock stays global AFTER this merge
  - Peak-gate *loaders* (JUN19 -> JUN19_peak file) are installed separately;
    full isolated peak-handler clones are v2

Enable: LUXURY_TOWER_MERGE=1 (default on when luxury_building.env present)
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
_JSON = DATA / "luxury_live_floors.json"
_STRENGTH = DATA / "peak_fidelity_ranker_report.json"
_strength_cache: dict[str, float] | None = None


def _enabled() -> bool:
    return os.environ.get("LUXURY_TOWER_MERGE", "1").strip() not in {"0", "false", "no"}


def _strength_map() -> dict[str, float]:
    """Load floor strength scores (peak WR/G0 ranker) for merge priority."""
    global _strength_cache
    if _strength_cache is not None:
        return _strength_cache
    out: dict[str, float] = {}
    try:
        data = json.loads(_STRENGTH.read_text(encoding="utf-8"))
        for row in data.get("ranking") or []:
            fl = str(row.get("floor") or "").upper()
            if fl:
                out[fl] = float(row.get("strength_score") or 0.0)
    except Exception:
        out = {}
    _strength_cache = out
    return out


def _load_floors() -> tuple[list[str], list[str], set[str]]:
    """Return (priority_floors, all_live, blocked)."""
    blocked = {"JUN12A", "JUN12B"}
    peaks: list[str] = []
    live: list[str] = []
    try:
        data = json.loads(_JSON.read_text(encoding="utf-8"))
        blocked |= {str(x).upper() for x in (data.get("blocked") or [])}
        peaks = [str(x).upper() for x in (data.get("peak_day_floors") or [])]
        live = [
            str(x).upper()
            for x in (data.get("live_floors") or data.get("live_building_floors") or [])
        ]
    except Exception:
        peaks = ["JUN19", "JUN20", "JUN08", "JUN10", "JUN26", "JUN27", "MAY19", "MAY10"]
        live = list(peaks) + ["LIVE", "ELITE_V2", "MAR19", "MAR20", "MAR21"]

    # Priority: strength rank (if report exists) among peaks, else peak_day order, then live.
    strength = _strength_map()
    if strength:
        peaks_sorted = sorted(
            [p for p in peaks if p not in blocked],
            key=lambda f: strength.get(f, 0.0),
            reverse=True,
        )
        if peaks_sorted:
            peaks = peaks_sorted

    ordered: list[str] = []
    for name in peaks + live + ["LIVE"]:
        if name in blocked:
            continue
        if name not in ordered:
            ordered.append(name)
    if not ordered:
        ordered = ["LIVE"]
    return peaks, ordered, blocked


def _rank(verdict: dict[str, Any], floor: str, peaks: list[str]) -> tuple:
    """Higher tuple wins. Peak + strength_score + sniper/watch beat LIVE."""
    action = str(verdict.get("action") or "")
    reason = str(verdict.get("reason") or "")
    if action not in {"ALLOW", "SHADOW_ALLOW"}:
        return (-1, -1, -1, -999.0, -999, floor)
    tier = 1
    if "SNIPER" in reason:
        tier = 3
    elif "WATCH" in reason:
        tier = 2
    is_peak = 1 if floor in peaks else 0
    is_named = 1 if floor not in {"LIVE", ""} else 0
    strength = float(_strength_map().get(floor, 0.0))
    try:
        peak_ord = len(peaks) - peaks.index(floor) if floor in peaks else 0
    except Exception:
        peak_ord = 0
    return (is_peak, is_named, tier, strength, peak_ord, floor)


def merge_candidate(
    *,
    kind: str,
    color: str,
    agreeing_rooms: Any,
    engine_floor: str = "LIVE",
    hour_utc: int | None = None,
) -> dict[str, Any]:
    """
    Evaluate EdgePolicy across all live floors; return merged verdict.

    If ANY floor ALLOWs → ALLOW with winning floor.
    If ALL BLOCK → BLOCK.
    """
    if not _enabled():
        from edge_live_policy import evaluate_one

        return evaluate_one(
            kind=kind,
            color=color,
            agreeing_rooms=agreeing_rooms,
            source_floor=engine_floor or "LIVE",
            hour_utc=hour_utc,
        )

    from edge_live_policy import evaluate_one

    peaks, floors, blocked = _load_floors()
    hour = hour_utc if hour_utc is not None else time.gmtime().tm_hour

    allows: list[tuple[tuple, dict[str, Any], str]] = []
    blocks: list[tuple[str, str]] = []
    proposals: list[dict[str, Any]] = []
    free = os.environ.get("FREE_PROPOSE", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }
    v2 = os.environ.get("V2_PROPOSERS", "0").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }

    for floor in floors:
        if floor in blocked:
            continue
        try:
            v = evaluate_one(
                kind=kind,
                color=color,
                agreeing_rooms=agreeing_rooms,
                source_floor=floor,
                hour_utc=hour,
            )
        except Exception as exc:
            blocks.append((floor, f"eval_error:{exc}"))
            if free:
                # Still propose — hub decides; mute gates do not kill propose path
                v = {
                    "action": "ALLOW",
                    "reason": f"FREE_PROPOSE_EVAL_ERR:{exc}",
                    "matched": [],
                    "mode": os.environ.get("EDGE_POLICY_MODE", "luxury"),
                    "score": 0.0,
                }
            else:
                continue
        action = str(v.get("action") or "")
        # FREE_PROPOSE: convert mute BLOCKs into proposals (hub orchestrates)
        if free and action in {"BLOCK", "SHADOW_BLOCK"}:
            reason0 = str(v.get("reason") or "")
            if "EDGE_FLOOR_BLOCKED" in reason0 and floor in blocked:
                blocks.append((floor, reason0))
                continue
            v = dict(v)
            v["action"] = "ALLOW"
            v["reason"] = f"FREE_PROPOSE·was:{reason0}"
            action = "ALLOW"
        if action in {"ALLOW", "SHADOW_ALLOW"}:
            allows.append((_rank(v, floor, peaks), v, floor))
            strength = _strength_map().get(floor, 0.0)
            proposals.append(
                {
                    "floor": floor,
                    "color": color,
                    "kind": kind,
                    "score": float(strength or 0.0)
                    + (10.0 if action == "ALLOW" else 5.0),
                    "window_id": f"{kind}:{color}:{hour}",
                    "lane": "MONEY",
                    "reason": str(v.get("reason") or ""),
                    "engine_floor": engine_floor,
                }
            )
        elif action in {"BLOCK", "SHADOW_BLOCK"}:
            blocks.append((floor, str(v.get("reason") or action)))

    # v2: every allow is a free proposer into the hub queue
    if v2 and proposals:
        try:
            from v2_floor_proposers import enqueue_proposal

            for p in proposals:
                enqueue_proposal(p)
        except Exception as exc:
            print("[TOWER] enqueue_proposal skip:", repr(exc))
        try:
            from hub_impact_learner import observe_fire

            rooms = []
            if agreeing_rooms:
                rooms = [str(r) for r in agreeing_rooms]
            n_prop = max(len(proposals), len(rooms), 1)
            observe_fire(
                floors=[p["floor"] for p in proposals],
                rooms=rooms,
                color=color,
                kind=kind,
                origin="COALITION" if n_prop >= 2 else "SOLO_FACT",
                mode="COALITION" if n_prop >= 2 else "SINGULAR",
            )
        except Exception:
            pass

    if allows:
        # HUB orchestrator picks primary among free proposers (not just merge stamp)
        best_floor = None
        best_v = None
        try:
            from hub_orchestrator import enabled as _hub_on, orchestrate

            if _hub_on() and proposals:
                decision = orchestrate(proposals, primary_peer="UNIQUE_g1")
                prim = decision.get("primary") or {}
                best_floor = str(prim.get("floor") or "")
                print(f"[HUB] {decision.get('why')}")
        except Exception as exc:
            print("[HUB] orchestrate skip:", repr(exc))

        if not best_floor:
            allows.sort(key=lambda x: x[0], reverse=True)
            _score, best_v, best_floor = allows[0]
        else:
            for _sc, vv, ff in allows:
                if ff == best_floor:
                    best_v = vv
                    break
            if best_v is None:
                allows.sort(key=lambda x: x[0], reverse=True)
                _score, best_v, best_floor = allows[0]

        out = dict(best_v)
        out["action"] = "ALLOW"
        out["winner_floor"] = best_floor
        out["tower_allows"] = [f for _, _, f in allows]
        out["hub_proposals"] = len(proposals)
        out["reason"] = (
            f"HUB_ORCH {best_floor} · {len(allows)} proposers · "
            f"{best_v.get('reason', '')}"
        )
        return out

    # Nobody allowed
    reason = "TOWER_MERGE_ALL_BLOCKED"
    if blocks:
        reason = f"TOWER_MERGE_ALL_BLOCKED · {blocks[0][0]}:{blocks[0][1]}"
    return {
        "action": "BLOCK",
        "reason": reason,
        "matched": [],
        "mode": os.environ.get("EDGE_POLICY_MODE", "luxury"),
        "legacy_warning": None,
        "winner_floor": engine_floor or "LIVE",
        "tower_allows": [],
    }


def apply_winner_to_state(winner_floor: str) -> None:
    """Stamp winner onto state / lux tag so DB+cards see the tower floor."""
    if not winner_floor:
        return
    floor = str(winner_floor).strip().upper()
    try:
        import sys

        for name in ("state", "__main__", "bacbo_royal_complete"):
            mod = sys.modules.get(name)
            if mod is None:
                continue
            try:
                setattr(mod, "_current_source_floor", floor)
                setattr(mod, "_lux_tag_floor", floor)
                setattr(mod, "_lux_tower_winner", floor)
            except Exception:
                pass
            st = getattr(mod, "state", None)
            if st is not None:
                try:
                    setattr(st, "_current_source_floor", floor)
                    setattr(st, "_lux_tag_floor", floor)
                    setattr(st, "_lux_tower_winner", floor)
                except Exception:
                    pass
    except Exception:
        pass
    # Align rotator tag so outbox matches merge winner for this fire
    try:
        import lux_floor_rotate as lfr

        with lfr._LOCK:
            lfr._FLOOR = floor
            floors = lfr._rotation_list()
            if floor in floors:
                lfr._IDX = floors.index(floor)
            lfr._LAST_ADV = time.time()
            lfr._sync_tag_state_unlocked(floor)
    except Exception:
        pass
