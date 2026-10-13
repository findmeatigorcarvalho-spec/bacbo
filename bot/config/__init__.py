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

# Compiled regexes — signal_handler/utils call .search(); NEVER export plain str.
_NEVER_RE = re.compile(r"(?!)")  # intentional no-match placeholder
_WIN_STREAK_RE = re.compile(
    r"(?P<n>\d+)\s*(?:Greens?|greens?|WINS?|wins?|✅)\s*(?:seguidos?|seguidas?|streak|em\s*sequencia|em\s*sequência)",
    re.I,
)
_GALE1_RE = re.compile(
    r"(?:GALE\s*1|G1|primeiro\s*gale|1[ºo°]?\s*gale|entrada\s*gale\s*1)",
    re.I,
)
_GALE_OPTIONAL_RE = re.compile(
    r"(?:GALE|gale)\s*(?:opcional|optional|0|zero)?|até\s*gale|ate\s*gale|max\s*gale|máx(?:imo)?\s*gale",
    re.I,
)
_ENTRADA_FINALIZADA_RE = re.compile(
    r"ENTRADA\s*FINALIZADA|entrada\s*finalizada|RESULTADO\s*FINAL|"
    r"✅\s*GREEN|❌\s*(?:RED|LOSS)|GREEN\b|LOSS\b|WIN\b",
    re.I,
)
_SCOREBOARD_PLACAR_RE = re.compile(
    r"(?:Placar|PLACAR|Scoreboard|Score)\s*[:：]?\s*.*?(?:✅|❌|\d+)|"
    r"Acertamos\s+[\d.,]+\s*%|"
    r"✅\s*\d+\s*[|｜]\s*❌\s*\d+",
    re.I,
)

