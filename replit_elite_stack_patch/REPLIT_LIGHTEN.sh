#!/usr/bin/env bash
# Diagnose why Replit is heavy + safe cleanup (does NOT delete bacbo.db or session).
#
# Run when Shell is slow / Run button hangs / disk full.
#   cd /home/runner/workspace
#   curl -fsSL -H 'Cache-Control: no-cache' -o LIGHTEN.sh \
#     'https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/cursor/add-engine-gate-registry-d5ba/replit_elite_stack_patch/REPLIT_LIGHTEN.sh'
#   bash LIGHTEN.sh
#
# DO NOT use Replit "Clear" / wipe workspace — you lose the live app if no backup.
set -euo pipefail
cd /home/runner/workspace 2>/dev/null || cd "$(dirname "$0")/.."

echo "========== [1/6] disk + memory =========="
df -h . 2>/dev/null || df -h
free -h 2>/dev/null || true
echo "workspace bytes:"; du -sb . 2>/dev/null | awk '{printf "  total %s GB\n", $1/1024/1024/1024}'

echo
echo "========== [2/6] top 25 largest paths =========="
du -ah . 2>/dev/null | sort -hr | head -25

echo
echo "========== [3/6] critical files (keep) =========="
for f in bacbo_royal_complete.py bot/bacbo.db .telegram_session_string .env luxury_building.env; do
  if [ -f "$f" ]; then
    ls -lah "$f"
  else
    echo "MISSING $f"
  fi
done

echo
echo "========== [4/6] safe cleanup candidates =========="
CANDIDATES=(
  "logs/*.log"
  "logs/*.log.*"
  "bot/logs/*.log"
  "*.zip"
  "bot/*.zip"
  "full_replit_app*.zip"
  "luxury_*.zip"
  "may_jul_export*.zip"
  "bacbo_db_only*.zip"
  "bacbo_royal_complete.py.bak*"
  "bot/signal_handler.py.bak*"
  "__pycache__"
  "bot/__pycache__"
  ".cache"
  "node_modules"
)
for pat in "${CANDIDATES[@]}"; do
  # shellcheck disable=SC2086
  found=$(ls -d $pat 2>/dev/null | head -5 || true)
  if [ -n "$found" ]; then
    echo "-- $pat"
    du -ch $pat 2>/dev/null | tail -1 || true
  fi
done

echo
echo "========== [5/6] running processes (kill duplicates?) =========="
pgrep -af 'bacbo_royal_complete|runtime_supervisor|telegram_outbox|fallback_' 2>/dev/null || echo "(none)"

echo
echo "========== [6/6] optional SAFE cleanup (set DO_CLEAN=1) =========="
if [ "${DO_CLEAN:-0}" = "1" ]; then
  echo "Stopping duplicate bot procs..."
  pkill -9 -f 'bacbo_royal_complete.py' 2>/dev/null || true
  pkill -9 -f 'runtime_supervisor.py' 2>/dev/null || true
  pkill -9 -f 'telegram_outbox.py' 2>/dev/null || true
  sleep 1

  echo "Trimming logs >50MB..."
  find logs bot/logs -type f -name '*.log*' -size +50M -print -delete 2>/dev/null || true

  echo "Removing old zip exports (NOT bot/bacbo.db)..."
  rm -f full_replit_app*.zip luxury_*.zip may_jul_export*.zip bacbo_db_only*.zip 2>/dev/null || true
  rm -f *.zip 2>/dev/null || true

  echo "Removing pycache..."
  find . -type d -name '__pycache__' -prune -exec rm -rf {} + 2>/dev/null || true

  if [ -f bot/bacbo.db ]; then
    echo "SQLite VACUUM (can take minutes on 2GB+ db)..."
    python3 - <<'PY'
import sqlite3
from pathlib import Path
db = Path("bot/bacbo.db")
if db.exists():
    con = sqlite3.connect(str(db), timeout=120)
    con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    con.execute("VACUUM")
    con.close()
    print("vacuum done", db.stat().st_size)
PY
  fi

  echo "After cleanup:"
  df -h .
  du -ah . 2>/dev/null | sort -hr | head -15
else
  cat <<'EOF'

SAFE NEXT STEPS (no full wipe):
  1) Paste sections [2] and [3] output here so we see what is heavy.
  2) Re-run with cleanup:
       DO_CLEAN=1 bash LIGHTEN.sh
  3) If still heavy: move bot/bacbo.db to external backup, then VACUUM.
  4) Do NOT use Replit "Clear workspace" unless you have a fresh YDRAY/Drive backup.

WHY Replit feels heavy (usual suspects):
  - bot/bacbo.db often 2–3 GB (main weight)
  - logs/bot_live.log growing without rotation
  - multiple full_replit_app*.zip / luxury_*.zip copies
  - duplicate bacbo + supervisor + outbox processes
  - __pycache__ / .pythonlibs / node_modules

EOF
fi

echo "DONE LIGHTEN"
