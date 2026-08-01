#!/usr/bin/env bash
# One-paste on Replit: zip the ENTIRE live Bac Bo app for re-upload to YDRAY / Drive.
#
# Creates:
#   full_replit_app.zip          — whole workspace (engine + bot + db + logs slice)
#   bacbo_db_only.zip            — bot/bacbo.db only
#
# Usage (Replit Shell):
#   cd /home/runner/workspace
#   curl -fsSL -H 'Cache-Control: no-cache' -o EXPORT.sh \
#     'https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/cursor/add-engine-gate-registry-d5ba/replit_elite_stack_patch/REPLIT_EXPORT_FULL_APP.sh'
#   bash EXPORT.sh
set -euo pipefail
cd /home/runner/workspace 2>/dev/null || cd "$(dirname "$0")/.."

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
MODE="${EXPORT_MODE:-slim}"   # slim | full
OUT="full_replit_app_${MODE}_${STAMP}.zip"
DBZIP="bacbo_db_only_${STAMP}.zip"

echo "========== [1/4] inventory =========="
ls -lah bacbo_royal_complete.py bot/bacbo.db 2>/dev/null || true
du -sh . bot bot_LEGACY_JULY_16 logs 2>/dev/null || true
echo "EXPORT_MODE=$MODE (slim=live app only; full=includes legacy snapshot)"

echo "========== [2/4] zip workspace =========="
rm -f "$OUT" full_replit_app.zip
ZIP_EXCLUDES=(
  -x '*/.git/*'
  -x '*/__pycache__/*'
  -x '*/node_modules/*'
  -x '*/.cache/*'
  -x '*/.pythonlibs/*'
  -x '*/.upm/*'
  -x 'logs/*'
  -x '*.zip'
  -x 'full_replit_app*.zip'
  -x 'bacbo_db_only*.zip'
)
if [ "$MODE" = "slim" ]; then
  # July-16 frozen copy duplicates gates + huge logs — not needed for live restore.
  ZIP_EXCLUDES+=(
    -x 'bot_LEGACY_JULY_16/*'
    -x 'bot_LEGACY_JULY_16/**'
    -x '*/bot.log*'
    -x '*/bot_output.log'
    -x '*/all_predictions.csv'
  )
fi
zip -r -9 "$OUT" . "${ZIP_EXCLUDES[@]}"
ln -sf "$OUT" full_replit_app.zip
ls -lah "$OUT" full_replit_app.zip

echo "========== [3/4] zip db only =========="
if [ -f bot/bacbo.db ]; then
  zip -0 "$DBZIP" bot/bacbo.db
  ln -sf "$DBZIP" bacbo_db_only.zip
  ls -lah "$DBZIP" bacbo_db_only.zip
else
  echo "WARN: bot/bacbo.db missing"
fi

echo "========== [4/4] NEXT =========="
cat <<EOF

Upload these via YDRAY (or Google Drive) and paste the NEW link in Cursor:

  $(pwd)/$OUT
  $(pwd)/full_replit_app.zip   (symlink)
  $(pwd)/bacbo_db_only.zip     (if created)

Then on the cloud agent VM:
  YDRAY_URL='https://ydray.com/get/t/YOUR_NEW_ID' \\
  bash replit_elite_stack_patch/download_ydray_full_app.sh

EOF
