#!/usr/bin/env bash
# UNIQUE_museum_chrono — every distinct Telegram-bound template (final triage)
#
# Rule: if it was built/taught/shadowed to reach Telegram → one example.
# SOLO/GOLDEN/etc. are just kinds — not buckets that swallow other skins.
#
# Resume (default — do NOT reset if already mid-parade):
#   # STOP live bacbo first OR use a second session — never AuthKey-war the money bot.
#   pkill -f 'run_bacbo_live|runtime_supervisor' || true; sleep 35
#   curl -fsSL -o /tmp/MUSEUM.sh \
#     'https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/cursor/add-engine-gate-registry-d5ba/replit_elite_stack_patch/REPLIT_UNIQUE_MUSEUM.sh?v=20260809d'
#   bash /tmp/MUSEUM.sh
#
# Only if you need a clean redo:
#   MUSEUM_RESET=1 bash /tmp/MUSEUM.sh
#
# Batch sample first (recommended):
#   MUSEUM_LIMIT=40 MUSEUM_OFFSET=0 bash /tmp/MUSEUM.sh
set -euo pipefail
cd /home/runner/workspace 2>/dev/null || cd "$(pwd)"

REF="${BACBO_REF:-cursor/add-engine-gate-registry-d5ba}"
RAW="https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/${REF}/replit_elite_stack_patch"
VER="20260809d"

echo "UNIQUE_MUSEUM cwd=$(pwd) ref=${REF}"
echo "AXIS: CHRONO_EVERYTHING_EXISTENCE — fingerprint-first (every template)"
echo "RULE: Telegram-bound = signal. Collapse only @room/date/N — not SOLO/GOLDEN buckets."
echo "GOAL: never lose a type that could be valuable in the new result system."

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

export MUSEUM_PEER="${MUSEUM_PEER:-UNIQUE_museum_chrono}"
export MUSEUM_USERNAME="${MUSEUM_USERNAME:-UNIQUE_museum_chrono}"
export MUSEUM_SLEEP_FIRE="${MUSEUM_SLEEP_FIRE:-2.0}"
export MUSEUM_SLEEP_RESULT="${MUSEUM_SLEEP_RESULT:-1.2}"
export MUSEUM_SLEEP_ITEM="${MUSEUM_SLEEP_ITEM:-2.5}"

python3 -m py_compile bot/museum_unique_poster.py
echo "========== UNIQUE_museum_chrono EVERYTHING =========="
python3 - <<'PY'
import json
from pathlib import Path
p=json.load(open('bot/data/museum_full_catalog.json'))
print('axis=', p.get('axis'))
print('stats=', p.get('stats'))
prog=Path('bot/data/museum_progress_UNIQUE_museum_chrono.json')
if prog.exists():
    g=json.load(open(prog))
    print('resume: already_done=', len(g.get('done_family_ids') or []), 'sent=', g.get('sent'))
else:
    print('resume: no progress file (starts from #1)')
print('first5 labels=')
for it in (p.get('items') or [])[:5]:
    print(' ', it.get('chrono_order'), it.get('existence_at') or 'NEVER', (it.get('label') or '')[:60])
print('starting poster (connecting…) …')
PY
python3 -u bot/museum_unique_poster.py | tee -a logs/museum_unique.log
echo "Done. Open @UNIQUE_museum_chrono — triage trash vs profit."
echo "Re-run WITHOUT MUSEUM_RESET to resume after Ctrl+C / FloodWait."
