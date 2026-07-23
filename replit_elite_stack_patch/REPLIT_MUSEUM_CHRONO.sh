#!/usr/bin/env bash
# Post next chronological FIRE→RESULT pairs (ALL signals, no timing filter).
# Default: offset=5 limit=5  → pairs #6–#10 after museum first5.
set -euo pipefail
cd /home/runner/workspace 2>/dev/null || cd "$(dirname "$0")/.."
BRANCH="${BACBO_BRANCH:-cursor/add-engine-gate-registry-d5ba}"
BASE="https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/${BRANCH}/replit_elite_stack_patch"
PY="${PYTHON:-python3}"
OFFSET="${MUSEUM_OFFSET:-5}"
LIMIT="${MUSEUM_LIMIT:-5}"
mkdir -p bot/data logs
for rel in bot/museum_chrono_poster.py bot/data/museum_chrono_all_pairs.json; do
  curl -fsSL -H "Cache-Control: no-cache" -o "$rel" "$BASE/$rel" || true
done
$PY -m py_compile bot/museum_chrono_poster.py
export TELEGRAM_TARGET_PEER="${TELEGRAM_TARGET_PEER:-6774605259}"
export MUSEUM_OFFSET="$OFFSET"
export MUSEUM_LIMIT="$LIMIT"
if [ -f .telegram_session_string ]; then
  export TELEGRAM_SESSION_STRING="$(tr -d '\n' < .telegram_session_string)"
fi
echo "========== MUSEUM CHRONO offset=$OFFSET limit=$LIMIT =========="
$PY bot/museum_chrono_poster.py | tee -a logs/museum_chrono.log
echo "Next offset would be $((OFFSET+LIMIT))"
