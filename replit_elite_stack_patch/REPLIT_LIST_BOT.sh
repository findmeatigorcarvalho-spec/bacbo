#!/usr/bin/env bash
# List EVERY file under bot/ — size, date, path. No filters, no name guessing.
#   curl -fsSL -H 'Cache-Control: no-cache' -o LIST_BOT.sh \
#     'https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/cursor/add-engine-gate-registry-d5ba/replit_elite_stack_patch/REPLIT_LIST_BOT.sh'
#   bash LIST_BOT.sh | tee list_bot_report.txt
set -euo pipefail
cd /home/runner/workspace 2>/dev/null || cd "$(dirname "$0")/.."

echo "========== bot/ TOTAL =========="
du -sh bot 2>/dev/null || { echo "no bot/"; exit 1; }
du -ah bot 2>/dev/null | sort -hr | head -80

echo ""
echo "========== EVERY FILE in bot/ (sorted by size) =========="
find bot -type f 2>/dev/null | while read -r f; do
  stat -c '%s %Y %n' "$f" 2>/dev/null
done | sort -rn | while read -r sz epoch path; do
  printf '%10s  %s  %s\n' "$(numfmt --to=iec "$sz" 2>/dev/null || echo "$sz")" \
    "$(date -u -d "@$epoch" +%Y-%m-%dT%H:%MZ 2>/dev/null || echo '?')" "$path"
done

echo ""
echo "========== SQLITE magic in bot/ (any extension) =========="
find bot -type f -size +1k 2>/dev/null | while read -r f; do
  if head -c 16 "$f" 2>/dev/null | grep -q 'SQLite format 3'; then
    ls -lah "$f"
  fi
done

echo ""
echo "========== DONE LIST_BOT =========="
