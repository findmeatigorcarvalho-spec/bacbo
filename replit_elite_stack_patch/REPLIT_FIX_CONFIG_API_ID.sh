#!/usr/bin/env bash
# Emergency: restore API_ID on bot/config/__init__.py so bacbo can boot.
#   curl -fsSL -o /tmp/FIXCFG.sh \
#     'https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/cursor/add-engine-gate-registry-d5ba/replit_elite_stack_patch/REPLIT_FIX_CONFIG_API_ID.sh?v=20260807a'
#   bash /tmp/FIXCFG.sh
set -euo pipefail
ROOT="${ROOT:-/home/runner/workspace}"
cd "$ROOT"
BRANCH="${BRANCH:-cursor/add-engine-gate-registry-d5ba}"
RAW="https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/${BRANCH}"
V="20260807a"

echo "========== FIX config API_ID =========="
mkdir -p bot/config
curl -fsSL -o bot/config/__init__.py "${RAW}/bot/config/__init__.py?v=${V}"
# Keep skin stack current too
for f in skin_families.py registry.py chat_shelves.py chat_router.py \
         bundle_organizer.py result_essence_engine.py profit_chat_bundle.py; do
  curl -fsSL -o "bot/config/${f}" "${RAW}/bot/config/${f}?v=${V}" || true
done

python3 - <<'PY'
import sys
sys.path.insert(0, "bot")
sys.path.insert(0, ".")
import config
print("API_ID", getattr(config, "API_ID", None))
print("API_HASH_set", bool(getattr(config, "API_HASH", None)))
print("TARGET", getattr(config, "TARGET", None))
missing = [k for k in ("API_ID", "API_HASH") if not getattr(config, k, None)]
if missing:
    print("MISSING", missing, "- set Replit Secrets TELEGRAM_API_ID / TELEGRAM_API_HASH")
    sys.exit(1)
print("CONFIG_OK")
PY

pkill -f 'runtime_supervisor.py|bacbo_royal_complete.py|telegram_outbox.py' 2>/dev/null || true
rm -f bot/data/runtime_supervisor.lock bot/data/telegram_outbox.lock 2>/dev/null || true
sleep 1
nohup python3 -u bot/runtime_supervisor.py > /tmp/luxury_supervisor.log 2>&1 &
sleep 4
pgrep -af 'runtime_supervisor|telegram_outbox|bacbo_royal' || true
echo "---- bot_live log ----"
tail -n 30 logs/bot_live.log 2>/dev/null || true
echo "========== DONE =========="
