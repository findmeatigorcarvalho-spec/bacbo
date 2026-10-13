#!/usr/bin/env bash
# Complete skin/floor census on Replit (CODE + Telegram types + live bacbo.db).
#
#   curl -fsSL -H 'Cache-Control: no-cache' -o CENSUS.sh \
#     'https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/cursor/add-engine-gate-registry-d5ba/replit_elite_stack_patch/REPLIT_SKIN_FLOOR_CENSUS.sh'
#   bash CENSUS.sh
#   # paste FETCH_URL= back to Cursor
set -euo pipefail
cd /home/runner/workspace 2>/dev/null || cd "$(pwd)"
ROOT="$(pwd)"
PY="${PYTHON:-python3}"
BR="cursor/add-engine-gate-registry-d5ba"
RAW="https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/${BR}"

mkdir -p bot/config bot/data replit_elite_stack_patch
for rel in \
  bot/config/__init__.py \
  bot/config/registry.py \
  bot/config/skin_families.py \
  bot/config/skin_gate.py \
  bot/config/skin_census.py
do
  curl -fsSL -H 'Cache-Control: no-cache' -o "$rel" "${RAW}/${rel}?v=$(date +%s)" || true
done

# Prefer full archaeology types CSV if present from prior scrape
TG_CSV=""
for cand in \
  tg_arch_*/types_first_seen.csv \
  bot/data/tg_arch_*/types_first_seen.csv \
  replit_elite_stack_patch/tg_archaeology_*/types_first_seen.csv \
  /tmp/tg_arch*/types_first_seen.csv
do
  for f in $cand; do
    if [[ -f "$f" ]]; then TG_CSV="$f"; break 2; fi
  done
done

DB=""
for cand in bot/bacbo.db bacbo.db data/bacbo.db; do
  if [[ -f "$cand" ]]; then DB="$cand"; break; fi
done

export PYTHONPATH="$ROOT:${PYTHONPATH:-}"
OUT_JSON="bot/data/skin_floor_census.json"
OUT_CSV="bot/data/skin_floor_census.csv"
OUT_MD="replit_elite_stack_patch/SKIN_FLOOR_CENSUS.md"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
ZIP="skin_floor_census_${STAMP}.zip"

ARGS=( -m bot.config.skin_census --out-json "$OUT_JSON" --out-csv "$OUT_CSV" --out-md "$OUT_MD" )
[[ -n "$TG_CSV" ]] && ARGS+=( --tg-csv "$TG_CSV" )
[[ -n "$DB" ]] && ARGS+=( --db "$DB" )

echo "[CENSUS] tg_csv=${TG_CSV:-NONE} db=${DB:-NONE}"
$PY "${ARGS[@]}"

zip -q "$ZIP" "$OUT_JSON" "$OUT_CSV" "$OUT_MD" 2>/dev/null || \
  tar -czf "${ZIP%.zip}.tgz" "$OUT_JSON" "$OUT_CSV" "$OUT_MD"

UPLOAD="$ZIP"
[[ -f "$ZIP" ]] || UPLOAD="${ZIP%.zip}.tgz"

# Prefer litterbox / catbox / transfer helpers if present
FETCH=""
if [[ -f replit_elite_stack_patch/REPLIT_TG_ARCH_UPLOAD.sh ]]; then
  # reuse upload style: try catbox/litterbox
  :
fi
if command -v curl >/dev/null; then
  FETCH=$(curl -fsS -F "reqtype=fileupload" -F "time=72h" -F "fileToUpload=@${UPLOAD}" \
    https://litterbox.catbox.moe/resources/internals/api.php 2>/dev/null || true)
  if [[ -z "$FETCH" ]]; then
    FETCH=$(curl -fsS -F "reqtype=fileupload" -F "fileToUpload=@${UPLOAD}" \
      https://catbox.moe/user/api.php 2>/dev/null || true)
  fi
fi

echo "========== PASTE TO CURSOR =========="
echo "FETCH_URL=${FETCH:-LOCAL_ONLY:$ROOT/$UPLOAD}"
echo "CENSUS_JSON=$ROOT/$OUT_JSON"
echo "CENSUS_CSV=$ROOT/$OUT_CSV"
echo "DB=${DB:-MISSING}"
echo "TG_CSV=${TG_CSV:-MISSING}"
echo "====================================="
