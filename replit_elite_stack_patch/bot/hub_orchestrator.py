"""HUB AI — free proposers in → orchestrated best card+RESULT out.

EMANATION model (locked) — see bot/config/emanation_laws.py:
  · Absorb 100% of every floor/camada/system proposal (FREE_PROPOSE).
  · Same-color = coalition strength. Opposite-color = LOCK + learn.
  · Color truth = FACTUAL win when known; committee is provisional only.
  · Emit complete vertical bundles per chat (FIRE→RESULT→gale).
  · Chats are hermetic — each stream unaware of siblings.

Env:
  HUB_ORCHESTRATOR=1     (default on when HUB_MAX=1)
  VOLUME_MODE=EXPLOSION  free same-color multi; opp-color lock
  FREE_PROPOSE=1         propose path ignores mute gates
  COLOR_TRUTH_FACTUAL=1  factual RESULT color overrides committee
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
    factual_color: Optional[str] = None,
) -> dict[str, Any]:
    """Pick primary card + spill list from free proposals for one window/round.

    Color truth:
      · If factual_color (actual winning color) is known → that color WINS.
        Opp proposers stay LOCKED for learner watchdog (not deleted from memory).
      · Else provisional coalition aggregate (sum scores) — until RESULT speaks.

    Returns:
      {
        primary: proposal | None,   # best card for APEX / primary_peer
        spill: [proposal, ...],     # same-color extras for g2…gN (hermetic clones)
        dropped_opp: [...],         # opposite-color LOCK (learn/watchdog)
        color: str,
        color_truth: FACTUAL|PROVISIONAL,
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
            "color_truth": "NONE",
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
            "color_truth": "UNTYPED",
            "n_in": len(norm),
            "why": "untyped_best_score",
        }

    # Winning color = factual truth when known; else provisional coalition.
    def _agg(items: list[dict[str, Any]]) -> float:
        return sum(p["score"] for p in items) + 0.01 * len(items)

    # Only explicit factual_color (same-window truth). Do NOT auto-pull the
    # previous round's RESULT — that would poison the next window's pick.
    fact = str(factual_color or "").strip().lower()
    if fact in {"b", "azul", "🔵"}:
        fact = "blue"
    elif fact in {"r", "vermelho", "🔴"}:
        fact = "red"

    color_truth = "PROVISIONAL"
    if fact and fact in by_color:
        # LAW: fire the color that is actually winning / won.
        win_color = fact
        color_truth = "FACTUAL"
    elif fact and fact in {"blue", "red"} and fact not in by_color:
        # Reality spoke a color no proposer held — keep best provisional,
        # but tag so learner sees the miss.
        win_color = max(by_color.keys(), key=lambda c: _agg(by_color[c]))
        color_truth = "FACTUAL_MISS"
    else:
        win_color = max(by_color.keys(), key=lambda c: _agg(by_color[c]))
        color_truth = "PROVISIONAL"

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
        "color_truth": color_truth,
        "factual_color": fact or "",
        "n_in": len(norm),
        "why": (
            f"HUB {color_truth} pick {win_color} from {len(winners)} same-color "
            f"proposers (locked {len(dropped)} opp); primary={primary.get('floor')} "
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
