#!/usr/bin/env bash
# Paste into Replit Shell (Bac-Bo-Watcher).
# No system sqlite3 binary required — uses python3.
set -euo pipefail

ROOT="${HOME}/workspace"
if [ ! -d "$ROOT/bot" ] && [ -d /home/runner/workspace/bot ]; then
  ROOT=/home/runner/workspace
fi
cd "$ROOT"

OUT="$ROOT/luxury_export_$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$OUT"/{bot_data,gates,reports,sqlite}

echo "[1/5] root=$ROOT out=$OUT"

echo "[2/5] copying gates + bot data json"
GATE_N=$(ls bot/_gates_*.py 2>/dev/null | wc -l | tr -d ' ')
cp -a bot/_gates_*.py "$OUT/gates/" 2>/dev/null || true
cp -a bot/data/*.json "$OUT/bot_data/" 2>/dev/null || true
cp -a bot/data/*.jsonl "$OUT/bot_data/" 2>/dev/null || true
echo "  gates_copied=$GATE_N"

echo "[3/5] python sqlite aggregates from bacbo.db"
DB="bot/bacbo.db"
if [ ! -f "$DB" ]; then
  echo "ERROR: missing $DB" >&2
  exit 1
fi

export LUXURY_OUT="$OUT"
export LUXURY_DB="$DB"
python3 <<'PY'
import csv, os, sqlite3
from pathlib import Path

db = os.environ["LUXURY_DB"]
out = Path(os.environ["LUXURY_OUT"]) / "sqlite"
out.mkdir(parents=True, exist_ok=True)

con = sqlite3.connect(db)
cols = {r[1] for r in con.execute("PRAGMA table_info(consensus_signals)")}
(out / "consensus_signals_pragma.txt").write_text("\n".join(sorted(cols)) + "\n")

def pick(*names, default=None):
    for n in names:
        if n in cols:
            return n
    return default

fired = pick("fired_at", "created_at", "ts", "timestamp")
floor = pick("source_floor", "floor", "camada", "floor_name")
kind = pick("kind", "signal_kind", "tier")
color = pick("color", "predicted_color", "bet_color")
outcome = pick("outcome", "result", "final_outcome")
g = pick("g_level", "gale_level", "g")

print("map:", {"fired": fired, "floor": floor, "kind": kind, "color": color, "outcome": outcome, "g": g})
if not fired or not outcome:
    raise SystemExit(f"Cannot map required columns from: {sorted(cols)}")

floor_expr = f"COALESCE(NULLIF({floor},''),'UNKNOWN')" if floor else "'UNKNOWN'"
kind_expr = f"COALESCE(NULLIF({kind},''),'UNKNOWN')" if kind else "'UNKNOWN'"
color_expr = f"COALESCE(NULLIF({color},''),'UNKNOWN')" if color else "'UNKNOWN'"

# day x floor x kind x color
q_day = f"""
SELECT date({fired}) AS d,
       {floor_expr} AS floor,
       {kind_expr} AS kind,
       {color_expr} AS color,
       COUNT(*) AS n,
       SUM(CASE WHEN {outcome}='win' THEN 1 ELSE 0 END) AS wins,
       SUM(CASE WHEN {outcome}='loss' THEN 1 ELSE 0 END) AS losses,
       SUM(CASE WHEN {outcome}='tie' THEN 1 ELSE 0 END) AS ties
FROM consensus_signals
WHERE {fired} >= '2026-03-01'
GROUP BY 1,2,3,4
ORDER BY 1,2,3,4
"""
rows = list(con.execute(q_day))
with (out / "floor_kind_day.csv").open("w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["d", "floor", "kind", "color", "n", "wins", "losses", "ties"])
    w.writerows(rows)
print("floor_kind_day rows:", len(rows))

# optional g0 columns if g exists
g0_wins = f"SUM(CASE WHEN {g}=0 AND {outcome}='win' THEN 1 ELSE 0 END) AS g0_wins" if g else "NULL AS g0_wins"
g0_losses = f"SUM(CASE WHEN {g}=0 AND {outcome}='loss' THEN 1 ELSE 0 END) AS g0_losses" if g else "NULL AS g0_losses"
g0_wr = (
    f"ROUND(100.0*SUM(CASE WHEN {g}=0 AND {outcome}='win' THEN 1 ELSE 0 END)/"
    f"NULLIF(SUM(CASE WHEN {g}=0 AND {outcome} IN ('win','loss') THEN 1 ELSE 0 END),0),2) AS g0_wr"
    if g else "NULL AS g0_wr"
)

q_floor = f"""
SELECT {floor_expr} AS floor,
       COUNT(*) AS n,
       COUNT(DISTINCT date({fired})) AS active_days,
       MIN({fired}) AS first_seen,
       MAX({fired}) AS last_seen,
       SUM(CASE WHEN {outcome}='win' THEN 1 ELSE 0 END) AS wins,
       SUM(CASE WHEN {outcome}='loss' THEN 1 ELSE 0 END) AS losses,
       SUM(CASE WHEN {outcome}='tie' THEN 1 ELSE 0 END) AS ties,
       ROUND(100.0*SUM(CASE WHEN {outcome}='win' THEN 1 ELSE 0 END)/
         NULLIF(SUM(CASE WHEN {outcome} IN ('win','loss') THEN 1 ELSE 0 END),0),2) AS wr,
       {g0_wins},
       {g0_losses},
       {g0_wr}
FROM consensus_signals
WHERE {fired} >= '2026-03-01'
GROUP BY 1
ORDER BY n DESC
"""
rows = list(con.execute(q_floor))
with (out / "floor_summary.csv").open("w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["floor","n","active_days","first_seen","last_seen","wins","losses","ties","wr","g0_wins","g0_losses","g0_wr"])
    w.writerows(rows)
print("floors:", len(rows))

q_kind = f"""
SELECT {kind_expr} AS kind,
       COUNT(*) AS n,
       ROUND(100.0*SUM(CASE WHEN {outcome}='win' THEN 1 ELSE 0 END)/
         NULLIF(SUM(CASE WHEN {outcome} IN ('win','loss') THEN 1 ELSE 0 END),0),2) AS wr,
       {g0_wr}
FROM consensus_signals
WHERE {fired} >= '2026-03-01'
GROUP BY 1
ORDER BY n DESC
"""
rows = list(con.execute(q_kind))
with (out / "kind_summary.csv").open("w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["kind","n","wr","g0_wr"])
    w.writerows(rows)

# rooms count if table exists
tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
(out / "tables.txt").write_text("\n".join(sorted(tables)) + "\n")
if "rooms" in tables:
    n = con.execute("SELECT COUNT(*) FROM rooms").fetchone()[0]
    (out / "rooms_count.txt").write_text(str(n) + "\n")
    print("rooms:", n)

# 60%+ floor shortlist
with (out / "floors_wr60plus.csv").open("w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["floor","n","wr","g0_wr","active_days"])
    for r in con.execute(q_floor):
        # r: floor,n,active_days,first,last,wins,losses,ties,wr,g0_wins,g0_losses,g0_wr
        wr = r[8]
        if wr is not None and wr >= 60 and (r[1] or 0) >= 10:
            w.writerow([r[0], r[1], wr, r[11], r[2]])
print("wrote floors_wr60plus.csv")
con.close()
PY

echo "[4/5] packing reports"
cp -a bot/data/*report*.json "$OUT/reports/" 2>/dev/null || true
cp -a bot/data/*audit*.json "$OUT/reports/" 2>/dev/null || true
cp -a bot/data/*frontier*.json "$OUT/reports/" 2>/dev/null || true
cp -a bot/data/*whitelist*.json "$OUT/reports/" 2>/dev/null || true
cp -a bot/data/*skyscraper*.json "$OUT/reports/" 2>/dev/null || true
cp -a bot/data/*floor*.json "$OUT/reports/" 2>/dev/null || true

echo "[5/5] zip"
ZIP="$ROOT/luxury_export_light.zip"
rm -f "$ZIP"
( cd "$OUT/.." && zip -r -9 "$(basename "$ZIP")" "$(basename "$OUT")" >/tmp/luxury_zip.log )
ls -lah "$ZIP"
echo
echo "DONE. Upload: $ZIP"
echo "Optional full DB: zip -0 bacbo_db_only.zip bot/bacbo.db"
