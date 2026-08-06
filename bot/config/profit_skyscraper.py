"""Profit Skyscraper OS — distribution brain + kid-simple play rules.

Locked architecture:
  Mr_iv4     = MONEY PENTHOUSE (max profit density; ENTER / gale / ops)
  UNIQUE_g1  = COUNTDOWN / SNIPER (time windows — never delay)
  UNIQUE_g2… = soft-cap overflow only (mint gN as needed; never delay)

User goal: every chat readable by a 12-year-old; minimum stake; capture every
real ENTER/GALE opportunity; skip DO-NOT-BET noise.

Env:
  PROFIT_SKYSCRAPER=1          enable money-first + spill wiring helpers
  HUB_MONEY_FIRST=1            money ENTER → Mr_iv4 (overrides Gunique-first)
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional


# ── Chat roles (locked) ─────────────────────────────────────────────────────
CHAT_MR_IV4 = {
    "id": "6774605259",
    "username": "Mr_iv4",
    "title": "Mr_iv4 — MONEY PENTHOUSE",
    "job": "Biggest money chat. ENTER NOW colors, gale retries, WIN/LOSS, ops.",
    "priority": 1,
}
CHAT_UNIQUE_G1 = {
    "id": "5855678138",
    "username": "UNIQUE_g1",
    "title": "UNIQUE_g1 — COUNTDOWN / SNIPER",
    "job": "Timed windows (JANELA / Sinal Retido / FLASH). Bet in the seconds.",
    "priority": 2,
}
CHAT_OVERFLOW = {
    "pattern": "UNIQUE_g{N}",
    "start_n": 2,
    "title": "UNIQUE_g2…gN — OVERFLOW",
    "job": "Only when Mr_iv4 or g1 is too busy. Same rules. Never wait.",
    "priority": 3,
}


def skyscraper_enabled() -> bool:
    return os.environ.get("PROFIT_SKYSCRAPER", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def money_first() -> bool:
    """Money ENTER skins → Mr_iv4 (user: Mr_iv4 is the profit king)."""
    if os.environ.get("HUB_MONEY_FIRST", "1").strip().lower() in {
        "0",
        "false",
        "no",
        "off",
    }:
        return False
    # Explicit money-first wins over legacy Gunique-first when skyscraper on
    if skyscraper_enabled():
        return True
    return os.environ.get("HUB_GUNIQUE_FIRST", "1").strip().lower() in {
        "0",
        "false",
        "no",
        "off",
    }


# ── Kid-simple play rules (universal — every chat) ──────────────────────────
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
        "Even if a chat only posts 5 ENTER days: play all 5 with min stake + official gales. "
        "Skip DO-NOT-BET. That chat is still fully used."
    ),
}


def playbook_card(chat_key: str) -> str:
    """Telegram-ready pin — human path first; labels are secondary."""
    try:
        import sys
        from pathlib import Path

        for root in (
            Path(__file__).resolve().parents[2] / "replit_elite_stack_patch" / "bot",
            Path("/home/runner/workspace/bot"),
            Path("/workspace/replit_elite_stack_patch/bot"),
        ):
            if (root / "human_return_path.py").is_file():
                s = str(root)
                if s not in sys.path:
                    sys.path.insert(0, s)
                from human_return_path import pin_card

                return pin_card(chat_key)
    except Exception:
        pass
    if chat_key in ("mr_iv4", "money", "penthouse"):
        where, focus = "This is the main money path.", "Most ENTER / gale / WIN-LOSS live here."
    elif chat_key in ("unique_g1", "g1", "countdown"):
        where, focus = "This is the fast-clock path.", "JANELA / timers — bet in the seconds you see."
    else:
        where, focus = "Same path, quieter room.", "If ENTER appears here, treat it as real."
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
            "Your job: follow. Minimum stake. Every real chance.",
        ]
    )


def chat_map() -> Dict[str, Any]:
    return {
        "mr_iv4": CHAT_MR_IV4,
        "unique_g1": CHAT_UNIQUE_G1,
        "overflow": CHAT_OVERFLOW,
        "rules": {
            "never_delay": True,
            "soft_cap_spills_only": True,
            "results_glue_to_parent_chat": True,
            "money_penthouse": "Mr_iv4",
            "countdown_primary": "UNIQUE_g1",
        },
        "play_rules": PLAY_RULES_SIMPLE,
        "stake_policy": STAKE_POLICY,
    }


def distribution_plan() -> Dict[str, Any]:
    """How every KEEP role is distributed across the building."""
    return {
        "FIRE_money_enter": {
            "shelf": "SHELF_PENTHOUSE_MONEY / SHELF_UPPER_MONEY",
            "chat": "Mr_iv4",
            "spill": "UNIQUE_g2…gN",
            "user": "Bet min on color",
        },
        "FIRE_countdown_sniper": {
            "shelf": "SHELF_COUNTDOWN / SHELF_SNIPER",
            "chat": "UNIQUE_g1",
            "spill": "UNIQUE_g2…gN",
            "user": "Bet min before timer ends",
        },
        "FIRE_gale": {
            "shelf": "SHELF_GALE",
            "chat": "Mr_iv4 (or parent if glued)",
            "spill": "UNIQUE_g2…gN",
            "user": "Same color min again",
        },
        "RESULT": {
            "shelf": "parent",
            "chat": "exact chat of the FIRE",
            "user": "Stop round on WIN/LOSS; follow gale if posted",
        },
        "OPS_health": {
            "shelf": "SHELF_OPS / overflow",
            "chat": "Mr_iv4",
            "user": "Read only — no bet",
        },
        "ROOM_RELAY": {
            "shelf": "AI-filter later; keep for edge",
            "chat": "Mr_iv4 / ops",
            "user": "Do not bet from raw relay alone",
        },
        "TRASH": {
            "shelf": "blocked",
            "chat": "nowhere",
            "user": "Ignored",
        },
    }
