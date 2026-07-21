#!/usr/bin/env bash
# Restore Telegram delivery after FIREAGAIN quiet-death.
#
# Root causes addressed:
#  1) FIREAGAIN early-injected lux_floor_rotate → bacbo dies ~60s after subscribe
#  2) 3 Telethon clients on one StringSession → chat goes silent
#
# This script:
#  - strips early inject, LATE+DEFER floor-rotate (45s after import)
#  - installs telegram_outbox (ONE session owner for cards + ONLINE ping)
#  - TEST_PING while everything is dead (exclusive)
#  - starts bacbo first; outbox after 70s delay
#  - watches bacbo 120s and dumps crash if it dies
set -euo pipefail
cd /home/runner/workspace
PY=python3
SHA="${LUXURY_PATCH_SHA:-cursor/add-engine-gate-registry-d5ba}"
BASE="https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/${SHA}/replit_elite_stack_patch"
PEER="${TELEGRAM_TARGET_PEER:-6774605259}"

echo "========== [1/8] hard-stop ALL telegram/session owners =========="
pkill -9 -f 'bacbo_royal_complete.py' 2>/dev/null || true
pkill -9 -f 'runtime_supervisor.py' 2>/dev/null || true
pkill -9 -f 'fallback_signal_sender.py' 2>/dev/null || true
pkill -9 -f 'fallback_result_sender.py' 2>/dev/null || true
pkill -9 -f 'telegram_outbox.py' 2>/dev/null || true
sleep 3
rm -f bot/data/telegram_outbox.lock 2>/dev/null || true
pgrep -af 'runtime_supervisor|bacbo_royal|fallback_|telegram_outbox' || echo clean

echo "========== [2/8] download bits =========="
mkdir -p bot/data logs
for rel in \
  bot/lux_floor_rotate.py \
  bot/runtime_supervisor.py \
  bot/telegram_outbox.py \
  bot/fallback_signal_sender.py \
  bot/fallback_result_sender.py \
  bot/lux_sqlite_harden.py
do
  curl -fsSL -H "Cache-Control: no-cache" -o "$rel" "$BASE/$rel"
done
$PY -m py_compile bot/lux_floor_rotate.py bot/runtime_supervisor.py bot/telegram_outbox.py

echo "========== [3/8] LATE+DEFER floor-rotate (kill early inject) =========="
$PY <<'PY'
import ast, re, time
from pathlib import Path

ROOT = Path("/home/runner/workspace")
bacbo = ROOT / "bacbo_royal_complete.py"
src = bacbo.read_text(encoding="utf-8", errors="replace")
# Strip ALL prior floor-rotate blocks (early or late)
src2 = re.sub(
    r"\n# --- LUXURY_FLOOR_ROTATE \(auto\) ---[\s\S]*?# --- end LUXURY_FLOOR_ROTATE ---\n?",
    "\n",
    src,
)
late = '''
# --- LUXURY_FLOOR_ROTATE (auto) ---
try:
    import os as _lux_os
    import sys as _lux_sys
    from pathlib import Path as _LuxP
    _lux_os.environ.setdefault("LUXURY_FLOOR_ROTATE_DEFER_APPLY", "1")
    _lux_os.environ.setdefault("LUXURY_FLOOR_ROTATE_APPLY_DELAY_SECS", "45")
    _lux_os.environ.setdefault("LUXURY_FLOOR_ROTATE_MODE", "tag")
    _lux_sys.path.insert(0, str(_LuxP("/home/runner/workspace/bot")))
    import lux_floor_rotate  # noqa: F401
    print("[LUXURY] floor-rotate LATE+DEFER OK mode=tag")
except Exception as _lux_fr_exc:
    print("[LUXURY] floor-rotate LATE+DEFER skipped:", _lux_fr_exc)
# --- end LUXURY_FLOOR_ROTATE ---
'''
m = re.search(r"^if __name__", src2, re.M)
if m:
    src2 = src2[: m.start()] + late + "\n" + src2[m.start() :]
    print("injected LATE before __main__")
