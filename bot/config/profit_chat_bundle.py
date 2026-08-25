"""Profit Chat Bundle — UNIQUE_g1 is #1; Mr_iv4 removed from the live equation.

Chats are not labels. A chat *is* when it BECOMES — proven by behavior:
  Profit · Volume · WR · Precision · Assertiveness · Existence · Essence · Impact · Results

Bundle (tactical):
  UNIQUE_g1  APEX         — #1 everything (replaces Mr_iv4)
  UNIQUE_g2  PRECISION    — sniper / high-assertiveness timed
  UNIQUE_g3  VOLUME       — dense secondary ENTER overflow
  UNIQUE_g4  ASSERTIVE    — gale / recovery / retentativa
  UNIQUE_g5  IMPACT       — result comprovation / ops that need a home
  UNIQUE_g6+ ELASTIC      — mint forever; never delay

Env:
  PROFIT_CHAT_BUNDLE=1
  TELEGRAM_PRIMARY_PEER=UNIQUE_g1   (or 5855678138)
  TELEGRAM_EXCLUDE_PEERS=Mr_iv4,6774605259
"""
from __future__ import annotations

import os
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple


PRIMARY_PEER = "UNIQUE_g1"
PRIMARY_ID = "5855678138"
EXCLUDED_DEFAULT = ("Mr_iv4", "mr_iv4", "6774605259")


@dataclass(frozen=True)
class ChatIdentity:
    """A chat becomes real by proven dimensions — not by a brand sticker."""

    peer: str
    peer_id: str
    rank: int
    becomes: str  # APEX | PRECISION | VOLUME | ASSERTIVE | IMPACT | ELASTIC
    essence: str
    method: str  # how it merges/uses/adds signals
    dimensions: Dict[str, str] = field(default_factory=dict)
    shelves: Tuple[str, ...] = ()

    def as_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["shelves"] = list(self.shelves)
        return d


BUNDLE: Tuple[ChatIdentity, ...] = (
    ChatIdentity(
        peer="UNIQUE_g1",
        peer_id=PRIMARY_ID,
        rank=1,
        becomes="APEX",
        essence="The first most important chat — all primary ENTER + clocks + gale home.",
        method="Take the signal when it is on time; glue RESULT here; spill only when soft-cap.",
        dimensions={
            "Profit": "max density — former Mr_iv4 seat",
            "Volume": "primary intake",
            "WR": "best cells preferred here",
            "Precision": "TTB release on this chat",
            "Assertiveness": "ENTER / JANELA stated as fact",
            "Existence": "always on for every round we have",
            "Essence": "the path",
            "Impact": "human acts here first",
            "Results": "comprovation glues here by default",
        },
        shelves=(
            "SHELF_PENTHOUSE_MONEY",
            "SHELF_UPPER_MONEY",
            "SHELF_COUNTDOWN",
            "SHELF_GALE",
            "SHELF_OPS_EXPIRE",
        ),
    ),
    ChatIdentity(
        peer="UNIQUE_g2",
        peer_id="",
        rank=2,
        becomes="PRECISION",
        essence="Sniper / high-assertiveness timed — FLASH, ULTRA_TIE, depth, certified.",
        method="Only high-precision FIRE families; opposite-color lock strict.",
        dimensions={
            "Profit": "edge per signal",
            "Volume": "lower, cleaner",
            "WR": "precision-first",
            "Precision": "max",
            "Assertiveness": "sharp ENTER",
            "Existence": "when precision cells fire",
            "Essence": "surgical",
            "Impact": "one clean bet",
            "Results": "glue to parent",
        },
        shelves=("SHELF_SNIPER",),
    ),
    ChatIdentity(
        peer="UNIQUE_g3",
        peer_id="",
        rank=3,
        becomes="VOLUME",
        essence="Dense secondary — overflow ENTER when APEX is at soft-cap.",
        method="Absorb volume without delaying the bet window.",
        dimensions={
            "Profit": "many min-stake windows",
            "Volume": "max secondary",
            "WR": "balanced",
            "Precision": "good enough + on time",
            "Assertiveness": "steady ENTER",
            "Existence": "fills gaps",
            "Essence": "throughput",
            "Impact": "no dead rounds",
            "Results": "glue to parent",
        },
        shelves=("SHELF_OVERFLOW", "SHELF_UPPER_MONEY"),
    ),
    ChatIdentity(
        peer="UNIQUE_g4",
        peer_id="",
        rank=4,
        becomes="ASSERTIVE",
        essence="Gale / recovery / retentativa — same color, stated only.",
        method="Follow parent color; never invent G3+.",
        dimensions={
            "Profit": "recovery capture",
            "Volume": "gale chain",
            "WR": "conditional on stated gale",
            "Precision": "same-color only",
            "Assertiveness": "max on RETENTATIVA",
            "Existence": "when G0 misses",
            "Essence": "second chance stated",
            "Impact": "bankroll discipline",
            "Results": "gale WIN/LOSS comprovation",
        },
        shelves=("SHELF_GALE",),
    ),
    ChatIdentity(
        peer="UNIQUE_g5",
        peer_id="",
        rank=5,
        becomes="IMPACT",
        essence="Result comprovation + ops that need a readable home.",
        method="THAT RESULT closes the subject; warnings protect.",
        dimensions={
            "Profit": "protect + close",
            "Volume": "results + ops",
            "WR": "truth display",
            "Precision": "forensic clear",
            "Assertiveness": "zero when WARN",
            "Existence": "every closed round",
            "Essence": "comprovation",
            "Impact": "human understands",
            "Results": "THE RESULT",
        },
        shelves=("SHELF_OPS_EXPIRE",),
    ),
)


