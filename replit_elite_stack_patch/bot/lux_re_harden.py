"""Harden config bindings in loaded modules (regex + numeric).

CrashGuard roots:
  1) `_WIN_STREAK_RE.search(text)` when binding is empty str
  2) `unary -: 'str'` when knobs like `_ACCUM_HOLD_SECS` / `SOLO_LOSS_COOLDOWN` are ""
  3) `str + int` from the same empty-string materialization

Repairs:
  - config / bot.config
  - signal_handler, utils, __main__, bacbo* already-imported names
"""
from __future__ import annotations

import re
import sys
from typing import Any, Dict, List, Tuple

_NEVER = re.compile(r"(?!)")

_CANON_RE: Dict[str, re.Pattern[str]] = {
    "_WIN_STREAK_RE": re.compile(
        r"(?P<n>\d+)\s*(?:Greens?|greens?|WINS?|wins?|✅)\s*"
        r"(?:seguidos?|seguidas?|streak|em\s*sequencia|em\s*sequência)",
        re.I,
    ),
    "_GALE1_RE": re.compile(
        r"(?:GALE\s*1|G1|primeiro\s*gale|1[ºo°]?\s*gale|entrada\s*gale\s*1)",
        re.I,
    ),
    "_GALE_OPTIONAL_RE": re.compile(
        r"(?:GALE|gale)\s*(?:opcional|optional|0|zero)?|"
        r"até\s*gale|ate\s*gale|max\s*gale|máx(?:imo)?\s*gale",
        re.I,
    ),
    "_ENTRADA_FINALIZADA_RE": re.compile(
        r"ENTRADA\s*FINALIZADA|entrada\s*finalizada|RESULTADO\s*FINAL|"
        r"✅\s*GREEN|❌\s*(?:RED|LOSS)|GREEN\b|LOSS\b|WIN\b",
        re.I,
    ),
    "_SCOREBOARD_PLACAR_RE": re.compile(
        r"(?:Placar|PLACAR|Scoreboard|Score)\s*[:：]?\s*.*?(?:✅|❌|\d+)|"
        r"Acertamos\s+[\d.,]+\s*%|"
        r"✅\s*\d+\s*[|｜]\s*❌\s*\d+",
        re.I,
    ),
}

# Defaults for arithmetic knobs (must be int/float — never "")
_CANON_NUM: Dict[str, float | int] = {
    "SIGNAL_DEDUP_SECS": 8.0,
    "LOSS_COOLDOWN_THRESHOLD": 3,
    "LOSS_COOLDOWN_DURATION": 300.0,
    "COOLDOWN_THRESHOLD_BUMP": 1,
    "POST_LOSS_PAUSE_SECS": 30.0,
    "AUTO_QUARANTINE_LOSSES": 5,
    "AUTO_QUARANTINE_SECS": 600.0,
    "ROLLING_WR_WINDOW": 20,
    "ROLLING_WR_MIN_PCT": 55.0,
    "ROLLING_WR_MUTE_SECS": 300.0,
    "PRE_ALERT_THRESHOLD": 2,
    "SOLO_LOSS_COOLDOWN": 120.0,
    "VIP_SILENCE_THRESHOLD": 3,
    "MOMENTUM_SOLO_MIN": 2,
    "MOMENTUM_LOSS_REQUIRE": 1,
    "MOMENTUM_COLD_REQUIRE": 1,
    "_ACCUM_HOLD_SECS": 3.0,
    "_SEQ_MAX_LEN": 8,
    "_SCAN_ALERT_COOLDOWN": 30.0,
    "_KG_CACHE_TTL": 60.0,
    "_OUTCOME_CONFIRM_WINDOW": 45.0,
    "BAC_BO_TIE_PROB": 0.09,
    "_SEND_TIMEOUT": 20.0,
    "_SEND_RETRIES": 3,
    "_SEND_QUIET_TIMEOUT": 10.0,
    "HEARTBEAT_INTERVAL": 30.0,
    "DB_HEARTBEAT_INTERVAL": 60.0,
    "ROOM_SYNC_INTERVAL": 120.0,
    "ROOM_REVALIDATE_CYCLES": 5,
    "DAILY_REPORT_HOUR": 0,
    "TIE_PRESSURE_THRESHOLD": 3,
    "_FINGERPRINT_SCAN_HOURS": 6,
    "AUTO_DISCOVER_ADD_SIG_PCT": 70.0,
    "AUTO_DISCOVER_ADD_RES_PCT": 70.0,
    "AUTO_DISCOVER_SCAN_MSGS": 200,
    "_KELLY_RETRAIN_EVERY": 50,
    "AUTO_DISCOVER_INTERVAL": 3600.0,
    "AUTO_DISCOVER_INITIAL_DELAY": 120.0,
    "AUTO_DISCOVER_REMOVE_SIG_PCT": 40.0,
    "AUTO_DISCOVER_REMOVE_RES_PCT": 40.0,
    "_FINGERPRINT_MIN_RESULTS": 5,
    "_FINGERPRINT_MAX_TIME_DRIFT": 30.0,
    "_FINGERPRINT_MIN_MATCH": 3,
    "_FINGERPRINT_MATCH_WINDOW": 120.0,
    "RECONNECT_DELAY": 5.0,
    "_BOOT_GRACE_SECS": 30.0,
}


