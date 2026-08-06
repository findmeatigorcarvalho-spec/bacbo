"""One AI Organizer — every valuable signal → perfect bundle placement.

Ambition: get as much / make the Most of literally everything.

Model (locked):
  ONE brain sees every KEEP signal (or anything that can become value).
  It organizes, mixes, merges, uses, and distributes across the bundle
  the way only the organizer knows — by what each chat BECOMES:

    UNIQUE_g1  APEX        — primary ENTER + clocks + gale home
    UNIQUE_g2  PRECISION   — sniper / FLASH / high-assertiveness
    UNIQUE_g3  VOLUME      — dense overflow / throughput
    UNIQUE_g4  ASSERTIVE   — gale / recovery stated
    UNIQUE_g5  IMPACT      — RESULT comprovation / heavy ops
    UNIQUE_g6+ ELASTIC     — mint under pressure; never delay

RESULT law (locked):
  Every RESULT attaches immediately under its own FIRE — bottom of that
  signal's chat — with zero intentional delay. No interval hold for glue.

Env:
  BUNDLE_ORGANIZER=1              (default on)
  RESULT_ATTACH_IMMEDIATE=1       (default on — zero delay RESULT glue)
"""
from __future__ import annotations

import os
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from bot.config.profit_chat_bundle import (
    BUNDLE,
    is_excluded,
    overflow_bundle_peers,
    peer_for_signal,
    primary_peer,
)


