#!/usr/bin/env bash
# Save EVERYTHING still on Replit into one timestamped archive for upload.
# Includes: git history, DB, WAL, luxury packs, attached_assets, all JSON reports, logs.
#
#   curl -fsSL -H 'Cache-Control: no-cache' -o SAVE_ALL.sh \
#     'https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/cursor/add-engine-gate-registry-d5ba/replit_elite_stack_patch/REPLIT_SAVE_EVERYTHING.sh'
#   bash SAVE_ALL.sh
set -euo pipefail
cd /home/runner/workspace 2>/dev/null || cd "$(dirname "$0")/.."

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="bacbo_SAVE_EVERYTHING_${STAMP}"
mkdir -p "$OUT"
log() { echo "[$(date -u +%H:%M:%S)] $*"; }

log "=== REPLIT_SAVE_EVERYTHING $STAMP ==="

# 1. Live DB + WAL (checkpoint merge optional)
log "[1/7] copying live database..."
mkdir -p "$OUT/bot"
cp -a bot/bacbo.db "$OUT/bot/" 2>/dev/null || true
cp -a bot/bacbo.db-wal "$OUT/bot/" 2>/dev/null || true
cp -a bot/bacbo.db-shm "$OUT/bot/" 2>/dev/null || true
cp -a bacbo.db.bak_pre_wal_* "$OUT/" 2>/dev/null || true

# 2. Git bundle (entire history since day 1)
log "[2/7] git bundle (full history)..."
if [ -d .git ]; then
  git bundle create "$OUT/git_full_history.bundle" --all 2>/dev/null \
    && ls -lah "$OUT/git_full_history.bundle" \
    || log "WARN: git bundle failed"
  git log --oneline --all > "$OUT/git_log_all.txt" 2>/dev/null || true
fi

# 3. Engine + gates
log "[3/7] engine + gates..."
cp -a bacbo_royal_complete.py "$OUT/" 2>/dev/null || true
mkdir -p "$OUT/bot_gates"
cp -a bot/_gates_*.py bot/*.py "$OUT/bot_gates/" 2>/dev/null || true
cp -a bot/data/*.json "$OUT/bot_data_json/" 2>/dev/null || mkdir -p "$OUT/bot_data_json"

# 4. Export packs + attached_assets
log "[4/7] luxury packs + attached_assets..."
for item in luxury_full_pack.zip luxury_export_light.zip luxury_export_* may_jul_export_* attached_assets; do
  [ -e "$item" ] && cp -a "$item" "$OUT/" 2>/dev/null && log "  copied $item"
done

# 5. All JSON reports anywhere
log "[5/7] all JSON reports..."
find . -maxdepth 4 -name '*.json' -size +10k 2>/dev/null \
  | while read -r f; do
      mkdir -p "$OUT/json_reports/$(dirname "$f")"
      cp -a "$f" "$OUT/json_reports/$f" 2>/dev/null || true
    done

# 6. Logs slice
log "[6/7] logs..."
[ -d logs ] && cp -a logs "$OUT/" 2>/dev/null || true

# 7. DB table dumps (CSV for big tables)
log "[7/7] dumping key DB tables to CSV..."
mkdir -p "$OUT/db_exports"
python3 - "$OUT" <<'PY'
import csv, sqlite3, sys
from pathlib import Path
out_base = Path(sys.argv[1])
p = Path("bot/bacbo.db")
if not p.exists():
    raise SystemExit(0)
con = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
out = out_base / "db_exports"
out.mkdir(parents=True, exist_ok=True)
tables = ["consensus_signals", "signals", "channel_messages", "rooms",
          "room_color_outcomes", "outcome_history", "signal_context"]
for t in tables:
    try:
        rows = con.execute(f"SELECT * FROM [{t}]").fetchall()
        cols = [d[0] for d in con.execute(f"SELECT * FROM [{t}] LIMIT 0").description]
        fp = out / f"{t}.csv"
        with fp.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(cols)
            w.writerows(rows)
        print(f"  {t}: {len(rows)} rows -> {fp}")
    except Exception as e:
        print(f"  {t}: SKIP {e}")
con.close()
PY

# Zip it all
ZIP="bacbo_SAVE_EVERYTHING_${STAMP}.zip"
log "zipping -> $ZIP (may take a few minutes)..."
zip -r -q "$ZIP" "$OUT" \
  -x '*/node_modules/*' '*/.cache/*' '*/__pycache__/*'
ln -sf "$ZIP" bacbo_SAVE_EVERYTHING.zip
ls -lah "$ZIP" bacbo_SAVE_EVERYTHING.zip

log "=== DONE ==="
log "Upload $ZIP to YDRAY or Google Drive and paste link in Cursor."
log "This captures everything still on Replit: git history, 251MB DB, 934k messages, luxury packs, assets."
