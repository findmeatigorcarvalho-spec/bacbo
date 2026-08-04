#!/usr/bin/env bash
# Full Telegram card archaeology — EVERY message since Mar 17, EVERY distinct type.
# Same method as manual scroll: chronological first-seen of each skin. Automated.
# Does NOT drop unknowns — fingerprints them so nothing is missed.
#
#   curl -fsSL -o TG_ARCH.sh \
#     'https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/cursor/add-engine-gate-registry-d5ba/replit_elite_stack_patch/REPLIT_TELEGRAM_TYPE_ARCHAEOLOGY.sh?v=20260803c'
#   bash TG_ARCH.sh              # fresh full scrape Mar 17 → today
#   bash TG_ARCH.sh --resume     # continue older than existing CSV (after Ctrl+C)
#   bash TG_ARCH.sh --diag
#
# MUST reach SINCE_ISO (default 2026-03-17). Jul-only dump = incomplete.
# When done: bash TG_UP.sh → paste FETCH_URL=
set -euo pipefail
cd /home/runner/workspace 2>/dev/null || cd "$(dirname "$0")/.."

ARCH_VERSION="20260803h"
echo "ARCH_VERSION=${ARCH_VERSION} cwd=$(pwd)"

OUT="tg_archaeology"
mkdir -p "$OUT"
export OUT
export SINCE_ISO="${SINCE_ISO:-2026-03-17T00:00:00+00:00}"
export TG_ARCH_RESUME="${TG_ARCH_RESUME:-0}"

