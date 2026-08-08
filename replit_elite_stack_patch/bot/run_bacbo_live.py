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

print("[BOOT] run_bacbo_live: preloading HUB + ESTUDO gates…")
try:
    import lux_chat_watchdog as _cw

    print("[BOOT] chat_watchdog:", "OK" if _cw.apply() else "FAIL")
except Exception as exc:
    print("[BOOT] chat_watchdog fail:", repr(exc))

try:
    import lux_dialog_resolve as _dr

    print("[BOOT] dialog_resolve:", "OK" if _dr.apply() else "FAIL")
except Exception as exc:
    print("[BOOT] dialog_resolve fail:", repr(exc))

try:
    import hub_max_boot as _hub

    print("[BOOT] hub_max_boot:", _hub.apply())
except Exception as exc:
    print("[BOOT] hub_max_boot fail:", repr(exc))

try:
    import hub_impact_learner as _hil  # noqa: F401

    print("[BOOT] hub_impact_learner: ON")
except Exception as exc:
    print("[BOOT] hub_impact_learner fail:", repr(exc))

try:
    import lux_no_hour_blocks as _nhb

    _nhb.apply()
    print("[BOOT] no_hour_blocks: ON")
except Exception as exc:
    print("[BOOT] no_hour_blocks fail:", repr(exc))

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

# Force free-propose / explosion for this process even if env file lagged
import os as _os

_os.environ.setdefault("FREE_PROPOSE", "1")
_os.environ.setdefault("VOLUME_MODE", "EXPLOSION")
_os.environ.setdefault("V2_PROPOSERS", "1")
_os.environ.setdefault("HUB_ORCHESTRATOR", "1")
_os.environ.setdefault("LUXURY_NO_HOUR_BLOCKS", "1")

bacbo = ROOT / "bacbo_royal_complete.py"
if not bacbo.is_file():
    bacbo = BOT / "bacbo_royal_complete.py"
if not bacbo.is_file():
    raise SystemExit(f"MISSING bacbo_royal_complete.py under {ROOT}")

print(f"[BOOT] run_bacbo_live: exec {bacbo}")
runpy.run_path(str(bacbo), run_name="__main__")
