"""
fallback_signal_sender.py - Telegram fallback output for fired DB signals.

Default mode sends new consensus_signals rows.
Volume mode also sends selected blocked_signals rows from gates that ShadowMode
identified as "costing money". Enable with:

  FALLBACK_SEND_BLOCKED=1

This is intentionally separate from signal_handler.py so Telegram output can be
restored even if the native card sender is broken.
"""
from __future__ import annotations

import asyncio
import os
import sqlite3
import sys
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


def _db_ro() -> sqlite3.Connection:
    """Short-lived read-only connection (does not block writers as hard)."""
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
STATE = HERE / "data/fallback_sender_state.txt"
BLOCK_STATE = HERE / "data/fallback_blocked_sender_state.txt"

MIN_BLOCKED_SCORE = float(os.environ.get("FALLBACK_MIN_BLOCKED_SCORE", "4.0"))
SEND_BLOCKED = os.environ.get("FALLBACK_SEND_BLOCKED", "0").strip() == "1"
BLOCKED_LOOKBACK_HOURS = int(os.environ.get("FALLBACK_BLOCKED_LOOKBACK_HOURS", "24"))

COSTING_MONEY_GATES = {
    "auto_vault_block",
    "solo_proven_room_main",
    "g3_predictor_hard",
    "color_acc_all_weak",
    "timing_gate_accum",
    "streak_reversal",
    "post_loss_cooldown",
    "streak_gate",
    "platinum_cold_pair",
    "timing_gate",
    "golden_hour_block",
    "golden_loss_contagion",
    "momentum_lll",
    "room_hour_block",
    "solo_g3_cap",
    "kind_suspended",
    "platinum_hour_block",
    "platinum_dow_block",
    "platinum_pair_hour_block",
    "room_hour_block_platinum",
    "golden_dow_cell_block",
    "coringa_hour_block",
    "solo_conf_floor",
    "solo_threshold",
    "pending_signal_exists",
    "solo_red_death_minute_gate",
    "tight_g3_spread",
    "room_quality_gate",
    "dynamic_threshold_bad_hour",
    "gale_filter",
    "platt_midconf_block",
    "rhc_matrix_block",
    "cross_color_window",
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
        "⚠️ Fallback sender active"
    )


