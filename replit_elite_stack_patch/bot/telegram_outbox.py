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
# Lookback must be wide: SQLite datetime('now') is UTC; engine fired_at can drift.
SIGNAL_LOOKBACK_HOURS = int(os.environ.get("OUTBOX_SIGNAL_LOOKBACK_HOURS", "48"))
RESULT_LOOKBACK_HOURS = int(os.environ.get("OUTBOX_RESULT_LOOKBACK_HOURS", "72"))
HEARTBEAT_EVERY = int(os.environ.get("OUTBOX_HEARTBEAT_EVERY", "12"))  # ~60s at 5s sleep
# NEVER default-mirror. User wants TOTAL SEPARATION, not duplication:
# MONEY fires → Mr_iv4 only; TIMED fires → @UNIQUE_g1 only; results glue under parent.
MIRROR_MONEY_TO_GUNIQUE = os.environ.get("TELEGRAM_MIRROR_MONEY_TO_GUNIQUE", "0").strip().lower() in {
    "1", "true", "yes", "on",
}


def _resolve_db() -> Path:
    """Use the live engine DB (freshest bacbo.db), not a stale sibling copy."""
    env = (os.environ.get("BACBO_DB") or os.environ.get("DB_PATH") or "").strip()
    candidates: list[Path] = []
    if env:
        candidates.append(Path(env))
    candidates.extend(
        [
            HERE / "bacbo.db",
            ROOT / "bacbo.db",
            HERE / "data" / "bacbo.db",
            Path("/home/runner/workspace/bot/bacbo.db"),
            Path("/home/runner/workspace/bacbo.db"),
        ]
    )
    existing = [p for p in candidates if p.exists() and p.is_file()]
    if not existing:
        return HERE / "bacbo.db"
    existing.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return existing[0]


DB = _resolve_db()


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


