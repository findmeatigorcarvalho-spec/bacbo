#!/usr/bin/env bash
# FINISH — one paste. Restores session, fixes bacbo boot, starts hub, proves live fires.
#
# WHAT WE ARE BUILDING (locked):
#   1) Engine (bacbo) owns ORIGINAL rich signal skins (SEQUÊNCIA 3x / SOLO / GOLDEN …)
#   2) High-trust fires → @UNIQUE_g1 (id 5855678138) via HUB_ENGINE_ROUTE
#   3) Lower-trust / ops → Mr_iv4 (6774605259)
#   4) Outbox does NOT send thin ENTER NOW / BAC BO SIGNAL duplicates
#   5) Outbox startup ping at most once / 6h (no spam)
#
# Those thin "🔥 SEQUÊNCIA — ENTER NOW" + forensic cards were outbox hub cards.
# The repeated "LUXURY OUTBOX ONLINE — GUNIQUE" lines are restart pings while bacbo was dead.
#
# Usage:
#   curl -fsSL -H "Cache-Control: no-cache" -o FINISH.sh \
#     "https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/cursor/add-engine-gate-registry-d5ba/replit_elite_stack_patch/REPLIT_FINISH.sh" \
#     && bash FINISH.sh
set -euo pipefail
cd /home/runner/workspace 2>/dev/null || cd "$(dirname "$0")/.."
PY="${PYTHON:-python3}"
SHA="${LUXURY_PATCH_SHA:-cursor/add-engine-gate-registry-d5ba}"
BASE="https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/${SHA}/replit_elite_stack_patch"

echo "============================================================"
echo " FINISH — original skins → Gunique #1 / money #2"
echo "============================================================"
echo "WANT in @UNIQUE_g1:"
echo "  • rich engine skins (SEQUÊNCIA 3x / SOLO ELITE with janela / GOLDEN …)"
echo "  • NOT thin 'ENTER NOW' hub cards"
echo "  • NOT endless 'OUTBOX ONLINE' pings"
echo

echo "========== [1/5] pull finish helpers =========="
mkdir -p bot/data logs
for rel in \
  bot/fix_tz_utils.py \
  bot/fix_bacbo_state.py \
  bot/hub_engine_route.py \
  bot/lux_send_config_bind.py \
  bot/telegram_outbox.py \
  bot/runtime_supervisor.py \
  bot/hub_max_boot.py \
  bot/hub_dispatch.py \
  REPLIT_DO_IT.sh \
  REPLIT_HUB_MAX.sh \
  REPLIT_ONE_STACK.sh
do
  curl -fsSL -H "Cache-Control: no-cache" -o "$rel" "$BASE/$rel" || echo "skip $rel"
done

echo "========== [2/5] session + tz + state =========="
set -a
# shellcheck disable=SC1091
[ -f .env ] && source ./.env || true
set +a
SESS="$(printf '%s' "${TELEGRAM_SESSION_STRING:-}" | tr -d '\n\r')"
if [ "${#SESS}" -le 50 ] && [ -f .telegram_session_string ]; then
  SESS="$(tr -d '\n\r' < .telegram_session_string)"
fi
if [ "${#SESS}" -le 50 ]; then
  echo "FATAL: set Replit Secret TELEGRAM_SESSION_STRING"
  exit 1
fi
printf '%s\n' "$SESS" > .telegram_session_string
chmod 600 .telegram_session_string 2>/dev/null || true
export TELEGRAM_SESSION_STRING="$SESS"
export TELEGRAM_GUNIQUE_PEER_ID="${TELEGRAM_GUNIQUE_PEER_ID:-5855678138}"
export GUNIQUE_PEER_ID="${GUNIQUE_PEER_ID:-5855678138}"
export HUB_MAX=1
export HUB_ENGINE_ROUTE=1
export HUB_OUTBOX_FIRE_CARDS=0
export HUB_OUTBOX_RESULT_CARDS=0
export TELEGRAM_OUTBOX_STARTUP_PING=1
export TELEGRAM_OUTBOX_PING_MIN_SECS="${TELEGRAM_OUTBOX_PING_MIN_SECS:-21600}"
export TELEGRAM_MIRROR_MONEY_TO_GUNIQUE=0

$PY bot/fix_tz_utils.py
$PY bot/fix_bacbo_state.py

echo "========== [3/5] boot stack (DOIT) =========="
bash REPLIT_DO_IT.sh

echo "========== [4/5] wait for bacbo alive (90s) =========="
ok=0
for i in $(seq 1 18); do
  n="$($PY - <<'PY'
from pathlib import Path
c=0
for p in Path("/proc").iterdir():
    if not p.name.isdigit():
        continue
    try:
        cmd=p.joinpath("cmdline").read_bytes().replace(b"\0",b" ").decode()
    except Exception:
        continue
    if "bacbo_royal_complete.py" in cmd and "python" in cmd.lower() and "REPLIT_" not in cmd:
        c+=1
print(c)
PY
)"
  if [ "$n" = "1" ]; then
    echo "bacbo alive at try $i"
    ok=1
    break
  fi
  echo "waiting bacbo… try $i (count=$n)"
  sleep 5
done

echo "========== [5/5] SUCCESS GATES =========="
$PY - <<'PY'
from pathlib import Path
import time

def cmdline(pid):
    try:
        return Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\0", b" ").decode()
    except Exception:
        return ""

def count(needle):
    n=0
    for p in Path("/proc").iterdir():
        if not p.name.isdigit():
            continue
        cmd=cmdline(int(p.name))
        if needle in cmd and "python" in cmd.lower() and "REPLIT_" not in cmd:
            n+=1
    return n

b,s,o = count("bacbo_royal_complete.py"), count("runtime_supervisor.py"), count("telegram_outbox.py")
print(f"processes: bacbo={b} supervisor={s} outbox={o}")

bl = Path("logs/bot_live.log")
chunk = bl.read_text(encoding="utf-8", errors="replace")[-8000:] if bl.exists() else ""
bad = any(x in chunk for x in (
    "NameError: name 'state'",
    "cannot import name 'local_hour'",
    "Traceback (most recent call last):",
))
# last start marker
alive_hints = any(x in chunk for x in (
    "run_forever",
    "Listening",
    "BootGrace",
    "EdgePolicy",
    "SEQUENCE",
    "FIRED",
    "[HUB-ROUTE]",
    "all imports OK",
))
print("bot_live recent crash?", bad)
print("bot_live shows progress?", alive_hints)
print("--- bot_live last 25 lines ---")
if bl.exists():
    for ln in bl.read_text(encoding="utf-8", errors="replace").splitlines()[-25:]:
        print(ln)

print("--- route / resolve ---")
import subprocess, shlex
cmd = "rg -n 'HUB-ROUTE|Gunique resolve OK|snap fire cursor|NameError|local_hour' logs/bot_live.log logs/telegram_outbox.log 2>/dev/null | tail -30"
print(subprocess.getoutput(cmd))

verdict = (b==1 and s==1 and o==1 and not bad)
print()
print("FINISH_VERDICT", "OK" if verdict else "BAD")
if verdict:
    print("NEXT: open @UNIQUE_g1 — wait for a LIVE rich skin (janela / SEQUÊNCIA 3x / SOLO with steps).")
    print("Ignore thin 'ENTER NOW' hub cards and OUTBOX ONLINE pings.")
    print("Confirm logs show: [HUB-ROUTE] dest=5855678138 reason=trust_skin→gunique")
else:
    print("NEXT: paste FINISH_VERDICT block + bot_live last 25 lines.")
PY

echo
echo "DONE FINISH."
