#!/usr/bin/env bash
# Find LITERALLY every signal skin/template/kind on the live Replit workspace.
#
#   curl -fsSL -H 'Cache-Control: no-cache' -o FIND_ALL_SKINS.sh \
#     'https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/cursor/add-engine-gate-registry-d5ba/replit_elite_stack_patch/REPLIT_FIND_ALL_SKINS.sh'
#   bash FIND_ALL_SKINS.sh
#   # paste FETCH_URL= back to Cursor
set -euo pipefail
cd /home/runner/workspace 2>/dev/null || cd "$(pwd)"
ROOT="$(pwd)"
PY="${PYTHON:-python3}"
BR="cursor/add-engine-gate-registry-d5ba"
RAW="https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/${BR}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"

mkdir -p bot/config bot/data replit_elite_stack_patch
for rel in \
  bot/config/__init__.py \
  bot/config/registry.py \
  bot/config/skin_families.py \
  bot/config/skin_gate.py \
  bot/config/skin_census.py \
  bot/config/chat_shelves.py \
  bot/config/find_all_skins.py
do
  curl -fsSL -H 'Cache-Control: no-cache' -o "$rel" "${RAW}/${rel}?v=$(date +%s)" || true
done

# Prefer fullest types_first_seen.csv
TG_CSV=""
while IFS= read -r f; do
  [[ -f "$f" ]] || continue
  if [[ -z "$TG_CSV" ]] || [[ $(wc -l < "$f") -gt $(wc -l < "$TG_CSV") ]]; then
    TG_CSV="$f"
  fi
done < <(find "$ROOT" /tmp -name 'types_first_seen.csv' 2>/dev/null | head -50)

DB=""
for cand in bot/bacbo.db bacbo.db data/bacbo.db; do
  [[ -f "$cand" ]] && DB="$cand" && break
done

export PYTHONPATH="$ROOT:${PYTHONPATH:-}"
OUT_JSON="bot/data/literally_everything_skins.json"
OUT_FLOORS="bot/data/literally_everything_floors.json"
OUT_CSV="bot/data/literally_everything_skins.csv"
OUT_FLOORS_CSV="bot/data/literally_everything_floors.csv"
OUT_MD="replit_elite_stack_patch/LITERALLY_EVERYTHING_SKINS.md"
OUT_FLOORS_MD="replit_elite_stack_patch/LITERALLY_EVERYTHING_FLOORS.md"

ARGS=( -m bot.config.find_all_skins --out-json "$OUT_JSON" --out-floors "$OUT_FLOORS" \
  --out-csv "$OUT_CSV" --out-md "$OUT_MD" --repo "$ROOT" )
[[ -n "$TG_CSV" ]] && ARGS+=( --tg-csv "$TG_CSV" )
[[ -n "$DB" ]] && ARGS+=( --db "$DB" )

echo "[FIND_ALL] tg=${TG_CSV:-NONE} db=${DB:-NONE} root=$ROOT"
$PY "${ARGS[@]}"

# Also dump quick path inventory of formatter-ish files for Cursor
LIST="bot/data/template_source_files.txt"
{
  echo "# formatter / string / send / bak files"
  find bot -type f \( \
    -name '*.py' -o -name '*.bak' -o -name '*.py.bak' -o -name '*bak*' -o -name '*.py~' \
  \) 2>/dev/null | sort
  echo "# gates"
  ls -1 bot/_gates_*.py 2>/dev/null || true
  echo "# top-level card-ish"
  ls -1 bot/*string* bot/*signal* bot/*telegram* bot/*outbox* bot/*template* bot/*card* 2>/dev/null || true
  echo "# strings / signal_handler present?"
  ls -la bot/strings.py bot/signal_handler.py bot/telegram_outbox.py 2>/dev/null || true
} > "$LIST" || true

# Pack live card formatters (critical — inventory alone is not enough)
SRC_DIR="bot/data/literally_everything_bot_sources"
mkdir -p "$SRC_DIR"
for f in \
  bot/strings.py \
  bot/signal_handler.py \
  bot/telegram_outbox.py \
  bot/dual_lane_router.py \
  bot/fire_origin.py \
  bot/fallback_signal_sender.py \
  bot/fallback_result_sender.py \
  bot/countdown_alert.py
do
  [[ -f "$f" ]] && cp -a "$f" "$SRC_DIR/" && cp -a "$f".bak* "$SRC_DIR/" 2>/dev/null || true
done
ls bot/_gates_*.py 2>/dev/null | wc -l > "$SRC_DIR/GATES_COUNT.txt" || true
ls bot/_gates_*.py 2>/dev/null > "$SRC_DIR/GATES_LIST.txt" || true

ZIP="literally_everything_skins_${STAMP}.zip"
# Prefer floors + list + sources in zip; full JSON can be huge — include if < 40MB
zip -q "$ZIP" "$OUT_FLOORS" "$OUT_FLOORS_CSV" "$OUT_FLOORS_MD" "$OUT_MD" "$LIST" "$SRC_DIR" 2>/dev/null || true
if [[ -f "$OUT_JSON" ]]; then
  SZ=$(wc -c < "$OUT_JSON" || echo 0)
  if [[ "$SZ" -lt 40000000 ]]; then
    zip -q -u "$ZIP" "$OUT_JSON" "$OUT_CSV" 2>/dev/null || true
  else
    echo "[FIND_ALL] full JSON ${SZ} bytes — floors-only zip (full left on disk)"
  fi
fi
[[ -f "$ZIP" ]] || tar -czf "${ZIP%.zip}.tgz" "$OUT_FLOORS" "$OUT_FLOORS_CSV" "$OUT_FLOORS_MD" "$OUT_MD" "$LIST" "$SRC_DIR"
UPLOAD="$ZIP"
[[ -f "$ZIP" ]] || UPLOAD="${ZIP%.zip}.tgz"

FETCH=""
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
echo "UNIQUE_KEYS=$(python3 -c "import json;print(json.load(open('$OUT_JSON'))['totals']['unique_keys'])" 2>/dev/null || echo '?')"
echo "FLOORS=$(python3 -c "import json;print(json.load(open('$OUT_FLOORS'))['totals']['unique_keys'])" 2>/dev/null || echo '?')"
echo "DB=${DB:-MISSING}"
echo "TG_CSV=${TG_CSV:-MISSING}"
echo "HAS_STRINGS=$([[ -f bot/strings.py ]] && echo YES || echo NO)"
echo "HAS_SIGNAL_HANDLER=$([[ -f bot/signal_handler.py ]] && echo YES || echo NO)"
echo "====================================="
