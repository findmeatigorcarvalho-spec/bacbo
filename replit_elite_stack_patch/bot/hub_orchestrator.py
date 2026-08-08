"""HUB AI — free proposers in → orchestrated best card+RESULT out.

User model (locked):
  Every signal gate / config / setup / camada / floor / system proposes
  freely 24/7 into the HUB (no hour / volume / WR mute on the propose path).

  Many proposers can agree the same color for the same round (e.g. 20 say RED).
  Next round maybe 10 say BLUE. The HUB scores strength, then chooses:
    · which ONE primary card+RESULT fits that round + APEX chat
    · how / when / where to place secondary same-color cards (spill chats)
    · opposite-color same-window → lock (cannot bet both ways)

  Floors are only one class of proposer. Skins, gates, factory camadas,
  and other systems also feed the hub as they get wired.

FIRE ↔ RESULT: every chosen FIRE gets a RESULT skin under it immediately.

Env:
  HUB_ORCHESTRATOR=1     (default on when HUB_MAX=1)
  VOLUME_MODE=EXPLOSION  free same-color multi; opp-color lock
  FREE_PROPOSE=1         propose path ignores mute gates
"""
from __future__ import annotations

import os
import time
from typing import Any, Optional


def enabled() -> bool:
    if os.environ.get("HUB_ORCHESTRATOR", "").strip().lower() in {
        "0",
        "false",
        "no",
        "off",
    }:
        return False
    if os.environ.get("HUB_MAX", "0").strip() in {"1", "true", "yes", "on"}:
        return True
    return os.environ.get("HUB_ORCHESTRATOR", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def free_propose() -> bool:
    return os.environ.get("FREE_PROPOSE", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def orchestrate(
    proposals: list[dict[str, Any]],
    *,
    primary_peer: str = "UNIQUE_g1",
) -> dict[str, Any]:
    """Pick primary card + spill list from free proposals for one window/round.

    Returns:
      {
        primary: proposal | None,   # best card for APEX / primary_peer
        spill: [proposal, ...],     # same-color extras for g2…gN
        dropped_opp: [...],         # opposite-color losers
        color: str,
        n_in: int,
        why: str,
      }
    """
    if not proposals:
        return {
            "primary": None,
            "spill": [],
            "dropped_opp": [],
            "color": "",
            "n_in": 0,
            "why": "no_proposals",
        }

    # Normalize + impact-learner enrich (watchdog WR/volume scores)
    try:
        from hub_impact_learner import enrich_proposal_score, enabled as _learn_on

        learn = _learn_on()
    except Exception:
        learn = False
        enrich_proposal_score = None  # type: ignore

    norm: list[dict[str, Any]] = []
    for p in proposals:
        q = dict(p)
        q["color"] = str(q.get("color") or "").strip().lower()
        base = float(q.get("score") or q.get("strength") or 0.0)
        q["floor"] = str(q.get("floor") or q.get("winner_floor") or "?").upper()
        if learn and enrich_proposal_score is not None:
            try:
                q["score"] = float(enrich_proposal_score(q))
                q["score_base"] = base
            except Exception:
                q["score"] = base
        else:
            q["score"] = base
        norm.append(q)

    by_color: dict[str, list[dict[str, Any]]] = {}
    for p in norm:
        c = p["color"] or "unknown"
        if c in {"", "tie", "empate"}:
            continue
        by_color.setdefault(c, []).append(p)

    if not by_color:
        # untyped — take highest score as primary
        best = max(norm, key=lambda p: p["score"])
        return {
            "primary": {**best, "hub_peer": primary_peer, "hub_role": "PRIMARY"},
            "spill": [],
            "dropped_opp": [],
            "color": best.get("color") or "",
            "n_in": len(norm),
            "why": "untyped_best_score",
        }

    # Winning color = highest aggregate strength (sum of scores)
    def _agg(items: list[dict[str, Any]]) -> float:
        return sum(p["score"] for p in items) + 0.01 * len(items)

    win_color = max(by_color.keys(), key=lambda c: _agg(by_color[c]))
    winners = sorted(by_color[win_color], key=lambda p: p["score"], reverse=True)
    dropped = []
    for c, items in by_color.items():
        if c != win_color:
            dropped.extend({**p, "hub_drop": "OPP_COLOR_LOCK"} for p in items)

    primary = {
        **winners[0],
        "hub_peer": primary_peer,
        "hub_role": "PRIMARY",
        "hub_color_votes": len(winners),
        "hub_agg_score": _agg(winners),
    }
    spill = []
    for i, p in enumerate(winners[1:], start=2):
        peer = f"UNIQUE_g{min(i, 9)}" if i <= 9 else "UNIQUE_g9"
        if peer == primary_peer:
            peer = "UNIQUE_g2"
        spill.append(
            {
                **p,
                "hub_peer": peer,
                "hub_role": "SPILL_SAME_COLOR",
                "hub_rank": i,
            }
        )

    # Full color map — watchdog learns which said what, what locked, what won
    color_map = {
        c: [
            {
                "floor": str(p.get("floor") or "").upper(),
                "score": float(p.get("score") or 0.0),
                "rooms": list(p.get("rooms") or []),
            }
            for p in items
        ]
        for c, items in by_color.items()
    }
    out = {
        "primary": primary,
        "spill": spill,
        "dropped_opp": dropped,
        "color": win_color,
        "n_in": len(norm),
        "why": (
            f"HUB pick {win_color} from {len(winners)} same-color proposers "
            f"(dropped {len(dropped)} opp); primary={primary.get('floor')} "
            f"score={primary.get('score')}"
        ),
        "ts": time.time(),
        "mode": "COALITION" if len(winners) >= 2 or dropped else "SINGULAR",
        "color_map": color_map,
        "opp_locked_colors": [c for c in by_color.keys() if c != win_color],
    }
    # Watchdog: every coalition / singular hub decision + opp locks
    try:
        from hub_impact_learner import observe_hub_decision

        observe_hub_decision(out)
    except Exception:
        pass
    return out


def pick_primary(
    proposals: list[dict[str, Any]],
    *,
    primary_peer: str = "UNIQUE_g1",
) -> Optional[dict[str, Any]]:
    return orchestrate(proposals, primary_peer=primary_peer).get("primary")
