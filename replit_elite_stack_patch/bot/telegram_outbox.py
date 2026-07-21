"""
telegram_outbox.py — SINGLE Telethon client for all fallback Telegram cards.

Why: bacbo + fallback_signal + fallback_result all used the same StringSession.
Concurrent MTProto clients on one auth key cause silent disconnects / no chat
delivery. This process owns the session for:
  - startup ONLINE ping
  - consensus signal cards
  - result cards under their signal

Enable via TELEGRAM_SINGLE_OUTBOX=1 (runtime_supervisor default when set).
"""
from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

from telethon import TelegramClient
from telethon.sessions import StringSession

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    import lux_sqlite_harden  # noqa: F401,E402
except Exception:
    pass
import config  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DB = HERE / "bacbo.db"
SIG_STATE = HERE / "data/fallback_sender_state.txt"
RES_STATE = HERE / "data/fallback_result_sender_state.txt"
LOCK = HERE / "data/telegram_outbox.lock"

SEND_BLOCKED = os.environ.get("FALLBACK_SEND_BLOCKED", "0").strip() == "1"
MIN_BLOCKED_SCORE = float(os.environ.get("FALLBACK_MIN_BLOCKED_SCORE", "4.0"))
BLOCKED_LOOKBACK_HOURS = int(os.environ.get("FALLBACK_BLOCKED_LOOKBACK_HOURS", "24"))
STARTUP_PING = os.environ.get("TELEGRAM_OUTBOX_STARTUP_PING", "1").strip() not in {
    "0",
    "false",
    "no",
}


def load_env() -> None:
    env = ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text(errors="ignore").splitlines():
        if "=" in line and not line.strip().startswith("#"):
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def read_int(path: Path) -> int:
    try:
        return int(path.read_text().strip())
    except Exception:
        return 0


def write_int(path: Path, value: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(value))


def _db_ro() -> sqlite3.Connection:
    uri = f"file:{DB}?mode=ro&cache=shared"
    try:
        conn = sqlite3.connect(uri, uri=True, timeout=60.0)
    except Exception:
        conn = sqlite3.connect(str(DB), timeout=60.0)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA busy_timeout=60000")
        conn.execute("PRAGMA query_only=ON")
    except Exception:
        pass
    return conn


def color_emoji(color: str) -> str:
    return "🔵" if color == "blue" else "🔴" if color == "red" else "🟡"


def fmt_consensus(row: sqlite3.Row) -> str:
    color = (row["color"] or "").lower()
    score = row["total_score"] or 0
    return (
        "🚨 BAC BO SIGNAL 🚨\n\n"
        f"{color_emoji(color)} COLOR: {color.upper()}\n"
        f"🎯 MODE: {row['signal_kind'] or 'SIGNAL'}\n"
        f"🏛 FLOOR: {row['source_floor'] or 'LIVE'}\n"
        "⚡ G0 ONLY\n"
        f"📊 SCORE: {score:.2f}\n"
        f"🏠 ROOMS: {row['rooms_agreed'] or 'engine'}\n\n"
        "⚠️ Outbox sender active"
    )


def actual_color(predicted: str, outcome: str) -> str:
    predicted = (predicted or "").lower()
    outcome = (outcome or "").lower()
    if outcome == "tie":
        return "tie"
    if outcome == "win":
        return predicted
    if outcome == "loss":
        if predicted == "blue":
            return "red"
        if predicted == "red":
            return "blue"
    return "unknown"


def fmt_time(fired_at: str | None) -> tuple[str, str]:
    try:
        fired_dt = datetime.strptime((fired_at or "")[:19], "%Y-%m-%d %H:%M:%S")
        return (
            (fired_dt - timedelta(hours=3)).strftime("%H:%M"),
            (fired_dt - timedelta(hours=4)).strftime("%H:%M"),
        )
    except Exception:
        return "--:--", "--:--"


def color_icon(color: str) -> str:
    if color == "blue":
        return "🔵"
    if color == "red":
        return "🔴"
    if color == "tie":
        return "🟡"
    return "⚪"


def fmt_result(row: sqlite3.Row) -> str:
    predicted = (row["color"] or "").lower()
    outcome = (row["outcome"] or "").lower()
    actual = actual_color(predicted, outcome)
    brt, edt = fmt_time(row["fired_at"])
    secs = row["secs_to_result"]
    secs_txt = f"{float(secs):.1f}s" if secs is not None else "-"
    gale = int(row["won_at_gale"] or 0)
    pred_icon = color_icon(predicted)
    actual_icon = color_icon(actual)
    result_icon = "✅" if outcome == "win" else "❌" if outcome == "loss" else "🟡"
    if outcome == "win":
        result_label = "G0 WIN" if gale == 0 else f"G{gale} WIN"
    elif outcome == "loss":
        result_label = "LOSS"
    else:
        result_label = "TIE"
    banner = actual_icon * 10
    return (
        f"{banner}\n"
        f"⏰  {brt} BRT  ·  {edt} EDT\n"
        f"{banner}\n"
        f"🔔 {result_icon} {result_label}  ·  #{row['id']}\n"
        f"🎲 Apostou: {pred_icon} {predicted.upper()}  →  Saiu: {actual_icon} {actual.upper()}\n"
        f"🔍 SINAL #{row['id']} — RESUMIDO FORENSE\n"
        f"  Tipo: {row['signal_kind']} · Cor: {predicted.upper()}\n"
        f"  Disparado: {row['fired_at']} UTC\n"
        f"  Resolvido: {row['resolved_at'] or ''} UTC\n"
        f"  ⏱ Intervalo: {secs_txt}\n"
        f"  Resultado: {result_icon} {result_label}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🏁 Aguarde o próximo sinal do bot"
    )


