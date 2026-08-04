"""Telegram card skin families → stable gate keys.

Source of truth chronology: replit_elite_stack_patch/TELEGRAM_CARD_ERAS.md
(Mar 17 → Aug 3 2026 archaeology).

Rules locked by archaeology:
- Gate on Telegram *skin families*, not only DB signal_kind.
- ♻️ GALE N — RETENTATIVA  ≠  🔁 GALE N — Entre novamente
- 🟡 EMPATE — SOLO_ELITE stays kind-scoped (RESULT_EMPATE:SOLO_ELITE)
- JANELA / ~Ns window are variable-N families (any seconds), not fixed 1/11/17
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple


ROLE_ONLINE = "ONLINE"
ROLE_FIRE = "FIRE"
ROLE_RESULT = "RESULT"
ROLE_OPS = "OPS"
ROLE_ROOM_RELAY = "ROOM_RELAY"
ROLE_UNKNOWN = "UNKNOWN"
ROLE_EMPTY = "EMPTY"

LANE_MONEY = "MONEY"
LANE_COUNTDOWN = "COUNTDOWN"

# Kind tokens that appear on FIRE/RESULT skins (DB signal_kind bridge).
_KIND_PATTERNS: Tuple[Tuple[str, str], ...] = (
    (r"SOLO[_\s]?ELITE", "SOLO_ELITE"),
    (r"\bGOLDEN\b", "GOLDEN"),
    (r"\bSEQUENCE\b", "SEQUENCE"),
    (r"SEQU[EÊ]NCIA", "SEQUENCE"),
    (r"\bPLATINUM\b", "PLATINUM"),
    (r"\bFLASH\b", "FLASH"),
    (r"ULTRA[_\s]?TIE", "ULTRA_TIE"),
    (r"EMERGIN[DG]O?|\bEMERGING\b", "EMERGING"),
)


@dataclass(frozen=True)
class SkinFamily:
    """Canonical skin family registered for engine gating."""

    family_id: str
    role: str
    era: str
    label: str
    example_first_line: str
    default_lane: Optional[str] = None
    kind_scoped: bool = False
    variable_n: bool = False
    notes: str = ""


@dataclass(frozen=True)
class SkinMatch:
    family_id: str
    role: str
    kind: Optional[str]
    lane: Optional[str]
    clock_n: Optional[int]
    gate_keys: Tuple[str, ...]
    first_line: str
    era: Optional[str]
    label: str
    notes: str = ""

    def as_dict(self) -> Dict[str, Any]:
        return {
            "family_id": self.family_id,
            "role": self.role,
            "kind": self.kind,
            "lane": self.lane,
            "clock_n": self.clock_n,
            "gate_keys": list(self.gate_keys),
            "first_line": self.first_line,
            "era": self.era,
            "label": self.label,
            "notes": self.notes,
        }


# Chronological catalog (stable IDs). Order here is documentation order, not
# classifier precedence — see classify_telegram_skin() for match order.
SKIN_FAMILIES: Tuple[SkinFamily, ...] = (
    # Era 0
    SkinFamily(
        "ONLINE_BANNER",
        ROLE_ONLINE,
        "0",
        "ONLINE banner",
        "🟢 BacBo Royal UserBot ONLINE 🟢",
    ),
    # Era 1
    SkinFamily(
        "FIRE_CONFIRMED_ENTER",
        ROLE_FIRE,
        "1",
        "FIRE confirmed ENTER NOW",
        "🏆 SIGNAL CONFIRMED — ENTER NOW 🏆",
        LANE_MONEY,
    ),
    SkinFamily(
        "FIRE_SOLO_ELITE_ENTER",
        ROLE_FIRE,
        "1",
        "FIRE SOLO ELITE",
        "💎 SOLO ELITE SIGNAL 💎",
        LANE_MONEY,
    ),
    SkinFamily(
        "FIRE_GOLDEN_ENTER",
        ROLE_FIRE,
        "1",
        "FIRE GOLDEN ENTER NOW",
        "🏆 GOLDEN SIGNAL — ENTER NOW 🏆",
        LANE_MONEY,
    ),
    SkinFamily(
        "FIRE_SEQUENCE_ENTER",
        ROLE_FIRE,
        "1",
        "FIRE SEQUENCE ENTER NOW",
        "📊 SEQUENCE SIGNAL — ENTER NOW 📊",
        LANE_MONEY,
    ),
    SkinFamily(
        "FIRE_PLATINUM_ENTER",
        ROLE_FIRE,
        "1",
        "FIRE PLATINUM",
        "💠 PLATINUM SIGNAL — PAR DE OURO",
        LANE_MONEY,
    ),
    # Era 1b
    SkinFamily(
        "RESULT_AUTO_TIE",
        ROLE_RESULT,
        "1b",
        "RESULT AUTO TIE banner",
        "⚪ AUTO TIE @…",
    ),
    SkinFamily(
        "RESULT_WIN_TIER",
        ROLE_RESULT,
        "1b",
        "RESULT WIN — kind",
        "✅ WIN — SOLO_ELITE",
        kind_scoped=True,
    ),
    SkinFamily(
        "RESULT_LOSS_TIER",
        ROLE_RESULT,
        "1b",
        "RESULT LOSS — kind",
        "❌ LOSS — GOLDEN",
        kind_scoped=True,
    ),
    SkinFamily(
        "FIRE_GALE_ENTRE_NOVAMENTE",
        ROLE_FIRE,
        "1b",
        "FIRE gale Entre novamente",
        "🔁 GALE 1 — Entre novamente",
        LANE_MONEY,
        kind_scoped=True,
        notes="Distinct from FIRE_GALE_RETENTATIVA",
    ),
    SkinFamily(
        "RESULT_EMPATE",
        ROLE_RESULT,
        "1b",
        "RESULT EMPATE — kind",
        "🟡 EMPATE — SOLO_ELITE",
        kind_scoped=True,
        notes="Keep RESULT_EMPATE:SOLO_ELITE distinct",
    ),
    SkinFamily(
        "FIRE_GALE_RETENTATIVA",
        ROLE_FIRE,
        "1b",
        "FIRE gale RETENTATIVA",
        "♻️ GALE 1 — RETENTATIVA",
        LANE_MONEY,
        kind_scoped=True,
        notes="Distinct from FIRE_GALE_ENTRE_NOVAMENTE",
    ),
    SkinFamily(
        "RESULT_GREEN_LEGACY_G0",
        ROLE_RESULT,
        "1b",
        "RESULT GREEN legacy G0",
        "✅✅✅ GREEN — VITÓRIA NO G0!",
    ),
    SkinFamily(
        "RESULT_GREEN_LEGACY_G1",
        ROLE_RESULT,
        "1b",
        "RESULT GREEN legacy G1",
        "♻️♻️♻️ GREEN — RECUPERADO NO G1!",
    ),
    # Era 2
    SkinFamily(
        "OPS_LOSS_COOLDOWN",
        ROLE_OPS,
        "2",
        "OPS loss cooldown",
        "⚠️ LOSS COOLDOWN ACTIVATED",
    ),
    SkinFamily(
        "OPS_PREALERT_FORMING",
        ROLE_OPS,
        "2",
        "PREALERT forming",
        "⚡ SINAL SE FORMANDO ⚡",
    ),
    SkinFamily(
        "OPS_DUPLO_ELITE",
        ROLE_OPS,
        "2",
        "OPS duplo elite",
        "🔮 DUPLO ELITE ANALISANDO",
    ),
    SkinFamily(
        "FIRE_JANELA_TIMED",
        ROLE_FIRE,
        "2",
        "TIMED JANELA (any N)",
        "⛔ JANELA FECHADA — NÃO ENTRE… / JANELA: Ns",
        LANE_COUNTDOWN,
        kind_scoped=True,
        variable_n=True,
        notes="Variable-N family — do not split per seconds",
    ),
    SkinFamily(
        "FIRE_ULTRA_TIE",
        ROLE_FIRE,
        "2",
        "FIRE ULTRA TIE",
        "🟡 ULTRA TIE — EMPATE CONFIRMADO",
        LANE_MONEY,
    ),
    SkinFamily(
        "OPS_TRIPLE_LOCK",
        ROLE_OPS,
        "2",
        "OPS triple lock",
        "🔐🔐🔐 TRIPLE LOCK CHEGANDO",
    ),
    # Era 3
    SkinFamily(
        "OPS_SEQ_QUENTE",
        ROLE_OPS,
        "3",
        "OPS sequência quente",
        "🔥🔥🔥 SEQUÊNCIA QUENTE",
    ),
    SkinFamily(
        "OPS_SEQ_FRIA",
        ROLE_OPS,
        "3",
        "OPS sequência fria",
        "🧊🧊🧊 SEQUÊNCIA FRIA — PAUSAR",
    ),
    SkinFamily(
        "OPS_SEQ_EMPATES",
        ROLE_OPS,
        "3",
        "OPS sequência empates",
        "🟡🟡🟡 SEQUÊNCIA DE EMPATES",
    ),
    SkinFamily(
        "RESULT_TIMED_WINDOW",
        ROLE_RESULT,
        "3",
        "RESULT timed ~Ns window",
        "🕐 HH:MM:SS EDT · … · ~Ns window",
        variable_n=True,
        notes="Clock C / resolve window reporting — variable N",
    ),
    SkinFamily(
        "OPS_PREALERT_3BOLT",
        ROLE_OPS,
        "3",
        "PREALERT 3-bolt",
        "⚡⚡⚡ SINAL FORMANDO",
    ),
    SkinFamily(
        "FIRE_EMPATE_DIRETO_G0",
        ROLE_FIRE,
        "3",
        "FIRE EMPATE DIRETO G0",
        "🎯🟡 EMPATE DIRETO — G0",
        LANE_MONEY,
    ),
    SkinFamily(
        "OPS_AUDIT_360",
        ROLE_OPS,
        "3",
        "OPS AUDIT 360",
        "📊 AUDIT 360° (DB only)",
    ),
    SkinFamily(
        "FIRE_G0_DIRETO",
        ROLE_FIRE,
        "3",
        "FIRE G0 DIRETO",
        "⚡ G0 DIRETO — Entre com confiança",
        LANE_MONEY,
    ),
    SkinFamily(
        "FIRE_PREPARE_G1",
        ROLE_FIRE,
        "3",
        "FIRE PREPARE G1",
        "♟ PREPARE O G1 — Provável…",
        LANE_MONEY,
    ),
    SkinFamily(
        "OPS_STREAK_BANNER",
        ROLE_OPS,
        "3",
        "STREAK banner",
        "🎰 SEQUÊNCIA Nx 🔴 VERMELHO",
    ),
    SkinFamily(
        "OPS_CAMADAS_DO_DIA",
        ROLE_OPS,
        "3",
        "CAMADAS DO DIA",
        "🏆 CAMADAS DO DIA — DD/MM/YYYY",
    ),
    # Era 4
    SkinFamily(
        "RESULT_FLASH_WIN",
        ROLE_RESULT,
        "4",
        "RESULT FLASH WIN",
        "✅ WIN — FLASH",
        kind_scoped=True,
    ),
    SkinFamily(
        "RESULT_GREEN_COMPACT_G0",
        ROLE_RESULT,
        "4",
        "RESULT GREEN compact G0",
        "✅ GREEN · G0 · HH:MM BRT",
    ),
    SkinFamily(
        "RESULT_GREEN_COMPACT_G1",
        ROLE_RESULT,
        "4",
        "RESULT GREEN compact G1",
        "♻️ GREEN · G1 · HH:MM BRT",
    ),
    # Era 5
    SkinFamily(
        "FIRE_COMPACT_HASH",
        ROLE_FIRE,
        "5",
        "COMPACT SIGNAL #",
        "🔵 SIGNAL #51250 -- SOLO_ELITE red | rooms: @…",
        LANE_MONEY,
        kind_scoped=True,
    ),
    SkinFamily(
        "RESULT_COMPACT_LOSS_HASH",
        ROLE_RESULT,
        "5",
        "COMPACT LOSS #",
        "❌ LOSS #51250 G0",
    ),
    SkinFamily(
        "RESULT_COMPACT_WIN_HASH",
        ROLE_RESULT,
        "5",
        "COMPACT WIN #",
        "✅ WIN #51252 G0",
    ),
    SkinFamily(
        "RESULT_COMPACT_TIE_HASH",
        ROLE_RESULT,
        "5",
        "COMPACT TIE #",
        "➖ TIE #51257 G0",
    ),
    # Era 6
    SkinFamily(
        "FIRE_SOLO_APOSTAR",
        ROLE_FIRE,
        "6",
        "FIRE SOLO APOSTAR AGORA",
        "⚡ SOLO ELITE — APOSTAR AGORA",
        LANE_MONEY,
    ),
    SkinFamily(
        "FIRE_SEQUENCE_APOSTAR",
        ROLE_FIRE,
        "6",
        "FIRE SEQUENCE APOSTAR AGORA",
        "⚡ SEQUENCE — APOSTAR AGORA",
        LANE_MONEY,
    ),
    SkinFamily(
        "FIRE_GOLDEN_APOSTAR",
        ROLE_FIRE,
        "6",
        "FIRE GOLDEN APOSTAR AGORA",
        "⚡ GOLDEN — APOSTAR AGORA",
        LANE_MONEY,
    ),
    SkinFamily(
        "FIRE_PLATINUM_APOSTAR",
        ROLE_FIRE,
        "6",
        "FIRE PLATINUM APOSTAR AGORA",
        "⚡ PLATINUM — APOSTAR AGORA",
        LANE_MONEY,
    ),
    SkinFamily(
        "FIRE_FLASH_APOSTAR",
        ROLE_FIRE,
        "6",
        "FIRE FLASH APOSTAR AGORA",
        "⚡ FLASH — APOSTAR AGORA",
        LANE_MONEY,
    ),
    SkinFamily(
        "ONLINE_LUXURY_OUTBOX",
        ROLE_ONLINE,
        "6",
        "ONLINE luxury outbox",
        "LUXURY OUTBOX ONLINE",
    ),
    SkinFamily(
        "FIRE_SEQUENCIA_ENTER_NOW",
        ROLE_FIRE,
        "6",
        "FIRE SEQUência ENTER NOW",
        "🔥 SEQUência — ENTER NOW 🔥",
        LANE_MONEY,
    ),
    SkinFamily(
        "OPS_ELITE_ANALISANDO",
        ROLE_OPS,
        "6",
        "OPS ELITE ANALISANDO",
        "⚡ ELITE ANALISANDO",
    ),
    SkinFamily(
        "OPS_DIVERGENCIA_SALAS",
        ROLE_OPS,
        "6",
        "OPS divergência de salas",
        "🟠 DIVERGÊNCIA DE SALAS",
    ),
    # High-value templates often missing from DB signal_kind (must stay floors)
    SkinFamily(
        "FIRE_SINAL_RETIDO_LIBERADO",
        ROLE_FIRE,
        "cd",
        "FIRE Sinal Retido→Liberado (countdown peak)",
        "⏳ Sinal Retido → Liberado",
        LANE_COUNTDOWN,
        kind_scoped=True,
        variable_n=True,
        notes="Among best countdown fires — Camada/JANELA/🟢 Ns 🟢; not a DB kind",
    ),
    SkinFamily(
        "CD_FIRE_TIMER_BRT_EDT_APOSTAR",
        ROLE_FIRE,
        "cd",
        "CD_FIRE timer BRT/EDT apostar",
        "🟢 HH UTC · EDT · apostar",
        LANE_COUNTDOWN,
        variable_n=True,
        notes="Countdown signal-fire family — historically elite volume",
    ),
    SkinFamily(
        "CD_FIRE_QUANTUM_LOCK",
        ROLE_FIRE,
        "cd",
        "CD_FIRE quantum lock",
        "🔒 QUANTUM LOCK",
        LANE_COUNTDOWN,
    ),
    SkinFamily(
        "CD_FIRE_RUSH_NS_LEFT",
        ROLE_FIRE,
        "cd",
        "CD_FIRE rush Ns left",
        "RUSH · Ns left",
        LANE_COUNTDOWN,
        variable_n=True,
    ),
    SkinFamily(
        "RESULT_FORENSIC_INTERVALO",
        ROLE_RESULT,
        "forensic",
        "RESULT resumido forense (G0/G1/G2)",
        "🔍 SINAL #N — RESUMIDO FORENSE",
        kind_scoped=True,
        notes="G0 WIN / LOSS forensic with ⏱ Intervalo — Clock C reporting; glue under parent",
    ),
    SkinFamily(
        "RESULT_BELL_GANHOU",
        ROLE_RESULT,
        "forensic",
        "RESULT bell GANHOU/PERDEU",
        "🔔 ✅ GANHOU  ·  #N",
        kind_scoped=True,
        notes="Often paired with forensic block; G0/G1 outcome product card",
    ),
    SkinFamily(
        "OPS_G1_EXPIROU",
        ROLE_OPS,
        "ops_result",
        "OPS G1 EXPIROU — verificar mesa",
        "⏰ G1 EXPIROU — VERIFICAR SUA MESA",
        notes="Result-ops — follow parent fire chat; user must /win /loss /tie",
    ),
    SkinFamily(
        "OPS_G2_MISS",
        ROLE_OPS,
        "ops_result",
        "OPS G2 MISS — perda total",
        "🛑 G2 MISS — PERDA TOTAL — PARE AGORA",
        notes="Hard stop card — follow parent; never invent G3",
    ),
    # Archaeology gaps — high volume, previously classified UNKNOWN
    SkinFamily(
        "FIRE_GOD_TIER",
        ROLE_FIRE,
        "elite",
        "FIRE GOD-TIER sync/conf",
        "💎 GOD-TIER — Sync apertado + ≥3 salas top + conf≥75%",
        LANE_MONEY,
        notes="TG FIRE_GOD_TIER_SYNC_* — rare elite multi-room",
    ),
    SkinFamily(
        "FIRE_GOLDEN_ENTRE_AGORA",
        ROLE_FIRE,
        "1",
        "FIRE GOLDEN ENTRE AGORA (PT)",
        "🏆🏆🏆 GOLDEN SIGNAL — ENTRE AGORA 🏆🏆🏆",
        LANE_MONEY,
        notes="Portuguese ENTER NOW twin of FIRE_GOLDEN_ENTER; keep distinct skin",
    ),
    SkinFamily(
        "FIRE_G0_MISS_ENTRE_G1",
        ROLE_FIRE,
        "1b",
        "FIRE G0 miss → enter G1 now",
        "⚠️ G0 NÃO FOI — ENTRE NO G1 AGORA",
        LANE_MONEY,
        kind_scoped=True,
        variable_n=True,
        notes="Distinct from FIRE_PREPARE_G1 / gale retentativa",
    ),
    SkinFamily(
        "RESULT_ORACLE_CARD",
        ROLE_RESULT,
        "oracle",
        "RESULT ORACLE CARD",
        "🔮 ORACLE CARD #N",
        kind_scoped=True,
        notes="Floor camada + tier/kind + timing delay — glue under parent",
    ),
    SkinFamily(
        "OPS_TIE_ALERT",
        ROLE_OPS,
        "2",
        "OPS alerta de empate / tie alert",
        "🟡 ALERTA DE EMPATE / TIE ALERT 🟡",
        notes="High-volume tie pressure family (also EMPATE CRÍTICO / JANELA DE EMPATE)",
    ),
    SkinFamily(
        "OPS_CORRECAO",
        ROLE_OPS,
        "ops_result",
        "OPS correção / correction",
        "♻️♻️♻️ CORREÇÃO / CORRECTION ♻️♻️♻️",
    ),
    SkinFamily(
        "OPS_JANELA_PRIME",
        ROLE_OPS,
        "cd",
        "OPS janela prime — sinais ativos",
        "🟢🟢 JANELA PRIME — SINAIS ATIVOS 🟢🟢",
        notes="Countdown-adjacent ops banner",
    ),
    # ── Code-side card formatters (bacbo_royal_complete.py + _gates_*.py) ────
    SkinFamily(
        "FIRE_ENTER_NOW_GENERIC",
        ROLE_FIRE,
        "code",
        "FIRE plain ENTER NOW (gate-era)",
        "⚡ **ENTER NOW**",
        LANE_MONEY,
        kind_scoped=True,
        notes="Includes PATTERN CONFIRMED / HIGH-PERFORMANCE ROOM CONFIRMED variants",
    ),
    SkinFamily(
        "FIRE_ENTRE_AGORA_GENERIC",
        ROLE_FIRE,
        "code",
        "FIRE ENTRE AGORA (virada/streak)",
        "⚡ **ENTRE AGORA — VIRADA DETECTADA**",
        LANE_MONEY,
        kind_scoped=True,
    ),
    SkinFamily(
        "FIRE_APOSTE_AGORA",
        ROLE_FIRE,
        "code",
        "FIRE APOSTE AGORA block",
        "⚡ **APOSTE AGORA:**",
        LANE_MONEY,
        kind_scoped=True,
    ),
    SkinFamily(
        "FIRE_G0_ENTRADA_DIRETA",
        ROLE_FIRE,
        "code",
        "FIRE G0 entrada direta / primeira entrada",
        "⚡⚡⚡ **G0 — ENTRADA DIRETA** ⚡⚡⚡",
        LANE_MONEY,
        kind_scoped=True,
    ),
    SkinFamily(
        "FIRE_DEPTH_G0_ONLY",
        ROLE_FIRE,
        "code",
        "FIRE depth G0 only (no retry)",
        "⚡ DEPTH G0 only — single entry, no retry",
        LANE_MONEY,
        notes="No-gale depth variant — distinct from gale ladder fires",
    ),
    SkinFamily(
        "FIRE_INVERTED_CONTRARIO",
        ROLE_FIRE,
        "code",
        "FIRE inverted / contrário signal",
        "🔴 CONTRÁRIO ← sinal invertido ativo",
        LANE_MONEY,
        kind_scoped=True,
        notes="Signal-inversion mode — bet opposite of base prediction",
    ),
    SkinFamily(
        "FIRE_ORACLE_LOCK",
        ROLE_FIRE,
        "code",
        "FIRE ORACLE LOCK hour/color WR",
        "🔮🔮🔮 **ORACLE LOCK — H07 SOLO ELITE 100% WR** 🔮🔮🔮",
        LANE_MONEY,
        kind_scoped=True,
        notes="Hour+color hardcoded WR locks — heavy per-hour overfit family",
    ),
    SkinFamily(
        "FIRE_CERTIFIED_ELITE",
        ROLE_FIRE,
        "code",
        "FIRE certified elite 100% G0",
        "🏆🏆 **CERTIFIED ELITE — 100% G0 HISTÓRICO** 🏆🏆",
        LANE_MONEY,
        kind_scoped=True,
    ),
    SkinFamily(
        "FIRE_GRADE_BANNER",
        ROLE_FIRE,
        "code",
        "FIRE grade A/B historical G0 banner",
        "💠 GRADE A · G0=76.1% historical (n=46) · elite pair",
        LANE_MONEY,
        kind_scoped=True,
    ),
    SkinFamily(
        "FIRE_HOT_STREAK",
        ROLE_FIRE,
        "code",
        "FIRE hot table / win-streak banner",
        "🔥🔥 PERFECT 5/5 WIN STREAK · G0=87.1% historical",
        LANE_MONEY,
        kind_scoped=True,
    ),
    SkinFamily(
        "FIRE_DOUBLE_TIE_LOCK",
        ROLE_FIRE,
        "code",
        "FIRE double tie lock",
        "🟡🟡 DOUBLE TIE LOCK · G0=94.1% after 2 consecutive ties (n=17)",
        LANE_MONEY,
        notes="Tiny-n tie lock (n=17)",
    ),
    SkinFamily(
        "FIRE_GALE_1_FACA_AGORA",
        ROLE_FIRE,
        "code",
        "FIRE gale 1 — faça agora",
        "🔁 **GALE 1 — FAÇA AGORA:**",
        LANE_MONEY,
        kind_scoped=True,
        notes="ELITE_V2-era gale card; distinct from RETENTATIVA / Entre novamente",
    ),
    SkinFamily(
        "OPS_DO_NOT_BET_YET",
        ROLE_OPS,
        "code",
        "OPS do not bet yet — waiting rooms",
        "⛔ **DO NOT BET YET** — waiting for more rooms",
    ),
    SkinFamily(
        "OPS_PREPARE_PLATFORM",
        ROLE_OPS,
        "code",
        "OPS prepare platform — signal in seconds",
        "⏳ Prepare a plataforma — **o sinal de entrada chegará em segundos**",
    ),
    SkinFamily(
        "OPS_NEXT_CERTIFIED_WINDOW",
        ROLE_OPS,
        "code",
        "OPS next certified window",
        "🏆 **Próxima janela certificada / Next certified window:**",
    ),
    SkinFamily(
        "OPS_JANELA_PEAK",
        ROLE_OPS,
        "code",
        "OPS janela peak / max precision",
        "⚡⚡ **JANELA PEAK / PEAK WINDOW — PRECISÃO MÁXIMA** ⚡⚡",
    ),
    SkinFamily(
        "OPS_G1_REGISTRADO_CALC_G2",
        ROLE_OPS,
        "ops_result",
        "OPS G1 recorded — calculating G2",
        "📊 **G1 registrado / G1 recorded** — calculando G2...",
    ),
    SkinFamily(
        "OPS_G2_STOP_IF_G1_LOST",
        ROLE_OPS,
        "ops_result",
        "OPS G2 (if G1 lost) → STOP",
        "⛔ G2 _(se perder G1)_ → STOP — aguarde novo sinal",
    ),
    SkinFamily(
        "OPS_G3_ATINGIDO",
        ROLE_OPS,
        "ops_result",
        "OPS G3 reached — signal closed (MAR20/21 era)",
        "⛔ **G3 ATINGIDO — SINAL ENCERRADO**",
        notes="Historical: MAR20/MAR21 gates ran a 3-gale ladder. Later eras stop at G2.",
    ),
    SkinFamily(
        "RESULT_G0_ACERTOU_PRIMEIRA",
        ROLE_RESULT,
        "code",
        "RESULT G0 acertou de primeira",
        "🏆 G0 — Acertou de primeira!",
        kind_scoped=True,
    ),
    SkinFamily(
        "RESULT_GALE_RECOVERED_CHAIN",
        ROLE_RESULT,
        "code",
        "RESULT gale recovery chain",
        "❌ G0 → ✅ **G1** RECUPERADO / RECOVERED!",
        kind_scoped=True,
        notes="Chain form shows which gale leg recovered",
    ),
    SkinFamily(
        "RESULT_EMPATE_DINHEIRO_DEVOLVIDO",
        ROLE_RESULT,
        "code",
        "RESULT empate = dinheiro devolvido",
        "✅ **EMPATE = DINHEIRO DEVOLVIDO**",
    ),
    SkinFamily(
        "RESULT_EMPATE_PROTECAO",
        ROLE_RESULT,
        "code",
        "RESULT empate — proteção ativada",
        "🟡🟡 **EMPATE — PROTEÇÃO ATIVADA** 🟡🟡",
    ),
    SkinFamily(
        "CD_RES_GREEN_G_BRT",
        ROLE_RESULT,
        "cd",
        "CD result GREEN G BRT",
        "🟢 G0 · BRT",
        notes="Countdown-lane result skin",
    ),
    SkinFamily(
        "CD_RES_RODADAS_TEMPO",
        ROLE_RESULT,
        "cd",
        "CD result rodadas·tempo",
        "⏱ N rodada(s) · Ns",
    ),
    SkinFamily(
        "CD_RES_BELL_GANHOU",
        ROLE_RESULT,
        "cd",
        "CD result bell ganhou",
        "🔔 ✅ GANHOU",
        kind_scoped=True,
    ),
    # Noise / ops catch-alls (not product ENTER→RESULT, but gate-addressable)
    SkinFamily(
        "ROOM_RELAY",
        ROLE_ROOM_RELAY,
        "noise",
        "Room relay / placar",
        "📡 @room …",
        notes="High-volume noise class",
    ),
    SkinFamily(
        "OPS_GATE_BLOCK_LOG",
        ROLE_OPS,
        "internal",
        "Internal gate block / momentum log line",
        "⛔ MomentumBlock L-L-L: G0=34.4% historically —",
        notes="Console/log output from _gates_*.py — classified so census has no UNKNOWN bucket",
    ),
    SkinFamily(
        "OPS_GATE_ALLOW_LOG",
        ROLE_OPS,
        "internal",
        "Internal gate allow / bypass log line",
        "⚡ [accum_solo_gale/DISABLED] gate disabled → ALLOW",
        notes="Console/log output — never a Telegram card",
    ),
    SkinFamily(
        "OPS_KIND_DOWNGRADE_LOG",
        ROLE_OPS,
        "internal",
        "Internal tier downgrade log",
        "⛔ PLATINUM coalition unrescuable after stripping toxic rooms — downgrading to GOLDEN.",
    ),
    SkinFamily(
        "CODE_FRAGMENT",
        ROLE_UNKNOWN,
        "internal",
        "Source-code literal (not a card)",
        'GOLDEN", "SOLO_ELITE", "PLATINUM", "EMERGING"',
        notes="Kind lists / ternaries / bare labels mined from source; retained, never dropped",
    ),
    SkinFamily(
        "OPS_G2_ATINGIDO_PARE",
        ROLE_OPS,
        "ops_result",
        "OPS G2 atingido — pare / signal closed",
        "⛔ **PARE — G2 ATINGIDO**",
        notes="Portuguese twin of OPS_G2_MISS; JUN08/JUN09 + ELITE_V2 eras",
    ),
    SkinFamily(
        "FIRE_APOSTAR_EMPATE",
        ROLE_FIRE,
        "code",
        "FIRE bet the tie (next rounds)",
        "🎯 **Aposte no EMPATE (🟠 Tie)** nas próximas rodadas.",
        LANE_MONEY,
        notes="Tie-side entry card — distinct from ULTRA_TIE and tie-alert ops",
    ),
    SkinFamily(
        "FIRE_NAMED_EDGE_BANNER",
        ROLE_FIRE,
        "code",
        "FIRE named formation / zone edge banner",
        "🏆 APEX TRIO · isadados+rigosinais+rqdados · G0=90.3% (n=31)",
        LANE_MONEY,
        kind_scoped=True,
        notes="APEX TRIO / ZERO-LOSS ZONE / PRIME formations — small-n named edges",
    ),
    SkinFamily(
        "OPS_NEGATIVE_WINDOW_BLOCK",
        ROLE_OPS,
        "code",
        "OPS named bad day/hour block banner",
        "⛔ BLUE TUESDAY ⛔ · G0=36.5% historically (n=159)",
        notes="Negative-edge window banners (day/color blocks)",
    ),
    SkinFamily(
        "OPS_TIER_LEGEND",
        ROLE_OPS,
        "0",
        "OPS tier legend / glossary line",
        "💎 SOLO ELITE → sala elite sozinha / single elite room",
        notes="Explanatory legend in ONLINE banner or /help glossary, not a standalone fire",
    ),
    # ── G2 RESERVE subsystem (always-red recovery loop) ─────────────────────
    SkinFamily(
        "FIRE_G2_RESERVE",
        ROLE_FIRE,
        "g2reserve",
        "FIRE G2 RESERVE — always red loop",
        "🔁 **G2 RESERVE — SEMPRE VERMELHO / ALWAYS RED**",
        LANE_MONEY,
        kind_scoped=True,
        notes="Fixed-color G2 reserve chain; loop continues until win or chain close",
    ),
    SkinFamily(
        "RESULT_G2_RESERVE_WIN",
        ROLE_RESULT,
        "g2reserve",
        "RESULT G2 RESERVE recovery win",
        "🏆🏆🏆 **G2 RESERVE — RECUPERAÇÃO WIN!** 🏆🏆🏆",
        kind_scoped=True,
    ),
    SkinFamily(
        "OPS_G2_RESERVE_MISS",
        ROLE_OPS,
        "g2reserve",
        "OPS G2 RESERVE miss — chain closed",
        "🛑🛑 **G2 RESERVE MISS — CADEIA ENCERRADA** 🛑🛑",
        notes="Terminal card for the reserve chain",
    ),
    SkinFamily(
        "OPS_TIE_AUDIT",
        ROLE_OPS,
        "audit",
        "OPS tie audit report (empates)",
        "🟡🟡🟡 **AUDITORIA COMPLETA — EMPATES** 🟡🟡🟡",
        notes="Includes room_memory tie accuracy + outcome_history real-tie sections",
    ),
    SkinFamily(
        "OPS_COMMAND_HELP",
        ROLE_OPS,
        "help",
        "OPS command help / keyword glossary",
        "🟡 **`empate`** · **`tie`** · **`pressao`**",
        notes="From strings.py — bot UI text, never a signal card",
    ),
    SkinFamily(
        "OPS_STAT_LINE",
        ROLE_OPS,
        "audit",
        "OPS combined WR stat line",
        "📊 **87.8% WR** combinado · TRUE G2 · n=115",
    ),
    # ── Real cards recovered from live gate sources (AST sweep) ─────────────
    SkinFamily(
        "OPS_RADAR_PARTIAL_CONSENSUS",
        ROLE_OPS,
        "radar",
        "OPS radar — partial consensus",
        "👁 **RADAR — PARTIAL CONSENSUS** 👁",
        notes="Pre-fire radar; rooms agreeing but below fire threshold",
    ),
    SkinFamily(
        "OPS_OPEN_PLATFORM_NOW",
        ROLE_OPS,
        "prealert",
        "OPS open the platform — signal in seconds",
        "🚨 **ABRA A PLATAFORMA AGORA — SINAL EM SEGUNDOS!** 🚨",
        notes="Also 'AGORA É A HORA!' variant; urgency prealert",
    ),
    SkinFamily(
        "FIRE_FLASH_CONFIRMADO",
        ROLE_FIRE,
        "flash",
        "FIRE flash confirmed",
        "⚡⚡ **FLASH CONFIRMADO** —",
        LANE_COUNTDOWN,
        kind_scoped=True,
        notes="FLASH-kind confirmation fire; sniper band",
    ),
    SkinFamily(
        "RESULT_AUTO_WIN",
        ROLE_RESULT,
        "auto",
        "RESULT auto-detected WIN",
        "✅ AUTO WIN",
        kind_scoped=True,
        notes="Auto-resolved from room outcome, no manual /win",
    ),
    SkinFamily(
        "RESULT_AUTO_LOSS",
        ROLE_RESULT,
        "auto",
        "RESULT auto-detected LOSS",
        "❌ AUTO LOSS",
        kind_scoped=True,
    ),
    SkinFamily(
        "OPS_AUTO_EXPIRED",
        ROLE_OPS,
        "auto",
        "OPS signal auto-expired by kind",
        "🏆 GOLDEN: auto-expired",
        kind_scoped=True,
        notes="Fire aged out with no resolvable outcome",
    ),
    SkinFamily(
        "RESULT_FINAL_LOSS_AFTER_G3",
        ROLE_RESULT,
        "g3",
        "RESULT final loss after G3",
        "❌ FINAL LOSS after G3 —",
        kind_scoped=True,
        notes="Terminal loss on the historical 3-gale ladder",
    ),
    SkinFamily(
        "OPS_DELIVERY_WINDOW_LOG",
        ROLE_OPS,
        "internal",
        "OPS delivery-audit window line",
        "| ⚠️  MISSED WIN — gate=",
        notes="BLOCKED LOSS / MISSED WIN / QUIET rows from the delivery auditor",
    ),
    SkinFamily(
        "CARD_BODY_LINE",
        ROLE_UNKNOWN,
        "internal",
        "Card body fragment (not a header)",
        "└ _Primary bet — full bankroll_",
        notes="Continuation lines, footers, table cells — kept for template fidelity",
    ),
)

_FAMILY_BY_ID: Dict[str, SkinFamily] = {f.family_id: f for f in SKIN_FAMILIES}

# Telegram archaeology type_id → canonical SkinFamily id (same skin, different label)
TG_TYPE_ALIASES: Dict[str, str] = {
    "FIRE_SOLO_ELITE_SIGNAL": "FIRE_SOLO_ELITE_ENTER",
    "FIRE_GOLDEN_SIGNAL_ENTER_NOW": "FIRE_GOLDEN_ENTER",
    "FIRE_GOLDEN": "FIRE_GOLDEN_ENTER",
    "FIRE_PLATINUM": "FIRE_PLATINUM_ENTER",
    "FIRE_SEQUENCE": "FIRE_SEQUENCE_ENTER",
    "FIRE_SIGNAL_CONFIRMED_ENTER_NOW": "FIRE_CONFIRMED_ENTER",
    "FIRE_GOD_TIER_SYNC_APERTADO_3_SALAS_TOP_CONF_75": "FIRE_GOD_TIER",
    "FIRE_GALE_1_RETENTATIVA_SOLO_ELITE": "FIRE_GALE_RETENTATIVA",
    "FIRE_GALE_1_RETENTATIVA_GOLDEN": "FIRE_GALE_RETENTATIVA",
    "FIRE_SINAL_RETIDO": "FIRE_SINAL_RETIDO_LIBERADO",
    "FIRE_SEQUENCIA_STREAK": "OPS_STREAK_BANNER",
    "FIRE_SEQU_NCIA_ENTER_NOW": "FIRE_SEQUENCIA_ENTER_NOW",
    "CD_FIRE_DO_NOT_BET_PASSED": "CD_FIRE_TIMER_BRT_EDT_APOSTAR",
    "CD_FIRE_TIMER": "CD_FIRE_TIMER_BRT_EDT_APOSTAR",
    "RESULT_WIN_SOLO_ELITE": "RESULT_WIN_TIER",
    "RESULT_WIN_GOLDEN": "RESULT_WIN_TIER",
    "RESULT_WIN_SEQUENCE": "RESULT_WIN_TIER",
    "RESULT_WIN_PLATINUM": "RESULT_WIN_TIER",
    "RESULT_WIN_FLASH": "RESULT_WIN_TIER",
    "RESULT_LOSS_SOLO_ELITE": "RESULT_LOSS_TIER",
    "RESULT_LOSS_GOLDEN": "RESULT_LOSS_TIER",
    "RESULT_LOSS_SEQUENCE": "RESULT_LOSS_TIER",
    "RESULT_LOSS_PLATINUM": "RESULT_LOSS_TIER",
    "RESULT_LOSS_G0_FALHOU": "RESULT_LOSS_TIER",
    "RESULT_LOSS_G1_FALHOU": "RESULT_LOSS_TIER",
    "RESULT_EMPATE_SOLO_ELITE": "RESULT_EMPATE",
    "RESULT_EMPATE_GOLDEN": "RESULT_EMPATE",
    "RESULT_EMPATE_SEQUENCE": "RESULT_EMPATE",
    "RESULT_EMPATE_PLATINUM": "RESULT_EMPATE",
    "RESULT_GALE_G0_N_O_FOI_ENTRE_NO_G1_AGORA": "FIRE_G0_MISS_ENTRE_G1",
    "RESULT_GALE_G1_N_O_FOI_G2_OPCIONAL_RISCO_ALTO": "OPS_G2_MISS",
    "RESULT_GALE_G2_N_O_FOI_PERDA_TOTAL_PARE_AGORA": "OPS_G2_MISS",
    "RESULT_GALE_G1_EXPIROU_VERIFIQUE_SUA_MESA": "OPS_G1_EXPIROU",
    "RESULT_GALE_G2_EXPIROU_VERIFIQUE_SUA_MESA": "OPS_G2_MISS",
    "RESULT_GALE_DO_NOT_BET_ROUND_PASSED": "FIRE_JANELA_TIMED",
    "RESULT_BANNER_TIE_ALERTA_DE_EMPATE_TIE_ALERT": "OPS_TIE_ALERT",
    "RESULT_BANNER_TIE_SEQU_NCIA_DE_EMPATES": "OPS_SEQ_EMPATES",
    "RESULT_BANNER_TIE_EMPATE_CR_TICO": "OPS_TIE_ALERT",
    "RESULT_BANNER_TIE_JANELA_DE_EMPATE_ATIVA": "OPS_TIE_ALERT",
    "RESULT_BANNER_TIE_PRESS_O_DE_EMPATE_ALERTA_AUTOM": "OPS_TIE_ALERT",
    "RESULT_BANNER_TIE_AVISO_DE_EMPATE": "OPS_TIE_ALERT",
    "RESULT_BANNER_TIE_ULTRA_TIE_EMPATE_CONFIRMADO": "FIRE_ULTRA_TIE",
    "RES_WIN_KIND": "RESULT_WIN_TIER",
    "RES_LOSS_KIND": "RESULT_LOSS_TIER",
    "RES_GREEN_G0": "RESULT_GREEN_LEGACY_G0",
    "RES_AUTO_WIN": "RESULT_WIN_TIER",
    "RES_AUTO_LOSS": "RESULT_LOSS_TIER",
    "RES_AUTO_TIE": "RESULT_AUTO_TIE",
}


def all_skin_families() -> Tuple[SkinFamily, ...]:
    return SKIN_FAMILIES


def get_skin_family(family_id: str) -> Optional[SkinFamily]:
    return _FAMILY_BY_ID.get((family_id or "").strip())


def canonical_family_id(raw_id: str) -> str:
    """Map archaeology / DB type labels onto registered SkinFamily ids."""
    rid = (raw_id or "").strip()
    if not rid:
        return rid
    if rid in _FAMILY_BY_ID:
        return rid
    if rid in TG_TYPE_ALIASES:
        return TG_TYPE_ALIASES[rid]
    # Variable-N JANELA type_ids → one family
    if re.match(r"^FIRE_JANELA_\d+S_", rid, re.I):
        return "FIRE_JANELA_TIMED"
    if rid.startswith("FIRE_GOD_TIER"):
        return "FIRE_GOD_TIER"
    # Kind-scoped short results already covered; strip trailing signal ids
    m = re.match(r"^(RESULT_WIN|RESULT_LOSS|RESULT_EMPATE)_([A-Z0-9]+?)(?:_\d+)?$", rid)
    if m:
        base = {"RESULT_WIN": "RESULT_WIN_TIER", "RESULT_LOSS": "RESULT_LOSS_TIER", "RESULT_EMPATE": "RESULT_EMPATE"}[
            m.group(1)
        ]
        return base
    return rid


def gate_keys_for(family_id: str, kind: Optional[str] = None) -> Tuple[str, ...]:
    """Stable keys EngineGateRegistry can disable/retire.

    Always includes the family id. When ``kind`` is known, also includes
    ``FAMILY:KIND`` so e.g. RESULT_EMPATE:SOLO_ELITE can be retired alone.
    """
    fid = (family_id or "").strip()
    if not fid:
        return ()
    keys: List[str] = [fid]
    k = (kind or "").strip().upper().replace(" ", "_")
    if k:
        keys.append(f"{fid}:{k}")
    seen = set()
    out: List[str] = []
    for key in keys:
        if key not in seen:
            seen.add(key)
            out.append(key)
    return tuple(out)


def _first_line(text: str) -> str:
    if not text:
        return ""
    for line in str(text).replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        s = line.strip()
        if s:
            return s
    return ""


def _extract_kind(text: str, first_line: str = "") -> Optional[str]:
    blob = f"{first_line}\n{text or ''}"
    for pat, kind in _KIND_PATTERNS:
        if re.search(pat, blob, re.I):
            return kind
    # Trailing "— KIND" / "-- KIND" forms
    m = re.search(
        r"(?:—|--)\s*([A-Z][A-Z0-9_]{2,})\b",
        first_line or _first_line(text),
    )
    if m:
        return m.group(1).upper()
    m = re.search(
        r"SIGNAL\s*#\d+\s*--\s*([A-Za-z0-9_]+)",
        text or "",
        re.I,
    )
    if m:
        return m.group(1).upper().replace(" ", "_")
    return None


def _extract_clock_n(text: str) -> Optional[int]:
    t = text or ""
    for pat in (
        r"JANELA\s*[:=]\s*(\d+)\s*s",
        r"~(\d+)\s*s\s*window",
        r"🟢\s*(\d+)\s*s\s*🟢",
        r"(\d+)\s*s\s+para\s+apostar",
        r"JANELA\s+FECHADA[^0-9]{0,40}(\d+)\s*s",
    ):
        m = re.search(pat, t, re.I)
        if m:
            try:
                return int(m.group(1))
            except ValueError:
                return None
    return None


def _match(
    family_id: str,
    *,
    text: str,
    first_line: str,
    kind: Optional[str] = None,
    clock_n: Optional[int] = None,
    lane_override: Optional[str] = None,
    notes: str = "",
) -> SkinMatch:
    fam = _FAMILY_BY_ID.get(family_id)
    resolved_kind = kind if kind is not None else _extract_kind(text, first_line)
    resolved_clock = clock_n
    if resolved_clock is None and fam and fam.variable_n:
        resolved_clock = _extract_clock_n(text)
    return SkinMatch(
        family_id=family_id,
        role=fam.role if fam else ROLE_UNKNOWN,
        kind=resolved_kind,
        lane=lane_override or (fam.default_lane if fam else None),
        clock_n=resolved_clock,
        gate_keys=gate_keys_for(family_id, resolved_kind),
        first_line=first_line,
        era=fam.era if fam else None,
        label=fam.label if fam else family_id,
        notes=notes or (fam.notes if fam else ""),
    )


def classify_telegram_skin(
    text: str | None = None,
    *,
    signal_kind: str | None = None,
    meta: Optional[Dict[str, Any]] = None,
) -> SkinMatch:
    """Map outbound/inbound card text → stable skin family + gate keys.

    Precedence mirrors archaeology: ONLINE → ROOM_RELAY → RESULT → timed FIRE →
    named FIRE → OPS → UNKNOWN.
    """
    meta = meta or {}
    body = str(text or meta.get("text") or meta.get("card_text") or "")
    fl = _first_line(body)
    low = body.lower()
    hint_kind = (signal_kind or meta.get("signal_kind") or meta.get("kind") or "")
    hint_kind = str(hint_kind).strip().upper().replace(" ", "_") or None

    if not fl and not body.strip():
        if hint_kind:
            family_id = f"SIGNAL_KIND_{hint_kind}"
            return SkinMatch(
                family_id=family_id,
                role=ROLE_FIRE,
                kind=hint_kind,
                lane=LANE_MONEY,
                clock_n=None,
                gate_keys=(family_id, hint_kind),
                first_line="",
                era=None,
                label=f"DB signal_kind {hint_kind}",
                notes="No Telegram text; bridging via signal_kind",
            )
        return SkinMatch(
            family_id="EMPTY",
            role=ROLE_EMPTY,
            kind=None,
            lane=None,
            clock_n=None,
            gate_keys=("EMPTY",),
            first_line="",
            era=None,
            label="empty",
        )

    # ── ONLINE ──────────────────────────────────────────────────────────────
    if "luxury outbox online" in low:
        return _match("ONLINE_LUXURY_OUTBOX", text=body, first_line=fl)
    if "userbot online" in low or re.search(r"BacBo Royal UserBot ONLINE", body, re.I):
        return _match("ONLINE_BANNER", text=body, first_line=fl)

    # ── ROOM RELAY ──────────────────────────────────────────────────────────
    if (
        re.match(r"^📡\s*@", fl)
        or re.match(r"^✅\s*AUTO\s*WIN\s*@", fl, re.I)
        or re.match(r"^🤑\s*✅", fl)
    ):
        return _match("ROOM_RELAY", text=body, first_line=fl, notes="noise")

    # ── RESULT / result-ops (before FIRE — Intervalo never makes a fire) ───
    if re.search(r"G2\s+MISS\s*—\s*PERDA\s+TOTAL|G2\s+MISS", body, re.I):
        return _match(
            "OPS_G2_MISS",
            text=body,
            first_line=fl,
            kind=hint_kind or _extract_kind(body, fl),
        )
    if re.search(r"G1\s+EXPIROU", body, re.I):
        return _match(
            "OPS_G1_EXPIROU",
            text=body,
            first_line=fl,
            kind=hint_kind or _extract_kind(body, fl),
        )
    if re.search(r"RESUMIDO\s+FORENSE", body, re.I):
        return _match(
            "RESULT_FORENSIC_INTERVALO",
            text=body,
            first_line=fl,
            kind=hint_kind or _extract_kind(body, fl),
            clock_n=_extract_clock_n(body),
        )
    if re.search(r"🔔\s*[✅❌].*(GANHOU|PERDEU|G0\s*WIN|LOSS)", body, re.I) or re.search(
        r"🔔\s*[✅❌]\s*(GANHOU|PERDEU|G0\s*WIN|LOSS)", body, re.I
    ):
        return _match(
            "RESULT_BELL_GANHOU",
            text=body,
            first_line=fl,
            kind=hint_kind or _extract_kind(body, fl),
        )

    if re.match(r"^🟡\s*EMPATE\s*—", fl, re.I) or re.match(r"^EMPATE\s*—", fl, re.I):
        kind = re.sub(r"^🟡\s*EMPATE\s*—\s*", "", fl, flags=re.I)
        kind = re.sub(r"^EMPATE\s*—\s*", "", kind, flags=re.I).strip()
        kind = kind.upper().replace(" ", "_") or hint_kind
        return _match("RESULT_EMPATE", text=body, first_line=fl, kind=kind)

    if re.match(r"^✅\s*WIN\s*—\s*FLASH\b", fl, re.I):
        return _match("RESULT_FLASH_WIN", text=body, first_line=fl, kind="FLASH")

    if re.match(r"^✅\s*WIN\s*—", fl, re.I):
        kind = re.sub(r"^✅\s*WIN\s*—\s*", "", fl, flags=re.I).strip()
        kind = kind.upper().replace(" ", "_") or hint_kind
        return _match("RESULT_WIN_TIER", text=body, first_line=fl, kind=kind)

    if re.match(r"^❌\s*LOSS\s*—", fl, re.I):
        kind = re.sub(r"^❌\s*LOSS\s*—\s*", "", fl, flags=re.I).strip()
        kind = kind.upper().replace(" ", "_") or hint_kind
        return _match("RESULT_LOSS_TIER", text=body, first_line=fl, kind=kind)

    if re.match(r"^✅\s*WIN\s*#\d+", fl, re.I):
        return _match("RESULT_COMPACT_WIN_HASH", text=body, first_line=fl, kind=hint_kind)
    if re.match(r"^❌\s*LOSS\s*#\d+", fl, re.I):
        return _match("RESULT_COMPACT_LOSS_HASH", text=body, first_line=fl, kind=hint_kind)
    if re.match(r"^➖\s*TIE\s*#\d+", fl, re.I) or re.match(r"^TIE\s*#\d+", fl, re.I):
        return _match("RESULT_COMPACT_TIE_HASH", text=body, first_line=fl, kind=hint_kind)

    if re.search(r"AUTO\s*TIE\s*@", fl, re.I) or re.match(r"^⚪\s*AUTO\s*TIE", fl, re.I):
        return _match("RESULT_AUTO_TIE", text=body, first_line=fl)

    if re.search(r"GREEN\s*—\s*VIT[ÓO]RIA\s+NO\s+G0", fl, re.I):
        return _match("RESULT_GREEN_LEGACY_G0", text=body, first_line=fl)
    if re.search(r"GREEN\s*—\s*RECUPERADO\s+NO\s+G1", fl, re.I):
        return _match("RESULT_GREEN_LEGACY_G1", text=body, first_line=fl)

    if re.match(r"^✅\s*GREEN\s*[·.]", fl, re.I) and re.search(r"\bG0\b", fl, re.I):
        return _match("RESULT_GREEN_COMPACT_G0", text=body, first_line=fl)
    if re.match(r"^♻️\s*GREEN\s*[·.]", fl, re.I) and re.search(r"\bG1\b", fl, re.I):
        return _match("RESULT_GREEN_COMPACT_G1", text=body, first_line=fl)

    if re.search(r"~\d+\s*s\s*window", body, re.I):
        return _match(
            "RESULT_TIMED_WINDOW",
            text=body,
            first_line=fl,
            clock_n=_extract_clock_n(body),
        )

    # ── FIRE gale follow-ups (before SOLO body match) ───────────────────────
    if re.search(r"GALE\s*\d+\s*—\s*RETENTATIVA", body, re.I) or re.match(
        r"^♻️\s*GALE", fl
    ):
        return _match(
            "FIRE_GALE_RETENTATIVA",
            text=body,
            first_line=fl,
            kind=hint_kind or _extract_kind(body, fl),
            lane_override=LANE_MONEY,
        )

    if re.search(r"GALE\s*\d+\s*—\s*Entre\s+novamente", body, re.I) or re.match(
        r"^🔁\s*GALE", fl
    ):
        return _match(
            "FIRE_GALE_ENTRE_NOVAMENTE",
            text=body,
            first_line=fl,
            kind=hint_kind or _extract_kind(body, fl),
            lane_override=LANE_MONEY,
        )

    # ── Countdown peak fires (Sinal Retido / CD_FIRE) — before bare JANELA ─
    if re.search(r"Sinal\s+Retido\s*→\s*Liberado|Sinal\s+Retido", body, re.I):
        return _match(
            "FIRE_SINAL_RETIDO_LIBERADO",
            text=body,
            first_line=fl,
            kind=hint_kind or _extract_kind(body, fl),
            clock_n=_extract_clock_n(body),
            lane_override=LANE_COUNTDOWN,
        )
    if re.search(r"QUANTUM\s*LOCK|CD_FIRE_QUANTUM", body, re.I):
        return _match(
            "CD_FIRE_QUANTUM_LOCK",
            text=body,
            first_line=fl,
            kind=hint_kind or _extract_kind(body, fl),
            lane_override=LANE_COUNTDOWN,
        )
    if re.search(r"CD_FIRE_TIMER_BRT_EDT_APOSTAR", body, re.I) or (
        re.search(r"\b(BRT|EDT)\b", body)
        and re.search(r"apostar|JANELA|timer|🟢\s*\d+\s*s", body, re.I)
        and not re.search(r"RESUMIDO\s+FORENSE|GANHOU|PERDEU", body, re.I)
    ):
        return _match(
            "CD_FIRE_TIMER_BRT_EDT_APOSTAR",
            text=body,
            first_line=fl,
            kind=hint_kind or _extract_kind(body, fl),
            clock_n=_extract_clock_n(body),
            lane_override=LANE_COUNTDOWN,
        )

    # ── Timed FIRE (Clock A — any N) ────────────────────────────────────────
    if (
        re.search(r"JANELA\s*[:=]\s*\d+\s*s", body, re.I)
        or re.search(r"🟢\s*\d+\s*s\s*🟢", body)
        or re.search(r"\d+\s*s\s+para\s+apostar", body, re.I)
        or re.search(r"JANELA\s+FECHADA", body, re.I)
    ):
        return _match(
            "FIRE_JANELA_TIMED",
            text=body,
            first_line=fl,
            kind=hint_kind or _extract_kind(body, fl),
            clock_n=_extract_clock_n(body),
            lane_override=LANE_COUNTDOWN,
        )

    # ── Compact hash FIRE ───────────────────────────────────────────────────
    if re.search(r"SIGNAL\s*#\d+", fl, re.I):
        return _match(
            "FIRE_COMPACT_HASH",
            text=body,
            first_line=fl,
            kind=hint_kind or _extract_kind(body, fl),
            lane_override=LANE_MONEY,
        )

    # ── APOSTAR AGORA (Era 6 — distinct from ENTER NOW) ─────────────────────
    if re.search(r"APOSTAR\s+AGORA", fl, re.I):
        if re.search(r"SOLO\s*ELITE", fl, re.I):
            return _match("FIRE_SOLO_APOSTAR", text=body, first_line=fl, kind="SOLO_ELITE")
        if re.search(r"SEQUENCE|SEQU[EÊ]NCIA", fl, re.I):
            return _match("FIRE_SEQUENCE_APOSTAR", text=body, first_line=fl, kind="SEQUENCE")
        if re.search(r"GOLDEN", fl, re.I):
            return _match("FIRE_GOLDEN_APOSTAR", text=body, first_line=fl, kind="GOLDEN")
        if re.search(r"PLATINUM", fl, re.I):
            return _match("FIRE_PLATINUM_APOSTAR", text=body, first_line=fl, kind="PLATINUM")
        if re.search(r"FLASH", fl, re.I):
            return _match("FIRE_FLASH_APOSTAR", text=body, first_line=fl, kind="FLASH")

    # ── Named money FIRE headers ────────────────────────────────────────────
    if re.search(r"SIGNAL\s+CONFIRMED\s*—\s*ENTER\s+NOW", body, re.I):
        return _match("FIRE_CONFIRMED_ENTER", text=body, first_line=fl, kind=hint_kind)
    if re.search(r"GOD[- ]?TIER", fl, re.I) or re.search(r"GOD[- ]?TIER", body, re.I):
        return _match(
            "FIRE_GOD_TIER",
            text=body,
            first_line=fl,
            kind=hint_kind or _extract_kind(body, fl),
            lane_override=LANE_MONEY,
        )
    if re.search(r"GOLDEN\s+SIGNAL\s*—\s*ENTRE\s+AGORA", body, re.I):
        return _match("FIRE_GOLDEN_ENTRE_AGORA", text=body, first_line=fl, kind="GOLDEN")
    if re.search(r"GOLDEN\s+SIGNAL\s*—\s*ENTER\s+NOW", body, re.I):
        return _match("FIRE_GOLDEN_ENTER", text=body, first_line=fl, kind="GOLDEN")
    if re.search(r"SOLO\s*ELITE\s+SIGNAL", body, re.I):
        return _match("FIRE_SOLO_ELITE_ENTER", text=body, first_line=fl, kind="SOLO_ELITE")
    if re.search(r"SEQUENCE\s+SIGNAL\s*—\s*ENTER\s+NOW", body, re.I):
        return _match("FIRE_SEQUENCE_ENTER", text=body, first_line=fl, kind="SEQUENCE")
    if re.search(r"PLATINUM", fl, re.I) and re.search(r"ENTER\s+NOW|SIGNAL|PAR DE OURO", body, re.I):
        return _match("FIRE_PLATINUM_ENTER", text=body, first_line=fl, kind="PLATINUM")
    if re.search(r"ULTRA\s*TIE|ULTRA_TIE", body, re.I) and re.search(
        r"EMPATE|ENTER|SIGNAL|CONFIRMADO", body, re.I
    ):
        return _match("FIRE_ULTRA_TIE", text=body, first_line=fl, kind="ULTRA_TIE")
    if re.search(r"EMPATE\s+DIRETO", fl, re.I):
        return _match("FIRE_EMPATE_DIRETO_G0", text=body, first_line=fl, kind=hint_kind)
    if re.search(r"G0\s+DIRETO", fl, re.I):
        return _match("FIRE_G0_DIRETO", text=body, first_line=fl, kind=hint_kind)
    if re.search(r"G0\s+N[AÃ]O\s+FOI\s*—\s*ENTRE\s+NO\s+G1", fl, re.I) or re.search(
        r"G0\s+MISS\s*—\s*G1\s+AGORA", fl, re.I
    ):
        return _match(
            "FIRE_G0_MISS_ENTRE_G1",
            text=body,
            first_line=fl,
            kind=hint_kind or _extract_kind(body, fl),
            clock_n=_extract_clock_n(body),
            lane_override=LANE_MONEY,
        )
    if re.search(r"PREPARE\s+O\s+G1", fl, re.I):
        return _match("FIRE_PREPARE_G1", text=body, first_line=fl, kind=hint_kind)
    if re.search(r"SEQU[EÊ]NCIA\s*—\s*ENTER\s+NOW", fl, re.I):
        return _match("FIRE_SEQUENCIA_ENTER_NOW", text=body, first_line=fl, kind="SEQUENCE")
    # Generic ENTER NOW / ENTRE AGORA / APOSTE AGORA (gate-era code cards) —
    # only after all named-kind headers above have had their chance.
    if re.search(r"ENTER\s+NOW", body, re.I):
        return _match(
            "FIRE_ENTER_NOW_GENERIC",
            text=body,
            first_line=fl,
            kind=hint_kind or _extract_kind(body, fl),
            lane_override=LANE_MONEY,
        )
    if re.search(r"ENTRE\s+AGORA", body, re.I):
        return _match(
            "FIRE_ENTRE_AGORA_GENERIC",
            text=body,
            first_line=fl,
            kind=hint_kind or _extract_kind(body, fl),
            lane_override=LANE_MONEY,
        )
    if re.search(r"APOSTE\s+AGORA", body, re.I):
        return _match(
            "FIRE_APOSTE_AGORA",
            text=body,
            first_line=fl,
            kind=hint_kind or _extract_kind(body, fl),
            lane_override=LANE_MONEY,
        )

    # ── Real cards recovered from gate sources ──────────────────────────────
    if re.search(r"RADAR\s*—\s*(?:PARTIAL\s+CONSENSUS|CONSENSO\s+PARCIAL)", body, re.I):
        return _match("OPS_RADAR_PARTIAL_CONSENSUS", text=body, first_line=fl)
    if re.search(r"ABRA\s+A\s+PLATAFORMA\s+AGORA|AGORA\s+[EÉ]\s+A\s+HORA", body, re.I):
        return _match("OPS_OPEN_PLATFORM_NOW", text=body, first_line=fl)
    if re.search(r"FLASH\s+CONFIRMADO", body, re.I):
        return _match(
            "FIRE_FLASH_CONFIRMADO",
            text=body,
            first_line=fl,
            kind="FLASH",
            lane_override=LANE_COUNTDOWN,
        )
    if re.search(r"FINAL\s+LOSS\s+after\s+G3", body, re.I):
        return _match(
            "RESULT_FINAL_LOSS_AFTER_G3",
            text=body,
            first_line=fl,
            kind=hint_kind or _extract_kind(body, fl),
        )
    if re.search(r"\bauto-expired\b", body, re.I):
        return _match(
            "OPS_AUTO_EXPIRED",
            text=body,
            first_line=fl,
            kind=hint_kind or _extract_kind(body, fl),
        )
    if re.fullmatch(r"[\s✅❌🟡⚪]*AUTO\s+WIN[\s!.]*", (fl or "").strip(), re.I):
        return _match("RESULT_AUTO_WIN", text=body, first_line=fl, kind=hint_kind)
    if re.fullmatch(r"[\s✅❌🟡⚪]*AUTO\s+LOSS[\s!.]*", (fl or "").strip(), re.I):
        return _match("RESULT_AUTO_LOSS", text=body, first_line=fl, kind=hint_kind)
    if re.fullmatch(r"[\s✅❌🟡⚪]*AUTO\s+TIE[\s!.@…]*", (fl or "").strip(), re.I):
        return _match("RESULT_AUTO_TIE", text=body, first_line=fl)
    if re.search(r"G0\s+[uú]nico\s*—\s*sem\s+gale", body, re.I):
        return _match("FIRE_DEPTH_G0_ONLY", text=body, first_line=fl, lane_override=LANE_MONEY)
    if re.search(r"\bG0\s+MISS\b", body, re.I):
        return _match(
            "FIRE_G0_MISS_ENTRE_G1",
            text=body,
            first_line=fl,
            kind=hint_kind or _extract_kind(body, fl),
            clock_n=_extract_clock_n(body),
            lane_override=LANE_MONEY,
        )
    if re.search(r"APEX\s+WINDOW", body, re.I):
        return _match(
            "FIRE_NAMED_EDGE_BANNER",
            text=body,
            first_line=fl,
            kind=hint_kind or _extract_kind(body, fl),
            lane_override=LANE_MONEY,
        )
    if re.search(r"~\s*\d+\s*s\s+para\s+o\s+\S+\s*—\s*esteja\s+pronto", body, re.I):
        return _match("OPS_OPEN_PLATFORM_NOW", text=body, first_line=fl)
    if re.search(r"(?:BLOCKED\s+LOSS|MISSED\s+WIN)\s*—\s*gate=|🔇\s*QUIET", body, re.I):
        return _match("OPS_DELIVERY_WINDOW_LOG", text=body, first_line=fl)

    # ── G2 RESERVE subsystem (before generic G2 handling) ───────────────────
    if re.search(r"G2\s+RESERVE", body, re.I):
        if re.search(r"MISS|CADEIA\s+ENCERRADA", body, re.I):
            return _match("OPS_G2_RESERVE_MISS", text=body, first_line=fl)
        if re.search(r"RECUPERA[CÇ][AÃ]O\s+WIN|WIN!|GANHOU", body, re.I):
            return _match(
                "RESULT_G2_RESERVE_WIN",
                text=body,
                first_line=fl,
                kind=hint_kind or _extract_kind(body, fl),
            )
        return _match(
            "FIRE_G2_RESERVE",
            text=body,
            first_line=fl,
            kind=hint_kind or _extract_kind(body, fl),
            lane_override=LANE_MONEY,
        )

    # ── Audit / help / stat surfaces ────────────────────────────────────────
    if re.search(r"AUDITORIA\s+COMPLETA\s*—\s*EMPATES", body, re.I) or re.search(
        r"Acur[aá]cia\s+de\s+empate\s+por\s+sala|[UÚ]ltimos\s+empates\s+reais",
        body,
        re.I,
    ):
        return _match("OPS_TIE_AUDIT", text=body, first_line=fl)
    if re.search(r"^\s*[🟡🔵🔴⚪✅❌]?\s*(?:\*\*)?`\w+`", fl):
        return _match("OPS_COMMAND_HELP", text=body, first_line=fl)
    if re.search(r"\d+(?:\.\d+)?%\s*WR\*?\*?\s*combinado|WR\*?\*?\s*combinado", body, re.I):
        return _match("OPS_STAT_LINE", text=body, first_line=fl)
    # Glossary/legend: "💎 *SOLO ELITE* — explanation" or "TIER → explanation"
    if re.search(
        r"(?:💎|🏆|📊|💠|⚡|🟡|🔵|🔴|⚪)\s*\*?\*?_?"
        r"(?:SOLO\s*ELITE|GOLDEN\s+SIGNAL|SEQUENCE|PLATINUM|FLASH|ULTRA\s*TIE|"
        r"Empate|Tie|Vermelho|Azul|Blue|Red|FORMANDO|FORMING|MEN[CÇ][AÃ]O|MENTION)"
        r"\*?\*?_?\s*(?:—|->|→|/)",
        fl,
        re.I,
    ) and not re.search(r"ENTER\s+NOW|ENTRE\s+AGORA|APOSTAR|JANELA", fl, re.I):
        return _match("OPS_TIER_LEGEND", text=body, first_line=fl)

    # ── Code-formatter cards (bacbo_royal_complete / _gates_*) ──────────────
    if re.search(r"ORACLE\s+LOCK|ORACLE\s*—\s*H\d+", body, re.I):
        return _match(
            "FIRE_ORACLE_LOCK",
            text=body,
            first_line=fl,
            kind=hint_kind or _extract_kind(body, fl),
            lane_override=LANE_MONEY,
        )
    if re.search(r"CERTIFIED\s+ELITE", body, re.I):
        return _match(
            "FIRE_CERTIFIED_ELITE",
            text=body,
            first_line=fl,
            kind=hint_kind or _extract_kind(body, fl),
            lane_override=LANE_MONEY,
        )
    if re.search(r"DOUBLE\s+TIE\s+LOCK", body, re.I):
        return _match("FIRE_DOUBLE_TIE_LOCK", text=body, first_line=fl, lane_override=LANE_MONEY)
    if re.search(r"GRADE\s+[A-D]\b.*G0\s*=", body, re.I):
        return _match(
            "FIRE_GRADE_BANNER",
            text=body,
            first_line=fl,
            kind=hint_kind or _extract_kind(body, fl),
            lane_override=LANE_MONEY,
        )
    if re.search(r"APEX\s+TRIO|ZERO[- ]LOSS\s+ZONE|\bPRIME\b\s*·|PRIME\s*·", body, re.I) or (
        re.search(r"[A-Z_]{4,}\s+PRIME\b", body) and re.search(r"G0\s*=", body, re.I)
    ):
        return _match(
            "FIRE_NAMED_EDGE_BANNER",
            text=body,
            first_line=fl,
            kind=hint_kind or _extract_kind(body, fl),
            lane_override=LANE_MONEY,
        )
    if re.search(
        r"\b(?:BLUE|RED|AZUL|VERMELHO)\s+(?:MONDAY|TUESDAY|WEDNESDAY|THURSDAY|"
        r"FRIDAY|SATURDAY|SUNDAY|SEGUNDA|TER[CÇ]A|QUARTA|QUINTA|SEXTA)\b",
        body,
        re.I,
    ):
        return _match("OPS_NEGATIVE_WINDOW_BLOCK", text=body, first_line=fl)
    if re.search(r"HOT\s+TABLE|HOT\s+STREAK|PERFECT\s+\d+/\d+\s+WIN\s+STREAK", body, re.I):
        return _match(
            "FIRE_HOT_STREAK",
            text=body,
            first_line=fl,
            kind=hint_kind or _extract_kind(body, fl),
            lane_override=LANE_MONEY,
        )
    if re.search(r"CONTR[AÁ]RIO", fl, re.I) and re.search(
        r"invertid|oposto|inverted|opposite", body, re.I
    ):
        return _match(
            "FIRE_INVERTED_CONTRARIO",
            text=body,
            first_line=fl,
            kind=hint_kind or _extract_kind(body, fl),
            lane_override=LANE_MONEY,
        )
    if re.search(r"DEPTH\s+G0\b|G0\s+ONLY", body, re.I):
        return _match("FIRE_DEPTH_G0_ONLY", text=body, first_line=fl, lane_override=LANE_MONEY)
    if re.search(r"Aposte\s+no\s+EMPATE", body, re.I):
        return _match("FIRE_APOSTAR_EMPATE", text=body, first_line=fl, lane_override=LANE_MONEY)
    if re.search(
        r"(?:PARE\s*—\s*G2\s+ATINGIDO|G2\s+atingido|Sinal\s+ENCERRADO\s*·?\s*\*?\*?pare\s+aqui)",
        body,
        re.I,
    ):
        return _match("OPS_G2_ATINGIDO_PARE", text=body, first_line=fl)
    if re.search(
        r"(?:💎|🏆|📊|💠|⚡)\s*(?:SOLO\s*ELITE|GOLDEN|SEQUENCE|PLATINUM|FLASH)\s*→",
        body,
        re.I,
    ):
        return _match("OPS_TIER_LEGEND", text=body, first_line=fl)
    if re.search(r"G0\s*—\s*(?:ENTRADA\s+DIRETA|PRIMEIRA\s+ENTRADA)", body, re.I):
        return _match(
            "FIRE_G0_ENTRADA_DIRETA",
            text=body,
            first_line=fl,
            kind=hint_kind or _extract_kind(body, fl),
            lane_override=LANE_MONEY,
        )
    if re.search(r"GALE\s*1\s*—\s*FA[CÇ]A\s+AGORA", body, re.I):
        return _match(
            "FIRE_GALE_1_FACA_AGORA",
            text=body,
            first_line=fl,
            kind=hint_kind or _extract_kind(body, fl),
            lane_override=LANE_MONEY,
        )
    if re.search(r"G3\s+ATINGIDO", body, re.I):
        return _match("OPS_G3_ATINGIDO", text=body, first_line=fl)
    if re.search(r"DO\s+NOT\s+BET\s+YET", body, re.I):
        return _match("OPS_DO_NOT_BET_YET", text=body, first_line=fl)
    if re.search(r"Prepare\s+a\s+plataforma", body, re.I):
        return _match("OPS_PREPARE_PLATFORM", text=body, first_line=fl)
    if re.search(r"Pr[oó]xima\s+janela\s+certificada|Next\s+certified\s+window", body, re.I):
        return _match("OPS_NEXT_CERTIFIED_WINDOW", text=body, first_line=fl)
    if re.search(r"JANELA\s+PEAK|PEAK\s+WINDOW", body, re.I):
        return _match("OPS_JANELA_PEAK", text=body, first_line=fl)
    if re.search(r"G1\s+(?:registrado|recorded).*calculando\s+G2", body, re.I):
        return _match("OPS_G1_REGISTRADO_CALC_G2", text=body, first_line=fl)
    if re.search(r"G2\s*_?\(se\s+perder\s+G1\)", body, re.I):
        return _match("OPS_G2_STOP_IF_G1_LOST", text=body, first_line=fl)
    if re.search(r"EMPATE\s*=\s*DINHEIRO\s+DEVOLVIDO", body, re.I):
        return _match("RESULT_EMPATE_DINHEIRO_DEVOLVIDO", text=body, first_line=fl)
    if re.search(r"EMPATE\s*—\s*PROTE[CÇ][AÃ]O\s+ATIVADA", body, re.I):
        return _match("RESULT_EMPATE_PROTECAO", text=body, first_line=fl)
    if re.search(r"G0\s*(?:→|->)\s*.*\bG[12]\b.*RECUPERAD|RECOVERED", body, re.I) and re.search(
        r"G0\s*(?:→|->)", body
    ):
        return _match(
            "RESULT_GALE_RECOVERED_CHAIN",
            text=body,
            first_line=fl,
            kind=hint_kind or _extract_kind(body, fl),
        )
    if re.search(r"ACERTOU\s+DE\s+PRIMEIRA|G0\s*—\s*Acertou\s+de\s+primeira", body, re.I):
        return _match(
            "RESULT_G0_ACERTOU_PRIMEIRA",
            text=body,
            first_line=fl,
            kind=hint_kind or _extract_kind(body, fl),
        )

    # ── RESULT oracle / tie alerts (before generic OPS) ─────────────────────
    if re.search(r"ORACLE\s+CARD", body, re.I):
        return _match(
            "RESULT_ORACLE_CARD",
            text=body,
            first_line=fl,
            kind=hint_kind or _extract_kind(body, fl),
        )
    if re.search(
        r"ALERTA\s+DE\s+EMPATE|TIE\s+ALERT|EMPATE\s+CR[IÍ]TICO|"
        r"JANELA\s+DE\s+EMPATE\s+ATIVA|PRESS[AÃ]O\s+DE\s+EMPATE|"
        r"AVISO\s+DE\s+EMPATE",
        body,
        re.I,
    ):
        return _match("OPS_TIE_ALERT", text=body, first_line=fl)
    if re.search(r"CORRE[CÇ][AÃ]O\s*/\s*CORRECTION", body, re.I):
        return _match("OPS_CORRECAO", text=body, first_line=fl)
    if re.search(r"JANELA\s+PRIME", fl, re.I):
        return _match("OPS_JANELA_PRIME", text=body, first_line=fl)

    # ── OPS ─────────────────────────────────────────────────────────────────
    if re.search(r"LOSS\s+COOLDOWN", body, re.I):
        return _match("OPS_LOSS_COOLDOWN", text=body, first_line=fl)
    if re.search(r"SINAL\s+SE\s+FORMANDO", body, re.I):
        return _match("OPS_PREALERT_FORMING", text=body, first_line=fl)
    if re.search(r"DUPLO\s+ELITE\s+ANALISANDO", body, re.I):
        return _match("OPS_DUPLO_ELITE", text=body, first_line=fl)
    if re.search(r"TRIPLE\s+LOCK", body, re.I):
        return _match("OPS_TRIPLE_LOCK", text=body, first_line=fl)
    if re.search(r"SEQU[EÊ]NCIA\s+QUENTE", body, re.I):
        return _match("OPS_SEQ_QUENTE", text=body, first_line=fl)
    if re.search(r"SEQU[EÊ]NCIA\s+FRIA", body, re.I):
        return _match("OPS_SEQ_FRIA", text=body, first_line=fl)
    if re.search(r"SEQU[EÊ]NCIA\s+DE\s+EMPATES", body, re.I):
        return _match("OPS_SEQ_EMPATES", text=body, first_line=fl)
    if re.search(r"⚡⚡⚡\s*SINAL\s+FORMANDO", body, re.I):
        return _match("OPS_PREALERT_3BOLT", text=body, first_line=fl)
    if re.search(r"AUDIT\s*360", body, re.I):
        return _match("OPS_AUDIT_360", text=body, first_line=fl)
    if re.search(r"CAMADAS\s+DO\s+DIA", body, re.I):
        return _match("OPS_CAMADAS_DO_DIA", text=body, first_line=fl)
    if re.search(r"SEQU[EÊ]NCIA\s+\d+x", fl, re.I) or (
        "🎰" in fl and re.search(r"VERMELHO|AZUL", fl, re.I)
    ):
        return _match("OPS_STREAK_BANNER", text=body, first_line=fl)
    if re.search(r"DIVERG[EÊ]NCIA\s+DE\s+SALAS", body, re.I):
        return _match("OPS_DIVERGENCIA_SALAS", text=body, first_line=fl)
    if re.search(r"ELITE\s+ANALISANDO", fl, re.I):
        return _match("OPS_ELITE_ANALISANDO", text=body, first_line=fl)

    # ── Internal log lines / source literals (never Telegram cards) ─────────
    # Bracketed gate tags, e.g. "[PlatDupeGuard]", "[AccumHold]", "[wl_x/DISABLED]".
    # Truncated literals may lack the closing bracket, so allow an open tag too.
    if re.search(r"\[[A-Za-z0-9_][A-Za-z0-9_/\-]*(?:\]|/|:|\s|$)", fl):
        if re.search(r"DISABLED|→\s*ALLOW|bypassed", body, re.I):
            return _match("OPS_GATE_ALLOW_LOG", text=body, first_line=fl)
        return _match("OPS_GATE_BLOCK_LOG", text=body, first_line=fl)
    if re.search(r"downgrad(?:e|ing)\s+to\s+[A-Z_]+", body, re.I):
        return _match("OPS_KIND_DOWNGRADE_LOG", text=body, first_line=fl)
    if re.search(
        r"MomentumBlock|CautionBlock|RoomHourGate|GoldenHourGate|"
        r"unrescuable|blocked at|saved=\d+|blocked_wins=\d+|shadow WR|"
        r"_ALWAYS_FIRES|exempt from|kept elite votes|"
        # CamelCase gate/guard/cooldown identifiers + verdict verbs
        r"\b[A-Z][A-Za-z0-9]*(?:Gate|Block|Guard|Cooldown|Hold|Fallback)\b|"
        r"\bBLOCK:|\bEXEMPTED\b|stripped\s+result\s+room|"
        r"downgrade|upgrade:|conf=|rooms=|only\s+\d+\s+(?:pts|rooms)|"
        r"pending\s+guard|standalone\s+for|blocked\s+for|"
        # "GOLDEN: only", "PLATINUM stripped", "GOLDEN G1 gate:", "SoloRoomWindow:"
        r"\b(?:GOLDEN|PLATINUM|SOLO[_\s]?ELITE|SEQUENCE|FLASH|EMERGING)\s*:?\s*"
        r"(?:only\b|stripped\b|auto-|G[123]\s+gate\b)|"
        r"\+FullCoalition|Window:|Filter-[A-Z]\b|PerfectG0|"
        r"Pipeline\s+Independente",
        body,
        re.I,
    ):
        if re.search(r"DISABLED|→\s*ALLOW|EXEMPTED|✅\s*Sent|bypassed", body, re.I):
            return _match("OPS_GATE_ALLOW_LOG", text=body, first_line=fl)
        return _match("OPS_GATE_BLOCK_LOG", text=body, first_line=fl)
    # Body continuation / footer fragments (not headers)
    if (
        re.match(r"^\s*(?:└|├|│|\||more\s+pts|_[A-Za-z])", fl)
        or re.fullmatch(r"[\s|]*Evolution\s+Bac\s+Bo[\s|]*", fl, re.I)
        or re.match(r"^\s*\*\*(?:APOSTAR|ENTRAR|BET)\s*:", fl, re.I)
    ):
        return _match("CARD_BODY_LINE", text=body, first_line=fl)
    # Source literals: quoted kind lists, ternaries, dict fragments
    if re.search(
        r'"\s*,\s*"|"\s*:\s*"|__import__|\bif\s+\w+\s*==|else\s+"|'
        r"_mom\[|w_color|_utc_hour|_is_flash_early|_g0wr|\\s\*|"
        r'\(\d+,\s*"|;\s*\w+\s*=\s*"|"\s*/\s*"|"\s*:\s*\d+',
        body,
    ):
        return _match("CODE_FRAGMENT", text=body, first_line=fl)
    # Bare kind words / outcome labels lifted out of source (not cards)
    if re.fullmatch(
        r"[✅❌⚪🟡🔵🔴\s]*(?:GOLDEN|SOLO[_\s]?ELITE|SEQUENCE|PLATINUM|FLASH|"
        r"ULTRA[_\s]?TIE|EMERGING|ganhou|perdeu|empatou|GANHOU|PERDEU|EMPATOU)"
        r"[!\s\"']*",
        (fl or "").strip(),
        re.I,
    ):
        return _match("CODE_FRAGMENT", text=body, first_line=fl)

    # Fallback: DB signal_kind only (no recognizable Telegram skin)
    if hint_kind:
        family_id = f"SIGNAL_KIND_{hint_kind}"
        return SkinMatch(
            family_id=family_id,
            role=ROLE_FIRE,
            kind=hint_kind,
            lane=LANE_MONEY,
            clock_n=None,
            gate_keys=(family_id, hint_kind),
            first_line=fl,
            era=None,
            label=f"DB signal_kind {hint_kind}",
            notes="No Telegram skin header matched; bridging via signal_kind",
        )

    return SkinMatch(
        family_id="UNKNOWN",
        role=ROLE_UNKNOWN,
        kind=None,
        lane=None,
        clock_n=None,
        gate_keys=("UNKNOWN",),
        first_line=fl,
        era=None,
        label="unknown",
    )


def skin_blocked_by_registry(registry: Any, match: SkinMatch) -> bool:
    """True if any of match.gate_keys is disabled or retired on the registry."""
    for key in match.gate_keys:
        try:
            if registry.is_disabled(key) or registry.is_retired(key):
                return True
        except (TypeError, ValueError):
            continue
    return False


def product_skin_families() -> Tuple[SkinFamily, ...]:
    """Families that matter for ENTER→RESULT product gating (excludes noise)."""
    return tuple(f for f in SKIN_FAMILIES if f.family_id != "ROOM_RELAY")


def family_ids() -> Tuple[str, ...]:
    return tuple(f.family_id for f in SKIN_FAMILIES)


# Self-test vectors (no Telegram). Kept here so Replit/CI can import them.
SELFTEST_CASES: Sequence[Tuple[str, str, Optional[str]]] = (
    ("🟢 BacBo Royal UserBot ONLINE 🟢\n6 salas", "ONLINE_BANNER", None),
    ("🏆 SIGNAL CONFIRMED — ENTER NOW 🏆\nRooms in consensus", "FIRE_CONFIRMED_ENTER", None),
    ("💎 SOLO ELITE SIGNAL 💎\n⚡ ENTER NOW", "FIRE_SOLO_ELITE_ENTER", "SOLO_ELITE"),
    ("🏆 GOLDEN SIGNAL — ENTER NOW 🏆", "FIRE_GOLDEN_ENTER", "GOLDEN"),
    ("📊 SEQUENCE SIGNAL — ENTER NOW 📊", "FIRE_SEQUENCE_ENTER", "SEQUENCE"),
    ("💠 PLATINUM SIGNAL — PAR DE OURO", "FIRE_PLATINUM_ENTER", "PLATINUM"),
    ("✅ WIN — SOLO_ELITE\nG0 — Acertou", "RESULT_WIN_TIER", "SOLO_ELITE"),
    ("❌ LOSS — GOLDEN", "RESULT_LOSS_TIER", "GOLDEN"),
    ("🔁 GALE 1 — Entre novamente", "FIRE_GALE_ENTRE_NOVAMENTE", None),
    (
        "♻️ GALE 1 — RETENTATIVA (1 room at G1)\n💎 SOLO ELITE SIGNAL 💎",
        "FIRE_GALE_RETENTATIVA",
        "SOLO_ELITE",
    ),
    (
        "🟡 EMPATE — SOLO_ELITE\nResultado empatado — proteção ativada!",
        "RESULT_EMPATE",
        "SOLO_ELITE",
    ),
    ("🟡 EMPATE — SEQUENCE", "RESULT_EMPATE", "SEQUENCE"),
    ("JANELA: 11s para apostar\n💎 SOLO ELITE", "FIRE_JANELA_TIMED", "SOLO_ELITE"),
    ("JANELA: 37s para apostar\n🏆 GOLDEN", "FIRE_JANELA_TIMED", "GOLDEN"),
    ("🟡 ULTRA TIE — EMPATE CONFIRMADO", "FIRE_ULTRA_TIE", "ULTRA_TIE"),
    ("⚡ SOLO ELITE — APOSTAR AGORA", "FIRE_SOLO_APOSTAR", "SOLO_ELITE"),
    ("⚡ FLASH — APOSTAR AGORA", "FIRE_FLASH_APOSTAR", "FLASH"),
    (
        "🔵 SIGNAL #51250 -- SOLO_ELITE red | rooms: @x",
        "FIRE_COMPACT_HASH",
        "SOLO_ELITE",
    ),
    ("✅ WIN #51252 G0", "RESULT_COMPACT_WIN_HASH", None),
    ("📡 @FooBar — tip\nANALISANDO mesa", "ROOM_RELAY", None),
)
