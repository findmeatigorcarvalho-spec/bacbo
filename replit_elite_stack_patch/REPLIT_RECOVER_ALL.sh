#!/usr/bin/env bash
# ONE-PASTE full recovery on Replit — find, deep-scan, auto-copy /proc handles, export hits.
#
#   cd /home/runner/workspace
#   curl -fsSL -H 'Cache-Control: no-cache' -o RECOVER_ALL.sh \
#     'https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/cursor/add-engine-gate-registry-d5ba/replit_elite_stack_patch/REPLIT_RECOVER_ALL.sh'
#   bash RECOVER_ALL.sh
#
# Output: recover_all_report.txt (+ any RECOVERED_*.db / FOUND_*.zip copied to workspace)
set -euo pipefail
cd /home/runner/workspace 2>/dev/null || cd "$(dirname "$0")/.."

REPORT="recover_all_report.txt"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
RECOV_DIR="./_recovery_${STAMP}"
mkdir -p "$RECOV_DIR"

log() { echo "[$(date -u +%H:%M:%S)] $*" | tee -a "$REPORT"; }

: > "$REPORT"
log "=== REPLIT_RECOVER_ALL start $STAMP ==="
log "pwd=$(pwd)"
log "DO NOT restart python/bacbo until this script finishes (preserves /proc recoverable fds)"

# ── 1. Quick inventory ──────────────────────────────────────────────────────
log ""
log "========== [1/8] DISK + INVENTORY =========="
{
  df -hT 2>/dev/null || df -h
  echo
  du -xh --max-depth=1 . 2>/dev/null | sort -hr | head -30
  echo
  du -xh --max-depth=1 /home/runner 2>/dev/null | sort -hr | head -15
  echo
  ls -lah bacbo_royal_complete.py bot/bacbo.db 2>/dev/null || true
  echo "gates:" "$(ls -1 bot/_gates_*.py 2>/dev/null | wc -l)"
} | tee -a "$REPORT"

# ── 2. All large files on VM ────────────────────────────────────────────────
log ""
log "========== [2/8] FILES >50MB (all /home/runner) =========="
{
  find /home/runner -xdev -type f -size +50M 2>/dev/null | while read -r f; do
    ls -lah "$f"
  done | sort -k5 -hr
} | tee -a "$REPORT"

# ── 3. Archives + named hunt ────────────────────────────────────────────────
log ""
log "========== [3/8] ARCHIVES + NAMED FILES =========="
{
  echo "--- archives >5MB ---"
  find /home/runner -xdev -type f \( \
    -name '*.zip' -o -name '*.tar' -o -name '*.tar.gz' -o -name '*.tgz' \
    -o -name '*.7z' -o -name '*.gz' -o -name '*.bz2' -o -name '*.zst' \
    -o -name '*.rar' \) -size +5M 2>/dev/null | while read -r f; do ls -lah "$f"; done | sort -k5 -hr
  echo "--- names: legacy backup full_replit ydray luxury bacbo ---"
  find /home/runner/workspace -type f \( \
    -iname '*legacy*' -o -iname '*backup*' -o -iname '*full_replit*' \
    -o -iname '*ydray*' -o -iname '*luxury*' -o -iname 'bacbo.db*' \
    \) 2>/dev/null | while read -r f; do ls -lah "$f" 2>/dev/null; done | sort -k5 -hr | head -60
} | tee -a "$REPORT"

# ── 4. SQLite files everywhere ─────────────────────────────────────────────
log ""
log "========== [4/8] ALL SQLITE FILES =========="
{
  find /home/runner/workspace -type f \( -name '*.db' -o -name '*.sqlite' -o -name '*.sqlite3' \) 2>/dev/null \
    | while read -r f; do ls -lah "$f"; done | sort -k5 -hr
  echo "--- magic header scan (files >20MB) ---"
  find /home/runner/workspace -type f -size +20M 2>/dev/null | while read -r f; do
    if head -c 16 "$f" 2>/dev/null | grep -q 'SQLite format 3'; then
      echo "SQLITE $f $(ls -lah "$f" | awk '{print $5}')"
    fi
  done
} | tee -a "$REPORT"

