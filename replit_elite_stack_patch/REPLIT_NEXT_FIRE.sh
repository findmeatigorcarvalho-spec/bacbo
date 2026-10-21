#!/usr/bin/env bash
# After get-everything succeeded: apply env, prefer *_peak gates, restart fire mode.
set -euo pipefail
cd /home/runner/workspace

BRANCH_BASE="https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/cursor/add-engine-gate-registry-d5ba/replit_elite_stack_patch"

# Always refresh seed + luxury stack builder (gate_aliases live here)
mkdir -p bot/data
curl -fsSL -o bot/data/historical_luxury_seed.json \
  "$BRANCH_BASE/bot/data/historical_luxury_seed.json"
curl -fsSL -o bot/luxury_building_stack.py \
  "$BRANCH_BASE/bot/luxury_building_stack.py"
python3 -u bot/luxury_building_stack.py \
  --db bot/bacbo.db \
  --seed bot/data/historical_luxury_seed.json

source luxury_building.env 2>/dev/null || true
export EDGE_POLICY_MODE=luxury
export EDGE_LUXURY_FLOOR_GATE=1
export FALLBACK_SEND_BLOCKED=0
printf 'EDGE_POLICY_MODE=luxury\nEDGE_LUXURY_FLOOR_GATE=1\nFALLBACK_SEND_BLOCKED=0\n' > luxury_building.env

# Prefer real peak gates already on disk (JUN19_peak etc.) over cloned stubs
python3 - <<'PY'
import json
from pathlib import Path
root=Path('/home/runner/workspace')
seed=json.loads((root/'bot/data/historical_luxury_seed.json').read_text())
aliases=seed.get('gate_aliases') or {}
if not aliases:
    raise SystemExit('ERROR: seed has no gate_aliases — download failed')
live_path=root/'bot/data/luxury_live_floors.json'
live=json.loads(live_path.read_text()) if live_path.exists() else {}
live['gate_aliases']=aliases
live['blocked']=sorted(set(live.get('blocked') or [])|set(seed.get('hard_block') or ['JUN12A','JUN12B']))
if not live.get('live_floors'):
    lux=json.loads((root/'bot/data/luxury_building_stack.json').read_text())
    live['live_floors']=lux.get('live_building_floors') or []
live_path.write_text(json.dumps(live, indent=2)+'\n')
print('live_floors', len(live.get('live_floors') or []))
print('blocked', live['blocked'])
print('aliases')
ok=miss=0
for k,v in sorted(aliases.items()):
    g=root/'bot'/f'_gates_{v}.py'
    status='OK' if g.exists() else 'MISSING_GATE'
    if g.exists(): ok+=1
    else: miss+=1
    print(f'  {k} -> {v}  {status}')
print(f'alias_gates_ok={ok} missing={miss}')
PY

echo
echo "MODE=$EDGE_POLICY_MODE"
echo "Now Stop/Start the Replit Run button (or restart supervisor)."
echo "Watch logs for: [EdgePolicy] ALLOW — EDGE_LUXURY_FLOOR"
echo
echo "THEN upload via YDRAY and paste links:"
ls -lah luxury_full_pack.zip luxury_export_light.zip may_jul_export.zip bacbo_db_only.zip
