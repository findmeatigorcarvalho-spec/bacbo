#!/usr/bin/env python3
"""Supervisor entry: patch ESTUDO/dedup BEFORE bacbo main ever runs.

Luxury binds at the EOF of bacbo_royal_complete.py often sit AFTER
`asyncio.run(main())` and never execute while the bot is live. This launcher
loads the kill gate first, then runs bacbo as __main__.
"""
from __future__ import annotations

import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOT = Path(__file__).resolve().parent

for p in (str(BOT), str(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

print("[BOOT] run_bacbo_live: preloading ESTUDO/dedup gate…")
ok = False
try:
    import lux_estudo_kill as _ek

    ok = bool(_ek.apply())
    print("[BOOT] run_bacbo_live: lux_estudo_kill", "OK" if ok else "PENDING")
except Exception as exc:
    print("[BOOT] run_bacbo_live: lux_estudo_kill fail:", repr(exc))

try:
    import lux_send_config_bind as _lux  # noqa: F401

    _lux.apply(silent=True)
    print("[BOOT] run_bacbo_live: lux_send_config_bind OK")
except Exception as exc:
    print("[BOOT] run_bacbo_live: lux_send_config_bind fail:", repr(exc))

bacbo = ROOT / "bacbo_royal_complete.py"
if not bacbo.is_file():
    bacbo = BOT / "bacbo_royal_complete.py"
if not bacbo.is_file():
    raise SystemExit(f"MISSING bacbo_royal_complete.py under {ROOT}")

print(f"[BOOT] run_bacbo_live: exec {bacbo}")
runpy.run_path(str(bacbo), run_name="__main__")
