# Bac Bo — Complete inventory map (day 1 → now)

Use this to know **where every class of data lives** and what to pull.

## On Replit RIGHT NOW (run `REPLIT_DAY_ONE_ARCHIVE.sh`)

| Category | Location | In DAY_ONE zip? |
|----------|----------|-----------------|
| **Engine** | `bacbo_royal_complete.py` + `.bak_*` | yes |
| **92+ gates** | `bot/_gates_*.py` | yes (`bot_full/`) |
| **Signal handler** | `bot/signal_handler.py` + backups | yes |
| **ML models** | `bot/models/*.pkl` | yes |
| **Live database** | `bot/bacbo.db` + WAL | yes + all tables CSV |
| **934k Telegram msgs** | `channel_messages` table in db | yes (CSV) |
| **143k signals** | `signals` table | yes (CSV) |
| **Floor reports** | `bot/data/*.json`, `every_blocked_win.json` | yes |
| **Luxury exports** | `luxury_export_*`, `may_jul_export_*` | yes |
| **Git since day 1** | `.git/` → `git/full_history.bundle` | yes |
| **Images/uploads** | `attached_assets/` | yes |
| **Bot logs** | `bot/bot.log*`, `logs/` | yes |
| **Replit AI/shell logs** | `.local/state/workflow-logs/` | yes |
| **Agent artifacts** | `.agents/` | yes |
| **Skills/prompts** | `.local/skills/` | yes |
| **Scribe notes** | `.local/state/scribe/` | yes |
| **Every file hash** | `MANIFEST_all_files.tsv` | yes |

## Already packaged (you ran this)

| File | Size | Contents |
|------|------|----------|
| `bacbo_SAVE_EVERYTHING_20260803T173541Z.zip` | 1.2 GB | git bundle, db, assets, CSVs |

**Upload this OR run DAY_ONE** (DAY_ONE is more complete — adds manifest, git blobs, workflow-logs, full bot/).

## NOT on Replit disk

| Item | Where to get it |
|------|-----------------|
| **Cursor chat history** | Cursor desktop → your account. Not stored in Replit workspace. |
| **YDRAY 7.4 GB full app** | Transfer `u17818127167255IdjZb8f932d8c217QL` — re-upload from PC if you have the zip |
| **Telegram cloud** | Live channels still have messages; db already has 934k cached |

## Finish checklist

1. **Replit:** `bash DAY_ONE.sh` → upload `bacbo_DAY_ONE_*.zip` → paste link in Cursor
2. **Cursor:** I pull zip and merge into cloud workspace + GitHub patch branch
3. **Hub/gates:** continue on `cursor/add-engine-gate-registry-d5ba` with full `bot/` + db
4. **Optional:** YDRAY 7.4 GB from your PC if found — merges 2.8 GB historical `bacbo.db` from June

## One-paste on Replit

```bash
cd /home/runner/workspace
curl -fsSL -H 'Cache-Control: no-cache' -o DAY_ONE.sh \
  'https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/cursor/add-engine-gate-registry-d5ba/replit_elite_stack_patch/REPLIT_DAY_ONE_ARCHIVE.sh'
bash DAY_ONE.sh
ls -lah bacbo_DAY_ONE*.zip
```