# ── 5. /proc deleted-but-open AUTO COPY ─────────────────────────────────────
log ""
log "========== [5/8] /proc RECOVERY (auto-copy) =========="
PROC_FOUND=0
{
  for pid_dir in /proc/[0-9]*; do
    pid="${pid_dir##*/}"
    for fd in "$pid_dir"/fd/*; do
      [ -r "$fd" ] || continue
      target="$(readlink "$fd" 2>/dev/null || true)"
      sz="$(stat -c%s "$fd" 2>/dev/null || echo 0)"
      case "$target" in
        *bacbo*|*Bac-Bo*|*full_replit*|*YDRAY*|*deleted*)
          if [ "$sz" -gt 10485760 ]; then
            out="${RECOV_DIR}/RECOVERED_pid${pid}_fd${fd##*/}_$((sz/1048576))MB.db"
            echo "COPYING pid=$pid fd=${fd##*/} size=$((sz/1024/1024))MB -> $out"
            echo "  target=$target"
            cp -a "$fd" "$out" && ls -lah "$out"
            PROC_FOUND=1
          else
            echo "small_fd pid=$pid size=$((sz/1024))KB target=$target"
          fi
          ;;
      esac
    done
  done
  if [ "$PROC_FOUND" = "0" ]; then
    echo "No recoverable large deleted-open handles found."
  fi
} | tee -a "$REPORT"

# ── 6. lsof + running processes ─────────────────────────────────────────────
log ""
log "========== [6/8] PROCESSES + OPEN FILES =========="
{
  ps aux 2>/dev/null | grep -E '[p]ython|[b]acbo|[u]vicorn|[g]unicorn' | head -25 || true
  echo "--- lsof bacbo (if available) ---"
  if command -v lsof >/dev/null 2>&1; then
    lsof 2>/dev/null | grep -i bacbo | head -30 || echo "(no lsof bacbo hits)"
  else
    echo "lsof not installed"
  fi
} | tee -a "$REPORT"

# ── 7. DB forensics + WAL checkpoint export ─────────────────────────────────
log ""
log "========== [7/8] DB FORENSICS =========="
python3 - <<'PY' 2>&1 | tee -a "$REPORT"
import os, sqlite3, struct
from pathlib import Path

def inspect_db(p: Path):
    if not p.exists():
        print(f"MISSING {p}")
        return
    sz = p.stat().st_size
    print(f"\n=== {p} size={sz} bytes ({sz/1024/1024:.1f} MB) ===")
    with open(p, "rb") as f:
        hdr = f.read(16)
    print("header", hdr[:16])
    try:
        con = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
        tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY 1")]
        print("tables", len(tables))
        for t in tables:
            try:
                n = con.execute(f"SELECT COUNT(*) FROM [{t}]").fetchone()[0]
                if n:
                    extra = ""
                    if t == "consensus_signals":
                        mn, mx = con.execute("SELECT MIN(fired_at), MAX(fired_at) FROM consensus_signals").fetchone()
                        extra = f" range={mn}..{mx}"
                    print(f"  {t}: {n}{extra}")
            except Exception as e:
                print(f"  {t}: ERR {e}")
        page = con.execute("PRAGMA page_count").fetchone()[0]
        psz = con.execute("PRAGMA page_size").fetchone()[0]
        freelist = con.execute("PRAGMA freelist_count").fetchone()[0]
        print(f"pages={page} page_size={psz} freelist={freelist} theoretical_max={(page*psz)/1024/1024:.1f}MB")
        con.close()
    except Exception as e:
        print("sqlite ERR", e)

