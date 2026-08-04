#!/usr/bin/env bash
# Create UNIQUE_museum (if needed) and paced-post every product skin + follow-ups.
# Does NOT touch Mr_iv4 / UNIQUE_g1 money lanes.
#
#   curl -fsSL -o /tmp/MUSEUM.sh \
#     'https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/cursor/add-engine-gate-registry-d5ba/replit_elite_stack_patch/REPLIT_UNIQUE_MUSEUM.sh?v=20260804e'
#   bash /tmp/MUSEUM.sh
#
# Resume after Ctrl+C / FloodWait:
#   bash /tmp/MUSEUM.sh
#
# Optional: MUSEUM_LIMIT=5 bash /tmp/MUSEUM.sh   # smoke test first 5 fires
set -euo pipefail
cd /home/runner/workspace 2>/dev/null || cd "$(pwd)"

REF="${BACBO_REF:-cursor/add-engine-gate-registry-d5ba}"
RAW="https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/${REF}/replit_elite_stack_patch"
VER="20260804e"

echo "UNIQUE_MUSEUM cwd=$(pwd) ref=${REF}"
echo "NOTE: UNIQUE_g2…g5 were never created as Telegram chats — only router names."
echo "      This creates/uses UNIQUE_museum for the paced catalog."
echo "RULE: RESULT under FIRE only if that historical signal originally had one."

mkdir -p bot/data logs
curl -fsSL -o bot/museum_unique_poster.py \
  "${RAW}/bot/museum_unique_poster.py?v=${VER}"
curl -fsSL -o bot/data/museum_full_catalog.json \
  "${RAW}/bot/data/museum_full_catalog.json?v=${VER}"

# shellcheck disable=SC1091
[[ -f .env ]] && set -a && source ./.env && set +a || true
if [[ -f .telegram_session_string ]]; then
  export TELEGRAM_SESSION_STRING="$(tr -d '\n\r' < .telegram_session_string)"
fi

export MUSEUM_PEER="${MUSEUM_PEER:-UNIQUE_museum}"
export MUSEUM_USERNAME="${MUSEUM_USERNAME:-UNIQUE_museum}"
export MUSEUM_SLEEP_FIRE="${MUSEUM_SLEEP_FIRE:-2.0}"
export MUSEUM_SLEEP_RESULT="${MUSEUM_SLEEP_RESULT:-1.2}"
export MUSEUM_SLEEP_ITEM="${MUSEUM_SLEEP_ITEM:-2.5}"

python3 -m py_compile bot/museum_unique_poster.py
echo "========== UNIQUE_museum paced catalog =========="
python3 bot/museum_unique_poster.py | tee -a logs/museum_unique.log
echo "Done. Open the UNIQUE_museum chat in Telegram."
echo "Entity cache: bot/data/telegram_museum_entity.json"
echo "Progress: bot/data/museum_unique_progress.json (resume-safe)"
