#!/usr/bin/env python3
"""Create/resolve museum chat and paced-post every product skin + follow-up cards.

Catalog axis (museum_full_catalog.json):
  CHRONO_FIRST_EXISTENCE — 1st skin ever → example #1, 2nd → #2, …
  Never-fired code skins still appear, after dated ones, in registry order.
  RESULT under FIRE only if that historical signal originally had one.

Safety:
  - Never blast: sleep between messages, respect FloodWait
  - Split bodies so Telegram never truncates mid-card (>~3800)
  - Resume via progress file
  - Catalog samples labeled NOT live bets

Env:
  TELEGRAM_SESSION_STRING / .telegram_session_string
  TELEGRAM_API_ID / TELEGRAM_API_HASH
  MUSEUM_PEER=UNIQUE_museum_chrono   (title/username to create or reuse)
  MUSEUM_SLEEP_FIRE=2.0
  MUSEUM_SLEEP_RESULT=1.2
  MUSEUM_SLEEP_ITEM=2.5
  MUSEUM_LIMIT=0                    (0 = all)
  MUSEUM_OFFSET=0
  MUSEUM_RESET=0                    (1 = wipe progress and re-post)
  MUSEUM_DRY_RUN=0
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, List, Optional


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent if (HERE.parent / ".telegram_session_string").exists() else Path.cwd()
DATA = HERE / "data"
CATALOG = DATA / "museum_full_catalog.json"
PROGRESS = DATA / "museum_unique_progress.json"
CACHE = DATA / "telegram_museum_entity.json"


def _safe_peer(peer: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in (peer or "museum"))


def _progress_path(peer: str, namespace: str = "") -> Path:
    """Separate resume files by chat *and* review pass."""
    suffix = f"_{_safe_peer(namespace)}" if namespace.strip() else ""
    return DATA / f"museum_progress_{_safe_peer(peer)}{suffix}.json"


def _cache_path(peer: str) -> Path:
    """Separate entity cache per museum title — never reuse UNIQUE_museum for chrono."""
    return DATA / f"telegram_museum_entity_{_safe_peer(peer)}.json"


def _session() -> str:
    # Safe museum lane: a dedicated account/session is mandatory.  Never
    # silently fall back to bacbo's .telegram_session_string while it is live.
    museum = (os.environ.get("MUSEUM_TELEGRAM_SESSION_STRING") or "").strip()
    if len(museum) > 50:
        return museum
    if os.environ.get("MUSEUM_REQUIRE_SEPARATE_SESSION", "0").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }:
        return ""
    for key in ("TELEGRAM_SESSION_STRING", "TELEGRAM_STRING_SESSION", "STRING_SESSION"):
        v = (os.environ.get(key) or "").strip()
        if len(v) > 50:
            return v
    for p in (
        ROOT / ".telegram_session_string",
        Path.cwd() / ".telegram_session_string",
        HERE / ".telegram_session_string",
    ):
        if p.exists():
            v = p.read_text(encoding="utf-8", errors="ignore").strip()
            if len(v) > 50:
                return v
    return ""


def _api() -> tuple[str, str]:
    api_id = (
        os.getenv("MUSEUM_TELEGRAM_API_ID")
        or os.getenv("TELEGRAM_API_ID")
        or os.getenv("API_ID")
        or ""
    )
    api_hash = (
        os.getenv("MUSEUM_TELEGRAM_API_HASH")
        or os.getenv("TELEGRAM_API_HASH")
        or os.getenv("API_HASH")
        or ""
    )
    if api_id and api_hash:
        return api_id, api_hash
    try:
        import config  # type: ignore

        api_id = api_id or str(
            getattr(config, "API_ID", "") or getattr(config, "TELEGRAM_API_ID", "")
        )
        api_hash = api_hash or str(
            getattr(config, "API_HASH", "") or getattr(config, "TELEGRAM_API_HASH", "")
        )
    except Exception:
        pass
    return api_id, api_hash


def _chunks(text: str, limit: int = 3800) -> List[str]:
    text = (text or "").rstrip()
    if len(text) <= limit:
        return [text]
    parts: List[str] = []
    while text:
        if len(text) <= limit:
            parts.append(text)
            break
        cut = text.rfind("\n", 0, limit)
        if cut < limit // 2:
            cut = limit
        parts.append(text[:cut].rstrip() + "\n…_(cont)_")
        text = "…_(cont)_\n" + text[cut:].lstrip()
    return parts


def _load_progress(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"done_family_ids": [], "museum_id": None, "sent": 0}


def _save_progress(path: Path, p: dict) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(p, indent=2), encoding="utf-8")
    # Keep the historical compatibility mirror only for the un-namespaced
    # default pass. FIRE review progress must never mark the full parade done.
    default_path = _progress_path("UNIQUE_museum_chrono")
    if path == default_path:
        try:
            PROGRESS.write_text(json.dumps(p, indent=2), encoding="utf-8")
        except Exception:
            pass


async def _sleep_fw(client, seconds: float) -> None:
    try:
        await asyncio.sleep(max(0.2, seconds))
    except Exception:
        time.sleep(max(0.2, seconds))


async def _safe_send(client, entity, text: str, *, dry: bool) -> None:
    from telethon.errors import FloodWaitError

    for part in _chunks(text):
        if dry:
            print(f"DRY {len(part)} chars: {part.splitlines()[0][:80]}")
            continue
        while True:
            try:
                await client.send_message(entity, part)
                break
            except FloodWaitError as fw:
                wait = int(getattr(fw, "seconds", 30)) + 2
                print(f"FloodWait {wait}s — sleeping (no drop)")
                await asyncio.sleep(wait)
            except Exception as exc:
                # one soft retry
                print(f"send error {exc!r} — retry in 5s")
                await asyncio.sleep(5)
                await client.send_message(entity, part)
                break


def _write_cache(path: Path, ent, title: str) -> None:
    path.write_text(
        json.dumps(
            {
                "id": int(ent.id),
                "username": getattr(ent, "username", None),
                "title": getattr(ent, "title", None) or title,
                "wanted_title": title,
            }
        ),
        encoding="utf-8",
    )
    # legacy mirror (debug only) — do not read this for resolve
    try:
        CACHE.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    except Exception:
        pass


async def _resolve_or_create_museum(client, title: str, username: str):
    """Find or create the museum chat for this exact title/username.

    Never fall back to UNIQUE_museum when asking for UNIQUE_museum_chrono.
    """
    from telethon.tl.functions.channels import (
        CreateChannelRequest,
        UpdateUsernameRequest,
    )
    from telethon.errors import FloodWaitError, UsernameOccupiedError, UsernameInvalidError

    cache_path = _cache_path(title)
    want_title = title.casefold()
    want_user = username.casefold().lstrip("@")
    print(f"resolving museum peer title={title!r} username={username!r} …")

    # 1) per-title cache (must match wanted title/username)
    if cache_path.exists():
        try:
            data = json.loads(cache_path.read_text(encoding="utf-8"))
            cached_title = (data.get("title") or data.get("wanted_title") or "").casefold()
            cached_user = (data.get("username") or "").casefold()
            if data.get("id") is not None and (
                cached_title == want_title or (want_user and cached_user == want_user)
            ):
                print(f"cache hit id={data['id']} — get_entity …")
                ent = await client.get_entity(int(data["id"]))
                print(
                    f"museum via cache id={ent.id} "
                    f"title={getattr(ent, 'title', None)}"
                )
                return ent
            print("cache ignored — title/username mismatch for this peer")
        except Exception as exc:
            print("cache miss:", repr(exc))

    # 2) username / title resolve first (fast; avoids long dialog scans)
    username_rate_limited = False
    for cand in (f"@{want_user}" if want_user else None, want_user, title):
        if not cand:
            continue
        for attempt in range(1, 4):
            try:
                print(f"get_entity {cand!r} attempt {attempt} …")
                ent = await client.get_entity(cand)
                got_title = (getattr(ent, "title", None) or "").casefold()
                got_user = (getattr(ent, "username", None) or "").casefold()
                if got_title == want_title or got_user == want_user:
                    print(f"museum via get_entity {cand} id={ent.id}")
                    _write_cache(cache_path, ent, title)
                    return ent
                break
            except FloodWaitError as exc:
                # Never retry a ResolveUsernameRequest during a long server
                # cooldown. A known dialog is enough to resolve this museum.
                username_rate_limited = True
                print(
                    f"username resolve rate-limited ({getattr(exc, 'seconds', '?')}s) "
                    "— skipping direct resolves; scanning dialogs",
                    flush=True,
                )
                break
            except Exception as exc:
                print(f"get_entity {cand!r} failed: {exc!r}")
                await asyncio.sleep(2 * attempt)
        if username_rate_limited:
            break

    # 3) exact dialog match only (cap scan — do not hang forever)
    print("scanning dialogs for exact title/username match …")
    scanned = 0
    max_dialogs = int(os.environ.get("MUSEUM_DIALOG_SCAN_MAX", "500") or 500)
    async for d in client.iter_dialogs():
        scanned += 1
        if scanned % 50 == 0:
            print(f"  … dialogs scanned {scanned}")
        ent = d.entity
        names = {
            (getattr(ent, "username", None) or "").casefold(),
            (getattr(ent, "title", None) or "").casefold(),
            (d.name or "").casefold(),
        }
        if want_title in names or (want_user and want_user in names):
            print(f"museum via dialog id={ent.id} name={d.name}")
            _write_cache(cache_path, ent, title)
            return ent
        if scanned >= max_dialogs:
            print(f"dialog scan cap {max_dialogs} — giving up scan")
            break
    print(f"dialog scan done ({scanned}) — no exact match")

    # 4) create megagroup (chat-like, good for museum scroll)
    print(f"creating museum chat title={title!r} …")
    result = await client(
        CreateChannelRequest(
            title=title,
            about=(
                "Bac Bo skin museum — first-existence order. "
                "Not live bets. Paced catalog."
            ),
            megagroup=True,
        )
    )
    ent = result.chats[0]
    print(f"created museum id={ent.id}")

    try:
        await client(UpdateUsernameRequest(channel=ent, username=username))
        print(f"username set @{username}")
        ent = await client.get_entity(ent.id)
    except (UsernameOccupiedError, UsernameInvalidError) as exc:
        print(f"username skip ({exc}) — using title/id only")
    except Exception as exc:
        print(f"username skip: {exc!r}")

    _write_cache(cache_path, ent, title)
    return ent


async def main() -> int:
    if not CATALOG.exists():
        print("MISSING catalog", CATALOG)
        return 2
    pack = json.loads(CATALOG.read_text(encoding="utf-8"))
    items = pack.get("items") or []
    if not items:
        print("empty catalog")
        return 2

    # Review in deliberate slices (e.g. FIRE first) before the all-template
    # archaeology pass. Empty means the complete 827-template catalog.
    role_filter = {
        x.strip().upper()
        for x in (os.environ.get("MUSEUM_ROLE_FILTER") or "").split(",")
        if x.strip()
    }
    if role_filter:
        items = [x for x in items if (x.get("role") or "").upper() in role_filter]
        if not items:
            print("EMPTY_ROLE_FILTER", ",".join(sorted(role_filter)))
            return 2

    dry = os.environ.get("MUSEUM_DRY_RUN", "0").strip().lower() in {"1", "true", "yes"}
    reset = os.environ.get("MUSEUM_RESET", "0").strip().lower() in {"1", "true", "yes"}
    sleep_fire = float(os.environ.get("MUSEUM_SLEEP_FIRE", "2.0"))
    sleep_res = float(os.environ.get("MUSEUM_SLEEP_RESULT", "1.2"))
    sleep_item = float(os.environ.get("MUSEUM_SLEEP_ITEM", "2.5"))
    offset = int(os.environ.get("MUSEUM_OFFSET", "0") or 0)
    limit = int(os.environ.get("MUSEUM_LIMIT", "0") or 0)
    title = (
        os.environ.get("MUSEUM_PEER") or pack.get("chat_title") or "UNIQUE_museum_chrono"
    ).strip()
    username = (
        os.environ.get("MUSEUM_USERNAME")
        or pack.get("chat_username")
        or "UNIQUE_museum_chrono"
    ).strip().lstrip("@")
    progress_namespace = (os.environ.get("MUSEUM_PROGRESS_NAMESPACE") or "").strip()
    prog_path = _progress_path(title, progress_namespace)

    session = _session()
    if not session:
        print(
            "NO_MUSEUM_TELEGRAM_SESSION — set MUSEUM_TELEGRAM_SESSION_STRING "
            "(safe lane never uses the live bacbo session)"
        )
        return 3
    api_id, api_hash = _api()
    if not api_id or not api_hash:
        print("NO_API_ID_HASH")
        return 5

    from telethon import TelegramClient
    from telethon.sessions import StringSession

    if reset and prog_path.exists():
        prog_path.unlink()
        print("RESET progress", prog_path)

    print("connecting Telegram …")
    client = TelegramClient(StringSession(session), int(api_id), api_hash)
    for attempt in range(1, 6):
        try:
            await client.connect()
            break
        except Exception as exc:
            print(f"connect failed attempt {attempt}: {exc!r}")
            await asyncio.sleep(3 * attempt)
    else:
        print("CONNECT_FAILED")
        return 7
    if not await client.is_user_authorized():
        print("SESSION_NOT_AUTHORIZED")
        await client.disconnect()
        return 6
    print("connected — resolving museum chat …")

    entity = await _resolve_or_create_museum(client, title=title, username=username)
    progress = _load_progress(prog_path)
    progress["museum_id"] = int(getattr(entity, "id", 0) or 0)
    progress["axis"] = pack.get("axis") or "CHRONO_FIRST_EXISTENCE"
    progress["namespace"] = progress_namespace or "all"
    done = set(progress.get("done_family_ids") or [])

    slice_items = items[offset:]
    if limit > 0:
        slice_items = slice_items[:limit]

    total = len(items)
    stats = pack.get("stats") or {}
    header = (
        "🏛 MUSEUM — REVIEW CATALOG\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Axis: {pack.get('axis') or 'CHRONO_EVERYTHING_EXISTENCE'}\n"
        f"Items: {total} "
        f"(dated {stats.get('with_existence_date', '?')} · "
        f"never-fired {stats.get('never_fired_code_order', '?')})\n"
        f"Raw TG types scanned: {stats.get('raw_tg_types_scanned', '?')} "
        "→ distinct templates\n"
        f"Role filter: {', '.join(sorted(role_filter)) if role_filter else 'ALL'}\n"
        "Includes FIRE · RESULT · OPS · ONLINE · news/update · heartbeats\n"
        "Order: 1st existence → #1 · code-only never-fired at end\n"
        "Purpose: last-stage triage — trash vs profit · noise vs value\n"
        "Rule: RESULT under FIRE only if that signal originally had one\n"
        "NOT live bets · paced · FloodWait-safe\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "_Every distinct template since Mar 17 — scroll and judge_"
    )
    if not progress.get("header_sent"):
        await _safe_send(client, entity, header, dry=dry)
        progress["header_sent"] = True
        _save_progress(prog_path, progress)
        await _sleep_fw(client, sleep_item)

    sent = int(progress.get("sent") or 0)
    for n, item in enumerate(slice_items, start=1 + offset):
        fid = item["family_id"]
        if fid in done:
            print(f"skip done {fid}")
            continue

        idx = int(item.get("chrono_order") or n)
        role = item.get("role") or "?"
        exist = item.get("existence_at") or ("never-fired · code order" if item.get("never_fired") else "?")
        fire_msg = (
            f"🏛 MUSEUM · #{idx}/{total} · first existence\n"
            f"`{fid}` · {role}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{item.get('label') or fid}\n"
            f"First existence (UTC): {exist}\n"
            f"Source: {item.get('existence_source') or '-'}\n"
            f"Lane: {item.get('lane') or '-'} · TG hits: {item.get('tg_count') or 0}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{item.get('body') or item.get('example_first_line') or fid}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"_Catalog sample — not a live bet_"
        )
        await _safe_send(client, entity, fire_msg, dry=dry)
        await _sleep_fw(client, sleep_fire)
        sent += 1

        # Only historical follow-ups (original signal had this result). Never invent.
        for fu in item.get("follow_ups") or []:
            if not (fu.get("body") or "").strip():
                continue
            if fu.get("historical") is False:
                continue
            gap = fu.get("gap_secs")
            gap_bit = f" · gap {gap}s" if gap is not None else ""
            fu_msg = (
                f"🏛 MUSEUM · {fu.get('role')} · `{fu.get('family_id')}`\n"
                f"↳ under `{fid}` · original result{gap_bit}\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"{fu.get('body')}\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"_Original result for this signal — not invented_"
            )
            await _safe_send(client, entity, fu_msg, dry=dry)
            await _sleep_fw(client, sleep_res)
            sent += 1

        done.add(fid)
        progress["done_family_ids"] = sorted(done)
        progress["sent"] = sent
        progress["last_family_id"] = fid
        _save_progress(prog_path, progress)
        print(
            f"OK #{idx}/{total} {fid} @ {exist} "
            f"(+{len(item.get('follow_ups') or [])} follow-ups)"
        )
        await _sleep_fw(client, sleep_item)

    footer = (
        f"✅ Museum chrono-existence pass complete\n"
        f"Families posted: {len(done)}/{total}\n"
        f"Messages ~{sent}\n"
        f"_Resume-safe · re-run skips done · MUSEUM_RESET=1 to restart_"
    )
    await _safe_send(client, entity, footer, dry=dry)
    await client.disconnect()
    print("DONE museum →", title, "id=", progress.get("museum_id"), "sent=", sent)
    print("CACHE", CACHE)
    print("PROGRESS", prog_path)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main()))
    except KeyboardInterrupt:
        print("INTERRUPTED — progress saved; re-run to resume")
        raise SystemExit(130)
