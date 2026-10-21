#!/usr/bin/env bash
# Surgical: fix NameError state — do NOT wipe other fixes.
set -euo pipefail
cd /home/runner/workspace

python3 - <<'PY'
from pathlib import Path
import ast, re

p = Path("bacbo_royal_complete.py")
src = p.read_text(encoding="utf-8", errors="replace")
lines = src.splitlines(True)

# Show context around first state.engine / state.client
for i, ln in enumerate(lines):
    if "state.engine" in ln or (ln.startswith("state.client") or "state.client =" in ln):
        if i < 320:
            a, b = max(0, i - 25), min(len(lines), i + 5)
            print(f"----- context {a+1}-{b} -----")
            for j in range(a, b):
                print(f"{j+1}: {lines[j].rstrip()[:160]}")
            print()
            if "state.engine" in ln:
                break

# Ensure after LUXURY_SESSION_AND_BIND (or before first state.XXX at boot) we have:
#   import state
#   state = state  # module
# Strategy: find first occurrence of `state.engine = ConsensusEngine` at module level
idx = None
for i, ln in enumerate(lines):
    if re.match(r"^state\.engine\s*=", ln):
        idx = i
        break
if idx is None:
    for i, ln in enumerate(lines):
        if "state.engine = ConsensusEngine" in ln:
            idx = i
            break
if idx is None:
    raise SystemExit("cannot find state.engine assign")

# Look backward for state = _lux_state_mod or import state
window = "".join(lines[max(0, idx - 40) : idx])
print("has state=_lux in window", "state = _lux_state_mod" in window)
print("has import state in window", bool(re.search(r"^import state\b", window, re.M)))

# Insert FORCE block immediately before state.engine
force = (
    "# --- LUXURY_STATE_NAME_FORCE (auto) ---\n"
    "import state as _lux_state_mod\n"
    "state = _lux_state_mod  # bare name for state.engine / state.learner / ...\n"
    "# --- end LUXURY_STATE_NAME_FORCE ---\n"
)
# Remove prior force blocks to avoid dupes
src2 = re.sub(
    r"\n# --- LUXURY_STATE_NAME_FORCE \(auto\) ---.*?--- end LUXURY_STATE_NAME_FORCE ---\n",
    "\n",
    src,
    flags=re.S,
)
lines = src2.splitlines(True)
idx = next(i for i, ln in enumerate(lines) if re.match(r"^state\.engine\s*=", ln) or "state.engine = ConsensusEngine" in ln)
# Also fix SESSION_AND_BIND to include state= if present but missing assignment
text = "".join(lines)
if "LUXURY_SESSION_AND_BIND" in text and "state = _lux_state_mod" not in text.split("LUXURY_SESSION_AND_BIND", 1)[1][:800]:
    text = text.replace(
        "print(\"[LUXURY] proxy bind failed:\", _lux_bind_exc)\n# --- end LUXURY_SESSION_AND_BIND ---",
        "print(\"[LUXURY] proxy bind failed:\", _lux_bind_exc)\nstate = _lux_state_mod\n# --- end LUXURY_SESSION_AND_BIND ---",
    )
    text = text.replace(
        "print('[LUXURY] proxy bind failed:', _lux_bind_exc)\n# --- end LUXURY_SESSION_AND_BIND ---",
        "print('[LUXURY] proxy bind failed:', _lux_bind_exc)\nstate = _lux_state_mod\n# --- end LUXURY_SESSION_AND_BIND ---",
    )
    lines = text.splitlines(True)
    idx = next(i for i, ln in enumerate(lines) if re.match(r"^state\.engine\s*=", ln) or "state.engine = ConsensusEngine" in ln)

lines.insert(idx, force)
src3 = "".join(lines)
ast.parse(src3)
p.write_text(src3, encoding="utf-8")
print("WROTE state name force before line", idx + 1)

# verify
lines = p.read_text().splitlines()
for i, ln in enumerate(lines):
    if "state.engine = ConsensusEngine" in ln:
        for j in range(max(0, i - 8), i + 2):
            print(f"{j+1}: {lines[j][:140]}")
        break
PY

echo "========== restart bot only =========="
pkill -9 -f 'bacbo_royal_complete.py' 2>/dev/null || true
pkill -9 -f 'runtime_supervisor.py' 2>/dev/null || true
pkill -9 -f 'fallback_signal_sender.py' 2>/dev/null || true
pkill -9 -f 'fallback_result_sender.py' 2>/dev/null || true
sleep 2

set -a; source ./luxury_building.env; set +a
export TELEGRAM_SESSION_STRING="$(tr -d '\n' < .telegram_session_string)"
export TELEGRAM_TARGET_PEER=6774605259

nohup env EDGE_POLICY_MODE=luxury EDGE_LUXURY_FLOOR_GATE=1 FALLBACK_SEND_BLOCKED=0 \
  BOT_TZ=America/Sao_Paulo \
  TELEGRAM_SESSION_STRING="$TELEGRAM_SESSION_STRING" \
  TELEGRAM_TARGET_PEER=6774605259 \
  python3 -u bot/runtime_supervisor.py > /tmp/luxury_supervisor.log 2>&1 &
echo "supervisor pid=$!"
sleep 14

echo "===== procs ====="
pgrep -af 'runtime_supervisor|bacbo_royal|fallback_signal|fallback_result' || true
echo "===== bot tail ====="
tail -n 45 logs/bot_live.log
echo "===== errors ====="
grep -E 'NameError|run_forever|BootGrace|GameCoach|rooms failed|InputPeer|ResolveUsername' logs/bot_live.log | tail -n 30

python3 - <<'PY'
import time, subprocess
time.sleep(4)
print(subprocess.getoutput('pgrep -af bacbo_royal || echo NO_BACBO'))
print('--- last 20 ---')
print(subprocess.getoutput('tail -n 20 logs/bot_live.log'))
PY

echo
echo "DONE. Paste ALL output."
