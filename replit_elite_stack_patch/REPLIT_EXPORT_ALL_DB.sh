#!/usr/bin/env bash
# Export ALL database files + full 7GB+ workspace from Replit.
#
# Creates:
#   bacbo_all_databases_<stamp>.zip   — every .db/.sqlite found (store, fast)
#   full_replit_app_full_<stamp>.zip   — entire workspace incl. bot_LEGACY_JULY_16
#   bacbo_db_only_<stamp>.zip         — bot/bacbo.db only
#   EXPORT_MANIFEST_<stamp>.txt       — paths + sizes
#
# One paste (Replit Shell):
#   cd /home/runner/workspace
#   curl -fsSL -H 'Cache-Control: no-cache' -o EXPORT_ALL.sh \
#     'https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/cursor/add-engine-gate-registry-d5ba/replit_elite_stack_patch/REPLIT_EXPORT_ALL_DB.sh'
#   bash EXPORT_ALL.sh
#
# Optional: skip full workspace zip (DBs only):
#   DB_ONLY=1 bash EXPORT_ALL.sh
set -euo pipefail
cd /home/runner/workspace 2>/dev/null || cd "$(dirname "$0")/.."

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DB_ONLY="${DB_ONLY:-0}"
MANIFEST="EXPORT_MANIFEST_${STAMP}.txt"
ALL_DB_ZIP="bacbo_all_databases_${STAMP}.zip"
DBZIP="bacbo_db_only_${STAMP}.zip"
FULLZIP="full_replit_app_full_${STAMP}.zip"

exec > >(tee -a "$MANIFEST") 2>&1

echo "========== EXPORT ALL DB + FULL APP =========="
echo "stamp=$STAMP pwd=$(pwd) DB_ONLY=$DB_ONLY"
date -u

echo
echo "========== [1/6] disk =========="
df -h .
du -sh . bot bot_LEGACY_JULY_16 logs 2>/dev/null || true

echo
echo "========== [2/6] find every database file =========="
if [ "${ALL_DBS:-0}" = "1" ]; then
  mapfile -t DB_FILES < <(find . \
    \( -path './.git/*' -o -path './node_modules/*' -o -path './.cache/*' \) -prune -o \
    \( -name '*.db' -o -name '*.sqlite' -o -name '*.sqlite3' \) -type f -size +1k -print 2>/dev/null | sort)
else
  mapfile -t DB_FILES < <(find . \
    \( -path './.git/*' -o -path './node_modules/*' -o -path './.cache/*' \
       -o -path './.gemini/*' -o -path './.local/*' \) -prune -o \
    \( -name '*.db' -o -name '*.sqlite' -o -name '*.sqlite3' \) -type f -size +1k -print 2>/dev/null | sort)
fi

if [ "${#DB_FILES[@]}" -eq 0 ]; then
  echo "FATAL: no .db/.sqlite files found under $(pwd)"
  exit 1
fi

echo "found ${#DB_FILES[@]} database file(s):"
TOTAL_DB=0
for f in "${DB_FILES[@]}"; do
  sz=$(stat -c%s "$f" 2>/dev/null || stat -f%z "$f")
  TOTAL_DB=$((TOTAL_DB + sz))
  printf '  %12s  %s\n' "$(numfmt --to=iec-i --suffix=B "$sz" 2>/dev/null || echo "${sz}B")" "$f"
done
echo "total db bytes: $(numfmt --to=iec-i --suffix=B "$TOTAL_DB" 2>/dev/null || echo "$TOTAL_DB")"

echo
echo "========== [3/6] SQLite WAL checkpoint (merge -wal into .db) =========="
if [ "${CHECKPOINT:-0}" != "1" ]; then
  echo "CHECKPOINT=0 — skipping (set CHECKPOINT=1 to try; may hang on 3GB db)"
else
  DB_LIST="/tmp/bacbo_db_export_list_${STAMP}.txt"
  printf '%s\n' "${DB_FILES[@]}" > "$DB_LIST"
  timeout 120 python3 - <<PY || echo "WARN: checkpoint timed out — continuing with raw .db files"
import sqlite3
from pathlib import Path
for line in Path("$DB_LIST").read_text().splitlines():
    p = Path(line.strip())
    if not p.exists() or "bacbo.db" not in p.name:
        continue
    try:
        con = sqlite3.connect(str(p), timeout=30)
        con.execute("PRAGMA wal_checkpoint(PASSIVE)")
        con.close()
        print("checkpoint OK", p, p.stat().st_size)
    except Exception as e:
        print("checkpoint SKIP", p, repr(e))
PY
fi

echo
echo "========== [4/6] zip ALL databases (store, no recompress) =========="
rm -f "$ALL_DB_ZIP" bacbo_all_databases.zip
# shellcheck disable=SC2068
zip -0 -q "$ALL_DB_ZIP" "${DB_FILES[@]}"
ln -sf "$ALL_DB_ZIP" bacbo_all_databases.zip
ls -lah "$ALL_DB_ZIP" bacbo_all_databases.zip

if [ -f bot/bacbo.db ]; then
  echo
  echo "========== [4b/6] zip bot/bacbo.db alone =========="
  rm -f "$DBZIP" bacbo_db_only.zip
  zip -0 -q "$DBZIP" bot/bacbo.db
  ln -sf "$DBZIP" bacbo_db_only.zip
  ls -lah "$DBZIP" bacbo_db_only.zip
fi

if [ "$DB_ONLY" = "1" ]; then
  echo
  echo "DB_ONLY=1 — skipping full workspace zip"
else
  echo
  echo "========== [5/6] zip FULL workspace (7GB+ expected) =========="
  echo "This includes bot/, bot_LEGACY_JULY_16/, bacbo_royal_complete.py, gates, etc."
  rm -f "$FULLZIP" full_replit_app.zip full_replit_app_full.zip
  zip -r -1 "$FULLZIP" . \
    -x '*/.git/*' \
    -x '*/node_modules/*' \
    -x '*/.cache/*' \
    -x '*/.pythonlibs/*' \
    -x '*/.upm/*' \
    -x '*.zip' \
    -x 'full_replit_app*.zip' \
    -x 'bacbo_all_databases*.zip' \
    -x 'bacbo_db_only*.zip' \
    -x 'EXPORT_MANIFEST_*.txt'
  ln -sf "$FULLZIP" full_replit_app.zip
  ln -sf "$FULLZIP" full_replit_app_full.zip
  ls -lah "$FULLZIP" full_replit_app.zip
fi

echo
echo "========== [6/6] DONE — upload these =========="
ls -lah "$MANIFEST" "$ALL_DB_ZIP" bacbo_all_databases.zip 2>/dev/null || true
ls -lah "$DBZIP" bacbo_db_only.zip 2>/dev/null || true
ls -lah "$FULLZIP" full_replit_app.zip 2>/dev/null || true

cat <<EOF

UPLOAD to YDRAY or Google Drive, then paste the link in Cursor:

  $(pwd)/$ALL_DB_ZIP          (all .db files)
  $(pwd)/bacbo_all_databases.zip
  $(pwd)/$DBZIP               (main bacbo.db only)
  $(pwd)/$FULLZIP             (full 7GB+ app — if not DB_ONLY)

Manifest: $(pwd)/$MANIFEST

Cursor download after upload:
  YDRAY_URL='https://ydray.com/get/t/YOUR_NEW_ID' \\
  bash replit_elite_stack_patch/download_ydray_full_app.sh

EOF