# ── Bacbo/utils knobs — TYPED defaults (never "" for numbers) ────────────────
# CrashGuard: unary -: 'str'  and  str+int  came from empty-string materialization.
SIGNAL_DEDUP_SECS = float(_env("SIGNAL_DEDUP_SECS", default="8") or "8")
LOSS_COOLDOWN_THRESHOLD = int(float(_env("LOSS_COOLDOWN_THRESHOLD", default="3") or "3"))
LOSS_COOLDOWN_DURATION = float(_env("LOSS_COOLDOWN_DURATION", default="300") or "300")
COOLDOWN_THRESHOLD_BUMP = int(float(_env("COOLDOWN_THRESHOLD_BUMP", default="1") or "1"))
POST_LOSS_PAUSE_SECS = float(_env("POST_LOSS_PAUSE_SECS", default="30") or "30")
AUTO_QUARANTINE_LOSSES = int(float(_env("AUTO_QUARANTINE_LOSSES", default="5") or "5"))
AUTO_QUARANTINE_SECS = float(_env("AUTO_QUARANTINE_SECS", default="600") or "600")
ROLLING_WR_WINDOW = int(float(_env("ROLLING_WR_WINDOW", default="20") or "20"))
ROLLING_WR_MIN_PCT = float(_env("ROLLING_WR_MIN_PCT", default="55") or "55")
ROLLING_WR_MUTE_SECS = float(_env("ROLLING_WR_MUTE_SECS", default="300") or "300")
PRE_ALERT_THRESHOLD = int(float(_env("PRE_ALERT_THRESHOLD", default="2") or "2"))
SOLO_LOSS_COOLDOWN = float(_env("SOLO_LOSS_COOLDOWN", default="120") or "120")
VIP_ROOMS: List[str] = []
VIP_SILENCE_THRESHOLD = int(float(_env("VIP_SILENCE_THRESHOLD", default="3") or "3"))
MOMENTUM_SOLO_MIN = int(float(_env("MOMENTUM_SOLO_MIN", default="2") or "2"))
MOMENTUM_LOSS_REQUIRE = int(float(_env("MOMENTUM_LOSS_REQUIRE", default="1") or "1"))
MOMENTUM_COLD_REQUIRE = int(float(_env("MOMENTUM_COLD_REQUIRE", default="1") or "1"))
_ACCUM_HOLD_SECS = float(_env("_ACCUM_HOLD_SECS", "ACCUM_HOLD_SECS", default="3") or "3")
_WEAK_COMBO_BLOCKLIST: Set[Any] = set()
_WEAK_GOLDEN_PAIRS: Set[Any] = set()
_SEQ_MAX_LEN = int(float(_env("_SEQ_MAX_LEN", default="8") or "8"))
_SCAN_ALERT_COOLDOWN = float(_env("_SCAN_ALERT_COOLDOWN", default="30") or "30")
_KG_CACHE_TTL = float(_env("_KG_CACHE_TTL", default="60") or "60")
_OUTCOME_CONFIRM_WINDOW = float(_env("_OUTCOME_CONFIRM_WINDOW", default="45") or "45")
IMAGE_RESULT_ROOMS: List[str] = []
IMAGE_ENTRY_ROOMS: List[str] = []
BAC_BO_TIE_PROB = float(_env("BAC_BO_TIE_PROB", default="0.09") or "0.09")
_HIGH_CONFIDENCE_ZONES: Dict[str, Any] = {}
RESEARCH_TARGET = TARGET
_HOUR_WR_STATIC: Dict[str, Any] = {}
_HOUR_COLOR_WR: Dict[str, Any] = {}
_SEND_TIMEOUT = float(_env("_SEND_TIMEOUT", "SEND_TIMEOUT", default="20") or "20")
_SEND_RETRIES = int(float(_env("_SEND_RETRIES", "SEND_RETRIES", default="3") or "3"))
_SEND_QUIET_TIMEOUT = float(
    _env("_SEND_QUIET_TIMEOUT", "SEND_QUIET_TIMEOUT", default="10") or "10"
)
HEARTBEAT_INTERVAL = float(_env("HEARTBEAT_INTERVAL", default="30") or "30")
DB_HEARTBEAT_INTERVAL = float(_env("DB_HEARTBEAT_INTERVAL", default="60") or "60")
ROOM_SYNC_INTERVAL = float(_env("ROOM_SYNC_INTERVAL", default="120") or "120")
ROOM_REVALIDATE_CYCLES = int(float(_env("ROOM_REVALIDATE_CYCLES", default="5") or "5"))
DAILY_REPORT_HOUR = int(float(_env("DAILY_REPORT_HOUR", default="0") or "0"))
TIE_PRESSURE_THRESHOLD = int(float(_env("TIE_PRESSURE_THRESHOLD", default="3") or "3"))
_FINGERPRINT_SCAN_HOURS = int(float(_env("_FINGERPRINT_SCAN_HOURS", default="6") or "6"))
AUTO_DISCOVER_ADD_SIG_PCT = float(_env("AUTO_DISCOVER_ADD_SIG_PCT", default="70") or "70")
AUTO_DISCOVER_ADD_RES_PCT = float(_env("AUTO_DISCOVER_ADD_RES_PCT", default="70") or "70")
AUTO_DISCOVER_SCAN_MSGS = int(float(_env("AUTO_DISCOVER_SCAN_MSGS", default="200") or "200"))
_KELLY_RETRAIN_EVERY = int(float(_env("_KELLY_RETRAIN_EVERY", default="50") or "50"))
AUTO_DISCOVER_INTERVAL = float(_env("AUTO_DISCOVER_INTERVAL", default="3600") or "3600")
AUTO_DISCOVER_INITIAL_DELAY = float(
    _env("AUTO_DISCOVER_INITIAL_DELAY", default="120") or "120"
)
AUTO_DISCOVER_REMOVE_SIG_PCT = float(
    _env("AUTO_DISCOVER_REMOVE_SIG_PCT", default="40") or "40"
)
AUTO_DISCOVER_REMOVE_RES_PCT = float(
    _env("AUTO_DISCOVER_REMOVE_RES_PCT", default="40") or "40"
)
_FINGERPRINT_MIN_RESULTS = int(float(_env("_FINGERPRINT_MIN_RESULTS", default="5") or "5"))
_FINGERPRINT_MAX_TIME_DRIFT = float(
    _env("_FINGERPRINT_MAX_TIME_DRIFT", default="30") or "30"
)
_FINGERPRINT_MIN_MATCH = int(float(_env("_FINGERPRINT_MIN_MATCH", default="3") or "3"))
_FINGERPRINT_MATCH_WINDOW = float(
    _env("_FINGERPRINT_MATCH_WINDOW", default="120") or "120"
)

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
    "_WIN_STREAK_RE",
    "_GALE1_RE",
    "_GALE_OPTIONAL_RE",
    "_ENTRADA_FINALIZADA_RE",
    "_SCOREBOARD_PLACAR_RE",
    "SIGNAL_DEDUP_SECS",
    "LOSS_COOLDOWN_THRESHOLD",
    "LOSS_COOLDOWN_DURATION",
    "COOLDOWN_THRESHOLD_BUMP",
    "POST_LOSS_PAUSE_SECS",
    "AUTO_QUARANTINE_LOSSES",
    "AUTO_QUARANTINE_SECS",
    "ROLLING_WR_WINDOW",
    "ROLLING_WR_MIN_PCT",
    "ROLLING_WR_MUTE_SECS",
    "PRE_ALERT_THRESHOLD",
    "SOLO_LOSS_COOLDOWN",
    "VIP_ROOMS",
    "VIP_SILENCE_THRESHOLD",
    "MOMENTUM_SOLO_MIN",
    "MOMENTUM_LOSS_REQUIRE",
    "MOMENTUM_COLD_REQUIRE",
    "_ACCUM_HOLD_SECS",
    "_WEAK_COMBO_BLOCKLIST",
    "_WEAK_GOLDEN_PAIRS",
    "_SEQ_MAX_LEN",
    "_SCAN_ALERT_COOLDOWN",
    "_KG_CACHE_TTL",
    "_OUTCOME_CONFIRM_WINDOW",
    "IMAGE_RESULT_ROOMS",
    "IMAGE_ENTRY_ROOMS",
    "BAC_BO_TIE_PROB",
    "_HIGH_CONFIDENCE_ZONES",
    "RESEARCH_TARGET",
    "_HOUR_WR_STATIC",
    "_HOUR_COLOR_WR",
    "_SEND_TIMEOUT",
    "_SEND_RETRIES",
    "_SEND_QUIET_TIMEOUT",
    "HEARTBEAT_INTERVAL",
    "DB_HEARTBEAT_INTERVAL",
    "ROOM_SYNC_INTERVAL",
    "ROOM_REVALIDATE_CYCLES",
    "DAILY_REPORT_HOUR",
    "TIE_PRESSURE_THRESHOLD",
    "_FINGERPRINT_SCAN_HOURS",
    "AUTO_DISCOVER_ADD_SIG_PCT",
    "AUTO_DISCOVER_ADD_RES_PCT",
    "AUTO_DISCOVER_SCAN_MSGS",
    "_KELLY_RETRAIN_EVERY",
    "AUTO_DISCOVER_INTERVAL",
    "AUTO_DISCOVER_INITIAL_DELAY",
    "AUTO_DISCOVER_REMOVE_SIG_PCT",
    "AUTO_DISCOVER_REMOVE_RES_PCT",
    "_FINGERPRINT_MIN_RESULTS",
    "_FINGERPRINT_MAX_TIME_DRIFT",
    "_FINGERPRINT_MIN_MATCH",
    "_FINGERPRINT_MATCH_WINDOW",
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