else:
    m2 = re.search(r"\brun_forever\s*\(", src2)
    if m2:
        src2 = src2[: m2.start()] + late + "\n" + src2[m2.start() :]
        print("injected LATE before run_forever")
    else:
        src2 = src2 + "\n" + late
        print("injected LATE at EOF")

if "lux_sqlite_harden" not in src2 and "LUXURY_SQLITE_HARDEN" not in src2:
    harden = '''
# --- LUXURY_SQLITE_HARDEN (auto) ---
try:
    import lux_sqlite_harden  # noqa: F401
except Exception as _lux_sql_exc:
    print("[LUXURY] sqlite harden skipped:", _lux_sql_exc)
# --- end LUXURY_SQLITE_HARDEN ---
'''
    src2 = src2.replace(late, harden + "\n" + late, 1)
    print("also injected sqlite harden")

ast.parse(src2)
Path(str(bacbo) + f".bak_pre_telegram_up_{int(time.time())}").write_text(src, encoding="utf-8")
bacbo.write_text(src2, encoding="utf-8")
print(
    "bacbo bytes", len(src2),
    "early_blocks", src2.count("early-load"),
    "late_blocks", src2.count("LATE+DEFER"),
)

# database tag rebind
dbp = ROOT / "bot" / "database.py"
if dbp.exists():
    dsrc = dbp.read_text(encoding="utf-8", errors="replace")
    dsrc2 = re.sub(
        r"\n# --- LUXURY_GET_FLOOR_REBIND \(auto\) ---[\s\S]*?# --- end LUXURY_GET_FLOOR_REBIND ---\n?",
        "\n",
        dsrc,
    )
    block = '''
# --- LUXURY_GET_FLOOR_REBIND (auto) ---
try:
    import lux_floor_rotate as _lux_fr
    def get_floor(*_a, **_k):
        return _lux_fr.tag_floor()
    def get_floor_badge(*_a, **_k):
        return _lux_fr._get_floor_badge_impl()
except Exception as _lux_gf_exc:
    print("[LUXURY] database tag-floor rebind skipped:", _lux_gf_exc)
# --- end LUXURY_GET_FLOOR_REBIND ---
'''
    m = re.search(r"^(?:from floor_tracker import[^\n]*|import floor_tracker[^\n]*)\n", dsrc2, re.M)
    if m:
        dsrc2 = dsrc2[: m.end()] + block + dsrc2[m.end() :]
    else:
        dsrc2 = "import floor_tracker\n" + block + dsrc2
    ast.parse(dsrc2)
    dbp.write_text(dsrc2, encoding="utf-8")
    print("database rebind OK")

ft = ROOT / "bot" / "floor_tracker.py"
if ft.exists() and "def get_floor_badge" not in ft.read_text(encoding="utf-8", errors="replace"):
    ft.write_text(ft.read_text(encoding="utf-8", errors="replace") + '''

def get_floor_badge() -> str:
    try:
        from lux_floor_rotate import _get_floor_badge_impl
        return _get_floor_badge_impl()
    except Exception:
        try:
            return f"🏛️ **{get_floor()}**"
        except Exception:
            return "🏛️ **LIVE**"
''', encoding="utf-8")
    print("badge appended")
else:
    print("badge OK")
PY

echo "========== [4/8] env (single outbox) =========="
cat > luxury_building.env <<EOF
export EDGE_POLICY_MODE=luxury
export EDGE_LUXURY_FLOOR_GATE=1
export FALLBACKS_ENABLED=1
export TELEGRAM_SINGLE_OUTBOX=1
export FALLBACK_SEND_BLOCKED=0
export FALLBACK_START_DELAY_SECS=70
export LUXURY_NO_HOUR_BLOCKS=1
export LUXURY_FLOOR_ROTATE=1
export LUXURY_FLOOR_ROTATE_MODE=tag
export LUXURY_FLOOR_ROTATE_SECS=180
export LUXURY_FLOOR_ROTATE_DEFER_APPLY=1
export LUXURY_FLOOR_ROTATE_APPLY_DELAY_SECS=45
export BOT_TZ=America/Sao_Paulo
export TELEGRAM_TARGET_PEER=${PEER}
export TELEGRAM_OUTBOX_STARTUP_PING=1
EOF
set -a
# shellcheck disable=SC1091
source ./luxury_building.env
set +a
export TELEGRAM_SESSION_STRING="$(tr -d '\n' < .telegram_session_string)"
export TELEGRAM_TARGET_PEER="$PEER"
export PYTHONPATH="/home/runner/workspace/bot:/home/runner/workspace:${PYTHONPATH:-}"

