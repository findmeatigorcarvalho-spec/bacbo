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
        "BEST_Existence": "Show up on time for the human — every round we can.",
        "BEST_Enlightenment_by_clarity": "One card, one job — no fear, no noise.",
        "THE_MOST_Helpful": (
            "Clear card. Minimum stake. Max honest use of every opportunity. "
            "No late spam. No invented gales."
        ),
        "intended_results": (
            "Proof-as-vanity does not matter. "
            "Intended results in every part/piece of the whole do."
        ),
        "ambition": (
            "Get as much as we can from literally everything — "
            "north star $100k+/day/chat when volume+WR+density allow; "
            "never less than each fragment can honestly contribute."
        ),
        "honesty": (
            "North star is direction, not a fake certificate. "
            "We maximize capture of real windows."
        ),
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
            "id": "BEST_Existence",
            "intended_result": "ENTER lands with time to bet",
            "ok": ttb_n >= 20,
            "have": ttb_n,
        },
        {
            "id": "BEST_Enlightenment_by_clarity",
            "intended_result": "Long signals invested; results aligned; path pin clear",
            "ok": prep_n >= 5 or res_n >= 5,
            "have": {"prep": prep_n, "results_aligned": res_n},
        },
        {
            "id": "THE_MOST_Helpful",
            "intended_result": "Late/trash burns stopped; quiet chats filled",
            "ok": (late_n + trash_n) >= 5 or gap_n >= 3,
            "have": {
                "late_plus_trash": late_n + trash_n,
                "gaps_filled": gap_n,
                "open_gaps": open_gaps,
            },
        },
        {
            "id": "literally_everything",
            "intended_result": "Every fragment has an intended result aimed at max return",
            "ok": pieces_n >= 100 and wired_n + becoming_n >= 100,
            "have": {
                "pieces": pieces_n,
                "WIRED": wired_n,
                "CAN_BECOME_REAL": becoming_n,
            },
        },
        {
            "id": "return_loop",
            "intended_result": "Human walks it and wants to shape it — only they mark this",
            "ok": bool(proof.get("human_return_loop_confirmed")),
            "have": proof.get("human_return_loop_confirmed", False),
        },
    ]
    machine_ok = all(c["ok"] for c in checks if c["id"] != "return_loop")
    becoming_ok = pieces_n >= 50 and (wired_n + becoming_n) >= 50
    human_ok = bool(proof.get("human_return_loop_confirmed"))
    if machine_ok and human_ok:
        verdict = "REAL"
        line = (
            "Only when a path is real — or can become turned into real — we'll know. "
            "It is real. We know."
        )
    elif machine_ok:
        verdict = "CAN_BECOME_REAL"
        line = (
            "Path can become real — intended results are firing. "
            "Human return loop still open."
        )
    elif becoming_ok or any(c["ok"] for c in checks):
        verdict = "CAN_BECOME_REAL"
        line = (
            "Only when a path is real — or can become turned into real — we'll know. "
            "It can become real. Turning is underway."
        )
    else:
        verdict = "NOT_YET"
        line = (
            "Only when a path is real — or can become turned into real — we'll know. "
            "Not yet. Aim every piece at intended results."
        )

    return {
        "verdict": verdict,
        "line": line,
        "checks": checks,
        "north_stars": [
            "BEST_Existence",
            "BEST_Enlightenment_by_clarity",
            "THE_MOST_Helpful",
        ],
        "ambition_per_chat_day_usd_north_star": 100_000,
        "rule": (
            "Only when a path is real — or can become turned into real — we'll know. "
            "Intended results in every piece > vanity proof."
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
            "THE PATH (not a brand — what you do)",
            where,
            focus,
            "",
            "1) ENTER + color → bet MINIMUM on that color.",
            "2) Seconds on the card → bet BEFORE 0.",
            "3) GALE / again → same color, MINIMUM.",
            "4) WIN → round over. LOSS + no gale → round over.",
            "5) DO NOT BET / expired → skip. That is protection.",
            "6) Never invent bets. The card is the only teacher.",
            "",
            "We hold long signals until you still have time.",
            "We skip late noise. We fill quiet chats when we can.",
            "Your job: follow. Minimum stake. Every real chance.",
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