for p in [
    Path("bot/bacbo.db"),
    Path("bacbo.db"),
    Path("bot/data/bacbo.db"),
    Path("bot/data/bot_database.db"),
]:
    inspect_db(p)

for wal in [Path("bot/bacbo.db-wal"), Path("bacbo.db-wal")]:
    if wal.exists():
        print(f"\nWAL {wal} size={wal.stat().st_size}")
PY

# If we recovered a large proc copy, inspect it too
for f in "$RECOV_DIR"/RECOVERED_*.db; do
  [ -f "$f" ] || continue
  python3 - <<PY 2>&1 | tee -a "$REPORT"
import sqlite3
from pathlib import Path
p = Path("$f")
con = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
try:
    n = con.execute("SELECT COUNT(*) FROM consensus_signals").fetchone()[0]
    print("RECOVERED", p, "consensus_signals", n, "size_mb", p.stat().st_size//1024//1024)
except Exception as e:
    print("RECOVERED", p, "ERR", e)
con.close()
PY
done

# ── 8. Auto-zip anything large we found ─────────────────────────────────────
log ""
log "========== [8/8] AUTO-EXPORT HITS =========="
EXPORTED=0
{
  # Recovered proc files
  for f in "$RECOV_DIR"/RECOVERED_*.db; do
    [ -f "$f" ] || continue
    sz=$(stat -c%s "$f")
    if [ "$sz" -gt 524288000 ]; then
      zip -0 -q "${RECOV_DIR}/RECOVERED_EXPORT.zip" "$f"
      ln -sf "${RECOV_DIR}/RECOVERED_EXPORT.zip" ./RECOVERED_bacbo_db.zip
      ls -lah "${RECOV_DIR}/RECOVERED_EXPORT.zip" ./RECOVERED_bacbo_db.zip
      EXPORTED=1
    fi
  done
  # Any db >500MB found on disk
  find /home/runner/workspace -type f \( -name 'bacbo.db' -o -name '*.db' \) -size +500M 2>/dev/null | while read -r dbf; do
    z="${RECOV_DIR}/FOUND_$(basename "$dbf")_${STAMP}.zip"
    echo "ZIPPING $dbf -> $z"
    zip -0 -q "$z" "$dbf"
    ls -lah "$z"
    EXPORTED=1
  done
  if [ "$EXPORTED" = "0" ]; then
    echo "Nothing >500MB to auto-export."
    echo "If you get a working YDRAY link, run on Cursor cloud:"
    echo "  YDRAY_URL='https://ydray.com/get/t/NEW_ID' bash download_ydray_full_app.sh"
  fi
} | tee -a "$REPORT"

# ── Verdict ─────────────────────────────────────────────────────────────────
log ""
log "========== VERDICT =========="
BIG=$(find /home/runner -xdev -type f -size +500M 2>/dev/null | wc -l)
WS=$(du -sh . 2>/dev/null | awk '{print $1}')
log "workspace_size=$WS  files_over_500MB=$BIG  proc_recovered=$PROC_FOUND"
if [ "$BIG" -gt 0 ] || [ "$PROC_FOUND" -eq 1 ]; then
  log "SUCCESS: large data found — upload RECOVERED_bacbo_db.zip or FOUND_*.zip to YDRAY/Drive NOW"
else
  log "No 500MB+ file on this VM. Full 7.4GB archive must come from:"
  log "  (A) YDRAY transfer u17818127167255IdjZb8f932d8c217QL — new/restored link"
  log "  (B) Your PC Downloads — YDRAY-Bac-Bo-Watcher-replit-full-app-audit-for-cursor-Ai.zip"
  log "  (C) Replit platform backup snapshot (before Aug 1)"
fi
log "Full log: $(pwd)/$REPORT"
log "Recovery dir: $(pwd)/$RECOV_DIR"
log "=== DONE RECOVER_ALL ==="

ls -lah "$REPORT" "$RECOV_DIR" 2>/dev/null | tee -a "$REPORT"
