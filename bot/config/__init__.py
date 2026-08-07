"""bot.config package — credentials for bacbo + Profit Family AI modules.

On Replit, PYTHONPATH includes `bot/`, so `from config import API_ID` resolves here.
This file MUST export every name bacbo imports from config (API_ID, SESSION_FILE, …).
"""
from __future__ import annotations

import ast
import os
import re
from pathlib import Path
from typing import Any, List

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

# Session paths — bacbo imports SESSION_FILE
_sess_string_path = _ROOT / ".telegram_session_string"
_sess_sqlite_default = _ROOT / "bacbo_royal.session"
SESSION_FILE = _env(
    "TELEGRAM_SESSION_FILE",
    "SESSION_FILE",
    default=str(_sess_sqlite_default),
)
SESSION_PATH = SESSION_FILE
SESSION = SESSION_FILE
STRING_SESSION = TELEGRAM_SESSION_STRING
TELEGRAM_STRING_SESSION = TELEGRAM_SESSION_STRING

# Materialize session string file if secret present
if len(TELEGRAM_SESSION_STRING) > 50:
    try:
        if (
            not _sess_string_path.exists()
            or len(_sess_string_path.read_text(errors="ignore").strip()) <= 50
        ):
            _sess_string_path.write_text(TELEGRAM_SESSION_STRING + "\n", encoding="utf-8")
    except Exception:
        pass
elif _sess_string_path.is_file():
    try:
        _sv = _sess_string_path.read_text(errors="ignore").strip()
        if len(_sv) > 50:
            TELEGRAM_SESSION_STRING = _sv
            STRING_SESSION = _sv
            TELEGRAM_STRING_SESSION = _sv
            os.environ.setdefault("TELEGRAM_SESSION_STRING", _sv)
    except Exception:
        pass

# Extra common aliases bacbo forks use
DB_PATH = _env("BACBO_DB", "DB_PATH", default=str(_ROOT / "bot" / "bacbo.db"))
DATABASE = DB_PATH
DB_FILE = DB_PATH
OWNER_ID = _env("OWNER_ID", "TELEGRAM_OWNER_ID", default="")
ADMIN_ID = OWNER_ID
CHAT_ID = TARGET
PEER = TARGET
GUNIQUE_PEER = TELEGRAM_COUNTDOWN_PEER

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
    "TELEGRAM_STRING_SESSION",
    "STRING_SESSION",
    "SESSION_FILE",
    "SESSION_PATH",
    "SESSION",
    "PHONE",
    "BOT_TOKEN",
    "DB_PATH",
    "DATABASE",
    "DB_FILE",
    "OWNER_ID",
    "ADMIN_ID",
    "CHAT_ID",
    "PEER",
    "GUNIQUE_PEER",
]


def _bacbo_import_names() -> List[str]:
    """Parse `from config import (...)` in bacbo_royal_complete.py."""
    path = _ROOT / "bacbo_royal_complete.py"
    if not path.is_file():
        path = Path("/home/runner/workspace/bacbo_royal_complete.py")
    if not path.is_file():
        return []
    try:
        src = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return []
    # Match first from-config import block (paren or single-line)
    m = re.search(
        r"from\s+config\s+import\s*\((.*?)\)",
        src,
        flags=re.S,
    )
    if not m:
        m = re.search(r"from\s+config\s+import\s+([^\n]+)", src)
        if not m:
            return []
        return [x.strip() for x in m.group(1).split(",") if x.strip() and x.strip() != "*"]
    body = m.group(1)
    names: List[str] = []
    for part in body.split(","):
        part = part.strip()
        if not part or part.startswith("#"):
            continue
        # strip trailing comments / "as" aliases → export the bound name
        part = part.split("#", 1)[0].strip()
        if " as " in part:
            part = part.split(" as ", 1)[-1].strip()
        if part.isidentifier():
            names.append(part)
    return names


def _ensure_bacbo_names() -> None:
    """Fill any name bacbo imports that we don't already define."""
    g = globals()
    defaults = {
        "API_ID": API_ID,
        "API_HASH": API_HASH,
        "TARGET": TARGET,
        "SESSION_FILE": SESSION_FILE,
        "SESSION_PATH": SESSION_FILE,
        "SESSION": SESSION_FILE,
        "STRING_SESSION": TELEGRAM_SESSION_STRING,
        "TELEGRAM_SESSION_STRING": TELEGRAM_SESSION_STRING,
        "PHONE": PHONE,
        "BOT_TOKEN": BOT_TOKEN,
        "DB_PATH": DB_PATH,
        "DATABASE": DB_PATH,
        "OWNER_ID": OWNER_ID,
        "CHAT_ID": TARGET,
        "PEER": TARGET,
    }
    for name in _bacbo_import_names():
        if name in g and g[name] not in (None, ""):
            continue
        if name in defaults:
            g[name] = defaults[name]
        elif name.endswith("_PEER") or name in {"TARGET", "CHAT", "CHAT_ID"}:
            g[name] = TARGET
        elif "SESSION" in name and "STRING" in name:
            g[name] = TELEGRAM_SESSION_STRING
        elif "SESSION" in name:
            g[name] = SESSION_FILE
        elif name in {"API_ID", "TELEGRAM_API_ID"}:
            g[name] = API_ID
        elif name in {"API_HASH", "TELEGRAM_API_HASH"}:
            g[name] = API_HASH
        else:
            # Last resort: empty / env mirror so import succeeds; bacbo may set later
            g[name] = _env(name, default="")
        if name not in __all__:
            __all__.append(name)


_ensure_bacbo_names()


def __getattr__(name: str) -> Any:  # pep 562 — catch late/odd imports
    if name.startswith("_"):
        raise AttributeError(name)
    # Prefer env
    val = _env(name)
    if val != "":
        globals()[name] = val
        return val
    if "SESSION" in name and "STRING" not in name:
        globals()[name] = SESSION_FILE
        return SESSION_FILE
    if "SESSION" in name:
        globals()[name] = TELEGRAM_SESSION_STRING
        return TELEGRAM_SESSION_STRING
    if name in {"TARGET", "CHAT_ID", "PEER", "CHAT"}:
        return TARGET
    globals()[name] = ""
    return ""


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
