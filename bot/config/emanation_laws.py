"""EMANATION LAWS — locked product model (hub brain → hermetic chat shelves).

North star
  Every gate/camada/floor/system/setup proposes at max volume into the HUB.
  Hub absorbs 100% invisibly, then emanates complete independent streams
  into whatever chat group is needed. Chats never see each other.

LAW 1 — Color truth = factual win
  Same-color coalitions score strength. Opposite-color same window = LOCK
  (watchdog + learn from RESULT causality — never delete the minority forever).
  What we FIRE as money truth is the color that is ACTUALLY winning / won
  (factual RESULT), not a committee cosplay when reality already spoke.
  Committee aggregate is PROVISIONAL only when factual color is unknown.

LAW 2 — One signal ID = one vertical bundle
  Signal #N is an atom. In its chat, everything for #N stays glued:
    FIRE → RESULT card right under it → gale cards after (if that signal needs)
    → then signal #N+1 for the next round.
  Nothing from #N interleaves with another signal.

LAW 3 — Hermetic chats
  Each chat is its own universe — unaware siblings exist.
  Own FIREs, own RESULTs, own gales, own rhythm.
  Hub may feed many chats; users never see the hub or other shelves.

Env (default ON under HUB_MAX):
  EMANATION_LAWS=1
  COLOR_TRUTH_FACTUAL=1
  SIGNAL_BUNDLE_VERTICAL=1
  CHAT_HERMETIC=1
  RESULT_REPLY_TO_FIRE=1
"""
from __future__ import annotations

import os
from typing import Any, Optional


def enabled() -> bool:
    return os.environ.get("EMANATION_LAWS", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def color_truth_factual() -> bool:
    if not enabled():
        return False
    return os.environ.get("COLOR_TRUTH_FACTUAL", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def signal_bundle_vertical() -> bool:
    if not enabled():
        return False
    return os.environ.get("SIGNAL_BUNDLE_VERTICAL", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def chat_hermetic() -> bool:
    if not enabled():
        return False
    return os.environ.get("CHAT_HERMETIC", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def result_reply_to_fire() -> bool:
    """Telegram reply_to so RESULT visually sits under its FIRE."""
    if not signal_bundle_vertical():
        return False
    return os.environ.get("RESULT_REPLY_TO_FIRE", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def normalize_color(c: Any) -> str:
    u = str(c or "").strip().lower()
    if u in {"b", "azul", "blue", "🔵"}:
        return "blue"
    if u in {"r", "vermelho", "red", "🔴"}:
        return "red"
    if u in {"tie", "empate", "🟡", "yellow"}:
        return "tie"
    return u


def factual_color_from_outcome(predicted: str, outcome: str) -> str:
    """Derive the color that actually won from predicted + outcome."""
    pred = normalize_color(predicted)
    out = str(outcome or "").strip().lower()
    if out in {"tie", "empate"}:
        return "tie"
    if out in {"win", "green", "g0", "g1", "g2"}:
        return pred
    if out in {"loss", "red_x", "lose"}:
        if pred == "blue":
            return "red"
        if pred == "red":
            return "blue"
    return "unknown"


def bundle_steps() -> tuple[str, ...]:
    """Canonical vertical order for one signal atom."""
    return ("FIRE", "RESULT", "GALE")


def law_banner() -> str:
    return (
        "[EMANATION] ON — factual color truth; "
        "signal# vertical FIRE→RESULT→gale; "
        "hermetic chats (unaware siblings)"
    )