echo "========== [5/8] exclusive TEST_PING (no other clients) =========="
$PY <<'PY'
import asyncio, os, sys, fcntl
from pathlib import Path
sys.path.insert(0, "bot"); sys.path.insert(0, ".")
from telethon import TelegramClient
from telethon.sessions import StringSession

def load_api():
    api_id = os.environ.get("TELEGRAM_API_ID") or os.environ.get("API_ID") or ""
    api_hash = os.environ.get("TELEGRAM_API_HASH") or os.environ.get("API_HASH") or ""
    try:
        import config as cfg
        api_id = api_id or str(getattr(cfg, "API_ID", "") or getattr(cfg, "TELEGRAM_API_ID", "") or "")
        api_hash = api_hash or str(getattr(cfg, "API_HASH", "") or getattr(cfg, "TELEGRAM_API_HASH", "") or "")
    except Exception as e:
        print("config", e)
    if Path(".env").exists():
        for line in Path(".env").read_text(errors="ignore").splitlines():
            if "=" not in line or line.strip().startswith("#"):
                continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if k in ("TELEGRAM_API_ID", "API_ID") and not api_id:
                api_id = v
            if k in ("TELEGRAM_API_HASH", "API_HASH") and not api_hash:
                api_hash = v
    return int(api_id), str(api_hash)

async def main():
    lockp = Path("bot/data/telegram_outbox.lock")
    lockp.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(lockp), os.O_CREAT | os.O_RDWR, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("TEST_PING FAIL: lock held — another telegram client still alive")
        os.close(fd)
        return
    api_id, api_hash = load_api()
    sess = (os.environ.get("TELEGRAM_SESSION_STRING") or "").strip()
    if len(sess) < 50:
        sess = Path(".telegram_session_string").read_text().strip()
    peer = int(os.environ.get("TELEGRAM_TARGET_PEER") or "6774605259")
    print("api_id", api_id, "session_len", len(sess), "peer", peer)
    client = TelegramClient(StringSession(sess), api_id, api_hash)
    await client.connect()
    if not await client.is_user_authorized():
        print("TEST_PING FAIL: not authorized — session may be burned (AuthKeyDuplicated)")
        await client.disconnect()
        os.close(fd)
        return
    ent = await client.get_entity(peer)
    msg = await client.send_message(
        ent,
        "LUXURY TEST PING\nTelegram path OK (exclusive).\nNext: OUTBOX ONLINE after bacbo boots.",
    )
    print("TEST_PING OK id=", msg.id, "to", getattr(ent, "username", None) or peer)
    await client.disconnect()
    os.close(fd)
    try:
        lockp.unlink()
    except Exception:
        pass

asyncio.run(main())
PY
sleep 2

echo "========== [6/8] start supervisor (bacbo first, outbox @70s) =========="
echo "===== TELEGRAM_UP $(date -u +%Y-%m-%dT%H:%M:%SZ) =====" >> logs/bot_live.log
nohup env EDGE_POLICY_MODE=luxury EDGE_LUXURY_FLOOR_GATE=1 FALLBACKS_ENABLED=1 \
  TELEGRAM_SINGLE_OUTBOX=1 FALLBACK_START_DELAY_SECS=70 FALLBACK_SEND_BLOCKED=0 \
  LUXURY_FLOOR_ROTATE=1 LUXURY_FLOOR_ROTATE_MODE=tag LUXURY_FLOOR_ROTATE_SECS=180 \
  LUXURY_FLOOR_ROTATE_DEFER_APPLY=1 LUXURY_FLOOR_ROTATE_APPLY_DELAY_SECS=45 \
  LUXURY_NO_HOUR_BLOCKS=1 BOT_TZ=America/Sao_Paulo \
  TELEGRAM_SESSION_STRING="$TELEGRAM_SESSION_STRING" \
  TELEGRAM_TARGET_PEER="$PEER" \
  TELEGRAM_OUTBOX_STARTUP_PING=1 \
  PYTHONPATH="$PYTHONPATH" \
  $PY -u bot/runtime_supervisor.py > /tmp/luxury_supervisor.log 2>&1 &
