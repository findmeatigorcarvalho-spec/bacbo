"""Harden *_RE config names to compiled regex across loaded modules.

CrashGuard root cause:
  signal_handler does `_WIN_STREAK_RE.search(text)`
  but `from config import _WIN_STREAK_RE` sometimes bound an empty str.

This module repairs:
  - config / bot.config module attributes
  - already-imported bindings in signal_handler, utils, __main__, bacbo*
"""
from __future__ import annotations

import re
import sys
from typing import Any, Dict, List, Tuple

_NEVER = re.compile(r"(?!)")

# Canonical patterns (must match bot/config/__init__.py)
_CANON: Dict[str, re.Pattern[str]] = {
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


def _is_re_name(name: str) -> bool:
    return name.endswith("_RE") or name.endswith("_REGEX") or name.endswith("_PATTERN")


def _as_re(name: str, val: Any) -> Any:
    if hasattr(val, "search") and callable(getattr(val, "search")):
        return val
    if name in _CANON:
        return _CANON[name]
    if isinstance(val, str):
        try:
            return re.compile(val, re.I) if val.strip() else _NEVER
        except re.error:
            return _NEVER
    return _NEVER


def harden_namespace(ns: dict, *, label: str = "") -> List[str]:
    fixed: List[str] = []
    for name, val in list(ns.items()):
        if not isinstance(name, str) or not _is_re_name(name):
            continue
        new = _as_re(name, val)
        if new is not val or not hasattr(val, "search"):
            ns[name] = new
            fixed.append(name)
        elif name in _CANON and not hasattr(val, "search"):
            ns[name] = _CANON[name]
            fixed.append(name)
    # Always force canon names present
    for name, pat in _CANON.items():
        cur = ns.get(name)
        if cur is None or not hasattr(cur, "search"):
            ns[name] = pat
            if name not in fixed:
                fixed.append(name)
    return fixed


def apply(silent: bool = False) -> Tuple[int, List[str]]:
    reports: List[str] = []
    total = 0

    # 1) config packages
    for modname in ("config", "bot.config"):
        mod = sys.modules.get(modname)
        if mod is None:
            continue
        fixed = harden_namespace(getattr(mod, "__dict__", {}), label=modname)
        if fixed:
            total += len(fixed)
            reports.append(f"{modname}:{','.join(fixed)}")

    # 2) Try import config if missing
    try:
        import config as cfg  # type: ignore

        fixed = harden_namespace(cfg.__dict__, label="config")
        if fixed:
            total += len(fixed)
            reports.append(f"config(import):{','.join(fixed)}")
    except Exception:
        pass

    # 3) Every loaded module that already bound these names
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
        # Only touch modules that already reference RE names (avoid noise)
        if not any(k in d for k in _CANON) and name not in priority:
            continue
        fixed = harden_namespace(d, label=name)
        if fixed:
            total += len(fixed)
            reports.append(f"{name}:{','.join(fixed)}")

    if not silent:
        print(f"[LUXURY] re-harden applied fixes={total} where={reports[:12]}")
        # Live proof against the CrashGuard line
        try:
            import config as cfg  # type: ignore

            ws = getattr(cfg, "_WIN_STREAK_RE", None)
            ok = hasattr(ws, "search") and bool(
                ws.search("💵 Estamos com 7 Greens seguidos!")  # type: ignore[union-attr]
            )
            print(f"[LUXURY] re-harden proof _WIN_STREAK_RE.search → {ok}")
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


# Auto-run when imported as luxury early patch
apply()
_schedule()
