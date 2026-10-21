#!/usr/bin/env bash
# Inline / cache-busted alias apply. Paste whole file into Replit Shell.
set -euo pipefail
cd /home/runner/workspace

SHA=a3f731f
BASE="https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/${SHA}/replit_elite_stack_patch"
TS=$(date +%s)

echo "=== refresh seed @ ${SHA} ==="
mkdir -p bot/data
curl -fsSL -H "Cache-Control: no-cache" -o bot/data/historical_luxury_seed.json \
  "${BASE}/bot/data/historical_luxury_seed.json?ts=${TS}"
curl -fsSL -H "Cache-Control: no-cache" -o bot/luxury_building_stack.py \
  "${BASE}/bot/luxury_building_stack.py?ts=${TS}"

python3 - <<'PY'
import json
from pathlib import Path
p=Path('bot/data/historical_luxury_seed.json')
d=json.loads(p.read_text())
aliases=d.get('gate_aliases') or {}
print('seed_aliases', len(aliases))
if len(aliases) < 5:
    raise SystemExit('SEED MISSING gate_aliases')
for k,v in list(aliases.items())[:5]:
    print(' sample', k, '->', v)
PY

python3 -u bot/luxury_building_stack.py --db bot/bacbo.db --seed bot/data/historical_luxury_seed.json >/tmp/lux_rebuild.json
python3 - <<'PY'
import json
from pathlib import Path
root=Path('.')
seed=json.loads((root/'bot/data/historical_luxury_seed.json').read_text())
aliases=seed['gate_aliases']
lux=json.loads((root/'bot/data/luxury_building_stack.json').read_text())
live={
  'live_floors': lux.get('live_building_floors') or [],
  'blocked': sorted(set(lux.get('blocked_floors') or []) | set(seed.get('hard_block') or ['JUN12A','JUN12B'])),
  'peak_day_floors': [p.get('floor') for p in (lux.get('peak_day_floors') or [])],
  'virtual_setups': [v.get('key') for v in (lux.get('virtual_setups') or [])],
  'gate_aliases': aliases,
}
(root/'bot/data/luxury_live_floors.json').write_text(json.dumps(live, indent=2)+'\n')
(root/'luxury_building.env').write_text(
  'export EDGE_POLICY_MODE=luxury\n'
  'export EDGE_LUXURY_FLOOR_GATE=1\n'
  'export FALLBACK_SEND_BLOCKED=0\n'
)
print('live_floors', len(live['live_floors']))
print('blocked', live['blocked'])
print('aliases')
ok=miss=0
for k,v in sorted(aliases.items()):
    g=root/'bot'/f'_gates_{v}.py'
    st='OK' if g.exists() else 'MISSING_GATE'
    ok += g.exists(); miss += (not g.exists())
    print(f'  {k} -> {v}  {st}')
print(f'alias_gates_ok={ok} missing={miss}')
print('MODE=luxury')
print('NOW: Stop/Start Replit Run button')
print('THEN upload YDRAY links for the 4 zips')
PY

ls -lah luxury_full_pack.zip luxury_export_light.zip may_jul_export.zip bacbo_db_only.zip
