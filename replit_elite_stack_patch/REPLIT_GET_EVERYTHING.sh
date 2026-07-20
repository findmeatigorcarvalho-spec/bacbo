#!/usr/bin/env bash
# ONE paste for Replit Shell — install luxury stack + export everything.
# Copy the whole file contents into Replit and run.
set -euo pipefail

ROOT=/home/runner/workspace
cd "$ROOT"
BRANCH_BASE="https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/cursor/add-engine-gate-registry-d5ba/replit_elite_stack_patch"

echo "========== [1/7] download installers =========="
curl -fsSL -o install_luxury_building.py "$BRANCH_BASE/install_luxury_building.py"
curl -fsSL -o replit_pull_full_luxury_pack.sh "$BRANCH_BASE/replit_pull_full_luxury_pack.sh"
curl -fsSL -o replit_pull_luxury_export.sh "$BRANCH_BASE/replit_pull_luxury_export.sh"
curl -fsSL -o replit_pull_may_jul.sh "$BRANCH_BASE/replit_pull_may_jul.sh"
chmod +x replit_pull_*.sh

echo "========== [2/7] install luxury building (seeded) =========="
python3 -u install_luxury_building.py
source "$ROOT/luxury_building.env" || true
export EDGE_POLICY_MODE=luxury
export EDGE_LUXURY_FLOOR_GATE=1
export FALLBACK_SEND_BLOCKED=0

echo "========== [3/7] create missing peak gates =========="
for F in JUN19 JUN20 JUN08 JUN10 JUN26 JUN27; do
  if [ ! -f "bot/_gates_${F}.py" ]; then
    SRC=$(ls bot/_gates_MAY19.py bot/_gates_MAY10.py bot/_gates_ELITE_V2.py bot/_gates_LIVE.py 2>/dev/null | head -1 || true)
    if [ -n "${SRC:-}" ]; then
      cp "$SRC" "bot/_gates_${F}.py"
      echo "CREATED bot/_gates_${F}.py from $SRC"
    else
      echo "WARN: no source gate to clone for $F"
    fi
  else
    echo "OK exists bot/_gates_${F}.py"
  fi
done

echo "========== [4/7] export all packs =========="
bash replit_pull_full_luxury_pack.sh

echo "========== [5/7] DB + gates diagnostics =========="
python3 - <<'PY'
import json, os, sqlite3
from pathlib import Path

root = Path('/home/runner/workspace')
db = root / 'bot' / 'bacbo.db'
print('ROOT', root)
print('DB_EXISTS', db.exists(), 'SIZE', db.stat().st_size if db.exists() else 0)
print('EDGE_POLICY_MODE', os.environ.get('EDGE_POLICY_MODE'))
print('EDGE_LUXURY_FLOOR_GATE', os.environ.get('EDGE_LUXURY_FLOOR_GATE'))

gates = sorted(p.name.replace('_gates_','').replace('.py','') for p in (root/'bot').glob('_gates_*.py'))
print('GATES_N', len(gates))
print('GATES', ','.join(gates))

for name in [
    'luxury_building_stack.json',
    'historical_luxury_seed.json',
    'luxury_live_floors.json',
    'floor_stack_registry_report.json',
]:
    p = root/'bot'/'data'/name
    print('FILE', name, 'OK' if p.exists() else 'MISSING', p.stat().st_size if p.exists() else 0)

lux = json.loads((root/'bot'/'data'/'luxury_building_stack.json').read_text())
print('LUX_COUNTS', json.dumps(lux.get('counts'), sort_keys=True))
print('LUX_LIVE', lux.get('live_building_floors'))
print('LUX_PEAKS', [p.get('floor') for p in lux.get('peak_day_floors') or []])
print('LUX_BLOCKED', lux.get('blocked_floors'))
print('LUX_VIRTUAL', [v.get('key') for v in lux.get('virtual_setups') or []])
need = {'JUN19','JUN20','JUN08','JUN10','ELITE_V2','MAR19','MAY19','LIVE'}
have = set(lux.get('live_building_floors') or [])
print('MISSING_NEED', sorted(need-have) or ['none'])

if db.exists():
    con = sqlite3.connect(f'file:{db}?mode=ro', uri=True)
    cols = {r[1] for r in con.execute('PRAGMA table_info(consensus_signals)')}
    print('COLS_HAS_won_at_gale', 'won_at_gale' in cols, 'secs_to_result', 'secs_to_result' in cols)
    rows = list(con.execute("""
      SELECT COALESCE(NULLIF(source_floor,''),'LIVE') floor, COUNT(*) n,
             ROUND(100.0*SUM(outcome='win')/NULLIF(SUM(outcome IN ('win','loss')),0),2) wr,
             MIN(fired_at), MAX(fired_at)
      FROM consensus_signals
      WHERE outcome IN ('win','loss','tie')
      GROUP BY 1 ORDER BY n DESC
    """))
    print('DB_FLOORS', len(rows))
    for r in rows[:40]:
        print('DB_FLOOR', r[0], 'n=', r[1], 'wr=', r[2], 'first=', r[3], 'last=', r[4])
    days = list(con.execute("""
      SELECT date(fired_at) d, COUNT(*) n,
             ROUND(100.0*SUM(outcome='win')/NULLIF(SUM(outcome IN ('win','loss')),0),2) wr
      FROM consensus_signals
      WHERE outcome IN ('win','loss','tie')
        AND date(fired_at) IN ('2026-06-19','2026-06-20','2026-06-08','2026-06-10','2026-05-19','2026-05-10')
      GROUP BY 1 ORDER BY 1
    """))
    print('DB_KEY_DAYS', days)
    rooms = con.execute("SELECT COUNT(*) FROM rooms").fetchone()[0] if 'rooms' in {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")} else None
    print('ROOMS_TABLE', rooms)
    con.close()
PY

echo "========== [6/7] zip inventory =========="
ls -lah \
  luxury_full_pack.zip \
  luxury_export_light.zip \
  may_jul_export.zip \
  bacbo_db_only.zip \
  luxury_building.env \
  bot/data/luxury_building_stack.json \
  bot/data/historical_luxury_seed.json \
  2>&1 || true

echo "========== [7/7] DONE =========="
echo
echo "NEXT: upload these via YDRAY and paste the download links HERE:"
echo "  $ROOT/luxury_full_pack.zip"
echo "  $ROOT/luxury_export_light.zip"
echo "  $ROOT/may_jul_export.zip"
echo "  $ROOT/bacbo_db_only.zip"
echo
echo "Also paste ALL terminal output from this script above the links."
