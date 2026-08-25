#!/usr/bin/env bash
# One-shot Replit export of everything needed to lock the luxury building.
# No system sqlite3 binary required.
set -euo pipefail

ROOT="${HOME}/workspace"
if [ ! -d "$ROOT/bot" ] && [ -d /home/runner/workspace/bot ]; then
  ROOT=/home/runner/workspace
fi
cd "$ROOT"

BRANCH_BASE="https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/cursor/add-engine-gate-registry-d5ba/replit_elite_stack_patch"

echo "[0/6] ensure pull scripts present"
for s in replit_pull_luxury_export.sh replit_pull_may_jul.sh; do
  if [ ! -f "$s" ]; then
    curl -fsSL -o "$s" "$BRANCH_BASE/$s"
  fi
done
chmod +x replit_pull_luxury_export.sh replit_pull_may_jul.sh 2>/dev/null || true

echo "[1/6] luxury_export_light"
bash replit_pull_luxury_export.sh

echo "[2/6] may_jul_export"
bash replit_pull_may_jul.sh

echo "[3/6] regenerate luxury stack reports if tools present"
if [ -f bot/luxury_building_stack.py ] && [ -f bot/bacbo.db ]; then
  python3 -u bot/floor_stack_registry.py --db bot/bacbo.db || true
  python3 -u bot/luxury_building_stack.py --db bot/bacbo.db || true
fi

echo "[4/6] optional DB-only zip (largest, best for Cursor)"
if [ -f bot/bacbo.db ]; then
  rm -f bacbo_db_only.zip
  zip -0 bacbo_db_only.zip bot/bacbo.db
  ls -lah bacbo_db_only.zip
else
  echo "  skip bacbo_db_only.zip — bot/bacbo.db missing"
fi

echo "[5/6] pack master zip"
PACK=luxury_full_pack.zip
rm -f "$PACK"
zip -r -9 "$PACK" \
  luxury_export_light.zip \
  may_jul_export.zip \
  bacbo_db_only.zip \
  luxury_building.env \
  bot/data/luxury_building_stack.json \
  bot/data/luxury_live_floors.json \
  bot/data/floor_stack_registry_report.json \
  bot/data/skyscraper_stack_report.json \
  bot/data/edge_whitelist_engine.json \
  2>/tmp/luxury_full_pack.log || true
ls -lah "$PACK" luxury_export_light.zip may_jul_export.zip 2>/dev/null || true

echo "[6/6] DONE"
echo
echo "Upload these via YDRAY and paste links:"
echo "  $ROOT/luxury_full_pack.zip"
echo "  $ROOT/luxury_export_light.zip"
echo "  $ROOT/may_jul_export.zip"
echo "  $ROOT/bacbo_db_only.zip   (optional but best)"
