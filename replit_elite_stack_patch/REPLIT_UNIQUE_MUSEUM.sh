#!/usr/bin/env bash
# Create UNIQUE_museum_chrono and paced-post skins in FIRST EXISTENCE order.
# 1st skin ever fired/built → example #1 · 2nd → #2 · …
# Never-fired code skins still appear (after dated ones, registry order).
# Does NOT touch Mr_iv4 / UNIQUE_g1 money lanes.
#
#   curl -fsSL -o /tmp/MUSEUM.sh \
#     'https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/cursor/add-engine-gate-registry-d5ba/replit_elite_stack_patch/REPLIT_UNIQUE_MUSEUM.sh?v=20260804g'
#   MUSEUM_RESET=1 MUSEUM_LIMIT=5 bash /tmp/MUSEUM.sh   # smoke into NEW chrono chat
#   bash /tmp/MUSEUM.sh                                  # full (resumes)
#
# If a previous run wrongly posted into UNIQUE_museum, reset:
#   MUSEUM_RESET=1 bash /tmp/MUSEUM.sh
set -euo pipefail
cd /home/runner/workspace 2>/dev/null || cd "$(pwd)"

REF="${BACBO_REF:-cursor/add-engine-gate-registry-d5ba}"
RAW="https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/${REF}/replit_elite_stack_patch"
VER="20260804g"

echo "UNIQUE_MUSEUM cwd=$(pwd) ref=${REF}"
echo "AXIS: CHRONO_FIRST_EXISTENCE — 1st skin ever → #1, 2nd → #2, …"
echo "NOTE: Creates/uses UNIQUE_museum_chrono ONLY (never aliases to UNIQUE_museum)."
echo "RULE: RESULT under FIRE only if that historical signal originally had one."

mkdir -p bot/data logs
curl -fsSL -o bot/museum_unique_poster.py \
  "${RAW}/bot/museum_unique_poster.py?v=${VER}"
curl -fsSL -o bot/data/museum_full_catalog.json \
  "${RAW}/bot/data/museum_full_catalog.json?v=${VER}"

# Drop legacy shared cache so old UNIQUE_museum id cannot hijack chrono.
rm -f bot/data/telegram_museum_entity.json

# shellcheck disable=SC1091
[[ -f .env ]] && set -a && source ./.env && set +a || true
if [[ -f .telegram_session_string ]]; then
  export TELEGRAM_SESSION_STRING="$(tr -d '\n\r' < .telegram_session_string)"
fi

export MUSEUM_PEER="${MUSEUM_PEER:-UNIQUE_museum_chrono}"
export MUSEUM_USERNAME="${MUSEUM_USERNAME:-UNIQUE_museum_chrono}"
export MUSEUM_SLEEP_FIRE="${MUSEUM_SLEEP_FIRE:-2.0}"
export MUSEUM_SLEEP_RESULT="${MUSEUM_SLEEP_RESULT:-1.2}"
export MUSEUM_SLEEP_ITEM="${MUSEUM_SLEEP_ITEM:-2.5}"

python3 -m py_compile bot/museum_unique_poster.py
echo "========== UNIQUE_museum_chrono (first existence order) =========="
python3 - <<'PY'
import json
p=json.load(open('bot/data/museum_full_catalog.json'))
print('axis=', p.get('axis'))
print('stats=', p.get('stats'))
print('first5=')
for it in (p.get('items') or [])[:5]:
    print(' ', it.get('chrono_order'), it.get('existence_at') or 'NEVER', it.get('family_id'))
print('starting poster (resolving chat may take a few seconds) …')
PY
python3 bot/museum_unique_poster.py | tee -a logs/museum_unique.log
echo "Done. Open the UNIQUE_museum_chrono chat in Telegram."
echo "Progress: bot/data/museum_progress_UNIQUE_museum_chrono.json (resume-safe)"
