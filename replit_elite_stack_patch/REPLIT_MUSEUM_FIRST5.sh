#!/usr/bin/env bash
# Post first 5 historical FIRE→RESULT museum pairs to Mr_iv4.
# Run on Replit (has Telethon session). Cloud agent cannot send without session.
set -euo pipefail
cd /home/runner/workspace 2>/dev/null || cd "$(dirname "$0")/.."
BRANCH="${BACBO_BRANCH:-cursor/add-engine-gate-registry-d5ba}"
BASE="https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/${BRANCH}/replit_elite_stack_patch"
PY="${PYTHON:-python3}"
mkdir -p bot/data logs
for rel in bot/museum_first5_poster.py bot/data/museum_first5_fire_result.json; do
  curl -fsSL -H "Cache-Control: no-cache" -o "$rel" "$BASE/$rel" || true
done
$PY -m py_compile bot/museum_first5_poster.py
export TELEGRAM_TARGET_PEER="${TELEGRAM_TARGET_PEER:-6774605259}"
if [ -f .telegram_session_string ]; then
  export TELEGRAM_SESSION_STRING="$(tr -d '\n' < .telegram_session_string)"
fi
echo "========== MUSEUM FIRST5 → Mr_iv4 =========="
$PY bot/museum_first5_poster.py | tee -a logs/museum_first5.log
echo "Done. Check Mr_iv4 for 🏛 MUSEUM #1/5 … #5/5 fire+result."
