#!/usr/bin/env python3
"""Factual card contract — REAL FACT of what to bet + warning + RESULT comprovation.

Every FIRE path must carry:
  1) REAL FACTUAL fact of what to bet on (color / act)
  2) Statement of warning of actual factual outcoming / result
  3) Later: THAT RESULT / THE RESULT — comprovation (WIN/LOSS/TIE closes the subject)

Ambition companion: get it all — always the most of all — truthfully resourceful.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Tuple


_BET_COLOR = re.compile(
    r"(🔴|🔵|🟡|\bRED\b|\bBLUE\b|\bTIE\b|\bVERMELHO\b|\bAZUL\b|\bEMPATE\b|"
    r"Player|Banker)",
    re.I,
)
_BET_ACT = re.compile(
    r"ENTER\s+NOW|APOSTE\s+AGORA|ENTRE\s+AGORA|APOSTAR\s+AGORA|"
    r"JANELA\s*[:=]|🟢\s*\d+\s*s|RETENTATIVA|Entre\s+novamente",
    re.I,
)
_WARNING = re.compile(
    r"DO\s+NOT\s+BET|N[AÃ]O\s+APOSTE|RODADA\s+J[AÁ]\s+PASSOU|JANELA\s+FECHADA|"
    r"EXPIROU|G2\s+MISS|PERDA\s+TOTAL|AGUARDE|jogue\s+com\s+cautela|"
    r"Cool-?Down|quarantine|SALA\s+EM\s+QUEDA|SEQU[EÊ]NCIA\s+FRIA|"
    r"risco|risk|WARNING|AVISO|⚠",
    re.I,
)
_RESULT_COMPROVATION = re.compile(
    r"\bWIN\b|\bLOSS\b|GANHOU|PERDEU|GREEN|G0\s*WIN|G1\s*WIN|G2\s*WIN|"
    r"RESUMIDO\s+FORENSE|TRUTH\s+THIS\s+ROUND|✅|❌|"
    r"comprov|confirmad|RESULTADO|outcome",
    re.I,
)


@dataclass
class ContractCheck:
    has_bet_fact: bool
    bet_subject: str
    has_warning: bool
    warning_subject: str
    has_result_comprovation: bool
    result_subject: str
    role_guess: str  # FIRE | RESULT | WARN | MIXED | UNKNOWN
    ok_for_fire: bool
    ok_for_result: bool
    gaps: List[str]
    stated_subject_of_matter: str

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _first_match(rx: re.Pattern, text: str) -> str:
    m = rx.search(text or "")
    return (m.group(0) if m else "").strip()


def check_card(text: str) -> ContractCheck:
    body = text or ""
    bet_c = _first_match(_BET_COLOR, body)
    bet_a = bool(_BET_ACT.search(body))
    has_bet = bool(bet_c) and bet_a
    warn = bool(_WARNING.search(body))
    warn_s = _first_match(_WARNING, body)
    res = bool(_RESULT_COMPROVATION.search(body))
    res_s = _first_match(_RESULT_COMPROVATION, body)

    if has_bet and not res:
        role = "FIRE"
    elif res and not bet_a:
        role = "RESULT"
    elif warn and not has_bet and not res:
        role = "WARN"
    elif has_bet and res:
        role = "MIXED"
    else:
        role = "UNKNOWN"

    gaps: List[str] = []
    if role == "FIRE":
        if not bet_c:
            gaps.append("missing_REAL_FACTUAL_bet_color")
        if not bet_a:
            gaps.append("missing_bet_act_ENTER_or_JANELA")
        # Warning may be on companion OPS card; soft gap if none in same body
        if not warn:
            gaps.append("no_inline_warning_of_factual_outcoming")
    if role == "RESULT":
        if not res:
            gaps.append("missing_RESULT_comprovation")
    if role == "UNKNOWN":
        gaps.append("no_clear_bet_fact_or_result_comprovation")

    subject = ""
    if has_bet:
        subject = f"BET → {bet_c or '?'} ({_first_match(_BET_ACT, body) or 'ENTER'})"
    if warn:
        subject = (subject + " | " if subject else "") + f"WARN → {warn_s}"
    if res:
        subject = (subject + " | " if subject else "") + f"RESULT comprovation → {res_s}"

    ok_fire = has_bet and bool(bet_c)
    ok_result = res

    return ContractCheck(
        has_bet_fact=has_bet,
        bet_subject=f"{bet_c}|{_first_match(_BET_ACT, body)}" if has_bet else "",
        has_warning=warn,
        warning_subject=warn_s,
        has_result_comprovation=res,
        result_subject=res_s,
        role_guess=role,
        ok_for_fire=ok_fire,
        ok_for_result=ok_result,
        gaps=gaps,
        stated_subject_of_matter=subject or "(none)",
    )


def contract_rules() -> Dict[str, str]:
    return {
        "bet_fact": (
            "REAL FACTUAL fact of what to bet on — color + act (ENTER/JANELA/GALE)."
        ),
        "outcome_warning": (
            "Statement of warning of actual factual outcoming / result "
            "(DO NOT BET, expire, cold, risk) when that is the subject."
        ),
        "result_comprovation": (
            "THAT RESULT / THE RESULT — comprovation (WIN/LOSS/TIE/forensic) "
            "closes the stated subject of the matter."
        ),
        "get_it_all": (
            "Always get the most of all. Always truthfully resourceful — "
            "even when disempowered, extract the maximum honest capture."
        ),
    }


def human_line(check: ContractCheck) -> str:
    if check.ok_for_fire and check.role_guess == "FIRE":
        base = f"BET FACT: {check.bet_subject}."
        if check.has_warning:
            base += f" WARN: {check.warning_subject}."
        return base + " Wait for RESULT comprovation."
    if check.ok_for_result:
        return f"RESULT comprovation: {check.result_subject}. Round subject closed."
    if check.role_guess == "WARN":
        return f"WARNING (factual outcoming): {check.warning_subject}. Do not invent a bet."
    return "Card incomplete vs contract: " + ", ".join(check.gaps or ["unknown"])
