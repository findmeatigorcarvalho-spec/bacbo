"""Bound how stale a room's messages can get.

Telethon only asks Telegram for a channel's missed messages when that channel's
15 minute no-updates timer expires. If Telegram stops pushing a room's updates,
the bot is deaf to that room until the timer fires, which looks like a freeze and
ends in a watchdog restart.

This task, running inside the bot process (never a second client), finds rooms
that have had no push and no poll for POLL_EVERY_S, re-arms their timers a few at
a time and wakes Telethon's update loop the same way Telethon's own catch_up()
does. Rooms that are being pushed normally are never polled.

It backs off for FLOOD_PAUSE_S if Telethon reports a FloodWait while fetching
differences.

A second task watches for the whole account going silent (no room message at
all). After SILENCE_PROBE_S it checks the connection with a state request, forces
a catch-up on the most idle rooms and logs what it saw. After SILENCE_RECONNECT_S
(or at once if the probe times out) it runs Telethon's own in-process reconnect,
which re-establishes the socket and catches up without restarting the bot. This
acts minutes before the 7 to 9 minute watchdog restart would.

Usage:
    python update_poller.py --install    # one-time edit of utils.py (idempotent)
    (the bot starts the loop via ensure_started(), hooked in resolve_room)
"""
import asyncio
import logging
import sys
import time
from pathlib import Path

log = logging.getLogger("UpdatePoller")

POLL_EVERY_S = 30.0
TICK_S = 2.0
BATCH = 6
FLOOD_PAUSE_S = 600.0
REPORT_EVERY_S = 300.0
_FALLBACK_NO_UPDATES_TIMEOUT = 15 * 60

SILENCE_TICK_S = 5.0
SILENCE_PROBE_S = 60.0
SILENCE_RECONNECT_S = 150.0
RECONNECT_COOLDOWN_S = 300.0
PROBE_TIMEOUT_S = 15.0
SILENCE_ARM_LIMIT = 30

_started = False


def _no_updates_timeout():
    try:
        from telethon._updates.messagebox import NO_UPDATES_TIMEOUT
        return float(NO_UPDATES_TIMEOUT)
    except Exception:
        return float(_FALLBACK_NO_UPDATES_TIMEOUT)


def due_entries(mb, now, poll_every=None, limit=None):
    """Channel ids whose timer was last re-armed at least poll_every ago."""
    poll_every = POLL_EVERY_S if poll_every is None else poll_every
    limit = BATCH if limit is None else limit
    full = _no_updates_timeout()
    due = []
    for entry, st in list(mb.map.items()):
        if not isinstance(entry, int) or entry in mb.getting_diff_for:
            continue
        idle = full - (st.deadline - now)
        if idle >= poll_every:
            due.append((idle, entry))
    due.sort(reverse=True)
    return [entry for _, entry in due[:limit]]


def arm(mb, entries):
    """Make the given channels' timers expire now and point Telethon at them.

    check_deadlines() only inspects mb.next_deadline's entry to decide whether
    anything expired. That pointer can be left at an entry that is not tracked
    (for example the account entry of a freshly loaded StringSession), in which
    case expired channel timers are never noticed. It is only a hint to the
    closest deadline, so aiming it at an entry we just expired is always valid.
    """
    armed = []
    for entry in entries:
        try:
            mb.reset_channel_deadline(entry, 0.001)
            armed.append(entry)
        except Exception:
            pass
    if armed:
        mb.next_deadline = min(armed, key=lambda e: mb.map[e].deadline)
    return len(armed)


class _FloodWatch(logging.Handler):
    def __init__(self):
        super().__init__(logging.WARNING)
        self.hit_at = 0.0

    def emit(self, record):
        try:
            if "FloodWait" in record.getMessage():
                self.hit_at = time.monotonic()
        except Exception:
            pass

    def paused(self):
        return self.hit_at and time.monotonic() - self.hit_at < FLOOD_PAUSE_S


async def poller_loop(client):
    from telethon.tl import types

    loop = asyncio.get_running_loop()
    watch = _FloodWatch()
    logging.getLogger("telethon.client.updates").addHandler(watch)
    polled = 0
    ticks = 0
    last_report = loop.time()
    while True:
        await asyncio.sleep(TICK_S)
        try:
            if loop.time() - last_report >= REPORT_EVERY_S:
                log.info("[UpdatePoller] last %ds: re-armed %d idle rooms (%d ticks)%s",
                         int(REPORT_EVERY_S), polled, ticks,
                         " | paused after FloodWait" if watch.paused() else "")
                polled = ticks = 0
                last_report = loop.time()
            ticks += 1
            if watch.paused() or not client.is_connected():
                continue
            mb = getattr(client, "_message_box", None)
            queue = getattr(client, "_updates_queue", None)
            if mb is None or queue is None or mb.getting_diff_for:
                continue
            batch = due_entries(mb, loop.time())
            if not batch:
                continue
            polled += arm(mb, batch)
            queue.put_nowait(types.UpdatesTooLong())
        except Exception as exc:
            log.warning("[UpdatePoller] tick failed: %s", exc)
            await asyncio.sleep(30)


