"""
botapi_client.py - Telegram Bot API transport with a Telethon-like send_message.

A bot token is a different Telegram identity from the user session, so a
FloodWait on the user account does not apply to it. Used by the fallback
senders when TELEGRAM_BOT_TOKEN (or BOT_TOKEN) is set.

Target chat: TELEGRAM_BOT_CHAT_ID, else TELEGRAM_TARGET_PEER, else TARGET_PEER_ID.
A private chat only works after that user has pressed Start on the bot; a
channel only works if the bot is an admin there.
"""
from __future__ import annotations

import asyncio
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

MSGMAP = Path(__file__).resolve().parent / "data" / "botapi_msgmap.json"


def token() -> str:
    return (os.environ.get("TELEGRAM_BOT_TOKEN") or os.environ.get("BOT_TOKEN") or "").strip()


def chat_id() -> str:
    for key in ("TELEGRAM_BOT_CHAT_ID", "TELEGRAM_TARGET_PEER", "TARGET_PEER_ID"):
        val = (os.environ.get(key) or "").strip()
        if val:
            return val
    return ""


def enabled() -> bool:
    return bool(token() and chat_id())


def _load_map() -> dict:
    try:
        return json.loads(MSGMAP.read_text(encoding="utf-8"))
    except Exception:
        return {}


def remember(signal_id, message_id) -> None:
    if not message_id:
        return
    data = _load_map()
    data[str(signal_id)] = int(message_id)
    if len(data) > 2000:
        data = dict(list(data.items())[-1000:])
    MSGMAP.parent.mkdir(parents=True, exist_ok=True)
    MSGMAP.write_text(json.dumps(data), encoding="utf-8")


def lookup(signal_id):
    return _load_map().get(str(signal_id))


def _post(method: str, payload: dict) -> dict:
    url = f"https://api.telegram.org/bot{token()}/{method}"
    body = urllib.parse.urlencode(payload).encode()
    req = urllib.request.Request(url, data=body)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        try:
            return json.loads(exc.read().decode())
        except Exception:
            return {"ok": False, "description": f"HTTP {exc.code}"}


class BotApiClient:
    async def send_message(self, entity, text, reply_to=None):
        payload = {"chat_id": str(entity), "text": text}
        if reply_to:
            payload["reply_parameters"] = json.dumps(
                {"message_id": int(reply_to), "allow_sending_without_reply": True}
            )
        for _ in range(3):
            res = await asyncio.to_thread(_post, "sendMessage", payload)
            if res.get("ok"):
                return res["result"]["message_id"]
            retry = (res.get("parameters") or {}).get("retry_after")
            if retry and int(retry) <= 30:
                await asyncio.sleep(int(retry) + 1)
                continue
            raise RuntimeError(f"Bot API sendMessage failed: {res.get('description')}")
        raise RuntimeError("Bot API sendMessage failed after retries")
