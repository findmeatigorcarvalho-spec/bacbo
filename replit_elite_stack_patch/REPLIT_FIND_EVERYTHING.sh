#!/usr/bin/env bash
# Find EVERYTHING on Replit — not by name. By size, date, git history, btrfs, assets.
# Run on Replit:
#   curl -fsSL -H 'Cache-Control: no-cache' -o FIND_EVERYTHING.sh \
#     'https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/cursor/add-engine-gate-registry-d5ba/replit_elite_stack_patch/REPLIT_FIND_EVERYTHING.sh'
#   bash FIND_EVERYTHING.sh 2>&1 | tee find_everything_report.txt
set -euo pipefail
cd /home/runner/workspace 2>/dev/null || cd "$(dirname "$0")/.."
REPORT="${1:-find_everything_report.txt}"

log() { echo "[$(date -u +%H:%M:%S)] $*" | tee -a "$REPORT"; }

: > "$REPORT"
log "=== REPLIT_FIND_EVERYTHING — full inventory, no name filter ==="
log "pwd=$(pwd) host=$(hostname 2>/dev/null || true)"

# ── A. Every file in workspace sorted by size ────────────────────────────────
log ""
log "========== A. ALL FILES >1MB (workspace, any name, sorted by size) =========="
find . -xdev -type f -size +1M 2>/dev/null \
  | while read -r f; do stat -c '%s %Y %n' "$f" 2>/dev/null; done \
  | sort -rn | head -200 \
  | while read -r sz epoch path; do
      printf '%10s  %s  %s\n' "$(numfmt --to=iec "$sz" 2>/dev/null || echo "${sz}B")" \
        "$(date -u -d "@$epoch" +%Y-%m-%dT%H:%MZ 2>/dev/null || echo '?')" "$path"
    done | tee -a "$REPORT"

log ""
log "========== B. ALL FILES >1MB under /home/runner (entire VM home) =========="
find /home/runner -xdev -type f -size +1M 2>/dev/null \
  | while read -r f; do stat -c '%s %Y %n' "$f" 2>/dev/null; done \
  | sort -rn | head -100 \
  | while read -r sz epoch path; do
      printf '%10s  %s  %s\n' "$(numfmt --to=iec "$sz" 2>/dev/null || echo "${sz}B")" \
        "$(date -u -d "@$epoch" +%Y-%m-%dT%H:%MZ 2>/dev/null || echo '?')" "$path"
    done | tee -a "$REPORT"

# ── C. BTRFS snapshots (Replit uses btrfs on /dev/vdd) ─────────────────────
log ""
log "========== C. BTRFS / SNAPSHOTS =========="
{
  df -hT /home/runner/workspace 2>/dev/null || true
  echo "--- btrfs subvolumes ---"
  btrfs subvolume list /home/runner/workspace 2>/dev/null || echo "(btrfs subvolume list unavailable)"
  echo "--- .snapshots dirs ---"
  find /home/runner -maxdepth 4 -type d \( -name '.snapshots' -o -name 'snapshots' -o -name '@*' \) 2>/dev/null | head -20
  echo "--- hidden snapshot paths ---"
  find /mnt -maxdepth 3 -type d 2>/dev/null | head -30 || true
} | tee -a "$REPORT"

# ── D. Git — entire history, large blobs, all branches ─────────────────────
log ""
log "========== D. GIT HISTORY (since day 1) =========="
{
  if [ -d .git ]; then
    echo "branches:"; git branch -a 2>/dev/null | head -30
    echo "first_commit:"; git log --reverse --oneline 2>/dev/null | head -3
    echo "last_commit:"; git log -1 --oneline 2>/dev/null
    echo "total_commits:"; git rev-list --count HEAD 2>/dev/null || echo 0
    echo "--- largest blobs ever in git ---"
    git rev-list --objects --all 2>/dev/null \
      | git cat-file --batch-check='%(objecttype) %(objectname) %(objectsize) %(rest)' 2>/dev/null \
      | awk '/^blob/ {if($3>100000) print $3, $4}' | sort -rn | head -40
    echo "--- files ever tracked >100KB (git log --all) ---"
    git log --all --pretty=format: --name-only 2>/dev/null | sort -u | while read -r f; do
      [ -n "$f" ] && [ -f "$f" ] && sz=$(stat -c%s "$f" 2>/dev/null || echo 0) && [ "$sz" -gt 102400 ] && ls -lah "$f"
    done 2>/dev/null | sort -k5 -hr | head -40
    echo "--- git stash / reflog ---"
    git stash list 2>/dev/null || true
    git reflog 2>/dev/null | head -15 || true
  else
    echo "no .git directory"
  fi
} | tee -a "$REPORT"

