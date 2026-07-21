#!/usr/bin/env bash
# Enforce ONE bacbo + ONE supervisor + ONE outbox + ZERO legacy fallbacks.
set -euo pipefail
cd /home/runner/workspace
PY=python3
SHA="${LUXURY_PATCH_SHA:-cursor/add-engine-gate-registry-d5ba}"
BASE="https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/${SHA}/replit_elite_stack_patch"
PEER="${TELEGRAM_TARGET_PEER:-6774605259}"

echo "========== [1/5] refresh supervisor/outbox =========="
mkdir -p bot/data logs
for rel in bot/runtime_supervisor.py bot/telegram_outbox.py bot/lux_floor_rotate.py; do
  curl -fsSL -H "Cache-Control: no-cache" -o "$rel" "$BASE/$rel"
done
$PY -m py_compile bot/runtime_supervisor.py bot/telegram_outbox.py

echo "========== [2/5] HARD RESET (+ clear locks) =========="
for i in 1 2 3 4 5 6 7 8; do
  pkill -9 -f 'runtime_supervisor.py' 2>/dev/null || true
  pkill -9 -f 'telegram_outbox.py' 2>/dev/null || true
  pkill -9 -f 'fallback_signal_sender.py' 2>/dev/null || true
  pkill -9 -f 'fallback_result_sender.py' 2>/dev/null || true
  pkill -9 -f 'bacbo_royal_complete.py' 2>/dev/null || true
  # Also stop common Replit entry duplicates
  pkill -9 -f 'start_luxury.sh' 2>/dev/null || true
  sleep 2
  left=$(pgrep -af 'bacbo_royal_complete|runtime_supervisor|telegram_outbox|fallback_signal|fallback_result' | grep -v pgrep || true)
  if [ -z "$left" ]; then
    echo "clean at pass $i"
    break
  fi
  echo "still alive pass $i:"
  echo "$left"
done
rm -f bot/data/telegram_outbox.lock bot/data/runtime_supervisor.lock 2>/dev/null || true
pgrep -af 'bacbo_royal_complete|runtime_supervisor|telegram_outbox|fallback_' | grep -v pgrep || echo "ALL CLEAR"

echo "========== [3/5] start ONE supervisor =========="
set -a
# shellcheck disable=SC1091
[ -f luxury_building.env ] && source ./luxury_building.env || true
set +a
export TELEGRAM_SESSION_STRING="$(tr -d '\n' < .telegram_session_string)"
export TELEGRAM_TARGET_PEER="$PEER"
export TELEGRAM_SINGLE_OUTBOX=1
export FALLBACKS_ENABLED=1
export FALLBACK_START_DELAY_SECS=20
export LUXURY_TOWER_MERGE=1
export LUXURY_FLOOR_ROTATE_DEFER_APPLY=0
export PYTHONPATH="/home/runner/workspace/bot:/home/runner/workspace:${PYTHONPATH:-}"

nohup env EDGE_POLICY_MODE=luxury EDGE_LUXURY_FLOOR_GATE=1 FALLBACKS_ENABLED=1 \
  TELEGRAM_SINGLE_OUTBOX=1 FALLBACK_START_DELAY_SECS=20 LUXURY_TOWER_MERGE=1 \
  LUXURY_FLOOR_ROTATE=1 LUXURY_FLOOR_ROTATE_MODE=tag LUXURY_FLOOR_ROTATE_DEFER_APPLY=0 \
  TELEGRAM_SESSION_STRING="$TELEGRAM_SESSION_STRING" \
  TELEGRAM_TARGET_PEER="$PEER" \
  TELEGRAM_OUTBOX_STARTUP_PING=1 \
  PYTHONPATH="$PYTHONPATH" \
  $PY -u bot/runtime_supervisor.py > /tmp/luxury_supervisor.log 2>&1 &
SUP_PID=$!
echo "supervisor pid=$SUP_PID"
sleep 3
# If a second supervisor tried to start, flock makes it exit — confirm ours lives
if ! kill -0 "$SUP_PID" 2>/dev/null; then
  echo "WARN supervisor died early — log:"
  cat /tmp/luxury_supervisor.log || true
fi

echo "========== [4/5] settle + prune extras =========="
sleep 25
$PY <<'PY'
import os, signal, subprocess, time

def pids(pat: str) -> list[int]:
    out = subprocess.getoutput(f"pgrep -f '{pat}' || true")
    me = os.getpid()
    return sorted({int(x) for x in out.split() if x.isdigit() and int(x) != me})

def kill_extras(pat: str, keep_n: int = 1) -> list[int]:
    ps = pids(pat)
    if len(ps) <= keep_n:
        return ps
    keep = ps[:keep_n]
    for pid in ps[keep_n:]:
        try:
            os.kill(pid, signal.SIGKILL)
            print("killed_extra", pat, pid)
        except Exception as e:
            print("kill_fail", pat, pid, e)
    time.sleep(1)
    return pids(pat)

# Always wipe legacy dual-fallback
for pat in ("fallback_signal_sender.py", "fallback_result_sender.py"):
    for pid in pids(pat):
        try:
            os.kill(pid, signal.SIGKILL)
            print("killed_legacy", pat, pid)
        except Exception:
            pass

b = kill_extras("bacbo_royal_complete.py", 1)
s = kill_extras("runtime_supervisor.py", 1)
o = kill_extras("telegram_outbox.py", 1)
fb = pids("fallback_signal_sender.py") + pids("fallback_result_sender.py")
print("after_prune bacbo", b, "sup", s, "outbox", o, "legacy", fb)
time.sleep(8)
# second prune pass (respawns)
b = kill_extras("bacbo_royal_complete.py", 1)
s = kill_extras("runtime_supervisor.py", 1)
o = kill_extras("telegram_outbox.py", 1)
for pat in ("fallback_signal_sender.py", "fallback_result_sender.py"):
    for pid in pids(pat):
        try:
            os.kill(pid, signal.SIGKILL)
        except Exception:
            pass
fb = pids("fallback_signal_sender.py") + pids("fallback_result_sender.py")
print("final bacbo", b, "n", len(b))
print("final supervisor", s, "n", len(s))
print("final outbox", o, "n", len(o))
print("final legacy_fb", fb, "n", len(fb))
PY

echo "========== [5/5] verdict =========="
$PY <<'PY'
import subprocess
from pathlib import Path

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
print(Path("/tmp/luxury_supervisor.log").read_text(errors="replace")[-1500:])
ok = len(b) == 1 and len(s) == 1 and len(o) <= 1 and len(fb) == 0
# outbox may still be in FALLBACK_START_DELAY — allow 0 briefly
if len(b) == 1 and len(s) == 1 and len(fb) == 0 and len(o) <= 1:
    ok = True
print("VERDICT", "OK" if ok else "BAD — paste output")
if len(o) == 0:
    print("NOTE: outbox=0 may still be in 20s start delay — wait 30s and pgrep telegram_outbox")
PY
echo "DONE."
