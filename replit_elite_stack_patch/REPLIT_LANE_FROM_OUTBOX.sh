#!/usr/bin/env bash
# Read dual-lane persistence (MONEY vs COUNTDOWN/TIMED) — window_secs is empty in DB.
#   curl -fsSL -H 'Cache-Control: no-cache' -o LANES.sh \
#     'https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/cursor/add-engine-gate-registry-d5ba/replit_elite_stack_patch/REPLIT_LANE_FROM_OUTBOX.sh'
#   bash LANES.sh | tee lane_outbox_report.txt
set -euo pipefail
cd /home/runner/workspace 2>/dev/null || cd "$(dirname "$0")/.."

python3 - <<'PY'
import json, sqlite3
from collections import Counter
from pathlib import Path

paths = [
    Path("bot/data/outbox_lane_by_signal.json"),
    Path("bot/data/outbox_lane_by_signal.jsonl"),
]
print("========== outbox lane files ==========")
found = None
for p in paths:
    print(p, "exists" if p.exists() else "MISSING", p.stat().st_size if p.exists() else "")
    if p.exists() and found is None:
        found = p

if not found:
    print("No lane persistence file — dual-lane map not on disk.")
    print("Timed vs money then ONLY recoverable from Telegram card text.")
else:
    raw = found.read_text(encoding="utf-8", errors="replace")
    try:
        data = json.loads(raw)
    except Exception:
        # maybe jsonl
        data = {}
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                o = json.loads(line)
                if isinstance(o, dict):
                    data.update(o)
            except Exception:
                pass
    print("entries", len(data) if isinstance(data, dict) else type(data))
    if isinstance(data, dict):
        ctr = Counter(str(v).upper() for v in data.values())
        print("LANE COUNTS:", dict(ctr))
        # join to consensus_signals kinds
        con = sqlite3.connect("file:bot/bacbo.db?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        lane_kind = Counter()
        for sid, lane in data.items():
            try:
                i = int(sid)
            except Exception:
                continue
            r = con.execute(
                "SELECT signal_kind, source_floor, outcome, fired_at FROM consensus_signals WHERE id=?",
                (i,),
            ).fetchone()
            if not r:
                lane_kind[(str(lane).upper(), "(id_not_in_db)")] += 1
                continue
            lane_kind[(str(lane).upper(), r["signal_kind"] or "?")] += 1
        print("\nLANE × KIND from outbox_lane_by_signal.json:")
        for (lane, kind), n in lane_kind.most_common(40):
            print(f"  {lane:12} {kind:16} {n}")
        con.close()

print("""
========== WHAT YOUR TREE RUN PROVED ==========
1) DB window_secs is ALWAYS empty → every row looked like MONEY. That is a STORAGE gap, not 'no timed fires ever'.
2) Locked from DB anyway:
   - 7 FIRE kinds
   - 34 floors
   - 86 KIND×FLOOR branches
   - 7 RESULT subtypes (win/loss/tie × G0–G3)
3) TIMED subtypes (JANELA 1s/11s/17s/CD skins) need Telegram text or outbox_lane file above.
""")
PY
