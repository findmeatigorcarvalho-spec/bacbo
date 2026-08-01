#!/usr/bin/env bash
# Fast DB export — no WAL checkpoint (avoids hang on 3.2GB bacbo.db).
# Writes progress to export_status.txt every step (cat that file if paste truncates).
#
# Replit one-paste:
#   cd /home/runner/workspace
#   curl -fsSL -H 'Cache-Control: no-cache' -o EXPORT_DB.sh \
#     'https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/cursor/add-engine-gate-registry-d5ba/replit_elite_stack_patch/REPLIT_EXPORT_DB_FAST.sh'
#   bash EXPORT_DB.sh
set -euo pipefail
cd /home/runner/workspace 2>/dev/null || cd "$(dirname "$0")/.."

STATUS="export_status.txt"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
log() { echo "[$(date -u +%H:%M:%S)] $*" | tee -a "$STATUS"; }

: > "$STATUS"
log "=== REPLIT_EXPORT_DB_FAST start stamp=$STAMP ==="
log "pwd=$(pwd) df=$(df -h . | tail -1)"

# App databases only (skip .gemini / .local / nss junk)
mapfile -t APP_DBS < <(find . \
  \( -path './.git/*' -o -path './node_modules/*' -o -path './.cache/*' \
     -o -path './.gemini/*' -o -path './.local/*' \) -prune -o \
  \( -name 'bacbo.db' -o -name 'bot_database.db' -o -name 'bot.db' \) -type f -size +1k -print 2>/dev/null | sort)

log "app db files (${#APP_DBS[@]}):"
for f in "${APP_DBS[@]}"; do
  log "  $(ls -lah "$f" | awk '{print $5, $9}')"
done

MAIN_DB=""
for candidate in ./bot/bacbo.db ./bacbo.db; do
  if [ -f "$candidate" ]; then MAIN_DB="$candidate"; break; fi
done
if [ -z "$MAIN_DB" ]; then
  log "FATAL: no bot/bacbo.db or ./bacbo.db"
  exit 1
fi
log "main_db=$MAIN_DB size=$(ls -lah "$MAIN_DB" | awk '{print $5}')"

# Optional quick checkpoint — OFF by default (CHECKPOINT=1 to enable)
if [ "${CHECKPOINT:-0}" = "1" ]; then
  log "CHECKPOINT=1 — trying 60s timeout on $MAIN_DB only..."
  timeout 60 python3 - <<PY || log "checkpoint timeout/fail — continuing with live db file"
import sqlite3
from pathlib import Path
p = Path("$MAIN_DB")
con = sqlite3.connect(str(p), timeout=30)
con.execute("PRAGMA wal_checkpoint(PASSIVE)")
con.close()
print("checkpoint passive ok")
PY
else
  log "CHECKPOINT=0 — skipping (prevents hang on 3GB db)"
fi

DBZIP="bacbo_db_only_${STAMP}.zip"
ALLZIP="bacbo_app_databases_${STAMP}.zip"

log "zipping main db -> $DBZIP (store, no compress)..."
rm -f "$DBZIP" bacbo_db_only.zip
zip -0 -q "$DBZIP" "$MAIN_DB"
ln -sf "$DBZIP" bacbo_db_only.zip
log "done $DBZIP $(ls -lah "$DBZIP" | awk '{print $5}')"

log "zipping all app dbs -> $ALLZIP ..."
rm -f "$ALLZIP" bacbo_app_databases.zip
# shellcheck disable=SC2068
zip -0 -q "$ALLZIP" "${APP_DBS[@]}"
ln -sf "$ALLZIP" bacbo_app_databases.zip
log "done $ALLZIP $(ls -lah "$ALLZIP" | awk '{print $5}')"

# Legacy main db separate (optional second copy ~3.2G)
LEGACY="./bot_LEGACY_JULY_16/bacbo.db"
if [ -f "$LEGACY" ] && [ "${INCLUDE_LEGACY:-0}" = "1" ]; then
  LEGZIP="bacbo_legacy_db_${STAMP}.zip"
  log "INCLUDE_LEGACY=1 zipping $LEGACY ..."
  zip -0 -q "$LEGZIP" "$LEGACY"
  ln -sf "$LEGZIP" bacbo_legacy_db.zip
  log "done $LEGZIP $(ls -lah "$LEGZIP" | awk '{print $5}')"
else
  log "legacy db skipped (INCLUDE_LEGACY=0). Set INCLUDE_LEGACY=1 for second 3.2G copy."
fi

log "=== DONE ==="
log "Upload these to YDRAY or Google Drive:"
log "  $(pwd)/$DBZIP"
log "  $(pwd)/bacbo_db_only.zip"
log "  $(pwd)/$ALLZIP"
log "  $(pwd)/bacbo_app_databases.zip"
log "Paste link here. cat export_status.txt for full log."

ls -lah "$DBZIP" "$ALLZIP" bacbo_db_only.zip bacbo_app_databases.zip 2>/dev/null | tee -a "$STATUS"
