#!/usr/bin/env bash
# Recover archaeology output after Replit shell/UI wipe (OOM / reconnect).
# The terminal can vanish while files on disk remain.
#
#   curl -fsSL -o TG_RECOVER.sh \
#     'https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/80eb019/replit_elite_stack_patch/REPLIT_TG_ARCH_RECOVER.sh'
#   bash TG_RECOVER.sh
set -euo pipefail
cd /home/runner/workspace 2>/dev/null || cd "$(pwd)"
echo "RECOVER cwd=$(pwd) $(date -u +%Y%m%dT%H%M%SZ)"

echo "=== hunt archaeology artifacts ==="
FOUND=0
for p in \
  tg_archaeology \
  tg_archaeology_*.zip \
  /tmp/tg_archaeology* \
  /tmp/tg_arch* \
  all_messages.csv \
  types_first_seen.csv \
  eras_auto.md \
  report.txt
do
  for f in $p; do
    if [[ -e "$f" ]]; then
      FOUND=1
      if [[ -d "$f" ]]; then
        echo "DIR  $f"
        du -sh "$f" 2>/dev/null || true
        ls -lah "$f" 2>/dev/null || true
      else
        ls -lah "$f" 2>/dev/null || true
      fi
    fi
  done
done

echo ""
echo "=== broader find (may take a few seconds) ==="
find /home/runner/workspace /tmp -maxdepth 3 \
  \( -name 'tg_archaeology*' -o -name 'all_messages.csv' -o -name 'types_first_seen.csv' \
     -o -name 'eras_auto.md' -o -name 'types_summary.json' \) \
  2>/dev/null | head -50

if [[ -f tg_archaeology/report.txt ]]; then
  echo ""
  echo "=== report.txt (head) ==="
  head -n 80 tg_archaeology/report.txt
fi
if [[ -f tg_archaeology/types_first_seen.csv ]]; then
  echo ""
  echo "=== types_first_seen.csv (all) ==="
  cat tg_archaeology/types_first_seen.csv
fi
if [[ -f tg_archaeology/eras_auto.md ]]; then
  echo ""
  echo "=== eras_auto.md ==="
  cat tg_archaeology/eras_auto.md
fi
if [[ -f tg_archaeology/all_messages.csv ]]; then
  echo ""
  echo "=== all_messages.csv stats ==="
  wc -l tg_archaeology/all_messages.csv
  echo "first rows:"
  head -n 3 tg_archaeology/all_messages.csv
  echo "last rows:"
  tail -n 3 tg_archaeology/all_messages.csv
fi

# Partial / crash dumps
echo ""
echo "=== partial dumps ==="
ls -lah tg_archaeology/*.csv tg_archaeology/*.jsonl tg_archaeology/*.partial 2>/dev/null || echo "(none)"

STAMP=$(date -u +%Y%m%dT%H%M%SZ)
if [[ -d tg_archaeology ]] && [[ -n "$(ls -A tg_archaeology 2>/dev/null)" ]]; then
  ZIP="tg_archaeology_RECOVERED_${STAMP}.zip"
  zip -r -q "$ZIP" tg_archaeology
  ls -lah "$ZIP"
  echo ""
  echo "RECOVERED ZIP: $ZIP"
  echo "Upload this zip (Replit → download) or paste:"
  echo "  cat tg_archaeology/report.txt"
  echo "  cat tg_archaeology/types_first_seen.csv"
else
  echo ""
  echo "NO archaeology output folder with files."
  echo "The scrape likely died BEFORE writing finals (all rows were in RAM)."
  echo "Re-run the NEW arch script (incremental flush) — SHA below."
fi

echo ""
echo "If empty: re-run scrape with incremental writer:"
echo "  curl -fsSL -o TG_ARCH.sh \\"
echo "    'https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/cursor/add-engine-gate-registry-d5ba/replit_elite_stack_patch/REPLIT_TELEGRAM_TYPE_ARCHAEOLOGY.sh?v=incr1'"
echo "  bash TG_ARCH.sh"
echo "Look for ARCH_VERSION=20260803e and lines like 'flushed N msgs'."
