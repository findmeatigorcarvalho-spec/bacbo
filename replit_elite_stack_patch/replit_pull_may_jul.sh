#!/usr/bin/env bash
# Pull May + June + July floor/room/day data from Replit bacbo.db (python3 only).
set -euo pipefail
ROOT=/home/runner/workspace
[ -d "$ROOT/bot" ] || ROOT="$HOME/workspace"
cd "$ROOT"
OUT="$ROOT/may_jul_export_$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$OUT"/{sqlite,gates,reports}
echo "[1/4] $OUT"
cp -a bot/_gates_*.py "$OUT/gates/" 2>/dev/null || true
cp -a bot/data/*.json "$OUT/reports/" 2>/dev/null || true
export OUT DB=bot/bacbo.db
python3 <<'PY'
import csv, os, sqlite3, json
from pathlib import Path
from collections import defaultdict

db=os.environ['DB']; out=Path(os.environ['OUT'])/'sqlite'; out.mkdir(parents=True, exist_ok=True)
con=sqlite3.connect(db)
cols={r[1] for r in con.execute('PRAGMA table_info(consensus_signals)')}
def pick(*n):
    for x in n:
        if x in cols: return x
    return None
fired=pick('fired_at','created_at','ts')
floor=pick('source_floor','floor','camada')
kind=pick('signal_kind','kind','tier')
color=pick('color','predicted_color')
outcome=pick('outcome','result')
g=pick('g_level','gale_level','g')
rooms_n=con.execute("SELECT COUNT(*) FROM rooms").fetchone()[0] if 'rooms' in {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")} else None
print('map',fired,floor,kind,color,outcome,g,'rooms',rooms_n)
assert fired and outcome and floor

fe=f"COALESCE(NULLIF({floor},''),'UNKNOWN')"
ke=f"COALESCE(NULLIF({kind},''),'UNKNOWN')" if kind else "'UNKNOWN'"
ce=f"COALESCE(NULLIF({color},''),'UNKNOWN')" if color else "'UNKNOWN'"
g0w=f"SUM(CASE WHEN {g}=0 AND {outcome}='win' THEN 1 ELSE 0 END)" if g else "NULL"
g0l=f"SUM(CASE WHEN {g}=0 AND {outcome}='loss' THEN 1 ELSE 0 END)" if g else "NULL"

# May Jun Jul daily by floor
q=f'''
SELECT strftime('%Y-%m',{fired}) ym, date({fired}) d, {fe} floor, {ke} kind, {ce} color,
 COUNT(*) n,
 SUM(CASE WHEN {outcome}='win' THEN 1 ELSE 0 END) wins,
 SUM(CASE WHEN {outcome}='loss' THEN 1 ELSE 0 END) losses,
 SUM(CASE WHEN {outcome}='tie' THEN 1 ELSE 0 END) ties,
 {g0w} g0_wins, {g0l} g0_losses
FROM consensus_signals
WHERE {fired} >= '2026-05-01' AND {fired} < '2026-08-01'
GROUP BY 1,2,3,4,5 ORDER BY 1,2,3,4,5
'''
rows=list(con.execute(q))
with (out/'may_jul_floor_kind_day.csv').open('w',newline='') as f:
    w=csv.writer(f); w.writerow(['ym','d','floor','kind','color','n','wins','losses','ties','g0_wins','g0_losses']); w.writerows(rows)
print('day rows',len(rows))

# peak day per floor in May-Jul
q2=f'''
SELECT {fe} floor, date({fired}) d, COUNT(*) n,
 SUM(CASE WHEN {outcome}='win' THEN 1 ELSE 0 END) wins,
 SUM(CASE WHEN {outcome}='loss' THEN 1 ELSE 0 END) losses,
 ROUND(100.0*SUM(CASE WHEN {outcome}='win' THEN 1 ELSE 0 END)/NULLIF(SUM(CASE WHEN {outcome} IN ('win','loss') THEN 1 ELSE 0 END),0),2) wr
FROM consensus_signals
WHERE {fired} >= '2026-05-01' AND {fired} < '2026-08-01'
GROUP BY 1,2
'''
by=defaultdict(list)
for floor_,d,n,wins,losses,wr in con.execute(q2):
    by[floor_].append((n or 0, wr or 0, d, wins, losses))
peaks=[]
for fl,items in by.items():
    items.sort(key=lambda x:(-x[0], -(x[1] or 0)))
    n,wr,d,wins,losses=items[0]
    # also best wr day with n>=20
    good=[x for x in items if x[0]>=20]
    best=max(good, key=lambda x:(x[1] or 0, x[0])) if good else items[0]
    peaks.append({
        'floor':fl,
        'peak_volume_day':d,'peak_volume_n':n,'peak_volume_wr':wr,'peak_volume_wins':wins,'peak_volume_losses':losses,
        'best_wr_day':best[2],'best_wr_n':best[0],'best_wr':best[1],
        'may_jul_days':len(items),'may_jul_n':sum(i[0] for i in items)
    })
peaks.sort(key=lambda x:-x['may_jul_n'])
with (out/'may_jul_floor_peaks.csv').open('w',newline='') as f:
    w=csv.DictWriter(f, fieldnames=list(peaks[0]) if peaks else ['floor'])
    w.writeheader(); w.writerows(peaks)
print('floors',len(peaks))

# month totals
q3=f'''
SELECT strftime('%Y-%m',{fired}) ym, {fe} floor, COUNT(*) n,
 ROUND(100.0*SUM(CASE WHEN {outcome}='win' THEN 1 ELSE 0 END)/NULLIF(SUM(CASE WHEN {outcome} IN ('win','loss') THEN 1 ELSE 0 END),0),2) wr
FROM consensus_signals
WHERE {fired} >= '2026-05-01' AND {fired} < '2026-08-01'
GROUP BY 1,2 ORDER BY 1, n DESC
'''
with (out/'may_jul_floor_month.csv').open('w',newline='') as f:
    w=csv.writer(f); w.writerow(['ym','floor','n','wr']); w.writerows(con.execute(q3))

# rooms contributing May-Jul if signal has room field
room_col=pick('lead_room','room','primary_room','source_room')
if room_col:
    q4=f'''
    SELECT COALESCE(NULLIF({room_col},''),'UNKNOWN') room, COUNT(*) n,
     ROUND(100.0*SUM(CASE WHEN {outcome}='win' THEN 1 ELSE 0 END)/NULLIF(SUM(CASE WHEN {outcome} IN ('win','loss') THEN 1 ELSE 0 END),0),2) wr
    FROM consensus_signals
    WHERE {fired} >= '2026-05-01' AND {fired} < '2026-08-01'
    GROUP BY 1 ORDER BY n DESC
    '''
    with (out/'may_jul_rooms.csv').open('w',newline='') as f:
        w=csv.writer(f); w.writerow(['room','n','wr']); w.writerows(con.execute(q4))
    print('wrote may_jul_rooms.csv')
else:
    # rooms table snapshot
    tables={r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if 'rooms' in tables:
        cols_r={r[1] for r in con.execute('PRAGMA table_info(rooms)')}
        (out/'rooms_pragma.txt').write_text('\n'.join(sorted(cols_r)))
        rows=list(con.execute('SELECT * FROM rooms'))
        with (out/'rooms_full.csv').open('w',newline='') as f:
            w=csv.writer(f); w.writerow([r[1] for r in con.execute('PRAGMA table_info(rooms)')]); w.writerows(rows)
        print('rooms_full',len(rows))

meta={'floors_may_jul':len(peaks),'rooms_table':rooms_n,'cols':sorted(cols),'peak_top10':peaks[:10]}
(out/'meta.json').write_text(json.dumps(meta,indent=2))
print(json.dumps(meta,indent=2)[:1500])
con.close()
PY
echo "[2/4] zip"
ZIP="$ROOT/may_jul_export.zip"
rm -f "$ZIP"
( cd "$OUT/.." && zip -r -9 "$(basename "$ZIP")" "$(basename "$OUT")" >/tmp/mjzip.log )
ls -lah "$ZIP"
echo "[3/4] ALSO re-zip light luxury if missing"
[ -f luxury_export_light.zip ] && ls -lah luxury_export_light.zip
echo "[4/4] DONE — upload may_jul_export.zip (+ luxury_export_light.zip) via YDRAY and paste links"
