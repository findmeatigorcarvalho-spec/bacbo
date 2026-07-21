#!/usr/bin/env bash
# Restore Telegram delivery: bacbo keeps dying after subscribe.
# - move floor-rotate inject LATE (early inject correlated with crash)
# - tag-only mode (engine LIVE, DB tags JUN19+)
# - TEST PING to prove chat delivery
# - watch bacbo stay alive 100s
set -euo pipefail
cd /home/runner/workspace
PY=python3
SHA="${LUXURY_PATCH_SHA:-cursor/add-engine-gate-registry-d5ba}"
BASE="https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/${SHA}/replit_elite_stack_patch"
PEER="${TELEGRAM_TARGET_PEER:-6774605259}"

echo "========== [1/7] hard-stop =========="
pkill -9 -f 'bacbo_royal_complete.py' 2>/dev/null || true
pkill -9 -f 'runtime_supervisor.py' 2>/dev/null || true
pkill -9 -f 'fallback_signal_sender.py' 2>/dev/null || true
pkill -9 -f 'fallback_result_sender.py' 2>/dev/null || true
sleep 3
pgrep -af 'runtime_supervisor|bacbo_royal|fallback_' || echo clean

echo "========== [2/7] download bits =========="
mkdir -p bot/data logs
for rel in \
  bot/lux_floor_rotate.py \
  bot/runtime_supervisor.py \
  bot/fallback_signal_sender.py \
  bot/fallback_result_sender.py \
  bot/lux_sqlite_harden.py
do
  curl -fsSL -H "Cache-Control: no-cache" -o "$rel" "$BASE/$rel"
done
$PY -m py_compile bot/lux_floor_rotate.py bot/runtime_supervisor.py bot/fallback_signal_sender.py

