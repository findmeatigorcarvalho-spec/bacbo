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
import time
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
# Profit Chat Bundle: APEX=UNIQUE_g1 (#1). Mr_iv4 removed. Results glue under parent.
MIRROR_MONEY_TO_GUNIQUE = os.environ.get("TELEGRAM_MIRROR_MONEY_TO_GUNIQUE", "0").strip().lower() in {
    "1", "true", "yes", "on",
}
HUB_MAX = os.environ.get("HUB_MAX", "0").strip() not in {"0", "false", "no", "off"}


def _env_flag(name: str, default: str = "0") -> bool:
    return os.environ.get(name, default).strip().lower() not in {"0", "false", "no", "off"}


# When HUB_MAX: engine owns original rich skins; outbox must not duplicate fire cards.
# Set HUB_OUTBOX_FIRE_CARDS=1 only for gap-fill / debug.
HUB_OUTBOX_FIRE_CARDS = _env_flag(
    "HUB_OUTBOX_FIRE_CARDS",
    "1" if not HUB_MAX else "0",
)
# FIRE↔RESULT law: default ON — every FIRE gets a RESULT card template skin.
# Even under HUB_MAX (engine owns FIRE skins), outbox still guarantees RESULT.
try:
    from bot.config.fire_result_law import outbox_must_emit_result_cards as _must_res

    _RESULT_DEFAULT = "1" if _must_res() else ("1" if not HUB_MAX else "0")
except Exception:
    _RESULT_DEFAULT = "1"
HUB_OUTBOX_RESULT_CARDS = _env_flag(
    "HUB_OUTBOX_RESULT_CARDS",
    _RESULT_DEFAULT,
)


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
    rooms = row["rooms_agreed"] if "rooms_agreed" in row.keys() else None
    origin_badge = "SIGNAL"
    origin_note = ""
    try:
        from fire_origin import classify_origin

        og = classify_origin(
            rooms_agreed=rooms,
            signal_kind=str(row["signal_kind"] or ""),
            source_floor=floor_name,
        )
        origin_badge = og.get("badge") or origin_badge
        if og.get("origin") == "SOLO_FACT":
            origin_note = "📌 SOLO FACT WARNING — not multi-room consensus\n"
        elif og.get("origin") == "COALITION":
            origin_note = "🏛 COALITION DECISION — multi-room confirmed\n"
    except Exception:
        pass
    return (
        "🚨 BAC BO SIGNAL 🚨\n\n"
        f"{origin_note}"
        f"🏷 ORIGIN: {origin_badge}\n"
        f"{color_emoji(color)} COLOR: {color.upper()}\n"
        f"🎯 MODE: {row['signal_kind'] or 'SIGNAL'}\n"
        f"🏛 FLOOR: {floor_name}\n"
        "⚡ G0 ONLY\n"
        f"📊 SCORE: {score:.2f}\n"
        f"🏠 ROOMS: {rooms or 'engine'}\n\n"
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
        result_label = f"G{gale} LOSS" if gale else "G0 LOSS"
    else:
        result_label = "TIE"
    # Loud truth board: bet blue + lost ⇒ this G0 was red (for certainty / learning).
    try:
        from fire_origin import truth_from_outcome

        truth_line = truth_from_outcome(predicted, outcome)["line"]
        if gale and outcome in ("win", "loss"):
            truth_line = truth_line.replace("LOST", f"LOST G{gale}").replace(
                "WIN ·", f"WIN G{gale} ·"
            )
    except Exception:
        truth_line = (
            f"BET {predicted.upper()} → OUT {actual.upper()} · {result_label}"
        )
    banner = actual_icon * 10
    return (
        f"{banner}\n"
        f"⏰  {brt} BRT  ·  {edt} EDT\n"
        f"{banner}\n"
        f"🔔 {result_icon} {result_label}  ·  #{row['id']}\n"
        f"🎲 Apostou: {pred_icon} {predicted.upper()}  →  Saiu: {actual_icon} {actual.upper()}\n"
        f"🧭 {truth_line}\n"
        f"🔍 SINAL #{row['id']} — RESUMIDO FORENSE\n"
        f"  Tipo: {row['signal_kind']} · Cor prevista: {predicted.upper()}\n"
        f"  Cor que SAIU: {actual.upper()}\n"
        f"  Disparado: {row['fired_at']} UTC\n"
        f"  Resolvido: {row['resolved_at'] or ''} UTC\n"
        f"  ⏱ Intervalo (Clock C — fire→resolve): {secs_txt}\n"
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


def _clean_peer(raw: str | None) -> str:
    s = (raw or "").strip().strip('"').strip("'").lstrip("@")
    return s


def _gunique_cache_path() -> Path:
    return HERE / "data" / "telegram_gunique_entity.json"


def _write_peer_cache(path: Path, target: str, ent) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "target": str(target),
                    "id": int(ent.id),
                    "username": getattr(ent, "username", None),
                    "title": getattr(ent, "title", None)
                    or getattr(ent, "first_name", None),
                }
            )
        )
    except Exception:
        pass


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
        raise RuntimeError("TARGET missing — set TELEGRAM_TARGET_PEER=UNIQUE_g1")
    ent = await client.get_entity(target)
    _write_peer_cache(cache, str(target), ent)
    return ent


