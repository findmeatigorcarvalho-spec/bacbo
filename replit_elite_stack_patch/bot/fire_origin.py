#!/usr/bin/env python3
"""
fire_origin.py — COALITION vs SOLO_FACT (epistemic origin of a FIRE).

Coalition: multi-room same-color decision → "ENTER NOW / rooms confirmed".
Solo fact: one strong peak/elite floor alone → independent warning, not dressed as consensus.

This is orthogonal to lane (MONEY vs TIMED / Clock A).
"""
from __future__ import annotations

import os
import re
from typing import Any


ORIGIN_COALITION = "COALITION"
ORIGIN_SOLO_FACT = "SOLO_FACT"
ORIGIN_UNKNOWN = "UNKNOWN"

_ELITE_KINDS = {
    "SOLO_ELITE",
    "GOLDEN",
    "PLATINUM",
    "SEQUENCE",
    "ELITE",
}

_COALITION_BODY = re.compile(
    r"(?is)("
    r"Rooms?\s+in\s+consensus|"
    r"CONFIRMED\s+ENTRY|"
    r"ENTER\s+NOW\s*—\s*\d+\s*ROOM|"
    r"\d+\s*ROOM\(S\)\s*CONFIRMED|"
    r"coalition"
    r")"
)


def _room_count(rooms_agreed: Any) -> int:
    if rooms_agreed is None:
        return 0
    if isinstance(rooms_agreed, (list, tuple, set)):
        return len([x for x in rooms_agreed if str(x).strip()])
    s = str(rooms_agreed).strip()
    if not s:
        return 0
    if s.isdigit():
        return int(s)
    # "a,b,c" or "@x · @y"
    parts = re.split(r"[,|;]+|\s+e\s+|\s+\+\s+", s)
    parts = [p.strip() for p in parts if p.strip() and p.strip().lower() != "engine"]
    return len(parts)


def _elite_floor(floor: str | None) -> bool:
    f = (floor or "").strip().upper()
    if not f or f == "LIVE":
        return False
    # Peak-day style tags / named elites
    if f.startswith(("JUN", "MAY", "APR", "MAR", "JUL", "AUG", "AITEST")):
        return True
    elite = os.environ.get("SOLO_ELITE_FLOORS", "")
    if elite:
        allow = {x.strip().upper() for x in elite.split(",") if x.strip()}
        if f in allow:
            return True
    return True  # any non-LIVE stamped floor can solo-fact; weak filter is room count


def classify_origin(
    *,
    rooms_agreed: Any = None,
    signal_kind: str | None = None,
    source_floor: str | None = None,
    text: str | None = None,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    meta = meta or {}
    n = _room_count(rooms_agreed if rooms_agreed is not None else meta.get("rooms_agreed"))
    kind = (signal_kind or meta.get("signal_kind") or "").strip().upper()
    body = str(text or meta.get("text") or "")
    floor = (source_floor or meta.get("source_floor") or "").strip().upper()

    if n >= 2 or (body and _COALITION_BODY.search(body)):
        return {
            "origin": ORIGIN_COALITION,
            "rooms": n,
            "badge": f"COALITION×{max(n, 2) if n else '?'}",
            "card_mode": "COALITION_ENTER",
            "note": "Multi-room decision — fire as consensus ENTER NOW",
        }

    if n <= 1 and (kind in _ELITE_KINDS or _elite_floor(floor)):
        return {
            "origin": ORIGIN_SOLO_FACT,
            "rooms": n,
            "badge": f"SOLO·{floor or kind or 'ELITE'}",
            "card_mode": "SOLO_FACT_WARNING",
            "note": "Single strong floor — independent fact warning, not fake consensus",
        }

    return {
        "origin": ORIGIN_UNKNOWN,
        "rooms": n,
        "badge": "UNKNOWN",
        "card_mode": "HOLD_OR_SHADOW",
        "note": "Weak/unclear origin — prefer hold over dressing as coalition",
    }


def truth_from_outcome(predicted: str, outcome: str) -> dict[str, str]:
    """If bet blue and lost G0 → actual/table color was red (and reverse)."""
    predicted = (predicted or "").lower().strip()
    outcome = (outcome or "").lower().strip()
    if outcome == "tie":
        return {
            "predicted": predicted,
            "actual": "tie",
            "truth_round": "tie",
            "line": f"BET {predicted.upper()} → OUT TIE · TRUTH THIS ROUND = TIE",
        }
    if outcome == "win":
        return {
            "predicted": predicted,
            "actual": predicted,
            "truth_round": predicted,
            "line": (
                f"BET {predicted.upper()} → OUT {predicted.upper()} · "
                f"WIN · TRUTH THIS ROUND = {predicted.upper()}"
            ),
        }
    if outcome == "loss":
        actual = "red" if predicted == "blue" else "blue" if predicted == "red" else "unknown"
        return {
            "predicted": predicted,
            "actual": actual,
            "truth_round": actual,
            "line": (
                f"BET {predicted.upper()} → OUT {actual.upper()} · "
                f"{predicted.upper()} LOST · TRUTH THIS ROUND = {actual.upper()}"
            ),
        }
    return {
        "predicted": predicted,
        "actual": "unknown",
        "truth_round": "unknown",
        "line": f"BET {predicted.upper()} → outcome={outcome}",
    }


if __name__ == "__main__":
    print(classify_origin(rooms_agreed="@A,@B,@C", signal_kind="GOLDEN"))
    print(classify_origin(rooms_agreed="CoringaDados", signal_kind="SOLO_ELITE", source_floor="MAY01"))
    print(truth_from_outcome("blue", "loss"))
    print(truth_from_outcome("red", "win"))
