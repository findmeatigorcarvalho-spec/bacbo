# Bac Bo full-app archive — IDs and access status

Last verified: 2026-08-01

## Original YDRAY upload (7.4 GB) — **NOT accessible**

| Field | Value |
|-------|-------|
| Share URL | https://ydray.com/get/t/u17818127167255IdjZb8f932d8c217QL |
| Transfer ID | `u17818127167255IdjZb8f932d8c217QL` |
| File ID | `21051862` |
| File hash | `7e83b1446f704866377e1be327b6cc0b` |
| Filename | `YDRAY-Bac-Bo-Watcher-replit-full-app-audit-for-cursor-Ai.zip` |
| Size | 7,400,961,129 bytes (~6.9–7.4 GB) |
| Expired | yes — API: `{"error":"expired","files":null}` |
| Paid recovery (€2.99) | **NO** — no `recoverable` flag (unlike messages export) |
| YDRAY page | "Your download has expired" — no restore button |

### Where it was saved (all gone)

| Location | Status |
|----------|--------|
| Cursor cloud agent VM `/tmp/replit-app-audit/YDRAY-...zip` | Ephemeral — deleted when VM ended |
| Replit `/home/runner/workspace/full_replit_app.zip` | Was downloaded Jun 18; **deleted later** (transcript confirms missing) |
| GitHub repo | **Never stored** (only patch stack) |
| Cursor artifacts | **Not stored** |
| Catbox links in `peak_lock_config.json` | Small exports only; all 404 |

### Zip internal layout (from Jun 18 extraction)

```
Bac-Bo-Watcher/
  bacbo_royal_complete.py   (main engine)
  bot/
    bacbo.db                (~2.8 GB)
    signal_handler.py       (~878 KB)
    main.py, database.py, state.py, utils.py, floor_tracker.py
    _gates_*.py             (66+ gate files)
    data/*.json
```

---

## Secondary YDRAY (Telegram messages only)

| Field | Value |
|-------|-------|
| Share URL | https://ydray.com/get/t/u1784507017063UBqg11e64279acc9Hc |
| Size | ~34 MB (`messages7.zip`) |
| Recovery | €2.99 until 2026-08-06 |
| **Not the full app** | Telegram export only |

---

## What you have NOW (live source of truth)

**Replit workspace** still contains the live app (your EXPORT.sh output proves it):

- `bacbo_royal_complete.py`
- `bot/` (live gates, db, handlers)
- `bot_LEGACY_JULY_16/` (July 16 snapshot — extra weight)
- Hub scripts (`HUBMAX.sh`, `REPLIT_*.sh`)

This **is** the whole app — same content family as the dead YDRAY zip, plus newer patches.

---

## If contacting YDRAY support

Ask recovery for transfer **`u17818127167255IdjZb8f932d8c217QL`**, file **`21051862`**, hash **`7e83b1446f704866377e1be327b6cc0b`**. Paid recovery may not be offered for free-tier 7-day expiry.

---

## Rescue path (no old YDRAY)

```bash
# On Replit — slim export (skip legacy bloat)
EXPORT_MODE=slim bash REPLIT_EXPORT_FULL_APP.sh
# Upload new zip to YDRAY/Drive → paste link in Cursor
# On cloud agent:
YDRAY_URL='https://ydray.com/get/t/NEW_ID' bash download_ydray_full_app.sh
```
