"""bot.config package — credentials for bacbo + Profit Family AI modules.

On Replit, PYTHONPATH includes `bot/`, so `from config import API_ID` resolves here.
This file MUST export Telegram credentials (from env/secrets) AND the skin/shelf APIs.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

__all__: list[str] = []

# ── Credentials (bacbo_royal_complete needs these) ───────────────────────────
def _load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    try:
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            if line.startswith("export "):
                line = line[len("export ") :].strip()
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val
    except Exception:
        pass


_ROOT = Path(__file__).resolve().parents[2]  # .../workspace when bot/config/
if not (_ROOT / "bacbo_royal_complete.py").is_file():
    _ROOT = Path("/home/runner/workspace")
for _p in (
    _ROOT / ".env",
    _ROOT / "luxury_building.env",
    _ROOT / "bot" / "data" / "profit_skyscraper.env",
    Path("/home/runner/workspace/.env"),
    Path("/home/runner/workspace/luxury_building.env"),
):
    _load_dotenv(_p)


def _env(*keys: str, default: str = "") -> str:
    for k in keys:
        v = (os.environ.get(k) or "").strip().strip('"').strip("'")
        if v:
            return v
    return default


# Canonical names bacbo expects
API_ID = _env("TELEGRAM_API_ID", "API_ID")
API_HASH = _env("TELEGRAM_API_HASH", "API_HASH")
try:
    API_ID = int(API_ID) if str(API_ID).lstrip("-").isdigit() else API_ID
except Exception:
    pass

TARGET = _env(
    "TELEGRAM_PRIMARY_PEER",
    "TELEGRAM_TARGET_PEER",
    "TARGET_PEER_ID",
    "TARGET",
    default="UNIQUE_g1",
)
# Never keep excluded Mr_iv4 as TARGET after Profit Chat Bundle pivot
if str(TARGET).lstrip("@") in {"Mr_iv4", "mr_iv4", "6774605259"}:
    TARGET = "UNIQUE_g1"

TELEGRAM_API_ID = API_ID
TELEGRAM_API_HASH = API_HASH
TELEGRAM_TARGET_PEER = TARGET
TELEGRAM_PRIMARY_PEER = _env("TELEGRAM_PRIMARY_PEER", default="UNIQUE_g1")
TELEGRAM_COUNTDOWN_PEER = _env("TELEGRAM_COUNTDOWN_PEER", "GUNIQUE_PEER", default="UNIQUE_g1")
TELEGRAM_SESSION_STRING = _env(
    "TELEGRAM_SESSION_STRING",
    "TELEGRAM_STRING_SESSION",
    "STRING_SESSION",
    "SESSION_STRING",
)
PHONE = _env("TELEGRAM_PHONE", "PHONE")
BOT_TOKEN = _env("TELEGRAM_BOT_TOKEN", "BOT_TOKEN")

# Materialize session file if secret present (bacbo forks often read the file)
_sess_file = _ROOT / ".telegram_session_string"
if len(TELEGRAM_SESSION_STRING) > 50:
    try:
        if not _sess_file.exists() or len(_sess_file.read_text(errors="ignore").strip()) <= 50:
            _sess_file.write_text(TELEGRAM_SESSION_STRING + "\n", encoding="utf-8")
    except Exception:
        pass
elif _sess_file.is_file():
    try:
        _sv = _sess_file.read_text(errors="ignore").strip()
        if len(_sv) > 50:
            TELEGRAM_SESSION_STRING = _sv
            os.environ.setdefault("TELEGRAM_SESSION_STRING", _sv)
    except Exception:
        pass

__all__ += [
    "API_ID",
    "API_HASH",
    "TARGET",
    "TELEGRAM_API_ID",
    "TELEGRAM_API_HASH",
    "TELEGRAM_TARGET_PEER",
    "TELEGRAM_PRIMARY_PEER",
    "TELEGRAM_COUNTDOWN_PEER",
    "TELEGRAM_SESSION_STRING",
    "PHONE",
    "BOT_TOKEN",
]

# ── Package APIs (fail-open) ─────────────────────────────────────────────────
try:
    from bot.config.registry import EngineGateRegistry

    __all__.append("EngineGateRegistry")
except Exception:
    try:
        from .registry import EngineGateRegistry  # type: ignore

        __all__.append("EngineGateRegistry")
    except Exception:
        pass

try:
    from bot.config.skin_families import (
        SKIN_FAMILIES,
        SkinFamily,
        SkinMatch,
        all_skin_families,
        classify_telegram_skin,
        family_ids,
        gate_keys_for,
        product_skin_families,
        skin_blocked_by_registry,
    )

    __all__ += [
        "SKIN_FAMILIES",
        "SkinFamily",
        "SkinMatch",
        "all_skin_families",
        "classify_telegram_skin",
        "family_ids",
        "gate_keys_for",
        "product_skin_families",
        "skin_blocked_by_registry",
    ]
except Exception:
    try:
        from .skin_families import (  # type: ignore
            SKIN_FAMILIES,
            SkinFamily,
            SkinMatch,
            all_skin_families,
            classify_telegram_skin,
            family_ids,
            gate_keys_for,
            product_skin_families,
            skin_blocked_by_registry,
        )

        __all__ += [
            "SKIN_FAMILIES",
            "SkinFamily",
            "SkinMatch",
            "all_skin_families",
            "classify_telegram_skin",
            "family_ids",
            "gate_keys_for",
            "product_skin_families",
            "skin_blocked_by_registry",
        ]
    except Exception:
        pass

try:
    from bot.config.skin_gate import (
        SendGateDecision,
        evaluate_send_gate,
        should_block_telegram_send,
        skin_gate_enabled,
    )

    __all__ += [
        "SendGateDecision",
        "evaluate_send_gate",
        "should_block_telegram_send",
        "skin_gate_enabled",
    ]
except Exception:
    pass

try:
    from bot.config.chat_shelves import (
        ShelfDecision,
        resolve_shelf,
        shelf_catalog,
        shelf_for_family,
    )

    __all__ += [
        "ShelfDecision",
        "resolve_shelf",
        "shelf_catalog",
        "shelf_for_family",
    ]
except Exception:
    pass

try:
    from bot.config.chat_router import (
        ChatTarget,
        get_router,
        overflow_peers,
        route_card,
    )

    __all__ += [
        "ChatTarget",
        "get_router",
        "overflow_peers",
        "route_card",
    ]
except Exception:
    pass
