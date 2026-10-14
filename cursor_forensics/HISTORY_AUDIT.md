# History Audit

Audit timestamp: 2026-10-14 UTC

## Scope searched

Metadata and filenames were searched in:

- current project: `/workspace`
- immediate contents of the current workspace
- `/home/ubuntu/Downloads`
- `/home/ubuntu/Desktop`
- `/home/ubuntu/Documents`
- accessible Cursor-local data under `/home/ubuntu/.cursor`
- accessible Cursor user data under `/home/ubuntu/.config/Cursor`
- this agent's persistent store

No broad whole-disk content search was used. No private Telegram message content,
credentials, session files, cookies, or secret-bearing environment files were
opened. Multi-gigabyte archives/databases were not opened or copied.

## Search availability

| Location | Result |
|---|---|
| `/workspace` | Present; approximately 12 MB |
| Nearby project folders | No additional project checkout visible beside `/workspace` |
| `/home/ubuntu/Downloads` | Not present |
| `/home/ubuntu/Desktop` | Not present |
| `/home/ubuntu/Documents` | Not present |
| `/home/ubuntu/.cursor` | Present; approximately 844 KB |
| `/home/ubuntu/.config/Cursor` | Not present |
| Agent persistent store | Empty |

## Cursor AI conversation history

No local Cursor conversation database, JSON/JSONL transcript export, chat archive,
or readable conversation-history store was found in the accessible Cursor user
data.

The accessible Cursor-local area contains support/runtime metadata and canvas
dependencies, not a durable copy of the user's full Cursor AI conversation
history. The current chat context is available to the running agent, but it is
not exposed here as a local history file that can be inventoried or preserved.

Therefore:

- full Cursor chat history is **unavailable locally in this environment**;
- it may be cloud-managed or retained on another user machine;
- this audit does **not** claim to have recovered it.

## High-value project-memory artifacts found

Modification timestamps below are filesystem timestamps in this checkout. Most
are checkout/materialization times, not reliable proof of original creation time.

| Path | Size | Modified (UTC) | Relevance |
|---|---:|---|---|
| `/workspace/replit_elite_stack_patch/AGENT_MEMORY_CAPTURED.md` | 3,529 B | 2026-10-13 16:19:50 | Distilled Replit-agent/project knowledge |
| `/workspace/replit_elite_stack_patch/DAY_ONE_MAP.md` | 2,644 B | 2026-10-13 16:19:50 | Day-one system map |
| `/workspace/replit_elite_stack_patch/TELEGRAM_CARD_ERAS.md` | 9,769 B | 2026-10-13 16:19:50 | Historical card-family/era map |
| `/workspace/replit_elite_stack_patch/bot/data/museum_full_catalog.json` | 629,494 B | 2026-10-13 16:19:50 | 827 catalogued card/template records |
| `/workspace/replit_elite_stack_patch/bot/data/signal_ledger.json` | 475,334 B | 2026-10-13 16:19:50 | 120 registry families plus unresolved decisions |
| `/workspace/replit_elite_stack_patch/bot/data/museum_chrono_all_pairs.json` | 288,650 B | 2026-10-13 16:19:50 | Distilled chronological fire/result pairs |
| `/workspace/bot/data/skin_floor_census.json` | 116,137 B | 2026-10-13 16:19:50 | 154-floor census across code/Telegram/DB sources |
| `/workspace/bot/data/tg_cross_compare/tg_cross_compare.json` | 88,360 B | 2026-10-13 16:19:50 | Telegram type-to-family coverage comparison |
| `/workspace/replit_elite_stack_patch/CARD_CONTENT_ATLAS.md` | 7,219 B | 2026-10-13 17:07:06 | Content-level card audit |
| `/workspace/replit_elite_stack_patch/TOTAL_CENSUS.md` | 5,186 B | 2026-10-13 16:34:00 | Reconciled inventory and verification status |

Additional relevant report groups include:

- `replit_elite_stack_patch/bot/data/early_*`
- `replit_elite_stack_patch/bot/data/peak_*`
- `replit_elite_stack_patch/bot/data/result_*`
- `replit_elite_stack_patch/bot/data/timing_*`
- `replit_elite_stack_patch/bot/data/volume_*`
- `replit_elite_stack_patch/bot/data/zero_miss_report.json`
- `replit_elite_stack_patch/LITERALLY_EVERYTHING*.md`
- `replit_elite_stack_patch/SYSTEM_COMPLETE_MAP.md`
- `replit_elite_stack_patch/MASTER_SKIN_FLOORS.md`
- `replit_elite_stack_patch/FINAL_LUXURY_BUILDING_PLAN.md`

