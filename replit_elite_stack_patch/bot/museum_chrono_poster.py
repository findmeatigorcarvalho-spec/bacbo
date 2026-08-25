#!/usr/bin/env python3
"""
museum_chrono_poster.py — post signal FIRE→RESULT pairs in pure chronological order.

User axis (locked):
  NOT filtered by WITH_TIMING / Clock A / kind buckets.
  Whatever signal was ever created, first → last, BEFORE stacking/categorizing them.

Uses museum_chrono_all_pairs.json (pre-stack era pairs preferred).

Env:
  MUSEUM_OFFSET=5     # skip already-posted (first5 used 0..4 → next is 5)
  MUSEUM_LIMIT=5      # how many pairs this run
  TELEGRAM_TARGET_PEER=6774605259
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent if (HERE.parent / "bacbo_royal_complete.py").exists() else HERE
PACK = HERE / "data" / "museum_chrono_all_pairs.json"
FALLBACK = HERE / "data" / "museum_first5_fire_result.json"


def _session() -> str:
    # The safe review launcher requires a dedicated museum account. Do not
    # fall back to the money bot's StringSession when that boundary is armed.
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
    for p in (ROOT / ".telegram_session_string", HERE / ".telegram_session_string", Path(".telegram_session_string")):
        if p.exists():
            v = p.read_text(encoding="utf-8", errors="ignore").strip()
            if len(v) > 50:
                return v
    return ""


def _clip(text: str, limit: int = 3500) -> str:
    text = (text or "").strip()
    return text if len(text) <= limit else text[: limit - 20] + "\n…_(truncated)_"


def _load_pairs() -> tuple[list[dict], dict]:
    path = PACK if PACK.exists() else FALLBACK
    data = json.loads(path.read_text(encoding="utf-8"))
    pairs = data.get("pairs") or []
    # normalize keys from first5 pack
    norm = []
    for i, p in enumerate(pairs):
        norm.append(
            {
                "seq": p.get("seq") or p.get("index") or (i + 1),
                "fire_at": p.get("fire_at"),
                "fire_message_id": p.get("fire_message_id"),
                "fire_text": p.get("fire_text") or "",
                "result_at": p.get("result_at"),
                "result_message_id": p.get("result_message_id"),
                "result_text": p.get("result_text") or "",
                "gap_secs": p.get("gap_secs"),
                "pre_stack": p.get("pre_stack", True),
            }
        )
    return norm, data


async def main() -> int:
    pairs, meta = _load_pairs()
    if not pairs:
        print("NO_PAIRS")
        return 2
    offset = max(0, int(os.environ.get("MUSEUM_OFFSET", "5")))
    limit = max(1, int(os.environ.get("MUSEUM_LIMIT", "5")))
    batch = pairs[offset : offset + limit]
    if not batch:
        print(f"EMPTY_BATCH offset={offset} limit={limit} total={len(pairs)}")
        return 2

    session = _session()
    if not session:
        print("NO_TELEGRAM_SESSION — run on Replit")
        return 3

    from telethon import TelegramClient
    from telethon.sessions import StringSession

    api_id = (
        os.getenv("MUSEUM_TELEGRAM_API_ID")
        or os.getenv("TELEGRAM_API_ID")
        or os.getenv("API_ID")
    )
    api_hash = (
        os.getenv("MUSEUM_TELEGRAM_API_HASH")
        or os.getenv("TELEGRAM_API_HASH")
        or os.getenv("API_HASH")
    )
    if not api_id or not api_hash:
        try:
            import config  # type: ignore

            api_id = api_id or str(getattr(config, "API_ID", "") or "")
            api_hash = api_hash or str(getattr(config, "API_HASH", "") or "")
        except Exception:
            pass
    if not api_id or not api_hash:
        print("NO_API_ID_HASH")
        return 5

    peer = (
        os.environ.get("MUSEUM_TELEGRAM_TARGET_PEER")
        or os.environ.get("TELEGRAM_TARGET_PEER")
        or "UNIQUE_museum_chrono"
    ).strip().lstrip("@")
    client = TelegramClient(StringSession(session), int(api_id), api_hash)
    await client.connect()
    if not await client.is_user_authorized():
        print("SESSION_NOT_AUTHORIZED")
        await client.disconnect()
        return 6
    entity = await client.get_entity(int(peer) if peer.lstrip("-").isdigit() else peer)

    start_seq = batch[0]["seq"]
    end_seq = batch[-1]["seq"]
    header = (
        "🏛 MUSEUM CHRONO — ALL SIGNALS FIRST→LAST\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "No timing filter · no kind buckets · no stacking yet\n"
        f"Batch seq #{start_seq}–#{end_seq} (offset={offset}, limit={limit})\n"
        "Era: before multi-camada / floor-stack idea when possible\n"
        f"Pre-stack marker in corpus: {meta.get('first_stack_marker_at') or 'n/a'}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━"
    )
    await client.send_message(entity, header)
    print("sent header", start_seq, end_seq)

    for p in batch:
        seq = p["seq"]
        fire_body = (
            f"🏛 CHRONO #{seq} — SIGNAL FIRE (historical)\n"
            f"⏰ {p.get('fire_at')} · pre_stack={p.get('pre_stack')}\n"
            f"id: {p.get('fire_message_id')}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{_clip(p.get('fire_text') or '')}"
        )
        await client.send_message(entity, fire_body)
        await asyncio.sleep(0.35)
        res_body = (
            f"🏛 CHRONO #{seq} — RESULT (historical)\n"
            f"⏰ {p.get('result_at')} · gap {p.get('gap_secs')}s\n"
            f"id: {p.get('result_message_id')}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{_clip(p.get('result_text') or '')}"
        )
        await client.send_message(entity, res_body)
        await asyncio.sleep(0.55)
        print("sent", seq)

    nxt = offset + limit
    await client.send_message(
        entity,
        f"✅ Chrono batch #{start_seq}–#{end_seq} done.\n"
        f"Next: MUSEUM_OFFSET={nxt} MUSEUM_LIMIT=5 (still pure first→last, no stacking).",
    )
    await client.disconnect()
    print("DONE", start_seq, end_seq, "next_offset", nxt)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