echo "========== [3/7] move floor-rotate to LATE inject + safe database tag =========="
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
# LATE inject — after most of module is defined, before __main__ / run_forever
late = '''
# --- LUXURY_FLOOR_ROTATE (auto) ---
try:
    import sys as _lux_sys
    from pathlib import Path as _LuxP
    _lux_sys.path.insert(0, str(_LuxP("/home/runner/workspace/bot")))
    import lux_floor_rotate  # noqa: F401
    print("[LUXURY] floor-rotate LATE-load OK mode=tag")
except Exception as _lux_fr_exc:
    print("[LUXURY] floor-rotate LATE-load skipped:", _lux_fr_exc)
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

# Ensure sqlite harden still present hint
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
print("bacbo bytes", len(src2), "early_blocks", src2.count("early-load"), "late_blocks", src2.count("LATE-load"))

# database tag rebind (idempotent)
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

# floor_tracker badge
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

echo "========== [4/7] env =========="
cat > luxury_building.env <<EOF
export EDGE_POLICY_MODE=luxury
export EDGE_LUXURY_FLOOR_GATE=1
export FALLBACKS_ENABLED=1
export FALLBACK_SEND_BLOCKED=0
export FALLBACK_START_DELAY_SECS=25
export LUXURY_NO_HOUR_BLOCKS=1
export LUXURY_FLOOR_ROTATE=1
export LUXURY_FLOOR_ROTATE_MODE=tag
export LUXURY_FLOOR_ROTATE_SECS=180
export BOT_TZ=America/Sao_Paulo
export TELEGRAM_TARGET_PEER=${PEER}
EOF
set -a
# shellcheck disable=SC1091
source ./luxury_building.env
set +a
export TELEGRAM_SESSION_STRING="$(tr -d '\n' < .telegram_session_string)"
export TELEGRAM_TARGET_PEER="$PEER"
export PYTHONPATH="/home/runner/workspace/bot:/home/runner/workspace:${PYTHONPATH:-}"

echo "========== [5/7] Telegram TEST PING =========="
$PY <<'PY'
import asyncio, os, sys
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
    api_id, api_hash = load_api()
    sess = (os.environ.get("TELEGRAM_SESSION_STRING") or "").strip()
    if len(sess) < 50:
        sess = Path(".telegram_session_string").read_text().strip()
    peer = int(os.environ.get("TELEGRAM_TARGET_PEER") or "6774605259")
    print("api_id", api_id, "session_len", len(sess), "peer", peer)
    client = TelegramClient(StringSession(sess), api_id, api_hash)
    await client.connect()
    if not await client.is_user_authorized():
        print("TEST_PING FAIL: not authorized")
        await client.disconnect()
        return
    ent = await client.get_entity(peer)
    msg = await client.send_message(
        ent,
        "LUXURY TEST PING\nTelegram path OK.\nWaiting for next engine FIRED → fallback card.",
    )
    print("TEST_PING OK id=", msg.id, "to", getattr(ent, "username", None) or peer)
    await client.disconnect()

asyncio.run(main())
PY

echo "========== [6/7] start supervisor + watch bacbo 100s =========="
echo "===== TELEGRAM_UP $(date -u +%Y-%m-%dT%H:%M:%SZ) =====" >> logs/bot_live.log
nohup env EDGE_POLICY_MODE=luxury EDGE_LUXURY_FLOOR_GATE=1 FALLBACKS_ENABLED=1 \
  FALLBACK_START_DELAY_SECS=25 FALLBACK_SEND_BLOCKED=0 \
  LUXURY_FLOOR_ROTATE=1 LUXURY_FLOOR_ROTATE_MODE=tag LUXURY_FLOOR_ROTATE_SECS=180 \
  LUXURY_NO_HOUR_BLOCKS=1 BOT_TZ=America/Sao_Paulo \
  TELEGRAM_SESSION_STRING="$TELEGRAM_SESSION_STRING" \
  TELEGRAM_TARGET_PEER="$PEER" \
  PYTHONPATH="$PYTHONPATH" \
  $PY -u bot/runtime_supervisor.py > /tmp/luxury_supervisor.log 2>&1 &
echo "supervisor pid=$!"

for t in 20 40 60 80 100; do
  sleep 20
  bp=$(pgrep -f 'python3 -u /home/runner/workspace/bacbo_royal_complete.py' || true)
  sp=$(pgrep -fc runtime_supervisor.py || echo 0)
  fp=$(pgrep -fc fallback_signal_sender.py || echo 0)
  echo "----- ${t}s bacbo_pids=[${bp:-NONE}] sup=$sp fallback=$fp -----"
  if [ -z "${bp:-}" ]; then
    echo "BACBO DEAD at ${t}s — dump crash"
    break
  fi
done

echo "========== [7/7] verdict =========="
$PY <<'PY'
import re, sqlite3, subprocess
from pathlib import Path

print("--- supervisor log ---")
print(Path("/tmp/luxury_supervisor.log").read_text(errors="replace")[-1200:])

bacbo = subprocess.getoutput("pgrep -af 'bacbo_royal_complete.py' | grep -v pgrep || true")
print("bacbo_proc", bacbo or "NONE")
print("sup", subprocess.getoutput("pgrep -fc runtime_supervisor.py || echo 0"))
print("fallback", subprocess.getoutput("pgrep -fc fallback_signal_sender.py || echo 0"))
print("fallback_result", subprocess.getoutput("pgrep -fc fallback_result_sender.py || echo 0"))

log = Path("logs/bot_live.log").read_text(errors="replace") if Path("logs/bot_live.log").exists() else ""
# since TELEGRAM_UP marker
idx = log.rfind("TELEGRAM_UP")
chunk = log[idx:] if idx >= 0 else "\n".join(log.splitlines()[-80:])
print("--- errors/crash since marker ---")
for ln in chunk.splitlines():
    if re.search(r"Traceback|Error|CRASH|FATAL|NameError|AttributeError|database is locked", ln, re.I):
        print(ln[:240])
print("--- rotate / boot ---")
for ln in chunk.splitlines():
    if "floor-rotate" in ln or "BootFilter" in ln or "BootGrace" in ln or "run_forever" in ln or "FIRED" in ln:
        print(ln[:220])
print("--- last 20 bot ---")
for ln in log.splitlines()[-20:]:
    print(ln)

print("--- fallback tails ---")
for p in ("logs/fallback_sender.log", "logs/fallback_result_sender.log"):
    print("##", p)
    if Path(p).exists():
        print("\n".join(Path(p).read_text(errors="replace").splitlines()[-8:]))

db = Path("bot/bacbo.db") if Path("bot/bacbo.db").exists() else Path("bacbo.db")
con = sqlite3.connect(str(db))
print("last8", list(con.execute(
    "select id,fired_at,signal_kind,source_floor,outcome from consensus_signals order by id desc limit 8")))
PY

echo
echo "VERDICT:"
echo "  1) TEST_PING OK → check Telegram for LUXURY TEST PING"
echo "  2) bacbo_proc must NOT be NONE after 100s"
echo "  3) If bacbo dead: paste this output — crash dump above is the cause"
echo "  4) Signal cards need FIRED rows; ping only proves Telegram path"
echo
echo "DONE. Paste ALL output."
