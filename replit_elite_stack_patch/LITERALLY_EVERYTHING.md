# Literally everything — required for the building to work

Partial catalogs are not enough. Every signal skin / template / kind ever **created** (fired or not, Telegram or not) must enter the inventory.

## What “everything” means

| Source | What it catches |
|--------|-----------------|
| **CODE + .bak** | Quoted card headers + `FIRE_`/`RESULT_`/`CD_*` ids in formatters, handlers, gates |
| **GIT history** | Deleted / renamed templates still in blobs |
| **DB** | `signal_kind` + card text first-lines + `channel_messages` card-like rows |
| **Telegram archaeology** | Every `type_id` / first_line from the Mar17→now scrape |
| **Registered families** | Canonical shelf/gate ids |

Union = master list. Distill = building floors (drops `RELAY_*` + `TG_LINE::` duplicates). Never drop CREATED_ONLY.

## Cloud status (partial)

Local deep mine already ran with full TG catalog (`types_first_seen.csv`):

| Metric | Cloud result |
|--------|-------------:|
| Full union keys | ~77k (includes TG_LINE + RELAY) |
| Distilled floors | ~6.4k (FIRE/RESULT/CD/OPS + headers + tokens) |
| TOKEN / REGISTERED ids | ~135 / 59 |
| HEADER templates (code/git) | ~256 |
| **DB kinds / texts** | **missing** |
| **Replit formatters / .bak / gates** | **missing** |

## Run on Replit (required — full `bot/` + `bacbo.db` live there)

```bash
cd /home/runner/workspace
curl -fsSL -H 'Cache-Control: no-cache' -o FIND_ALL_SKINS.sh \
  'https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/cursor/add-engine-gate-registry-d5ba/replit_elite_stack_patch/REPLIT_FIND_ALL_SKINS.sh'
bash FIND_ALL_SKINS.sh
```

Paste `FETCH_URL=` (and `FLOORS=` / `HAS_STRINGS=`) back here. Cursor merges into census + shelves.

## Outputs

| File | Role |
|------|------|
| `bot/data/literally_everything_skins.json` | Full union (can be huge) |
| `bot/data/literally_everything_floors.json` | Distilled floors for the building |
| `bot/data/literally_everything_floors.csv` | Same, spreadsheet |
| `replit_elite_stack_patch/LITERALLY_EVERYTHING_FLOORS.md` | Human summary |
| `bot/data/template_source_files.txt` | Every formatter/bak/gate path on Replit |

## Honesty

Cloud workspace alone **cannot** finish this — it lacks Replit’s full `bot/` and live `bacbo.db`. The script above is the missing leg.
