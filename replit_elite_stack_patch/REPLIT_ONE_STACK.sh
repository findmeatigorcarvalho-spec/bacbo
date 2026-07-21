#!/usr/bin/env bash
# Enforce ONE bacbo + ONE supervisor + ONE outbox (no legacy fallbacks).
# Does not change luxury/peak logic — process hygiene only.
set -euo pipefail
cd /home/runner/workspace
PY=python3
SHA="${LUXURY_PATCH_SHA:-cursor/add-engine-gate-registry-d5ba}"
BASE="https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/${SHA}/replit_elite_stack_patch"
PEER="${TELEGRAM_TARGET_PEER:-6774605259}"

echo "========== [1/4] refresh supervisor/outbox/rotator =========="
mkdir -p bot/data logs
for rel in bot/runtime_supervisor.py bot/telegram_outbox.py bot/lux_floor_rotate.py; do
  curl -fsSL -H "Cache-Control: no-cache" -o "$rel" "$BASE/$rel"
done

echo "========== [2/4] kill senders + supervisors; keep ONE bacbo =========="
pkill -9 -f 'runtime_supervisor.py' 2>/dev/null || true
pkill -9 -f 'telegram_outbox.py' 2>/dev/null || true
pkill -9 -f 'fallback_signal_sender.py' 2>/dev/null || true
pkill -9 -f 'fallback_result_sender.py' 2>/dev/null || true
sleep 2
rm -f bot/data/telegram_outbox.lock 2>/dev/null || true

$PY <<'PY'
import os, signal, subprocess, time
raw = subprocess.getoutput("pgrep -f bacbo_royal_complete.py || true")
pids = sorted(int(x) for x in raw.split() if x.isdigit())
print("bacbo_pids_before", pids)
if len(pids) > 1:
    keep = pids[0]
    for pid in pids[1:]:
        try:
            os.kill(pid, signal.SIGKILL)
            print("killed_extra_bacbo", pid)
        except Exception as e:
            print("kill_fail", pid, e)
    time.sleep(1)
raw2 = subprocess.getoutput("pgrep -f bacbo_royal_complete.py || true")
print("bacbo_pids_after", [int(x) for x in raw2.split() if x.isdigit()])
elif not pids:
    print("WARN: no bacbo running — supervisor will start one")
else:
    print("bacbo_ok", pids[0])
PY

echo "========== [3/4] start single supervisor (adopts bacbo) =========="
set -a
# shellcheck disable=SC1091
[ -f luxury_building.env ] && source ./luxury_building.env || true
set +a
export TELEGRAM_SESSION_STRING="$(tr -d '\n' < .telegram_session_string)"
export TELEGRAM_TARGET_PEER="$PEER"
export TELEGRAM_SINGLE_OUTBOX=1
export FALLBACKS_ENABLED=1
export FALLBACK_START_DELAY_SECS=15
export LUXURY_FLOOR_ROTATE_DEFER_APPLY=0
export PYTHONPATH="/home/runner/workspace/bot:/home/runner/workspace:${PYTHONPATH:-}"

nohup env EDGE_POLICY_MODE=luxury EDGE_LUXURY_FLOOR_GATE=1 FALLBACKS_ENABLED=1 \
  TELEGRAM_SINGLE_OUTBOX=1 FALLBACK_START_DELAY_SECS=15 \
  LUXURY_FLOOR_ROTATE=1 LUXURY_FLOOR_ROTATE_MODE=tag LUXURY_FLOOR_ROTATE_DEFER_APPLY=0 \
  TELEGRAM_SESSION_STRING="$TELEGRAM_SESSION_STRING" \
  TELEGRAM_TARGET_PEER="$PEER" \
  TELEGRAM_OUTBOX_STARTUP_PING=1 \
  PYTHONPATH="$PYTHONPATH" \
  $PY -u bot/runtime_supervisor.py > /tmp/luxury_supervisor.log 2>&1 &
echo "supervisor pid=$!"

echo "========== [4/4] settle 20s =========="
sleep 20
$PY <<'PY'
import subprocess
from pathlib import Path
print("bacbo", subprocess.getoutput("pgrep -fc bacbo_royal_complete.py || echo 0"))
print("supervisor", subprocess.getoutput("pgrep -fc runtime_supervisor.py || echo 0"))
print("outbox", subprocess.getoutput("pgrep -fc telegram_outbox.py || echo 0"))
print("legacy_fb", subprocess.getoutput(
    "pgrep -fc 'fallback_signal_sender.py|fallback_result_sender.py' || echo 0"))
print(Path("/tmp/luxury_supervisor.log").read_text(errors="replace")[-900:])
PY
echo "EXPECT: bacbo=1 supervisor=1 outbox=1 legacy_fb=0 + adopting existing bacbo"
echo "DONE."
