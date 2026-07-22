#!/usr/bin/env python3
"""
dual_lane_router.py — split fires by TEMPLATE (not by result card skin).

MONEY lane (Mr_iv4):
  Signal-fire templates WITHOUT countdown-in-seconds / intervalo / janela / window timer.
  Floor coalition applies. Result card under fire is OK even if result text has countdown UX.

COUNTDOWN lane (Gunique):
  Signal-fire templates WITH countdown-in-seconds for the hit (timer / intervalo / janela).
  Own chat. CD result cards under those fires are OK / required for glue.

Env:
  TELEGRAM_TARGET_PEER          — money peer (default 6774605259 / Mr_iv4)
  TELEGRAM_COUNTDOWN_PEER       — Gunique (default UNIQUE_g1)
  LUXURY_DUAL_LANE=1            — enable routing (default on when set)
"""
from __future__ import annotations

import os
import re
from typing import Any


LANE_MONEY = "MONEY"
LANE_COUNTDOWN = "COUNTDOWN"
DEFAULT_MONEY_PEER = "6774605259"  # Mr_iv4
DEFAULT_COUNTDOWN_PEER = "UNIQUE_g1"  # Gunique (@UNIQUE_g1)

# Fire template has an explicit seconds/window countdown for the prediction to hit.
_CD_FIRE = re.compile(
    r"(?is)("
    r"\bcountdown\b|"
    r"\bintervalo\b|"
    r"\bjanela\b|"
    r"⏳|"
    r"apostar\s+agora|"
    r"em\s+\d{1,3}\s*(s|sec|secs|seg|segundos?|seconds?)\b|"
    r"(?<!sem\s)\b\d{1,3}\s*(s|sec|secs|seg|segundos?|seconds?)\b|"
    r"CD_FIRE_|"
    r"COUNTDOWN_SIGNAL"
    r")"
)
# Explicit "no timer" money fires must never route to countdown.
_NOT_CD = re.compile(r"(?is)\b(sem\s+timer|without\s+timer|no\s+countdown|sem\s+countdown)\b")

# Kinds / tags that are always countdown-lane fires when present on the signal row.
_CD_KINDS = {
    "COUNTDOWN",
    "COUNTDOWN_SIGNAL",
    "COUNTDOWN_SIGNAL_FIRE",
    "CD_FIRE",
    "CD_TIMER",
    "CD_FIRE_TIMER_BRT_EDT_APOSTAR",
    "CD_FIRE_QUANTUM_LOCK",
    "CD_FIRE_RUSH_NS_LEFT",
}


def is_countdown_fire(
    *,
    text: str | None = None,
    signal_kind: str | None = None,
    card_type: str | None = None,
    meta: dict[str, Any] | None = None,
) -> bool:
    """True when the SIGNAL FIRE itself carries countdown-seconds / window timing."""
    meta = meta or {}
    kind = (signal_kind or meta.get("signal_kind") or meta.get("kind") or "").strip().upper()
    ctype = (card_type or meta.get("card_type") or meta.get("template") or "").strip().upper()
    if kind in _CD_KINDS or ctype in _CD_KINDS:
        return True
    if ctype.startswith("CD_FIRE") or "COUNTDOWN_SIGNAL" in ctype:
        return True
    # Explicit meta flag from engine
    if str(meta.get("lane") or "").strip().upper() == LANE_COUNTDOWN:
        return True
    if meta.get("has_countdown_seconds") in (1, True, "1", "true", "yes"):
        return True
    body = text or meta.get("text") or meta.get("card_text") or ""
    if body and _NOT_CD.search(str(body)):
        return False
    if body and _CD_FIRE.search(str(body)):
        return True
    return False


def route_lane(
    *,
    text: str | None = None,
    signal_kind: str | None = None,
    card_type: str | None = None,
    meta: dict[str, Any] | None = None,
) -> str:
    return LANE_COUNTDOWN if is_countdown_fire(
        text=text, signal_kind=signal_kind, card_type=card_type, meta=meta
    ) else LANE_MONEY


def _norm_peer(raw: str | None) -> str | None:
    if not raw:
        return None
    s = str(raw).strip()
    if not s:
        return None
    if s.startswith("@"):
        s = s[1:]
    return s


def peer_for_lane(lane: str) -> str | None:
    """Return Telegram peer string for lane (money=Mr_iv4, countdown=Gunique)."""
    lane = (lane or LANE_MONEY).upper()
    if lane == LANE_COUNTDOWN:
        return _norm_peer(
            os.environ.get("TELEGRAM_COUNTDOWN_PEER")
            or os.environ.get("GUNIQUE_PEER")
            or os.environ.get("TELEGRAM_GUNIQUE_PEER")
            or DEFAULT_COUNTDOWN_PEER
        )
    return _norm_peer(
        os.environ.get("TELEGRAM_TARGET_PEER")
        or os.environ.get("TARGET_PEER_ID")
        or DEFAULT_MONEY_PEER
    )


def route_peer(
    *,
    text: str | None = None,
    signal_kind: str | None = None,
    card_type: str | None = None,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    lane = route_lane(
        text=text, signal_kind=signal_kind, card_type=card_type, meta=meta
    )
    peer = peer_for_lane(lane)
    return {
        "lane": lane,
        "peer": peer,
        "peer_ready": bool(peer),
        "coalition": lane == LANE_MONEY,
        "glue_result_under_fire": True,
        "note": (
            "money coalition → Mr_iv4"
            if lane == LANE_MONEY
            else f"countdown → Gunique (@{peer})"
        ),
    }


if __name__ == "__main__":
    demos = [
        {"signal_kind": "SOLO_ELITE", "text": "🚨 BAC BO SIGNAL 🚨\n🔵 BLUE"},
        {"signal_kind": "GOLDEN", "text": "SINAL GOLDEN — sem timer"},
        {"card_type": "CD_FIRE_TIMER_BRT_EDT_APOSTAR", "text": "⏳ 45s apostar agora"},
        {"signal_kind": "SEQUENCE", "text": "INTERVALO 30s janela"},
    ]
    for d in demos:
        print(d, "→", route_peer(**d))
