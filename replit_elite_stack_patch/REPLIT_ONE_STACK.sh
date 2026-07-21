#!/usr/bin/env bash
# Enforce ONE bacbo + ONE supervisor + ONE outbox.
# Hard-reset loop — prior versions left orphans that immediately respawned.
set -euo pipefail
cd /home/runner/workspace
PY=python3
SHA="${LUXURY_PATCH_SHA:-cursor/add-engine-gate-registry-d5ba}"
BASE="https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/${SHA}/replit_elite_stack_patch"
PEER="${TELEGRAM_TARGET_PEER:-6774605259}"

echo "========== [1/4] refresh bits =========="
mkdir -p bot/data logs
for rel in bot/runtime_supervisor.py bot/telegram_outbox.py bot/lux_floor_rotate.py; do
  curl -fsSL -H "Cache-Control: no-cache" -o "$rel" "$BASE/$rel"
done

echo "========== [2/4] HARD RESET all bot/telegram procs =========="
for i in 1 2 3 4 5 6; do
  pkill -9 -f 'runtime_supervisor.py' 2>/dev/null || true
  pkill -9 -f 'telegram_outbox.py' 2>/dev/null || true
  pkill -9 -f 'fallback_signal_sender.py' 2>/dev/null || true
  pkill -9 -f 'fallback_result_sender.py' 2>/dev/null || true
  pkill -9 -f 'bacbo_royal_complete.py' 2>/dev/null || true
  sleep 2
  left=$(pgrep -af 'bacbo_royal_complete|runtime_supervisor|telegram_outbox|fallback_signal|fallback_result' | grep -v pgrep || true)
  if [ -z "$left" ]; then
    echo "clean at pass $i"
    break
  fi
  echo "still alive pass $i:"
  echo "$left"
done
rm -f bot/data/telegram_outbox.lock 2>/dev/null || true
pgrep -af 'bacbo_royal_complete|runtime_supervisor|telegram_outbox|fallback_' | grep -v pgrep || echo "ALL CLEAR"

echo "========== [3/4] start ONE supervisor (starts bacbo+outbox) =========="
set -a
# shellcheck disable=SC1091
[ -f luxury_building.env ] && source ./luxury_building.env || true
set +a
export TELEGRAM_SESSION_STRING="$(tr -d '\n' < .telegram_session_string)"
export TELEGRAM_TARGET_PEER="$PEER"
export TELEGRAM_SINGLE_OUTBOX=1
export FALLBACKS_ENABLED=1
export FALLBACK_START_DELAY_SECS=20
export LUXURY_FLOOR_ROTATE_DEFER_APPLY=0
export PYTHONPATH="/home/runner/workspace/bot:/home/runner/workspace:${PYTHONPATH:-}"

nohup env EDGE_POLICY_MODE=luxury EDGE_LUXURY_FLOOR_GATE=1 FALLBACKS_ENABLED=1 \
  TELEGRAM_SINGLE_OUTBOX=1 FALLBACK_START_DELAY_SECS=20 \
  LUXURY_FLOOR_ROTATE=1 LUXURY_FLOOR_ROTATE_MODE=tag LUXURY_FLOOR_ROTATE_DEFER_APPLY=0 \
  TELEGRAM_SESSION_STRING="$TELEGRAM_SESSION_STRING" \
  TELEGRAM_TARGET_PEER="$PEER" \
  TELEGRAM_OUTBOX_STARTUP_PING=1 \
  PYTHONPATH="$PYTHONPATH" \
  $PY -u bot/runtime_supervisor.py > /tmp/luxury_supervisor.log 2>&1 &
echo "supervisor pid=$!"

echo "========== [4/4] settle 35s =========="
sleep 35
$PY <<'PY'
import subprocess
from pathlib import Path

def count(pat: str) -> int:
    out = subprocess.getoutput(f"pgrep -f '{pat}' | grep -v pgrep || true")
    return len([x for x in out.splitlines() if x.strip().isdigit() or x.strip()])

# count unique PIDs from pgrep -af
def pids(pat: str) -> list[int]:
    out = subprocess.getoutput(f"pgrep -f '{pat}' || true")
    return sorted({int(x) for x in out.split() if x.isdigit()})

b, s, o = pids("bacbo_royal_complete.py"), pids("runtime_supervisor.py"), pids("telegram_outbox.py")
fb = pids("fallback_signal_sender.py") + pids("fallback_result_sender.py")
print("bacbo_pids", b, "n", len(b))
print("supervisor_pids", s, "n", len(s))
print("outbox_pids", o, "n", len(o))
print("legacy_fb_pids", fb, "n", len(fb))
print("--- supervisor log ---")
print(Path("/tmp/luxury_supervisor.log").read_text(errors="replace")[-1200:])
ok = len(b) == 1 and len(s) == 1 and len(o) == 1 and len(fb) == 0
print("VERDICT", "OK" if ok else "BAD — paste output")
PY
echo "DONE."
