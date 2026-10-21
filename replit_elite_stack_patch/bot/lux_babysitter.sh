#!/usr/bin/env bash
# Keep runtime_supervisor alive after Shell disconnect / stray pkills.
# Does NOT steal Replit PORT (KeepAlive off).
set -u
ROOT="${ROOT:-/home/runner/workspace}"
cd "$ROOT" || exit 1
mkdir -p logs bot/data
LOG=logs/babysitter.log
PY="${PY:-python3}"
echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) babysitter start pid=$$" >>"$LOG"

# Detach from controlling terminal if any
cd "$ROOT" || exit 1
unset PORT REPLIT_SOCKET REPLIT_SOCKETS REPLIT_PORT 2>/dev/null || true
export LUX_KEEPALIVE_OFF=1 LUX_FLASK_GUARD=1 FLASK_DEBUG=0
export FLASK_ENV=production WERKZEUG_RUN_MAIN=true

while true; do
  if ! pgrep -f '[r]untime_supervisor.py' >/dev/null 2>&1; then
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) supervisor missing — starting" >>"$LOG"
    rm -f bot/data/runtime_supervisor.lock 2>/dev/null || true
    # setsid: survive Shell close better than bare nohup on Replit
    setsid "$PY" -u bot/runtime_supervisor.py >>/tmp/luxury_supervisor.log 2>&1 </dev/null &
    sleep 25
  fi
  # If supervisor alive but bacbo missing for too long, poke via supervisor (it restarts)
  if pgrep -f '[r]untime_supervisor.py' >/dev/null 2>&1 \
    && ! pgrep -f '[r]un_bacbo_live.py' >/dev/null 2>&1; then
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) bacbo missing (supervisor will restart)" >>"$LOG"
  fi
  sleep 20
done
