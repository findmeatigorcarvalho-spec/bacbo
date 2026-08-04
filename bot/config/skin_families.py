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
)

_FAMILY_BY_ID: Dict[str, SkinFamily] = {f.family_id: f for f in SKIN_FAMILIES}


def all_skin_families() -> Tuple[SkinFamily, ...]:
    return SKIN_FAMILIES


def get_skin_family(family_id: str) -> Optional[SkinFamily]:
    return _FAMILY_BY_ID.get((family_id or "").strip())


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
    if re.search(r"PREPARE\s+O\s+G1", fl, re.I):
        return _match("FIRE_PREPARE_G1", text=body, first_line=fl, kind=hint_kind)
    if re.search(r"SEQU[EÊ]NCIA\s*—\s*ENTER\s+NOW", fl, re.I):
        return _match("FIRE_SEQUENCIA_ENTER_NOW", text=body, first_line=fl, kind="SEQUENCE")

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