# shellcheck disable=SC1091
[[ -f .env ]] && set -a && source ./.env && set +a || true
# File wins over a short/broken Replit secret (same as REPLIT_FINISH / ONE_STACK)
if [[ -f .telegram_session_string ]]; then
  _S="$(tr -d '\n\r' < .telegram_session_string)"
  if [[ ${#_S} -gt 50 ]]; then
    export TELEGRAM_SESSION_STRING="$_S"
    echo "prefill: .telegram_session_string len=${#_S} first_char='${_S:0:1}'"
  fi
fi

# Usage: bash TG_ARCH.sh [--selftest|--diag|--resume]
if [[ "${1:-}" == "--selftest" ]]; then
  export TG_ARCH_SELFTEST=1
fi
if [[ "${1:-}" == "--diag" ]]; then
  export TG_ARCH_DIAG=1
fi
if [[ "${1:-}" == "--resume" ]]; then
  export TG_ARCH_RESUME=1
  echo "RESUME=1 — will append older msgs from existing tg_archaeology/all_messages.csv"
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

    # 🟡 EMPATE — SOLO_ELITE  (bot TIE result — ≠ WIN/LOSS, ≠ room relay)
    if re.search(r"^🟡\s*EMPATE\s*—", fl, re.I) or re.search(r"^EMPATE\s*—", fl, re.I):
        kind = re.sub(r"^🟡\s*EMPATE\s*—\s*", "", fl, flags=re.I)
        kind = re.sub(r"^EMPATE\s*—\s*", "", kind, flags=re.I).strip()
        role, tid = "RESULT", f"RESULT_EMPATE_{fingerprint(kind, 40)}"
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
    # GALE N RETENTATIVA before plain SOLO — body still contains SOLO ELITE SIGNAL
    if re.search(r"GALE\s*\d+\s*—\s*RETENTATIVA", t, re.I) or re.match(r"^♻️\s*GALE", fl):
        gm = re.search(r"GALE\s*(\d+)", t, re.I)
        g = gm.group(1) if gm else "X"
        kind = "GENERIC"
        for k in ("SOLO ELITE", "GOLDEN", "SEQUENCE", "PLATINUM", "FLASH", "ULTRA TIE", "EMERGING", "EMERGINDO"):
            if re.search(k, t, re.I):
                kind = fingerprint(k, 20)
                break
        role, tid = "FIRE", f"FIRE_GALE_{g}_RETENTATIVA_{kind}"
    elif re.search(r"GOLDEN SIGNAL\s*—\s*ENTER NOW", t, re.I):
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
    (
        "♻️ GALE 1 — RETENTATIVA (1 room at G1)\n💎 SOLO ELITE SIGNAL 💎\n⚡ ENTER NOW",
        "FIRE",
        "FIRE_GALE_1_RETENTATIVA_SOLO_ELITE",
    ),
    (
        "🟡 EMPATE — SOLO_ELITE\nResultado empatado — proteção ativada!",
        "RESULT",
        "RESULT_EMPATE_SOLO_ELITE",
    ),
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


def _session_diag(label: str, s: str) -> None:
    s = _clean(s)
    if not s:
        print(f"  {label}: EMPTY")
        return
    first = s[0]
    print(
        f"  {label}: len={len(s)} first={first!r} ord={ord(first)} "
        f"starts_with_1={first == '1'} tail={s[-8:]!r}"
    )


def _looks_like_string_session(s: str) -> bool:
    """Telethon StringSession must start with version char '1' (see telethon/sessions/string.py)."""
    s = _clean(s)
    if len(s) <= 50:
        return False
    if ":" in s and s.split(":", 1)[0].isdigit():  # bot API token shape
        return False
    if s.startswith("/") or s.endswith(".session"):
        return False
    if s.lower() in ("none", "null", "changeme", "your_session"):
        return False
    # Exact Telethon rule — this is the ValueError you hit
    if s[0] != "1":
        return False
    try:
        from telethon.sessions import StringSession
        StringSession(s)
        return True
    except Exception:
        return False


def find_sqlite_session_names():
    """Return Telethon session stems (path without .session)."""
    names = []
    for p in (
        Path("userbot_session.session"),
        Path("bot/userbot_session.session"),
        Path("/home/runner/workspace/userbot_session.session"),
        Path("bacbo_session.session"),
        Path("bot/bacbo_session.session"),
        Path("anon.session"),
        Path("bot/anon.session"),
    ):
        if p.exists():
            names.append(str(p.with_suffix("")))
    # any other *.session in workspace root / bot
    for folder in (Path("."), Path("bot")):
        if not folder.is_dir():
            continue
        for p in folder.glob("*.session"):
            # skip journal
            if p.name.endswith("-journal") or p.name.endswith("-wal"):
                continue
            stem = str(p.with_suffix(""))
            if stem not in names:
                names.append(stem)
    return names


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
        _session_diag(src, v)
        ok = _looks_like_string_session(v)
        print(f"    → valid_StringSession={ok}")
        if ok:
            try:
                Path(".telegram_session_string").write_text(v + "\n", encoding="utf-8")
            except Exception:
                pass
            return v, src

    return None, None


async def open_telegram_client(api_id, api_hash):
    """Open client via valid StringSession OR on-disk *.session (live bot often uses file)."""
    from telethon import TelegramClient
    from telethon.sessions import StringSession

    session, sess_src = load_session()
    if session:
        print(f"using StringSession from {sess_src} (len={len(session)})")
        client = TelegramClient(StringSession(session), int(api_id), str(api_hash))
        await client.connect()
        if await client.is_user_authorized():
            return client, sess_src
        await client.disconnect()
        print("StringSession connected but NOT authorized — trying *.session files")

    sqlite_names = find_sqlite_session_names()
    print(f"sqlite session files found: {sqlite_names or 'NONE'}")
    for name in sqlite_names:
        try:
            client = TelegramClient(name, int(api_id), str(api_hash))
            await client.connect()
            if await client.is_user_authorized():
                # refresh string file for next time
                try:
                    s = _clean(StringSession.save(client.session))
                    if _looks_like_string_session(s):
                        Path(".telegram_session_string").write_text(s + "\n", encoding="utf-8")
                        print(f"refreshed .telegram_session_string from {name}.session len={len(s)}")
                except Exception as e:
                    print(f"could not refresh string session: {e}")
                print(f"using sqlite session: {name}.session")
                return client, f"sqlite:{name}"
            await client.disconnect()
            print(f"  {name}.session: not authorized")
        except Exception as e:
            print(f"  {name}.session failed: {e}")

    return None, None


def run_diag() -> int:
    print("=== TG SESSION DIAG ===")
    api_id, api_hash = load_api_creds()
    print(f"api_id={'set' if api_id else 'MISSING'} api_hash={'set' if api_hash else 'MISSING'}")
    p = Path(".telegram_session_string")
    if p.exists():
        raw = p.read_bytes()
        print(f"file .telegram_session_string: {p.stat().st_size} bytes on disk")
        print(f"  raw_head_hex={raw[:16].hex()} raw_head_ascii={raw[:20]!r}")
        _session_diag("file_cleaned", raw.decode("utf-8", "replace"))
        print(f"  valid={_looks_like_string_session(raw.decode('utf-8', 'replace'))}")
        print("  Telethon requires first char == '1' (version). len after version for IPv4 == 352 → total 353.")
    else:
        print("file .telegram_session_string: MISSING")
    for key in (
        "TELEGRAM_SESSION_STRING",
        "TELEGRAM_STRING_SESSION",
        "STRING_SESSION",
        "TG_SESSION_STRING",
    ):
        v = os.environ.get(key)
        if v is not None:
            _session_diag(f"env:{key}", v)
            print(f"    → valid={_looks_like_string_session(v)}")
    print("sqlite:", find_sqlite_session_names() or "NONE")
    print("ls *.session:")
    for folder in (Path("."), Path("bot")):
        if folder.is_dir():
            for f in sorted(folder.glob("*.session*")):
                print(f"  {f} ({f.stat().st_size} bytes)")
    return 0


if os.environ.get("TG_ARCH_DIAG") == "1":
    sys.exit(run_diag())


async def scrape():
    try:
        from telethon import TelegramClient  # noqa: F401
        from telethon.sessions import StringSession  # noqa: F401
    except ImportError:
        print("Installing telethon...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "telethon"])

    api_id, api_hash = load_api_creds()
    if not api_id or not api_hash:
        print("FATAL: TELEGRAM_API_ID + TELEGRAM_API_HASH required")
        sys.exit(2)

    client, sess_src = await open_telegram_client(api_id, api_hash)
    if not client:
        print("FATAL: no usable Telegram session")
        print("Your .telegram_session_string is 354 bytes but Telethon says invalid")
        print("if it does NOT start with the character 1.")
        print("Run:  bash TG_ARCH.sh --diag")
        print("Then either:")
        print("  - fix/regenerate StringSession (must start with '1'), OR")
        print("  - ensure a live *.session file exists (userbot_session.session)")
        sys.exit(2)

    print(f"client ready via {sess_src}")

    peers = []
    for key in (
        "TELEGRAM_ARCH_PEERS",  # dual-scan override: Mr_iv4,UNIQUE_g1,…
        "TELEGRAM_ARCHAEOLOGY_PEERS",
        "TELEGRAM_TARGET_PEER",
        "TELEGRAM_COUNTDOWN_PEER",
    ):
        v = os.environ.get(key)
        if not v:
            continue
        for part in v.split(","):
            part = part.strip()
            if part and part not in peers:
                peers.append(part)
    # Always include money + Gunique (never miss a destination chat).
    for d in ("6774605259", "UNIQUE_g1", "@UNIQUE_g1", "Mr_iv4", "@Mr_iv4"):
        if d not in peers:
            peers.append(d)
    print(f"ARCH_PEERS_RESOLVE_LIST={peers}", flush=True)

    # INCREMENTAL WRITE — do NOT keep 260k rows in RAM (that killed the last run)
    OUT.mkdir(parents=True, exist_ok=True)
    fields = [
        "chat", "peer", "msg_id", "date_utc", "role", "type_id", "lane", "clocks",
        "note", "first_line", "text_len", "text_head",
    ]
    csv_path = OUT / "all_messages.csv"
    unk_path = OUT / "unknown_messages.csv"
    progress_path = OUT / "progress.json"
    RESUME = os.environ.get("TG_ARCH_RESUME") == "1"
    print(f"TARGET_RANGE: {SINCE.date()} → today (UTC)  RESUME={RESUME}", flush=True)

    resolved = []
    seen_ent = set()
    for peer in peers:
        try:
            ent = await client.get_entity(int(peer) if peer.lstrip("-").isdigit() else peer)
            eid = getattr(ent, "id", None)
            if eid in seen_ent:
                print(f"DEDUP peer {peer} (same entity {eid})", flush=True)
                continue
            seen_ent.add(eid)
            title = getattr(ent, "title", None) or getattr(ent, "username", None) or str(peer)
            resolved.append((peer, title, ent))
            print(f"OK peer {peer} → {title} id={eid}", flush=True)
        except Exception as e:
            print(f"SKIP peer {peer}: {e}", flush=True)

    if not resolved:
        print("FATAL: no peers resolved — listing dialogs with bacbo/unique/iv4...", flush=True)
        async for d in client.iter_dialogs():
            name = (d.name or "") + " "
            if re.search(r"bacbo|unique|iv4|g1|gunique|royal", name, re.I):
                eid = getattr(d.entity, "id", d.id)
                if eid in seen_ent:
                    continue
                seen_ent.add(eid)
                print("  dialog:", d.name, d.id, flush=True)
                resolved.append((str(d.id), d.name, d.entity))
        if not resolved:
            sys.exit(4)

    first = {}  # type_id -> oldest row (scan is newest-first)
    counts = Counter()
    role_counts = Counter()
    lane_counts = Counter()
    unknown_first = OrderedDict()
    total = 0
    unknown_n = 0
    # per chat title → oldest msg_id already stored (for resume offset_id)
    resume_offset_id = {}  # title -> min msg_id
    oldest_date_seen = None
    newest_date_seen = None

    def ingest_row(row, write_unk_file=None):
        nonlocal total, unknown_n, oldest_date_seen, newest_date_seen
        tid = row["type_id"]
        counts[tid] += 1
        role_counts[row["role"]] += 1
        if row.get("lane"):
            lane_counts[row["lane"]] += 1
        prev = first.get(tid)
        if prev is None or row["date_utc"] < prev["date_utc"] or (
            row["date_utc"] == prev["date_utc"] and int(row["msg_id"]) < int(prev["msg_id"])
        ):
            first[tid] = row
        is_unk = row["role"] in ("UNKNOWN", "EMPTY") or tid.startswith("UNKNOWN_") or tid.startswith("RELAY_OTHER_")
        if is_unk:
            unknown_n += 1
            if tid not in unknown_first:
                unknown_first[tid] = row
            if write_unk_file is not None:
                write_unk_file.writerow(row)
        total += 1
        d = row["date_utc"]
        if oldest_date_seen is None or d < oldest_date_seen:
            oldest_date_seen = d
        if newest_date_seen is None or d > newest_date_seen:
            newest_date_seen = d

    if RESUME and csv_path.exists() and csv_path.stat().st_size > 0:
        print(f"Loading existing {csv_path} for resume...", flush=True)
        with csv_path.open(newline="", encoding="utf-8") as rf:
            for row in csv.DictReader(rf):
                ingest_row(row)
                title = row["chat"]
                mid = int(row["msg_id"])
                if title not in resume_offset_id or mid < resume_offset_id[title]:
                    resume_offset_id[title] = mid
        print(
            f"RESUME state: total={total} types={len(first)} "
            f"range={oldest_date_seen} → {newest_date_seen} offsets={resume_offset_id}",
            flush=True,
        )
        csv_f = csv_path.open("a", newline="", encoding="utf-8")
        unk_f = unk_path.open("a", newline="", encoding="utf-8")
        w = csv.DictWriter(csv_f, fieldnames=fields)
        wu = csv.DictWriter(unk_f, fieldnames=fields)
        # no header on append
    else:
        if RESUME:
            print("RESUME requested but no existing CSV — starting fresh", flush=True)
        csv_f = csv_path.open("w", newline="", encoding="utf-8")
        unk_f = unk_path.open("w", newline="", encoding="utf-8")
        w = csv.DictWriter(csv_f, fieldnames=fields)
        wu = csv.DictWriter(unk_f, fieldnames=fields)
        w.writeheader()
        wu.writeheader()
    csv_f.flush()
    unk_f.flush()

    def flush_progress(force_types=False):
        # ALWAYS rewrite progress + types snapshot every call (every 500 msgs).
        # Prior bug: types_first_seen only every 2000 → upload after kill had STALE Jul-only types.
        coverage_ok = bool(oldest_date_seen and oldest_date_seen[:10] <= SINCE.date().isoformat())
        progress_path.write_text(json.dumps({
            "total": total,
            "distinct_types": len(first),
            "unknown_n": unknown_n,
            "by_role": dict(role_counts),
            "oldest_date_utc": oldest_date_seen,
            "newest_date_utc": newest_date_seen,
            "target_since": SINCE.date().isoformat(),
            "coverage_complete_to_mar17": coverage_ok,
            "updated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        }, indent=2), encoding="utf-8")
        ordered = sorted(first.values(), key=lambda r: (r["date_utc"], int(r["msg_id"])))
        tmp = OUT / "types_first_seen.csv.tmp"
        with tmp.open("w", newline="", encoding="utf-8") as ff:
            wf = csv.DictWriter(ff, fieldnames=[
                "type_id", "role", "lane", "clocks", "first_date_utc", "first_chat",
                "first_msg_id", "count", "first_line", "note",
            ])
            wf.writeheader()
            for r in ordered:
                wf.writerow({
                    "type_id": r["type_id"],
                    "role": r["role"],
                    "lane": r["lane"],
                    "clocks": r["clocks"],
                    "first_date_utc": r["date_utc"],
                    "first_chat": r["chat"],
                    "first_msg_id": r["msg_id"],
                    "count": counts[r["type_id"]],
                    "first_line": r["first_line"],
                    "note": r["note"],
                })
        tmp.replace(OUT / "types_first_seen.csv")
        # tiny coverage flag file for upload scripts
        (OUT / "COVERAGE.txt").write_text(
            f"oldest={oldest_date_seen}\nnewest={newest_date_seen}\n"
            f"total={total}\ncomplete_to_mar17={coverage_ok}\n",
            encoding="utf-8",
        )

    try:
        for peer, title, ent in resolved:
            n = 0
            offset_id = resume_offset_id.get(title) if RESUME else None
            if offset_id:
                print(f"CONTINUE {title} older than msg_id={offset_id}", flush=True)
            async for msg in client.iter_messages(ent, offset_id=offset_id or 0):
                if not msg or not msg.date:
                    continue
                dt = msg.date
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                if dt < SINCE:
                    print(f"HIT_SINCE {title}: reached {dt.date()} < {SINCE.date()} — peer complete", flush=True)
                    break  # newest-first
                text = msg.message or msg.raw_text or ""
                if msg.media and not text:
                    text = f"[MEDIA:{type(msg.media).__name__}]"
                role, type_id, note, lane, clocks = classify(text)
                row = {
                    "chat": title,
                    "peer": peer,
                    "msg_id": msg.id,
                    "date_utc": dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                    "role": role,
                    "type_id": type_id,
                    "lane": lane,
                    "clocks": clocks,
                    "note": (note or "")[:200],
                    "first_line": first_line(text),
                    "text_len": len(text),
                    "text_head": text[:400].replace("\n", "\\n"),
                }
                w.writerow(row)
                ingest_row(row, write_unk_file=wu)
                n += 1
                if n % 500 == 0:
                    csv_f.flush()
                    unk_f.flush()
                    flush_progress()
                    print(
                        f"  … {title}: +{n} (total={total} types={len(first)} "
                        f"oldest={oldest_date_seen}) flushed",
                        flush=True,
                    )
            print(f"DONE {title}: +{n} this pass | total={total} oldest={oldest_date_seen}", flush=True)
            csv_f.flush()
            unk_f.flush()
            flush_progress(force_types=True)
    finally:
        csv_f.close()
        unk_f.close()
        try:
            await client.disconnect()
        except Exception:
            pass

    flush_progress(force_types=True)
    ordered = sorted(first.values(), key=lambda r: (r["date_utc"], int(r["msg_id"])))
    first_path = OUT / "types_first_seen.csv"
    coverage_ok = bool(oldest_date_seen and oldest_date_seen[:10] <= SINCE.date().isoformat())
    print(
        f"COVERAGE: oldest={oldest_date_seen} newest={newest_date_seen} "
        f"target_since={SINCE.date()} complete={coverage_ok}",
        flush=True,
    )
    if not coverage_ok:
        print(
            "INCOMPLETE: dump does NOT reach Mar 17 yet. Re-run: bash TG_ARCH.sh --resume",
            flush=True,
        )

    summary = {
        "since": SINCE.isoformat(),
        "total_messages": total,
        "distinct_types": len(first),
        "unknown_or_other_relay": unknown_n,
        "oldest_date_utc": oldest_date_seen,
        "newest_date_utc": newest_date_seen,
        "coverage_complete_to_mar17": coverage_ok,
        "by_role": dict(role_counts),
        "by_lane": dict(lane_counts),
        "types_in_order_first_seen": [
            {
                "type_id": r["type_id"],
                "role": r["role"],
                "lane": r["lane"],
                "first": r["date_utc"],
                "count": counts[r["type_id"]],
                "first_line": r["first_line"],
            }
            for r in ordered
        ],
    }
    (OUT / "types_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    eras = [
        "# Telegram card eras (AUTO from Telethon scrape)",
        "",
        f"Source of truth = chat text since {SINCE.date()}. Nothing omitted.",
        f"total_messages={total} distinct_types={len(first)} unknown_review={unknown_n}",
        "",
        "## TYPES IN ORDER OF FIRST APPEARANCE",
        "",
        "| First UTC | Role | Lane | n | type_id | First line |",
        "|-----------|------|------|--:|---------|------------|",
    ]
    for r in ordered:
        eras.append(
            f"| {r['date_utc']} | {r['role']} | {r['lane'] or '—'} | {counts[r['type_id']]} | `{r['type_id']}` | {r['first_line'][:80].replace('|', '/')} |"
        )
    eras += ["", "## UNKNOWN / OTHER (must review — each is a candidate new type)", ""]
    if not unknown_first:
        eras.append("_none — every message matched a known role fingerprint_")
    else:
        for tid, r in unknown_first.items():
            eras.append(f"- `{r['date_utc']}` `{tid}` — {r['first_line'][:100]}")
    eras += [
        "",
        "## Notes",
        "- ROOM_RELAY `AUTO WIN` ≠ bot RESULT",
        "- Early FIRE can exist without RESULT type (manual /win /loss /tie era)",
        "- Clock A (JANELA Ns) ≠ Clock C (Intervalo on result); any Ns counts when present",
    ]
    (OUT / "eras_auto.md").write_text("\n".join(eras) + "\n", encoding="utf-8")

    report_lines = [
        f"TELEGRAM TYPE ARCHAEOLOGY since {SINCE.date()}",
        f"total_messages={total} distinct_types={len(first)} unknown_review={unknown_n}",
        f"by_role={summary['by_role']}",
        f"by_lane={summary['by_lane']}",
        "",
        "TYPES IN ORDER OF FIRST APPEARANCE (nothing omitted):",
    ]
    for r in ordered:
        report_lines.append(
            f"  {r['date_utc']}  {r['role']:12}  lane={r['lane'] or '-':16}  n={counts[r['type_id']]:5}  {r['type_id']}  | {r['first_line'][:70]}"
        )
    if unknown_first:
        report_lines.append("")
        report_lines.append(f"UNKNOWN/OTHER TO REVIEW ({unknown_n} msgs, {len(unknown_first)} fingerprints):")
        for tid, r in list(unknown_first.items())[:80]:
            report_lines.append(f"  {r['date_utc']}  {tid}  | {r['first_line'][:70]}")
        if len(unknown_first) > 80:
            report_lines.append(f"  ... +{len(unknown_first)-80} more fingerprints in unknown_messages.csv")
    report_lines += ["", f"Full dump: {csv_path}", f"First-seen: {first_path}", f"Eras: {OUT / 'eras_auto.md'}"]
    report = "\n".join(report_lines) + "\n"
    (OUT / "report.txt").write_text(report, encoding="utf-8")
    (OUT / "PASTE_ME.txt").write_text(report, encoding="utf-8")
    print(report, flush=True)
    print("UPLOAD/zip folder:", OUT, flush=True)


import asyncio
asyncio.run(scrape())
PY

# Skip zip after --selftest / --diag
if [[ "${TG_ARCH_SELFTEST:-0}" == "1" ]]; then
  echo "selftest finished"
  exit 0
fi
if [[ "${TG_ARCH_DIAG:-0}" == "1" ]]; then
  exit 0
fi

echo "=== zip archaeology ==="
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
ZIP="tg_archaeology_${STAMP}.zip"
zip -r -q "$ZIP" "$OUT"
ls -lah "$ZIP" "$OUT"/* 2>/dev/null | head -40

echo ""
echo "=== auto-upload catalog so cloud agent can FETCH (you only paste one URL) ==="
UPLOADER="replit_elite_stack_patch/REPLIT_TG_ARCH_UPLOAD.sh"
if [[ ! -f "$UPLOADER" ]]; then
  curl -fsSL -o /tmp/TG_UP.sh \
    "https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/cursor/add-engine-gate-registry-d5ba/replit_elite_stack_patch/REPLIT_TG_ARCH_UPLOAD.sh" \
    && UPLOADER=/tmp/TG_UP.sh || true
fi
if [[ -f "$UPLOADER" ]]; then
  bash "$UPLOADER" "$OUT" || true
else
  echo "uploader missing — paste: cat $OUT/PASTE_ME.txt"
fi
echo ""
echo "DONE. Paste the FETCH_URL= line here (one line). Agent downloads the rest."
