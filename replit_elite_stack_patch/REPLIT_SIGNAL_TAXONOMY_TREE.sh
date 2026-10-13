#!/usr/bin/env bash
# Multi-level taxonomy: ROLE → LANE → KIND → FLOOR → RESULT subtype
# Timed lane also has many types (not one bucket). Money same.
#
#   curl -fsSL -H 'Cache-Control: no-cache' -o CENSUS2.sh \
#     'https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/cursor/add-engine-gate-registry-d5ba/replit_elite_stack_patch/REPLIT_SIGNAL_TAXONOMY_TREE.sh'
#   bash CENSUS2.sh | tee signal_taxonomy_tree.txt
set -euo pipefail
cd /home/runner/workspace 2>/dev/null || cd "$(dirname "$0")/.."

python3 - <<'PY'
import sqlite3, json
from collections import defaultdict
from pathlib import Path

con = sqlite3.connect("file:bot/bacbo.db?mode=ro", uri=True)
con.row_factory = sqlite3.Row
SINCE = "2026-03-17"

print("""
========================================================================
TAXONOMY TREE (what you mean by families / lanes / types)
========================================================================

LEVEL 0  ROLE          ONLINE | FIRE | RESULT | UPDATE/OPS
LEVEL 1  LANE          MONEY (no bet-window on fire) | TIMED (JANELA/Ns on fire)
LEVEL 2  FIRE KIND     SOLO_ELITE | GOLDEN | PLATINUM | SEQUENCE | FLASH | ...
LEVEL 3  FLOOR         JUN19 | JUN10 | LIVE | MAY10 | ...
LEVEL 4  RESULT TYPE   win | loss | tie  ×  gale G0/G1/G2/G3  ×  skin (forensic/short)
LEVEL 5  TIMED SUBTYPE window_secs buckets / JANELA skins (1s,11s,17s, CD templates)

IMPORTANT: TIMED is NOT one type. MONEY is NOT one type.
Each lane has many FIRE kinds × floors × result subtypes.
ONLINE (your Mar 17 paste) sits outside FIRE — 1 role, no result.
""")

cols = [r[1] for r in con.execute("PRAGMA table_info(consensus_signals)")]
print("columns:", cols)

# Lane proxy: window_secs > 0 => TIMED-ish; else MONEY-ish
# (Telegram template is ultimate truth; DB window_secs is best proxy we have)
has_window = "window_secs" in cols

def lane_of(row):
    if has_window:
        w = row["window_secs"]
        try:
            if w is not None and float(w) > 0:
                return "TIMED"
        except Exception:
            pass
    return "MONEY"

rows = con.execute(
    f"""SELECT id, signal_kind, source_floor, outcome, won_at_gale, fired_at,
               {"window_secs" if has_window else "NULL AS window_secs"},
               classification, signal_tier
        FROM consensus_signals WHERE fired_at >= ?""",
    (SINCE,),
).fetchall()

# ── LEVEL 1×2: lane × kind ────────────────────────────────────────────────
print("\n========== LANE × FIRE KIND (every timed type listed separately) ==========")
lane_kind = defaultdict(lambda: {"n": 0, "win": 0, "loss": 0, "tie": 0, "windows": set()})
for r in rows:
    lane = lane_of(r)
    kind = r["signal_kind"] or "(null)"
    k = (lane, kind)
    lane_kind[k]["n"] += 1
    o = (r["outcome"] or "").lower()
    if o == "win":
        lane_kind[k]["win"] += 1
    elif o == "loss":
        lane_kind[k]["loss"] += 1
    elif "tie" in o:
        lane_kind[k]["tie"] += 1
    if has_window and r["window_secs"] is not None:
        try:
            lane_kind[k]["windows"].add(float(r["window_secs"]))
        except Exception:
            pass

print(f"{'LANE':8} {'KIND':16} {'N':>6} {'WIN':>6} {'LOSS':>5} {'TIE':>5}  window_secs seen")
for (lane, kind), s in sorted(lane_kind.items(), key=lambda x: (-x[1]["n"], x[0][0], x[0][1])):
    wins = sorted(s["windows"])[:12]
    wtxt = ",".join(str(int(x)) if x == int(x) else str(x) for x in wins)
    if len(s["windows"]) > 12:
        wtxt += ",..."
    print(f"{lane:8} {kind:16} {s['n']:6} {s['win']:6} {s['loss']:5} {s['tie']:5}  {wtxt or '-'}")

