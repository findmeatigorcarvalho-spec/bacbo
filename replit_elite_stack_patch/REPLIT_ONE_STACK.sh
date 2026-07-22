#!/usr/bin/env bash
# Enforce ONE bacbo + ONE supervisor + ONE outbox + ZERO legacy fallbacks.
# NEVER use pgrep -f for counts: it matches itself and always reports n=2.
set -euo pipefail
cd /home/runner/workspace
PY=python3
SHA="${LUXURY_PATCH_SHA:-cursor/add-engine-gate-registry-d5ba}"
BASE="https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/${SHA}/replit_elite_stack_patch"
PEER="${TELEGRAM_TARGET_PEER:-6774605259}"
CD_PEER="${TELEGRAM_COUNTDOWN_PEER:-${GUNIQUE_PEER:-UNIQUE_g1}}"
CD_PEER="${CD_PEER#@}"

echo "========== [0/5] note =========="
echo "Prior VERDICT BAD was often a false alarm: pgrep -f matches its own cmdline."
echo "This script counts via /proc (python workers only)."
echo "If a REAL second stack keeps appearing, press STOP on Replit Run first."
echo

echo "========== [1/5] refresh supervisor/outbox =========="
mkdir -p bot/data logs
for rel in \
  bot/runtime_supervisor.py \
  bot/telegram_outbox.py \
  bot/lux_floor_rotate.py \
  bot/lux_tower_merge.py \
  bot/dual_lane_router.py \
  bot/zero_miss_ledger.py
do
  curl -fsSL -H "Cache-Control: no-cache" -o "$rel" "$BASE/$rel" || true
done
$PY -m py_compile bot/runtime_supervisor.py bot/telegram_outbox.py bot/dual_lane_router.py bot/lux_tower_merge.py 2>/dev/null || \
  $PY -m py_compile bot/runtime_supervisor.py bot/telegram_outbox.py bot/dual_lane_router.py


if [ -f luxury_building.env ]; then
  grep -q 'TELEGRAM_SINGLE_OUTBOX' luxury_building.env || echo 'export TELEGRAM_SINGLE_OUTBOX=1' >> luxury_building.env
  sed -i 's/^export TELEGRAM_SINGLE_OUTBOX=.*/export TELEGRAM_SINGLE_OUTBOX=1/' luxury_building.env || true
  grep -q 'TELEGRAM_COUNTDOWN_PEER' luxury_building.env || echo "export TELEGRAM_COUNTDOWN_PEER=${CD_PEER}" >> luxury_building.env
  sed -i "s/^export TELEGRAM_COUNTDOWN_PEER=.*/export TELEGRAM_COUNTDOWN_PEER=${CD_PEER}/" luxury_building.env || true
  grep -q 'GUNIQUE_PEER' luxury_building.env || echo "export GUNIQUE_PEER=${CD_PEER}" >> luxury_building.env
  sed -i "s/^export GUNIQUE_PEER=.*/export GUNIQUE_PEER=${CD_PEER}/" luxury_building.env || true
fi

echo "========== [2/5] HARD RESET =========="
for i in 1 2 3 4 5 6 7 8 9 10; do
  pkill -9 -f 'bot/runtime_supervisor.py' 2>/dev/null || true
  pkill -9 -f 'runtime_supervisor.py' 2>/dev/null || true
  pkill -9 -f 'bot/telegram_outbox.py' 2>/dev/null || true
  pkill -9 -f 'telegram_outbox.py' 2>/dev/null || true
  pkill -9 -f 'fallback_signal_sender.py' 2>/dev/null || true
  pkill -9 -f 'fallback_result_sender.py' 2>/dev/null || true
  pkill -9 -f 'bacbo_royal_complete.py' 2>/dev/null || true
  pkill -9 -f 'start_luxury.sh' 2>/dev/null || true
  sleep 2
  left=$($PY - <<'PY'
from pathlib import Path

NEEDLES = (
    "bacbo_royal_complete.py",
    "runtime_supervisor.py",
    "telegram_outbox.py",
    "fallback_signal_sender.py",
    "fallback_result_sender.py",
)

def cmdline(pid: int) -> str:
    try:
        raw = Path(f"/proc/{pid}/cmdline").read_bytes()
    except Exception:
        return ""
    return raw.replace(b"\0", b" ").decode("utf-8", "replace").strip()

rows = []
for p in Path("/proc").iterdir():
    if not p.name.isdigit():
        continue
    cmd = cmdline(int(p.name))
    if not cmd:
        continue
    low = cmd.lower()
    if "python" not in low:
        continue
    if any(n in cmd for n in ("ONE.sh", "REPLIT_ONE_STACK", "pgrep")):
        continue
    if any(n in cmd for n in NEEDLES):
        rows.append(f"{p.name} {cmd[:160]}")
print("\n".join(rows))
PY
)
  if [ -z "$left" ]; then
    echo "clean at pass $i"
    break
  fi
  echo "still alive pass $i:"
  echo "$left"
done
rm -f bot/data/telegram_outbox.lock bot/data/runtime_supervisor.lock 2>/dev/null || true

echo "========== [3/5] start ONE supervisor =========="
set -a
# shellcheck disable=SC1091
[ -f luxury_building.env ] && source ./luxury_building.env || true
set +a
export TELEGRAM_SESSION_STRING="$(tr -d '\n' < .telegram_session_string)"
export TELEGRAM_TARGET_PEER="$PEER"
export TELEGRAM_COUNTDOWN_PEER="$CD_PEER"
export GUNIQUE_PEER="$CD_PEER"
export TELEGRAM_SINGLE_OUTBOX=1
export FALLBACKS_ENABLED=1
export FALLBACK_START_DELAY_SECS=15
export LUXURY_TOWER_MERGE=1
export LUXURY_NO_HOUR_BLOCKS=1
export FALLBACK_SEND_BLOCKED=0
export LUXURY_FLOOR_ROTATE_DEFER_APPLY=0
export PYTHONPATH="/home/runner/workspace/bot:/home/runner/workspace:${PYTHONPATH:-}"