echo "supervisor pid=$!"

echo "========== [7/8] watch bacbo 120s =========="
DEAD=0
for t in 20 40 60 80 100 120; do
  sleep 20
  bp=$(pgrep -f 'python3 -u /home/runner/workspace/bacbo_royal_complete.py' || true)
  sp=$(pgrep -fc runtime_supervisor.py || echo 0)
  op=$(pgrep -fc telegram_outbox.py || echo 0)
  fp=$(pgrep -fc 'fallback_signal_sender.py|fallback_result_sender.py' || echo 0)
  echo "----- ${t}s bacbo_pids=[${bp:-NONE}] sup=$sp outbox=$op legacy_fallback=$fp -----"
  if [ -z "${bp:-}" ]; then
    echo "BACBO DEAD at ${t}s — dump crash"
    DEAD=1
    break
  fi
done

echo "========== [8/8] verdict =========="
$PY <<'PY'
import re, sqlite3, subprocess
from pathlib import Path

print("--- supervisor log ---")
print(Path("/tmp/luxury_supervisor.log").read_text(errors="replace")[-1500:])

bacbo = subprocess.getoutput("pgrep -af 'bacbo_royal_complete.py' | grep -v pgrep || true")
print("bacbo_proc", bacbo or "NONE")
print("sup", subprocess.getoutput("pgrep -fc runtime_supervisor.py || echo 0"))
print("outbox", subprocess.getoutput("pgrep -fc telegram_outbox.py || echo 0"))
print("legacy_fallback", subprocess.getoutput("pgrep -fc 'fallback_signal_sender.py|fallback_result_sender.py' || echo 0"))

log = Path("logs/bot_live.log").read_text(errors="replace") if Path("logs/bot_live.log").exists() else ""
idx = log.rfind("TELEGRAM_UP")
chunk = log[idx:] if idx >= 0 else "\n".join(log.splitlines()[-100:])
print("--- errors/crash since marker ---")
for ln in chunk.splitlines():
    if re.search(r"Traceback|Error|CRASH|FATAL|NameError|AttributeError|AuthKey|database is locked", ln, re.I):
        print(ln[:240])
print("--- rotate / boot / fire ---")
for ln in chunk.splitlines():
    if any(k in ln for k in ("floor-rotate", "BootFilter", "BootGrace", "run_forever", "FIRED", "LATE+DEFER", "DEFER")):
        print(ln[:220])
print("--- last 25 bot ---")
for ln in log.splitlines()[-25:]:
    print(ln)

print("--- outbox / fallback tails ---")
for p in ("logs/telegram_outbox.log", "logs/fallback_sender.log", "logs/fallback_result_sender.log"):
    print("##", p)
    if Path(p).exists():
        print("\n".join(Path(p).read_text(errors="replace").splitlines()[-12:]))

db = Path("bot/bacbo.db") if Path("bot/bacbo.db").exists() else Path("bacbo.db")
con = sqlite3.connect(str(db))
print("last8", list(con.execute(
    "select id,fired_at,signal_kind,source_floor,outcome from consensus_signals order by id desc limit 8")))
PY

echo
echo "VERDICT — check Telegram for BOTH:"
echo "  1) LUXURY TEST PING  (immediate)"
echo "  2) LUXURY OUTBOX ONLINE  (~70s after start)"
echo "  3) bacbo_proc must NOT be NONE after 120s"
echo "  4) Do NOT re-run FIREAGAIN (it re-injects early rotate and kills bacbo)"
echo "  5) Signal cards need new FIRED rows after bacbo is stable"
echo
echo "DONE. Paste ALL output."
