#!/usr/bin/env bash
# Profit Skyscraper OS — apply KEEP allowlist + money-first Mr_iv4 + never-delay spill.
# Run on the live Replit bot workspace.
#
#   curl -fsSL -o /tmp/SKY.sh \
#     'https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/cursor/add-engine-gate-registry-d5ba/replit_elite_stack_patch/REPLIT_PROFIT_SKYSCRAPER.sh?v=20260806a'
#   bash /tmp/SKY.sh
set -euo pipefail
ROOT="${ROOT:-/home/runner/workspace}"
cd "$ROOT"
PY="${PY:-python3}"
BRANCH="${BRANCH:-cursor/add-engine-gate-registry-d5ba}"
RAW="https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/${BRANCH}"

echo "========== PROFIT SKYSCRAPER OS =========="
mkdir -p bot/config bot/data logs

# Config brain modules
for f in keep_allowlist.py profit_skyscraper.py skin_gate.py; do
  curl -fsSL -o "bot/config/${f}" "${RAW}/bot/config/${f}?v=20260806a" || true
done
# Also pull chat router/shelves if missing
for f in chat_router.py chat_shelves.py skin_families.py registry.py; do
  if [[ ! -f "bot/config/${f}" ]]; then
    curl -fsSL -o "bot/config/${f}" "${RAW}/bot/config/${f}?v=20260806a" || true
  fi
done

# Patch runtime modules
for f in hub_engine_route.py telegram_outbox.py chat_router.py chat_shelves.py skin_gate.py \
         lux_send_config_bind.py window_packer.py round_sync_densifier.py human_return_path.py \
         literally_everything_return.py factual_card_contract.py runtime_supervisor.py \
         build_profit_skyscraper_brain.py triage_museum_keep_trash.py; do
  curl -fsSL -o "bot/${f}" \
    "${RAW}/replit_elite_stack_patch/bot/${f}?v=20260806e" || true
done

# Data: triage + allowlist + playbook (from repo)
mkdir -p bot/data
for f in museum_triage_keep_trash.json keep_allowlist.json profit_skyscraper_brain.json \
         chat_playbook_cards.json CHAT_PROFIT_PLAYBOOK.md museum_full_catalog.json; do
  curl -fsSL -o "bot/data/${f}" \
    "${RAW}/replit_elite_stack_patch/bot/data/${f}?v=20260806a" || true
done

# Rebuild brain locally if triage present
if [[ -f bot/data/museum_triage_keep_trash.json ]]; then
  $PY bot/build_profit_skyscraper_brain.py || $PY - <<'PY'
import runpy
runpy.run_path("bot/build_profit_skyscraper_brain.py", run_name="__main__")
PY
fi

# Runtime env (persist into a small dotenv the supervisor can source)
ENVF=bot/data/profit_skyscraper.env
cat > "$ENVF" <<'EOF'
PROFIT_SKYSCRAPER=1
HUB_MONEY_FIRST=1
HUB_GUNIQUE_FIRST=0
TELEGRAM_TRASH_BLOCK=1
TELEGRAM_SKIN_GATE=1
TELEGRAM_TARGET_PEER=6774605259
TELEGRAM_COUNTDOWN_PEER=UNIQUE_g1
TELEGRAM_SHELF_OVERFLOW_PEERS=UNIQUE_g2,UNIQUE_g3,UNIQUE_g4,UNIQUE_g5
ROUND_SYNC=1
ROUND_INTERVAL_SECS=10
TTB_IDEAL_SECS=10
TTB_RELEASE_MAX_SECS=12
TTB_RELEASE_MIN_SECS=3
PREP_INVEST_MAX_SECS=400
ROUND_SYNC_RESULT_ALIGN=1
PACKER_REAL_COUNTDOWN_MAX=12
EOF
# Export for this shell / child restarts
set -a
# shellcheck disable=SC1090
source "$ENVF"
set +a

# Compile check
$PY -m py_compile bot/config/keep_allowlist.py bot/config/profit_skyscraper.py \
  bot/hub_engine_route.py bot/telegram_outbox.py 2>/dev/null || true

# Soft restart outbox so new route + trash block load
pkill -f 'telegram_outbox.py' 2>/dev/null || true
rm -f bot/data/telegram_outbox.lock 2>/dev/null || true

$PY bot/literally_everything_return.py 2>/dev/null | head -50 || true
$PY bot/human_return_path.py 2>/dev/null | head -40 || true

echo "========== DONE =========="
echo "Law: real OR can-become-real — then we'll know."
echo "North stars: BEST Existence · BEST clarity · THE MOST helpful"
echo "Ambition: max from literally everything (north star \$100k+/day/chat — not a guarantee)"
echo "Money: Mr_iv4 | Clocks: UNIQUE_g1 | Spill: UNIQUE_gN (never delay) | TTB≈10s"
echo "Status: python3 bot/human_return_path.py"
echo "Everything map: python3 bot/literally_everything_return.py"