def _load_telegram_session() -> str:
    for key in (
        "TELEGRAM_SESSION_STRING",
        "TELEGRAM_STRING_SESSION",
        "STRING_SESSION",
        "TG_SESSION_STRING",
    ):
        value = (os.environ.get(key) or "").strip()
        if len(value) > 50:
            return value
    for path in (ROOT / ".telegram_session_string", HERE / ".telegram_session_string"):
        if path.exists():
            value = path.read_text().strip()
            if len(value) > 50:
                return value
    raise FileNotFoundError("Telegram session missing (.telegram_session_string)")


def _acquire_lock() -> int:
    """Exclusive flock so only one outbox / ping owns the session."""
    import fcntl

    LOCK.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(LOCK), os.O_CREAT | os.O_RDWR, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        os.close(fd)
        raise RuntimeError("telegram_outbox.lock held — another sender owns the session") from exc
    os.write(fd, f"{os.getpid()}\n".encode())
    return fd


async def _resolve_target(client, target):
    cache = HERE / "data" / "telegram_target_entity.json"
    cache.parent.mkdir(parents=True, exist_ok=True)
    peer = os.environ.get("TELEGRAM_TARGET_PEER") or os.environ.get("TARGET_PEER_ID")
    if peer and str(peer).lstrip("-").isdigit():
        return await client.get_entity(int(peer))
    if isinstance(target, int) or (isinstance(target, str) and str(target).lstrip("-").isdigit()):
        return await client.get_entity(int(target))
    if cache.exists():
        try:
            data = json.loads(cache.read_text())
            if data.get("id") is not None:
                return await client.get_entity(int(data["id"]))
        except Exception:
            pass
    if target is None:
        raise RuntimeError("TARGET missing — set TELEGRAM_TARGET_PEER=6774605259")
    ent = await client.get_entity(target)
    try:
        cache.write_text(json.dumps({"target": str(target), "id": int(ent.id)}))
    except Exception:
        pass
    return ent


async def main() -> None:
    load_env()
    lock_fd = _acquire_lock()
    api_id = os.getenv("TELEGRAM_API_ID") or os.getenv("API_ID")
    api_hash = os.getenv("TELEGRAM_API_HASH") or os.getenv("API_HASH")
    if not api_id or not api_hash:
        try:
            api_id = api_id or str(getattr(config, "API_ID", "") or getattr(config, "TELEGRAM_API_ID", ""))
            api_hash = api_hash or str(getattr(config, "API_HASH", "") or getattr(config, "TELEGRAM_API_HASH", ""))
        except Exception:
            pass
    session = _load_telegram_session()
    target = getattr(config, "TARGET", None)
    peer = os.environ.get("TELEGRAM_TARGET_PEER") or "6774605259"

    client = TelegramClient(StringSession(session), int(api_id), str(api_hash))
    await client.connect()
    if not await client.is_user_authorized():
        print("[Outbox] FAIL: session not authorized")
        await client.disconnect()
        os.close(lock_fd)
        return

    try:
        entity = await _resolve_target(client, target)
    except Exception as exc:
        print("[Outbox] resolve peer fallback:", exc)
        entity = await client.get_entity(int(peer))

    print(
        f"[Outbox] ONLINE peer={getattr(entity, 'username', None) or peer} "
        f"send_blocked={SEND_BLOCKED} pid={os.getpid()}"
    )

    if STARTUP_PING:
        try:
            msg = await client.send_message(
                entity,
                "LUXURY OUTBOX ONLINE\n"
                "Single Telegram session owner.\n"
                "Waiting for engine FIRED → signal/result cards.",
            )
            print("[Outbox] startup ping OK id=", msg.id)
        except Exception as exc:
            print("[Outbox] startup ping FAIL:", repr(exc))

    while True:
        try:
            conn = _db_ro()
            last_sig = read_int(SIG_STATE)
            rows = conn.execute(
                """
                SELECT id, fired_at, signal_kind, color, rooms_agreed, source_floor, total_score
                FROM consensus_signals
                WHERE id > ? AND fired_at >= datetime('now','-2 hours')
                ORDER BY id ASC
                LIMIT 20
                """,
                (last_sig,),
            ).fetchall()

            last_res = read_int(RES_STATE)
            results = conn.execute(
                """
                SELECT id, fired_at, resolved_at, signal_kind, color, outcome,
                       won_at_gale, secs_to_result
                FROM consensus_signals
                WHERE id > ?
                  AND outcome IN ('win','loss','tie')
                  AND fired_at >= datetime('now','-24 hours')
                ORDER BY id ASC
                LIMIT 20
                """,
                (last_res,),
            ).fetchall()
            conn.close()

            # Send signals first, then results for the same ids (card under signal).
            for row in rows:
                await client.send_message(entity, fmt_consensus(row))
                write_int(SIG_STATE, row["id"])
                print("[Outbox] sent signal", row["id"], row["signal_kind"], row["color"], row["source_floor"])

            for row in results:
                await client.send_message(entity, fmt_result(row))
                write_int(RES_STATE, row["id"])
                print("[Outbox] sent result", row["id"], row["outcome"], row["secs_to_result"])
        except Exception as exc:
            print("[Outbox] error:", repr(exc))
            # AuthKeyDuplicated / disconnect — exit so supervisor restarts cleanly
            err = repr(exc)
            if "AuthKey" in err or "authorization key" in err.lower():
                print("[Outbox] FATAL session conflict — exiting")
                break
        await asyncio.sleep(5)

    try:
        await client.disconnect()
    except Exception:
        pass
    try:
        os.close(lock_fd)
    except Exception:
        pass


if __name__ == "__main__":
    asyncio.run(main())
