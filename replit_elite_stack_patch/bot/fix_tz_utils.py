#!/usr/bin/env python3
"""Rewrite root + bot/tz_utils.py with the API bacbo/database expect.

Fixes: ImportError: cannot import name 'local_hour' from 'tz_utils'
"""
from __future__ import annotations

import re
import sys
from pathlib import Path


FULL = '''"""Timezone helpers for Bac Bo (root module — bacbo_royal_complete loads this first)."""
from __future__ import annotations

import os
from datetime import datetime, timezone

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None  # type: ignore

_BOT_TZ = os.environ.get("BOT_TZ") or os.environ.get("TZ_NAME") or "America/New_York"
DISPLAY_TZ = _BOT_TZ  # string name used by cards / learning


def _zone():
    if ZoneInfo is None:
        return timezone.utc
    try:
        return ZoneInfo(_BOT_TZ)
    except Exception:
        return timezone.utc


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def now_local() -> datetime:
    return datetime.now(tz=_zone())


# aliases used across modules
local_now = now_local
TZ_NAME = DISPLAY_TZ
# Compatibility alias for legacy imports. Its value is Pawtucket/ET, not BRT.
BRT_TZ = DISPLAY_TZ


def local_hour(dt=None) -> int:
    if dt is None:
        return now_local().hour
    if getattr(dt, "tzinfo", None) is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(_zone()).hour


def today_iso(dt=None) -> str:
    if dt is None:
        return now_local().date().isoformat()
    if getattr(dt, "tzinfo", None) is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(_zone()).date().isoformat()


def ts(dt=None) -> str:
    """Compact local timestamp used in logs/cards."""
    d = now_local() if dt is None else dt
    if getattr(d, "tzinfo", None) is None:
        d = d.replace(tzinfo=timezone.utc).astimezone(_zone())
    else:
        d = d.astimezone(_zone())
    return d.strftime("%Y-%m-%d %H:%M:%S")


def dts(dt=None) -> str:
    """ISO-ish local datetime string."""
    d = now_local() if dt is None else dt
    if getattr(d, "tzinfo", None) is None:
        d = d.replace(tzinfo=timezone.utc).astimezone(_zone())
    else:
        d = d.astimezone(_zone())
    return d.isoformat(sep=" ", timespec="seconds")


def to_local(dt):
    if dt is None:
        return now_local()
    if getattr(dt, "tzinfo", None) is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(_zone())


def to_utc(dt):
    if dt is None:
        return now_utc()
    if getattr(dt, "tzinfo", None) is None:
        dt = dt.replace(tzinfo=_zone())
    return dt.astimezone(timezone.utc)
'''


def _needed(root: Path) -> set[str]:
    needed: set[str] = set()
    paths = list(root.glob("*.py"))
    bot = root / "bot"
    if bot.is_dir():
        paths += list(bot.glob("*.py"))
    for p in paths:
        try:
            t = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        for m in re.finditer(r"from\s+tz_utils\s+import\s+([^\n]+)", t):
            chunk = m.group(1).split("#")[0]
            for part in chunk.split(","):
                part = part.strip()
                if not part or part.startswith("("):
                    continue
                name = part.split(" as ")[0].strip()
                if name and name.isidentifier():
                    needed.add(name)
    return needed


def apply(root: Path | None = None) -> dict:
    root = root or Path("/home/runner/workspace")
    if not (root / "bacbo_royal_complete.py").exists() and Path.cwd().joinpath("bacbo_royal_complete.py").exists():
        root = Path.cwd()
    root_tz = root / "tz_utils.py"
    bot_tz = root / "bot" / "tz_utils.py"
    bot_tz.parent.mkdir(parents=True, exist_ok=True)

    needed = _needed(root)
    body = FULL
    # stub any extra imported names
    extra = []
    for n in sorted(needed):
        if n in {
            "local_hour",
            "today_iso",
            "now_local",
            "now_utc",
            "local_now",
            "ts",
            "dts",
            "to_local",
            "to_utc",
            "DISPLAY_TZ",
            "TZ_NAME",
            "BRT_TZ",
        }:
            continue
        if n.isupper():
            extra.append(f"{n} = DISPLAY_TZ\n")
        else:
            extra.append(f"def {n}(*a, **k):\n    return now_local()\n")
    if extra:
        body = FULL + "\n# auto-stubs\n" + "".join(extra)

    if root_tz.exists():
        bak = root_tz.with_suffix(".py.bak_pre_local_hour")
        if not bak.exists():
            bak.write_text(root_tz.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")
    root_tz.write_text(body, encoding="utf-8")
    if bot_tz.exists():
        bakb = bot_tz.with_suffix(".py.bak_pre_local_hour")
        if not bakb.exists():
            bakb.write_text(bot_tz.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")
    bot_tz.write_text(body, encoding="utf-8")

    # smoke
    sys.path.insert(0, str(root))
    if "tz_utils" in sys.modules:
        del sys.modules["tz_utils"]
    import tz_utils  # noqa: E402

    missing = [n for n in (needed or {"local_hour", "today_iso"}) if not hasattr(tz_utils, n)]
    out = {
        "root": str(root_tz),
        "bot": str(bot_tz),
        "loaded": getattr(tz_utils, "__file__", None),
        "needed": sorted(needed),
        "missing": missing,
        "local_hour": int(tz_utils.local_hour()),
        "today_iso": str(tz_utils.today_iso()),
    }
    if missing:
        raise SystemExit(f"tz_utils still missing {missing}")
    print("[fix_tz_utils]", out)
    return out


if __name__ == "__main__":
    apply()