# ── E. attached_assets (485MB in your report) ─────────────────────────────
log ""
log "========== E. attached_assets (full tree) =========="
{
  if [ -d attached_assets ]; then
    du -ah attached_assets 2>/dev/null | sort -hr | head -60
    echo "--- file types ---"
    find attached_assets -type f 2>/dev/null | sed 's/.*\.//' | sort | uniq -c | sort -rn | head -20
  else
    echo "(no attached_assets/)"
  fi
} | tee -a "$REPORT"

# ── F. All export / luxury / may_jul packs ─────────────────────────────────
log ""
log "========== F. EXPORT PACKS (luxury, may_jul, zips) =========="
{
  for z in luxury_full_pack.zip luxury_export_light.zip bacbo_db_only*.zip bacbo_app_databases*.zip; do
    [ -f "$z" ] && echo "ZIP $z" && unzip -l "$z" 2>/dev/null | tail -5 && ls -lah "$z"
  done
  for d in luxury_export_* may_jul_export_*; do
    [ -d "$d" ] && echo "DIR $d" && du -sh "$d" && find "$d" -type f | head -30
  done
} | tee -a "$REPORT"

# ── G. SQLite anywhere (magic header, not filename) ───────────────────────
log ""
log "========== G. EVERY SQLITE FILE (magic scan, all sizes >100KB) =========="
{
  find . -xdev -type f -size +100k 2>/dev/null | while read -r f; do
    if head -c 16 "$f" 2>/dev/null | grep -q 'SQLite format 3'; then
      ls -lah "$f"
    fi
  done | sort -k5 -hr
} | tee -a "$REPORT"

# ── H. What's INSIDE the live DB (your actual knowledge base) ───────────────
log ""
log "========== H. LIVE DB — ALL TABLES + DATE RANGES =========="
python3 - <<'PY' 2>&1 | tee -a "$REPORT"
import sqlite3
from pathlib import Path

p = Path("bot/bacbo.db")
if not p.exists():
    print("no bot/bacbo.db"); raise SystemExit
con = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
print(f"db={p} size_mb={p.stat().st_size/1024/1024:.1f}")
tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY 1")]
for t in tables:
    try:
        n = con.execute(f"SELECT COUNT(*) FROM [{t}]").fetchone()[0]
        extra = ""
        for col in ("fired_at", "created_at", "ts", "timestamp", "sent_at", "recorded_at"):
            try:
                mn, mx = con.execute(f"SELECT MIN([{col}]), MAX([{col}]) FROM [{t}]").fetchone()
                if mn: extra = f" {col}={mn}..{mx}"; break
            except Exception:
                pass
        print(f"  {t}: {n:,}{extra}")
    except Exception as e:
        print(f"  {t}: ERR {e}")
# Sample channel_messages — often holds months of Telegram
try:
    sample = con.execute("SELECT id, substr(content,1,120) FROM channel_messages ORDER BY id DESC LIMIT 3").fetchall()
    print("channel_messages_latest:", sample)
except Exception as e:
    print("channel_messages sample ERR", e)
con.close()
PY

# ── I. logs, .local, .cache breakdown ─────────────────────────────────────
log ""
log "========== I. logs / .local / .cache breakdown =========="
{
  for d in logs .local .cache .config .pythonlibs artifacts scripts reports; do
    [ -d "$d" ] && echo "--- $d ---" && du -ah "$d" 2>/dev/null | sort -hr | head -25
  done
} | tee -a "$REPORT"

# ── J. Files by age — oldest still on disk ─────────────────────────────────
log ""
log "========== J. OLDEST 40 FILES (by mtime — day 1 survivors) =========="
find . -xdev -type f 2>/dev/null | while read -r f; do
  stat -c '%Y %s %n' "$f" 2>/dev/null
done | sort -n | head -40 | while read -r epoch sz path; do
  printf '%s  %8s  %s\n' "$(date -u -d "@$epoch" +%Y-%m-%d 2>/dev/null || echo '?')" \
    "$(numfmt --to=iec "$sz" 2>/dev/null || echo "$sz")" "$path"
done | tee -a "$REPORT"

# ── K. Verdict + next export commands ─────────────────────────────────────
log ""
log "========== K. VERDICT + SAVE EVERYTHING NOW =========="
BIG=$(find /home/runner -xdev -type f -size +500M 2>/dev/null | wc -l)
log "files_over_500MB=$BIG"
log ""
log "To save ALL knowledge still on disk (run after this report):"
log "  curl -fsSL -H 'Cache-Control: no-cache' -o SAVE_ALL.sh \\"
log "    'https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/cursor/add-engine-gate-registry-d5ba/replit_elite_stack_patch/REPLIT_SAVE_EVERYTHING.sh'"
log "  bash SAVE_ALL.sh"
log "=== DONE FIND_EVERYTHING ==="
