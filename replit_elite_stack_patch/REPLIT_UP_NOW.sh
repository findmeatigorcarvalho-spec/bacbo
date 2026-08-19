#!/usr/bin/env bash
# Instant bring-up after a crash — heals state + picks the real DB, then starts
# babysitter/supervisor. Use when pgrep is empty.
#   curl -fsSL -o /tmp/UP.sh \
#     'https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/cursor/add-engine-gate-registry-d5ba/replit_elite_stack_patch/REPLIT_UP_NOW.sh?v=20260819e'
#   bash /tmp/UP.sh
set -euo pipefail
ROOT="${ROOT:-/home/runner/workspace}"
cd "$ROOT"
PY="${PY:-python3}"
BRANCH="${BRANCH:-cursor/add-engine-gate-registry-d5ba}"
RAW="https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/${BRANCH}/replit_elite_stack_patch"
V="20260819e"
mkdir -p logs bot/data

unset PORT REPLIT_SOCKET REPLIT_SOCKETS REPLIT_PORT 2>/dev/null || true
export LUX_KEEPALIVE_OFF=1 LUX_FLASK_GUARD=1 FLASK_DEBUG=0
export LUX_CHAT_WATCHDOG=1 LUX_BLOCK_ESTUDO=1
export LUX_G2_COALITION_TO_G1=1
export LUX_FREE_VOLUME=1
export FREE_PROPOSE=1
export VOLUME_MODE=EXPLOSION
export EDGE_LUXURY_FLOOR_GATE=0
export ROLLING_WR_MUTE_SECS=0
export HUB_GUNIQUE_TRUST_MIN=0
export LUX_SEND_DEDUP_SECS=12
export LUX_CHAT_WATCH_CALL=0 LUX_CHAT_WATCH_CALL_AFTER_SETTLE=1
export FLASK_ENV=production WERKZEUG_RUN_MAIN=true

echo "========== UP NOW ${V} =========="
echo "-- pull heal/db/g2 (small; does not clobber state.py) --"
for rel in bot/lux_state_heal.py bot/lux_live_db.py bot/g2_coalition.py bot/lux_free_volume.py bot/lux_send_config_bind.py bot/telegram_outbox.py bot/hub_dispatch.py bot/hub_max_boot.py; do
  if curl -fsSL --connect-timeout 20 --max-time 90 -o "$rel" "${RAW}/${rel}?v=${V}"; then
    echo "  OK $rel"
  else
    echo "  FAIL $rel"
  fi
done

if [[ -f bot/lux_state_heal.py ]]; then
  echo "-- heal state.py --"
  $PY -u bot/lux_state_heal.py || true
  $PY -m py_compile bot/state.py
fi
if [[ -f bot/lux_live_db.py ]]; then
  echo "-- live DB probe --"
  $PY -u bot/lux_live_db.py || true
fi
if [[ -f bot/lux_free_volume.py ]]; then
  echo "-- free-volume --"
  $PY -u bot/lux_free_volume.py || true
fi

# Soft clear only bot/outbox — leave babysitter if we will restart supervisor
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

echo "-- wait 90s for bacbo --"
for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18; do
  if pgrep -f '[r]un_bacbo_live.py' >/dev/null 2>&1; then
    echo "BACBO_UP t=$((i * 5))s"
    pgrep -af 'lux_babysitter|runtime_supervisor|run_bacbo_live' || true
    echo "---- last log ----"
    tail -n 20 logs/bot_live.log || true
    exit 0
  fi
  sleep 5
done
echo "BACBO_PENDING — supervisor may still be settling"
pgrep -af 'lux_babysitter|runtime_supervisor|run_bacbo_live' || true
echo "---- supervisor ----"
tail -n 30 /tmp/luxury_supervisor.log 2>/dev/null || true
echo "---- bot_live ----"
tail -n 30 logs/bot_live.log || true
exit 1
