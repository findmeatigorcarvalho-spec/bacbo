"""Throttled room joiner.

Joins rooms from data/slow_join_targets.txt one at a time with long random
gaps, a daily cap, and a hard stop on any FloodWait. It runs inside the bot
process (never a second client on the same session) and only issues a username
lookup when the shared guard block file has expired.

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

_started = False


def _load():
    try:
        st = json.loads(STATE.read_text())
    except Exception:
        st = {}
    st.setdefault("done", [])
    st.setdefault("skip", {})
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
        return "done", "already member"
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
            if now < st["next_at"] or st["day_count"] >= PER_DAY:
                continue
            pending = [h for h in _targets() if h not in st["done"] and h not in st["skip"]]
            if not pending:
                log.info("[SlowJoin] nothing left to join (%d done, %d skipped)", len(st["done"]), len(st["skip"]))
                _save(st)
                await asyncio.sleep(3600)
                continue
            handle = pending[0]
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
                else:
                    st["skip"][handle] = why
                log.info("[SlowJoin] @%s -> %s (%s) | %d/%d today, %d left",
                         handle, kind, why, st["day_count"], PER_DAY, len(pending) - 1)
            except errors.FloodWaitError as exc:
                wait = int(getattr(exc, "seconds", 3600))
                st["not_before"] = time.time() + wait + POST_FLOOD_MARGIN_S
                nul._block(wait)
                log.warning("[SlowJoin] FloodWait %ss on @%s - pausing joiner", wait, handle)
            except (errors.UsernameNotOccupiedError, errors.UsernameInvalidError):
                st["skip"][handle] = "username does not exist"
            except errors.ChannelPrivateError:
                st["skip"][handle] = "private / banned"
            except errors.ChannelsTooMuchError:
                st["not_before"] = time.time() + TOO_MANY_CHANNELS_PAUSE_S
                log.warning("[SlowJoin] account at joined-channels limit - pausing 3 days")
            except Exception as exc:
                st["not_before"] = time.time() + UNKNOWN_ERROR_PAUSE_S
                log.warning("[SlowJoin] @%s error: %s - pausing 1h", handle, exc)
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
