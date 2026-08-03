#!/usr/bin/env bash
# Full Telegram card archaeology — EVERY message since Mar 17, EVERY distinct type.
# Same method as manual scroll: chronological first-seen of each skin. Automated.
# Does NOT drop unknowns — fingerprints them so nothing is missed.
#
#   curl -fsSL -H 'Cache-Control: no-cache' -o TG_ARCH.sh \
#     'https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/cursor/add-engine-gate-registry-d5ba/replit_elite_stack_patch/REPLIT_TELEGRAM_TYPE_ARCHAEOLOGY.sh'
#   bash TG_ARCH.sh
#
# Outputs (nothing omitted):
#   tg_archaeology/all_messages.csv
#   tg_archaeology/types_first_seen.csv
#   tg_archaeology/unknown_messages.csv   ← review these; each is a new fingerprint
#   tg_archaeology/types_summary.json
#   tg_archaeology/eras_auto.md           ← chronological catalog ready to merge
#   tg_archaeology/report.txt
#   tg_archaeology_*.zip
set -euo pipefail
cd /home/runner/workspace 2>/dev/null || cd "$(dirname "$0")/.."

OUT="tg_archaeology"
mkdir -p "$OUT"
export OUT
export SINCE_ISO="${SINCE_ISO:-2026-03-17T00:00:00+00:00}"

