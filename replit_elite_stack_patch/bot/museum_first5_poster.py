#!/usr/bin/env python3
"""
museum_first5_poster.py — post the first 5 historical FIRE→RESULT pairs to Telegram.

Opinion: best bootstrap. Seeing day-one DNA in chat beats more abstract routing talk.

Uses museum_first5_fire_result.json (built from Vany export).
Requires Telethon session on the Replit host (same as outbox).

Env:
  TELEGRAM_SESSION_STRING / .telegram_session_string
  TELEGRAM_API_ID / TELEGRAM_API_HASH (or config)
  TELEGRAM_TARGET_PEER=6774605259   (Mr_iv4 default)
  MUSEUM_ALSO_GUNIQUE=1             also post pack header to @UNIQUE_g1
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent if (HERE.parent / "bacbo_royal_complete.py").exists() else HERE
DATA = HERE / "data"
PACK = DATA / "museum_first5_fire_result.json"


def _session() -> str:
    for key in (
        "TELEGRAM_SESSION_STRING",
        "TELEGRAM_STRING_SESSION",
        "STRING_SESSION",
    ):
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
    if len(text) <= limit:
        return text
    return text[: limit - 20] + "\n…_(truncated)_"


async def main() -> int:
    if not PACK.exists():
        print("MISSING", PACK)
        return 2
    pack = json.loads(PACK.read_text(encoding="utf-8"))
    pairs = pack.get("pairs") or []
    if len(pairs) < 1:
        print("No pairs in pack")
        return 2

    session = _session()
    if not session:
        print("NO_TELEGRAM_SESSION — run on Replit host with outbox session")
        return 3

    try:
        from telethon import TelegramClient
        from telethon.sessions import StringSession
    except Exception as exc:
        print("telethon missing:", exc)
        return 4

    api_id = os.getenv("TELEGRAM_API_ID") or os.getenv("API_ID")
    api_hash = os.getenv("TELEGRAM_API_HASH") or os.getenv("API_HASH")
    if not api_id or not api_hash:
        try:
            import config  # type: ignore

            api_id = api_id or str(getattr(config, "API_ID", "") or getattr(config, "TELEGRAM_API_ID", ""))
            api_hash = api_hash or str(getattr(config, "API_HASH", "") or getattr(config, "TELEGRAM_API_HASH", ""))
        except Exception:
            pass
    if not api_id or not api_hash:
        print("NO_API_ID_HASH")
        return 5

    peer = (os.environ.get("TELEGRAM_TARGET_PEER") or "6774605259").strip().lstrip("@")
    client = TelegramClient(StringSession(session), int(api_id), api_hash)
    await client.connect()
    if not await client.is_user_authorized():
        print("SESSION_NOT_AUTHORIZED")
        await client.disconnect()
        return 6

    if peer.lstrip("-").isdigit():
        entity = await client.get_entity(int(peer))
    else:
        entity = await client.get_entity(peer)

    header = (
        "🏛 MUSEUM PACK — FIRST 5 FIRE→RESULT PAIRS EVER (day-one DNA)\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "Raw historical templates · good or bad · not live bets\n"
        "Source: Vany chat chronology · first complete glued pairs\n"
        "Purpose: see real signal+result skins before more routing theory\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━"
    )
    await client.send_message(entity, header)
    print("sent header →", peer)

    for p in pairs[:5]:
        idx = p.get("index")
        fire_body = (
            f"🏛 MUSEUM #{idx}/5 — SIGNAL FIRE (historical)\n"
            f"⏰ original: {p.get('fire_at')}\n"
            f"id: {p.get('fire_message_id')}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{_clip(p.get('fire_text') or '')}"
        )
        await client.send_message(entity, fire_body)
        await asyncio.sleep(0.4)
        res_body = (
            f"🏛 MUSEUM #{idx}/5 — RESULT CARD (historical)\n"
            f"⏰ original: {p.get('result_at')} · gap {p.get('gap_secs')}s\n"
            f"id: {p.get('result_message_id')}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{_clip(p.get('result_text') or '')}"
        )
        await client.send_message(entity, res_body)
        await asyncio.sleep(0.6)
        print(f"sent pair #{idx}")

    footer = (
        "✅ MUSEUM #1–5 posted.\n"
        "Next museum packs can be: first WITH_TIMING five · first LOSS five · first Clock-A five."
    )
    await client.send_message(entity, footer)

    if os.environ.get("MUSEUM_ALSO_GUNIQUE", "0").strip() in {"1", "true", "yes"}:
        cd = (os.environ.get("TELEGRAM_COUNTDOWN_PEER") or "UNIQUE_g1").strip().lstrip("@")
        try:
            cd_ent = await client.get_entity(cd)
            await client.send_message(
                cd_ent,
                header + "\n\n_(copy notice — full museum pack posted to Mr_iv4)_",
            )
            print("pinged gunique")
        except Exception as exc:
            print("gunique skip:", exc)

    await client.disconnect()
    print("DONE museum first5")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main()))
    except KeyboardInterrupt:
        raise SystemExit(130)