def _is_regex_name(name: str) -> bool:
    u = name.upper()
    return (
        name.endswith("_RE")
        or name.endswith("_REGEX")
        or name.endswith("_PATTERN")
        or u.endswith("_COMPILED")
    )


def _is_numeric_name(name: str) -> bool:
    """Names that signal_handler uses in arithmetic / unary minus."""
    u = name.upper()
    suffixes = (
        "_SECS",
        "_SECONDS",
        "_TIMEOUT",
        "_INTERVAL",
        "_THRESHOLD",
        "_DURATION",
        "_WINDOW",
        "_TTL",
        "_DELAY",
        "_PCT",
        "_PROB",
        "_RETRIES",
        "_CYCLES",
        "_EVERY",
        "_MSGS",
        "_HOUR",
        "_HOURS",
        "_BUMP",
        "_LOSSES",
        "_REQUIRE",
        "_LEN",
        "_COOLDOWN",
        "_DRIFT",
        "_MATCH",
        "_RESULTS",
        "_MIN",
        "_MAX",
        "_LIMIT",
        "_COUNT",
        "_SIZE",
        "_RATE",
    )
    if any(name.endswith(s) for s in suffixes):
        return True
    if any(k in u for k in ("DELAY", "TIMEOUT", "INTERVAL", "THRESHOLD", "COOLDOWN")):
        return True
    return False


