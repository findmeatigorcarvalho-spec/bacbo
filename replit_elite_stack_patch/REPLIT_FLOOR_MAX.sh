#!/usr/bin/env bash
# Floor-max pass: peak-lock every live floor, rank by strength, unlock hours,
# refresh merge/outbox, ONE stack, verify towers are speaking.
set -euo pipefail
cd /home/runner/workspace
PY=python3
SHA="${LUXURY_PATCH_SHA:-cursor/add-engine-gate-registry-d5ba}"
BASE="https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/${SHA}/replit_elite_stack_patch"

echo "========== [0/7] honesty =========="
echo "v1: LIVE proposes; all floors scored; best peak stamped (TOWER_MERGE)."
echo "True per-floor peak volume = v2 proposers (next). This pass maxes v1."
echo

echo "========== [1/7] refresh floor-max bits =========="
mkdir -p bot/data logs
for rel in \
  bot/lux_tower_merge.py \
  bot/edge_live_policy.py \
  bot/peak_fidelity_ranker.py \
  bot/gate_alias_resolve.py \
  bot/telegram_outbox.py \
  bot/dual_lane_router.py \
  bot/runtime_supervisor.py \
  bot/lux_floor_rotate.py \
  bot/data/peak_lock_config.json \
  bot/data/luxury_live_floors.json \
  bot/data/historical_luxury_seed.json \
  REPLIT_PEAK_LOCK_APPLY.sh \
  REPLIT_ONE_STACK.sh
do
  curl -fsSL -H "Cache-Control: no-cache" -o "$rel" "$BASE/$rel" || echo "skip $rel"
done
$PY -m py_compile bot/lux_tower_merge.py bot/peak_fidelity_ranker.py bot/telegram_outbox.py bot/dual_lane_router.py

echo "========== [2/7] peak-lock apply (no double supervisor) =========="
export SKIP_SUPERVISOR_RESTART=1
bash REPLIT_PEAK_LOCK_APPLY.sh || true

echo "========== [3/7] luxury env max unlocks =========="
$PY - <<'PY'
from pathlib import Path
p = Path("luxury_building.env")
text = p.read_text(errors="ignore") if p.exists() else ""
want = {
    "EDGE_POLICY_MODE": "luxury",
    "EDGE_LUXURY_FLOOR_GATE": "1",
    "LUXURY_TOWER_MERGE": "1",
    "LUXURY_NO_HOUR_BLOCKS": "1",
    "FALLBACK_SEND_BLOCKED": "0",
    "TELEGRAM_SINGLE_OUTBOX": "1",
    "FALLBACKS_ENABLED": "1",
    "TELEGRAM_COUNTDOWN_PEER": "UNIQUE_g1",
    "GUNIQUE_PEER": "UNIQUE_g1",
    "TELEGRAM_MIRROR_MONEY_TO_GUNIQUE": "1",
    "LUXURY_FLOOR_ROTATE": "1",
    "LUXURY_FLOOR_ROTATE_MODE": "tag",
    "LUXURY_FLOOR_ROTATE_DEFER_APPLY": "0",
}
kept, seen = [], set()
for ln in text.splitlines():
    s = ln.strip()
    if not s or s.startswith("#") or "=" not in s:
        kept.append(ln); continue
    raw = s[7:].strip() if s.startswith("export ") else s
    k = raw.split("=", 1)[0].strip()
    if k in want:
        kept.append(f"export {k}={want[k]}"); seen.add(k)
    else:
        kept.append(ln)
for k, v in want.items():
    if k not in seen:
        kept.append(f"export {k}={v}")
p.write_text("\n".join(kept).rstrip() + "\n")
print("env ok", p)
PY

echo "========== [4/7] peak fidelity rank (strength for merge) =========="
DB=bot/bacbo.db
[ -f bot/bacbo.db ] || DB=bacbo.db
$PY bot/peak_fidelity_ranker.py --db "$DB" || true
$PY - <<'PY'
import json
from pathlib import Path
r = json.loads(Path("bot/data/peak_fidelity_ranker_report.json").read_text())
print("floors", r["counts"])
print("top5:")
for x in r.get("top10", [])[:5]:
    print(f"  #{x['rank']} {x['floor']} score={x['strength_score']} peak={x['peak_day']} wr={x['peak_wr']} fid={x['fidelity']}")
gaps = (r.get("fidelity_groups") or {}).get("VOLUME_GAP_VS_PEAK") or []
silent = (r.get("fidelity_groups") or {}).get("NO_LIVE_ATTRIBUTION") or []
print("volume_gap", len(gaps), gaps[:12])
print("silent", len(silent), silent[:12])
PY

echo "========== [5/7] ONE stack =========="
bash REPLIT_ONE_STACK.sh

echo "========== [6/7] verify merge + mode + recent floors =========="
$PY - <<'PY'
import os, sqlite3, json
from pathlib import Path
import sys
sys.path[:0] = ["bot", "."]
os.environ.setdefault("EDGE_POLICY_MODE", "luxury")
os.environ.setdefault("LUXURY_TOWER_MERGE", "1")

from lux_tower_merge import merge_candidate, _load_floors, _strength_map
peaks, floors, blocked = _load_floors()
print("live_floors_n", len(floors), "peaks", peaks[:8], "blocked", sorted(blocked))
print("strength_loaded", len(_strength_map()))
v = merge_candidate(kind="GOLDEN", color="blue", agreeing_rooms=["@rqdados1"], engine_floor="LIVE")
print("merge_smoke", v.get("action"), v.get("winner_floor"), (v.get("reason") or "")[:100], "allows", v.get("tower_allows"))

db = Path("bot/bacbo.db") if Path("bot/bacbo.db").is_file() else Path("bacbo.db")
c = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=30)
print("recent_floors_6h:")
for r in c.execute(
    """
    SELECT COALESCE(source_floor,'?') f, COUNT(*) n,
           SUM(outcome='win') w,
           SUM(outcome='win' AND COALESCE(won_at_gale,0)=0) g0
    FROM consensus_signals
    WHERE fired_at >= datetime('now','-6 hours')
    GROUP BY 1 ORDER BY n DESC LIMIT 15
    """
):
    print(" ", dict(f=r[0], n=r[1], w=r[2], g0=r[3]))
mx = c.execute("SELECT MAX(id), MAX(fired_at) FROM consensus_signals").fetchone()
print("max", mx)
c.close()
PY

echo "========== [7/7] bot_live TOWER_MERGE / FIRED tail =========="
grep -E 'TOWER_MERGE|SIGNAL FIRED|EdgePolicy|QUIET' logs/bot_live.log 2>/dev/null | tail -n 25 || true
grep -E 'sent signal|mirror|Gunique|ONLINE' logs/telegram_outbox.log 2>/dev/null | tail -n 15 || true

echo
echo "FLOOR_MAX DONE."
echo "Expect: luxury mode, peak gates bound, merge prefers strongest peak, money→Mr_iv4+@UNIQUE_g1."
echo "If volume_gap floors stay high: need v2 proposers (each floor originates fires)."
echo "DONE."
