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


def _progress_path(peer: str) -> Path:
    """Separate resume files per museum chat so chrono ≠ old registry dump."""
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in (peer or "museum"))
    return DATA / f"museum_progress_{safe}.json"


def _session() -> str:
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
    api_id = os.getenv("TELEGRAM_API_ID") or os.getenv("API_ID") or ""
    api_hash = os.getenv("TELEGRAM_API_HASH") or os.getenv("API_HASH") or ""
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
    # keep legacy path mirrored for the default chrono peer
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


async def _resolve_or_create_museum(client, title: str, username: str):
    """Find existing UNIQUE_museum dialog or create a megagroup/channel."""
    from telethon.tl.functions.channels import (
        CreateChannelRequest,
        UpdateUsernameRequest,
    )
    from telethon.errors import UsernameOccupiedError, UsernameInvalidError

    # 1) cache
    if CACHE.exists():
        try:
            data = json.loads(CACHE.read_text())
            if data.get("id") is not None:
                ent = await client.get_entity(int(data["id"]))
                print(f"museum via cache id={ent.id} title={getattr(ent,'title',None)}")
                return ent
        except Exception as exc:
            print("cache miss:", exc)

    # 2) dialog scan
    want = {title.casefold(), username.casefold(), "unique_museum", "museum"}
    async for d in client.iter_dialogs():
        ent = d.entity
        names = {
            (getattr(ent, "username", None) or "").casefold(),
            (getattr(ent, "title", None) or "").casefold(),
            (d.name or "").casefold(),
        }
        if names & want:
            print(f"museum via dialog id={ent.id} name={d.name}")
            CACHE.write_text(
                json.dumps(
                    {
                        "id": int(ent.id),
                        "username": getattr(ent, "username", None),
                        "title": getattr(ent, "title", None),
                    }
                ),
                encoding="utf-8",
            )
            return ent

    # 3) try username resolve
    for cand in (username, f"@{username}", title):
        try:
            ent = await client.get_entity(cand)
            print(f"museum via get_entity {cand} id={ent.id}")
            CACHE.write_text(
                json.dumps(
                    {
                        "id": int(ent.id),
                        "username": getattr(ent, "username", None),
                        "title": getattr(ent, "title", None),
                    }
                ),
                encoding="utf-8",
            )
            return ent
        except Exception:
            pass

    # 4) create megagroup (chat-like, good for museum scroll)
    print(f"creating museum chat title={title!r} …")
    result = await client(
        CreateChannelRequest(
            title=title,
            about="Bac Bo skin museum — every product FIRE + glued RESULT/OPS. Not live bets. Paced catalog.",
            megagroup=True,
        )
    )
    ent = result.chats[0]
    print(f"created museum id={ent.id}")

    # optional public username (may fail if taken — title alone is enough)
    try:
        await client(UpdateUsernameRequest(channel=ent, username=username))
        print(f"username set @{username}")
        ent = await client.get_entity(ent.id)
    except (UsernameOccupiedError, UsernameInvalidError) as exc:
        print(f"username skip ({exc}) — using title/id only")
    except Exception as exc:
        print(f"username skip: {exc!r}")

    CACHE.write_text(
        json.dumps(
            {
                "id": int(ent.id),
                "username": getattr(ent, "username", None),
                "title": getattr(ent, "title", None) or title,
            }
        ),
        encoding="utf-8",
    )
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
    prog_path = _progress_path(title)

    session = _session()
    if not session:
        print("NO_TELEGRAM_SESSION — run on Replit with .telegram_session_string")
        return 3
    api_id, api_hash = _api()
    if not api_id or not api_hash:
        print("NO_API_ID_HASH")
        return 5

    from telethon import TelegramClient
    from telethon.sessions import StringSession

    client = TelegramClient(StringSession(session), int(api_id), api_hash)
    await client.connect()
    if not await client.is_user_authorized():
        print("SESSION_NOT_AUTHORIZED")
        await client.disconnect()
        return 6

    entity = await _resolve_or_create_museum(client, title=title, username=username)
    if reset and prog_path.exists():
        prog_path.unlink()
        print("RESET progress", prog_path)
    progress = _load_progress(prog_path)
    progress["museum_id"] = int(getattr(entity, "id", 0) or 0)
    progress["axis"] = pack.get("axis") or "CHRONO_FIRST_EXISTENCE"
    done = set(progress.get("done_family_ids") or [])

    slice_items = items[offset:]
    if limit > 0:
        slice_items = slice_items[:limit]

    total = len(items)
    stats = pack.get("stats") or {}
    header = (
        "🏛 MUSEUM — FIRST EXISTENCE ORDER\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Axis: {pack.get('axis') or 'CHRONO_FIRST_EXISTENCE'}\n"
        f"Items: {total} "
        f"(dated {stats.get('with_existence_date', '?')} · "
        f"never-fired {stats.get('never_fired_code_order', '?')})\n"
        "Order: 1st skin ever → #1 · 2nd → #2 · …\n"
        "Never-fired skins still included (code/registry order after dated)\n"
        "Rule: RESULT under a FIRE only if that signal originally had one\n"
        "Purpose: parade of existence — NOT live bets\n"
        "Pace: slow send · FloodWait-safe · no truncate\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "_Scroll chronologically — birth order of each skin_"
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
