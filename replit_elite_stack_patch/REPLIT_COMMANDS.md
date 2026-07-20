# Replit Shell — Luxury Building Commands

Copy/paste these blocks into the Bac-Bo-Watcher Replit Shell.

Branch files are served from:
`https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/cursor/add-engine-gate-registry-d5ba/replit_elite_stack_patch/`

---

## 1) Install luxury building (seeded — includes JUN19/JUN20)

Live `bacbo.db` is often truncated. Installer merges `historical_luxury_seed.json`
so you still get the full building (not just LIVE).

```bash
cd /home/runner/workspace

curl -fsSL -o install_luxury_building.py \
  https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/cursor/add-engine-gate-registry-d5ba/replit_elite_stack_patch/install_luxury_building.py

python3 -u install_luxury_building.py

source luxury_building.env
echo "EDGE_POLICY_MODE=$EDGE_POLICY_MODE"
python3 - <<'PY'
import json
from pathlib import Path
d=json.loads(Path('bot/data/luxury_building_stack.json').read_text())
print('counts', d['counts'])
print('live', d['live_building_floors'])
print('peaks', [p.get('floor') for p in d.get('peak_day_floors') or []])
print('blocked', d['blocked_floors'])
need={'JUN19','JUN20','ELITE_V2','MAR19','MAY19'}
print('missing', sorted(need-set(d['live_building_floors'])) or 'none')
PY
```

Expected: **~32 live floors** including `JUN19` `JUN20` `JUN08` `JUN10` `JUN26` `JUN27`.  
Blocked only `JUN12A` `JUN12B`. If you still see `live=1`, seed download failed — re-run.

### Optional: create missing peak gates

```bash
cd /home/runner/workspace
ls bot/_gates_*.py | sed 's|.*/_gates_||;s|\.py||' | sort
for F in JUN19 JUN20 JUN08 JUN10 JUN26 JUN27; do
  if [ ! -f "bot/_gates_${F}.py" ]; then
    SRC=$(ls bot/_gates_MAY19.py bot/_gates_MAY10.py bot/_gates_ELITE_V2.py bot/_gates_LIVE.py 2>/dev/null | head -1)
    [ -n "$SRC" ] && cp "$SRC" "bot/_gates_${F}.py" && echo "created _gates_${F}.py from $SRC"
  fi
done
```

---

## 2) Export everything I need (run after install)

```bash
cd /home/runner/workspace

curl -fsSL -o replit_pull_luxury_export.sh \
  https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/cursor/add-engine-gate-registry-d5ba/replit_elite_stack_patch/replit_pull_luxury_export.sh
curl -fsSL -o replit_pull_may_jul.sh \
  https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/cursor/add-engine-gate-registry-d5ba/replit_elite_stack_patch/replit_pull_may_jul.sh
curl -fsSL -o replit_pull_full_luxury_pack.sh \
  https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/cursor/add-engine-gate-registry-d5ba/replit_elite_stack_patch/replit_pull_full_luxury_pack.sh

bash replit_pull_full_luxury_pack.sh
ls -lah luxury_export_light.zip may_jul_export.zip luxury_full_pack.zip bacbo_db_only.zip 2>/dev/null
```

Upload **all zips that exist** via YDRAY and paste the links here.

---

## 3) Start firing to Telegram (luxury mode)

```bash
cd /home/runner/workspace
source luxury_building.env

# Make sure mode is luxury (not shadow)
export EDGE_POLICY_MODE=luxury
export EDGE_LUXURY_FLOOR_GATE=1
export FALLBACK_SEND_BLOCKED=0

# Restart your normal bot process (use whatever you already use), e.g.:
#  - Stop/Start the Replit Run button
#  - OR supervisor:
python3 -u bot/runtime_supervisor.py
```

Watch logs for:
- `[EdgePolicy] ... ALLOW — EDGE_LUXURY_FLOOR ...`
- `EDGE_FLOOR_BLOCKED JUN12A/JUN12B`

---

## 4) Safe first hour (optional dry shadow before flood)

```bash
export EDGE_POLICY_MODE=shadow
# restart bot, watch SHADOW_ALLOW / SHADOW_BLOCK for ~30-60 min
# then:
export EDGE_POLICY_MODE=luxury
# restart again
```

---

## 5) Quick health checks

```bash
cd /home/runner/workspace
python3 - <<'PY'
import json,os
from pathlib import Path
print('mode', os.environ.get('EDGE_POLICY_MODE'))
for name in [
  'luxury_building_stack.json',
  'floor_stack_registry_report.json',
  'skyscraper_stack_report.json',
  'edge_whitelist_engine.json',
]:
  p=Path('bot/data')/name
  print(name, 'OK' if p.exists() else 'MISSING', p.stat().st_size if p.exists() else 0)
lux=json.loads(Path('bot/data/luxury_building_stack.json').read_text())
print('live_building', lux['counts'])
print(lux['live_building_floors'])
PY

# optional: room cleaner dry-run
python3 -u bot/room_cleaner.py --db bot/bacbo.db || true
```

---

## 6) If install_edge_tools alone (older path)

```bash
cd /home/runner/workspace
curl -fsSL -o install_edge_tools.py \
  https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/cursor/add-engine-gate-registry-d5ba/replit_elite_stack_patch/install_edge_tools.py
python3 -u install_edge_tools.py
python3 -u bot/luxury_building_stack.py --db bot/bacbo.db
source luxury_building.env 2>/dev/null || export EDGE_POLICY_MODE=luxury
```
