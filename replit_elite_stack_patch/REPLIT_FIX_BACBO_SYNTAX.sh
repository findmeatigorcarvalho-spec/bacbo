#!/usr/bin/env bash
# Repair bacbo_royal_complete.py SyntaxError (broken try from bad inject).
#   curl -fsSL -o /tmp/FIXSYN.sh \
#     'https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/cursor/add-engine-gate-registry-d5ba/replit_elite_stack_patch/REPLIT_FIX_BACBO_SYNTAX.sh?v=20260807j'
#   bash /tmp/FIXSYN.sh && bash /tmp/LIVE.sh
set -euo pipefail
ROOT="${ROOT:-/home/runner/workspace}"
cd "$ROOT"
BRANCH="${BRANCH:-cursor/add-engine-gate-registry-d5ba}"
RAW="https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/${BRANCH}"
V="20260807j"
PY="${PY:-python3}"

echo "========== FIX bacbo SYNTAX =========="
mkdir -p bot
curl -fsSL -o bot/fix_bacbo_syntax.py \
  "${RAW}/replit_elite_stack_patch/bot/fix_bacbo_syntax.py?v=${V}"
curl -fsSL -o bot/lux_re_harden.py \
  "${RAW}/replit_elite_stack_patch/bot/lux_re_harden.py?v=${V}" || true

$PY -u bot/fix_bacbo_syntax.py
$PY -m py_compile bacbo_royal_complete.py 2>/dev/null \
  || $PY -m py_compile bot/bacbo_royal_complete.py
echo "PY_COMPILE_OK"

pkill -f 'runtime_supervisor.py|bacbo_royal_complete.py|telegram_outbox.py' 2>/dev/null || true
rm -f bot/data/runtime_supervisor.lock bot/data/telegram_outbox.lock 2>/dev/null || true
sleep 1
nohup $PY -u bot/runtime_supervisor.py > /tmp/luxury_supervisor.log 2>&1 &
sleep 28
echo "---- procs ----"
pgrep -af 'runtime_supervisor|telegram_outbox|bacbo_royal' || true
echo "---- bot_live ----"
tail -n 50 logs/bot_live.log 2>/dev/null || true
echo "========== DONE =========="