def organizer_enabled() -> bool:
    return os.environ.get("BUNDLE_ORGANIZER", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def result_attach_immediate() -> bool:
    """RESULT must land under its FIRE now — no intentional delay."""
    return os.environ.get("RESULT_ATTACH_IMMEDIATE", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


@dataclass
class OrganizeDecision:
    peer: str
    becomes: str
    why: str
    value: str
    is_result: bool = False
    glue_parent: bool = False
    delayed_seconds: float = 0.0
    dimensions_used: List[str] = field(default_factory=list)
    mix: List[str] = field(default_factory=list)
    score_by_peer: Dict[str, float] = field(default_factory=dict)
    never_delay: bool = True

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


# Dimension weights — tactical certainty for "most of everything"
_DIM_WEIGHT = {
    "Profit": 1.4,
    "Volume": 1.1,
    "WR": 1.3,
    "Precision": 1.25,
    "Assertiveness": 1.2,
    "Existence": 1.0,
    "Essence": 1.15,
    "Impact": 1.2,
    "Results": 1.35,
}


def _body_flags(text: str, kind: str, fam: str, role: str) -> Dict[str, bool]:
    u = f"{text}\n{kind}\n{fam}\n{role}".upper()
    return {
        "enter": bool(
            re.search(
                r"ENTER\s+NOW|APOSTE\s+AGORA|ENTRE\s+AGORA|APOSTAR\s+AGORA|"
                r"GOLDEN|SOLO|SEQUENCE|PLATINUM|CONFIRMED",
                u,
                re.I,
            )
            or role.upper() == "FIRE"
        ),
        "timed": bool(
            re.search(r"JANELA|SINAL\s+RETIDO|🟢\s*\d+\s*S|CD_FIRE|COUNTDOWN", u, re.I)
        ),
        "precision": bool(
            re.search(
                r"FLASH|ULTRA[_\s]?TIE|EMPATE\s+DIRETO|DEPTH_G0|CERTIFIED|SNIPER",
                u,
                re.I,
            )
        ),
        "gale": bool(
            re.search(
                r"GALE|RETENTATIVA|ENTRE\s+NOVAMENTE|PREPARE[_\s]?G1|AGUARDANDO\s+G",
                u,
                re.I,
            )
        ),
        "result": bool(
            role.upper() == "RESULT"
            or re.search(
                r"\b(WIN|LOSS|GANHOU|PERDEU|GREEN|DERROTA|VIT[ÓO]RIA|"
                r"RESUMIDO\s+FORENSE|G0\s+WIN|G1\s+WIN|G2\s+WIN)\b",
                u,
                re.I,
            )
        ),
        "impact_ops": bool(
            re.search(r"RESUMIDO\s+FORENSE|DELIVERY\s+AUDIT|GATE\s*\[|EXPIROU|G2\s+MISS", u, re.I)
        ),
        "warn": bool(
            re.search(r"DO\s+NOT\s+BET|N[ÃA]O\s+APOSTE|RODADA\s+J[ÁA]\s+PASSOU|COLD", u, re.I)
        ),
    }


def _value_of(flags: Dict[str, bool], text: str) -> str:
    if flags["result"]:
        return "RESULT_COMPROVATION — closes the stated subject"
    if flags["warn"]:
        return "PROTECTION — bankroll save (stated warning)"
    if flags["gale"]:
        return "RECOVERY — second chance stated, same color"
    if flags["timed"] and flags["precision"]:
        return "TIMED_PRECISION — high-assertiveness window"
    if flags["timed"]:
        return "TIMED_WINDOW — bet before 0"
    if flags["precision"]:
        return "PRECISION_EDGE — clean high-conviction ENTER"
    if flags["enter"]:
        return "ENTER_WINDOW — primary actionable chance"
    if flags["impact_ops"]:
        return "OPS_TRUTH — readable proof / audit"
    if (text or "").strip():
        return "FRAGMENT_VALUE — keep if usable; organizer places it"
    return "EMPTY"


def _score_peers(flags: Dict[str, bool]) -> Dict[str, float]:
    """Score each bundle identity for this situation (mix allowed)."""
    scores: Dict[str, float] = {c.peer: 0.0 for c in BUNDLE}
    # Base: APEX always competitive for existence
    scores["UNIQUE_g1"] += 2.0 * _DIM_WEIGHT["Existence"]

    if flags["enter"]:
        scores["UNIQUE_g1"] += 3.0 * _DIM_WEIGHT["Profit"]
        scores["UNIQUE_g1"] += 2.0 * _DIM_WEIGHT["Assertiveness"]
        scores["UNIQUE_g3"] += 1.5 * _DIM_WEIGHT["Volume"]

    if flags["timed"]:
        scores["UNIQUE_g1"] += 3.5 * _DIM_WEIGHT["Precision"]
        scores["UNIQUE_g1"] += 2.0 * _DIM_WEIGHT["Existence"]

    if flags["precision"]:
        scores["UNIQUE_g2"] += 4.0 * _DIM_WEIGHT["Precision"]
        scores["UNIQUE_g2"] += 2.5 * _DIM_WEIGHT["WR"]
        scores["UNIQUE_g2"] += 2.0 * _DIM_WEIGHT["Assertiveness"]
        # Mix: timed precision still prefers APEX so human hits the window
        if flags["timed"]:
            scores["UNIQUE_g1"] += 2.5 * _DIM_WEIGHT["Precision"]

    if flags["gale"]:
        scores["UNIQUE_g1"] += 2.5 * _DIM_WEIGHT["Profit"]
        scores["UNIQUE_g4"] += 3.5 * _DIM_WEIGHT["Assertiveness"]
        scores["UNIQUE_g4"] += 2.0 * _DIM_WEIGHT["WR"]

    if flags["result"]:
        scores["UNIQUE_g1"] += 1.0  # fallback only if no parent
        scores["UNIQUE_g5"] += 3.0 * _DIM_WEIGHT["Results"]
        scores["UNIQUE_g5"] += 2.0 * _DIM_WEIGHT["Impact"]

    if flags["impact_ops"] and not flags["result"]:
        scores["UNIQUE_g5"] += 3.0 * _DIM_WEIGHT["Impact"]
        scores["UNIQUE_g1"] += 1.0 * _DIM_WEIGHT["Essence"]

    if flags["warn"]:
        scores["UNIQUE_g1"] += 2.0 * _DIM_WEIGHT["Impact"]
        scores["UNIQUE_g5"] += 1.5 * _DIM_WEIGHT["Impact"]

    # Volume chat earns when APEX would otherwise be the only home
    if flags["enter"] and not flags["timed"] and not flags["precision"]:
        scores["UNIQUE_g3"] += 1.0 * _DIM_WEIGHT["Volume"]

    return scores


def _becomes_for(peer: str) -> str:
    for c in BUNDLE:
        if c.peer.lower() == peer.lower():
            return c.becomes
    m = re.match(r"^UNIQUE_g(\d+)$", peer, re.I)
    if m and int(m.group(1)) >= 6:
        return "ELASTIC"
    return "APEX"


def _mix_notes(flags: Dict[str, bool], peer: str, becomes: str) -> List[str]:
    notes: List[str] = []
    if flags["timed"] and flags["precision"] and becomes == "APEX":
        notes.append("mix:PRECISION+EXISTENCE→APEX (window > neatness)")
    if flags["gale"] and becomes == "APEX":
        notes.append("mix:ASSERTIVE home on APEX first; g4 absorbs spill")
    if flags["enter"] and becomes == "VOLUME":
        notes.append("mix:VOLUME absorbs ENTER when APEX soft-capped")
    if flags["result"]:
        notes.append("mix:RESULT always parent-first; IMPACT is identity not reroute")
    if becomes == "ELASTIC":
        notes.append("mix:ELASTIC minted — never delay the window")
    if not notes:
        notes.append(f"pure:{becomes}@{peer}")
    return notes


def organize(
    text: Optional[str] = None,
    *,
    signal_kind: Optional[str] = None,
    family_id: Optional[str] = None,
    role: Optional[str] = None,
    parent_peer: Optional[str] = None,
    signal_id: Optional[str] = None,
    is_result: bool = False,
    load_hints: Optional[Dict[str, float]] = None,
) -> OrganizeDecision:
    """Organize one signal into the bundle. Never Mr_iv4. Never delay RESULT."""
    body = text or ""
    kind = signal_kind or ""
    fam = family_id or ""
    role_u = (role or "").upper()
    flags = _body_flags(body, kind, fam, role_u)
    if is_result:
        flags["result"] = True
    value = _value_of(flags, body)

    # ── RESULT: attach under parent FIRE immediately ───────────────────────
    if flags["result"]:
        peer = ""
        if parent_peer and not is_excluded(parent_peer):
            peer = parent_peer.lstrip("@")
            why = f"result_attach_immediate→parent:{peer}"
        else:
            # Fail-open to last heuristic / APEX — still immediate
            peer, base_why = peer_for_signal(
                body, signal_kind=kind, family_id=fam, role="RESULT", is_result=True
            )
            why = f"result_attach_immediate→{base_why}"
        becomes = _becomes_for(peer)
        return OrganizeDecision(
            peer=peer or primary_peer(),
            becomes=becomes,
            why=why,
            value=value,
            is_result=True,
            glue_parent=bool(parent_peer),
            delayed_seconds=0.0,
            dimensions_used=["Results", "Impact", "Essence"],
            mix=_mix_notes(flags, peer or primary_peer(), becomes),
            never_delay=True,
        )

    if not organizer_enabled():
        peer, why = peer_for_signal(
            body, signal_kind=kind, family_id=fam, role=role_u or None
        )
        return OrganizeDecision(
            peer=peer,
            becomes=_becomes_for(peer),
            why=f"organizer_off:{why}",
            value=value,
            delayed_seconds=0.0,
            dimensions_used=["Existence"],
            mix=["organizer_disabled→bundle_heuristic"],
        )

    scores = _score_peers(flags)
    # Soft load preference: prefer less-loaded peers among close scores
    if load_hints:
        for peer, load in load_hints.items():
            if peer in scores:
                scores[peer] -= float(load) * 0.35

    # Pick best; never excluded
    ranked = sorted(
        ((p, s) for p, s in scores.items() if not is_excluded(p)),
        key=lambda x: (-x[1], 0 if x[0] == "UNIQUE_g1" else 1, x[0]),
    )
    if not ranked:
        peer = primary_peer()
        best_score = 0.0
    else:
        peer, best_score = ranked[0]

    # Gale: prefer APEX unless ASSERTIVE clearly wins by margin
    if flags["gale"] and peer == "UNIQUE_g4":
        apex_s = scores.get("UNIQUE_g1", 0)
        if best_score - apex_s < 1.5:
            peer = primary_peer()

    # Precision untuned (no timer) → g2; timed precision → APEX already scored
    becomes = _becomes_for(peer)
    dims = [d for d, w in _DIM_WEIGHT.items() if w >= 1.2]
    if flags["precision"]:
        dims = ["Precision", "WR", "Assertiveness"] + dims
    if flags["timed"]:
        dims = ["Precision", "Existence", "Profit"] + dims

    why = (
        f"organize→{becomes}@{peer} score={best_score:.2f} "
        f"sid={signal_id or '-'} value={value.split('—')[0].strip()}"
    )
    return OrganizeDecision(
        peer=peer,
        becomes=becomes,
        why=why,
        value=value,
        is_result=False,
        glue_parent=False,
        delayed_seconds=0.0,
        dimensions_used=list(dict.fromkeys(dims))[:6],
        mix=_mix_notes(flags, peer, becomes),
        score_by_peer={p: round(s, 3) for p, s in ranked[:6]},
        never_delay=True,
    )


def organize_spill_order(preferred: str) -> List[str]:
    """After preferred chat is soft-capped: remaining bundle then elastic."""
    pref = (preferred or primary_peer()).lstrip("@")
    order = [pref]
    for p in overflow_bundle_peers():
        if p not in order and not is_excluded(p):
            order.append(p)
    # Ensure all identity peers appear once
    for c in BUNDLE:
        if c.peer not in order and not is_excluded(c.peer):
            order.append(c.peer)
    return order


def organizer_manifest() -> Dict[str, Any]:
    return {
        "model": "ONE_AI_ORGANIZER",
        "ambition": "get as much / make the Most of literally everything",
        "law": (
            "Every valuable signal is seen. The organizer distributes across the "
            "bundle by what each chat BECOMES — mixing/merging/using as needed."
        ),
        "result_law": (
            "RESULT attaches immediately under its own FIRE — zero intentional delay."
        ),
        "enabled": organizer_enabled(),
        "result_attach_immediate": result_attach_immediate(),
        "bundle": [(c.peer, c.becomes) for c in BUNDLE],
        "excluded": ["Mr_iv4", "6774605259"],
        "reality": "Make It Real / It Is Real, Really. It Is Real truthfully.",
    }
