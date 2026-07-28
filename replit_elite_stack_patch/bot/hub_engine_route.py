#!/usr/bin/env python3
"""
hub_engine_route.py — route bacbo engine send() to Gunique vs money.

Engine owns the original rich skins. Outbox must NOT duplicate those fires.
This module picks the Telegram TARGET for each engine message when HUB_MAX=1.

Env:
  HUB_MAX=1
  HUB_ENGINE_ROUTE=1          (default on when HUB_MAX)
  HUB_GUNIQUE_FIRST=1
  TELEGRAM_TARGET_PEER       money (#2)
  TELEGRAM_GUNIQUE_PEER_ID   numeric preferred
  TELEGRAM_COUNTDOWN_PEER / GUNIQUE_PEER  username fallback
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
    return _clean(
        os.environ.get("TELEGRAM_TARGET_PEER")
        or os.environ.get("TARGET_PEER_ID")
        or "6774605259"
    ) or "6774605259"


def gunique_peer() -> str:
    for key in (
        "TELEGRAM_GUNIQUE_PEER_ID",
        "GUNIQUE_PEER_ID",
        "TELEGRAM_COUNTDOWN_PEER_ID",
    ):
        raw = _clean(os.environ.get(key))
        if raw and raw.lstrip("-").isdigit():
            return raw
    if GUNIQUE_CACHE.exists():
        try:
            data = json.loads(GUNIQUE_CACHE.read_text(encoding="utf-8"))
            if data.get("id") is not None:
                return str(int(data["id"]))
        except Exception:
            pass
    return _clean(
        os.environ.get("TELEGRAM_COUNTDOWN_PEER")
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
    """
    if not hub_route_enabled():
        return None, "route_off"
    body = str(text or "")
    if not body.strip():
        return None, "empty"

    money = _as_target(money_peer())
    gunique = _as_target(gunique_peer())
    gunique_first = os.environ.get("HUB_GUNIQUE_FIRST", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }

    # Ops / schedule noise → money (#2). Allow SEQUÊNCIA QUENTE/FRIA without
    # treating them as enter-fires (they share the SEQUÊNCIA token).
    if _OPS_HINT.search(body) and not re.search(
        r"(APOSTE AGORA|ENTER NOW|GOLDEN SIGNAL|FLASH SIGNAL|SOLO ELITE)",
        body,
        re.I,
    ):
        return money, "ops→money"

    if _is_result(body):
        last = _load_last_target()
        return (last if last is not None else money), "result→parent"

    # Timed / countdown fires → Gunique
    try:
        from dual_lane_router import LANE_COUNTDOWN, is_countdown_fire, route_lane

        if is_countdown_fire(text=body) or route_lane(text=body) == LANE_COUNTDOWN:
            _save_last(gunique, role="FIRE", reason="countdown→gunique")
            return gunique, "countdown→gunique"
    except Exception:
        pass

    # Trust-first: original enter skins → Gunique #1
    if gunique_first and (_TRUST_FIRE.search(body) or _FIRE_HINT.search(body)):
        _save_last(gunique, role="FIRE", reason="trust_skin→gunique")
        return gunique, "trust_skin→gunique"

    _save_last(money, role="FIRE", reason="default→money")
    return money, "default→money"


def apply_target_to_config(cfg: Any, target: Any) -> Any:
    """Set config.TARGET for one send; return previous value."""
    prev = getattr(cfg, "TARGET", None)
    try:
        cfg.TARGET = target
    except Exception:
        pass
    return prev
