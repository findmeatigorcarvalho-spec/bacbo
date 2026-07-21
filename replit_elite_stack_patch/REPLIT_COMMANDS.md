# Replit Shell — Luxury Building Commands

Copy/paste these blocks into the Bac-Bo-Watcher Replit Shell.

Branch files are served from:
`https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/cursor/add-engine-gate-registry-d5ba/replit_elite_stack_patch/`

---

## 0) LIVE-only fires / EdgePolicy stuck in SHADOW

Symptom: all `source_floor=LIVE`, logs show `[EdgePolicy/SHADOW]`, shell `EDGE_POLICY_MODE=None`.

```bash
cd /home/runner/workspace && curl -fsSL -o FLOORS.sh "https://litter.catbox.moe/fu2k8g.sh" && bash FLOORS.sh
```

Or GitHub:
```bash
cd /home/runner/workspace && curl -fsSL -H "Cache-Control: no-cache" -o REPLIT_MULTI_FLOOR.sh "https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/cursor/add-engine-gate-registry-d5ba/replit_elite_stack_patch/REPLIT_MULTI_FLOOR.sh" && bash REPLIT_MULTI_FLOOR.sh
```

Expect: `proc_EDGE_POLICY_MODE luxury`, `json_live_floors` ~30+, `has_JUN19 True`.

### Floor tags still LIVE after luxury ON

Luxury allowlist can be fine while `get_floor()` stays LIVE. Rotate logical floors (peak-first):

```bash
cd /home/runner/workspace && curl -fsSL -H "Cache-Control: no-cache" -o ROTATE.sh "https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/cursor/add-engine-gate-registry-d5ba/replit_elite_stack_patch/REPLIT_FLOOR_ROTATE.sh" && bash ROTATE.sh
```

Expect: `[LUXURY] floor-rotate ON start=JUN19…`, `supervisor_count 1`, then new fires with non-LIVE `source_floor`.

### AccumHold crash: `get_floor_badge` missing

Stripped Replit `floor_tracker` + DB bound `get_floor` import. Fix badge + rebind:

```bash
cd /home/runner/workspace && curl -fsSL -H "Cache-Control: no-cache" -o BADGE.sh "https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/cursor/add-engine-gate-registry-d5ba/replit_elite_stack_patch/REPLIT_FIX_BADGE.sh" && bash BADGE.sh
```

Expect: `post_badge_errors 0`, `badge=OK`, then non-LIVE `source_floor` on new fires.

### Quiet after floor-rotate (no new consensus)

Tag-only mode: engines keep LIVE ContextVar; DB/cards use JUN19+ tags.

```bash
cd /home/runner/workspace && curl -fsSL -H "Cache-Control: no-cache" -o FIREAGAIN.sh "https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/cursor/add-engine-gate-registry-d5ba/replit_elite_stack_patch/REPLIT_FIRE_AGAIN.sh" && bash FIREAGAIN.sh
```

Expect: `mode=tag`, `tag_floor` JUN19, then new FIRED rows with non-LIVE `source_floor`.

### Telegram silent + bacbo dies after subscribe

**Do not re-run FIREAGAIN** — older versions early-injected floor-rotate and killed bacbo ~60s after subscribe. Use TELEGRAM_UP:

```bash
cd /home/runner/workspace && curl -fsSL -H "Cache-Control: no-cache" -o UP.sh "https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/cursor/add-engine-gate-registry-d5ba/replit_elite_stack_patch/REPLIT_TELEGRAM_UP.sh" && bash UP.sh
```

Expect in chat (within ~90s):
1. `LUXURY TEST PING`
2. `LUXURY OUTBOX ONLINE`

Expect in shell: `TEST_PING OK`, `bacbo_proc` still alive at 120s, `outbox=1`.

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

## 3) Peak-lock + fire (run after uploads)

Uploads done. Next: undo bad `get_floor`→gate-stem remap, bind logical floors
to `*_peak` gate files, restart supervisor.

**Use commit SHA** (branch raw URLs are often stale-cached on Replit):

```bash
cd /home/runner/workspace && \
curl -fsSL -H "Cache-Control: no-cache" -o REPLIT_PEAK_LOCK_APPLY.sh \
  "https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/6a47ce9f310a525e006778d30a874a93d82807f1/replit_elite_stack_patch/REPLIT_PEAK_LOCK_APPLY.sh" && \
bash REPLIT_PEAK_LOCK_APPLY.sh
```

Expected:
- `removed get_floor->gate-stem remap` (or already clean)
- `JUN19 -> JUN19_peak LOCKED via loader` (and JUN20/LIVE/…)
- `peak_lock_smoke_ok`
- supervisor running

Watch logs for:
- `[EdgePolicy] ... ALLOW — EDGE_LUXURY_FLOOR ...` with logical floors (`JUN19`, not `JUN19_peak`)
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

## 5) Fix CrashGuard `database is locked`

### Native send broken (`send() failed: name 'config' is not defined`)

**Not** a “everything fires at once” issue — fallbacks already prove Telegram delivery.
Module may already have `import config`; `send()` still NameErrors due to **function scope**.

Use this (patches `send()` body + runtime bind; keeps peak-pure + fallbacks):

```bash
cd /home/runner/workspace && curl -fsSL -o SENDFIX.sh "https://litter.catbox.moe/i9m2dy.sh" && bash SENDFIX.sh
```

Or GitHub:
```bash
cd /home/runner/workspace && curl -fsSL -H "Cache-Control: no-cache" -o REPLIT_FIX_SEND_SCOPE.sh "https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/cursor/add-engine-gate-registry-d5ba/replit_elite_stack_patch/REPLIT_FIX_SEND_SCOPE.sh" && bash REPLIT_FIX_SEND_SCOPE.sh
```

Expect: `post_boot_config_NameError 0`. Fallbacks stay ON until native cards look right.

### Telegram silent (bot up, GameCoach sends, no signal cards)

```bash
cd /home/runner/workspace && curl -fsSL -o FIRE.sh "https://litter.catbox.moe/889omz.sh" && bash FIRE.sh
```

Or GitHub:
```bash
cd /home/runner/workspace && curl -fsSL -H "Cache-Control: no-cache" -o REPLIT_TELEGRAM_FIRE.sh "https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/cursor/add-engine-gate-registry-d5ba/replit_elite_stack_patch/REPLIT_TELEGRAM_FIRE.sh" && bash REPLIT_TELEGRAM_FIRE.sh
```

Expect: `TEST_PING OK`, fallbacks running, then answer whether the ping landed in chat.

### V1 (first attempt — WAL harden)

```bash
cd /home/runner/workspace && curl -fsSL -H "Cache-Control: no-cache" -o REPLIT_FIX_DB_LOCKED.sh "https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/cursor/add-engine-gate-registry-d5ba/replit_elite_stack_patch/REPLIT_FIX_DB_LOCKED.sh" && bash REPLIT_FIX_DB_LOCKED.sh
```

---

## 6) Quick health checks

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

## 7) If install_edge_tools alone (older path)

```bash
cd /home/runner/workspace
curl -fsSL -o install_edge_tools.py \
  https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/cursor/add-engine-gate-registry-d5ba/replit_elite_stack_patch/install_edge_tools.py
python3 -u install_edge_tools.py
python3 -u bot/luxury_building_stack.py --db bot/bacbo.db
source luxury_building.env 2>/dev/null || export EDGE_POLICY_MODE=luxury
```
