"""Throttled room joiner.

Joins rooms from data/slow_join_targets.txt one at a time with long random
gaps, a daily cap, and a hard stop on any FloodWait. It runs inside the bot
process (never a second client on the same session) and only issues a username
lookup when the shared guard block file has expired.

Already-joined rooms are recognised from the account's dialog list (one
GetDialogs call, refreshed hourly) — never from per-username lookups and never
against the daily cap, so the cap is spent only on genuinely new rooms. A
handle that errors or times out is deferred on its own and the queue moves on
to the next handle; only FloodWait / ChannelsTooMuch pause the whole joiner.

Usage:
    python slow_join.py --patch-guard     # one-time edit of no_username_lookup.py
    (the bot starts the loop via ensure_started(), hooked in resolve_room)
"""
import asyncio
import json
import logging
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger("SlowJoin")

HERE = Path(__file__).resolve().parent
TARGETS = HERE / "data" / "slow_join_targets.txt"
STATE = HERE / "data" / "slow_join_state.json"

PER_DAY = 6
GAP_MIN_S = 1500
GAP_MAX_S = 2700
MARGIN_AFTER_BLOCK_S = 300
POST_FLOOD_MARGIN_S = 900
TOO_MANY_CHANNELS_PAUSE_S = 3 * 86400
UNKNOWN_ERROR_PAUSE_S = 3600
DIALOGS_REFRESH_S = 3600
HANDLE_DEFER_S = 7200

_started = False
_joined_cache = {"at": 0.0, "names": set()}


def _load():
    try:
        st = json.loads(STATE.read_text())
    except Exception:
        st = {}
    st.setdefault("done", [])
    st.setdefault("skip", {})
    st.setdefault("defer", {})
    st.setdefault("not_before", 0.0)
    st.setdefault("next_at", 0.0)
    st.setdefault("day", "")
    st.setdefault("day_count", 0)
    return st


def _save(st):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(st, indent=1))


def _targets():
    try:
        lines = TARGETS.read_text().splitlines()
    except Exception:
        return []
    out = []
    for ln in lines:
        h = ln.strip().lstrip("@").lower()
        if h and not h.startswith("#") and h not in out:
            out.append(h)
    return out


def _already_known(client, handle):
    try:
        rows = client.session.get_entity_rows_by_username(handle)
        return bool(rows)
    except Exception:
        return False


def _dialog_usernames(dialogs):
    """Lowercased usernames from an iterable of Telethon dialogs/entities."""
    names = set()
    for d in dialogs or []:
        ent = getattr(d, "entity", d)
        name = getattr(ent, "username", None)
        if name:
            names.add(str(name).strip().lstrip("@").lower())
    return names


def _pick_pending(targets, done, skip, defer, now):
    """First target not done/skipped whose per-handle defer has expired."""
    done_s, skip_s = set(done or []), set(skip or {})
    defer = defer or {}
    for h in targets or []:
        if h in done_s or h in skip_s:
            continue
        if float(defer.get(h, 0) or 0) > now:
            continue
        return h
    return None


def _mark_joined(targets, joined_names, st):
    """Move every target already in the dialog list to done. Returns count."""
    joined = set(joined_names or set())
    n = 0
    for h in targets or []:
        if h in joined and h not in st["done"] and h not in st["skip"]:
            st["done"].append(h)
            st.get("defer", {}).pop(h, None)
            n += 1
    return n


async def _refresh_joined(client, targets, st):
    """Refresh the joined set from the dialog list and bulk-mark done.

    One GetDialogs call for the whole account — no username resolution, so it
    cannot trip the ResolveUsername guard or a FloodWait on lookups. Falls
    back to the session entity cache if the dialog fetch fails.
    """
    now = time.time()
    if now - _joined_cache["at"] < DIALOGS_REFRESH_S and _joined_cache["names"]:
        return _mark_joined(targets, _joined_cache["names"], st)
    try:
        dialogs = await asyncio.wait_for(client.get_dialogs(), timeout=120)
        _joined_cache["names"] = _dialog_usernames(dialogs)
        _joined_cache["at"] = now
    except Exception as exc:
        log.warning("[SlowJoin] dialog list unavailable (%s) - using session cache", type(exc).__name__)
        _joined_cache["names"] = {h for h in targets if _already_known(client, h)}
        _joined_cache["at"] = now
    n = _mark_joined(targets, _joined_cache["names"], st)
    if n:
        log.info("[SlowJoin] marked %d already-joined rooms from dialogs (no lookups, no cap used)", n)
    return n


async def _join_one(client, handle, nul, errors, functions, types):
    nul.JOIN_ALLOW.add(handle)
    try:
        ent = await asyncio.wait_for(client.get_entity(handle), timeout=45)
    finally:
        nul.JOIN_ALLOW.discard(handle)
    if not isinstance(ent, types.Channel):
        return "skip", "not a channel (user/bot/group)"
    try:
        await client(functions.channels.JoinChannelRequest(ent))
    except errors.UserAlreadyParticipantError:
        return "member", "already member"
    except errors.InviteRequestSentError:
        return "skip", "join request sent, needs admin approval"
    return "done", "joined"


