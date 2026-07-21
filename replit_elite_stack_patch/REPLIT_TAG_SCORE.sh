#!/usr/bin/env bash
# Hot-fix outbox: JUN19+ floor tags + real SCORE. Keeps bacbo up.
# Fixes: tag_floor stuck LIVE (DEFER + init bug), orphan outbox/legacy, dead supervisor.
set -euo pipefail
cd /home/runner/workspace
PY=python3
SHA="${LUXURY_PATCH_SHA:-cursor/add-engine-gate-registry-d5ba}"
BASE="https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/${SHA}/replit_elite_stack_patch"
PEER="${TELEGRAM_TARGET_PEER:-6774605259}"

echo "========== [1/5] refresh bits =========="
mkdir -p bot/data logs
for rel in bot/telegram_outbox.py bot/lux_floor_rotate.py bot/runtime_supervisor.py; do
  curl -fsSL -H "Cache-Control: no-cache" -o "$rel" "$BASE/$rel"
done
$PY -m py_compile bot/telegram_outbox.py bot/lux_floor_rotate.py bot/runtime_supervisor.py

echo "========== [2/5] env (force apply, no DEFER for tag smoke) =========="
# Keep luxury policy; clear DEFER so tag_floor initializes to JUN19 immediately.
if [ -f luxury_building.env ]; then
  grep -v 'LUXURY_FLOOR_ROTATE_DEFER_APPLY' luxury_building.env > luxury_building.env.tmp || true
  mv luxury_building.env.tmp luxury_building.env
fi
cat >> luxury_building.env <<EOF
export TELEGRAM_SINGLE_OUTBOX=1
export FALLBACKS_ENABLED=1
export FALLBACK_START_DELAY_SECS=15
export LUXURY_FLOOR_ROTATE=1
export LUXURY_FLOOR_ROTATE_MODE=tag
export LUXURY_FLOOR_ROTATE_DEFER_APPLY=0
export TELEGRAM_TARGET_PEER=${PEER}
export TELEGRAM_OUTBOX_STARTUP_PING=1
EOF
# de-dupe keys (last wins) — simple rewrite of critical exports
$PY <<'PY'
from pathlib import Path
p = Path("luxury_building.env")
keys = {}
order = []
for ln in p.read_text().splitlines():
    s = ln.strip()
    if not s or s.startswith("#") or "=" not in s:
        continue
    if s.startswith("export "):
        s = s[7:].strip()
    k, v = s.split("=", 1)
    k = k.strip()
    if k not in keys:
        order.append(k)
    keys[k] = v.strip()
keys.update({
    "TELEGRAM_SINGLE_OUTBOX": "1",
    "FALLBACKS_ENABLED": "1",
    "FALLBACK_START_DELAY_SECS": "15",
    "LUXURY_FLOOR_ROTATE": "1",
    "LUXURY_FLOOR_ROTATE_MODE": "tag",
    "LUXURY_FLOOR_ROTATE_DEFER_APPLY": "0",
    "TELEGRAM_OUTBOX_STARTUP_PING": "1",
    "EDGE_POLICY_MODE": keys.get("EDGE_POLICY_MODE", "luxury"),
})
for k in (
    "TELEGRAM_SINGLE_OUTBOX",
    "FALLBACKS_ENABLED",
    "FALLBACK_START_DELAY_SECS",
    "LUXURY_FLOOR_ROTATE",
    "LUXURY_FLOOR_ROTATE_MODE",
    "LUXURY_FLOOR_ROTATE_DEFER_APPLY",
    "TELEGRAM_OUTBOX_STARTUP_PING",
    "EDGE_POLICY_MODE",
):
    if k not in order:
        order.append(k)
p.write_text("\n".join(f"export {k}={keys[k]}" for k in order if k in keys) + "\n")
print("luxury_building.env keys", len(keys), "DEFER", keys.get("LUXURY_FLOOR_ROTATE_DEFER_APPLY"))
PY

echo "========== [3/5] kill ALL telegram session stealers (bacbo stays) =========="
pkill -9 -f 'telegram_outbox.py' 2>/dev/null || true
pkill -9 -f 'fallback_signal_sender.py' 2>/dev/null || true
pkill -9 -f 'fallback_result_sender.py' 2>/dev/null || true
# Dead supervisor leaves orphans — restart supervisor so only ONE outbox returns
pkill -9 -f 'runtime_supervisor.py' 2>/dev/null || true
sleep 2
rm -f bot/data/telegram_outbox.lock 2>/dev/null || true
pgrep -af 'telegram_outbox|fallback_signal|fallback_result|runtime_supervisor' || echo "senders clean"

echo "========== [4/5] stamp JUN19 + restart supervisor (bacbo untouched) =========="
export LUXURY_FLOOR_ROTATE=1
export LUXURY_FLOOR_ROTATE_MODE=tag
export LUXURY_FLOOR_ROTATE_DEFER_APPLY=0
export TELEGRAM_SINGLE_OUTBOX=1
export PYTHONPATH="/home/runner/workspace/bot:/home/runner/workspace:${PYTHONPATH:-}"

