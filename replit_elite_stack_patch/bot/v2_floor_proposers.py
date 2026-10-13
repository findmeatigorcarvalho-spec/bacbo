#!/usr/bin/env python3
"""
v2_floor_proposers.py — every peak floor PROPOSES (not just scores LIVE).

WHY THIS EXISTS
---------------
v1 (lux_tower_merge): ONE LIVE engine proposes → N floors SCORE → merge stamps ≤1.
That cannot replay 30+ peak days at once → VOLUME_GAP / silence / "slowing down."

v2: each peak floor is a free proposer with its own frozen peak gates.
Conflict referee runs AFTER proposals, and only as hard as VOLUME_MODE says.

VOLUME_MODE
-----------
  SAFE_MERGE  — ≤1 money card per conflict window (current bankroll-safe default)
  EXPLOSION   — each floor free-fires peak stream; lock ONLY opposite-color same window

Env:
  VOLUME_MODE=EXPLOSION|SAFE_MERGE   (default SAFE_MERGE until wired into engine)
  V2_PROPOSERS=1                     enable proposal path hooks
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
_PEAK_LOCK = DATA / "peak_lock_config.json"
_LIVE = DATA / "luxury_live_floors.json"
_FIDELITY = DATA / "peak_fidelity_ranker_report.json"
_REPORT = DATA / "v2_proposer_report.json"
_QUEUE = DATA / "v2_proposal_queue.jsonl"

BLOCKED = {"JUN12A", "JUN12B"}


def volume_mode() -> str:
    m = (os.environ.get("VOLUME_MODE") or "SAFE_MERGE").strip().upper()
    return m if m in {"SAFE_MERGE", "EXPLOSION"} else "SAFE_MERGE"


def proposers_enabled() -> bool:
    return os.environ.get("V2_PROPOSERS", "0").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def list_peak_floors() -> list[dict[str, Any]]:
    """All floors that should be independent proposers."""
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    cfg = _load_json(_PEAK_LOCK)
    towers = cfg.get("towers") or []
    if isinstance(towers, dict):
        # legacy shape {FLOOR: gate}
        towers = [{"floor": k, "gate": v} for k, v in towers.items()]
    for t in towers:
        if not isinstance(t, dict):
            continue
        fl = str(t.get("floor") or t.get("name") or "").upper()
        if not fl or fl in BLOCKED or fl in seen:
            continue
        seen.add(fl)
        out.append(
            {
                "floor": fl,
                "gate": t.get("gate") or t.get("gate_file"),
                "peak_day": t.get("peak_day") or t.get("max_day"),
                "lane": (t.get("lane") or "MONEY").upper(),
                "role": "PROPOSER",
            }
        )
    live = _load_json(_LIVE)
    for key in ("peak_day_floors", "live_floors", "live_building_floors"):
        for fl in live.get(key) or []:
            fl = str(fl).upper()
            if not fl or fl in BLOCKED or fl in seen:
                continue
            seen.add(fl)
            out.append(
                {
                    "floor": fl,
                    "gate": None,
                    "peak_day": None,
                    "lane": "MONEY",
                    "role": "PROPOSER",
                }
            )
    return out


def fidelity_gaps() -> dict[str, Any]:
    rep = _load_json(_FIDELITY)
    ranking = rep.get("ranking") or []
    gaps = [
        r
        for r in ranking
        if str(r.get("fidelity") or "")
        in {"VOLUME_GAP_VS_PEAK", "NO_LIVE_ATTRIBUTION"}
    ]
    return {
        "floors_ranked": len(ranking),
        "gap_or_silent": len(gaps),
        "gap_floors": [str(r.get("floor")) for r in gaps[:40]],
        "note": (
            "Gaps mean peak machines are installed but not freely proposing "
            "their peak-day stream (v1 single LIVE mouth)."
        ),
    }


def expected_peak_sum(peak_n_by_floor: dict[str, int] | None = None) -> dict[str, Any]:
    """
    Rough SHOULD volume: sum of each floor's peak_n (from fidelity report).
    This is the user's mental model — not a promise of zero collisions.
    """
    rep = _load_json(_FIDELITY)
    ranking = rep.get("ranking") or []
    per: dict[str, int] = {}
    for r in ranking:
        fl = str(r.get("floor") or "").upper()
        if not fl or fl in BLOCKED or fl == "LIVE":
            continue
        n = int(r.get("peak_n") or r.get("peak_day_db_n_attributed") or 0)
        if peak_n_by_floor and fl in peak_n_by_floor:
            n = int(peak_n_by_floor[fl])
        if n > 0:
            per[fl] = n
    total = sum(per.values())
    return {
        "floors_with_peak_n": len(per),
        "peak_sum_signals": total,
        "top10": sorted(per.items(), key=lambda x: -x[1])[:10],
        "interpretation": (
            "SHOULD ≈ sum of independent peak-day free-fires. "
            "IS under v1 ≈ single LIVE stream (merge ≤1). "
            f"VOLUME_MODE={volume_mode()}."
        ),
    }


def enqueue_proposal(proposal: dict[str, Any]) -> None:
    """Append one floor proposal for later merge/outbox (v2 hook)."""
    proposal = dict(proposal)
    proposal.setdefault("ts", time.time())
    proposal.setdefault("volume_mode", volume_mode())
    _QUEUE.parent.mkdir(parents=True, exist_ok=True)
    with _QUEUE.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(proposal, ensure_ascii=False) + "\n")


def referee(
    proposals: list[dict[str, Any]],
    *,
    mode: str | None = None,
) -> list[dict[str, Any]]:
    """
    Collapse proposals according to VOLUME_MODE.

    EXPLOSION: keep all; drop only opposite-color losers in same window_id.
    SAFE_MERGE: keep best one per window_id (strength/score).
    """
    mode = (mode or volume_mode()).upper()
    if not proposals:
        return []
    by_win: dict[str, list[dict[str, Any]]] = {}
    for p in proposals:
        wid = str(p.get("window_id") or p.get("round_id") or p.get("ts") or "na")
        by_win.setdefault(wid, []).append(p)

    kept: list[dict[str, Any]] = []
    for wid, group in by_win.items():
        if mode == "EXPLOSION":
            # Opposite-color lock only
            colors = {(str(p.get("color") or "").lower()) for p in group}
            colors.discard("")
            colors.discard("tie")
            if len(colors) <= 1:
                kept.extend(group)
                continue
            # keep highest score among conflicting colors
            best = max(group, key=lambda p: float(p.get("score") or 0.0))
            kept.append({**best, "referee": "OPP_COLOR_LOCK", "window_id": wid})
        else:
            best = max(group, key=lambda p: float(p.get("score") or 0.0))
            kept.append({**best, "referee": "SAFE_MERGE_ONE", "window_id": wid})
    return kept


def build_report() -> dict[str, Any]:
    floors = list_peak_floors()
    gaps = fidelity_gaps()
    peak_sum = expected_peak_sum()
    report = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "volume_mode": volume_mode(),
        "v2_proposers_enabled": proposers_enabled(),
        "architecture": {
            "v1": "LIVE proposes → N floors score → merge ≤1",
            "v2": "N floors propose → referee by VOLUME_MODE → outbox",
            "user_worry": (
                "36 peak floors installed but volume not exploding — "
                "correct: they are scorers, not free proposers yet"
            ),
        },
        "proposer_floors": len(floors),
        "floors": floors,
        "fidelity_gaps": gaps,
        "should_volume": peak_sum,
        "next": [
            "Wire engine room events into per-floor peak-gate evaluate()",
            "enqueue_proposal({floor, color, kind, score, window_id, lane})",
            "Set VOLUME_MODE=EXPLOSION for peak-sum free-fire",
            "Outbox drain referee(kept) with dual-lane + result glue",
            "KPI: each floor live_n/day ≥ peak_n/day",
        ],
    }
    _REPORT.parent.mkdir(parents=True, exist_ok=True)
    _REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    r = build_report()
    print(json.dumps({
        "volume_mode": r["volume_mode"],
        "proposer_floors": r["proposer_floors"],
        "gap_or_silent": r["fidelity_gaps"]["gap_or_silent"],
        "peak_sum_signals": r["should_volume"]["peak_sum_signals"],
        "top10": r["should_volume"]["top10"],
        "next0": r["next"][0],
    }, indent=2))