# shellcheck disable=SC1091
[[ -f .env ]] && set -a && source ./.env && set +a || true
# File wins over a short/broken Replit secret (same as REPLIT_FINISH / ONE_STACK)
if [[ -f .telegram_session_string ]]; then
  _S="$(tr -d '\n\r' < .telegram_session_string)"
  if [[ ${#_S} -gt 50 ]]; then
    export TELEGRAM_SESSION_STRING="$_S"
    echo "prefill: .telegram_session_string len=${#_S}"
  fi
fi

# Usage: bash TG_ARCH.sh [--selftest]
if [[ "${1:-}" == "--selftest" ]]; then
  export TG_ARCH_SELFTEST=1
fi

python3 - <<'PY'
import csv, json, os, re, sys, zipfile
from collections import OrderedDict, Counter
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(os.environ.get("OUT", "tg_archaeology"))
SINCE = datetime.fromisoformat(os.environ["SINCE_ISO"])
if SINCE.tzinfo is None:
    SINCE = SINCE.replace(tzinfo=timezone.utc)


def first_line(text: str) -> str:
    for line in (text or "").splitlines():
        s = line.strip()
        if s:
            return s[:160]
    return ""


def normalize_header(h: str) -> str:
    return re.sub(r"\s+", " ", (h or "").strip())[:120]


def fingerprint(s: str, n: int = 50) -> str:
    s = re.sub(r"[^A-Z0-9]+", "_", (s or "").upper()).strip("_")
    return (s[:n] or "EMPTY")


def detect_lane_and_clocks(text: str, role: str) -> tuple[str, str]:
    """Lane hint + clock tags. Clock A≠C. Any Ns counts when present."""
    t = text or ""
    clocks = []
    # Clock A — entry window on FIRE
    m_janela = re.search(r"JANELA\s*:\s*(\d+)\s*s", t, re.I)
    m_green = re.search(r"🟢\s*(\d+)\s*s\s*🟢", t)
    m_apostar = re.search(r"(\d+)\s*s\s+para\s+apostar", t, re.I)
    m_left = re.search(r"(\d+)\s*s\s+(left|restantes|remaining)", t, re.I)
    secs_a = None
    for m in (m_janela, m_green, m_apostar, m_left):
        if m:
            secs_a = m.group(1)
            break
    if secs_a is not None:
        clocks.append(f"A:{secs_a}s")
    # Clock C — forensic interval on RESULT
    m_int = re.search(r"Intervalo\s*:\s*([\d.]+)\s*s", t, re.I)
    if m_int:
        clocks.append(f"C:{m_int.group(1)}s")
    # Lane
    if role == "FIRE":
        if secs_a is not None or re.search(
            r"Sinal Retido|QUANTUM|RUSH|CD_FIRE|COUNTDOWN|BRT.*EDT|para apostar", t, re.I
        ):
            lane = "COUNTDOWN"
        else:
            lane = "MONEY"
    elif role == "RESULT":
        # result inherits parent; tag by presence of CD skins / intervalo only as hint
        if re.search(r"GANHOU|RODADAS|TEMPO|BELL|🟢\s*G\d|BRT", t, re.I) and re.search(
            r"Intervalo|placar|rodada", t, re.I
        ):
            lane = "COUNTDOWN_HINT"
        else:
            lane = "MONEY_HINT"
    else:
        lane = ""
    return lane, ",".join(clocks)


def classify(text: str) -> tuple[str, str, str, str, str]:
    """Return (role, type_id, note, lane, clocks). Never drops — UNKNOWN gets fingerprint."""
    t = text or ""
    fl = normalize_header(first_line(t))
    low = t.lower()

    # ── ONLINE ──────────────────────────────────────────────────────────────
    if "userbot online" in low or re.search(r"BacBo Royal UserBot ONLINE", t, re.I):
        rooms = re.search(r"(\d+)\s*salas monitoradas", t, re.I)
        solo = re.search(r"SOLO ELITE[^0-9]*≥\s*([0-9.]+)", t, re.I)
        gold = re.search(r"GOLDEN[^0-9]*≥\s*([0-9.]+)", t, re.I)
        note = (
            f"rooms={rooms.group(1) if rooms else '?'};"
            f"solo>={solo.group(1) if solo else '?'};"
            f"golden>={gold.group(1) if gold else '?'}"
        )
        role, tid = "ONLINE", "ONLINE_BANNER"
        lane, clocks = detect_lane_and_clocks(t, role)
        return role, tid, note, lane, clocks

    # ── ROOM RELAY (before RESULT — AUTO WIN is relay, not bot RESULT) ──────
    if re.match(r"^📡\s*@", fl) or re.match(r"^✅\s*AUTO\s*WIN\s*@", fl, re.I) or re.match(
        r"^🤑\s*✅", fl
    ):
        body = t.split("\n", 1)[-1] if "\n" in t else t
        bl = first_line(body) if "📡" in fl or "AUTO" in fl.upper() else fl
        if re.search(r"ANALISANDO", t, re.I):
            sub = "ANALISANDO"
        elif re.search(r"Estamos no\s*\d|1[ºo°]\s*gale|2[ºo°]\s*gale", t, re.I):
            sub = "GALE_STATUS"
        elif re.search(r"MÃO PESADA|MAO PESADA", t, re.I):
            sub = "MAO_PESADA"
        elif re.search(r"HORÁRIOS EMPATES|HORARIOS EMPATES", t, re.I):
            sub = "HORARIOS_EMPATES"
        elif re.search(r"AUTO\s*WIN|GREEN", t, re.I):
            sub = "AUTO_WIN_GREEN"
        elif re.search(r"t\.me/|CONVIDAR|LINK|ENTRE NO GRUPO", t, re.I):
            sub = "PROMO_INVITE"
        elif re.search(r"ENTRADA CONFIRMADA|SINAL CONFIRMADO", t, re.I):
            sub = "ROOM_ENTRADA"
        elif re.search(r"\bTIE\b|EMPATE", t, re.I):
            sub = "ROOM_TIE"
        elif re.search(r"LOSS|RED|PERDEU", t, re.I):
            sub = "ROOM_LOSS"
        else:
            sub = "OTHER_" + fingerprint(bl, 40)
        role, tid = "ROOM_RELAY", f"RELAY_{sub}"
        lane, clocks = detect_lane_and_clocks(t, role)
        return role, tid, fl, lane, clocks

    # ── BOT RESULT skins ────────────────────────────────────────────────────
    if re.search(r"^✅\s*WIN\s*—", fl, re.I) or re.search(r"^❌\s*LOSS\s*—", fl, re.I):
        kind = re.sub(r"^✅\s*WIN\s*—\s*", "", fl, flags=re.I)
        kind = re.sub(r"^❌\s*LOSS\s*—\s*", "", kind, flags=re.I).strip()
        outcome = "WIN" if "WIN" in fl.upper() else "LOSS"
        role, tid = "RESULT", f"RESULT_{outcome}_{fingerprint(kind, 40)}"
        lane, clocks = detect_lane_and_clocks(t, role)
        return role, tid, fl, lane, clocks

    if re.search(r"^🔵|^🔴|^🟡|^⚪", fl) and re.search(r"GANHOU|PERDEU|EMPATE|TIE", t, re.I):
        outcome = "WIN" if re.search(r"GANHOU", t, re.I) else (
            "LOSS" if re.search(r"PERDEU", t, re.I) else "TIE"
        )
        role, tid = "RESULT", f"RESULT_BANNER_{outcome}_{fingerprint(fl, 30)}"
        lane, clocks = detect_lane_and_clocks(t, role)
        return role, tid, fl, lane, clocks

    if re.search(r"RESUMIDO FORENSE|⏱\s*Intervalo", t, re.I):
        role, tid = "RESULT", "RESULT_FORENSIC_INTERVALO"
        lane, clocks = detect_lane_and_clocks(t, role)
        return role, tid, fl, lane, clocks

    if re.search(r"G0\s*—\s*Acertou|G1\s*—\s*Recuperado|G2 MISS|G1 EXPIROU|PERDA TOTAL|G3", t, re.I):
        # standalone gale outcome line (sometimes separate msg)
        if not re.search(r"ENTER NOW|SIGNAL", t, re.I):
            role, tid = "RESULT", f"RESULT_GALE_{fingerprint(fl, 40)}"
            lane, clocks = detect_lane_and_clocks(t, role)
            return role, tid, fl, lane, clocks

    # CD result skins
    if re.search(r"🔔|BELL", t) and re.search(r"GANHOU|GREEN|WIN", t, re.I):
        role, tid = "RESULT", "CD_RES_BELL_GANHOU"
        lane, clocks = detect_lane_and_clocks(t, role)
        return role, tid, fl, "COUNTDOWN_HINT", clocks
    if re.search(r"rodadas|tempo total|⏱", t, re.I) and re.search(r"G\d|GREEN|WIN|GANHOU", t, re.I):
        if re.search(r"rodadas|tempo", t, re.I) and "ENTER" not in t.upper():
            role, tid = "RESULT", "CD_RES_RODADAS_TEMPO"
            lane, clocks = detect_lane_and_clocks(t, role)
            return role, tid, fl, "COUNTDOWN_HINT", clocks
    if re.search(r"🟢\s*G[0-3]|GREEN\s*G[0-3]", t, re.I) and "ENTER" not in t.upper():
        role, tid = "RESULT", "CD_RES_GREEN_G_BRT"
        lane, clocks = detect_lane_and_clocks(t, role)
        return role, tid, fl, "COUNTDOWN_HINT", clocks

    if re.search(r"/win\s*·\s*/loss|/tie_|After result:", t, re.I) and not re.search(
        r"ENTER NOW|SIGNAL", t, re.I
    ):
        # rare: footer-only followup — still record
        role, tid = "OPS", "OPS_MANUAL_RESULT_HINT"
        return role, tid, fl, "", ""

    # ── BOT FIRE skins (money + countdown) ──────────────────────────────────
    # Clock-A / countdown fires first (any Ns)
    if re.search(r"JANELA\s*:\s*\d+\s*s", t, re.I) or re.search(r"🟢\s*\d+\s*s\s*🟢", t):
        m = re.search(r"(\d+)\s*s", t, re.I)
        secs = m.group(1) if m else "X"
        # keep kind if present
        kind = "GENERIC"
        for k in ("SOLO ELITE", "GOLDEN", "SEQUENCE", "PLATINUM", "FLASH", "ULTRA TIE", "EMERGING", "EMERGINDO"):
            if re.search(k, t, re.I):
                kind = fingerprint(k, 20)
                break
        role, tid = "FIRE", f"FIRE_JANELA_{secs}S_{kind}"
        lane, clocks = detect_lane_and_clocks(t, role)
        return role, tid, fl, lane, clocks

    if re.search(r"Sinal Retido\s*→\s*Liberado|Sinal Retido", t, re.I):
        role, tid = "FIRE", "FIRE_SINAL_RETIDO_LIBERADO"
        lane, clocks = detect_lane_and_clocks(t, role)
        return role, tid, fl, lane or "COUNTDOWN", clocks

    if re.search(r"QUANTUM\s*LOCK|CD_FIRE_QUANTUM", t, re.I):
        role, tid = "FIRE", "CD_FIRE_QUANTUM_LOCK"
        lane, clocks = detect_lane_and_clocks(t, role)
        return role, tid, fl, "COUNTDOWN", clocks

    if re.search(r"RUSH|\d+\s*s\s+left", t, re.I) and re.search(r"ENTER|SIGNAL|APOSTAR", t, re.I):
        role, tid = "FIRE", "CD_FIRE_RUSH_NS_LEFT"
        lane, clocks = detect_lane_and_clocks(t, role)
        return role, tid, fl, "COUNTDOWN", clocks

    if re.search(r"BRT|EDT", t) and re.search(r"apostar|JANELA|timer", t, re.I):
        role, tid = "FIRE", "CD_FIRE_TIMER_BRT_EDT_APOSTAR"
        lane, clocks = detect_lane_and_clocks(t, role)
        return role, tid, fl, "COUNTDOWN", clocks

    # Named money FIRE headers
    if re.search(r"GOLDEN SIGNAL\s*—\s*ENTER NOW", t, re.I):
        role, tid = "FIRE", "FIRE_GOLDEN_SIGNAL_ENTER_NOW"
    elif re.search(r"SIGNAL CONFIRMED\s*—\s*ENTER NOW", t, re.I):
        role, tid = "FIRE", "FIRE_SIGNAL_CONFIRMED_ENTER_NOW"
    elif re.search(r"SOLO ELITE SIGNAL", t, re.I):
        role, tid = "FIRE", "FIRE_SOLO_ELITE_SIGNAL"
    elif re.search(r"PLATINUM", fl, re.I) and re.search(r"ENTER NOW|SIGNAL", t, re.I):
        role, tid = "FIRE", "FIRE_PLATINUM"
    elif re.search(r"SEQUENCE", fl, re.I) and re.search(r"ENTER NOW|SIGNAL", t, re.I):
        role, tid = "FIRE", "FIRE_SEQUENCE"
    elif re.search(r"FLASH", fl, re.I) and re.search(r"ENTER|SIGNAL", t, re.I):
        role, tid = "FIRE", "FIRE_FLASH"
    elif re.search(r"ULTRA\s*TIE|ULTRA_TIE", t, re.I) and re.search(r"ENTER|SIGNAL", t, re.I):
        role, tid = "FIRE", "FIRE_ULTRA_TIE"
    elif re.search(r"EMERGINDO|EMERGING", fl, re.I):
        role, tid = "FIRE", "FIRE_EMERGING"
    elif re.search(r"ENTER NOW\s*—\s*\d+\s*ROOM", t, re.I):
        role, tid = "FIRE", "FIRE_ENTER_NOW_N_ROOMS"
    elif re.search(r"ENTER NOW", t, re.I) and "📡 @" not in fl:
        role, tid = "FIRE", "FIRE_" + fingerprint(fl, 50)
    else:
        role, tid = None, None

    if role == "FIRE":
        lane, clocks = detect_lane_and_clocks(t, role)
        return role, tid, fl, lane, clocks

    # ── OPS ─────────────────────────────────────────────────────────────────
    if re.search(r"DeliveryAudit|QUARANTINE|FloodWait|DB_WRITE|ROOMS_SILENT|RESTART|boot", t, re.I):
        role, tid = "OPS", "OPS_" + fingerprint(fl, 40)
        return role, tid, fl, "", ""

    # ── Catch-all — NEVER drop ──────────────────────────────────────────────
    if fl:
        if fl.startswith("[MEDIA:"):
            return "MEDIA", "MEDIA_" + fingerprint(fl, 40), fl, "", ""
        return "UNKNOWN", "UNKNOWN_" + fingerprint(fl, 50), fl, "", ""
    return "EMPTY", "EMPTY", "", "", ""


# ── Self-test (no Telegram) ─────────────────────────────────────────────────
SELFTEST_CASES = [
    ("🟢 BacBo Royal UserBot ONLINE\n6 salas monitoradas\nSOLO ELITE ≥ 2.0", "ONLINE", "ONLINE_BANNER"),
    ("📡 @FooBar — tip\nANALISANDO mesa", "ROOM_RELAY", "RELAY_ANALISANDO"),
    ("✅ AUTO WIN @CoringaDados\n🤑✅ GREEN", "ROOM_RELAY", "RELAY_AUTO_WIN_GREEN"),
    ("🏆 SIGNAL CONFIRMED — ENTER NOW\nRooms in consensus", "FIRE", "FIRE_SIGNAL_CONFIRMED_ENTER_NOW"),
    ("💎 SOLO ELITE SIGNAL\nENTER NOW", "FIRE", "FIRE_SOLO_ELITE_SIGNAL"),
    ("🏆 GOLDEN SIGNAL — ENTER NOW", "FIRE", "FIRE_GOLDEN_SIGNAL_ENTER_NOW"),
    ("✅ WIN — SOLO_ELITE\nG0 — Acertou de primeira!", "RESULT", "RESULT_WIN_SOLO_ELITE"),
    ("JANELA: 11s para apostar\n💎 SOLO ELITE", "FIRE", "FIRE_JANELA_11S_SOLO_ELITE"),
    ("🟢 1s 🟢\nSEQUENCE SIGNAL", "FIRE", "FIRE_JANELA_1S_SEQUENCE"),
]


def run_selftest() -> int:
    bad = 0
    for text, exp_role, exp_tid in SELFTEST_CASES:
        role, tid, *_ = classify(text)
        ok = role == exp_role and tid == exp_tid
        print(("OK " if ok else "FAIL"), role, tid, "<=", text.splitlines()[0][:60])
        if not ok:
            print(f"     expected {exp_role}/{exp_tid}")
            bad += 1
    return bad


if os.environ.get("TG_ARCH_SELFTEST") == "1":
    sys.exit(run_selftest())


def _clean(s: str) -> str:
    return (s or "").replace("\n", "").replace("\r", "").strip().strip('"').strip("'")


def _looks_like_string_session(s: str) -> bool:
    """Telethon StringSession is base64-ish and usually >> 50 chars."""
    s = _clean(s)
    if len(s) <= 50:
        return False
    # Reject obvious non-sessions (bot tokens, placeholders, paths)
    if ":" in s and s.split(":", 1)[0].isdigit():  # bot API token shape
        return False
    if s.startswith("/") or s.endswith(".session"):
        return False
    if s.lower() in ("none", "null", "changeme", "your_session"):
        return False
    try:
        from telethon.sessions import StringSession
        StringSession(s)  # raises ValueError if not valid
        return True
    except Exception:
        return False


def load_api_creds():
    api_id = os.environ.get("TELEGRAM_API_ID") or os.environ.get("API_ID")
    api_hash = os.environ.get("TELEGRAM_API_HASH") or os.environ.get("API_HASH")
    for p in (Path(".env"), Path("bot/.env"), Path("luxury_building.env")):
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            s = line.strip()
            if not s or s.startswith("#") or "=" not in s:
                continue
            if s.startswith("export "):
                s = s[len("export "):]
            k, _, v = s.partition("=")
            k, v = k.strip(), _clean(v)
            if k in ("TELEGRAM_API_ID", "API_ID") and not api_id:
                api_id = v
            if k in ("TELEGRAM_API_HASH", "API_HASH") and not api_hash:
                api_hash = v
    return api_id, api_hash


def load_session():
    """Same sources the live bot uses — NOT .session_str (wrong file caused Not a valid string)."""
    candidates = []  # (source, value)

    for key in (
        "TELEGRAM_SESSION_STRING",
        "TELEGRAM_STRING_SESSION",
        "STRING_SESSION",
        "TG_SESSION_STRING",
    ):
        v = _clean(os.environ.get(key) or "")
        if v:
            candidates.append((f"env:{key}", v))

    for p in (
        Path(".telegram_session_string"),
        Path("bot/.telegram_session_string"),
        Path("/home/runner/workspace/.telegram_session_string"),
    ):
        if p.exists():
            v = _clean(p.read_text(encoding="utf-8", errors="replace"))
            if v:
                candidates.append((f"file:{p}", v))

    for p in (Path(".env"), Path("bot/.env"), Path("luxury_building.env")):
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            s = line.strip()
            if not s or s.startswith("#") or "=" not in s:
                continue
            if s.startswith("export "):
                s = s[len("export "):]
            k, _, v = s.partition("=")
            k, v = k.strip(), _clean(v)
            if k in (
                "TELEGRAM_SESSION_STRING",
                "TELEGRAM_STRING_SESSION",
                "STRING_SESSION",
                "TG_SESSION_STRING",
            ) and v:
                candidates.append((f"{p}:{k}", v))

    # Diagnose every candidate; pick first valid StringSession
    print("session candidates:")
    for src, v in candidates:
        ok = _looks_like_string_session(v)
        print(f"  {src}: len={len(v)} valid={ok}")
        if ok:
            # materialize canonical file for other tools
            try:
                Path(".telegram_session_string").write_text(v + "\n", encoding="utf-8")
            except Exception:
                pass
            return v, src

    return None, None


async def maybe_convert_sqlite_session(api_id, api_hash):
    """Last resort: convert Telethon *.session SQLite → StringSession."""
    from telethon import TelegramClient
    from telethon.sessions import StringSession

    for sess_file in (
        Path("userbot_session.session"),
        Path("bot/userbot_session.session"),
        Path("/home/runner/workspace/userbot_session.session"),
    ):
        if not sess_file.exists():
            continue
        try:
            name = str(sess_file.with_suffix(""))  # Telethon wants path without .session
            c = TelegramClient(name, int(api_id), str(api_hash))
            await c.connect()
            s = _clean(StringSession.save(c.session))
            await c.disconnect()
            if _looks_like_string_session(s):
                Path(".telegram_session_string").write_text(s + "\n", encoding="utf-8")
                print(f"converted {sess_file} → StringSession len={len(s)}")
                return s, f"converted:{sess_file}"
        except Exception as e:
            print(f"convert {sess_file} failed: {e}")
    return None, None


async def scrape():
    try:
        from telethon import TelegramClient
        from telethon.sessions import StringSession
    except ImportError:
        print("Installing telethon...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "telethon"])
        from telethon import TelegramClient
        from telethon.sessions import StringSession

    api_id, api_hash = load_api_creds()
    session, sess_src = load_session()
    if not session and api_id and api_hash:
        session, sess_src = await maybe_convert_sqlite_session(api_id, api_hash)
    if not session or not api_id or not api_hash:
        print("FATAL: need a valid Telethon StringSession + TELEGRAM_API_ID + TELEGRAM_API_HASH")
        print("On Replit the bot uses:")
        print("  Secret TELEGRAM_SESSION_STRING  OR  file .telegram_session_string")
        print("Check:")
        print("  ls -la .telegram_session_string")
        print("  wc -c .telegram_session_string")
        print("  python3 -c \"from pathlib import Path; t=Path('.telegram_session_string').read_text().strip(); print(len(t))\"")
        sys.exit(2)

    print(f"using session from {sess_src} (len={len(session)})")

    peers = []
    for key in (
        "TELEGRAM_TARGET_PEER",
        "TELEGRAM_COUNTDOWN_PEER",
        "TELEGRAM_ARCHAEOLOGY_PEERS",
    ):
        v = os.environ.get(key)
        if not v:
            continue
        for part in v.split(","):
            part = part.strip()
            if part and part not in peers:
                peers.append(part)
    for d in ("6774605259", "UNIQUE_g1", "@UNIQUE_g1", "Mr_iv4", "@Mr_iv4"):
        if d not in peers:
            peers.append(d)

    client = TelegramClient(StringSession(session), int(api_id), str(api_hash))
    await client.connect()
    if not await client.is_user_authorized():
        print("FATAL: session not authorized")
        sys.exit(3)

    rows = []
    resolved = []
    for peer in peers:
        try:
            ent = await client.get_entity(int(peer) if peer.lstrip("-").isdigit() else peer)
            title = getattr(ent, "title", None) or getattr(ent, "username", None) or str(peer)
            resolved.append((peer, title, ent))
            print(f"OK peer {peer} → {title}")
        except Exception as e:
            print(f"SKIP peer {peer}: {e}")

    if not resolved:
        print("FATAL: no peers resolved — listing dialogs with bacbo/unique/iv4...")
        async for d in client.iter_dialogs():
            name = (d.name or "") + " "
            if re.search(r"bacbo|unique|iv4|g1|gunique|royal", name, re.I):
                print("  dialog:", d.name, d.id)
                resolved.append((str(d.id), d.name, d.entity))
        if not resolved:
            sys.exit(4)

    for peer, title, ent in resolved:
        n = 0
        async for msg in client.iter_messages(ent, offset_date=None):
            if not msg or not msg.date:
                continue
            dt = msg.date
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            if dt < SINCE:
                break  # newest-first
            text = msg.message or msg.raw_text or ""
            if msg.media and not text:
                text = f"[MEDIA:{type(msg.media).__name__}]"
            role, type_id, note, lane, clocks = classify(text)
            rows.append({
                "chat": title,
                "peer": peer,
                "msg_id": msg.id,
                "date_utc": dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                "role": role,
                "type_id": type_id,
                "lane": lane,
                "clocks": clocks,
                "note": note,
                "first_line": first_line(text),
                "text_len": len(text),
                "text_head": text[:400].replace("\n", "\\n"),
            })
            n += 1
            if n % 500 == 0:
                print(f"  … {title}: {n} msgs")
        print(f"DONE {title}: {n} msgs since {SINCE.date()}")

    await client.disconnect()

    rows.sort(key=lambda r: (r["date_utc"], r["msg_id"]))
    OUT.mkdir(parents=True, exist_ok=True)

    fields = [
        "chat", "peer", "msg_id", "date_utc", "role", "type_id", "lane", "clocks",
        "note", "first_line", "text_len", "text_head",
    ]
    csv_path = OUT / "all_messages.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    first = OrderedDict()
    counts = Counter()
    for r in rows:
        counts[r["type_id"]] += 1
        if r["type_id"] not in first:
            first[r["type_id"]] = r

    first_path = OUT / "types_first_seen.csv"
    with first_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[
            "type_id", "role", "lane", "clocks", "first_date_utc", "first_chat",
            "first_msg_id", "count", "first_line", "note",
        ])
        w.writeheader()
        for tid, r in first.items():
            w.writerow({
                "type_id": tid,
                "role": r["role"],
                "lane": r["lane"],
                "clocks": r["clocks"],
                "first_date_utc": r["date_utc"],
                "first_chat": r["chat"],
                "first_msg_id": r["msg_id"],
                "count": counts[tid],
                "first_line": r["first_line"],
                "note": r["note"],
            })

    unknowns = [r for r in rows if r["role"] in ("UNKNOWN", "EMPTY") or r["type_id"].startswith("UNKNOWN_")
                or r["type_id"].startswith("RELAY_OTHER_")]
    unk_path = OUT / "unknown_messages.csv"
    with unk_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(unknowns)

    summary = {
        "since": SINCE.isoformat(),
        "total_messages": len(rows),
        "distinct_types": len(first),
        "unknown_or_other_relay": len(unknowns),
        "by_role": dict(Counter(r["role"] for r in rows)),
        "by_lane": dict(Counter(r["lane"] for r in rows if r["lane"])),
        "types_in_order_first_seen": [
            {
                "type_id": tid,
                "role": first[tid]["role"],
                "lane": first[tid]["lane"],
                "first": first[tid]["date_utc"],
                "count": counts[tid],
                "first_line": first[tid]["first_line"],
            }
            for tid in first
        ],
    }
    (OUT / "types_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    # Auto eras markdown — same structure as manual TELEGRAM_CARD_ERAS.md
    eras = []
    eras.append("# Telegram card eras (AUTO from Telethon scrape)")
    eras.append("")
    eras.append(f"Source of truth = chat text since {SINCE.date()}. Nothing omitted.")
    eras.append(f"total_messages={len(rows)} distinct_types={len(first)} unknown_review={len(unknowns)}")
    eras.append("")
    eras.append("## TYPES IN ORDER OF FIRST APPEARANCE")
    eras.append("")
    eras.append("| First UTC | Role | Lane | n | type_id | First line |")
    eras.append("|-----------|------|------|--:|---------|------------|")
    for tid, r in first.items():
        eras.append(
            f"| {r['date_utc']} | {r['role']} | {r['lane'] or '—'} | {counts[tid]} | `{tid}` | {r['first_line'][:80].replace('|', '/')} |"
        )
    eras.append("")
    eras.append("## UNKNOWN / OTHER (must review — each is a candidate new type)")
    eras.append("")
    if not unknowns:
        eras.append("_none — every message matched a known role fingerprint_")
    else:
        seen_u = OrderedDict()
        for r in unknowns:
            if r["type_id"] not in seen_u:
                seen_u[r["type_id"]] = r
        for tid, r in seen_u.items():
            eras.append(f"- `{r['date_utc']}` `{tid}` — {r['first_line'][:100]}")
    eras.append("")
    eras.append("## Notes")
    eras.append("- ROOM_RELAY `AUTO WIN` ≠ bot RESULT")
    eras.append("- Early FIRE can exist without RESULT type (manual /win /loss /tie era)")
    eras.append("- Clock A (JANELA Ns) ≠ Clock C (Intervalo on result); any Ns counts when present")
    (OUT / "eras_auto.md").write_text("\n".join(eras) + "\n", encoding="utf-8")

    report_lines = [
        f"TELEGRAM TYPE ARCHAEOLOGY since {SINCE.date()}",
        f"total_messages={len(rows)} distinct_types={len(first)} unknown_review={len(unknowns)}",
        f"by_role={summary['by_role']}",
        f"by_lane={summary['by_lane']}",
        "",
        "TYPES IN ORDER OF FIRST APPEARANCE (nothing omitted):",
    ]
    for tid, r in first.items():
        report_lines.append(
            f"  {r['date_utc']}  {r['role']:12}  lane={r['lane'] or '-':16}  n={counts[tid]:5}  {tid}  | {r['first_line'][:70]}"
        )
    if unknowns:
        report_lines.append("")
        report_lines.append(f"UNKNOWN/OTHER TO REVIEW ({len(unknowns)} msgs, {len({u['type_id'] for u in unknowns})} fingerprints):")
        seen_u = OrderedDict()
        for r in unknowns:
            if r["type_id"] not in seen_u:
                seen_u[r["type_id"]] = r
        for tid, r in list(seen_u.items())[:80]:
            report_lines.append(f"  {r['date_utc']}  {tid}  | {r['first_line'][:70]}")
        if len(seen_u) > 80:
            report_lines.append(f"  ... +{len(seen_u)-80} more fingerprints in unknown_messages.csv")
    report_lines += ["", f"Full dump: {csv_path}", f"First-seen: {first_path}", f"Eras: {OUT / 'eras_auto.md'}"]
    report = "\n".join(report_lines) + "\n"
    (OUT / "report.txt").write_text(report, encoding="utf-8")
    print(report)
    print("UPLOAD/zip folder:", OUT)


import asyncio
asyncio.run(scrape())
PY

# Skip zip after --selftest (python already exited 0/1)
if [[ "${TG_ARCH_SELFTEST:-0}" == "1" ]]; then
  echo "selftest finished"
  exit 0
fi

echo "=== zip archaeology ==="
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
ZIP="tg_archaeology_${STAMP}.zip"
zip -r -q "$ZIP" "$OUT"
ls -lah "$ZIP" "$OUT"/* 2>/dev/null | head -40
echo ""
echo "DONE. Paste report.txt here OR upload $ZIP and paste the link."
echo "I will lock every type into TELEGRAM_CARD_ERAS.md from that output — zero manual scrolling."
