"""bot.config package — credentials for bacbo + Profit Family AI modules.

On Replit, PYTHONPATH includes `bot/`, so `from config import API_ID` resolves here.
`from config import X` does NOT call __getattr__ — every imported name must exist
in this module's dict. We scan bacbo + bot/*.py and materialize all of them.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Set

__all__: list[str] = []

# ── dotenv ───────────────────────────────────────────────────────────────────
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


_ROOT = Path(__file__).resolve().parents[2]
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


# ── Core credentials ─────────────────────────────────────────────────────────
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

DB_PATH = _env("BACBO_DB", "DB_PATH", default=str(_ROOT / "bot" / "bacbo.db"))
DATABASE = DB_PATH
DB_FILE = DB_PATH
OWNER_ID = _env("OWNER_ID", "TELEGRAM_OWNER_ID", default="")
ADMIN_ID = OWNER_ID
CHAT_ID = TARGET
PEER = TARGET
GUNIQUE_PEER = TELEGRAM_COUNTDOWN_PEER

# Bacbo / utils private constants (safe defaults — overridden if env sets them)
RECONNECT_DELAY = float(_env("RECONNECT_DELAY", default="5") or "5")
_BOOT_GRACE_SECS = float(_env("_BOOT_GRACE_SECS", "BOOT_GRACE_SECS", default="30") or "30")
PROTECTED_ROOMS: List[str] = []
_KNOWN_DEAD_ROOMS: Set[str] = set()
ROOM_TIERS: Dict[str, Any] = {}
_COLOR_ICON_SHORT = {
    "red": "🔴",
    "blue": "🔵",
    "tie": "🟡",
    "player": "🔵",
    "banker": "🔴",
    "R": "🔴",
    "B": "🔵",
    "T": "🟡",
}
_COLOR_ICON = _COLOR_ICON_SHORT
COLOR_ICON = _COLOR_ICON_SHORT
COLOR_ICON_SHORT = _COLOR_ICON_SHORT
_COLOR_EMOJI = _COLOR_ICON_SHORT

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
    "RECONNECT_DELAY",
    "_BOOT_GRACE_SECS",
    "PROTECTED_ROOMS",
    "_KNOWN_DEAD_ROOMS",
    "ROOM_TIERS",
    "_COLOR_ICON_SHORT",
    "_COLOR_ICON",
    "COLOR_ICON",
    "COLOR_ICON_SHORT",
    "_COLOR_EMOJI",
]


def _parse_from_config_names(src: str) -> List[str]:
    names: List[str] = []
    for m in re.finditer(r"from\s+config\s+import\s*\((.*?)\)", src, flags=re.S):
        for part in m.group(1).split(","):
            part = part.split("#", 1)[0].strip()
            if " as " in part:
                part = part.split(" as ", 1)[-1].strip()
            if part.isidentifier():
                names.append(part)
    for m in re.finditer(r"from\s+config\s+import\s+([^\n(]+)", src):
        chunk = m.group(1).strip()
        if chunk.startswith("("):
            continue
        for part in chunk.split(","):
            part = part.split("#", 1)[0].strip()
            if " as " in part:
                part = part.split(" as ", 1)[-1].strip()
            if part.isidentifier() and part != "*":
                names.append(part)
    return names


def _scan_import_names() -> List[str]:
    found: List[str] = []
    roots = [_ROOT, Path("/home/runner/workspace")]
    seen_files: Set[str] = set()
    for root in roots:
        if not root.is_dir():
            continue
        candidates = [root / "bacbo_royal_complete.py"]
        bot = root / "bot"
        if bot.is_dir():
            candidates.extend(bot.glob("*.py"))
            candidates.extend(bot.glob("**/*.py"))
        for path in candidates:
            try:
                key = str(path.resolve())
            except Exception:
                key = str(path)
            if key in seen_files or not path.is_file():
                continue
            seen_files.add(key)
            # skip this package's own files to avoid noise
            if "bot/config/" in key.replace("\\", "/"):
                continue
            try:
                src = path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            if "from config import" not in src:
                continue
            found.extend(_parse_from_config_names(src))
    # dedupe preserve order
    out: List[str] = []
    seen: Set[str] = set()
    for n in found:
        if n not in seen:
            seen.add(n)
            out.append(n)
    return out


def _default_for(name: str) -> Any:
    g = globals()
    if name in g:
        return g[name]
    u = name.upper()
    if name in {"API_ID", "TELEGRAM_API_ID"}:
        return API_ID
    if name in {"API_HASH", "TELEGRAM_API_HASH"}:
        return API_HASH
    if name in {"TARGET", "CHAT_ID", "PEER", "CHAT", "TELEGRAM_TARGET_PEER"}:
        return TARGET
    if "COLOR" in u and "ICON" in u:
        return dict(_COLOR_ICON_SHORT)
    if "COLOR" in u and "EMOJI" in u:
        return dict(_COLOR_ICON_SHORT)
    if name.endswith("_ROOMS") or name.endswith("_ROOM_IDS"):
        return []
    if name.startswith("_KNOWN_") or name.endswith("_SET"):
        return set()
    if name.endswith("_TIERS") or name.endswith("_MAP") or name.endswith("_DICT"):
        return {}
    if "DELAY" in u or name.endswith("_SECS") or name.endswith("_SECONDS"):
        return 5.0
    if "TIMEOUT" in u or "INTERVAL" in u:
        return 10.0
    if "SESSION" in u and "STRING" in u:
        return TELEGRAM_SESSION_STRING
    if "SESSION" in u:
        return SESSION_FILE
    if name.endswith("_PATH") or name.endswith("_FILE"):
        return str(_ROOT / name.lower())
    if name.endswith("_ID") and name != "API_ID":
        return OWNER_ID or ""
    if name.startswith("IS_") or name.endswith("_ENABLED") or name.startswith("ENABLE_"):
        return True
    if name.endswith("_MIN") or name.endswith("_MAX") or name.endswith("_LIMIT"):
        return 0
    # env mirror
    ev = _env(name)
    if ev != "":
        if ev.replace(".", "", 1).isdigit():
            return float(ev) if "." in ev else int(ev)
        return ev
    return ""


def _ensure_all_config_imports() -> List[str]:
    """Materialize every name any local file imports from config."""
    g = globals()
    names = _scan_import_names()
    created: List[str] = []
    for name in names:
        if name not in g:
            g[name] = _default_for(name)
            created.append(name)
        if name not in __all__:
            __all__.append(name)
    return created


_CREATED = _ensure_all_config_imports()


def __getattr__(name: str) -> Any:
    if name.startswith("__"):
        raise AttributeError(name)
    val = _default_for(name)
    globals()[name] = val
    return val


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