$PY <<'PY'
import os, sys, json, sqlite3
from pathlib import Path
sys.path.insert(0, "bot")
os.environ["LUXURY_FLOOR_ROTATE"] = "1"
os.environ["LUXURY_FLOOR_ROTATE_MODE"] = "tag"
os.environ["LUXURY_FLOOR_ROTATE_DEFER_APPLY"] = "0"

jp = Path("bot/data/luxury_live_floors.json")
if jp.exists():
    data = json.loads(jp.read_text())
    peaks = data.get("peak_day_floors") or []
    live = data.get("live_floors") or data.get("live_building_floors") or []
    print("json_peaks", peaks[:5], "json_live_n", len(live))
else:
    print("WARN missing", jp)

import importlib
import lux_floor_rotate
# Force immediate apply (ignore any prior DEFER thread state via reload)
importlib.reload(lux_floor_rotate)
lux_floor_rotate.apply()
floors = lux_floor_rotate._rotation_list()
print("rotation0", floors[:5], "n", len(floors))
print("tag_floor", lux_floor_rotate.tag_floor())
print("mode", lux_floor_rotate._mode())
n = lux_floor_rotate.stamp_live_rows(limit=40)
print("stamped", n)
db = Path("bot/bacbo.db") if Path("bot/bacbo.db").exists() else Path("bacbo.db")
con = sqlite3.connect(str(db))
print("last8", list(con.execute(
    "select id,signal_kind,source_floor,"
    "coalesce(total_score,0),coalesce(final_score,0),coalesce(confidence_pct,0) "
    "from consensus_signals order by id desc limit 8")))
# score smoke: outbox should pick confidence 85 for 1770
from telegram_outbox import _row_score, _row_floor
row = con.execute(
    "select id,source_floor,total_score,final_score,confidence_pct,calibrated_pct "
    "from consensus_signals where id=1770"
).fetchone()
if row:
    class R(dict):
        def __getitem__(self, k):
            if isinstance(k, int):
                return list(self.values())[k]
            return dict.__getitem__(self, k)
    # sqlite Row-like
    cols = ["id","source_floor","total_score","final_score","confidence_pct","calibrated_pct"]
    class Fake:
        def __init__(self, t):
            self._t = t
            self._m = dict(zip(cols, t))
        def __getitem__(self, k):
            return self._m[k]
    fr = Fake(row)
    print("smoke_1770_floor", _row_floor(fr), "smoke_1770_score", _row_score(fr))
PY

set -a
# shellcheck disable=SC1091
source ./luxury_building.env
set +a
export TELEGRAM_SESSION_STRING="$(tr -d '\n' < .telegram_session_string)"
export TELEGRAM_TARGET_PEER="$PEER"
export TELEGRAM_SINGLE_OUTBOX=1
export FALLBACKS_ENABLED=1
export FALLBACK_START_DELAY_SECS=15
export LUXURY_FLOOR_ROTATE_DEFER_APPLY=0
export PYTHONPATH="/home/runner/workspace/bot:/home/runner/workspace:${PYTHONPATH:-}"

nohup env EDGE_POLICY_MODE=luxury EDGE_LUXURY_FLOOR_GATE=1 FALLBACKS_ENABLED=1 \
  TELEGRAM_SINGLE_OUTBOX=1 FALLBACK_START_DELAY_SECS=15 FALLBACK_SEND_BLOCKED=0 \
  LUXURY_FLOOR_ROTATE=1 LUXURY_FLOOR_ROTATE_MODE=tag LUXURY_FLOOR_ROTATE_DEFER_APPLY=0 \
  TELEGRAM_SESSION_STRING="$TELEGRAM_SESSION_STRING" \
  TELEGRAM_TARGET_PEER="$PEER" \
  TELEGRAM_OUTBOX_STARTUP_PING=1 \
  PYTHONPATH="$PYTHONPATH" \
  $PY -u bot/runtime_supervisor.py > /tmp/luxury_supervisor.log 2>&1 &
echo "supervisor pid=$!"

echo "========== [5/5] settle 25s + verdict =========="
sleep 25
$PY <<'PY'
import subprocess
from pathlib import Path
print("bacbo", subprocess.getoutput("pgrep -fc bacbo_royal_complete.py || echo 0"))
print("supervisor", subprocess.getoutput("pgrep -fc runtime_supervisor.py || echo 0"))
print("outbox", subprocess.getoutput("pgrep -fc telegram_outbox.py || echo 0"))
print("legacy_fb", subprocess.getoutput(
    "pgrep -fc 'fallback_signal_sender.py|fallback_result_sender.py' || echo 0"))
print("--- supervisor ---")
print(Path("/tmp/luxury_supervisor.log").read_text(errors="replace")[-800:])
print("--- outbox tail ---")
p = Path("logs/telegram_outbox.log")
print("\n".join(p.read_text(errors="replace").splitlines()[-12:]) if p.exists() else "missing")
PY

echo
echo "EXPECT:"
echo "  tag_floor = JUN19 (not LIVE)"
echo "  stamped > 0  OR last8 source_floor = JUN19"
echo "  smoke_1770_score = 85"
echo "  bacbo>=1 supervisor>=1 outbox=1 legacy_fb=0"
echo "  Telegram: OUTBOX ONLINE; next FIRED card FLOOR JUN19 + SCORE 85-ish"
echo
echo "DONE. Paste ALL output."
