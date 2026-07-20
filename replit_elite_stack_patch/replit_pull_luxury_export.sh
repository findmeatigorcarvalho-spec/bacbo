#!/usr/bin/env bash
# Paste into Replit Shell (Bac-Bo-Watcher) to export everything needed
# for luxury-building floor rebuild + cross-compare.
set -euo pipefail

ROOT="${HOME}/workspace"
if [ ! -d "$ROOT/bot" ] && [ -d /home/runner/workspace/bot ]; then
  ROOT=/home/runner/workspace
fi
cd "$ROOT"

OUT="$ROOT/luxury_export_$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$OUT"/{bot_data,gates,reports,sqlite}

echo "[1/6] root=$ROOT out=$OUT"

# --- copy gate / floor config sources ---
echo "[2/6] copying gates + bot data json"
cp -a bot/_gates_*.py "$OUT/gates/" 2>/dev/null || true
cp -a bot/data/*.json "$OUT/bot_data/" 2>/dev/null || true
cp -a bot/data/*.jsonl "$OUT/bot_data/" 2>/dev/null || true
ls bot/_gates_*.py 2>/dev/null | wc -l | xargs -I{} echo "  gates_copied={}"

# --- lightweight DB aggregates (no full 3GB upload required first) ---
echo "[3/6] sqlite aggregates from bacbo.db"
DB="bot/bacbo.db"
if [ ! -f "$DB" ]; then
  echo "ERROR: missing $DB" >&2
  exit 1
fi

sqlite3 "$DB" <<'SQL' > "$OUT/sqlite/floor_kind_day.csv"
.headers on
.mode csv
SELECT
  date(fired_at) AS d,
  COALESCE(NULLIF(source_floor,''),'UNKNOWN') AS floor,
  COALESCE(NULLIF(kind,''),'UNKNOWN') AS kind,
  COALESCE(NULLIF(color,''),'UNKNOWN') AS color,
  COUNT(*) AS n,
  SUM(CASE WHEN outcome='win' THEN 1 ELSE 0 END) AS wins,
  SUM(CASE WHEN outcome='loss' THEN 1 ELSE 0 END) AS losses,
  SUM(CASE WHEN outcome='tie' THEN 1 ELSE 0 END) AS ties,
  SUM(CASE WHEN g_level=0 AND outcome='win' THEN 1 ELSE 0 END) AS g0_wins,
  SUM(CASE WHEN g_level=0 AND outcome='loss' THEN 1 ELSE 0 END) AS g0_losses
FROM consensus_signals
WHERE fired_at >= '2026-03-01'
GROUP BY 1,2,3,4
ORDER BY 1,2,3,4;
SQL

sqlite3 "$DB" <<'SQL' > "$OUT/sqlite/floor_summary.csv"
.headers on
.mode csv
SELECT
  COALESCE(NULLIF(source_floor,''),'UNKNOWN') AS floor,
  COUNT(*) AS n,
  COUNT(DISTINCT date(fired_at)) AS active_days,
  MIN(fired_at) AS first_seen,
  MAX(fired_at) AS last_seen,
  SUM(CASE WHEN outcome='win' THEN 1 ELSE 0 END) AS wins,
  SUM(CASE WHEN outcome='loss' THEN 1 ELSE 0 END) AS losses,
  SUM(CASE WHEN outcome='tie' THEN 1 ELSE 0 END) AS ties,
  ROUND(100.0*SUM(CASE WHEN outcome='win' THEN 1 ELSE 0 END)/
    NULLIF(SUM(CASE WHEN outcome IN ('win','loss') THEN 1 ELSE 0 END),0),2) AS wr,
  ROUND(100.0*SUM(CASE WHEN g_level=0 AND outcome='win' THEN 1 ELSE 0 END)/
    NULLIF(SUM(CASE WHEN g_level=0 AND outcome IN ('win','loss') THEN 1 ELSE 0 END),0),2) AS g0_wr,
  SUM(CASE WHEN g_level=0 AND outcome='win' THEN 1 ELSE 0 END) AS g0_wins
FROM consensus_signals
WHERE fired_at >= '2026-03-01'
GROUP BY 1
ORDER BY n DESC;
SQL

sqlite3 "$DB" <<'SQL' > "$OUT/sqlite/kind_summary.csv"
.headers on
.mode csv
SELECT
  COALESCE(NULLIF(kind,''),'UNKNOWN') AS kind,
  COUNT(*) AS n,
  ROUND(100.0*SUM(CASE WHEN outcome='win' THEN 1 ELSE 0 END)/
    NULLIF(SUM(CASE WHEN outcome IN ('win','loss') THEN 1 ELSE 0 END),0),2) AS wr,
  ROUND(100.0*SUM(CASE WHEN g_level=0 AND outcome='win' THEN 1 ELSE 0 END)/
    NULLIF(SUM(CASE WHEN g_level=0 AND outcome IN ('win','loss') THEN 1 ELSE 0 END),0),2) AS g0_wr
FROM consensus_signals
WHERE fired_at >= '2026-03-01'
GROUP BY 1
ORDER BY n DESC;
SQL

sqlite3 "$DB" <<'SQL' > "$OUT/sqlite/schema_tables.csv"
.headers on
.mode csv
SELECT name, type FROM sqlite_master WHERE type IN ('table','view') ORDER BY name;
SQL

# column detect fallback note
sqlite3 "$DB" "PRAGMA table_info(consensus_signals);" > "$OUT/sqlite/consensus_signals_pragma.txt"

echo "[4/6] packing reports if present"
cp -a bot/data/*report*.json "$OUT/reports/" 2>/dev/null || true
cp -a bot/data/*audit*.json "$OUT/reports/" 2>/dev/null || true
cp -a bot/data/*frontier*.json "$OUT/reports/" 2>/dev/null || true
cp -a bot/data/*whitelist*.json "$OUT/reports/" 2>/dev/null || true
cp -a bot/data/*skyscraper*.json "$OUT/reports/" 2>/dev/null || true
cp -a bot/data/*floor*.json "$OUT/reports/" 2>/dev/null || true

echo "[5/6] zip lightweight export"
ZIP="$ROOT/luxury_export_light.zip"
rm -f "$ZIP"
( cd "$OUT/.." && zip -r -9 "$(basename "$ZIP")" "$(basename "$OUT")" >/tmp/luxury_zip.log )
ls -lah "$ZIP"

echo "[6/6] DONE"
echo "Upload this file from Replit:"
echo "  $ZIP"
echo "Then paste the YDRAY/wormhole link back in chat."
echo
echo "OPTIONAL full DB (huge):"
echo "  zip -0 bacbo_db_only.zip bot/bacbo.db"
echo "  # then upload bacbo_db_only.zip"