nohup env EDGE_POLICY_MODE=luxury EDGE_LUXURY_FLOOR_GATE=1 FALLBACKS_ENABLED=1 \
  TELEGRAM_SINGLE_OUTBOX=1 FALLBACK_START_DELAY_SECS=15 LUXURY_TOWER_MERGE=1 \
  LUXURY_NO_HOUR_BLOCKS=1 FALLBACK_SEND_BLOCKED=0 \
  LUXURY_FLOOR_ROTATE=1 LUXURY_FLOOR_ROTATE_MODE=tag LUXURY_FLOOR_ROTATE_DEFER_APPLY=0 \
  TELEGRAM_SESSION_STRING="$TELEGRAM_SESSION_STRING" \
  TELEGRAM_TARGET_PEER="$PEER" \
  TELEGRAM_COUNTDOWN_PEER="$CD_PEER" \
  GUNIQUE_PEER="$CD_PEER" \
  TELEGRAM_MIRROR_MONEY_TO_GUNIQUE=1 \
  TELEGRAM_OUTBOX_STARTUP_PING=1 \
  PYTHONPATH="$PYTHONPATH" \
  $PY -u bot/runtime_supervisor.py > /tmp/luxury_supervisor.log 2>&1 &
SUP_PID=$!
echo "supervisor pid=$SUP_PID"
sleep 4
if ! kill -0 "$SUP_PID" 2>/dev/null; then
  echo "FATAL: supervisor died — log:"
  cat /tmp/luxury_supervisor.log || true
  exit 1
fi

echo "========== [4/5] enforce singleton for 50s =========="
$PY <<PY
import os, signal, time
from pathlib import Path

OUR_SUP = $SUP_PID
NEEDLES = {
    "bacbo": "bacbo_royal_complete.py",
    "sup": "runtime_supervisor.py",
    "outbox": "telegram_outbox.py",
    "fb_sig": "fallback_signal_sender.py",
    "fb_res": "fallback_result_sender.py",
}

def cmdline(pid: int) -> str:
    try:
        raw = Path(f"/proc/{pid}/cmdline").read_bytes()
    except Exception:
        return ""
    return raw.replace(b"\0", b" ").decode("utf-8", "replace").strip()

def ppid_of(pid: int) -> int:
    try:
        for line in Path(f"/proc/{pid}/status").read_text().splitlines():
            if line.startswith("PPid:"):
                return int(line.split()[1])
    except Exception:
        pass
    return 0

def list_python(needle: str):
    rows = []
    for p in Path("/proc").iterdir():
        if not p.name.isdigit():
            continue
        pid = int(p.name)
        cmd = cmdline(pid)
        if not cmd or needle not in cmd:
            continue
        low = cmd.lower()
        if "python" not in low:
            continue
        if any(x in cmd for x in ("ONE.sh", "REPLIT_ONE_STACK", "pgrep", "pkill")):
            continue
        rows.append((pid, ppid_of(pid), cmd))
    return sorted(rows)

def kill_pid(pid: int, why: str):
    try:
        os.kill(pid, signal.SIGKILL)
        print(f"killed pid={pid} ({why})")
    except ProcessLookupError:
        pass
    except Exception as e:
        print(f"kill_fail pid={pid} {e}")

deadline = time.time() + 50
while time.time() < deadline:
    for pid, ppid, args in list_python(NEEDLES["sup"]):
        if pid != OUR_SUP:
            kill_pid(pid, f"extra supervisor ppid={ppid}")

    for key in ("fb_sig", "fb_res"):
        for pid, ppid, args in list_python(NEEDLES[key]):
            kill_pid(pid, f"legacy {key} ppid={ppid}")

    bacbos = list_python(NEEDLES["bacbo"])
    if len(bacbos) > 1:
        keep = bacbos[0][0]
        for pid, ppid, args in bacbos[1:]:
            kill_pid(pid, f"extra bacbo keep={keep} ppid={ppid}")

    outs = list_python(NEEDLES["outbox"])
    if len(outs) > 1:
        keep = outs[0][0]
        for pid, ppid, args in outs[1:]:
            kill_pid(pid, f"extra outbox keep={keep} ppid={ppid}")

    time.sleep(3)

print("--- final process table ---")
for label, needle in NEEDLES.items():
    rows = list_python(needle)
    print(f"{label}: {len(rows)}")
    for pid, ppid, args in rows:
        print(f"  pid={pid} ppid={ppid} {args[:140]}")

b = list_python(NEEDLES["bacbo"])
s = list_python(NEEDLES["sup"])
o = list_python(NEEDLES["outbox"])
fb = list_python(NEEDLES["fb_sig"]) + list_python(NEEDLES["fb_res"])
ok = len(b) == 1 and len(s) == 1 and len(o) == 1 and len(fb) == 0 and s[0][0] == OUR_SUP
print("VERDICT", "OK" if ok else "BAD")
if not ok:
    print("If BAD with real duplicate cmdlines above: STOP Replit Run, wait 5s, re-run ONE.sh")
    for pid, ppid, args in b + s + o + fb:
        parent = cmdline(ppid) or f"(ppid={ppid} gone)"
        print(f"  parent_of {pid}: {parent[:140]}")
PY

echo "========== [5/5] supervisor log =========="
tail -n 40 /tmp/luxury_supervisor.log || true
echo "DONE."