async def _resolve_gunique(client, peer: str | None):
    """Resolve @UNIQUE_g1 (Gunique) with cache → numeric id → dialogs → username variants.

    Username ResolveUsername often fails / FloodWaits on cold sessions. Prefer cached
    numeric id or an existing dialog so trust-first routing does not fall back to money.
    """
    cache = _gunique_cache_path()
    cache.parent.mkdir(parents=True, exist_ok=True)
    peer = _clean_peer(peer) or "UNIQUE_g1"
    errors: list[str] = []

    # 1) Explicit numeric id wins (TELEGRAM_GUNIQUE_PEER_ID / COUNTDOWN_PEER_ID)
    for env_key in (
        "TELEGRAM_GUNIQUE_PEER_ID",
        "GUNIQUE_PEER_ID",
        "TELEGRAM_COUNTDOWN_PEER_ID",
        "COUNTDOWN_PEER_ID",
    ):
        raw = _clean_peer(os.environ.get(env_key))
        if raw and raw.lstrip("-").isdigit():
            try:
                ent = await client.get_entity(int(raw))
                _write_peer_cache(cache, peer, ent)
                print(f"[Outbox] Gunique resolve OK via {env_key}={raw} id={ent.id}")
                return ent
            except Exception as exc:
                errors.append(f"{env_key}:{exc!r}")

    # 2) Peer itself is numeric
    if peer.lstrip("-").isdigit():
        try:
            ent = await client.get_entity(int(peer))
            _write_peer_cache(cache, peer, ent)
            print(f"[Outbox] Gunique resolve OK via numeric peer id={ent.id}")
            return ent
        except Exception as exc:
            errors.append(f"numeric:{exc!r}")

    # 3) Cached entity id (avoid ResolveUsername hammer)
    if cache.exists():
        try:
            data = json.loads(cache.read_text())
            cid = data.get("id")
            if cid is not None:
                ent = await client.get_entity(int(cid))
                print(f"[Outbox] Gunique resolve OK via cache id={ent.id}")
                return ent
        except Exception as exc:
            errors.append(f"cache:{exc!r}")

    # 4) Dialog scan — session already knows the chat
    want = peer.casefold()
    aliases = {
        want,
        "unique_g1",
        "gunique",
        "g1 unique",
        "g1_unique",
        "unique g1",
    }
    try:
        async for dialog in client.iter_dialogs(limit=400):
            ent = dialog.entity
            uname = (getattr(ent, "username", None) or "").casefold()
            title = (
                getattr(ent, "title", None)
                or getattr(ent, "first_name", None)
                or getattr(dialog, "name", None)
                or ""
            ).casefold()
            if uname in aliases or title in aliases:
                _write_peer_cache(cache, peer, ent)
                print(
                    f"[Outbox] Gunique resolve OK via dialogs "
                    f"username={getattr(ent, 'username', None)} id={ent.id}"
                )
                return ent
            # Fuzzy only for near-full username overlap (avoid short false hits)
            if uname and len(uname) >= 6 and (want in uname or uname in want):
                _write_peer_cache(cache, peer, ent)
                print(
                    f"[Outbox] Gunique resolve OK via dialogs~ "
                    f"username={getattr(ent, 'username', None)} id={ent.id}"
                )
                return ent
    except Exception as exc:
        errors.append(f"dialogs:{exc!r}")
        print("[Outbox] Gunique dialogs scan FAIL:", repr(exc))

    # 5) Username ResolveUsername variants (last — can FloodWait)
    variants = []
    for v in (peer, peer.lower(), peer.upper(), f"@{peer}", "@UNIQUE_g1", "UNIQUE_g1"):
        if v and v not in variants:
            variants.append(v)
    try:
        from telethon.errors import FloodWaitError, UsernameNotOccupiedError
    except Exception:  # pragma: no cover
        FloodWaitError = Exception  # type: ignore
        UsernameNotOccupiedError = Exception  # type: ignore

    for cand in variants:
        try:
            ent = await client.get_entity(cand)
            _write_peer_cache(cache, peer, ent)
            print(
                f"[Outbox] Gunique resolve OK via username {cand!r} id={ent.id}"
            )
            return ent
        except FloodWaitError as exc:
            errors.append(f"flood:{cand}:{getattr(exc, 'seconds', '?')}")
            print(
                "[Outbox] Gunique ResolveUsername FloodWait — set "
                "TELEGRAM_GUNIQUE_PEER_ID=<numeric> seconds=",
                getattr(exc, "seconds", "?"),
            )
            break
        except UsernameNotOccupiedError as exc:
            errors.append(f"uname:{cand}:{exc!r}")
        except Exception as exc:
            errors.append(f"get:{cand}:{exc!r}")

    print(
        "[Outbox] Gunique peer resolve FAIL peer=",
        peer,
        "tried=",
        len(errors),
        "last=",
        errors[-3:] if errors else [],
        "— high-trust fires will MONEY_FALLBACK until fixed",
    )
    return None


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
    peer = (
        os.environ.get("TELEGRAM_PRIMARY_PEER")
        or os.environ.get("TELEGRAM_TARGET_PEER")
        or "UNIQUE_g1"
    )

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

    # Profit Chat Bundle: APEX=UNIQUE_g1 owns money + countdown.
    # Mr_iv4 removed. RESULT always same chat as parent fire.
    # Precision/volume/assertive/impact spill to UNIQUE_g2…g5 (never delay).
    cd_peer = _clean_peer(
        os.environ.get("TELEGRAM_COUNTDOWN_PEER")
        or os.environ.get("TELEGRAM_PRIMARY_PEER")
        or os.environ.get("GUNIQUE_PEER")
        or os.environ.get("TELEGRAM_GUNIQUE_PEER")
        or "UNIQUE_g1"
    )
    cd_entity = await _resolve_gunique(client, cd_peer) if cd_peer else None
    if cd_entity is not None:
        print(
            f"[Outbox] APEX/COUNTDOWN peer ready: @{cd_peer} "
            f"id={getattr(cd_entity, 'id', '?')} (g1 #1; Mr_iv4 excluded)"
        )
    else:
        print(
            f"[Outbox] APEX NOT READY peer=@{cd_peer} — will soft-retry; "
            "set TELEGRAM_GUNIQUE_PEER_ID=5855678138 if FloodWait / UsernameNotOccupied"
        )
    try:
        mid = int(getattr(entity, "id", 0) or 0)
        cid = int(getattr(cd_entity, "id", 0) or 0) if cd_entity is not None else 0
        if mid and cid and mid == cid:
            # Expected under Profit Chat Bundle — UNIQUE_g1 is both money + countdown.
            print(
                f"[Outbox] APEX unified: money+countdown share peer id={mid} "
                "(UNIQUE_g1 #1 — intentional; Mr_iv4 removed)"
            )
        elif cd_entity is None:
            # Prefer primary entity as APEX when countdown resolve fails
            cd_entity = entity
            print("[Outbox] APEX fallback: using primary entity for countdown lane")
    except Exception:
        pass
    print(
        f"[Outbox] hub_card_policy fire_cards={int(HUB_OUTBOX_FIRE_CARDS)} "
        f"result_cards={int(HUB_OUTBOX_RESULT_CARDS)} "
        f"(HUB_MAX engine owns original skins when fire_cards=0)"
    )
    try:
        from bot.config.fire_result_law import law_banner, law_enabled

        if law_enabled():
            print(law_banner())
    except Exception:
        print(
            "[FIRE↔RESULT LAW] ON (fallback) — every FIRE gets RESULT card skin"
        )

    # Cache resolved overflow peers for this outbox session (never delay on miss).
    _peer_entity_cache: dict[str, object] = {}

    async def _resolve_peer_entity(peer: str | None):
        """Resolve UNIQUE_gN / APEX. Mr_iv4 redirects to APEX. Fail-open → primary."""
        if not peer:
            return None
        key = str(peer).lstrip("@").strip()
        if not key:
            return None
        # Excluded former money king → APEX (UNIQUE_g1)
        if key in {"6774605259", "Mr_iv4", "mr_iv4"}:
            return cd_entity or entity
        if key == str(getattr(entity, "id", "")) or key in {
            "UNIQUE_g1",
            "unique_g1",
            "5855678138",
            str(cd_peer),
            str(getattr(cd_entity, "id", "") or ""),
        }:
            return cd_entity or entity
        if key in _peer_entity_cache:
            return _peer_entity_cache[key]
        if key.lstrip("-").isdigit():
            try:
                ent = await client.get_entity(int(key))
                _peer_entity_cache[key] = ent
                return ent
            except Exception as exc:
                print(f"[Outbox] peer resolve id={key} fail:", repr(exc))
                return None
        try:
            ent = await client.get_entity(key if key.startswith("@") else f"@{key}")
            _peer_entity_cache[key] = ent
            return ent
        except Exception:
            try:
                ent = await client.get_entity(key)
                _peer_entity_cache[key] = ent
                return ent
            except Exception as exc:
                print(f"[Outbox] peer resolve @{key} fail (spill skip→primary):", repr(exc))
                return None

    def _lane_dests(
        signal_kind: str | None,
        text: str | None = None,
        *,
        signal_id: int | None = None,
        is_result: bool = False,
        peer_slot: str | None = None,
    ):
        """Return (primary_dest, lane_name, mirror_dests). Hub trust can force GUNIQUE/MONEY.

        Profit skyscraper: soft-cap spill via chat_router (never delay). Overflow
        peer strings are resolved asynchronously by the send loop when needed;
        this sync helper returns primary MONEY/COUNTDOWN entities plus an optional
        spill_peer name in lane_name metadata via SKYSCRAPER:* lane tags.
        """
        # Hub trust / persisted parent slot wins when set
        slot = (peer_slot or "").upper().strip()
        if not slot and is_result and signal_id is not None:
            try:
                from hub_dispatch import parent_peer_slot

                slot = parent_peer_slot(signal_id) or ""
            except Exception:
                slot = ""
        if slot == "GUNIQUE":
            if cd_entity is not None:
                return cd_entity, "GUNIQUE", []
            print(
                f"[Outbox] GUNIQUE ROUTE FAIL id={signal_id} peer=@{cd_peer} "
                "→ MONEY_FALLBACK_FROM_GUNIQUE (entity unresolved)"
            )
            return entity, "MONEY_FALLBACK_FROM_GUNIQUE", []
        if slot == "MONEY":
            return entity, "MONEY", []

        # Profit skyscraper router (shelf + soft-cap spill, never delay)
        try:
            from chat_router import route_card

            meta = {"is_result": is_result} if is_result else {}
            target = route_card(
                text,
                signal_id=str(signal_id) if signal_id is not None else None,
                signal_kind=signal_kind,
                meta=meta,
            )
            if getattr(target, "suppressed", False):
                return entity, f"SUPPRESSED:{getattr(target, 'reason', '')}", []
            peer = getattr(target, "peer", None)
            shelf = getattr(target, "shelf_id", "") or ""
            reason = getattr(target, "reason", "") or ""
            # Map shelf → primary entity; overflow peers tagged for async resolve
            if peer and str(peer).upper().startswith("UNIQUE_G") and str(peer).upper() != "UNIQUE_G1":
                # Spill candidate — prefer COUNTDOWN entity as fail-open if gN missing
                base = cd_entity if cd_entity is not None else entity
                return base, f"SKYSCRAPER_SPILL:{peer}:{shelf}:{reason}", []
            if shelf in {"SHELF_COUNTDOWN", "SHELF_SNIPER"} or (
                peer and str(peer).upper() in {"UNIQUE_G1", "5855678138"}
            ):
                if cd_entity is not None:
                    return cd_entity, f"SKYSCRAPER_CD:{shelf}:{reason}", []
                return entity, "MONEY_FALLBACK_FROM_CD", []
            if peer:
                return entity, f"SKYSCRAPER_MONEY:{shelf}:{reason}", []
        except Exception as exc:
            print("[Outbox] skyscraper route error:", repr(exc))

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
            # Shelf override: countdown/sniper families force COUNTDOWN peer
            try:
                from chat_shelves import SHELF_COUNTDOWN, SHELF_SNIPER, resolve_shelf

                shelf = resolve_shelf(
                    text,
                    signal_kind=signal_kind,
                    meta=meta,
                    parent_lane=parent,
                )
                if (
                    not is_result
                    and shelf.shelf_id in {SHELF_COUNTDOWN, SHELF_SNIPER}
                ):
                    lane = "COUNTDOWN"
                    print(
                        f"[Outbox] shelf {shelf.shelf_id} family={shelf.family_id} → COUNTDOWN"
                    )
            except Exception:
                pass
            if not is_result and signal_id is not None:
                persist_fire_lane(signal_id, lane)
        except Exception as exc:
            print("[Outbox] lane route error:", repr(exc))
            lane = "MONEY"
        if lane == "COUNTDOWN":
            if cd_entity is not None:
                return cd_entity, "COUNTDOWN", []
            print(
                f"[Outbox] CD lane FAIL id={signal_id} peer=@{cd_peer} "
                "→ MONEY_FALLBACK_FROM_CD (Gunique not ready)"
            )
            return entity, "MONEY_FALLBACK_FROM_CD", []
        mirrors = []
        if MIRROR_MONEY_TO_GUNIQUE and cd_entity is not None:
            try:
                if int(getattr(cd_entity, "id", 0) or 0) != int(getattr(entity, "id", 0) or 0):
                    mirrors.append(cd_entity)
            except Exception:
                mirrors.append(cd_entity)
        return entity, "MONEY", mirrors

    async def _apply_spill(dest, lane: str):
        """If lane tags SKYSCRAPER_SPILL:UNIQUE_gN, resolve that chat NOW (never wait)."""
        if not isinstance(lane, str) or not lane.startswith("SKYSCRAPER_SPILL:"):
            return dest, lane
        parts = lane.split(":")
        peer = parts[1] if len(parts) > 1 else ""
        ent = await _resolve_peer_entity(peer)
        if ent is not None:
            print(f"[Outbox] spill → @{peer} (never delay)")
            return ent, lane
        # Chat not created yet — send to primary immediately (no queue).
        print(f"[Outbox] spill @{peer} unresolved → primary NOW (never delay)")
        return dest, lane + ":FALLBACK_PRIMARY"

    def _estudo_spam(body: str | None) -> bool:
        if not body:
            return False
        bu = body.upper()
        if (
            "G2 ESTUDO" in bu
            or "G1 ESTUDO" in bu
            or "G3 ESTUDO" in bu
            or "ESTUDO |" in bu
            or "ESTUDO :" in bu
        ):
            return True
        first = body.splitlines()[0].upper() if body else ""
        return "ESTUDO" in first

    async def _send_all(dests, body: str):
        # Never flood UNIQUE with engine study spam / identical repeats.
        if _estudo_spam(body):
            print("[Outbox] drop ESTUDO study spam")
            return None
        last = None
        for dest in dests:
            last = await client.send_message(dest, body)
        return last

    async def _release_round_sync_holds() -> int:
        """Flush prep-invested fires/results at perfect TTB / interval start."""
        try:
            from round_sync_densifier import enabled as _rs_on, pop_ready, status as _rs_status
        except Exception:
            return 0
        if not _rs_on():
            return 0
        ready = pop_ready()
        n = 0
        for held in ready:
            body = held.text or ""
            if not body.strip():
                continue
            if _estudo_spam(body):
                print("[Outbox] drop ESTUDO from round-sync hold")
                continue
            chat = (held.chat or "UNIQUE_g1").strip()
            if chat in {"6774605259", "Mr_iv4", "mr_iv4"}:
                chat = "UNIQUE_g1"
            dest = (await _resolve_peer_entity(chat)) or cd_entity or entity
            try:
                await client.send_message(dest, body)
                n += 1
                print(
                    f"[ROUND-SYNC] RELEASE chat={chat} round={held.round_id} "
                    f"score={held.score} family={held.family_id} src={held.source}"
                )
            except Exception as exc:
                print("[ROUND-SYNC] RELEASE FAIL:", repr(exc))
        if tick % HEARTBEAT_EVERY == 0:
            try:
                st = _rs_status()
                print(
                    f"[ROUND-SYNC] phase={st['phase']['phase']} "
                    f"ttb={st['phase']['ttb_remaining']} "
                    f"hold={st['hold_queue']} gaps={len(st.get('density_gaps') or [])}"
                )
            except Exception:
                pass
        return n

    print(
        f"[Outbox] ONLINE money={getattr(entity, 'username', None) or peer} "
        f"id={getattr(entity, 'id', '?')} "
        f"gunique=@{cd_peer or 'UNSET'} "
        f"gid={getattr(cd_entity, 'id', None) if cd_entity else 'UNRESOLVED'} "
        f"mirror_money={MIRROR_MONEY_TO_GUNIQUE} "
        f"hub_max={HUB_MAX} separation=1 send_blocked={SEND_BLOCKED} "
        f"tag={boot_tag} pid={os.getpid()} db={DB}"
    )

    if STARTUP_PING:
        # Throttle: do not spam OUTBOX ONLINE on every restart (default 6h)
        ping_min = int(os.environ.get("TELEGRAM_OUTBOX_PING_MIN_SECS", "21600"))
        ping_stamp = HERE / "data" / "outbox_startup_ping_at.txt"
        do_ping = True
        try:
            if ping_min > 0 and ping_stamp.exists():
                last = float(ping_stamp.read_text().strip() or "0")
                age = time.time() - last
                if age < ping_min:
                    do_ping = False
                    print(
                        f"[Outbox] startup ping skipped "
                        f"(last {age/60:.0f}m ago · min={ping_min/3600:.1f}h)"
                    )
        except Exception:
            do_ping = True
        if do_ping:
            ping_apex = (
                "PROFIT BUNDLE ONLINE — UNIQUE_g1 APEX (#1)\n"
                f"DEST peer id: {getattr(cd_entity or entity, 'id', '?')}\n"
                f"Tag floor: {boot_tag}\n"
                f"DB: {DB.name}\n"
                "Mr_iv4 REMOVED. All primary ENTER + clocks + gale home here.\n"
                f"Outbox fire cards: {'ON' if HUB_OUTBOX_FIRE_CARDS else 'OFF (engine owns skins)'}\n"
                f"HUB_MAX={int(HUB_MAX)} · bundle spill g2…gN · never delay."
            )
            try:
                dest_ping = cd_entity or entity
                msg = await client.send_message(dest_ping, ping_apex)
                print("[Outbox] startup ping UNIQUE_g1 APEX OK id=", msg.id)
            except Exception as exc:
                print("[Outbox] startup ping UNIQUE_g1 APEX FAIL:", repr(exc))
            try:
                ping_stamp.parent.mkdir(parents=True, exist_ok=True)
                ping_stamp.write_text(str(time.time()))
            except Exception:
                pass

    try:
        conn0 = _db_ro()
        mx = conn0.execute("SELECT MAX(id), MAX(fired_at) FROM consensus_signals").fetchone()
        conn0.close()
        print(
            f"[Outbox] db_max_id={mx[0]} db_max_fired={mx[1]} "
            f"sig_state={read_int(SIG_STATE)} res_state={read_int(RES_STATE)}"
        )
        # When outbox does not send fire/result cards, snap cursors to DB tip so we
        # do not walk a thousand-row historical backlog printing skip lines.
        tip = int(mx[0] or 0)
        if tip > 0 and HUB_MAX and not HUB_OUTBOX_FIRE_CARDS:
            cur = read_int(SIG_STATE)
            if cur < tip:
                write_int(SIG_STATE, tip)
                print(f"[Outbox] HUB snap fire cursor {cur}→{tip} (engine owns skins)")
        if tip > 0 and HUB_MAX and not HUB_OUTBOX_RESULT_CARDS:
            cur = read_int(RES_STATE)
            if cur < tip:
                write_int(RES_STATE, tip)
                print(f"[Outbox] HUB snap result cursor {cur}→{tip} (engine owns skins)")
    except Exception as exc:
        print("[Outbox] db probe FAIL:", repr(exc))

    tick = 0
    gunique_retry_every = max(1, int(os.environ.get("GUNIQUE_RESOLVE_RETRY_TICKS", "6")))
    while True:
        try:
            # Soft-retry Gunique resolve so trust-first does not stay stuck on money fallback
            if cd_entity is None and cd_peer and (tick % gunique_retry_every == 0):
                print(f"[Outbox] Gunique soft-retry resolve @{cd_peer} tick={tick}")
                cd_entity = await _resolve_gunique(client, cd_peer)
                if cd_entity is not None:
                    print(
                        f"[Outbox] Gunique soft-retry OK id={getattr(cd_entity, 'id', '?')}"
                    )

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
                    gstat = (
                        f"ready id={getattr(cd_entity, 'id', '?')}"
                        if cd_entity is not None
                        else "UNRESOLVED→fallback"
                    )
                    print(
                        f"[Outbox] HEARTBEAT last_sig={last_sig} abs_max_id={abs_mx[0]} "
                        f"abs_max_fired={abs_mx[1]} pending={mx[1]} recent_30m={recent} "
                        f"pending_send={len(rows)} pending_res={len(results)} "
                        f"gunique={gstat}"
                    )
                    if recent == 0 and (mx[1] or 0) == 0:
                        print(
                            "[Outbox] NOTE engine quiet — no new consensus rows; "
                            "outbox is caught up (not a Telegram send failure)"
                        )
                except Exception as exc:
                    print("[Outbox] HEARTBEAT probe fail:", repr(exc))

            conn.close()

            # Hub catch-up throttle — avoid dumping 30 generic cards at once
            if HUB_MAX:
                try:
                    from hub_dispatch import throttle_rows

                    before = len(rows)
                    rows = throttle_rows(rows)
                    if before != len(rows):
                        print(f"[Outbox] HUB throttle signals {before}→{len(rows)}")
                    results = throttle_rows(results)
                except Exception as exc:
                    print("[Outbox] hub throttle skip:", repr(exc))

            lane_by_id: dict[int, tuple] = {}
            result_ids = {int(r["id"]) for r in results}
            for row in rows:
                try:
                    floor = _row_floor(row)
                    _stamp_floor(int(row["id"]), floor)
                    score = _row_score(row)
                    if HUB_MAX and not HUB_OUTBOX_FIRE_CARDS:
                        # Engine already posted the original skin; do not double-card.
                        write_int(SIG_STATE, row["id"])
                        print(
                            "[Outbox] HUB skip fire card (engine owns skin)",
                            row["id"],
                            row["signal_kind"],
                            floor,
                            "score",
                            score,
                        )
                        continue
                    peer_slot = None
                    if HUB_MAX:
                        try:
                            from hub_dispatch import dispatch_fire

                            hub = dispatch_fire(row, floor=floor, score=score)
                            body = hub["card_text"]
                            peer_slot = hub.get("peer_slot")
                            print(
                                "[Outbox] HUB trust",
                                row["id"],
                                hub.get("trust"),
                                hub.get("reason"),
                            )
                        except Exception as exc:
                            print("[Outbox] hub_dispatch fail:", repr(exc))
                            body = fmt_consensus(row, floor=floor)
                    else:
                        body = fmt_consensus(row, floor=floor)
                    dest, lane, mirrors = _lane_dests(
                        row["signal_kind"],
                        text=body,
                        signal_id=int(row["id"]),
                        is_result=False,
                        peer_slot=peer_slot,
                    )
                    dest, lane = await _apply_spill(dest, lane)
                    if HUB_MAX:
                        try:
                            from hub_dispatch import stamp_route_label

                            body = stamp_route_label(body, lane)
                        except Exception:
                            pass
                    dests = [dest] + list(mirrors)
                    lane_by_id[int(row["id"])] = (dest, lane, mirrors)
                    try:
                        from skin_gate import evaluate_send_gate, log_block

                        gate = evaluate_send_gate(
                            body, signal_kind=row["signal_kind"]
                        )
                        if gate.blocked:
                            log_block(gate, where=f"outbox_fire id={row['id']}")
                            write_int(SIG_STATE, row["id"])
                            print(
                                "[Outbox] SKIN-GATE skip fire",
                                row["id"],
                                gate.family_id,
                                gate.matched_keys,
                            )
                            continue
                    except Exception as exc:
                        print("[Outbox] skin_gate skip:", repr(exc))
                    # Round sync: invest prep → release at TTB; never burn late window
                    try:
                        from round_sync_densifier import decide_fire

                        sync = decide_fire(
                            body,
                            score=float(score or 0),
                            signal_kind=str(row.get("signal_kind") or ""),
                            source="outbox",
                            fire_key=f"outbox:{row['id']}",
                        )
                        action = sync.action
                        try:
                            from bot.config.fire_result_law import decide_fire_override

                            ov = decide_fire_override(
                                action,
                                body,
                                signal_kind=str(row.get("signal_kind") or ""),
                                has_result_row=int(row["id"]) in result_ids,
                            )
                            if ov:
                                print(
                                    f"[FIRE↔RESULT LAW] outbox fire {row['id']} "
                                    f"{action}→{ov} (result-paired must fire)"
                                )
                                action = ov
                        except Exception:
                            pass
                        if action in {"HOLD_PREP", "TOO_LATE", "DEDUP"}:
                            write_int(SIG_STATE, row["id"])
                            print(
                                f"[ROUND-SYNC] outbox fire {row['id']} {action} {sync.reason}"
                            )
                            continue
                    except Exception as exc:
                        print("[ROUND-SYNC] outbox fire skip:", repr(exc))
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
                        score,
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
                    # FIRE↔RESULT law: never skip RESULT card template skins.
                    _law_force_result = False
                    try:
                        from bot.config.fire_result_law import (
                            law_enabled,
                            outbox_must_emit_result_cards,
                        )

                        _law_force_result = (
                            law_enabled() or outbox_must_emit_result_cards()
                        )
                    except Exception:
                        _law_force_result = True
                    if (
                        HUB_MAX
                        and not HUB_OUTBOX_RESULT_CARDS
                        and not _law_force_result
                    ):
                        write_int(RES_STATE, row["id"])
                        print(
                            "[Outbox] HUB skip result card (engine owns skin)",
                            row["id"],
                            row["outcome"],
                        )
                        continue
                    if _law_force_result and not HUB_OUTBOX_RESULT_CARDS:
                        print(
                            "[FIRE↔RESULT LAW] forcing RESULT card skin",
                            row["id"],
                            row["outcome"],
                        )
                    res_body = fmt_result(row)
                    cached = lane_by_id.get(int(row["id"]))
                    if cached:
                        dest, lane, mirrors = cached
                    else:
                        slot = None
                        if HUB_MAX:
                            try:
                                from hub_dispatch import parent_peer_slot

                                slot = parent_peer_slot(int(row["id"]))
                            except Exception:
                                slot = None
                        dest, lane, mirrors = _lane_dests(
                            row["signal_kind"],
                            text=res_body,
                            signal_id=int(row["id"]),
                            is_result=True,
                            peer_slot=slot,
                        )
                        dest, lane = await _apply_spill(dest, lane)
                    dests = [dest] + list(mirrors)
                    try:
                        from skin_gate import evaluate_send_gate, log_block

                        gate = evaluate_send_gate(
                            res_body, signal_kind=row["signal_kind"]
                        )
                        if gate.blocked:
                            log_block(gate, where=f"outbox_result id={row['id']}")
                            write_int(RES_STATE, row["id"])
                            print(
                                "[Outbox] SKIN-GATE skip result",
                                row["id"],
                                gate.family_id,
                                gate.matched_keys,
                            )
                            continue
                    except Exception as exc:
                        print("[Outbox] skin_gate result skip:", repr(exc))
                    try:
                        from round_sync_densifier import (
                            HeldFire,
                            decide_result,
                            get_clock,
                            get_densifier,
                        )

                        # RESULT attaches under its own FIRE immediately.
                        rsync = decide_result(res_body, force_now=True)
                        if rsync.action == "HOLD_RESULT":
                            phase = get_clock().phase_at()
                            try:
                                get_clock().nudge_from_resolve(time.time())
                            except Exception:
                                pass
                            parent_chat = "UNIQUE_g1"
                            try:
                                from hub_dispatch import parent_peer_slot

                                slot = parent_peer_slot(int(row["id"]))
                                if slot:
                                    parent_chat = str(slot)
                            except Exception:
                                pass
                            get_densifier()._enqueue(
                                HeldFire(
                                    fire_key=f"outbox_res:{row['id']}",
                                    text=res_body,
                                    color=str(row.get("color") or ""),
                                    family_id="RESULT",
                                    signal_kind=str(row.get("signal_kind") or "RESULT"),
                                    score=0.0,
                                    chat=parent_chat,
                                    clock_a_secs=None,
                                    detected_at=time.time(),
                                    ideal_release_at=phase.next_interval_start,
                                    round_id=phase.round_id + 1,
                                    source="outbox_result",
                                    meta={"kind": "result_align", "id": row["id"]},
                                )
                            )
                            write_int(RES_STATE, row["id"])
                            print(
                                f"[ROUND-SYNC] outbox result {row['id']} HOLD_RESULT {rsync.reason}"
                            )
                            continue
                    except Exception as exc:
                        print("[ROUND-SYNC] outbox result skip:", repr(exc))
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
                    try:
                        from hub_impact_learner import observe_result

                        rooms_agreed = row.get("rooms_agreed") or []
                        if isinstance(rooms_agreed, str):
                            try:
                                import json as _json

                                rooms_agreed = _json.loads(rooms_agreed)
                            except Exception:
                                rooms_agreed = [rooms_agreed]
                        observe_result(
                            signal_id=row["id"],
                            outcome=str(row["outcome"] or ""),
                            predicted=str(row["color"] or ""),
                            floors=[str(row.get("source_floor") or "")],
                            rooms=list(rooms_agreed or []),
                            kind=str(row.get("signal_kind") or ""),
                            primary_floor=str(row.get("source_floor") or ""),
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
        try:
            await _release_round_sync_holds()
        except Exception as exc:
            print("[ROUND-SYNC] release tick skip:", repr(exc))
        tick += 1
        # Tighter loop when holds are waiting for exact TTB
        sleep_s = 5
        try:
            from round_sync_densifier import enabled as _rs_on, status as _rs_status

            if _rs_on() and int((_rs_status() or {}).get("hold_queue") or 0) > 0:
                sleep_s = 1
        except Exception:
            sleep_s = 5
        await asyncio.sleep(sleep_s)

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
