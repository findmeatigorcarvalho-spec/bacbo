#!/usr/bin/env bash
# ONE paste: force luxury MODE, restart supervisor, print EdgePolicy lines.
set -euo pipefail
cd /home/runner/workspace

cat > luxury_building.env <<'EOF'
export EDGE_POLICY_MODE=luxury
export EDGE_LUXURY_FLOOR_GATE=1
export FALLBACK_SEND_BLOCKED=0
EOF
# shell + .env
set -a
# shellcheck disable=SC1091
source ./luxury_building.env
set +a
export EDGE_POLICY_MODE=luxury EDGE_LUXURY_FLOOR_GATE=1 FALLBACK_SEND_BLOCKED=0

if [ -f .env ]; then
  sed -i '/^EDGE_POLICY_MODE=/d;/^EDGE_LUXURY_FLOOR_GATE=/d;/^FALLBACK_SEND_BLOCKED=/d' .env || true
fi
cat >> .env <<'EOF'
EDGE_POLICY_MODE=luxury
EDGE_LUXURY_FLOOR_GATE=1
FALLBACK_SEND_BLOCKED=0
EOF

echo "shell MODE=$EDGE_POLICY_MODE"

pkill -f 'runtime_supervisor.py' 2>/dev/null || true
pkill -f 'bacbo_royal_complete.py' 2>/dev/null || true
sleep 1

mkdir -p logs
nohup env EDGE_POLICY_MODE=luxury EDGE_LUXURY_FLOOR_GATE=1 FALLBACK_SEND_BLOCKED=0 \
  python3 -u bot/runtime_supervisor.py > /tmp/luxury_supervisor.log 2>&1 &
echo "supervisor pid=$!"
sleep 3

echo "===== PROCS ====="
pgrep -af 'runtime_supervisor|bot_live|fallback_' || echo "(no procs)"

echo "===== EDGE / ALLOW (last 50) ====="
grep -E 'EdgePolicy|EDGE_LUXURY|DENY_FLOOR|ALLOW|FLOOR_BLOCKED|JUN12' \
  /tmp/luxury_supervisor.log logs/*.log 2>/dev/null | tail -n 50 || echo "(no EdgePolicy lines yet)"

echo "===== SUPERVISOR TAIL ====="
tail -n 40 /tmp/luxury_supervisor.log || true

echo
echo "DONE. Paste this whole block back to Cursor."
echo "If empty EdgePolicy lines: wait ~1-2 min for a signal cycle, re-run: bash REPLIT_LUXURY_FIRE_NOW.sh"
