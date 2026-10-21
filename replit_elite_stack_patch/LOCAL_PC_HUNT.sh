#!/usr/bin/env bash
# Run on YOUR computer (Mac/Linux) to find saved Bac Bo archives.
#   bash LOCAL_PC_HUNT.sh > pc_hunt_report.txt 2>&1
#   cat pc_hunt_report.txt
#
# Windows: use WSL or search Explorer for:
#   YDRAY-Bac-Bo-Watcher
#   full_replit_app
#   bacbo.db  (sort by size, look for 2-7 GB files)
set -euo pipefail

echo "========== LOCAL PC HUNT $(date -u) =========="
echo "hostname=$(hostname 2>/dev/null || true)"

search_roots=(
  "$HOME/Downloads"
  "$HOME/Desktop"
  "$HOME/Documents"
  "$HOME"
)

names=(
  'YDRAY-Bac-Bo-Watcher*'
  'full_replit_app*'
  'bacbo.db'
  'bacbo_db_only*'
  'Bac-Bo-Watcher*'
)

echo ""
echo "========== BY NAME =========="
for root in "${search_roots[@]}"; do
  [ -d "$root" ] || continue
  for pat in "${names[@]}"; do
    find "$root" -maxdepth 6 -iname "$pat" 2>/dev/null | while read -r f; do
      ls -lah "$f" 2>/dev/null
    done
  done
done | sort -u -k5 -hr | head -40

echo ""
echo "========== LARGE FILES 500MB-15GB (Downloads + Desktop) =========="
for root in "$HOME/Downloads" "$HOME/Desktop" "$HOME/Documents"; do
  [ -d "$root" ] || continue
  find "$root" -maxdepth 5 -type f -size +500M -size -15G 2>/dev/null | while read -r f; do
    ls -lah "$f"
  done
done | sort -k5 -hr | head -30

echo ""
echo "========== SQLITE >200MB anywhere under HOME (slow) =========="
find "$HOME" -maxdepth 8 -type f -size +200M 2>/dev/null | while read -r f; do
  if head -c 16 "$f" 2>/dev/null | grep -q 'SQLite format 3'; then
    ls -lah "$f"
  fi
done | sort -k5 -hr | head -20

echo ""
echo "========== DONE =========="
echo "If you find the 7.4GB zip: upload to fresh YDRAY/Drive and paste link in Cursor."
