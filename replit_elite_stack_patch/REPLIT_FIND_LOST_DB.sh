#!/usr/bin/env bash
# Hunt for lost/truncated bacbo.db copies anywhere on workspace.
# Run after export shows suspiciously small db (e.g. 239M instead of 3.2G).
#
#   curl -fsSL -H 'Cache-Control: no-cache' -o FIND_DB.sh \
#     'https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/cursor/add-engine-gate-registry-d5ba/replit_elite_stack_patch/REPLIT_FIND_LOST_DB.sh'
#   bash FIND_DB.sh > find_db_report.txt 2>&1
#   cat find_db_report.txt
set -euo pipefail
cd /home/runner/workspace 2>/dev/null || cd "$(dirname "$0")/.."

echo "========== DISK =========="
df -h .
du -sh . bot bot_LEGACY_JULY_16 bot_broken_backup_* 2>/dev/null || true

echo
echo "========== LIVE bot/bacbo.db =========="
if [ -f bot/bacbo.db ]; then
  ls -lah bot/bacbo.db bot/bacbo.db-wal bot/bacbo.db-shm 2>/dev/null || ls -lah bot/bacbo.db
  python3 - <<'PY' 2>/dev/null || true
import sqlite3
from pathlib import Path
p = Path("bot/bacbo.db")
con = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
for q, label in [
    ("SELECT COUNT(*) FROM consensus_signals", "consensus_signals"),
    ("SELECT MIN(fired_at), MAX(fired_at) FROM consensus_signals", "fired range"),
    ("SELECT COUNT(*) FROM rooms", "rooms"),
]:
    try:
        print(label, con.execute(q).fetchone())
    except Exception as e:
        print(label, "ERR", e)
con.close()
print("size_bytes", p.stat().st_size)
PY
else
  echo "MISSING bot/bacbo.db"
fi

echo
echo "========== ALL .db files >10MB (sorted by size) =========="
find . -type f \( -name '*.db' -o -name '*.sqlite' -o -name '*.sqlite3' \) -size +10M 2>/dev/null \
  | while read -r f; do ls -lah "$f"; done | sort -k5 -hr | head -30

echo
echo "========== backup folders =========="
ls -lad bot_broken_backup_* bot_LEGACY_JULY_16 full_replit_app* 2>/dev/null || echo "(none)"
for d in bot_broken_backup_* bot_LEGACY_JULY_16; do
  [ -d "$d" ] && du -sh "$d" && ls -lah "$d/bacbo.db" 2>/dev/null || true
done

echo
echo "========== zip archives =========="
find . -maxdepth 2 -name '*.zip' -size +50M -ls 2>/dev/null | head -20

echo
echo "========== wal/shm/bak =========="
find . -type f \( -name 'bacbo.db*' -o -name '*.db-wal' -o -name '*.db-shm' -o -name '*.db.bak*' \) 2>/dev/null \
  | head -40 | while read -r f; do ls -lah "$f"; done

echo
echo "========== VERDICT =========="
MAIN_SZ=$(stat -c%s bot/bacbo.db 2>/dev/null || echo 0)
if [ "$MAIN_SZ" -lt 500000000 ]; then
  echo "WARN: bot/bacbo.db is only $((MAIN_SZ/1024/1024))MB — likely TRUNCATED (expect ~2-3GB for full history)"
  echo "DO NOT upload 239M zip as full backup — search for bot_LEGACY or bot_broken_backup or old zips above"
else
  echo "OK: bot/bacbo.db looks large enough ($((MAIN_SZ/1024/1024))MB)"
fi
echo "DONE FIND_DB"
