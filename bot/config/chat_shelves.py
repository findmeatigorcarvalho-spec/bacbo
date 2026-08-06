"""Chat shelves — capacity-aware placement for skin/floor building.

NOT DB-kinds-only. Shelves cover:
  - ENTER NOW money skins (SOLO/GOLDEN/SEQUENCE/PLATINUM)
  - Countdown peak fires (Sinal Retido, JANELA, CD_FIRE_*)
  - Forensic G0/G1/G2 results + short WIN/LOSS
  - Gale follow-ups, G1 EXPIROU, G2 MISS
  - Sniper kinds (FLASH / ULTRA_TIE / EMERGING)
  - CREATED_ONLY vault (never drop)
  - Noise sink

RESULT / result-ops always prefer the parent fire's shelf when known.
Overflow when a shelf exceeds ~2–3 signals/min — never drop a fire.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from bot.config.skin_families import (
    LANE_COUNTDOWN,
    LANE_MONEY,
    SkinMatch,
    canonical_family_id,
    classify_telegram_skin,
)


# ── Shelf ids (stable) ──────────────────────────────────────────────────────
SHELF_PENTHOUSE_MONEY = "SHELF_PENTHOUSE_MONEY"
SHELF_UPPER_MONEY = "SHELF_UPPER_MONEY"
SHELF_COUNTDOWN = "SHELF_COUNTDOWN"
SHELF_SNIPER = "SHELF_SNIPER"
SHELF_GALE = "SHELF_GALE"
SHELF_OPS_EXPIRE = "SHELF_OPS_EXPIRE"
SHELF_OVERFLOW = "SHELF_OVERFLOW"
SHELF_VAULT = "SHELF_VAULT"
SHELF_SINK = "SHELF_SINK"

# Default peer env keys / fallbacks (elastic chats can override later)
_SHELF_PEER_ENV = {
    SHELF_PENTHOUSE_MONEY: ("TELEGRAM_SHELF_PENTHOUSE", "TELEGRAM_TARGET_PEER"),
    SHELF_UPPER_MONEY: ("TELEGRAM_SHELF_UPPER", "TELEGRAM_TARGET_PEER"),
    SHELF_COUNTDOWN: (
        "TELEGRAM_SHELF_COUNTDOWN",
        "TELEGRAM_COUNTDOWN_PEER",
        "TELEGRAM_GUNIQUE_PEER",
        "GUNIQUE_PEER",
    ),
    SHELF_SNIPER: ("TELEGRAM_SHELF_SNIPER", "TELEGRAM_COUNTDOWN_PEER", "TELEGRAM_TARGET_PEER"),
    SHELF_GALE: ("TELEGRAM_SHELF_GALE", "TELEGRAM_TARGET_PEER"),
    SHELF_OPS_EXPIRE: ("TELEGRAM_SHELF_OPS", "TELEGRAM_TARGET_PEER"),
    SHELF_OVERFLOW: ("TELEGRAM_SHELF_OVERFLOW", "TELEGRAM_TARGET_PEER"),
    SHELF_VAULT: ("TELEGRAM_SHELF_VAULT",),  # usually no live send
    SHELF_SINK: ("TELEGRAM_SHELF_SINK",),
}

# Chat map (locked — Profit Chat Bundle):
#   UNIQUE_g1            — APEX #1 (replaces Mr_iv4): money + countdown + gale
#   UNIQUE_g2            — PRECISION sniper
#   UNIQUE_g3..g5        — VOLUME / ASSERTIVE / IMPACT
#   UNIQUE_g6+           — elastic overflow (see chat_router)
#   Mr_iv4               — REMOVED from live equation
_DEFAULT_PEERS = {
    SHELF_PENTHOUSE_MONEY: "UNIQUE_g1",  # APEX
    SHELF_UPPER_MONEY: "UNIQUE_g1",  # APEX
    SHELF_COUNTDOWN: "UNIQUE_g1",  # APEX
    SHELF_SNIPER: "UNIQUE_g2",  # PRECISION
    SHELF_GALE: "UNIQUE_g1",  # APEX
    SHELF_OPS_EXPIRE: "UNIQUE_g1",  # glue prefers parent; default APEX
    SHELF_OVERFLOW: "UNIQUE_g3",  # VOLUME first overflow
    SHELF_VAULT: "",
    SHELF_SINK: "",
}

# Family → shelf (FIRE / OPS that choose a shelf). RESULT inherits parent.
_FAMILY_SHELF: Dict[str, str] = {
    # PENTHOUSE money
    "FIRE_SOLO_ELITE_ENTER": SHELF_PENTHOUSE_MONEY,
    "FIRE_SOLO_ELITE_SIGNAL": SHELF_PENTHOUSE_MONEY,
    "FIRE_SOLO_APOSTAR": SHELF_PENTHOUSE_MONEY,
    "SIGNAL_KIND_SOLO_ELITE": SHELF_PENTHOUSE_MONEY,
    # UPPER money
    "FIRE_GOLDEN_ENTER": SHELF_UPPER_MONEY,
    "FIRE_GOLDEN_SIGNAL_ENTER_NOW": SHELF_UPPER_MONEY,
    "FIRE_GOLDEN_APOSTAR": SHELF_UPPER_MONEY,
    "FIRE_SEQUENCE_ENTER": SHELF_UPPER_MONEY,
    "FIRE_SEQUENCE": SHELF_UPPER_MONEY,
    "FIRE_SEQUENCE_APOSTAR": SHELF_UPPER_MONEY,
    "FIRE_SEQUENCIA_ENTER_NOW": SHELF_UPPER_MONEY,
    "FIRE_PLATINUM_ENTER": SHELF_UPPER_MONEY,
    "FIRE_PLATINUM": SHELF_UPPER_MONEY,
    "FIRE_PLATINUM_APOSTAR": SHELF_UPPER_MONEY,
    "FIRE_CONFIRMED_ENTER": SHELF_UPPER_MONEY,
    "FIRE_SIGNAL_CONFIRMED_ENTER_NOW": SHELF_UPPER_MONEY,
    "FIRE_COMPACT_HASH": SHELF_UPPER_MONEY,
    "FIRE_GOD_TIER": SHELF_UPPER_MONEY,
    "FIRE_GOLDEN_ENTRE_AGORA": SHELF_UPPER_MONEY,
    "SIGNAL_KIND_GOLDEN": SHELF_UPPER_MONEY,
    "SIGNAL_KIND_SEQUENCE": SHELF_UPPER_MONEY,
    "SIGNAL_KIND_PLATINUM": SHELF_UPPER_MONEY,
    # COUNTDOWN peak (historically elite — not optional)
    "FIRE_SINAL_RETIDO_LIBERADO": SHELF_COUNTDOWN,
    "FIRE_JANELA_TIMED": SHELF_COUNTDOWN,
    "CD_FIRE_TIMER_BRT_EDT_APOSTAR": SHELF_COUNTDOWN,
    "CD_FIRE_QUANTUM_LOCK": SHELF_COUNTDOWN,
    "CD_FIRE_RUSH_NS_LEFT": SHELF_COUNTDOWN,
    # Sniper
    "FIRE_FLASH_APOSTAR": SHELF_SNIPER,
    "FIRE_FLASH": SHELF_SNIPER,
    "SIGNAL_KIND_FLASH": SHELF_SNIPER,
    "FIRE_ULTRA_TIE": SHELF_SNIPER,
    "SIGNAL_KIND_ULTRA_TIE": SHELF_SNIPER,
    "SIGNAL_KIND_EMERGING": SHELF_SNIPER,
    "FIRE_EMERGING": SHELF_SNIPER,
    "FIRE_EMPATE_DIRETO_G0": SHELF_SNIPER,
    "FIRE_G0_DIRETO": SHELF_SNIPER,
    "FIRE_PREPARE_G1": SHELF_GALE,
    # Gale follow-ups
    "FIRE_GALE_RETENTATIVA": SHELF_GALE,
    "FIRE_GALE_ENTRE_NOVAMENTE": SHELF_GALE,
    "FIRE_GALE_1_RETENTATIVA_SOLO_ELITE": SHELF_GALE,
    "FIRE_GALE_1_RETENTATIVA_GOLDEN": SHELF_GALE,
    "FIRE_G0_MISS_ENTRE_G1": SHELF_GALE,
    # Expire ops
    "OPS_G1_EXPIROU": SHELF_OPS_EXPIRE,
    "OPS_G2_MISS": SHELF_OPS_EXPIRE,
    # Code-formatter FIRE cards
    "FIRE_ENTER_NOW_GENERIC": SHELF_UPPER_MONEY,
    "FIRE_ENTRE_AGORA_GENERIC": SHELF_UPPER_MONEY,
    "FIRE_APOSTE_AGORA": SHELF_UPPER_MONEY,
    "FIRE_G0_ENTRADA_DIRETA": SHELF_UPPER_MONEY,
    "FIRE_DEPTH_G0_ONLY": SHELF_SNIPER,
    "FIRE_INVERTED_CONTRARIO": SHELF_OVERFLOW,
    "FIRE_ORACLE_LOCK": SHELF_VAULT,
    "FIRE_CERTIFIED_ELITE": SHELF_PENTHOUSE_MONEY,
    "FIRE_GRADE_BANNER": SHELF_UPPER_MONEY,
    "FIRE_HOT_STREAK": SHELF_OVERFLOW,
    "FIRE_DOUBLE_TIE_LOCK": SHELF_VAULT,
    "FIRE_GALE_1_FACA_AGORA": SHELF_GALE,
    # Ops banners (overflow unless dedicated shelf later)
    "OPS_TIE_ALERT": SHELF_OVERFLOW,
    "OPS_CORRECAO": SHELF_OVERFLOW,
    "OPS_JANELA_PRIME": SHELF_COUNTDOWN,
    "OPS_DO_NOT_BET_YET": SHELF_OVERFLOW,
    "OPS_PREPARE_PLATFORM": SHELF_OVERFLOW,
    "OPS_NEXT_CERTIFIED_WINDOW": SHELF_COUNTDOWN,
    "OPS_JANELA_PEAK": SHELF_COUNTDOWN,
    "OPS_G1_REGISTRADO_CALC_G2": SHELF_OPS_EXPIRE,
    "OPS_G2_STOP_IF_G1_LOST": SHELF_OPS_EXPIRE,
    "OPS_G3_ATINGIDO": SHELF_OPS_EXPIRE,
    # Noise
    "ROOM_RELAY": SHELF_SINK,
    "RESULT_BANNER_FAMILY": SHELF_SINK,
    "OPS_GATE_HEALTH_DUMP": SHELF_SINK,
    "OPS_ROOM_QUARANTINE": SHELF_SINK,
    "OPS_DELIVERY_AUDIT": SHELF_SINK,
    "OPS_MANUAL_RESULT_HINT": SHELF_SINK,
}

# Families that glue under parent (never choose shelf alone)
_PARENT_FOLLOW = {
    "RESULT_FORENSIC_INTERVALO",
    "RESULT_BELL_GANHOU",
    "RESULT_WIN_TIER",
    "RESULT_LOSS_TIER",
    "RESULT_EMPATE",
    "RESULT_FLASH_WIN",
    "RESULT_GREEN_LEGACY_G0",
    "RESULT_GREEN_LEGACY_G1",
    "RESULT_GREEN_COMPACT_G0",
    "RESULT_GREEN_COMPACT_G1",
    "RESULT_COMPACT_WIN_HASH",
    "RESULT_COMPACT_LOSS_HASH",
    "RESULT_COMPACT_TIE_HASH",
    "RESULT_AUTO_TIE",
    "RESULT_TIMED_WINDOW",
    "RESULT_GALE_OUTCOME",
    "RESULT_ORACLE_CARD",
    "RESULT_G0_ACERTOU_PRIMEIRA",
    "RESULT_GALE_RECOVERED_CHAIN",
    "RESULT_EMPATE_DINHEIRO_DEVOLVIDO",
    "RESULT_EMPATE_PROTECAO",
    "CD_RES_GREEN_G_BRT",
    "CD_RES_RODADAS_TEMPO",
    "CD_RES_BELL_GANHOU",
    "OPS_G1_EXPIROU",
    "OPS_G2_MISS",
    "OPS_G1_REGISTRADO_CALC_G2",
    "OPS_G2_STOP_IF_G1_LOST",
    "OPS_G3_ATINGIDO",
    "OPS_CORRECAO",
}


@dataclass(frozen=True)
class ShelfDecision:
    shelf_id: str
    family_id: str
    role: str
    kind: Optional[str]
    lane: Optional[str]
    peer: Optional[str]
    follow_parent: bool
    band_hint: str
    reason: str
    skin: Optional[SkinMatch] = None

    def as_dict(self) -> Dict[str, Any]:
        return {
            "shelf_id": self.shelf_id,
            "family_id": self.family_id,
            "role": self.role,
            "kind": self.kind,
            "lane": self.lane,
            "peer": self.peer,
            "follow_parent": self.follow_parent,
            "band_hint": self.band_hint,
            "reason": self.reason,
            "skin": self.skin.as_dict() if self.skin else None,
        }


def _peer_for_shelf(shelf_id: str) -> Optional[str]:
    try:
        from bot.config.profit_chat_bundle import (
            is_excluded,
            peer_for_shelf,
            primary_peer,
        )

        # Bundle wins when enabled — never return Mr_iv4
        peer = peer_for_shelf(shelf_id)
        if peer and not is_excluded(peer):
            return peer
        return primary_peer()
    except Exception:
        pass
    for key in _SHELF_PEER_ENV.get(shelf_id, ()):
        raw = (os.environ.get(key) or "").strip().strip('"').strip("'")
        if raw:
            peer = raw.lstrip("@") if not raw.lstrip("-").isdigit() else raw
            # Hard-exclude Mr_iv4 even without bundle import
            if peer in {"6774605259", "Mr_iv4", "mr_iv4"}:
                continue
            return peer
    default = _DEFAULT_PEERS.get(shelf_id, "") or "UNIQUE_g1"
    if default in {"6774605259", "Mr_iv4", "mr_iv4"}:
        return "UNIQUE_g1"
    return default or None


def _band_hint(shelf_id: str) -> str:
    return {
        SHELF_PENTHOUSE_MONEY: "PENTHOUSE",
        SHELF_UPPER_MONEY: "UPPER",
        SHELF_COUNTDOWN: "UPPER_COUNTDOWN",
        SHELF_SNIPER: "MID_SNIPER",
        SHELF_GALE: "MID_GALE",
        SHELF_OPS_EXPIRE: "OPS",
        SHELF_OVERFLOW: "OVERFLOW",
        SHELF_VAULT: "CREATED_ONLY",
        SHELF_SINK: "NOISE",
    }.get(shelf_id, "UNRANKED")


def shelf_for_family(family_id: str) -> str:
    raw = (family_id or "").strip()
    fid = canonical_family_id(raw)
    if fid in _FAMILY_SHELF:
        return _FAMILY_SHELF[fid]
    if raw in _FAMILY_SHELF:
        return _FAMILY_SHELF[raw]
    if fid == "SIGNAL_KIND_SOLO_ELITE" or raw == "SIGNAL_KIND_SOLO_ELITE":
        return SHELF_PENTHOUSE_MONEY
    if fid.startswith("SIGNAL_KIND_") or raw.startswith("SIGNAL_KIND_"):
        kind = (fid or raw).replace("SIGNAL_KIND_", "")
        if kind == "FLASH":
            return SHELF_SNIPER
        if kind in {"ULTRA_TIE", "EMERGING"}:
            return SHELF_SNIPER
        return SHELF_UPPER_MONEY
    if fid.startswith("CD_FIRE_") or fid.startswith("FIRE_JANELA"):
        return SHELF_COUNTDOWN
    if fid.startswith("CD_RES_") or fid.startswith("RESULT_"):
        return SHELF_UPPER_MONEY  # placeholder; resolve_shelf uses parent
    if fid.startswith("OPS_"):
        return SHELF_OPS_EXPIRE
    if fid.startswith("FIRE_"):
        return SHELF_UPPER_MONEY
    return SHELF_OVERFLOW


def resolve_shelf(
    text: Optional[str] = None,
    *,
    signal_kind: Optional[str] = None,
    meta: Optional[Dict[str, Any]] = None,
    parent_shelf: Optional[str] = None,
    parent_lane: Optional[str] = None,
) -> ShelfDecision:
    """Classify card → shelf. RESULT/expire follow parent when provided."""
    meta = meta or {}
    skin = classify_telegram_skin(text, signal_kind=signal_kind, meta=meta)
    fid = skin.family_id
    follow = fid in _PARENT_FOLLOW or skin.role == "RESULT"

    if follow:
        shelf = (parent_shelf or "").strip()
        if not shelf:
            # Infer from lane hint if parent unknown
            lane = (parent_lane or skin.lane or "").upper()
            shelf = SHELF_COUNTDOWN if lane == LANE_COUNTDOWN else SHELF_UPPER_MONEY
            reason = f"follow_parent_missing→{shelf}"
        else:
            reason = f"follow_parent:{shelf}"
        lane = parent_lane or skin.lane
        if shelf == SHELF_COUNTDOWN:
            lane = LANE_COUNTDOWN
        elif shelf in {SHELF_PENTHOUSE_MONEY, SHELF_UPPER_MONEY, SHELF_GALE}:
            lane = lane or LANE_MONEY
        return ShelfDecision(
            shelf_id=shelf,
            family_id=fid,
            role=skin.role,
            kind=skin.kind,
            lane=lane,
            peer=_peer_for_shelf(shelf),
            follow_parent=True,
            band_hint=_band_hint(shelf),
            reason=reason,
            skin=skin,
        )

    shelf = shelf_for_family(fid)
    lane = skin.lane
    if shelf == SHELF_COUNTDOWN:
        lane = LANE_COUNTDOWN
    elif shelf in {SHELF_PENTHOUSE_MONEY, SHELF_UPPER_MONEY}:
        lane = LANE_MONEY
    elif shelf == SHELF_SNIPER and not lane:
        lane = LANE_COUNTDOWN

    return ShelfDecision(
        shelf_id=shelf,
        family_id=fid,
        role=skin.role,
        kind=skin.kind,
        lane=lane,
        peer=_peer_for_shelf(shelf),
        follow_parent=False,
        band_hint=_band_hint(shelf),
        reason=f"family→{shelf}",
        skin=skin,
    )


def shelf_catalog() -> Tuple[Dict[str, Any], ...]:
    """Human/AI readable shelf definitions for docs + Replit."""
    return (
        {
            "shelf_id": SHELF_PENTHOUSE_MONEY,
            "band": "PENTHOUSE",
            "purpose": "SOLO ELITE ENTER / APOSTAR — max volume+WR money",
            "includes": ["FIRE_SOLO_ELITE_ENTER", "FIRE_SOLO_APOSTAR"],
            "default_peer_env": "TELEGRAM_SHELF_PENTHOUSE → TELEGRAM_TARGET_PEER",
        },
        {
            "shelf_id": SHELF_UPPER_MONEY,
            "band": "UPPER",
            "purpose": "GOLDEN / SEQUENCE / PLATINUM ENTER NOW (+ compact #)",
            "includes": [
                "FIRE_GOLDEN_ENTER",
                "FIRE_SEQUENCE_ENTER",
                "FIRE_PLATINUM_ENTER",
                "FIRE_COMPACT_HASH",
            ],
            "default_peer_env": "TELEGRAM_SHELF_UPPER → TELEGRAM_TARGET_PEER",
        },
        {
            "shelf_id": SHELF_COUNTDOWN,
            "band": "UPPER_COUNTDOWN",
            "purpose": "Best countdown fires — Sinal Retido, JANELA any-N, CD_FIRE_*",
            "includes": [
                "FIRE_SINAL_RETIDO_LIBERADO",
                "FIRE_JANELA_TIMED",
                "CD_FIRE_TIMER_BRT_EDT_APOSTAR",
                "CD_FIRE_QUANTUM_LOCK",
            ],
            "default_peer_env": "TELEGRAM_SHELF_COUNTDOWN → TELEGRAM_COUNTDOWN_PEER (@UNIQUE_g1)",
            "note": "Historically elite; many systems never reach Telegram — still a floor",
        },
        {
            "shelf_id": SHELF_SNIPER,
            "band": "MID_SNIPER",
            "purpose": "FLASH / ULTRA_TIE / EMERGING / EMPATE DIRETO — thin n, high WR",
            "includes": ["FIRE_FLASH_APOSTAR", "FIRE_ULTRA_TIE", "SIGNAL_KIND_EMERGING"],
            "default_peer_env": "TELEGRAM_SHELF_SNIPER",
        },
        {
            "shelf_id": SHELF_GALE,
            "band": "MID_GALE",
            "purpose": "Gale retentativa / entre novamente / PREPARE G1",
            "includes": ["FIRE_GALE_RETENTATIVA", "FIRE_GALE_ENTRE_NOVAMENTE"],
            "default_peer_env": "TELEGRAM_SHELF_GALE → parent money by default",
        },
        {
            "shelf_id": SHELF_OPS_EXPIRE,
            "band": "OPS",
            "purpose": "G1 EXPIROU / G2 MISS — follow parent shelf when possible",
            "includes": ["OPS_G1_EXPIROU", "OPS_G2_MISS"],
            "default_peer_env": "parent shelf",
        },
        {
            "shelf_id": SHELF_OVERFLOW,
            "band": "OVERFLOW",
            "purpose": "Elastic extra chats when shelf > ~2–3/min — never drop",
            "includes": ["*rate overflow*"],
            "default_peer_env": "TELEGRAM_SHELF_OVERFLOW",
        },
        {
            "shelf_id": SHELF_VAULT,
            "band": "CREATED_ONLY",
            "purpose": "Built templates not yet observed live — keep, do not delete",
            "includes": ["FIRE_EMERGING", "CREATED_ONLY census rows"],
            "default_peer_env": "(no live peer until revived)",
        },
        {
            "shelf_id": SHELF_SINK,
            "band": "NOISE",
            "purpose": "Room relay / quarantine / gate dumps — never mix into money",
            "includes": ["ROOM_RELAY", "OPS_ROOM_QUARANTINE"],
            "default_peer_env": "TELEGRAM_SHELF_SINK or suppress",
        },
    )