def _is_re_name(name: str) -> bool:
    return name.endswith("_RE") or name.endswith("_REGEX") or name.endswith("_PATTERN")


def _is_num_name(name: str) -> bool:
    if name in _CANON_NUM:
        return True
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
    )
    return any(name.endswith(s) for s in suffixes)


def _as_re(name: str, val: Any) -> Any:
    if hasattr(val, "search") and callable(getattr(val, "search")):
        return val
    if name in _CANON_RE:
        return _CANON_RE[name]
    if isinstance(val, str):
        try:
            return re.compile(val, re.I) if val.strip() else _NEVER
        except re.error:
            return _NEVER
    return _NEVER


def _as_num(name: str, val: Any) -> Any:
    default = _CANON_NUM.get(name, 5.0)
    if isinstance(val, bool):
        return int(val)
    if isinstance(val, (int, float)):
        return val
    if isinstance(val, str):
        s = val.strip()
        if not s:
            return default
        try:
            return float(s) if ("." in s or "e" in s.lower()) else int(s)
        except Exception:
            return default
    return default


def harden_namespace(ns: dict, *, label: str = "") -> List[str]:
    fixed: List[str] = []
    for name, val in list(ns.items()):
        if not isinstance(name, str):
            continue
        if _is_re_name(name):
            new = _as_re(name, val)
            if new is not val or not hasattr(val, "search"):
                ns[name] = new
                fixed.append(name)
        elif _is_num_name(name):
            if not isinstance(val, (int, float)) or isinstance(val, bool):
                ns[name] = _as_num(name, val)
                fixed.append(name)
    for name, pat in _CANON_RE.items():
        cur = ns.get(name)
        if cur is None or not hasattr(cur, "search"):
            ns[name] = pat
            if name not in fixed:
                fixed.append(name)
    for name, num in _CANON_NUM.items():
        cur = ns.get(name, None)
        # Only force if key already present (imported) or priority modules
        if name in ns and not isinstance(ns[name], (int, float)):
            ns[name] = num
            if name not in fixed:
                fixed.append(name)
    return fixed


def apply(silent: bool = False) -> Tuple[int, List[str]]:
    reports: List[str] = []
    total = 0

    for modname in ("config", "bot.config"):
        mod = sys.modules.get(modname)
        if mod is None:
            continue
        fixed = harden_namespace(getattr(mod, "__dict__", {}), label=modname)
        if fixed:
            total += len(fixed)
            reports.append(f"{modname}:{len(fixed)}")

    try:
        import config as cfg  # type: ignore

        fixed = harden_namespace(cfg.__dict__, label="config")
        if fixed:
            total += len(fixed)
            reports.append(f"config(import):{len(fixed)}")
    except Exception:
        pass

    priority = (
        "signal_handler",
        "utils",
        "__main__",
        "bacbo_royal_complete",
        "bacbo",
    )
    seen = set()
    for name in list(priority) + list(sys.modules.keys()):
        if name in seen:
            continue
        seen.add(name)
        mod = sys.modules.get(name)
        if mod is None:
            continue
        d = getattr(mod, "__dict__", None)
        if not isinstance(d, dict):
            continue
        if (
            not any(k in d for k in _CANON_RE)
            and not any(k in d for k in _CANON_NUM)
            and name not in priority
        ):
            continue
        fixed = harden_namespace(d, label=name)
        if fixed:
            total += len(fixed)
            reports.append(f"{name}:{len(fixed)}")

    if not silent:
        print(f"[LUXURY] re-harden applied fixes={total} where={reports[:12]}")
        try:
            import config as cfg  # type: ignore

            ws = getattr(cfg, "_WIN_STREAK_RE", None)
            ok = hasattr(ws, "search") and bool(
                ws.search("💵 Estamos com 7 Greens seguidos!")  # type: ignore[union-attr]
            )
            hold = getattr(cfg, "_ACCUM_HOLD_SECS", None)
            solo = getattr(cfg, "SOLO_LOSS_COOLDOWN", None)
            print(
                f"[LUXURY] re-harden proof search={ok} "
                f"_ACCUM_HOLD_SECS={hold!r}({type(hold).__name__}) "
                f"SOLO_LOSS_COOLDOWN={solo!r}({type(solo).__name__})"
            )
            # Unary-minus must not raise
            _ = -float(hold)  # type: ignore[arg-type]
            _ = -float(solo)  # type: ignore[arg-type]
            print("[LUXURY] re-harden proof unary-minus OK")
        except Exception as exc:
            print("[LUXURY] re-harden proof fail:", repr(exc))
    return total, reports


def _schedule() -> None:
    try:
        import threading

        for d in (0.5, 2.0, 5.0, 15.0, 45.0):
            threading.Timer(d, lambda: apply(silent=True)).start()
    except Exception:
        pass


apply()
_schedule()