# ── TIMED subtypes by window_secs ─────────────────────────────────────────
from collections import Counter
if has_window:
    print("\n========== TIMED SUBTYPES by window_secs (different timed 'types') ==========")
    print(f"{'window_s':>10} {'N':>6} {'kinds'}")
    by_w = defaultdict(Counter)
    money_n = timed_n = 0
    for r in rows:
        w = r["window_secs"]
        try:
            wf = float(w) if w is not None else 0.0
        except Exception:
            wf = 0.0
        if wf > 0:
            timed_n += 1
            by_w[wf][r["signal_kind"] or "?"] += 1
        else:
            money_n += 1
    print(f"MONEY proxy (window_secs null/0): {money_n}")
    print(f"TIMED proxy (window_secs > 0):    {timed_n}")
    for w, ctr in sorted(by_w.items(), key=lambda x: -sum(x[1].values())):
        kinds = ", ".join(f"{k}={n}" for k, n in ctr.most_common())
        print(f"{w:10g} {sum(ctr.values()):6}  {kinds}")

# ── RESULT subtypes: outcome × gale ───────────────────────────────────────
print("\n========== RESULT SUBTYPES (outcome × gale) — under EVERY lane/kind ==========")
print(f"{'outcome':8} {'gale':6} {'N':>6}  (G0=won_at_gale 0, G1=1, ...)")
rc = Counter()
for r in rows:
    o = (r["outcome"] or "(none)").lower()
    g = r["won_at_gale"]
    g = 0 if g is None else int(g)
    rc[(o, g)] += 1
for (o, g), n in rc.most_common():
    print(f"{o:8} G{g:<5} {n:6}")

# ── Full tree sample: LANE → KIND → FLOOR → RESULT ─────────────────────────
print("\n========== TREE: LANE → KIND → FLOOR (top 50 branches) ==========")
tree = Counter()
for r in rows:
    lane = lane_of(r)
    kind = r["signal_kind"] or "?"
    floor = r["source_floor"] or "LIVE"
    tree[(lane, kind, floor)] += 1
print(f"{'LANE':8} {'KIND':16} {'FLOOR':18} {'N':>6}")
for (lane, kind, floor), n in tree.most_common(50):
    print(f"{lane:8} {kind:16} {floor:18} {n:6}")

# ── Distinct counts summary ───────────────────────────────────────────────
print("\n========== DISTINCT COUNTS (your checklist) ==========")
kinds = {r["signal_kind"] for r in rows}
floors = {r["source_floor"] or "LIVE" for r in rows}
outcomes = {r["outcome"] for r in rows}
gales = {r["won_at_gale"] for r in rows}
lanes = {lane_of(r) for r in rows}
print(f"  Lanes (proxy):           {len(lanes)} → {sorted(lanes)}")
print(f"  FIRE kinds:              {len(kinds)} → {sorted(k for k in kinds if k)}")
print(f"  Floors:                  {len(floors)}")
print(f"  Outcome values:          {sorted(outcomes)}")
print(f"  Gale depths used:        {sorted(gales, key=lambda x: -1 if x is None else x)}")
if has_window:
    windows = sorted({float(r['window_secs']) for r in rows if r['window_secs'] not in (None, 0, 0.0)})
    print(f"  Timed window_secs types: {len(windows)} → {windows[:30]}")
print(f"  LANE×KIND branches:      {len(lane_kind)}")
print(f"  LANE×KIND×FLOOR:         {len(tree)}")
print(f"  RESULT subtypes (out×G): {len(rc)}")

print("""
========== TELEGRAM CARD TYPES DB CANNOT SEE ==========
Still only visible in chat export / scrape:
  ONLINE          (your Mar 17 banners)
  UPDATE/OPS      (expire, quarantine, delivery audit, G1 EXPIROU...)
  RESULT SKINS    (forensic Intervalo vs short ✅ WIN — … vs G0/G1 text)
  TIMED FIRE SKINS (JANELA 1s vs 11s vs 17s vs CD_FIRE_TIMER... templates)
DB window_secs approximates timed vs money; template skin needs Telegram text.
""")

Path("signal_taxonomy_tree.json").write_text(json.dumps({
    "since": SINCE,
    "lanes": sorted(lanes),
    "fire_kinds": sorted(k for k in kinds if k),
    "floor_count": len(floors),
    "lane_kind": {f"{a}|{b}": {**v, "windows": sorted(v["windows"])} for (a,b), v in lane_kind.items()},
    "result_subtypes": {f"{o}|G{g}": n for (o, g), n in rc.items()},
}, indent=2, default=str))
print("Wrote signal_taxonomy_tree.json")
con.close()
PY
