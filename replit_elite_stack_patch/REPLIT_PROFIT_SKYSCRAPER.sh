#!/usr/bin/env bash
# Profit Chat Bundle — UNIQUE_g1 APEX #1; Mr_iv4 REMOVED from live equation.
#
#   curl -fsSL -o /tmp/SKY.sh \
#     'https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/cursor/add-engine-gate-registry-d5ba/replit_elite_stack_patch/REPLIT_PROFIT_SKYSCRAPER.sh?v=20260806f'
#   bash /tmp/SKY.sh
set -euo pipefail
ROOT="${ROOT:-/home/runner/workspace}"
cd "$ROOT"
PY="${PY:-python3}"
BRANCH="${BRANCH:-cursor/add-engine-gate-registry-d5ba}"
RAW="https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/${BRANCH}"

echo "========== PROFIT CHAT BUNDLE — UNIQUE_g1 APEX =========="
mkdir -p bot/config bot/data logs

for f in keep_allowlist.py profit_skyscraper.py profit_chat_bundle.py skin_gate.py \
         chat_shelves.py chat_router.py; do
  curl -fsSL -o "bot/config/${f}" "${RAW}/bot/config/${f}?v=20260806f" || true
done
for f in chat_router.py chat_shelves.py skin_families.py registry.py; do
  if [[ ! -f "bot/config/${f}" ]]; then
    curl -fsSL -o "bot/config/${f}" "${RAW}/bot/config/${f}?v=20260806f" || true
  fi
done

for f in hub_engine_route.py telegram_outbox.py dual_lane_router.py chat_router.py chat_shelves.py \
         skin_gate.py lux_send_config_bind.py window_packer.py round_sync_densifier.py \
         human_return_path.py literally_everything_return.py factual_card_contract.py \
         runtime_supervisor.py hub_max_boot.py hub_dispatch.py build_profit_skyscraper_brain.py \
         triage_museum_keep_trash.py; do
  curl -fsSL -o "bot/${f}" \
    "${RAW}/replit_elite_stack_patch/bot/${f}?v=20260806f" || true
done

mkdir -p bot/data
for f in museum_triage_keep_trash.json keep_allowlist.json profit_skyscraper_brain.json \
         chat_playbook_cards.json CHAT_PROFIT_PLAYBOOK.md museum_full_catalog.json \
         profit_skyscraper.env literally_everything_return.json; do
  curl -fsSL -o "bot/data/${f}" \
    "${RAW}/replit_elite_stack_patch/bot/data/${f}?v=20260806f" || true
done

ENVF=bot/data/profit_skyscraper.env
cat > "$ENVF" <<'EOF'
PROFIT_SKYSCRAPER=1
PROFIT_CHAT_BUNDLE=1
HUB_G1_APEX_FIRST=1
HUB_MONEY_FIRST=0
HUB_GUNIQUE_FIRST=1
TELEGRAM_TRASH_BLOCK=1
TELEGRAM_SKIN_GATE=1
TELEGRAM_PRIMARY_PEER=UNIQUE_g1
TELEGRAM_PRIMARY_PEER_ID=5855678138
TELEGRAM_TARGET_PEER=UNIQUE_g1
TELEGRAM_COUNTDOWN_PEER=UNIQUE_g1
TELEGRAM_GUNIQUE_PEER_ID=5855678138
TELEGRAM_EXCLUDE_PEERS=Mr_iv4,6774605259
TELEGRAM_SHELF_OVERFLOW_PEERS=UNIQUE_g2,UNIQUE_g3,UNIQUE_g4,UNIQUE_g5
ROUND_SYNC=1
ROUND_INTERVAL_SECS=10
TTB_IDEAL_SECS=10
TTB_RELEASE_MAX_SECS=12
TTB_RELEASE_MIN_SECS=3
PREP_INVEST_MAX_SECS=400
ROUND_SYNC_RESULT_ALIGN=1
PACKER_REAL_COUNTDOWN_MAX=12
HUMAN_RETURN_PATH=1
EOF
set -a
# shellcheck disable=SC1090
source "$ENVF"
set +a

$PY -m py_compile bot/config/profit_chat_bundle.py bot/config/profit_skyscraper.py \
  bot/hub_engine_route.py bot/telegram_outbox.py 2>/dev/null || true
$PY - <<'PY' 2>/dev/null || true
import json, sys
sys.path.insert(0, ".")
from bot.config.profit_chat_bundle import bundle_catalog
print(json.dumps({
  "primary": bundle_catalog()["primary"],
  "excluded": bundle_catalog()["excluded"],
  "bundle": [(c["peer"], c["becomes"]) for c in bundle_catalog()["bundle"]],
}, indent=2))
PY

pkill -f 'telegram_outbox.py' 2>/dev/null || true
rm -f bot/data/telegram_outbox.lock 2>/dev/null || true

echo "========== DONE =========="
echo "APEX #1: UNIQUE_g1 | Mr_iv4: REMOVED"
echo "Bundle: g1 APEX · g2 PRECISION · g3 VOLUME · g4 ASSERTIVE · g5 IMPACT · g6+ ELASTIC"
echo "Reality: Make It Real / It Is Real, Really. It Is Real truthfully."
echo "Pin chat_playbook_cards.json in each UNIQUE_gN chat."
