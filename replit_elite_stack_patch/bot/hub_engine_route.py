#!/usr/bin/env python3
"""
hub_engine_route.py — route bacbo engine send() to Gunique vs money.

Engine owns the original rich skins. Outbox must NOT duplicate those fires.
This module picks the Telegram TARGET for each engine message when HUB_MAX=1.

Env:
  HUB_MAX=1
  HUB_ENGINE_ROUTE=1          (default on when HUB_MAX)
  HUB_GUNIQUE_FIRST=1
  HUB_G1_APEX_FIRST=1
  PROFIT_CHAT_BUNDLE=1
  TELEGRAM_PRIMARY_PEER / TELEGRAM_TARGET_PEER  APEX (#1 UNIQUE_g1)
  TELEGRAM_EXCLUDE_PEERS=Mr_iv4,6774605259
  TELEGRAM_GUNIQUE_PEER_ID   numeric preferred (5855678138)
  TELEGRAM_COUNTDOWN_PEER / GUNIQUE_PEER  username fallback (same APEX)
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
LAST_DEST = DATA / "hub_engine_last_dest.json"
GUNIQUE_CACHE = DATA / "telegram_gunique_entity.json"

_FIRE_HINT = re.compile(
    r"(ENTER NOW|SEQU[EÊ]NCIA|GOLDEN SIGNAL|SOLO ELITE|FLASH SIGNAL|"
    r"APOSTE AGORA|JANELA|COUNTDOWN|Sinal Retido|BAC BO SIGNAL|"
    r"PLATINUM|CONFIRMED ENTRY)",
    re.I,
)
_OPS_HINT = re.compile(
    r"(OUTBOX ONLINE|UserBot ONLINE|GRADE DE JOGO|AVISO DE EMPATE|"
    r"SEQU[EÊ]NCIA FRIA|SEQU[EÊ]NCIA QUENTE|BacBo Royal —|"
    r"H\d+\s*UTC|Briefing completo|Aguardando sinais|"
    r"MUSEUM |LUXURY TEST PING)",
    re.I,
)
_RESULT_HINT = re.compile(
    r"(G0 WIN|G1 WIN|G2 WIN|G0 LOSS|G1 LOSS|G2 LOSS|GANHOU|PERDEU|"
    r"RESUMIDO FORENSE|TRUTH THIS ROUND|G1 EXPIROU|G2 MISS|"
    r"WIN G1|WIN G2|✅ WIN|❌ LOSS)",
    re.I,
)
_TRUST_FIRE = re.compile(
    r"(GOLDEN SIGNAL|SOLO ELITE|SEQU[EÊ]NCIA|FLASH SIGNAL|"
    r"PLATINUM|JANELA\s*:|🟢\s*\d+s|APOSTE AGORA)",
    re.I,
)


def hub_route_enabled() -> bool:
    if os.environ.get("HUB_MAX", "0").strip().lower() in {"0", "false", "no", "off"}:
        return False
    return os.environ.get("HUB_ENGINE_ROUTE", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def _clean(raw: str | None) -> str:
    return (raw or "").strip().strip('"').strip("'").lstrip("@")


def money_peer() -> str:
    """Primary money/apex peer — UNIQUE_g1 (Mr_iv4 removed from equation)."""
    try:
        from bot.config.profit_chat_bundle import is_excluded, primary_peer, primary_peer_id

        pid = primary_peer_id()
        if pid and not is_excluded(pid):
            return pid
        return primary_peer()
    except Exception:
        pass
    raw = _clean(
        os.environ.get("TELEGRAM_PRIMARY_PEER")
        or os.environ.get("TELEGRAM_TARGET_PEER")
        or os.environ.get("TARGET_PEER_ID")
        or "UNIQUE_g1"
    )
    if raw in {"6774605259", "Mr_iv4", "mr_iv4"}:
        return "5855678138"  # UNIQUE_g1 id
    return raw or "UNIQUE_g1"


def gunique_peer() -> str:
    """Same APEX home as money under Profit Chat Bundle (g1 is #1)."""
    for key in (
        "TELEGRAM_GUNIQUE_PEER_ID",
        "GUNIQUE_PEER_ID",
        "TELEGRAM_COUNTDOWN_PEER_ID",
        "TELEGRAM_PRIMARY_PEER_ID",
    ):
        raw = _clean(os.environ.get(key))
        if raw and raw.lstrip("-").isdigit() and raw not in {"6774605259"}:
            return raw
    if GUNIQUE_CACHE.exists():
        try:
            data = json.loads(GUNIQUE_CACHE.read_text(encoding="utf-8"))
            if data.get("id") is not None:
                gid = str(int(data["id"]))
                if gid != "6774605259":
                    return gid
        except Exception:
            pass
    return _clean(
        os.environ.get("TELEGRAM_COUNTDOWN_PEER")
        or os.environ.get("TELEGRAM_PRIMARY_PEER")
        or os.environ.get("GUNIQUE_PEER")
        or "UNIQUE_g1"
    ) or "UNIQUE_g1"


def _as_target(peer: str) -> Any:
    p = _clean(peer)
    if not p:
        return p
    if p.lstrip("-").isdigit():
        return int(p)
    return f"@{p}"


def _save_last(dest: Any, *, role: str, reason: str) -> None:
    try:
        DATA.mkdir(parents=True, exist_ok=True)
        LAST_DEST.write_text(
            json.dumps({"dest": str(dest), "role": role, "reason": reason}),
            encoding="utf-8",
        )
    except Exception:
        pass


def _load_last_target() -> Any | None:
    try:
        if not LAST_DEST.exists():
            return None
        d = json.loads(LAST_DEST.read_text(encoding="utf-8"))
        v = d.get("dest")
        if v is None:
            return None
        return _as_target(str(v))
    except Exception:
        return None


def _is_result(body: str) -> bool:
    if _RESULT_HINT.search(body) and not _FIRE_HINT.search(body):
        return True
    try:
        from dual_lane_router import ROLE_RESULT, classify_role

        return classify_role(text=body) == ROLE_RESULT
    except Exception:
        return bool(_RESULT_HINT.search(body))


def pick_target_for_text(text: str | None) -> tuple[Any | None, str]:
    """
    Returns (target_or_None, reason).
    None target = leave engine TARGET unchanged.
    When a skin family is registry-blocked, reason starts with ``skin_blocked:``
    (send wrappers should drop the message — see lux_send_config_bind).
    """
    if not hub_route_enabled():
        return None, "route_off"
    body = str(text or "")
    if not body.strip():
        return None, "empty"

    try:
        from skin_gate import evaluate_send_gate

        gate = evaluate_send_gate(body)
        if gate.blocked:
            return None, f"skin_blocked:{gate.family_id}:{','.join(gate.matched_keys)}"
    except Exception:
        pass

    # Profit Chat Bundle: UNIQUE_g1 APEX is #1 (Mr_iv4 removed).
    apex = _as_target(gunique_peer() or money_peer())
    try:
        from bot.config.profit_chat_bundle import peer_for_signal

        peer, why = peer_for_signal(
            body, is_result=_is_result(body), role="RESULT" if _is_result(body) else "FIRE"
        )
        if peer:
            dest = _as_target(str(peer))
            if _is_result(body):
                last = _load_last_target()
                return (last if last is not None else dest), f"bundle_result:{why}"
            if _FIRE_HINT.search(body) or _TRUST_FIRE.search(body):
                _save_last(dest, role="FIRE", reason=f"bundle:{why}")
            return dest, f"bundle:{why}"
    except Exception:
        pass

    # Results glue to last FIRE chat (engine path has no signal_id).
    if _is_result(body):
        last = _load_last_target()
        return (last if last is not None else apex), "result→parent"

    # Soft-cap spill via chat_router for FIRE/ops (never delay).
    try:
        from chat_router import route_card

        target = route_card(body)
        if getattr(target, "suppressed", False):
            return apex, f"router_suppressed:{getattr(target, 'reason', '')}"
        peer = getattr(target, "peer", None)
        if peer and str(peer) not in {"6774605259", "Mr_iv4", "mr_iv4"}:
            dest = _as_target(str(peer))
            reason = (
                f"skyscraper:{getattr(target, 'reason', '')}:"
                f"{getattr(target, 'shelf_id', '')}"
            )
            if getattr(target, "role", "") == "FIRE" or _FIRE_HINT.search(body):
                _save_last(dest, role="FIRE", reason=reason)
            return dest, reason
    except Exception:
        pass

    # Chat shelves → APEX / PRECISION peers (never Mr_iv4)
    try:
        from chat_shelves import SHELF_SINK, resolve_shelf

        shelf = resolve_shelf(body)
        if shelf.shelf_id == SHELF_SINK:
            return apex, f"shelf_sink:{shelf.family_id}"
        peer = getattr(shelf, "peer", None) or "UNIQUE_g1"
        if str(peer) in {"6774605259", "Mr_iv4", "mr_iv4"}:
            peer = "UNIQUE_g1"
        dest = _as_target(str(peer))
        if shelf.role == "FIRE":
            _save_last(dest, role="FIRE", reason=f"shelf:{shelf.shelf_id}")
        return dest, f"shelf:{shelf.shelf_id}:{shelf.family_id}"
    except Exception:
        pass

    if _OPS_HINT.search(body) and not re.search(
        r"(APOSTE AGORA|ENTER NOW|GOLDEN SIGNAL|FLASH SIGNAL|SOLO ELITE)",
        body,
        re.I,
    ):
        return apex, "ops→APEX"

    if _TRUST_FIRE.search(body) or _FIRE_HINT.search(body):
        _save_last(apex, role="FIRE", reason="apex_first→UNIQUE_g1")
        return apex, "apex_first→UNIQUE_g1"

    _save_last(apex, role="FIRE", reason="default→APEX")
    return apex, "default→APEX"


def apply_target_to_config(cfg: Any, target: Any) -> Any:
    """Set config.TARGET for one send; return previous value."""
    prev = getattr(cfg, "TARGET", None)
    try:
        cfg.TARGET = target
    except Exception:
        pass
    return prev
