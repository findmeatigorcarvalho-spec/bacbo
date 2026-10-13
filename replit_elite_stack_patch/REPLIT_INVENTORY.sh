#!/usr/bin/env bash
# Full inventory of /home/runner/workspace — paste output into Cursor.
set -euo pipefail
cd /home/runner/workspace 2>/dev/null || cd "$(dirname "$0")/.."

echo "========== DISK =========="
df -h .
echo
du -sh . bot bot_LEGACY_JULY_16 logs 2>/dev/null || true

echo
echo "========== LIVE ENGINE (what actually runs) =========="
for f in \
  bacbo_royal_complete.py \
  bot/bacbo.db \
  bot/signal_handler.py \
  bot/main.py \
  bot/database.py \
  bot/state.py \
  bot/floor_tracker.py \
  .telegram_session_string \
  .env \
  luxury_building.env \
  .replit
do
  if [ -e "$f" ]; then ls -lah "$f"; else echo "MISSING $f"; fi
done

echo
echo "========== LIVE GATES (bot/_gates_*.py) =========="
ls -1 bot/_gates_*.py 2>/dev/null | wc -l | xargs echo "count"
ls -1 bot/_gates_*.py 2>/dev/null | head -20
echo "..."
ls -1 bot/_gates_*.py 2>/dev/null | tail -10

echo
echo "========== LEGACY SNAPSHOT bot_LEGACY_JULY_16 =========="
if [ -d bot_LEGACY_JULY_16 ]; then
  du -sh bot_LEGACY_JULY_16
  echo "gates:"; ls -1 bot_LEGACY_JULY_16/_gates_*.py 2>/dev/null | wc -l
  echo "logs:"; ls -lah bot_LEGACY_JULY_16/bot.log* bot_LEGACY_JULY_16/bot_output.log 2>/dev/null || true
  echo "core:"; ls -1 bot_LEGACY_JULY_16/{main.py,signal_handler.py,database.py,config.py} 2>/dev/null
else
  echo "(not present)"
fi

echo
echo "========== TOP 30 LARGEST FILES =========="
find . -type f -printf '%s\t%p\n' 2>/dev/null | sort -rn | head -30 | awk '{printf "%.1f MB\t%s\n", $1/1024/1024, $2}'

echo
echo "========== PROCESSES =========="
pgrep -af 'bacbo_royal|runtime_supervisor|telegram_outbox|fallback_' 2>/dev/null || echo "(none)"

echo
echo "========== ZIPS IN ROOT =========="
ls -lah *.zip 2>/dev/null || echo "(none)"

echo
echo "========== PATCH / HUB SCRIPTS =========="
ls -lah REPLIT_*.sh HUBMAX.sh install_*.py 2>/dev/null | head -20

echo
echo "========== DB QUICK STATS =========="
python3 - <<'PY' 2>/dev/null || echo "(db skip)"
import sqlite3
from pathlib import Path
db = Path("bot/bacbo.db")
if not db.exists():
    print("no bot/bacbo.db")
    raise SystemExit
con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")]
print("tables", len(tables), sorted(tables)[:15], "...")
if "consensus_signals" in tables:
    n = con.execute("SELECT COUNT(*) FROM consensus_signals").fetchone()[0]
    mx = con.execute("SELECT MAX(id), MAX(fired_at) FROM consensus_signals").fetchone()
    print("consensus_signals rows", n, "max_id", mx[0], "last_fired", mx[1])
if "rooms" in tables:
    print("rooms", con.execute("SELECT COUNT(*) FROM rooms").fetchone()[0])
con.close()
print("db_size_gb", round(db.stat().st_size/1024/1024/1024, 2))
PY

echo "DONE INVENTORY"
