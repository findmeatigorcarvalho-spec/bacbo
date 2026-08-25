#!/usr/bin/env bash
# Quick post-FIREAGAIN check: procs up? crashes? next source_floor?
set -euo pipefail
cd /home/runner/workspace
PY=python3

echo "========== procs =========="
pgrep -af 'runtime_supervisor|bacbo_royal|fallback_' || echo NONE
echo "sup=$(pgrep -fc runtime_supervisor.py || echo 0) bacbo=$(pgrep -fc bacbo_royal_complete.py || echo 0)"

echo "========== tag smoke =========="
$PY <<'PY'
import sys
sys.path.insert(0,"bot"); sys.path.insert(0,".")
import lux_floor_rotate as lfr
import floor_tracker as ft
print("mode", lfr._mode())
print("tag_floor", lfr.tag_floor())
print("engine_get_floor", ft.get_floor())
try:
    print("badge", ft.get_floor_badge()[:70])
except Exception as e:
    print("badge_err", e)
PY

echo "========== log since last BootFilter =========="
$PY <<'PY'
import re
from pathlib import Path
lines = Path("logs/bot_live.log").read_text(errors="replace").splitlines() if Path("logs/bot_live.log").exists() else []
cut=0
for i,ln in enumerate(lines):
    if "[BootFilter]" in ln or "floor-rotate early-load" in ln:
        cut=i
post=lines[cut:]
print("post_lines", len(post))
for pat,lab in [
    (r"SIGNAL FIRED|SEQUENCE/FIRED","fired"),
    (r"QUIET —","quiet"),
    (r"Traceback|CRASH|AttributeError|NameError","crash"),
    (r"floor-rotate","rotate"),
]:
    print(lab, len(re.findall(pat,"\n".join(post))))
print("--- rotate/crash ---")
for ln in post:
    if "floor-rotate" in ln or "CRASH" in ln or "Traceback" in ln or "AttributeError" in ln:
        print(ln[:220])
print("--- last 12 ---")
for ln in lines[-12:]:
    print(ln)
PY

echo "========== db =========="
$PY <<'PY'
import sqlite3
from pathlib import Path
db="bot/bacbo.db" if Path("bot/bacbo.db").exists() else "bacbo.db"
con=sqlite3.connect(db)
rows=list(con.execute(
  "select id,fired_at,signal_kind,source_floor,color,outcome from consensus_signals order by id desc limit 10"))
print("last10:")
for r in rows:
    print(r)
if rows:
    print("newest_floor", rows[0][3], "id", rows[0][0])
print("floors_60m", list(con.execute(
  "select coalesce(source_floor,'NULL'),count(*) from consensus_signals "
  "where fired_at>=datetime('now','-60 minutes') group by 1 order by 2 desc")))
PY

echo
echo "WANT: bacbo=1, mode=tag, tag=JUN19, engine_get_floor=LIVE,"
echo "      newest source_floor JUN19+ after next fire (id>1768)."
echo "DONE. Paste ALL output."