def silence_action(silence, since_probe, since_reconnect, probe_failed=False):
    """Decide what to do when no room message has arrived for `silence` seconds.

    Returns "none", "probe" or "reconnect".
    """
    if silence < SILENCE_PROBE_S:
        return "none"
    can_reconnect = since_reconnect >= RECONNECT_COOLDOWN_S
    if can_reconnect and (probe_failed or silence >= SILENCE_RECONNECT_S):
        return "reconnect"
    if since_probe >= SILENCE_PROBE_S:
        return "probe"
    return "none"


_MESSAGE_UPDATES = ("UpdateNewChannelMessage", "UpdateNewMessage",
                    "UpdateEditChannelMessage", "UpdateEditMessage")


class _LastMessage:
    def __init__(self, now):
        self.at = now
        self.silent_for = 0.0

    def seen(self, now):
        self.silent_for = now - self.at
        self.at = now


async def silence_loop(client):
    from telethon import events, functions
    from telethon.tl import types

    loop = asyncio.get_running_loop()
    last = _LastMessage(loop.time())

    async def on_update(update):
        if type(update).__name__ in _MESSAGE_UPDATES:
            now = loop.time()
            if now - last.at >= SILENCE_PROBE_S:
                log.info("[Silence] messages flowing again after %ds", int(now - last.at))
            last.seen(now)

    client.add_event_handler(on_update, events.Raw())
    last_probe = last_reconnect = -1e9
    probe_failed = False
    while True:
        await asyncio.sleep(SILENCE_TICK_S)
        try:
            now = loop.time()
            if not client.is_connected():
                continue
            silence = now - last.at
            if silence < SILENCE_PROBE_S:
                probe_failed = False
                continue
            action = silence_action(silence, now - last_probe, now - last_reconnect, probe_failed)
            if action == "probe":
                last_probe = now
                started = loop.time()
                try:
                    await asyncio.wait_for(client(functions.updates.GetStateRequest()), PROBE_TIMEOUT_S)
                    rtt = "%.2fs" % (loop.time() - started)
                    probe_failed = False
                except Exception as exc:
                    rtt = "FAILED (%s)" % type(exc).__name__
                    probe_failed = True
                armed = 0
                mb = getattr(client, "_message_box", None)
                queue = getattr(client, "_updates_queue", None)
                if mb is not None and queue is not None and not mb.getting_diff_for:
                    batch = due_entries(mb, loop.time(), poll_every=0.0, limit=SILENCE_ARM_LIMIT)
                    armed = arm(mb, batch)
                    if armed:
                        queue.put_nowait(types.UpdatesTooLong())
                log.warning("[Silence] no room message for %ds | state probe %s | forced catch-up on %d rooms",
                            int(silence), rtt, armed)
            elif action == "reconnect":
                last_reconnect = now
                last_probe = now
                probe_failed = False
                sender = getattr(client, "_sender", None)
                if sender is None or not hasattr(sender, "_start_reconnect"):
                    log.warning("[Silence] no sender to reconnect")
                    continue
                log.error("[Silence] no room message for %ds — in-process reconnect (no restart)", int(silence))
                sender._start_reconnect(None)
        except Exception as exc:
            log.warning("[Silence] tick failed: %s", exc)
            await asyncio.sleep(30)


def ensure_started():
    global _started
    if _started:
        return
    try:
        import state
        client = getattr(state, "client", None)
        if client is None:
            return
        loop = asyncio.get_running_loop()
        loop.create_task(poller_loop(client))
        loop.create_task(silence_loop(client))
        _started = True
        log.info("[UpdatePoller] started (idle>=%ds, <=%d rooms/%ds tick)",
                 int(POLL_EVERY_S), BATCH, int(TICK_S))
    except Exception as exc:
        log.warning("[UpdatePoller] could not start: %s", exc)


OLD_HOOK = 'exec("try:\\n import slow_join as _sj; _sj.ensure_started()\\nexcept Exception:\\n pass")'
NEW_HOOK = ('exec("try:\\n import slow_join as _sj; _sj.ensure_started()\\nexcept Exception:\\n pass\\n'
            'try:\\n import update_poller as _up; _up.ensure_started()\\nexcept Exception:\\n pass")')


def install(utils_path):
    src = Path(utils_path).read_text(encoding="utf-8")
    if "update_poller" in src:
        return "already installed"
    if OLD_HOOK not in src:
        return "hook line not found (expected the slow_join exec line in resolve_room)"
    Path(str(utils_path) + ".bak_update_poller").write_text(src, encoding="utf-8")
    Path(utils_path).write_text(src.replace(OLD_HOOK, NEW_HOOK, 1), encoding="utf-8")
    return "installed"


if __name__ == "__main__":
    if "--install" in sys.argv:
        target = Path(__file__).resolve().parent / "utils.py"
        print(install(target))
    else:
        print(__doc__)
