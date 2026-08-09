#!/usr/bin/env python3
"""Supervisor entry: patch ESTUDO/dedup BEFORE bacbo main ever runs.

Luxury binds at the EOF of bacbo_royal_complete.py often sit AFTER
`asyncio.run(main())` and never execute while the bot is live. This launcher
loads the kill gate first, then runs bacbo as __main__.
"""
from __future__ import annotations

import atexit
import runpy
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOT = Path(__file__).resolve().parent

for p in (str(BOT), str(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

print("[BOOT] run_bacbo_live: preloading HUB + ESTUDO gates…")
try:
    import lux_session_guard as _sg

    print("[BOOT] session_guard:", "OK" if _sg.apply() else "FAIL")
except Exception as exc:
    print("[BOOT] session_guard fail:", repr(exc))

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
_os.environ.setdefault("TELEGRAM_OUTBOX_INLINE", "1")
_os.environ.setdefault("TELEGRAM_OUTBOX_STARTUP_PING", "0")
_os.environ.setdefault("OUTBOX_INLINE_SETTLE_SECS", "70")
_os.environ.setdefault("LUX_SESSION_GUARD", "1")
_os.environ.setdefault("LUX_SESSION_RECONNECTS", "12")
_os.environ.setdefault("LUX_DIALOG_WARM", "cache")


def _rss_mb() -> float:
    try:
        with open("/proc/self/status", encoding="utf-8") as fh:
            for ln in fh:
                if ln.startswith("VmRSS:"):
                    return int(ln.split()[1]) / 1024.0
    except Exception:
        pass
    return -1.0


def _start_rss_heartbeat() -> None:
    """Log RSS every 5s for 3 min — proves OOM vs external SIGKILL on exit -9."""
    import threading
    import time as _t

    def _run() -> None:
        for i in range(36):
            rss = _rss_mb()
            print(f"[BOOT] rss_heartbeat #{i + 1} rss_mb={rss:.1f}", flush=True)
            _t.sleep(5.0)

    try:
        threading.Thread(target=_run, name="lux_rss_hb", daemon=True).start()
        print(f"[BOOT] rss_heartbeat ON start_rss_mb={_rss_mb():.1f}", flush=True)
    except Exception as exc:
        print("[BOOT] rss_heartbeat skip:", repr(exc), flush=True)


# RESULT outbox shares bacbo's TelegramClient — never a second session
try:
    import lux_outbox_inline as _obi

    print("[BOOT] outbox_inline:", "OK" if _obi.apply() else "OFF")
except Exception as exc:
    print("[BOOT] outbox_inline fail:", repr(exc))

bacbo = ROOT / "bacbo_royal_complete.py"
if not bacbo.is_file():
    bacbo = BOT / "bacbo_royal_complete.py"
if not bacbo.is_file():
    raise SystemExit(f"MISSING bacbo_royal_complete.py under {ROOT}")

print(f"[BOOT] run_bacbo_live: exec {bacbo}")
_start_rss_heartbeat()


def _on_exit() -> None:
    print(
        f"[BOOT] run_bacbo_live atexit — process ending rss_mb={_rss_mb():.1f}",
        flush=True,
    )


atexit.register(_on_exit)

try:
    runpy.run_path(str(bacbo), run_name="__main__")
    print("[BOOT] run_bacbo_live: bacbo main returned normally (disconnect?)")
except SystemExit as exc:
    print("[BOOT] run_bacbo_live SystemExit:", repr(exc))
    raise
except BaseException as exc:
    print("[BOOT] run_bacbo_live FATAL:", repr(exc))
    traceback.print_exc()
    raise
finally:
    print("[BOOT] run_bacbo_live EXITING")
