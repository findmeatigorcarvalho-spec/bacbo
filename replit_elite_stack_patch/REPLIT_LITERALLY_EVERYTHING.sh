#!/usr/bin/env bash
# ONE paste — pack LITERALLY everything the building needs from live Replit.
#
#   curl -fsSL -H 'Cache-Control: no-cache' -o LITERALLY_EVERYTHING.sh \
#     'https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/cursor/add-engine-gate-registry-d5ba/replit_elite_stack_patch/REPLIT_LITERALLY_EVERYTHING.sh'
#   bash LITERALLY_EVERYTHING.sh
#   # paste FETCH_URL= back to Cursor
set -euo pipefail
cd /home/runner/workspace 2>/dev/null || cd "$(pwd)"
ROOT="$(pwd)"
PY="${PYTHON:-python3}"
BR="cursor/add-engine-gate-registry-d5ba"
RAW="https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/${BR}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUTDIR="literally_everything_${STAMP}"
mkdir -p "$OUTDIR" bot/config bot/data replit_elite_stack_patch

echo "[1/5] pull miner + skin stack from GitHub"
for rel in \
  bot/config/__init__.py \
  bot/config/registry.py \
  bot/config/skin_families.py \
  bot/config/skin_gate.py \
  bot/config/skin_census.py \
  bot/config/chat_shelves.py \
  bot/config/find_all_skins.py \
  replit_elite_stack_patch/REPLIT_FIND_ALL_SKINS.sh
do
  curl -fsSL -H 'Cache-Control: no-cache' -o "$rel" "${RAW}/${rel}?v=$(date +%s)" || true
done

echo "[2/5] deep skin mine (code/bak/git/DB/TG)"
bash replit_elite_stack_patch/REPLIT_FIND_ALL_SKINS.sh 2>&1 | tee "$OUTDIR/find_all_skins.log" || true
# Prefer floors artifacts into outdir
cp -f bot/data/literally_everything_floors.json "$OUTDIR/" 2>/dev/null || true
cp -f bot/data/literally_everything_floors.csv "$OUTDIR/" 2>/dev/null || true
cp -f replit_elite_stack_patch/LITERALLY_EVERYTHING_FLOORS.md "$OUTDIR/" 2>/dev/null || true
cp -f bot/data/template_source_files.txt "$OUTDIR/" 2>/dev/null || true

echo "[3/5] pack live bot formatters / handlers / gates / bak"
PACK="$OUTDIR/bot_sources"
mkdir -p "$PACK"
# Core card pipeline files (created-or-not — list presence)
for f in \
  bot/strings.py \
  bot/signal_handler.py \
  bot/telegram_outbox.py \
  bot/dual_lane_router.py \
  bot/fire_origin.py \
  bot/skin_gate.py \
  bot/hub_engine_route.py \
  bot/lux_send_config_bind.py \
  bacbo_royal_complete.py
do
  if [[ -f "$f" ]]; then
    mkdir -p "$PACK/$(dirname "$f")"
    cp -a "$f" "$PACK/$f"
    # sibling backups
    for b in "$f".bak* "$f"~ "$f".bak; do
      [[ -f "$b" ]] || continue
      cp -a "$b" "$PACK/$(dirname "$f")/" 2>/dev/null || true
    done
  fi
done
# All gates + bak
mkdir -p "$PACK/bot"
cp -a bot/_gates_*.py "$PACK/bot/" 2>/dev/null || true
find bot -maxdepth 2 -type f \( -name '*string*' -o -name '*template*' -o -name '*card*' -o -name '*outbox*' -o -name '*signal*' \) \
  \( -name '*.py' -o -name '*.bak*' -o -name '*.py~' \) -print0 2>/dev/null \
  | while IFS= read -r -d '' f; do
      mkdir -p "$PACK/$(dirname "$f")"
      cp -a "$f" "$PACK/$f" 2>/dev/null || true
    done

{
  echo "HAS_STRINGS=$([[ -f bot/strings.py ]] && echo YES || echo NO)"
  echo "HAS_SIGNAL_HANDLER=$([[ -f bot/signal_handler.py ]] && echo YES || echo NO)"
  echo "HAS_OUTBOX=$([[ -f bot/telegram_outbox.py ]] && echo YES || echo NO)"
  echo "GATES_N=$(ls bot/_gates_*.py 2>/dev/null | wc -l)"
  echo "GATES=$(ls bot/_gates_*.py 2>/dev/null | xargs -n1 basename | tr '\n' ',' )"
  echo "DB=$(ls -lah bot/bacbo.db bacbo.db 2>/dev/null | head -5)"
  echo "BAK_N=$(find bot -name '*.bak*' 2>/dev/null | wc -l)"
} | tee "$OUTDIR/presence.txt"

echo "[4/5] DB kind census (small) + schema"
DB=""
for cand in bot/bacbo.db bacbo.db data/bacbo.db; do
  [[ -f "$cand" ]] && DB="$cand" && break
done
if [[ -n "$DB" ]]; then
  "$PY" - <<PY | tee "$OUTDIR/db_kinds.json"
import json, sqlite3
from pathlib import Path
db = Path("$DB")
con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
out = {"db": str(db), "size": db.stat().st_size, "tables": {}, "kinds": {}}
for (name,) in con.execute("SELECT name FROM sqlite_master WHERE type='table'"):
    try:
        n = con.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
    except Exception:
        n = None
    out["tables"][name] = n
for table in ("consensus_signals", "signals", "blocked_signals", "oracle_signals"):
    cols = {r[1] for r in con.execute(f"PRAGMA table_info({table})")} if table in out["tables"] else set()
    if "signal_kind" not in cols:
        continue
    rows = con.execute(
        f"SELECT signal_kind, COUNT(*) n FROM {table} GROUP BY signal_kind ORDER BY n DESC"
    ).fetchall()
    out["kinds"][table] = [{"kind": k, "n": n} for k, n in rows]
con.close()
print(json.dumps(out, indent=2))
PY
fi

echo "[5/5] zip + upload"
ZIP="bacbo_literally_everything_${STAMP}.zip"
(
  cd "$ROOT"
  zip -qr "$ZIP" "$OUTDIR" \
    bot/data/literally_everything_floors.json \
    bot/data/literally_everything_floors.csv \
    replit_elite_stack_patch/LITERALLY_EVERYTHING_FLOORS.md \
    2>/dev/null || zip -qr "$ZIP" "$OUTDIR"
)

FETCH=""
if command -v curl >/dev/null; then
  FETCH=$(curl -fsS -F "reqtype=fileupload" -F "time=72h" -F "fileToUpload=@${ZIP}" \
    https://litterbox.catbox.moe/resources/internals/api.php 2>/dev/null || true)
  if [[ -z "$FETCH" ]]; then
    FETCH=$(curl -fsS -F "reqtype=fileupload" -F "fileToUpload=@${ZIP}" \
      https://catbox.moe/user/api.php 2>/dev/null || true)
  fi
fi

echo "========== PASTE TO CURSOR =========="
echo "FETCH_URL=${FETCH:-LOCAL_ONLY:$ROOT/$ZIP}"
echo "ZIP=$ROOT/$ZIP"
echo "OUTDIR=$ROOT/$OUTDIR"
cat "$OUTDIR/presence.txt" 2>/dev/null || true
echo "FLOORS=$(python3 -c "import json;print(json.load(open('bot/data/literally_everything_floors.json'))['totals']['unique_keys'])" 2>/dev/null || echo '?')"
echo "====================================="