def fmt_blocked(row: sqlite3.Row) -> str:
    color = (row["color"] or "").lower()
    score = row["score"] or 0
    return (
        "🚨 BAC BO VOLUME SIGNAL 🚨\n\n"
        f"{color_emoji(color)} COLOR: {color.upper()}\n"
        f"🎯 MODE: {row['signal_kind'] or 'SIGNAL'}\n"
        "⚡ G0 ONLY\n"
        f"📊 SCORE: {score:.2f}\n"
        f"🧠 UNLOCKED GATE: {row['gate_reason']}\n"
        f"🏠 ROOMS: {row['rooms_agreed'] or 'engine'}\n\n"
        "⚠️ Volume fallback: higher volume, shadow-validated gate"
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
            value = path.read_text(errors="ignore").strip()
            if len(value) > 50:
                return value
    raise FileNotFoundError(
        "Telegram session missing. Set Replit Secret TELEGRAM_SESSION_STRING "
        "or create /home/runner/workspace/.telegram_session_string"
    )


async def _resolve_target(client, target):
    """Resolve Telegram target without hammering ResolveUsername (FloodWait)."""
    import json

    cache = HERE / "data" / "telegram_target_entity.json"
    cache.parent.mkdir(parents=True, exist_ok=True)

    if target is None:
        raise RuntimeError("TARGET missing in config")
    if isinstance(target, int) or (isinstance(target, str) and str(target).lstrip("-").isdigit()):
        return await client.get_entity(int(target))

    peer = os.environ.get("TELEGRAM_TARGET_PEER") or os.environ.get("TARGET_PEER_ID")
    if peer and str(peer).lstrip("-").isdigit():
        return await client.get_entity(int(peer))

    if cache.exists():
        try:
            data = json.loads(cache.read_text())
            if data.get("target") == str(target) and data.get("id") is not None:
                return await client.get_entity(int(data["id"]))
        except Exception:
            pass

    tnorm = str(target).lstrip("@").lower()
    try:
        async for dialog in client.iter_dialogs():
            ent = dialog.entity
            uname = (getattr(ent, "username", None) or "").lower()
            title = (getattr(ent, "title", None) or getattr(ent, "first_name", None) or "").lower()
            if uname == tnorm or title == tnorm or (tnorm and tnorm in uname):
                try:
                    cache.write_text(json.dumps({"target": str(target), "id": int(ent.id)}))
                except Exception:
                    pass
                return ent
    except Exception as exc:
        print("[Fallback] dialogs scan failed:", exc)

    try:
        from telethon.errors import FloodWaitError
    except Exception:  # pragma: no cover
        FloodWaitError = Exception  # type: ignore
    try:
        ent = await client.get_entity(target)
        try:
            cache.write_text(json.dumps({"target": str(target), "id": int(ent.id)}))
        except Exception:
            pass
        return ent
    except FloodWaitError as exc:
        print(
            "[Fallback] FloodWait on ResolveUsername — set TELEGRAM_TARGET_PEER "
            f"to numeric chat id. seconds={getattr(exc, 'seconds', '?')}"
        )
        raise


async def main() -> None:
    load_env()
    api_id = os.getenv("TELEGRAM_API_ID")
    api_hash = os.getenv("TELEGRAM_API_HASH")
    session = _load_telegram_session()
    target = getattr(config, "TARGET", None)

    client = TelegramClient(StringSession(session), int(api_id), api_hash)
    await client.connect()
    entity = await _resolve_target(client, target)
    print(
        f"[FallbackSender] started target={target} send_blocked={SEND_BLOCKED} "
        f"min_blocked_score={MIN_BLOCKED_SCORE} blocked_lookback_h={BLOCKED_LOOKBACK_HOURS}"
    )

    while True:
        try:
            conn = _db_ro()

            last_id = read_int(STATE)
            rows = conn.execute(
                """
                SELECT id, fired_at, signal_kind, color, rooms_agreed, source_floor, total_score
                FROM consensus_signals
                WHERE id > ? AND fired_at >= datetime('now','-2 hours')
                ORDER BY id ASC
                LIMIT 20
                """,
                (last_id,),
            ).fetchall()
            if SEND_BLOCKED:
                last_bid = read_int(BLOCK_STATE)
                blocked_rows = conn.execute(
                    """
                    SELECT id, blocked_at, signal_kind, color, rooms_agreed, score, gate_reason
                    FROM blocked_signals
                    WHERE id > ?
                      AND blocked_at >= datetime('now', ?)
                      AND score >= ?
                    ORDER BY id ASC
                    LIMIT 30
                    """,
                    (last_bid, f"-{BLOCKED_LOOKBACK_HOURS} hours", MIN_BLOCKED_SCORE),
                ).fetchall()
            else:
                blocked_rows = []
            conn.close()

            for row in rows:
                await client.send_message(entity, fmt_consensus(row))
                write_int(STATE, row["id"])
                print("[FallbackSender] sent consensus", row["id"], row["signal_kind"], row["color"])

            if SEND_BLOCKED:
                for row in blocked_rows:
                    gate = row["gate_reason"] or ""
                    if gate in COSTING_MONEY_GATES:
                        await client.send_message(entity, fmt_blocked(row))
                        print("[FallbackSender] sent blocked", row["id"], row["signal_kind"], row["color"], gate)
                    else:
                        print("[FallbackSender] skipped blocked", row["id"], gate)
                    write_int(BLOCK_STATE, row["id"])
        except Exception as exc:
            print("[FallbackSender] error:", repr(exc))

        await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(main())
