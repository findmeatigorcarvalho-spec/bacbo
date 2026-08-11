#!/usr/bin/env bash
# Safe museum review lane: cannot reuse the live bacbo StringSession.
#
# Required once (a new StringSession; it may be the same Telegram account as
# live bacbo, but must never be the same StringSession):
#   export MUSEUM_TELEGRAM_SESSION_STRING='...'
#   export MUSEUM_TELEGRAM_API_ID='...'
#   export MUSEUM_TELEGRAM_API_HASH='...'
#
# It posts ONLY to UNIQUE_museum_chrono. It neither stops bacbo nor reads
# .telegram_session_string, so UNIQUE_g1 can remain running.
set -euo pipefail

cd /home/runner/workspace 2>/dev/null || cd "$(dirname "$0")/.."

REF="${BACBO_REF:-cursor/add-engine-gate-registry-d5ba}"
RAW="https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/${REF}/replit_elite_stack_patch"
VER="20260811d"
MODE="${MUSEUM_REVIEW_MODE:-ledger}" # ledger, fires, types, or pairs
LIMIT="${MUSEUM_LIMIT:-20}"
OFFSET="${MUSEUM_OFFSET:-0}"

require() {
  local key="$1"
  if [[ -z "${!key:-}" ]]; then
    echo "MISSING_${key} — refusing to fall back to the live bacbo session" >&2
    exit 2
  fi
}

mkdir -p bot/data logs
for rel in \
  bot/museum_unique_poster.py \
  bot/museum_chrono_poster.py \
  bot/build_signal_ledger.py \
  bot/data/museum_full_catalog.json \
  bot/data/museum_chrono_all_pairs.json \
  bot/data/museum_triage_keep_trash.json; do
  curl -fsSL -o "$rel" "${RAW}/${rel}?v=${VER}"
done

python3 -m py_compile bot/museum_unique_poster.py bot/museum_chrono_poster.py bot/build_signal_ledger.py
python3 bot/build_signal_ledger.py

# `ledger` is offline and safe to run before a dedicated museum account exists.
if [[ "$MODE" == "ledger" ]]; then
  echo "SIGNAL_LEDGER_READY bot/data/SIGNAL_LEDGER_REVIEW.md"
  echo "No Telegram session used; UNIQUE_g1 is untouched."
  exit 0
fi

require MUSEUM_TELEGRAM_SESSION_STRING
require MUSEUM_TELEGRAM_API_ID
require MUSEUM_TELEGRAM_API_HASH

# Do not export/read TELEGRAM_SESSION_STRING or the normal API variables.
# The poster has a separate-only guard, then accepts this explicit museum identity.
export MUSEUM_REQUIRE_SEPARATE_SESSION=1
export MUSEUM_PEER="${MUSEUM_PEER:-UNIQUE_museum_chrono}"
export MUSEUM_LIMIT="$LIMIT"
export MUSEUM_OFFSET="$OFFSET"
export MUSEUM_SLEEP_FIRE="${MUSEUM_SLEEP_FIRE:-2.0}"
export MUSEUM_SLEEP_RESULT="${MUSEUM_SLEEP_RESULT:-1.2}"
export MUSEUM_SLEEP_ITEM="${MUSEUM_SLEEP_ITEM:-2.5}"
export MUSEUM_TELEGRAM_TARGET_PEER="${MUSEUM_TELEGRAM_TARGET_PEER:-UNIQUE_museum_chrono}"

echo "MUSEUM_SAFE_LANE mode=${MODE} peer=${MUSEUM_PEER} offset=${OFFSET} limit=${LIMIT}"
echo "Live bacbo is not stopped or contacted."
if [[ "$MODE" == "fires" ]]; then
  unset MUSEUM_ROLE_FILTER
  export MUSEUM_CANONICAL_ROLE_FILTER="FIRE"
  export MUSEUM_PROGRESS_NAMESPACE="fires-review"
  python3 -u bot/museum_unique_poster.py | tee -a logs/museum_review_fires.log
elif [[ "$MODE" == "types" ]]; then
  export MUSEUM_PROGRESS_NAMESPACE="types-review"
  python3 -u bot/museum_unique_poster.py | tee -a logs/museum_review_types.log
elif [[ "$MODE" == "pairs" ]]; then
  python3 -u bot/museum_chrono_poster.py | tee -a logs/museum_review_pairs.log
else
  echo "Unknown MUSEUM_REVIEW_MODE=${MODE}; use ledger, fires, types, or pairs" >&2
  exit 2
fi