def _peak_from_json() -> str:
    for path in (HERE / "data" / "luxury_live_floors.json", ROOT / "bot" / "data" / "luxury_live_floors.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        peaks = [str(x).upper() for x in (data.get("peak_day_floors") or []) if str(x).strip()]
        if peaks:
            return peaks[0]
        live = [
            str(x).upper()
            for x in (data.get("live_floors") or data.get("live_building_floors") or [])
            if str(x).strip() and str(x).upper() != "LIVE"
        ]
        if live:
            return live[0]
    return "JUN19"


def _tag_floor_name() -> str:
    """Always return a peak tag for cards — never stay stuck on LIVE in outbox."""
    os.environ.setdefault("LUXURY_FLOOR_ROTATE", "1")
    os.environ.setdefault("LUXURY_FLOOR_ROTATE_MODE", "tag")
    # Outbox must label now; ignore DEFER inherited from luxury_building.env
    os.environ["LUXURY_FLOOR_ROTATE_DEFER_APPLY"] = "0"
    try:
        import importlib
        import lux_floor_rotate as lfr

        # Force apply if rotator never initialized (DEFER / fresh import).
        if not getattr(lfr, "_APPLIED", False):
            try:
                lfr.apply()
            except Exception as exc:
                print("[Outbox] lux_floor_rotate.apply failed:", repr(exc))
        else:
            # Ensure first-touch moved off LIVE
            try:
                with lfr._LOCK:
                    if lfr._FLOOR == "LIVE" or lfr._LAST_ADV <= 0:
                        lfr._LAST_ADV = 0.0
                        lfr._maybe_advance_unlocked()
            except Exception:
                pass
        tag = str(lfr.tag_floor() or "").strip().upper()
        if tag and tag != "LIVE":
            return tag
    except Exception as exc:
        print("[Outbox] tag_floor failed:", repr(exc))
    return _peak_from_json()


def _row_score(row: sqlite3.Row) -> float:
    """Prefer real score columns — total_score is often 0/NULL on Replit DB."""
    for key in ("total_score", "final_score", "confidence_pct", "calibrated_pct"):
        try:
            val = row[key]
        except (IndexError, KeyError):
            continue
        if val is None:
            continue
        try:
            f = float(val)
        except Exception:
            continue
        if f != 0.0:
            return f
    return 0.0


def _row_floor(row: sqlite3.Row) -> str:
    """Tag-mode: engine ContextVar stays LIVE; cards show rotator / peak floor."""
    db_floor = (row["source_floor"] or "").strip().upper() if row["source_floor"] else ""
    if db_floor and db_floor != "LIVE":
        return db_floor
    tag = _tag_floor_name().strip().upper()
    return tag if tag else "JUN19"


def _stamp_floor(signal_id: int, floor: str) -> None:
    """Persist tag onto LIVE rows so DB matches the card."""
    if not floor or floor == "LIVE":
        return
    try:
        conn = sqlite3.connect(str(DB), timeout=30.0)
        conn.execute("PRAGMA busy_timeout=30000")
        conn.execute(
            "UPDATE consensus_signals SET source_floor=? "
            "WHERE id=? AND (source_floor IS NULL OR source_floor='' OR source_floor='LIVE')",
            (floor, signal_id),
        )
        conn.commit()
        conn.close()
    except Exception as exc:
        print("[Outbox] stamp_floor failed:", repr(exc))


def fmt_consensus(row: sqlite3.Row, floor: str | None = None) -> str:
    color = (row["color"] or "").lower()
    score = _row_score(row)
    floor_name = floor or _row_floor(row)
    return (
        "🚨 BAC BO SIGNAL 🚨\n\n"
        f"{color_emoji(color)} COLOR: {color.upper()}\n"
        f"🎯 MODE: {row['signal_kind'] or 'SIGNAL'}\n"
        f"🏛 FLOOR: {floor_name}\n"
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
    global DB
    load_env()
    lock_fd = _acquire_lock()
    # Re-resolve after env load (BACBO_DB may appear in .env)
    DB = _resolve_db()
    boot_tag = _tag_floor_name()
    print(f"[Outbox] boot_tag_floor={boot_tag} db={DB}")
    if not DB.exists():
        print(f"[Outbox] FATAL: DB missing at {DB}")
        os.close(lock_fd)
        return
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

    # Dual-lane SEPARATION (no mirror): money FIRE → Mr_iv4; timed FIRE → @UNIQUE_g1;
    # RESULT always same chat as parent fire (lane persisted by signal id).
    cd_entity = None
    cd_peer = (
        os.environ.get("TELEGRAM_COUNTDOWN_PEER")
        or os.environ.get("GUNIQUE_PEER")
        or os.environ.get("TELEGRAM_GUNIQUE_PEER")
        or "UNIQUE_g1"
    ).strip().lstrip("@")
    if cd_peer:
        try:
            if cd_peer.lstrip("-").isdigit():
                cd_entity = await client.get_entity(int(cd_peer))
            else:
                cd_entity = await client.get_entity(cd_peer)
            print(f"[Outbox] COUNTDOWN/Gunique peer ready: @{cd_peer} (SEPARATE lane, no money mirror)")
        except Exception as exc:
            print("[Outbox] Gunique peer resolve FAIL:", repr(exc))
            cd_entity = None

    def _lane_dests(
        signal_kind: str | None,
        text: str | None = None,
        *,
        signal_id: int | None = None,
        is_result: bool = False,
    ):
        """Return (primary_dest, lane_name, mirror_dests). Mirrors empty unless explicitly enabled."""
        try:
            from dual_lane_router import (
                parent_lane_for,
                persist_fire_lane,
                route_lane,
            )

            parent = parent_lane_for(signal_id) if signal_id is not None else None
            meta = {"is_result": is_result, "parent_lane": parent} if is_result else {}
            lane = route_lane(
                signal_kind=signal_kind,
                text=text,
                meta=meta,
                parent_lane=parent,
            )
            if not is_result and signal_id is not None:
                persist_fire_lane(signal_id, lane)
        except Exception as exc:
            print("[Outbox] lane route error:", repr(exc))
            lane = "MONEY"
        if lane == "COUNTDOWN":
            if cd_entity is not None:
                return cd_entity, "COUNTDOWN", []
            print("[Outbox] CD lane fallback → money peer (Gunique not ready)")
            return entity, "MONEY_FALLBACK_FROM_CD", []
        mirrors = []
        if MIRROR_MONEY_TO_GUNIQUE and cd_entity is not None:
            try:
                if int(getattr(cd_entity, "id", 0) or 0) != int(getattr(entity, "id", 0) or 0):
                    mirrors.append(cd_entity)
            except Exception:
                mirrors.append(cd_entity)
        return entity, "MONEY", mirrors

    async def _send_all(dests, body: str):
        last = None
        for dest in dests:
            last = await client.send_message(dest, body)
        return last

    print(
        f"[Outbox] ONLINE money={getattr(entity, 'username', None) or peer} "
        f"gunique=@{cd_peer or 'UNSET'} mirror_money={MIRROR_MONEY_TO_GUNIQUE} "
        f"separation=1 send_blocked={SEND_BLOCKED} tag={boot_tag} pid={os.getpid()} db={DB}"
    )

    if STARTUP_PING:
        ping_money = (
            "LUXURY OUTBOX ONLINE — MONEY LANE\n"
            f"Tag floor: {boot_tag}\n"
            f"DB: {DB.name}\n"
            "Lane: FIRE without bet-window/janela → Mr_iv4 ONLY\n"
            "Results for those fires glue here (Intervalo on result ≠ countdown fire).\n"
            "No mirror to @UNIQUE_g1."
        )
        ping_cd = (
            "LUXURY OUTBOX ONLINE — TIMED/COUNTDOWN LANE\n"
            f"Tag floor: {boot_tag}\n"
            f"DB: {DB.name}\n"
            "Lane: FIRE with JANELA / Ns para apostar / CD_FIRE → @UNIQUE_g1 ONLY\n"
            "Those fires still get their OWN result cards here.\n"
            "Not a money mirror — total separation."
        )
        try:
            msg = await client.send_message(entity, ping_money)
            print("[Outbox] startup ping Mr_iv4 OK id=", msg.id)
        except Exception as exc:
            print("[Outbox] startup ping Mr_iv4 FAIL:", repr(exc))
        if cd_entity is not None:
            try:
                msg2 = await client.send_message(cd_entity, ping_cd)
                print("[Outbox] startup ping Gunique OK id=", msg2.id)
            except Exception as exc:
                print("[Outbox] startup ping Gunique FAIL:", repr(exc))

    try:
        conn0 = _db_ro()
        mx = conn0.execute("SELECT MAX(id), MAX(fired_at) FROM consensus_signals").fetchone()
        conn0.close()
        print(
            f"[Outbox] db_max_id={mx[0]} db_max_fired={mx[1]} "
            f"sig_state={read_int(SIG_STATE)} res_state={read_int(RES_STATE)}"
        )
    except Exception as exc:
        print("[Outbox] db probe FAIL:", repr(exc))

    tick = 0
    while True:
        try:
            if SEND_BLOCKED:
                if tick % HEARTBEAT_EVERY == 0:
                    print("[Outbox] HEARTBEAT send_blocked=1 — not sending")
                tick += 1
                await asyncio.sleep(5)
                continue

            conn = _db_ro()
            last_sig = read_int(SIG_STATE)
            lookback_sig = f"-{SIGNAL_LOOKBACK_HOURS} hours"
            try:
                rows = conn.execute(
                    """
                    SELECT id, fired_at, signal_kind, color, rooms_agreed, source_floor,
                           total_score, final_score, confidence_pct, calibrated_pct
                    FROM consensus_signals
                    WHERE id > ?
                      AND (
                        fired_at IS NULL
                        OR fired_at >= datetime('now', ?)
                        OR id > ? - 50
                      )
                    ORDER BY id ASC
                    LIMIT 30
                    """,
                    (last_sig, lookback_sig, last_sig),
                ).fetchall()
            except sqlite3.OperationalError:
                rows = conn.execute(
                    """
                    SELECT id, fired_at, signal_kind, color, rooms_agreed, source_floor, total_score
                    FROM consensus_signals
                    WHERE id > ?
                    ORDER BY id ASC
                    LIMIT 30
                    """,
                    (last_sig,),
                ).fetchall()

            last_res = read_int(RES_STATE)
            lookback_res = f"-{RESULT_LOOKBACK_HOURS} hours"
            results = conn.execute(
                """
                SELECT id, fired_at, resolved_at, signal_kind, color, outcome,
                       won_at_gale, secs_to_result, source_floor
                FROM consensus_signals
                WHERE id > ?
                  AND outcome IN ('win','loss','tie')
                  AND (
                    fired_at IS NULL
                    OR fired_at >= datetime('now', ?)
                    OR id > ? - 50
                  )
                ORDER BY id ASC
                LIMIT 30
                """,
                (last_res, lookback_res, last_res),
            ).fetchall()

            if tick % HEARTBEAT_EVERY == 0:
                try:
                    abs_mx = conn.execute(
                        "SELECT MAX(id), MAX(fired_at) FROM consensus_signals"
                    ).fetchone()
                    mx = conn.execute(
                        "SELECT MAX(id), COUNT(*) FROM consensus_signals WHERE id > ?",
                        (last_sig,),
                    ).fetchone()
                    recent = conn.execute(
                        "SELECT COUNT(*) FROM consensus_signals "
                        "WHERE fired_at >= datetime('now','-30 minutes')"
                    ).fetchone()[0]
                    print(
                        f"[Outbox] HEARTBEAT last_sig={last_sig} abs_max_id={abs_mx[0]} "
                        f"abs_max_fired={abs_mx[1]} pending={mx[1]} recent_30m={recent} "
                        f"pending_send={len(rows)} pending_res={len(results)}"
                    )
                    if recent == 0 and (mx[1] or 0) == 0:
                        print(
                            "[Outbox] NOTE engine quiet — no new consensus rows; "
                            "outbox is caught up (not a Telegram send failure)"
                        )
                except Exception as exc:
                    print("[Outbox] HEARTBEAT probe fail:", repr(exc))

            conn.close()

            lane_by_id: dict[int, tuple] = {}
            for row in rows:
                try:
                    floor = _row_floor(row)
                    _stamp_floor(int(row["id"]), floor)
                    body = fmt_consensus(row, floor=floor)
                    dest, lane, mirrors = _lane_dests(
                        row["signal_kind"],
                        text=body,
                        signal_id=int(row["id"]),
                        is_result=False,
                    )
                    dests = [dest] + list(mirrors)
                    lane_by_id[int(row["id"])] = (dest, lane, mirrors)
                    await _send_all(dests, body)
                    write_int(SIG_STATE, row["id"])
                    print(
                        "[Outbox] sent signal",
                        row["id"],
                        row["signal_kind"],
                        row["color"],
                        floor,
                        "lane",
                        lane,
                        "mirrors",
                        len(mirrors),
                        "score",
                        _row_score(row),
                    )
                    try:
                        from zero_miss_ledger import record_proposal

                        record_proposal(
                            signal_id=row["id"],
                            floors=[floor],
                            color=str(row["color"] or ""),
                            kind=str(row["signal_kind"] or ""),
                            lane=str(lane),
                            decision="SENT",
                        )
                    except Exception:
                        pass
                except Exception as exc:
                    print("[Outbox] SEND SIGNAL FAIL id=", row["id"], repr(exc))
                    break

            for row in results:
                try:
                    res_body = fmt_result(row)
                    cached = lane_by_id.get(int(row["id"]))
                    if cached:
                        dest, lane, mirrors = cached
                    else:
                        dest, lane, mirrors = _lane_dests(
                            row["signal_kind"],
                            text=res_body,
                            signal_id=int(row["id"]),
                            is_result=True,
                        )
                    dests = [dest] + list(mirrors)
                    await _send_all(dests, res_body)
                    write_int(RES_STATE, row["id"])
                    print(
                        "[Outbox] sent result",
                        row["id"],
                        row["outcome"],
                        row["secs_to_result"],
                        "lane",
                        lane,
                        "mirrors",
                        len(mirrors),
                    )
                    try:
                        from zero_miss_ledger import record_resolve

                        pred = str(row["color"] or "")
                        outc = str(row["outcome"] or "")
                        record_resolve(
                            signal_id=row["id"],
                            outcome=outc,
                            predicted=pred,
                            actual=actual_color(pred, outc),
                            g0=int(row["won_at_gale"] or 0) == 0 and outc == "win",
                        )
                    except Exception:
                        pass
                except Exception as exc:
                    print("[Outbox] SEND RESULT FAIL id=", row["id"], repr(exc))
                    break
        except Exception as exc:
            print("[Outbox] error:", repr(exc))
            err = repr(exc)
            if "AuthKey" in err or "authorization key" in err.lower():
                print("[Outbox] FATAL session conflict — exiting")
                break
        tick += 1
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
