#!/usr/bin/env bash
# Hot-fix outbox: JUN19+ floor tags on cards + real SCORE (no bacbo restart).
# Use when Telegram is already up (TEST_PING/OUTBOX OK) but cards say FLOOR:LIVE / SCORE:0.00
set -euo pipefail
cd /home/runner/workspace
PY=python3
SHA="${LUXURY_PATCH_SHA:-cursor/add-engine-gate-registry-d5ba}"
BASE="https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/${SHA}/replit_elite_stack_patch"
PEER="${TELEGRAM_TARGET_PEER:-6774605259}"

echo "========== [1/4] refresh outbox + rotator (bacbo stays up) =========="
mkdir -p bot/data logs
for rel in bot/telegram_outbox.py bot/lux_floor_rotate.py bot/runtime_supervisor.py; do
  curl -fsSL -H "Cache-Control: no-cache" -o "$rel" "$BASE/$rel"
done
$PY -m py_compile bot/telegram_outbox.py bot/lux_floor_rotate.py

echo "========== [2/4] kill ONLY telegram senders (keep bacbo) =========="
pkill -9 -f 'telegram_outbox.py' 2>/dev/null || true
pkill -9 -f 'fallback_signal_sender.py' 2>/dev/null || true
pkill -9 -f 'fallback_result_sender.py' 2>/dev/null || true
sleep 2
rm -f bot/data/telegram_outbox.lock 2>/dev/null || true

# If supervisor is up it will restart outbox; otherwise start outbox alone.
if ! pgrep -f 'runtime_supervisor.py' >/dev/null; then
  echo "WARN: no supervisor — starting outbox under nohup"
  set -a
  # shellcheck disable=SC1091
  [ -f luxury_building.env ] && source ./luxury_building.env || true
  set +a
  export TELEGRAM_SESSION_STRING="$(tr -d '\n' < .telegram_session_string)"
  export TELEGRAM_TARGET_PEER="$PEER"
  export TELEGRAM_SINGLE_OUTBOX=1
  export TELEGRAM_OUTBOX_STARTUP_PING=1
  export PYTHONPATH="/home/runner/workspace/bot:/home/runner/workspace:${PYTHONPATH:-}"
  nohup $PY -u bot/telegram_outbox.py >> logs/telegram_outbox.log 2>&1 &
  echo "outbox pid=$!"
else
  echo "supervisor alive — it will restart telegram_outbox"
fi

echo "========== [3/4] stamp recent LIVE rows + smoke =========="
sleep 8
$PY <<'PY'
import os, sys, sqlite3, subprocess
from pathlib import Path
sys.path.insert(0, "bot")
os.environ.setdefault("LUXURY_FLOOR_ROTATE", "1")
os.environ.setdefault("LUXURY_FLOOR_ROTATE_MODE", "tag")
os.environ.setdefault("LUXURY_FLOOR_ROTATE_DEFER_APPLY", "0")
import importlib
import lux_floor_rotate
importlib.reload(lux_floor_rotate)
print("tag_floor", lux_floor_rotate.tag_floor())
print("mode", lux_floor_rotate._mode())
n = lux_floor_rotate.stamp_live_rows(limit=30)
print("stamped", n)
db = Path("bot/bacbo.db") if Path("bot/bacbo.db").exists() else Path("bacbo.db")
con = sqlite3.connect(str(db))
print("last8", list(con.execute(
    "select id,fired_at,signal_kind,source_floor,"
    "coalesce(total_score,0),coalesce(final_score,0),coalesce(confidence_pct,0) "
    "from consensus_signals order by id desc limit 8")))
print("bacbo", subprocess.getoutput("pgrep -fc bacbo_royal_complete.py || echo 0"))
print("outbox", subprocess.getoutput("pgrep -fc telegram_outbox.py || echo 0"))
print("legacy_fb", subprocess.getoutput(
    "pgrep -fc 'fallback_signal_sender.py|fallback_result_sender.py' || echo 0"))
PY

echo "========== [4/4] outbox log =========="
tail -n 15 logs/telegram_outbox.log 2>/dev/null || echo "(no outbox log yet)"

echo
echo "VERDICT:"
echo "  - bacbo should stay up (count >= 1)"
echo "  - outbox >= 1, legacy_fb = 0"
echo "  - next FIRED card: FLOOR=JUN19+ (not LIVE), SCORE != 0.00 when DB has final/confidence"
echo "  - check Telegram for OUTBOX ONLINE ping"
echo
echo "DONE. Paste output if next card still says LIVE / 0.00."
