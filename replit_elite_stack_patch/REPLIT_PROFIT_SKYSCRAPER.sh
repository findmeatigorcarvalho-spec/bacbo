#!/usr/bin/env bash
# Profit Family AI + One AI Organizer + UNIQUE_g1 APEX Bundle (Mr_iv4 REMOVED).
#
#   curl -fsSL -o /tmp/SKY.sh \
#     'https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/cursor/add-engine-gate-registry-d5ba/replit_elite_stack_patch/REPLIT_PROFIT_SKYSCRAPER.sh?v=20260807g'
#   bash /tmp/SKY.sh
#
# Do NOT paste the printed DONE lines back into the shell — they are messages, not commands.
set -euo pipefail
ROOT="${ROOT:-/home/runner/workspace}"
cd "$ROOT"
PY="${PY:-python3}"
BRANCH="${BRANCH:-cursor/add-engine-gate-registry-d5ba}"
RAW="https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/${BRANCH}"
V="20260807h"
OK=0
FAIL=0

echo "========== PROFIT FAMILY AI + ONE ORGANIZER + G1 APEX =========="
echo "ROOT=$ROOT"
mkdir -p bot/config bot/data logs

pull() {
  local dest="$1" url="$2"
  if curl -fsSL -o "$dest" "$url"; then
    OK=$((OK + 1))
    echo "  OK  $dest"
  else
    FAIL=$((FAIL + 1))
    echo "  FAIL $dest"
  fi
}

echo "-- config --"
# ALWAYS overwrite skin_families/registry — older Replit copies miss canonical_family_id.
for f in keep_allowlist.py profit_skyscraper.py profit_chat_bundle.py bundle_organizer.py \
         result_essence_engine.py fire_result_law.py skin_gate.py chat_shelves.py chat_router.py \
         skin_families.py registry.py __init__.py; do
  pull "bot/config/${f}" "${RAW}/bot/config/${f}?v=${V}"
done

echo "-- bot runtime --"
for f in hub_engine_route.py telegram_outbox.py dual_lane_router.py chat_router.py chat_shelves.py \
         skin_gate.py lux_send_config_bind.py lux_re_harden.py window_packer.py round_sync_densifier.py \
         human_return_path.py literally_everything_return.py factual_card_contract.py \
         runtime_supervisor.py hub_max_boot.py hub_dispatch.py build_profit_skyscraper_brain.py \
         build_result_essence_atlas.py triage_museum_keep_trash.py; do
  pull "bot/${f}" "${RAW}/replit_elite_stack_patch/bot/${f}?v=${V}"
done

echo "-- data --"
for f in museum_triage_keep_trash.json keep_allowlist.json profit_skyscraper_brain.json \
         chat_playbook_cards.json CHAT_PROFIT_PLAYBOOK.md museum_full_catalog.json \
         profit_skyscraper.env literally_everything_return.json result_essence_atlas.json \
         peak_fidelity_ranker_report.json profit_organism_report.json; do
  pull "bot/data/${f}" "${RAW}/replit_elite_stack_patch/bot/data/${f}?v=${V}"
done

ENVF=bot/data/profit_skyscraper.env
cat > "$ENVF" <<'EOF'
PROFIT_SKYSCRAPER=1
PROFIT_CHAT_BUNDLE=1
BUNDLE_ORGANIZER=1
RESULT_ESSENCE_ENGINE=1
PROFIT_FAMILY_AI=1
FIRE_RESULT_LAW=1
RESULT_ATTACH_IMMEDIATE=1
HUB_OUTBOX_RESULT_CARDS=1
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
ROUND_SYNC_RESULT_ALIGN=0
PACKER_REAL_COUNTDOWN_MAX=12
HUMAN_RETURN_PATH=1
EOF
set -a
# shellcheck disable=SC1090
source "$ENVF"
set +a

echo "-- compile --"
if $PY -m py_compile bot/config/fire_result_law.py bot/config/result_essence_engine.py \
  bot/config/bundle_organizer.py bot/config/profit_chat_bundle.py bot/config/chat_router.py 2>&1; then
  echo "  OK  py_compile config"
else
  echo "  WARN py_compile config (non-fatal if deps missing)"
fi

echo "-- verify --"
$PY - <<'PY'
import json, sys
from pathlib import Path
sys.path.insert(0, ".")
errs = []
for p in [
    "bot/config/fire_result_law.py",
    "bot/config/result_essence_engine.py",
    "bot/config/bundle_organizer.py",
    "bot/config/profit_chat_bundle.py",
    "bot/data/result_essence_atlas.json",
    "bot/data/profit_skyscraper.env",
]:
    if not Path(p).is_file():
        errs.append(f"missing {p}")
        print("MISSING", p)
    else:
        print("HAVE", p)

try:
    from bot.config.result_essence_engine import family_ai_manifest, load_atlas
    from bot.config.bundle_organizer import organize
    from bot.config.fire_result_law import (
        law_banner,
        law_enabled,
        outbox_must_emit_result_cards,
        result_skin_required,
    )
    a = load_atlas()
    m = family_ai_manifest()
    d = organize("SOLO ELITE SIGNAL\nENTER NOW")
    print(law_banner())
    print(json.dumps({
        "model": m.get("model"),
        "layers": m.get("layers"),
        "keep_scored": (a.get("stats") or {}).get("keep_scored"),
        "sample_peer": d.peer,
        "sample_becomes": d.becomes,
        "fire_result_law": law_enabled(),
        "result_skin_required": result_skin_required(),
        "outbox_result_cards": outbox_must_emit_result_cards(),
        "primary_env": __import__("os").environ.get("TELEGRAM_PRIMARY_PEER"),
        "exclude": __import__("os").environ.get("TELEGRAM_EXCLUDE_PEERS"),
        "HUB_OUTBOX_RESULT_CARDS": __import__("os").environ.get("HUB_OUTBOX_RESULT_CARDS"),
    }, indent=2))
    if d.peer != "UNIQUE_g1":
        errs.append(f"expected UNIQUE_g1 got {d.peer}")
    if not law_enabled() or not outbox_must_emit_result_cards():
        errs.append("FIRE↔RESULT law not fully ON")
except Exception as exc:
    errs.append(repr(exc))
    print("VERIFY_EXC", repr(exc))

if errs:
    print("VERIFY_FAIL", errs)
    sys.exit(1)
print("VERIFY_OK")
PY

pkill -f 'telegram_outbox.py' 2>/dev/null || true
rm -f bot/data/telegram_outbox.lock 2>/dev/null || true

echo "----------"
echo "pull_ok=$OK pull_fail=$FAIL"
echo "DONE — Profit Family AI + Organizer + UNIQUE_g1 APEX | Mr_iv4 OUT"
echo "RESULT attaches immediate under its own FIRE"
echo "Docs: PROFIT_FAMILY_AI.md and ONE_AI_ORGANIZER.md"
echo "Next: restart supervisor / outbox so env force-keys load"
echo "Do not paste these lines back into the shell."
