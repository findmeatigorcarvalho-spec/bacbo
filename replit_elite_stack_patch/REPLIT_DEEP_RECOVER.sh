#!/usr/bin/env bash
# Aggressive recovery hunt — run on Replit when FIND_DB finds nothing large.
# Finds: other mounts, deleted-but-open DB handles, sqlite blobs, all archives.
#
#   curl -fsSL -H 'Cache-Control: no-cache' -o DEEP.sh \
#     'https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/cursor/add-engine-gate-registry-d5ba/replit_elite_stack_patch/REPLIT_DEEP_RECOVER.sh'
#   bash DEEP.sh | tee deep_recover_report.txt
set -euo pipefail
cd /home/runner/workspace 2>/dev/null || cd "$(dirname "$0")/.."

echo "========== ALL MOUNTS =========="
df -hT 2>/dev/null || df -h
echo
mount | head -30

echo
echo "========== DISK BY TOP-LEVEL (workspace) =========="
du -xh --max-depth=1 . 2>/dev/null | sort -hr | head -25

echo
echo "========== DISK BY TOP-LEVEL (/home/runner) =========="
du -xh --max-depth=1 /home/runner 2>/dev/null | sort -hr | head -20

echo
echo "========== ANY FILE >100MB (entire /home/runner, all types) =========="
find /home/runner -xdev -type f -size +100M 2>/dev/null \
  | while read -r f; do ls -lah "$f"; done | sort -k5 -hr

echo
echo "========== ARCHIVES >10MB (.zip .tar .gz .7z .bz2 .zst) =========="
find /home/runner -xdev -type f \( \
  -name '*.zip' -o -name '*.tar' -o -name '*.tar.gz' -o -name '*.tgz' \
  -o -name '*.7z' -o -name '*.gz' -o -name '*.bz2' -o -name '*.zst' \
  \) -size +10M 2>/dev/null | while read -r f; do ls -lah "$f"; done | sort -k5 -hr | head -40

echo
echo "========== NAMES: legacy | backup | full_replit | ydray | luxury =========="
find /home/runner -xdev -type f \( \
  -iname '*legacy*' -o -iname '*backup*' -o -iname '*full_replit*' \
  -o -iname '*ydray*' -o -iname '*luxury*' -o -iname '*bacbo*' \
  \) -size +1M 2>/dev/null | while read -r f; do ls -lah "$f"; done | sort -k5 -hr | head -50

echo
echo "========== SQLITE MAGIC (files that START with SQLite header, any extension) =========="
# Header: SQLite format 3
find /home/runner/workspace -xdev -type f -size +50M 2>/dev/null | while read -r f; do
  if head -c 16 "$f" 2>/dev/null | grep -q 'SQLite format 3'; then
    ls -lah "$f"
  fi
done
find /home/runner/workspace -xdev -type f \( -name '*.db' -o -name '*.sqlite' -o -name '*.sqlite3' -o -name '*.db-wal' \) 2>/dev/null \
  | while read -r f; do ls -lah "$f"; done | sort -k5 -hr | head -30

echo
echo "========== DELETED BUT STILL OPEN (recoverable via /proc/PID/fd) =========="
# If engine held old 3GB bacbo.db open when file was replaced, data may still be here
FOUND_DEL=0
for pid_dir in /proc/[0-9]*; do
  pid="${pid_dir##*/}"
  for fd in "$pid_dir"/fd/*; do
    [ -r "$fd" ] || continue
    target="$(readlink "$fd" 2>/dev/null || true)"
    case "$target" in
      *bacbo.db*|*full_replit*|*YDRAY*|*deleted*)
        sz="$(stat -c%s "$fd" 2>/dev/null || echo 0)"
        if [ "$sz" -gt 104857600 ]; then
          echo "RECOVERABLE pid=$pid fd=${fd##*/} size=$((sz/1024/1024))MB target=$target"
          echo "  -> cp $fd /home/runner/workspace/RECOVERED_${pid}_${fd##*/}.db"
          FOUND_DEL=1
        fi
        ;;
    esac
  done
done
if [ "$FOUND_DEL" = "0" ]; then
  echo "(no large deleted-but-open bacbo/full_replit handles found)"
fi

echo
echo "========== RUNNING PROCESSES (python/bacbo) =========="
ps aux 2>/dev/null | grep -E '[p]ython|[b]acbo|[r]eplit' | head -20 || true

echo
echo "========== OTHER MOUNTS under /mnt /data /replit =========="
for root in /mnt /data /replit /var /opt; do
  [ -d "$root" ] || continue
  echo "--- $root ---"
  du -sh "$root"/* 2>/dev/null | sort -hr | head -10 || true
done

echo
echo "========== LIVE DB ROW COUNTS =========="
python3 - <<'PY' 2>/dev/null || true
import sqlite3
from pathlib import Path
p = Path("bot/bacbo.db")
if not p.exists():
    print("no bot/bacbo.db")
    raise SystemExit
con = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY 1")]
print("tables", len(tables))
for t in tables:
    try:
        n = con.execute(f"SELECT COUNT(*) FROM [{t}]").fetchone()[0]
        if n > 0:
            print(f"  {t}: {n}")
    except Exception as e:
        print(f"  {t}: ERR {e}")
con.close()
print("size_mb", p.stat().st_size // (1024*1024))
PY

echo
echo "========== VERDICT =========="
WS_BYTES=$(du -sb . 2>/dev/null | awk '{print $1}')
echo "workspace_bytes=$WS_BYTES ($(du -sh . 2>/dev/null | awk '{print $1}'))"
BIG=$(find /home/runner -xdev -type f -size +500M 2>/dev/null | wc -l)
echo "files_over_500MB_under_home_runner=$BIG"
if [ "$BIG" -eq 0 ]; then
  echo "No 500MB+ file exists on this Replit VM right now."
  echo "If 3.2GB bacbo.db existed before, it was removed/replaced — check DELETED BUT STILL OPEN above."
  echo "Next: YDRAY re-download OR search your PC for the 7.4GB zip."
else
  echo "FOUND large files — zip and upload immediately."
fi
echo "DONE DEEP_RECOVER"