def _as_compiled_re(val: Any) -> Any:
    """Ensure .search() exists — strings become compiled patterns."""
    if hasattr(val, "search") and callable(getattr(val, "search")):
        return val
    if isinstance(val, str):
        try:
            return re.compile(val, re.I) if val.strip() else _NEVER_RE
        except re.error:
            return _NEVER_RE
    return _NEVER_RE


def _as_number(name: str, val: Any, *, default: float = 0.0) -> Any:
    if isinstance(val, bool):
        return int(val)
    if isinstance(val, (int, float)):
        return val
    if isinstance(val, str):
        s = val.strip()
        if not s:
            # Prefer float for time-like names (unary-/subtraction safe)
            u = name.upper()
            if any(
                name.endswith(x)
                for x in (
                    "_SECS",
                    "_SECONDS",
                    "_TIMEOUT",
                    "_INTERVAL",
                    "_DURATION",
                    "_TTL",
                    "_DELAY",
                    "_PCT",
                    "_PROB",
                    "_COOLDOWN",
                    "_DRIFT",
                    "_WINDOW",
                )
            ) or any(k in u for k in ("DELAY", "TIMEOUT", "INTERVAL", "COOLDOWN")):
                return float(default if default else 5.0)
            return int(default)
        try:
            return float(s) if ("." in s or "E" in s.upper()) else int(s)
        except Exception:
            return float(default if default else 0.0)
    try:
        return float(val)
    except Exception:
        return float(default)


def _default_for(name: str) -> Any:
    g = globals()
    if name in g:
        val = g[name]
        if _is_regex_name(name):
            return _as_compiled_re(val)
        if _is_numeric_name(name) and (
            val == "" or val is None or (isinstance(val, str) and not val.strip())
        ):
            return _as_number(name, "", default=5.0)
        return val
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
    # CRITICAL: signal_handler calls name.search(text) — must be compiled re
    if _is_regex_name(name):
        return _NEVER_RE
    if name.endswith("_ROOMS") or name.endswith("_ROOM_IDS"):
        return []
    if (
        name.startswith("_KNOWN_")
        or name.endswith("_SET")
        or name.endswith("_BLOCKLIST")
        or name.endswith("_PAIRS")
    ):
        return set()
    if (
        name.endswith("_TIERS")
        or name.endswith("_MAP")
        or name.endswith("_DICT")
        or name.endswith("_ZONES")
        or name.endswith("_STATIC")
        or name.endswith("_WR")
    ):
        return {}
    if _is_numeric_name(name):
        ev = _env(name)
        if ev != "":
            return _as_number(name, ev, default=5.0)
        return _as_number(name, "", default=5.0)
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
    # env mirror (non-numeric leftovers)
    ev = _env(name)
    if ev != "":
        return ev
    # NEVER default bare numeric-looking unknowns to "" — 0 is safer than unary- crash
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
        else:
            val = g[name]
            if _is_regex_name(name):
                fixed = _as_compiled_re(val)
                if fixed is not val:
                    g[name] = fixed
                    created.append(name)
            elif _is_numeric_name(name) and (
                val == ""
                or val is None
                or (isinstance(val, str) and not str(val).strip())
            ):
                g[name] = _as_number(name, "", default=5.0)
                created.append(name)
        if name not in __all__:
            __all__.append(name)
    # Absolute harden pass
    for name, val in list(g.items()):
        if not isinstance(name, str):
            continue
        if _is_regex_name(name) and not hasattr(val, "search"):
            g[name] = _as_compiled_re(val)
        elif _is_numeric_name(name) and isinstance(val, str):
            g[name] = _as_number(name, val, default=5.0)
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
