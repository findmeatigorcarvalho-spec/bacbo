"""Name the exact code that freezes the event loop.

The poller can only report that its ticks collapsed (e.g. 1 tick per 300s);
it cannot say *what* the main thread was doing, because the blocking code
never yields to it. This watcher can: a daemon thread (which the GIL keeps
scheduling even while the loop is stuck in synchronous work) watches a
heartbeat that a loop task updates every second. When the heartbeat is more
than LAG_WARN_S stale, the thread dumps the main thread's current stack to
the log, throttled to once per DUMP_COOLDOWN_S:

    [LoopLag] event loop blocked 47s - main thread at:
      File "background.py", line 1234, in periodic_...
        ...

One such line names the offender precisely, so it can be moved off the loop
(asyncio.to_thread) instead of guessed at. Read-only: it never restarts,
kills or reconnects anything.

Started by update_poller.ensure_started(); no separate wiring needed.
"""
import asyncio
import logging
import sys
import threading
import time
import traceback

log = logging.getLogger("LoopLag")

HEARTBEAT_S = 1.0
CHECK_S = 2.0
LAG_WARN_S = 15.0
DUMP_COOLDOWN_S = 60.0
STACK_FRAMES = 14

_beat = {"at": time.monotonic()}
_started = False


def should_dump(lag, since_last_dump, warn_s=LAG_WARN_S, cooldown_s=DUMP_COOLDOWN_S):
    return lag >= warn_s and since_last_dump >= cooldown_s


def _main_thread_stack():
    main = threading.main_thread()
    frame = sys._current_frames().get(main.ident)
    if frame is None:
        return "(main thread frame unavailable)"
    lines = traceback.format_stack(frame, limit=STACK_FRAMES)
    return "".join(lines).rstrip()


async def _heartbeat():
    while True:
        _beat["at"] = time.monotonic()
        await asyncio.sleep(HEARTBEAT_S)


def _watch():
    last_dump = -1e9
    while True:
        time.sleep(CHECK_S)
        try:
            now = time.monotonic()
            lag = now - _beat["at"]
            if should_dump(lag, now - last_dump):
                last_dump = now
                log.error("[LoopLag] event loop blocked %ds - main thread at:\n%s",
                          int(lag), _main_thread_stack())
        except Exception:
            pass


def start(loop=None):
    global _started
    if _started:
        return False
    try:
        loop = loop or asyncio.get_running_loop()
    except RuntimeError:
        return False
    _beat["at"] = time.monotonic()
    loop.create_task(_heartbeat())
    threading.Thread(target=_watch, name="loop-lag-watch", daemon=True).start()
    _started = True
    log.info("[LoopLag] watcher started (warns when the loop is blocked >%ds)", int(LAG_WARN_S))
    return True
