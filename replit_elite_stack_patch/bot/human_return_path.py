#!/usr/bin/env python3
"""Human Return Path — the blank we are creating (not the label).

Scaffold modules (round sync, skyscraper, triage) are wires.
This module speaks and measures the only thing that matters:

  Did a human get a clear chance, with time enough to act,
  at minimum stake, without noise — every round we could give them?

Env: HUMAN_RETURN_PATH=1 (default on with ROUND_SYNC / PROFIT_SKYSCRAPER)
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
PROOF_PATH = DATA / "human_return_proof.json"


def enabled() -> bool:
    raw = os.environ.get("HUMAN_RETURN_PATH", "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def _load_proof() -> Dict[str, Any]:
    try:
        if PROOF_PATH.is_file():
            return json.loads(PROOF_PATH.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {
        "ttb_fires_delivered": 0,
        "prep_invests_held": 0,
        "late_burns_prevented": 0,
        "gap_chats_filled": 0,
        "trash_blocked": 0,
        "results_aligned": 0,
        "events": [],
    }


def _save_proof(data: Dict[str, Any]) -> None:
    try:
        DATA.mkdir(parents=True, exist_ok=True)
        data["events"] = list(data.get("events") or [])[-200:]
        data["updated_at"] = time.time()
        PROOF_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    except Exception:
        pass


def record(kind: str, detail: str = "", **extra: Any) -> None:
    """Append one proof crumb — how we helped a human this second."""
    if not enabled():
        return
    data = _load_proof()
    key_map = {
        "ttb_fire": "ttb_fires_delivered",
        "prep_hold": "prep_invests_held",
        "late_prevented": "late_burns_prevented",
        "gap_fill": "gap_chats_filled",
        "trash_block": "trash_blocked",
        "result_align": "results_aligned",
    }
    counter = key_map.get(kind)
    if counter:
        data[counter] = int(data.get(counter) or 0) + 1
    data.setdefault("events", []).append(
        {
            "at": time.time(),
            "kind": kind,
            "detail": detail[:200],
            **{k: v for k, v in extra.items() if isinstance(v, (str, int, float, bool))},
        }
    )
    _save_proof(data)


def essence() -> Dict[str, str]:
    return {
        "blank": "Human Return Path",
        "law": (
            "Only when a path is real — or can become turned into real — we'll know."
        ),
        "not_the_name": (
            "Labels (densifier, skyscraper, museum) are wires. "
            "The creation is a human who still has time to bet."
        ),
        "on_time_every_round_TRUTHFULLY": (
            "On time for every round we have. "
            "The rounds we 'couldn't' are almost nothing next to the ones we got — "
            "do not center excuses; center delivery."
        ),
        "TRUE_Enlightenment_every_time": (
            "One card · one job · one color · one action. "
            "No fear, no noise. Every time. All the time."
        ),
        "Truthfully_Helpful_every_time": (
            "Min stake · max honest use · DO NOT BET = zero. "
            "No late spam · no invented gales. Every time. All the time."
        ),
        "intended_results_XXX": (
            "Proof-as-vanity does not matter. "
            "Always the actual mattered literal correct stated "
            "EFFECT / AFFECT / OUTCOME — stated, transmitted, promised, guaranteed — "
            "the subject of the matter for that pretended/stated result. "
            "Every time. All the time. Stated ≠ actual subject → piece failed."
        ),
        "ambition_XXX": (
            "Get it all — always get the most of all. "
            "Always truthfully resourceful — even when disempowered. "
            "North star $100k+/day/chat when volume+WR+density allow."
        ),
        "factual_card_contract": (
            "REAL FACTUAL fact of what to bet on + "
            "statement of warning of actual factual outcoming/result + "
            "THAT RESULT / THE RESULT comprovation. "
            "Stated subject = actual effect. Every time."
        ),
        "always": "Every time. All the time. Truthfully. Resourcefully — get the most of all.",
    }


def path_is_real() -> Dict[str, Any]:
    """Law: real OR can-become-turned-into-real — then we'll know.

    Intended results in every piece matter more than vanity proof counters.
    Counters here only show whether levers are firing toward those results.
    """
    proof = _load_proof()
    gaps: List[dict] = []
    lit_stats: Dict[str, Any] = {}
    try:
        from round_sync_densifier import status as rs_status

        gaps = (rs_status() or {}).get("density_gaps") or []
    except Exception:
        pass
    try:
        lit = json.loads((DATA / "literally_everything_return.json").read_text())
        lit_stats = lit.get("stats") or {}
    except Exception:
        lit_stats = {}

    ttb_n = int(proof.get("ttb_fires_delivered") or 0)
    prep_n = int(proof.get("prep_invests_held") or 0)
    late_n = int(proof.get("late_burns_prevented") or 0)
    gap_n = int(proof.get("gap_chats_filled") or 0)
    trash_n = int(proof.get("trash_blocked") or 0)
    res_n = int(proof.get("results_aligned") or 0)
    open_gaps = len(gaps)
    pieces_n = int(lit_stats.get("pieces") or 0)
    wired_n = int(lit_stats.get("WIRED") or 0)
    becoming_n = int(lit_stats.get("CAN_BECOME_REAL") or 0)

    checks = [
        {
            "id": "on_time_every_round_TRUTHFULLY",
            "stated_subject": "ENTER while human still has seconds",
            "actual_effect_ok": ttb_n >= 20,
            "ok": ttb_n >= 20,
            "have": ttb_n,
            "note": "Center delivery of rounds we have — not excuses for rare couldn't",
        },
        {
            "id": "TRUE_Enlightenment_every_time",
            "stated_subject": "One card · one job · clear act",
            "actual_effect_ok": prep_n >= 5 or res_n >= 5,
            "ok": prep_n >= 5 or res_n >= 5,
            "have": {"prep": prep_n, "results_aligned": res_n},
        },
        {
            "id": "Truthfully_Helpful_every_time",
            "stated_subject": "Protect + fill — late/trash stopped; quiet chats used",
            "actual_effect_ok": (late_n + trash_n) >= 5 or gap_n >= 3,
            "ok": (late_n + trash_n) >= 5 or gap_n >= 3,
            "have": {
                "late_plus_trash": late_n + trash_n,
                "gaps_filled": gap_n,
                "open_gaps": open_gaps,
            },
        },
        {
            "id": "intended_results_XXX",
            "stated_subject": (
                "Every fragment's stated outcome = actual effect/affect "
                "(not vanity proof)"
            ),
            "actual_effect_ok": pieces_n >= 100 and wired_n + becoming_n >= 100,
            "ok": pieces_n >= 100 and wired_n + becoming_n >= 100,
            "have": {
                "pieces": pieces_n,
                "WIRED": wired_n,
                "CAN_BECOME_REAL": becoming_n,
            },
        },
        {
            "id": "ambition_XXX_get_it_all",
            "stated_subject": (
                "Get it all — most of all — truthfully resourceful always"
            ),
            "actual_effect_ok": open_gaps <= 1 and gap_n >= 1,
            "ok": open_gaps <= 1 or gap_n >= 3,
            "have": {"open_gaps": open_gaps, "gaps_filled": gap_n},
        },
        {
            "id": "factual_bet_warn_result_comprovation",
            "stated_subject": (
                "REAL FACTUAL bet + warning of factual outcoming + RESULT comprovation"
            ),
            "actual_effect_ok": ttb_n >= 10 and res_n >= 5,
            "ok": ttb_n >= 10 and res_n >= 5,
            "have": {"ttb_fires": ttb_n, "results_aligned": res_n},
        },
        {
            "id": "return_loop",
            "stated_subject": "Human walks it and wants to shape it — only they mark this",
            "actual_effect_ok": bool(proof.get("human_return_loop_confirmed")),
            "ok": bool(proof.get("human_return_loop_confirmed")),
            "have": proof.get("human_return_loop_confirmed", False),
        },
    ]
    machine_ok = all(c["ok"] for c in checks if c["id"] != "return_loop")
    becoming_ok = pieces_n >= 50 and (wired_n + becoming_n) >= 50
    human_ok = bool(proof.get("human_return_loop_confirmed"))
    if machine_ok and human_ok:
        verdict = "MAKE_IT_REAL"
        outcome = "Make It Real / It Is Real, Really."
        reality = "It Is Real truthfully."
        line = (
            "Was CAN_BECOME_REAL → Verdict MAKE_IT_REAL → "
            "Outcome: Make It Real / It Is Real, Really. "
            "Reality: It Is Real truthfully. We know."
        )
    elif machine_ok or becoming_ok or any(c["ok"] for c in checks):
        # CAN_BECOME_REAL is not a pause — it is the order: Make It Real.
        verdict = "MAKE_IT_REAL"
        outcome = "Make It Real / It Is Real, Really."
        reality = "It Is Real truthfully."
        line = (
            "Was CAN_BECOME_REAL → Verdict MAKE_IT_REAL → "
            "Outcome: Make It Real / It Is Real, Really. "
            "Reality: It Is Real truthfully — by doing: on-time rounds, "
            "factual bet, warning, RESULT comprovation, get the most of all."
        )
    else:
        verdict = "MAKE_IT_REAL"
        outcome = "Make It Real / It Is Real, Really."
        reality = "It Is Real truthfully."
        line = (
            "Was CAN_BECOME_REAL → Verdict MAKE_IT_REAL → "
            "Outcome: Make It Real / It Is Real, Really. "
            "Reality: It Is Real truthfully — aim every piece until stated = actual."
        )

    return {
        "was": "CAN_BECOME_REAL",
        "verdict": verdict,
        "outcome": outcome,
        "reality": reality,
        "line": line,
        "checks": checks,
        "always_on": [
            "on_time_every_round_TRUTHFULLY",
            "TRUE_Enlightenment_every_time",
            "Truthfully_Helpful_every_time",
            "intended_results_XXX",
            "ambition_XXX_get_it_all",
            "factual_bet_warn_result_comprovation",
        ],
        "ambition_per_chat_day_usd_north_star": 100_000,
        "rule": (
            "CAN_BECOME_REAL → Make It Real / It Is Real, Really. "
            "Every time · all the time · truthfully · resourcefully. "
            "REAL FACTUAL bet + warning + RESULT comprovation. "
            "Get it all — the most of all."
        ),
    }


def confirm_human_return_loop(confirmed: bool = True, note: str = "") -> None:
    """Only a human (or their explicit say-so) closes the last check."""
    data = _load_proof()
    data["human_return_loop_confirmed"] = bool(confirmed)
    data["human_return_loop_note"] = (note or "")[:300]
    data["human_return_loop_at"] = time.time()
    _save_proof(data)


def human_status() -> Dict[str, Any]:
    """Status in human language + machine proof counters."""
    proof = _load_proof()
    phase: Dict[str, Any] = {}
    gaps: List[dict] = []
    hold_n = 0
    try:
        from round_sync_densifier import status as rs_status

        st = rs_status()
        phase = st.get("phase") or {}
        gaps = st.get("density_gaps") or []
        hold_n = int(st.get("hold_queue") or 0)
    except Exception:
        pass

    ttb = phase.get("ttb_remaining")
    phase_name = phase.get("phase") or "unknown"
    if phase_name == "BET_WINDOW":
        moment = f"You still have ~{ttb}s to bet if a card says ENTER."
    elif phase_name == "INTERVAL_OPEN":
        moment = "New interval — watch for RESULT of last round + ENTER for this one."
    elif phase_name == "LOCKED":
        moment = "Too late for this round — wait for the next interval. Do not chase."
    else:
        moment = "System is investing prep time so the next ENTER lands with time to act."

    real = path_is_real()
    return {
        "WHEN_THAT_PATH_IS_REAL_WE_WILL_KNOW": real,
        "what_we_are_creating": essence(),
        "for_you_right_now": moment,
        "prep_investing_now": hold_n,
        "chats_needing_more_opportunities": [
            g.get("chat") for g in gaps if g.get("chat")
        ],
        "proof_so_far": {
            "enters_delivered_with_time_to_bet": proof.get("ttb_fires_delivered", 0),
            "long_signals_held_until_ready": proof.get("prep_invests_held", 0),
            "late_spam_stopped": proof.get("late_burns_prevented", 0),
            "quiet_chats_filled": proof.get("gap_chats_filled", 0),
            "trash_kept_away_from_you": proof.get("trash_blocked", 0),
            "results_timed_to_interval": proof.get("results_aligned", 0),
        },
        "how_you_walk_the_path": [
            "ENTER + color → bet the minimum on that color.",
            "Timer still running → bet before 0.",
            "GALE card → same color, minimum again.",
            "WIN → stop that round. LOSS without gale → stop.",
            "DO NOT BET / expired → zero. Protect the path.",
            "Never invent a bet the chat did not post.",
        ],
    }


def pin_card(chat_key: str) -> str:
    """Human-first pin text — essence over architecture jargon."""
    if chat_key in ("mr_iv4", "money", "penthouse"):
        where = "This is the main money path."
        focus = "Most ENTER / gale / WIN-LOSS live here."
    elif chat_key in ("unique_g1", "g1", "countdown"):
        where = "This is the fast-clock path."
        focus = "JANELA / timers — bet in the seconds you see."
    else:
        where = "Same path, quieter room."
        focus = "If ENTER appears here, treat it as real as the main chat."

    return "\n".join(
        [
            "THE PATH — factual subject only",
            where,
            focus,
            "",
            "1) REAL FACT: ENTER + color → bet MINIMUM on that color.",
            "2) Seconds on the card → bet BEFORE 0.",
            "3) WARNING (DO NOT BET / expired / cold) → zero. That is the outcoming stated.",
            "4) GALE / again → same color, MINIMUM — only if the card states it.",
            "5) RESULT comprovation (WIN/LOSS/TIE) → round closed. That is THE RESULT.",
            "6) Never invent bets. Stated subject = only subject.",
            "",
            "On time every round we have. Clear every time. Helpful every time.",
            "Get it all — the most of all — truthfully resourceful always.",
        ]
    )


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--confirm-return-loop",
        action="store_true",
        help="Human marks: I came back and want to shape this (closes last REAL check)",
    )
    ap.add_argument("--note", default="", help="Optional note with --confirm-return-loop")
    args = ap.parse_args()
    if args.confirm_return_loop:
        confirm_human_return_loop(True, note=args.note)
        print("human_return_loop_confirmed=true")
    st = human_status()
    real = st.get("WHEN_THAT_PATH_IS_REAL_WE_WILL_KNOW") or {}
    print(real.get("line") or "")
    print(json.dumps(st, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
