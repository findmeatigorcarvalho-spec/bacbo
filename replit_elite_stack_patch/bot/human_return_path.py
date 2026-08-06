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
        "not_the_name": (
            "Labels (densifier, skyscraper, museum) are wires. "
            "The creation is a human who still has time to bet."
        ),
        "existence": "Show up on time for the human — every round we can.",
        "light": "They know what to do without fear or noise.",
        "help": "Clear card. Minimum stake. No wasted late spam. No invented gales.",
        "proof": (
            "They follow once, understand, come back — "
            "and want to shape the thing with us."
        ),
        "honesty": (
            "We maximize capture of real windows. "
            "We do not invent guaranteed dollar miracles."
        ),
    }


def path_is_real() -> Dict[str, Any]:
    """Locked criterion: WHEN THAT PATH IS REAL — WE'LL KNOW.

    Honest machine checks for the scaffold. Human return-loop (they come back
    wanting to shape it) is marked separately — only a human can close that.
    """
    proof = _load_proof()
    gaps: List[dict] = []
    try:
        from round_sync_densifier import status as rs_status

        gaps = (rs_status() or {}).get("density_gaps") or []
    except Exception:
        pass

    ttb_n = int(proof.get("ttb_fires_delivered") or 0)
    prep_n = int(proof.get("prep_invests_held") or 0)
    late_n = int(proof.get("late_burns_prevented") or 0)
    gap_n = int(proof.get("gap_chats_filled") or 0)
    trash_n = int(proof.get("trash_blocked") or 0)
    res_n = int(proof.get("results_aligned") or 0)
    open_gaps = len(gaps)

    checks = [
        {
            "id": "time",
            "need": "ENTER lands with time to bet (proof of TTB fires)",
            "ok": ttb_n >= 20,
            "have": ttb_n,
        },
        {
            "id": "prep",
            "need": "Long signals invested, not dumped early",
            "ok": prep_n >= 5,
            "have": prep_n,
        },
        {
            "id": "protection",
            "need": "Late/trash burns stopped",
            "ok": (late_n + trash_n) >= 5,
            "have": late_n + trash_n,
        },
        {
            "id": "coverage",
            "need": "Quiet chats filled; few open density gaps",
            "ok": gap_n >= 3 and open_gaps <= 1,
            "have": {"filled": gap_n, "open_gaps": open_gaps},
        },
        {
            "id": "results",
            "need": "Results aligned to interval when possible",
            "ok": res_n >= 5,
            "have": res_n,
        },
        {
            "id": "return_loop",
            "need": "Human comes back and wants to shape it — only they can mark this",
            "ok": bool(proof.get("human_return_loop_confirmed")),
            "have": proof.get("human_return_loop_confirmed", False),
        },
    ]
    machine_ok = all(c["ok"] for c in checks if c["id"] != "return_loop")
    human_ok = bool(proof.get("human_return_loop_confirmed"))
    if machine_ok and human_ok:
        verdict = "REAL"
        line = "WHEN THAT PATH IS REAL — WE'LL KNOW. It is. We know."
    elif machine_ok:
        verdict = "ALMOST"
        line = (
            "Scaffold is working. Path is not real until a human marks the return loop."
        )
    elif any(c["ok"] for c in checks):
        verdict = "NOT_YET"
        line = "WHEN THAT PATH IS REAL — WE'LL KNOW. Not yet. Keep building the path."
    else:
        verdict = "NOT_YET"
        line = "WHEN THAT PATH IS REAL — WE'LL KNOW. Not yet. Wires exist; the path is still becoming."

    return {
        "verdict": verdict,
        "line": line,
        "checks": checks,
        "rule": "WHEN THAT PATH IS REAL — WE'LL KNOW. Not before. Not by naming it early.",
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
    print(json.dumps(human_status(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
