#!/usr/bin/env bash
# HUB MAX — Replit one-shot
# Locks:
#   1) Every config separate: decide/analyze/fire at its own peak-volume day (no shrink gates)
#   2) Original card skins (strip noise, refresh facts only)
#   3) Gunique @UNIQUE_g1 = #1 priority 24/7; money chat #2; rest cascade
#   4) Timed cards: hold if >30s live; post at ≤30s; keep original secs on card
#
# Usage:
#   curl -fsSL -H "Cache-Control: no-cache" -o HUBMAX.sh \
#     "https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/cursor/add-engine-gate-registry-d5ba/replit_elite_stack_patch/REPLIT_HUB_MAX.sh" \
#     && bash HUBMAX.sh
set -euo pipefail
cd /home/runner/workspace 2>/dev/null || cd "$(dirname "$0")/.."
PY="${PYTHON:-python3}"
SHA="${LUXURY_PATCH_SHA:-cursor/add-engine-gate-registry-d5ba}"
BASE="https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/${SHA}/replit_elite_stack_patch"
PEER="${TELEGRAM_TARGET_PEER:-6774605259}"
CD_PEER="${TELEGRAM_COUNTDOWN_PEER:-${GUNIQUE_PEER:-UNIQUE_g1}}"
CD_PEER="${CD_PEER#@}"
# Optional numeric bypass if username Resolve fails / FloodWaits:
#   export TELEGRAM_GUNIQUE_PEER_ID=<chat_id>
GUNIQUE_ID="${TELEGRAM_GUNIQUE_PEER_ID:-${GUNIQUE_PEER_ID:-${TELEGRAM_COUNTDOWN_PEER_ID:-}}}"

echo "========== HUB MAX [1/4] refresh modules =========="
mkdir -p bot/data logs
for rel in \
  bot/hub_max_boot.py \
  bot/hub_dispatch.py \
  bot/hub_engine_route.py \
  bot/lux_send_config_bind.py \
  bot/window_packer.py \
  bot/dual_lane_router.py \
  bot/fire_origin.py \
  bot/v2_floor_proposers.py \
  bot/telegram_outbox.py \
  bot/runtime_supervisor.py \
  BLUEPRINT_MAX_PROFIT.md \
  REPLIT_ONE_STACK.sh
do
  curl -fsSL -H "Cache-Control: no-cache" -o "$rel" "$BASE/$rel" || echo "skip $rel"
done
$PY -m py_compile bot/hub_max_boot.py bot/hub_dispatch.py bot/hub_engine_route.py bot/lux_send_config_bind.py bot/window_packer.py bot/dual_lane_router.py bot/fire_origin.py bot/telegram_outbox.py

# Ensure bacbo loads send-route bind (engine owns original skins → Gunique/money)
$PY - <<'PY'
import re
from pathlib import Path
cands = [Path("bacbo_royal_complete.py"), Path("bacbo.py"), Path("bot/bacbo_royal_complete.py")]
p = next((c for c in cands if c.exists()), None)
if not p:
    print("bacbo source not found — skip send-bind inject")
else:
    src = p.read_text(encoding="utf-8", errors="replace")
    if "LUXURY_SEND_CONFIG_BIND" in src:
        print("send-config-bind already injected in", p)
    else:
        block = '''
# --- LUXURY_SEND_CONFIG_BIND (auto) ---
try:
    import lux_send_config_bind  # noqa: F401
    print("[LUXURY] send-config-bind loaded (HUB engine route)")
except Exception as _lux_scb_exc:
    print("[LUXURY] send-config-bind skipped:", _lux_scb_exc)
# --- end LUXURY_SEND_CONFIG_BIND ---
'''
        m = re.search(r"^if __name__", src, re.M)
        if m:
            src = src[: m.start()] + block + "\n" + src[m.start() :]
        else:
            src = src + "\n" + block
        p.write_text(src, encoding="utf-8")
        print("injected send-config-bind into", p)
PY

echo "========== HUB MAX [2/4] apply locks → luxury_building.env =========="
export TELEGRAM_TARGET_PEER="$PEER"
export TELEGRAM_COUNTDOWN_PEER="$CD_PEER"
export GUNIQUE_PEER="$CD_PEER"
if [ -n "$GUNIQUE_ID" ]; then
  export TELEGRAM_GUNIQUE_PEER_ID="$GUNIQUE_ID"
  export GUNIQUE_PEER_ID="$GUNIQUE_ID"
fi
export HUB_MAX=1
export VOLUME_MODE=EXPLOSION
export V2_PROPOSERS=1
export TELEGRAM_MIRROR_MONEY_TO_GUNIQUE=0
export HUB_GUNIQUE_FIRST=1
export HUB_CONFIG_SEPARATE=1
export HUB_NO_SHRINK_GATES=1
export HUB_ORIGINAL_CARD_SKINS=1
export HUB_ENGINE_ROUTE=1
export HUB_OUTBOX_FIRE_CARDS=0
export HUB_OUTBOX_RESULT_CARDS=0
export PACKER_REAL_COUNTDOWN_MAX=30
$PY bot/hub_max_boot.py | tee logs/hub_max_boot.log

echo "========== HUB MAX [3/4] ONE stack (gunique-first env) =========="
# Ensure ONE_STACK uses Gunique peer + no money mirror
export TELEGRAM_TARGET_PEER="$PEER"
export TELEGRAM_COUNTDOWN_PEER="$CD_PEER"
export GUNIQUE_PEER="$CD_PEER"
if [ -n "$GUNIQUE_ID" ]; then
  export TELEGRAM_GUNIQUE_PEER_ID="$GUNIQUE_ID"
  export GUNIQUE_PEER_ID="$GUNIQUE_ID"
fi
export TELEGRAM_MIRROR_MONEY_TO_GUNIQUE=0
export VOLUME_MODE=EXPLOSION
export V2_PROPOSERS=1
export HUB_MAX=1
bash REPLIT_ONE_STACK.sh

echo "========== HUB MAX [4/4] verify =========="
echo "Priority: 1=@${CD_PEER} (Gunique 24/7)  2=${PEER} (money)  3+=specialists"
echo "Expect: mirror_money=False · VOLUME_MODE=EXPLOSION · HUB_MAX=1"
echo "Gunique resolve: cache/dialogs/username · optional TELEGRAM_GUNIQUE_PEER_ID=${GUNIQUE_ID:-unset}"
echo "Anti-double: HUB_OUTBOX_FIRE_CARDS=0 (engine skins) · HUB_ENGINE_ROUTE=1 (send→Gunique/money)"
echo "After boot check:"
echo "  rg -n 'HUB-ROUTE|Gunique resolve|skip fire card|FATAL CONFIG' logs/*.log | tail -40"
rg -n "HUB_MAX|VOLUME_MODE|GUNIQUE|COUNTDOWN_PEER|MIRROR" luxury_building.env 2>/dev/null | head -n 20 || true
if [ -f bot/data/hub_max_status.json ]; then
  $PY - <<'PY'
import json
st=json.load(open("bot/data/hub_max_status.json"))
print("status locks:", json.dumps(st.get("locks"), indent=2))
print("chat_priority:", st.get("chat_priority"))
print("packer_ok:", st.get("packer_ok"), st.get("packer_demo"))
PY
fi
echo
echo "DONE HUB MAX. Gunique first · configs separate peak volume · original skins · ≤30s real release."
echo "Optional museum continue: MUSEUM_OFFSET=10 MUSEUM_LIMIT=5 bash MC.sh"