These are derived artifacts. They are useful project memory, but they are not
substitutes for the original source tree, raw database, or raw Telegram export.

## Files mentioning the requested historical terms

The current repository contains many files referring to `bacbo`, `replit`,
`telegram`, and `mr_iv4`; the search returned at least 291 matching project
files. The most relevant clusters are:

- runtime and delivery modules under `replit_elite_stack_patch/bot/`;
- Replit recovery/deployment scripts named `REPLIT_*.sh`;
- Telegram archaeology scripts named `REPLIT_TG_*` and
  `REPLIT_TELEGRAM_*`;
- card/family/floor maps under `replit_elite_stack_patch/*.md`;
- distilled catalogs under `replit_elite_stack_patch/bot/data/` and
  `/workspace/bot/data/`.

Files specifically mentioning Ydray include:

- `/workspace/replit_elite_stack_patch/DL_YDRAY.sh`
- `/workspace/replit_elite_stack_patch/download_ydray_full_app.sh`
- `/workspace/replit_elite_stack_patch/ydray_probe_all.sh`
- `/workspace/replit_elite_stack_patch/ARCHIVE_MANIFEST.md`
- `/workspace/replit_elite_stack_patch/LOCAL_PC_HUNT.sh`
- several Replit export/recovery scripts and planning documents

No actual Ydray-sized archive was found locally.

## Archive/database findings

Only one project archive/database candidate exists in this checkout:

| Path | Size | Modified (UTC) | Type | Finding |
|---|---:|---|---|---|
| `/workspace/replit_elite_stack_patch.zip` | 229,152 B | 2026-10-13 16:19:50 | ZIP | Small patch archive; archive listing totals about 1.59 MB uncompressed and contains 60 patch files. It is not the full app and contains no live multi-GB database. |

No `.db`, `.sqlite`, `.sqlite3`, `.7z`, or `.rar` project artifact was found
under `/workspace` or the accessible standard user folders.

Several small synthetic databases existed under temporary storage during this
agent session. They were generated for unit tests, are not historical project
artifacts, and are intentionally excluded as candidates.

## Historical Ydray record

`ARCHIVE_MANIFEST.md` records a historical full-application Ydray archive:

- expected filename:
  `YDRAY-Bac-Bo-Watcher-replit-full-app-audit-for-cursor-Ai.zip`
- recorded size: 7,400,961,129 bytes
- recorded contents: the main engine, `bot/bacbo.db` (then approximately
  2.8 GB), `signal_handler.py`, runtime modules, and many gate files
- recorded status: transfer expired; prior ephemeral copy deleted; never
  committed to Git

That archive is **not present locally** in this environment. Transfer identifiers,
download URLs, and hashes are intentionally omitted from this report.

## Replit evidence supplied by the operator

The operator's read-only Replit command reported these remote candidates:

| Remote Replit path | Size | Interpretation |
|---|---:|---|
| `./bot/bacbo.db` | 3,461,976,064 B | Largest/current live database candidate |
| `./bot_LEGACY_JULY_16/bacbo.db` | 3,334,729,728 B | July legacy snapshot candidate |
| `./bacbo.db` | 45,056 B | Tiny sibling; not likely the full database |
| `./bot_LEGACY_JULY_16/data/bacbo.db` | 0 B | Empty file |

Those files are on Replit, not in `/workspace`, and were not opened by this
audit. The same output reported a latest consensus timestamp of
`2026-08-19 01:08:19`.

## Historical interpretation

The repository supports the following restrained conclusions:

1. Development proceeded through many card, family, floor, gate, timing, and
   routing variants.
2. Later work focused heavily on restoring stalled firing, preventing database
   mis-selection, avoiding Telegram session conflicts, and creating recovery
   scripts.
3. Most retained local material is a reconstruction layer produced after the
   fact, not the original application source.
4. No direct casino truth dataset is present in the retained reports:
   `truth_verification_report.json` records zero direct casino rows and zero
   signal-to-casino matches.
5. Accordingly, historical accuracy or profitability claims cannot be treated
   as independently verified.

## Audit limitation

Telegram history was not accessed in this phase, as requested. The catalog files
already in the repository are summaries/derivatives and may not preserve every
raw message or exact pairing. Cursor cloud chat history and the user's other
machines are outside this filesystem's accessible evidence.
