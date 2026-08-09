#!/usr/bin/env bash
# Instant bring-up — no full pull. Use when pgrep is empty.
#   bash <(curl -fsSL 'https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/cursor/add-engine-gate-registry-d5ba/replit_elite_stack_patch/REPLIT_UP_NOW.sh?v=20260808w')
set -euo pipefail
ROOT="${ROOT:-/home/runner/workspace}"
cd "$ROOT"
PY="${PY:-python3}"
mkdir -p logs bot/data

unset PORT REPLIT_SOCKET REPLIT_SOCKETS REPLIT_PORT 2>/dev/null || true
export LUX_KEEPALIVE_OFF=1 LUX_FLASK_GUARD=1 FLASK_DEBUG=0
export LUX_CHAT_WATCHDOG=1 LUX_BLOCK_ESTUDO=1
export LUX_CHAT_WATCH_CALL=0 LUX_CHAT_WATCH_CALL_AFTER_SETTLE=1
export FLASK_ENV=production WERKZEUG_RUN_MAIN=true

# Soft clear only bot/outbox — leave babysitter alone
pkill -TERM -f 'runtime_supervisor.py|run_bacbo_live.py|telegram_outbox.py' 2>/dev/null || true
sleep 4
pkill -KILL -f 'runtime_supervisor.py|run_bacbo_live.py|telegram_outbox.py' 2>/dev/null || true
rm -f bot/data/runtime_supervisor.lock bot/data/telegram_outbox.lock 2>/dev/null || true
echo "-- AuthKey settle 20s --"
sleep 20

if ! pgrep -f '[l]ux_babysitter.sh' >/dev/null 2>&1; then
  if [[ -f bot/lux_babysitter.sh ]]; then
    chmod +x bot/lux_babysitter.sh
    setsid bash bot/lux_babysitter.sh >>logs/babysitter.log 2>&1 </dev/null &
    echo "babysitter started"
  fi
fi

if ! pgrep -f '[r]untime_supervisor.py' >/dev/null 2>&1; then
  setsid "$PY" -u bot/runtime_supervisor.py >>/tmp/luxury_supervisor.log 2>&1 </dev/null &
  echo "supervisor started pid=$!"
fi

echo "-- wait 70s for bacbo --"
for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14; do
  if pgrep -f '[r]un_bacbo_live.py' >/dev/null 2>&1; then
    echo "BACBO_UP t=$((i * 5))s"
    pgrep -af 'lux_babysitter|runtime_supervisor|run_bacbo_live' || true
    exit 0
  fi
  sleep 5
done
echo "BACBO_PENDING — supervisor may still be settling"
pgrep -af 'lux_babysitter|runtime_supervisor|run_bacbo_live' || true
exit 1
