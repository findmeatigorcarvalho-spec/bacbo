# Literally everything — required for the building to work

Partial catalogs are not enough. Every signal skin / template / kind ever **created** (fired or not, Telegram or not) must enter the inventory.

## What “everything” means

| Source | What it catches |
|--------|-----------------|
| **CODE + .bak** | Quoted card headers + `FIRE_`/`RESULT_`/`CD_*` ids in formatters, handlers, gates |
| **GIT history** | Deleted / renamed templates still in blobs |
| **DB** | `signal_kind` + card text first-lines + `channel_messages` card-like rows |
| **Telegram archaeology** | Every `type_id` / first_line from the Mar17→now scrape |
| **Timing catalog** | ~19k structural fingerprints (`timing_presence_catalog.json`) |
| **Registered families** | Canonical shelf/gate ids (now **66**) |

Union = master list. Distill = building floors. Never drop CREATED_ONLY.

## Cloud status

| Metric | Status |
|--------|--------|
| TG archaeology | ✅ mined |
| Timing fingerprints (top) | ✅ mined |
| Registered + classify gaps filled | ✅ GOD-TIER, ORACLE, ENTRE AGORA, G0→G1, TIE ALERT, … |
| Master floors doc | `MASTER_SKIN_FLOORS.md` |
| **Live Replit formatters / `.bak` / gates** | ❌ missing |
| **Live `bacbo.db`** | ❌ missing |

## Run on Replit (ONE paste — packs mine + bot sources + DB kinds)

```bash
cd /home/runner/workspace
curl -fsSL -H 'Cache-Control: no-cache' -o LITERALLY_EVERYTHING.sh \
  'https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/cursor/add-engine-gate-registry-d5ba/replit_elite_stack_patch/REPLIT_LITERALLY_EVERYTHING.sh'
bash LITERALLY_EVERYTHING.sh
```

Paste the `FETCH_URL=` line back here. That zip is the missing leg.

## Outputs

| File | Role |
|------|------|
| `bot/data/literally_everything_floors.json` | Distilled floors |
| `replit_elite_stack_patch/MASTER_SKIN_FLOORS.md` | TG→classify coverage |
| `literally_everything_*/bot_sources/` | Live strings/handlers/gates/bak |
| `literally_everything_*/db_kinds.json` | DB signal_kind census |

## Honesty

Cloud alone **cannot** finish this — Replit holds the live `bot/` and `bacbo.db`. Older catbox luxury packs (404) are gone; only a fresh Replit upload recovers them.