async def slow_join_loop(client):
    import no_username_lookup as nul
    from telethon import errors, functions, types

    if not hasattr(nul, "JOIN_ALLOW"):
        log.warning("guard not patched (run: python slow_join.py --patch-guard) - joiner disabled")
        return

    while True:
        await asyncio.sleep(60)
        try:
            st = _load()
            now = time.time()
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            if st["day"] != today:
                st["day"], st["day_count"] = today, 0
            if now < max(st["not_before"], nul._blocked_until() + MARGIN_AFTER_BLOCK_S):
                continue
            targets = _targets()
            if await _refresh_joined(client, targets, st):
                _save(st)
            pending = [h for h in targets if h not in st["done"] and h not in st["skip"]]
            if not pending:
                log.info("[SlowJoin] nothing left to join (%d done, %d skipped)", len(st["done"]), len(st["skip"]))
                _save(st)
                await asyncio.sleep(3600)
                continue
            handle = _pick_pending(targets, st["done"], st["skip"], st["defer"], now)
            if handle is None:
                continue  # every remaining handle is in its own defer window
            if now < st["next_at"] or st["day_count"] >= PER_DAY:
                continue
            if _already_known(client, handle):
                st["done"].append(handle)
                _save(st)
                continue
            st["next_at"] = now + random.uniform(GAP_MIN_S, GAP_MAX_S)
            try:
                kind, why = await _join_one(client, handle, nul, errors, functions, types)
                if kind == "done":
                    st["done"].append(handle)
                    st["day_count"] += 1
                    _joined_cache["names"].add(handle)
                elif kind == "member":
                    st["done"].append(handle)
                    _joined_cache["names"].add(handle)
                else:
                    st["skip"][handle] = why
                st["defer"].pop(handle, None)
                log.info("[SlowJoin] @%s -> %s (%s) | %d/%d today, %d left",
                         handle, kind, why, st["day_count"], PER_DAY, len(pending) - 1)
            except errors.FloodWaitError as exc:
                wait = int(getattr(exc, "seconds", 3600))
                st["not_before"] = time.time() + wait + POST_FLOOD_MARGIN_S
                nul._block(wait)
                log.warning("[SlowJoin] FloodWait %ss on @%s - pausing joiner", wait, handle)
            except (errors.UsernameNotOccupiedError, errors.UsernameInvalidError):
                st["skip"][handle] = "username does not exist"
            except (asyncio.TimeoutError, TimeoutError):
                # wait_for() timeouts have an empty str(), which used to read
                # as a blank error and pause the whole queue at its head.
                st["defer"][handle] = time.time() + HANDLE_DEFER_S
                log.warning("[SlowJoin] @%s lookup timed out - deferred 2h, moving on", handle)
            except ValueError as exc:
                # Telethon's get_entity raises ValueError("No user has ...")
                # for dead handles instead of UsernameNotOccupiedError.
                # Without this, a dead room sits at the head of the queue
                # and is retried every hour forever, blocking all joins.
                if "No user has" in str(exc) or "username" in str(exc).lower():
                    st["skip"][handle] = "username does not exist"
                    log.info("[SlowJoin] @%s -> skip (username does not exist)", handle)
                else:
                    st["defer"][handle] = time.time() + HANDLE_DEFER_S
                    log.warning("[SlowJoin] @%s error: %s - deferred 2h, moving on", handle, exc)
            except errors.ChannelPrivateError:
                st["skip"][handle] = "private / banned"
            except errors.ChannelsTooMuchError:
                st["not_before"] = time.time() + TOO_MANY_CHANNELS_PAUSE_S
                log.warning("[SlowJoin] account at joined-channels limit - pausing 3 days")
            except Exception as exc:
                st["defer"][handle] = time.time() + HANDLE_DEFER_S
                log.warning("[SlowJoin] @%s error: %s (%s) - deferred 2h, moving on",
                            handle, type(exc).__name__, exc)
            _save(st)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.warning("[SlowJoin] loop error: %s", exc)
            await asyncio.sleep(300)


def ensure_started():
    global _started
    if _started or not TARGETS.exists():
        return
    try:
        import state
        client = getattr(state, "client", None)
        if client is None:
            return
        asyncio.get_running_loop().create_task(slow_join_loop(client))
        _started = True
        log.info("[SlowJoin] started (%d targets, <=%d/day)", len(_targets()), PER_DAY)
    except Exception as exc:
        log.warning("[SlowJoin] could not start: %s", exc)


OLD_SEEN = "_SEEN = set()\n"
NEW_SEEN = "_SEEN = set()\nJOIN_ALLOW = set()\n"
OLD_COND = (
    "            if name and name == _TARGET and now >= _blocked_until() and now - _LAST_TARGET > 900:\n"
    "                _LAST_TARGET = now\n"
)
NEW_COND = (
    "            _joinok = name in JOIN_ALLOW\n"
    "            if name and (_joinok or name == _TARGET) and now >= _blocked_until() and (_joinok or now - _LAST_TARGET > 900):\n"
    "                if not _joinok:\n"
    "                    _LAST_TARGET = now\n"
)


def patch_guard(path=None):
    p = Path(path) if path else HERE / "no_username_lookup.py"
    src = p.read_text()
    if "JOIN_ALLOW" in src:
        print("guard already patched")
        return 0
    if OLD_SEEN not in src or OLD_COND not in src:
        print("guard layout not recognised - not modified")
        return 1
    p.with_suffix(".py.bak_joinallow").write_text(src)
    p.write_text(src.replace(OLD_SEEN, NEW_SEEN, 1).replace(OLD_COND, NEW_COND, 1))
    print("guard patched (backup: %s)" % p.with_suffix(".py.bak_joinallow").name)
    return 0


if __name__ == "__main__":
    if "--patch-guard" in sys.argv:
        sys.exit(patch_guard())
    print(__doc__)