def bundle_enabled() -> bool:
    return os.environ.get("PROFIT_CHAT_BUNDLE", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def excluded_peers() -> List[str]:
    raw = (os.environ.get("TELEGRAM_EXCLUDE_PEERS") or "").strip()
    if raw:
        return [p.strip().lstrip("@") for p in raw.split(",") if p.strip()]
    return list(EXCLUDED_DEFAULT)


def is_excluded(peer: Optional[str]) -> bool:
    if not peer:
        return False
    p = str(peer).lstrip("@").strip()
    ex = {x.lower() for x in excluded_peers()}
    return p.lower() in ex or p in excluded_peers()


def primary_peer() -> str:
    env = (os.environ.get("TELEGRAM_PRIMARY_PEER") or "").strip().lstrip("@")
    if env and not is_excluded(env):
        return env
    # Force g1 — Mr_iv4 removed from equation
    target = (os.environ.get("TELEGRAM_TARGET_PEER") or "").strip().lstrip("@")
    if target and not is_excluded(target):
        return target
    return PRIMARY_PEER


def primary_peer_id() -> str:
    env = (os.environ.get("TELEGRAM_PRIMARY_PEER_ID") or "").strip()
    if env.lstrip("-").isdigit():
        return env
    return PRIMARY_ID


def identity_for_peer(peer: str) -> Optional[ChatIdentity]:
    p = peer.lstrip("@")
    for c in BUNDLE:
        if c.peer.lower() == p.lower() or (c.peer_id and c.peer_id == p):
            return c
    m = re.match(r"^UNIQUE_g(\d+)$", p, re.I)
    if m and int(m.group(1)) >= 6:
        return ChatIdentity(
            peer=p,
            peer_id="",
            rank=int(m.group(1)),
            becomes="ELASTIC",
            essence="Minted overflow — never delay a bet window.",
            method="Soft-cap spill destination; same path rules.",
            dimensions={
                "Profit": "capture overflow",
                "Volume": "elastic",
                "WR": "inherits parent quality",
                "Precision": "on-time > neatness",
                "Assertiveness": "same as stated card",
                "Existence": "when needed",
                "Essence": "never miss",
                "Impact": "human still acts",
                "Results": "glue to parent",
            },
            shelves=("SHELF_OVERFLOW",),
        )
    return None


def peer_for_shelf(shelf_id: str) -> str:
    """Map shelf → bundle peer (Mr_iv4 never returned)."""
    for c in BUNDLE:
        if shelf_id in c.shelves:
            return c.peer
    # Defaults by shelf family
    if shelf_id in {
        "SHELF_PENTHOUSE_MONEY",
        "SHELF_UPPER_MONEY",
        "SHELF_COUNTDOWN",
        "SHELF_GALE",
        "SHELF_OPS_EXPIRE",
    }:
        return primary_peer()
    if shelf_id == "SHELF_SNIPER":
        return "UNIQUE_g2"
    if shelf_id == "SHELF_OVERFLOW":
        return "UNIQUE_g3"
    return primary_peer()


def peer_for_signal(
    text: Optional[str] = None,
    *,
    signal_kind: Optional[str] = None,
    family_id: Optional[str] = None,
    role: Optional[str] = None,
    is_result: bool = False,
    parent_peer: Optional[str] = None,
) -> Tuple[str, str]:
    """Situation-aware route: returns (peer, reason). Never Mr_iv4."""
    body = text or ""
    kind = (signal_kind or "").upper()
    fam = (family_id or "").upper()
    role_u = (role or "").upper()

    if is_result or role_u == "RESULT":
        if parent_peer and not is_excluded(parent_peer):
            return parent_peer.lstrip("@"), "result_glue_parent"
        return primary_peer(), "result→APEX"

    # Precision sniper families → g2
    if any(
        x in fam or x in kind or x in body.upper()
        for x in (
            "FLASH",
            "ULTRA_TIE",
            "ULTRA TIE",
            "DEPTH_G0",
            "EMPATE_DIRETO",
            "CERTIFIED_ELITE",
            "SHELF_SNIPER",
        )
    ):
        if re.search(r"JANELA|Sinal\s+Retido|🟢\s*\d+\s*s", body, re.I):
            return primary_peer(), "timed_precision→APEX"
        return "UNIQUE_g2", "precision→g2"

    # Gale / assertive → g4 if not primary density; prefer APEX first then g4 spill
    if any(
        x in fam or x in body
        for x in (
            "GALE",
            "RETENTATIVA",
            "Entre novamente",
            "PREPARE_G1",
            "PREPARE O G1",
            "AGUARDANDO G",
        )
    ):
        return primary_peer(), "gale→APEX"

    # Countdown / JANELA → APEX (g1 is both money + clock now)
    if re.search(
        r"JANELA\s*[:=]|Sinal\s+Retido|🟢\s*\d+\s*s|CD_FIRE|COUNTDOWN",
        body,
        re.I,
    ) or "COUNTDOWN" in kind:
        return primary_peer(), "countdown→APEX"

    # Default ENTER / money → APEX
    if role_u == "FIRE" or re.search(
        r"ENTER\s+NOW|APOSTE\s+AGORA|ENTRE\s+AGORA|APOSTAR\s+AGORA|GOLDEN|SOLO|SEQUENCE|PLATINUM",
        body,
        re.I,
    ):
        return primary_peer(), "enter→APEX"

    # Ops / warnings → APEX (readable on #1) or IMPACT g5 for heavy forensic
    if re.search(r"RESUMIDO\s+FORENSE|DELIVERY\s+AUDIT|GATE\s*\[", body, re.I):
        return "UNIQUE_g5", "impact→g5"

    return primary_peer(), "default→APEX"


def overflow_bundle_peers() -> List[str]:
    """Soft-cap spill order — never includes Mr_iv4."""
    env = (os.environ.get("TELEGRAM_SHELF_OVERFLOW_PEERS") or "").strip()
    if env:
        peers = [p.strip().lstrip("@") for p in env.split(",") if p.strip()]
        return [p for p in peers if not is_excluded(p)]
    return ["UNIQUE_g2", "UNIQUE_g3", "UNIQUE_g4", "UNIQUE_g5"]


def bundle_catalog() -> Dict[str, Any]:
    return {
        "law": "A chat IS when it BECOMES — proven by Profit/Volume/WR/Precision/Assertiveness/Existence/Essence/Impact/Results.",
        "primary": primary_peer(),
        "primary_id": primary_peer_id(),
        "excluded": excluded_peers(),
        "excluded_note": "Mr_iv4 removed from the live equation — UNIQUE_g1 takes its place.",
        "bundle": [c.as_dict() for c in BUNDLE],
        "overflow_order": overflow_bundle_peers(),
        "reality": "Make It Real / It Is Real, Really. Reality: It Is Real truthfully.",
    }
