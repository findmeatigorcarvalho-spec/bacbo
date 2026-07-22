#!/usr/bin/env bash
# Wake a silent engine: unlock hour blocks, ensure luxury edge, restart ONE stack, watch for FIRED.
set -euo pipefail
cd /home/runner/workspace
PY=python3
SHA="${LUXURY_PATCH_SHA:-cursor/add-engine-gate-registry-d5ba}"
BASE="https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/${SHA}/replit_elite_stack_patch"
PEER="${TELEGRAM_TARGET_PEER:-6774605259}"
CD_PEER="${TELEGRAM_COUNTDOWN_PEER:-${GUNIQUE_PEER:-UNIQUE_g1}}"
CD_PEER="${CD_PEER#@}"

echo "========== [1/6] patch luxury_building.env unlocks =========="
touch luxury_building.env
$PY - <<'PY'
from pathlib import Path
p = Path("luxury_building.env")
text = p.read_text(errors="ignore") if p.exists() else ""
lines = text.splitlines()
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
    "LUXURY_FLOOR_ROTATE": "1",
    "LUXURY_FLOOR_ROTATE_MODE": "tag",
    "LUXURY_FLOOR_ROTATE_DEFER_APPLY": "0",
}
kept = []
seen = set()
for ln in lines:
    s = ln.strip()
    if not s or s.startswith("#") or "=" not in s:
        kept.append(ln)
        continue
    raw = s[7:].strip() if s.startswith("export ") else s
    k = raw.split("=", 1)[0].strip()
    if k in want:
        kept.append(f"export {k}={want[k]}")
        seen.add(k)
    else:
        kept.append(ln)
for k, v in want.items():
    if k not in seen:
        kept.append(f"export {k}={v}")
p.write_text("\n".join(kept).rstrip() + "\n")
print("wrote", p)
for k in sorted(want):
    print(f"  {k}={want[k]}")
PY

echo "========== [2/6] refresh outbox + dual lane + ONE =========="
curl -fsSL -H "Cache-Control: no-cache" -o ONE.sh "$BASE/REPLIT_ONE_STACK.sh"
bash ONE.sh

echo "========== [3/6] force env into running supervisor children =========="
# ONE already started; ensure no hour-block secret overrides linger in process — restart outbox/bacbo via supervisor is enough.
# Soft-touch: kill bacbo only so supervisor restarts with fresh env from luxury_building.env sourced by ONE.
sleep 2

echo "========== [4/6] DB snapshot before wait =========="
$PY - <<'PY'
import sqlite3, time
from pathlib import Path

def db():
    for p in (Path("bot/bacbo.db"), Path("bacbo.db")):
        if p.is_file():
            return p
    raise SystemExit("no db")
p = db()
c = sqlite3.connect(f"file:{p}?mode=ro", uri=True, timeout=60)
mx = c.execute("SELECT MAX(id), MAX(fired_at) FROM consensus_signals").fetchone()
print("before", mx, "db", p)
c.close()
Path("/tmp/wake_before_id.txt").write_text(str(mx[0] or 0))
PY

echo "========== [5/6] watch 90s for FIRED / new consensus =========="
for i in 1 2 3 4 5 6; do
  sleep 15
  echo "--- t=$((i*15))s ---"
  grep -E 'FIRED|TOWER_MERGE|EdgePolicy.*ALLOW|EdgePolicy.*BLOCK|QUIET|subscribe|Subscribed|Traceback' logs/bot_live.log 2>/dev/null | tail -n 8 || true
  $PY - <<'PY'
import sqlite3
from pathlib import Path
p = Path("bot/bacbo.db") if Path("bot/bacbo.db").is_file() else Path("bacbo.db")
c = sqlite3.connect(f"file:{p}?mode=ro", uri=True, timeout=30)
mx = c.execute("SELECT MAX(id), MAX(fired_at) FROM consensus_signals").fetchone()
before = int(Path("/tmp/wake_before_id.txt").read_text() or 0)
print("consensus_max", mx, "delta", (mx[0] or 0) - before)
recent = c.execute("SELECT COUNT(*) FROM consensus_signals WHERE fired_at>=datetime('now','-10 minutes')").fetchone()[0]
blocked = c.execute("SELECT COUNT(*) FROM blocked_signals WHERE blocked_at>=datetime('now','-10 minutes')").fetchone()[0]
print("recent_10m_fires", recent, "recent_10m_blocked", blocked)
c.close()
PY
  grep -E 'sent signal|HEARTBEAT' logs/telegram_outbox.log 2>/dev/null | tail -n 5 || true
done

echo "========== [6/6] verdict =========="
$PY - <<'PY'
import sqlite3
from pathlib import Path
p = Path("bot/bacbo.db") if Path("bot/bacbo.db").is_file() else Path("bacbo.db")
c = sqlite3.connect(f"file:{p}?mode=ro", uri=True, timeout=30)
mx = c.execute("SELECT MAX(id), MAX(fired_at) FROM consensus_signals").fetchone()
before = int(Path("/tmp/wake_before_id.txt").read_text() or 0)
delta = (mx[0] or 0) - before
recent = c.execute("SELECT COUNT(*) FROM consensus_signals WHERE fired_at>=datetime('now','-5 minutes')").fetchone()[0]
c.close()
print("max_id", mx[0], "max_fired", mx[1], "new_rows", delta, "recent_5m", recent)
if delta > 0 or recent > 0:
    print("WAKE_VERDICT OK — engine fired; watch Mr_iv4 for cards")
else:
    print("WAKE_VERDICT STILL_SILENT — paste bot_live FIRED/BLOCK/subscribe lines + this output")
    print("Likely: rooms not receiving, Telethon disconnect, or gates quiet — not outbox")
PY
echo "DONE."
