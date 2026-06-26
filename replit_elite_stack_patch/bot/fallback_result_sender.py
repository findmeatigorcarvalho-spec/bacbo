"""
fallback_result_sender.py - rich Telegram result cards from resolved DB signals.

Watches consensus_signals for newly resolved rows and sends a forensic result
card with BRT/EDT time and exact secs_to_result interval.
"""
from __future__ import annotations

import asyncio
import os
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

from telethon import TelegramClient
from telethon.sessions import StringSession

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config  # noqa: E402


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DB = HERE / "bacbo.db"
STATE = HERE / "data/fallback_result_sender_state.txt"


def load_env() -> None:
    env = ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text(errors="ignore").splitlines():
        if "=" in line and not line.strip().startswith("#"):
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def read_state() -> int:
    try:
        return int(STATE.read_text().strip())
    except Exception:
        return 0


def write_state(value: int) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(str(value))


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


def fmt(row: sqlite3.Row) -> str:
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


async def main() -> None:
    load_env()
    api_id = os.getenv("TELEGRAM_API_ID")
    api_hash = os.getenv("TELEGRAM_API_HASH")
    session = (ROOT / ".telegram_session_string").read_text().strip()
    target = getattr(config, "TARGET", None)

    client = TelegramClient(StringSession(session), int(api_id), api_hash)
    await client.connect()
    entity = await client.get_entity(target)
    print(f"[FallbackResultSender] started target={target}")

    while True:
        try:
            conn = sqlite3.connect(DB)
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
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
                (read_state(),),
            ).fetchall()
            conn.close()

            for row in rows:
                await client.send_message(entity, fmt(row))
                write_state(row["id"])
                print("[FallbackResultSender] sent result", row["id"], row["outcome"], row["secs_to_result"])
        except Exception as exc:
            print("[FallbackResultSender] error:", repr(exc))
        await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(main())
