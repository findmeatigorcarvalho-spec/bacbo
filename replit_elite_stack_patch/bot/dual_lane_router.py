#!/usr/bin/env python3
"""
dual_lane_router.py — TOTAL SEPARATION by card ROLE + fire template family.

NOT a mirror. NOT "any text that mentions seconds."

═══════════════════════════════════════════════════════════════════
SPLIT KEY (locked)
═══════════════════════════════════════════════════════════════════
1) Classify ROLE first: FIRE (color-coming / enter) vs RESULT (outcome).
2) Only FIRE templates choose the Telegram lane.
3) RESULT always inherits the parent FIRE's lane (same chat as the signal).
4) Printed Intervalo on the forensic Apostou→Saiu card IS the outcome timer
   (this family fires as a countdown FIRE). Do not treat Saiu as a finished ball.

LANES (Profit Chat Bundle — Mr_iv4 REMOVED)
─────
MONEY     → UNIQUE_g1 APEX (TELEGRAM_PRIMARY_PEER / TELEGRAM_TARGET_PEER)
  FIRE templates with NO bet-window / janela / Ns-to-hit on the SIGNAL itself.
  Examples: 🏆 GOLDEN SIGNAL — ENTER NOW, rooms consensus, ENTER NOW — N ROOM(S).

COUNTDOWN → UNIQUE_g1 APEX (same #1 chat; sniper precision may spill UNIQUE_g2)
  FIRE templates with CLOCK A — ENTRY WINDOW (Ns to PLACE the bet).
  Examples: JANELA: 1s/11s/17s para apostar, 🟢 1s 🟢, CD_FIRE_TIMER_*,
            Sinal Retido→Liberado + entry window.
  Clock A ≠ Clock C. Clock A is urgency to enter; not “how long until resolve.”
  Each still gets its OWN result cards glued under that fire in the SAME chat.

RESULT families (never lane-select by themselves)
─────────────────────────────────────────────────
  Plain: G0/G1/G2 win/loss, "✅ WIN — SOLO_ELITE", "blue win on G0", forensic resumido
  Ops:   G1 EXPIROU, G2 MISS, session stop — still RESULTS; glue under parent fire
  Forensic Apostou→Saiu Intervalo is the outcome timer on that FIRE family.
  See TIMING_CLOCKS.md + fire_origin.py (COALITION vs SOLO_FACT).
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any


LANE_MONEY = "MONEY"
LANE_COUNTDOWN = "COUNTDOWN"
ROLE_FIRE = "FIRE"
ROLE_RESULT = "RESULT"
ROLE_UNKNOWN = "UNKNOWN"

# Profit Chat Bundle: UNIQUE_g1 is APEX #1 for money + countdown (Mr_iv4 removed).
DEFAULT_MONEY_PEER = os.environ.get("TELEGRAM_PRIMARY_PEER") or os.environ.get(
    "TELEGRAM_TARGET_PEER"
) or "UNIQUE_g1"
DEFAULT_COUNTDOWN_PEER = os.environ.get("TELEGRAM_COUNTDOWN_PEER") or "UNIQUE_g1"

# Persist fire→lane so results follow parent across outbox restarts.
_LANE_STATE = Path(
    os.environ.get(
        "OUTBOX_LANE_STATE",
        str(Path(__file__).resolve().parent / "data" / "outbox_lane_by_signal.json"),
    )
)

# ── RESULT detectors (role first — never treat these as timed FIRES) ─────────
_RESULT_KIND = {
    "RESULT",
    "NORMAL_RESULT",
    "CD_RESULT",
    "CD_RES",
    "FORENSIC_RESULT",
    "G0_WIN",
    "G0_LOSS",
    "G1_WIN",
    "G1_LOSS",
    "G2_WIN",
    "G2_LOSS",
    "G2_MISS",
    "EXPIRE",
    "EXPIRED",
    "G1_EXPIROU",
}
_RESULT_BODY = re.compile(
    r"(?is)("
    r"RESUMIDO\s+FORENSE|"
    r"🔔\s*[✅❌🟡].*(GANHOU|PERDEU|G0\s*WIN|LOSS|TIE)|"
    r"✅\s*WIN\s*—|"
    r"❌\s*LOSS\s*—|"
    r"GANHOU\s+NO\s+G[0-3]|"
    r"G[0-3]\s*—\s*(Acertou|Recuperado)|"
    r"G1\s+EXPIROU|"
    r"G2\s+MISS|"
    r"PERDA\s+TOTAL|"
    r"⏱\s*Intervalo\s*:|"
    r"Apostou\s*:|"
    r"Sinal\s+#\d+\s+encerrado|"
    r"Aguarde\s+o\s+próximo\s+sinal|"
    r"PASSO\s+A\s+PASSO\s*—\s*O\s+QUE\s+FAZER\s+AGORA"
    r")"
)
_RESULT_TEMPLATE_PREFIX = ("CD_RES_", "RESULT_", "RES_", "FORENSIC_")

# ── TIMED FIRE detectors (timing ON the SIGNAL of when to bet / hit) ─────────
_CD_FIRE_KINDS = {
    "COUNTDOWN",
    "COUNTDOWN_SIGNAL",
    "COUNTDOWN_SIGNAL_FIRE",
    "CD_FIRE",
    "CD_TIMER",
    "CD_FIRE_TIMER_BRT_EDT_APOSTAR",
    "CD_FIRE_QUANTUM_LOCK",
    "CD_FIRE_RUSH_NS_LEFT",
    "TIMED_FIRE",
    "WINDOW_FIRE",
    "JANELA",
}
_TIMED_FIRE_BODY = re.compile(
    r"(?is)("
    r"JANELA\s*:\s*\d+\s*s|"
    r"\d{1,3}\s*s\s+para\s+apostar|"
    r"🟢\s*\d{1,3}\s*s\s*🟢|"
    r"Sinal\s+Retido\s*→\s*Liberado|"
    r"CD_FIRE_|"
    r"COUNTDOWN_SIGNAL|"
    r"\bcountdown\b.*\b(apostar|signal|sinal)\b|"
    r"⏳\s*\d{1,3}\s*s|"
    r"em\s+\d{1,3}\s*(s|sec|secs|seg|segundos?|seconds?)\s+(para|left|restam)"
    r")"
)
# Explicit money / no-timer fires
_MONEY_FIRE_BODY = re.compile(
    r"(?is)("
    r"GOLDEN\s+SIGNAL\s*—\s*ENTER\s+NOW|"
    r"ENTER\s+NOW\s*—\s*\d+\s*ROOM|"
    r"Rooms?\s+in\s+consensus|"
    r"CONFIRMED\s+ENTRY|"
    r"sem\s+timer|without\s+timer|no\s+countdown|sem\s+countdown"
    r")"
)
_MONEY_KINDS = {
    "GOLDEN",
    "PLATINUM",
    "SEQUENCE",
    "SOLO_ELITE",
    "COALITION",
    "CONSENSUS",
    "ENTER_NOW",
}


def _norm_peer(raw: str | None) -> str | None:
    if not raw:
        return None
    s = str(raw).strip()
    if not s:
        return None
    if s.startswith("@"):
        s = s[1:]
    return s


def classify_role(
    *,
    text: str | None = None,
    signal_kind: str | None = None,
    card_type: str | None = None,
    meta: dict[str, Any] | None = None,
) -> str:
    """FIRE | RESULT | UNKNOWN — RESULT wins over naive 'has seconds' heuristics."""
    meta = meta or {}
    kind = (signal_kind or meta.get("signal_kind") or meta.get("kind") or "").strip().upper()
    ctype = (card_type or meta.get("card_type") or meta.get("template") or "").strip().upper()
    role_hint = str(meta.get("role") or meta.get("card_role") or "").strip().upper()
    if role_hint in (ROLE_FIRE, ROLE_RESULT):
        return role_hint
    if kind in _RESULT_KIND or ctype in _RESULT_KIND:
        return ROLE_RESULT
    if any(ctype.startswith(p) for p in _RESULT_TEMPLATE_PREFIX):
        return ROLE_RESULT
    if meta.get("is_result") in (1, True, "1", "true", "yes"):
        return ROLE_RESULT
    if meta.get("is_fire") in (1, True, "1", "true", "yes"):
        return ROLE_FIRE
    body = str(text or meta.get("text") or meta.get("card_text") or "")
    if body and _RESULT_BODY.search(body):
        try:
            from sequence_family_wake import forensic_is_live_fire

            if forensic_is_live_fire(body) and meta.get("is_result") not in (
                1,
                True,
                "1",
                "true",
                "yes",
            ):
                return ROLE_FIRE
        except Exception:
            pass
        # Forensic / win-loss skins are results even if they also say Intervalo Ns
        return ROLE_RESULT
    if kind in _CD_FIRE_KINDS or ctype in _CD_FIRE_KINDS or ctype.startswith("CD_FIRE"):
        return ROLE_FIRE
    if kind in _MONEY_KINDS or (body and _MONEY_FIRE_BODY.search(body)):
        return ROLE_FIRE
    if body and _TIMED_FIRE_BODY.search(body):
        return ROLE_FIRE
    if kind or ctype or body:
        return ROLE_FIRE  # default unknown engine rows = fire candidates
    return ROLE_UNKNOWN


def is_countdown_fire(
    *,
    text: str | None = None,
    signal_kind: str | None = None,
    card_type: str | None = None,
    meta: dict[str, Any] | None = None,
) -> bool:
    """True ONLY when the SIGNAL FIRE itself carries bet-window / hit timing."""
    meta = meta or {}
    if classify_role(
        text=text, signal_kind=signal_kind, card_type=card_type, meta=meta
    ) == ROLE_RESULT:
        return False  # Intervalo on results is reporting, not lane selection

    kind = (signal_kind or meta.get("signal_kind") or meta.get("kind") or "").strip().upper()
    ctype = (card_type or meta.get("card_type") or meta.get("template") or "").strip().upper()
    if kind in _CD_FIRE_KINDS or ctype in _CD_FIRE_KINDS:
        return True
    if ctype.startswith("CD_FIRE") or "COUNTDOWN_SIGNAL" in ctype:
        return True
    if str(meta.get("lane") or "").strip().upper() == LANE_COUNTDOWN:
        return True
    if meta.get("has_countdown_seconds") in (1, True, "1", "true", "yes"):
        return True
    if meta.get("has_bet_window") in (1, True, "1", "true", "yes"):
        return True

    body = str(text or meta.get("text") or meta.get("card_text") or "")
    if body and _MONEY_FIRE_BODY.search(body) and not _TIMED_FIRE_BODY.search(body):
        return False
    if body and _TIMED_FIRE_BODY.search(body):
        return True
    return False


def route_lane(
    *,
    text: str | None = None,
    signal_kind: str | None = None,
    card_type: str | None = None,
    meta: dict[str, Any] | None = None,
    parent_lane: str | None = None,
) -> str:
    """
    FIRE → MONEY or COUNTDOWN by template family.
    RESULT → parent_lane if known, else MONEY (safe default; prefer persist_lane).
    """
    role = classify_role(
        text=text, signal_kind=signal_kind, card_type=card_type, meta=meta
    )
    if role == ROLE_RESULT:
        pl = (parent_lane or (meta or {}).get("parent_lane") or "").strip().upper()
        if pl in (LANE_MONEY, LANE_COUNTDOWN):
            return pl
        return LANE_MONEY
    return (
        LANE_COUNTDOWN
        if is_countdown_fire(
            text=text, signal_kind=signal_kind, card_type=card_type, meta=meta
        )
        else LANE_MONEY
    )


def peer_for_lane(lane: str) -> str | None:
    lane = (lane or LANE_MONEY).upper()
    if lane == LANE_COUNTDOWN:
        peer = _norm_peer(
            os.environ.get("TELEGRAM_COUNTDOWN_PEER")
            or os.environ.get("TELEGRAM_PRIMARY_PEER")
            or os.environ.get("GUNIQUE_PEER")
            or os.environ.get("TELEGRAM_GUNIQUE_PEER")
            or DEFAULT_COUNTDOWN_PEER
        )
    else:
        peer = _norm_peer(
            os.environ.get("TELEGRAM_PRIMARY_PEER")
            or os.environ.get("TELEGRAM_TARGET_PEER")
            or os.environ.get("TARGET_PEER_ID")
            or DEFAULT_MONEY_PEER
        )
    # Mr_iv4 removed from live equation — always APEX
    if peer and peer.lstrip("@") in {"6774605259", "Mr_iv4", "mr_iv4"}:
        return "UNIQUE_g1"
    return peer


def route_peer(
    *,
    text: str | None = None,
    signal_kind: str | None = None,
    card_type: str | None = None,
    meta: dict[str, Any] | None = None,
    parent_lane: str | None = None,
) -> dict[str, Any]:
    role = classify_role(
        text=text, signal_kind=signal_kind, card_type=card_type, meta=meta
    )
    lane = route_lane(
        text=text,
        signal_kind=signal_kind,
        card_type=card_type,
        meta=meta,
        parent_lane=parent_lane,
    )
    peer = peer_for_lane(lane)
    return {
        "role": role,
        "lane": lane,
        "peer": peer,
        "peer_ready": bool(peer),
        "coalition": lane == LANE_MONEY and role != ROLE_RESULT,
        "glue_result_under_fire": True,
        "mirror": False,
        "note": (
            "RESULT → same chat as parent fire"
            if role == ROLE_RESULT
            else (
                f"FIRE money/coalition → @{peer} APEX (Mr_iv4 excluded)"
                if lane == LANE_MONEY
                else f"FIRE timed/janela/countdown → @{peer} APEX"
            )
        ),
    }


# ── Persist fire lane so results never re-classify by Intervalo text ─────────

def _load_lane_map() -> dict[str, str]:
    try:
        if _LANE_STATE.exists():
            data = json.loads(_LANE_STATE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return {str(k): str(v).upper() for k, v in data.items()}
    except Exception:
        pass
    return {}


def _save_lane_map(m: dict[str, str]) -> None:
    try:
        _LANE_STATE.parent.mkdir(parents=True, exist_ok=True)
        # Cap growth — keep last 20k ids
        if len(m) > 20000:
            keys = sorted(m.keys(), key=lambda x: int(x) if str(x).isdigit() else 0)
            m = {k: m[k] for k in keys[-20000:]}
        _LANE_STATE.write_text(json.dumps(m), encoding="utf-8")
    except Exception:
        pass


def persist_fire_lane(signal_id: int | str, lane: str) -> None:
    lane = (lane or LANE_MONEY).upper()
    if lane not in (LANE_MONEY, LANE_COUNTDOWN):
        lane = LANE_MONEY
    m = _load_lane_map()
    m[str(signal_id)] = lane
    _save_lane_map(m)


def parent_lane_for(signal_id: int | str) -> str | None:
    m = _load_lane_map()
    v = m.get(str(signal_id))
    if v in (LANE_MONEY, LANE_COUNTDOWN):
        return v
    return None


def classify_card(
    *,
    text: str | None = None,
    signal_kind: str | None = None,
    card_type: str | None = None,
    meta: dict[str, Any] | None = None,
    signal_id: int | str | None = None,
    parent_shelf: str | None = None,
) -> dict[str, Any]:
    """Full classification for audits / outbox (lane + skin + chat shelf)."""
    parent = parent_lane_for(signal_id) if signal_id is not None else None
    info = route_peer(
        text=text,
        signal_kind=signal_kind,
        card_type=card_type,
        meta=meta,
        parent_lane=parent,
    )
    info["signal_id"] = signal_id
    info["parent_lane"] = parent
    try:
        from skin_gate import evaluate_send_gate

        gate = evaluate_send_gate(text, signal_kind=signal_kind, meta=meta)
        info["skin_family"] = gate.family_id
        info["skin_kind"] = gate.kind
        info["skin_gate_keys"] = list(gate.gate_keys)
        info["skin_blocked"] = bool(gate.blocked)
        info["skin_gate_reason"] = gate.reason
    except Exception:
        info["skin_blocked"] = False
    try:
        from chat_shelves import resolve_shelf

        shelf = resolve_shelf(
            text,
            signal_kind=signal_kind,
            meta=meta,
            parent_shelf=parent_shelf,
            parent_lane=parent,
        )
        info["shelf_id"] = shelf.shelf_id
        info["shelf_peer"] = shelf.peer
        info["shelf_band"] = shelf.band_hint
        info["shelf_follow_parent"] = bool(shelf.follow_parent)
        info["shelf_reason"] = shelf.reason
        # Shelf lane wins when it is more specific than dual-lane default
        if shelf.lane and not parent:
            info["lane"] = shelf.lane
            info["peer"] = shelf.peer or info.get("peer")
    except Exception:
        info.setdefault("shelf_id", None)
    return info


if __name__ == "__main__":
    demos = [
        # MONEY FIRE — ENTER NOW, no janela on signal
        {
            "label": "GOLDEN ENTER NOW (money fire)",
            "signal_kind": "GOLDEN",
            "text": (
                "🏆 GOLDEN SIGNAL — ENTER NOW 🏆\n"
                "🎯 Enter: blue\nRooms in consensus (3):\n"
                "⚡ ENTER NOW — 3 ROOM(S) CONFIRMED"
            ),
        },
        # TIMED FIRE — janela on SIGNAL
        {
            "label": "SOLO ELITE 1s JANELA (countdown fire)",
            "signal_kind": "SOLO_ELITE",
            "text": (
                "⏳ Sinal Retido → Liberado\n"
                "🔴 JANELA: 1s para apostar\n"
                "🟢 1s 🟢\n💎 SOLO ELITE — APOSTAR 🔴 VERMELHO"
            ),
        },
        # RESULT with Intervalo — MUST NOT become countdown fire
        {
            "label": "Forensic G0 WIN (result; Intervalo is metadata)",
            "signal_kind": "SEQUENCE",
            "text": (
                "🔵🔵🔵🔵🔵🔵🔵🔵🔵🔵\n"
                "🔔 ✅ GANHOU  ·  #48950\n"
                "🔍 SINAL #48950 — RESUMIDO FORENSE\n"
                "  ⏱ Intervalo: 16.6s\n"
                "  Resultado: ✅ G0 WIN\n"
                "📋 ✅  GANHOU NO G0"
            ),
        },
        # RESULT ops
        {
            "label": "G1 EXPIROU (result ops)",
            "text": "⏰ G1 EXPIROU — VERIFICAR SUA MESA\nPASSO A PASSO — O QUE FAZER AGORA",
        },
        # Classic CD fire kind
        {
            "label": "CD_FIRE_TIMER kind",
            "card_type": "CD_FIRE_TIMER_BRT_EDT_APOSTAR",
            "text": "⏳ 45s apostar agora",
        },
        # Plain short result
        {
            "label": "WIN SOLO_ELITE short",
            "text": "✅ WIN — SOLO_ELITE\n🏆 G0 — Acertou de primeira!",
        },
    ]
    for d in demos:
        label = d.pop("label")
        print(f"\n=== {label} ===")
        print(classify_card(**d))
