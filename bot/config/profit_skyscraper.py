"""Profit Chat Bundle OS — UNIQUE_g1 is #1; Mr_iv4 removed.

Chats BECOME by proven dimensions (Profit/Volume/WR/Precision/Assertiveness/
Existence/Essence/Impact/Results) — not brand stickers.

  UNIQUE_g1  APEX       — #1 everything (takes Mr_iv4's place)
  UNIQUE_g2  PRECISION  — sniper
  UNIQUE_g3  VOLUME     — dense overflow
  UNIQUE_g4  ASSERTIVE  — gale / recovery
  UNIQUE_g5  IMPACT     — result comprovation / ops home
  UNIQUE_g6+ ELASTIC    — never delay

Env:
  PROFIT_CHAT_BUNDLE=1
  TELEGRAM_PRIMARY_PEER=UNIQUE_g1
  TELEGRAM_EXCLUDE_PEERS=Mr_iv4,6774605259
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from bot.config.profit_chat_bundle import (
    BUNDLE,
    bundle_catalog,
    bundle_enabled,
    excluded_peers,
    primary_peer,
    primary_peer_id,
)


def skyscraper_enabled() -> bool:
    return os.environ.get("PROFIT_SKYSCRAPER", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def money_first() -> bool:
    """Legacy name: primary-first. With bundle, PRIMARY = UNIQUE_g1 (not Mr_iv4).

    Returns True when ENTER/money should prefer the primary peer (g1).
    Mr_iv4 money-first is OFF — excluded from the equation.
    """
    if os.environ.get("HUB_MONEY_FIRST", "0").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }:
        # Explicit legacy Mr_iv4 money-first — ignore when excluded
        if "6774605259" in excluded_peers() or "Mr_iv4" in excluded_peers():
            return False
        return True
    # Bundle default: g1 is primary for everything that used to be "money"
    return bundle_enabled() or skyscraper_enabled()


def g1_apex_first() -> bool:
    """UNIQUE_g1 is the first most important chat."""
    return os.environ.get("HUB_G1_APEX_FIRST", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


PLAY_RULES_SIMPLE: List[Dict[str, str]] = [
    {
        "when": "ENTER NOW / APOSTE AGORA / ENTRE AGORA + color (🔴/🔵)",
        "do": "Bet the MINIMUM on that color NOW.",
        "stop": "Wait for WIN / LOSS / gale card for this signal.",
    },
    {
        "when": "JANELA / 🟢 Ns 🟢 / Sinal Retido→Liberado",
        "do": "Same: minimum bet on the color before the seconds hit 0.",
        "stop": "If it says RODADA JÁ PASSOU / DO NOT BET — skip.",
    },
    {
        "when": "GALE / RETENTATIVA / Entre novamente / AGUARDANDO G1",
        "do": "Same color, MINIMUM bet again (G1). Then G2 only if the card says so.",
        "stop": "Never invent G3+ unless the chat posts it.",
    },
    {
        "when": "✅ WIN / GREEN / GANHOU",
        "do": "Round over. Bank the win. Wait for next ENTER.",
        "stop": "Do not re-bet the same round.",
    },
    {
        "when": "❌ LOSS / PERDEU + no gale card",
        "do": "Round over. Next signal only.",
        "stop": "Do not chase with your own gales.",
    },
    {
        "when": "DO NOT BET / NÃO APOSTE / RODADA PASSOU / EXPIROU / G2 MISS",
        "do": "Skip. Zero bet.",
        "stop": "This protects the bankroll.",
    },
    {
        "when": "OPS only (quarantine, schedule, grounded, hot/cold)",
        "do": "Read. Do not bet from ops alone.",
        "stop": "Bet only from ENTER / JANELA / GALE cards.",
    },
]

STAKE_POLICY = {
    "mode": "MINIMUM_ALWAYS",
    "rule": "Always the platform minimum unit. Volume of correct windows > size of bet.",
    "gale_ladder": "G0 = 1u, G1 = 1u (same min), G2 = 1u only if card says enter G2.",
    "never": "Never raise stake to 'recover'. Never bet without a card.",
    "worst_case_5_signals": (
        "Even if a chat only posts 5 ENTER/day: play all 5 with min stake + official gales. "
        "Skip DO-NOT-BET. That chat is still fully used."
    ),
}


def playbook_card(chat_key: str) -> str:
    """Pin text — chat identity by what it BECOMES."""
    key = (chat_key or "").lower()
    if key in ("unique_g1", "g1", "apex", "primary", "money", "penthouse"):
        becomes, focus = "APEX #1", "All primary ENTER + clocks + gale. Replaces Mr_iv4."
    elif key in ("unique_g2", "g2", "precision"):
        becomes, focus = "PRECISION", "Sniper / FLASH / ULTRA_TIE — clean high-assertiveness."
    elif key in ("unique_g3", "g3", "volume"):
        becomes, focus = "VOLUME", "Dense overflow when APEX is busy — never delay."
    elif key in ("unique_g4", "g4", "assertive", "gale"):
        becomes, focus = "ASSERTIVE", "Gale / recovery — same color only if stated."
    elif key in ("unique_g5", "g5", "impact"):
        becomes, focus = "IMPACT", "RESULT comprovation + protective warnings."
    else:
        becomes, focus = "ELASTIC", "Minted overflow — same path, never miss a window."

    return "\n".join(
        [
            f"THE PATH — this chat BECOMES: {becomes}",
            focus,
            "",
            "1) REAL FACT: ENTER + color → bet MINIMUM on that color.",
            "2) Seconds on the card → bet BEFORE 0.",
            "3) WARNING (DO NOT BET / expired / cold) → zero.",
            "4) GALE / again → same color, MINIMUM — only if stated.",
            "5) RESULT comprovation (WIN/LOSS/TIE) → round closed.",
            "6) Never invent bets. Stated subject = only subject.",
            "",
            "On time every round we have. Get the most of all — truthfully resourceful.",
            "Mr_iv4 is out of this equation. Bundle = UNIQUE_g1…gN.",
        ]
    )


def chat_map() -> Dict[str, Any]:
    cat = bundle_catalog()
    return {
        "primary": cat["primary"],
        "primary_id": cat["primary_id"],
        "excluded": cat["excluded"],
        "bundle": cat["bundle"],
        "rules": {
            "never_delay": True,
            "soft_cap_spills_only": True,
            "results_glue_to_parent_chat": True,
            "apex": "UNIQUE_g1",
            "mr_iv4": "REMOVED",
        },
        "play_rules": PLAY_RULES_SIMPLE,
        "stake_policy": STAKE_POLICY,
        "reality": cat["reality"],
    }


def distribution_plan() -> Dict[str, Any]:
    return {
        "FIRE_money_enter": {
            "shelf": "SHELF_PENTHOUSE_MONEY / SHELF_UPPER_MONEY",
            "chat": "UNIQUE_g1 APEX",
            "spill": "UNIQUE_g3…gN",
            "user": "Bet min on color",
        },
        "FIRE_countdown_sniper": {
            "shelf": "SHELF_COUNTDOWN → APEX; SHELF_SNIPER → g2",
            "chat": "UNIQUE_g1 / UNIQUE_g2",
            "spill": "UNIQUE_g3…gN",
            "user": "Bet min before timer ends",
        },
        "FIRE_gale": {
            "shelf": "SHELF_GALE",
            "chat": "UNIQUE_g1 APEX (or parent)",
            "spill": "UNIQUE_g4 ASSERTIVE",
            "user": "Same color min again",
        },
        "RESULT": {
            "shelf": "parent",
            "chat": "exact chat of the FIRE",
            "user": "RESULT comprovation closes the round",
        },
        "OPS_health": {
            "shelf": "SHELF_OPS / IMPACT",
            "chat": "UNIQUE_g1 or UNIQUE_g5",
            "user": "Read only — no bet",
        },
        "ROOM_RELAY": {
            "shelf": "AI-filter later; keep for edge",
            "chat": "UNIQUE_g5 IMPACT",
            "user": "Do not bet from raw relay alone",
        },
        "TRASH": {
            "shelf": "blocked",
            "chat": "nowhere",
            "user": "Ignored",
        },
        "MR_IV4": {
            "shelf": "excluded",
            "chat": "REMOVED from live equation",
            "user": "—",
        },
    }
