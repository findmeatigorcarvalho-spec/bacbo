#!/usr/bin/env bash
# After get-everything succeeded: apply env, prefer *_peak gates, restart fire mode.
set -euo pipefail
cd /home/runner/workspace

source luxury_building.env
export EDGE_POLICY_MODE=luxury
export EDGE_LUXURY_FLOOR_GATE=1
export FALLBACK_SEND_BLOCKED=0

# Prefer real peak gates already on disk (JUN19_peak etc.) over cloned stubs
python3 - <<'PY'
import json
from pathlib import Path
root=Path('/home/runner/workspace')
seed=json.loads((root/'bot/data/historical_luxury_seed.json').read_text())
aliases=seed.get('gate_aliases') or {}
live=json.loads((root/'bot/data/luxury_live_floors.json').read_text())
live['gate_aliases']=aliases
live['blocked']=sorted(set(live.get('blocked') or [])|set(seed.get('hard_block') or ['JUN12A','JUN12B']))
(root/'bot/data/luxury_live_floors.json').write_text(json.dumps(live, indent=2)+'\n')
print('live_floors', len(live.get('live_floors') or []))
print('blocked', live['blocked'])
print('aliases')
for k,v in sorted(aliases.items()):
    g=root/'bot'/f'_gates_{v}.py'
    print(f'  {k} -> {v}', 'OK' if g.exists() else 'MISSING_GATE')
PY

echo
echo "MODE=$EDGE_POLICY_MODE"
echo "Now Stop/Start the Replit Run button (or restart supervisor)."
echo "Watch logs for: [EdgePolicy] ALLOW — EDGE_LUXURY_FLOOR"
echo
echo "THEN upload via YDRAY and paste links:"
ls -lah luxury_full_pack.zip luxury_export_light.zip may_jul_export.zip bacbo_db_only.zip
