#!/usr/bin/env bash
# Restore multi-floor luxury: rebuild floor allowlist, force EDGE_POLICY_MODE=luxury,
# peak-lock gates, restart with fallbacks. Fixes LIVE-only fires + SHADOW stuck mode.
set -euo pipefail
cd /home/runner/workspace
PY=python3
SHA="${LUXURY_PATCH_SHA:-cursor/add-engine-gate-registry-d5ba}"
BASE="https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/${SHA}/replit_elite_stack_patch"
PEER="${TELEGRAM_TARGET_PEER:-6774605259}"

echo "========== [1/7] stop =========="
pkill -9 -f 'bacbo_royal_complete.py' 2>/dev/null || true
pkill -9 -f 'runtime_supervisor.py' 2>/dev/null || true
pkill -9 -f 'fallback_signal_sender.py' 2>/dev/null || true
pkill -9 -f 'fallback_result_sender.py' 2>/dev/null || true
sleep 2

echo "========== [2/7] download luxury stack + supervisor =========="
mkdir -p bot/data logs
for rel in \
  bot/runtime_supervisor.py \
  bot/edge_live_policy.py \
  bot/luxury_building_stack.py \
  bot/floor_stack_registry.py \
  bot/gate_alias_resolve.py \
  bot/lux_no_hour_blocks.py \
  bot/lux_sqlite_harden.py \
  bot/lux_send_config_bind.py \
  bot/fallback_signal_sender.py \
  bot/fallback_result_sender.py \
  bot/data/luxury_live_floors.json \
  bot/data/luxury_building_stack.json \
  bot/data/historical_luxury_seed.json \
  bot/data/peak_lock_config.json \
  REPLIT_PEAK_LOCK_APPLY.sh
do
  echo "get $rel"
  curl -fsSL -H "Cache-Control: no-cache" -o "$rel" "$BASE/$rel"
done
chmod +x REPLIT_PEAK_LOCK_APPLY.sh
$PY -m py_compile bot/runtime_supervisor.py bot/edge_live_policy.py bot/luxury_building_stack.py

echo "========== [3/7] rebuild luxury floors from seed =========="
$PY <<'PY'
import json, os, subprocess, sys
from pathlib import Path

ROOT = Path("/home/runner/workspace")
BOT = ROOT / "bot"
DATA = BOT / "data"
db = BOT / "bacbo.db"
seed = DATA / "historical_luxury_seed.json"
env = os.environ.copy()
env["PYTHONPATH"] = f"{BOT}:{ROOT}:{env.get('PYTHONPATH','')}"

if not seed.exists():
    raise SystemExit("missing historical_luxury_seed.json")

cmd = [sys.executable, "-u", str(BOT / "luxury_building_stack.py"), "--db", str(db), "--seed", str(seed)]
print("run", " ".join(cmd))
subprocess.check_call(cmd, cwd=str(BOT), env=env)

report = json.loads((DATA / "luxury_building_stack.json").read_text())
live = [str(x).upper() for x in (report.get("live_building_floors") or [])]
blocked = [str(x).upper() for x in (report.get("blocked_floors") or ["JUN12A", "JUN12B"])]
peaks = []
for p in report.get("peak_day_floors") or []:
    if isinstance(p, dict) and p.get("floor"):
        peaks.append(str(p["floor"]).upper())
    elif isinstance(p, str):
        peaks.append(p.upper())
if not peaks:
    peaks = ["JUN19", "JUN20", "JUN08", "JUN10", "JUN26", "JUN27", "MAY19", "MAY10"]

# Merge prior gate_aliases if present
prior = {}
allow_path = DATA / "luxury_live_floors.json"
if allow_path.exists():
    try:
        prior = json.loads(allow_path.read_text())
    except Exception:
        prior = {}

allow = {
    "live_floors": live,
    "live_building_floors": live,  # both keys — old/new readers
    "blocked": blocked,
    "peak_day_floors": peaks,
    "virtual_setups": prior.get("virtual_setups")
    or ["SOLO_ELITE|BLUE", "GOLDEN|BLUE", "SEQUENCE|BLUE", "PLATINUM|BLUE", "SEQUENCE"],
    "gate_aliases": prior.get("gate_aliases") or {},
    "peak_lock": True,
}
allow_path.write_text(json.dumps(allow, indent=2) + "\n")
print("live_floors", len(live))
print("sample", live[:15])
print("peaks", peaks)
print("blocked", blocked)
if len(live) < 5:
    raise SystemExit("FAIL: live floor list too small after rebuild")
PY

echo "========== [4/7] peak-lock apply =========="
bash REPLIT_PEAK_LOCK_APPLY.sh || {
  echo "WARN peak-lock script exited non-zero — continuing with floor JSON already written"
}

echo "========== [5/7] force luxury_building.env (overwrite shadow secrets) =========="
$PY <<PY
import json
from pathlib import Path
ROOT = Path("/home/runner/workspace")
allow = json.loads((ROOT / "bot/data/luxury_live_floors.json").read_text())
live = allow.get("live_floors") or allow.get("live_building_floors") or []
peer = "${PEER}"
body = f"""# Luxury building runtime — FORCE luxury (supervisor overwrites Secrets)
export EDGE_POLICY_MODE=luxury
export EDGE_LUXURY_FLOOR_GATE=1
export EDGE_LEGACY_355_WARN=1
export FALLBACKS_ENABLED=1
export FALLBACK_SEND_BLOCKED=0
export LUXURY_NO_HOUR_BLOCKS=1
export BOT_TZ=America/Sao_Paulo
export TELEGRAM_TARGET_PEER={peer}
export LUXURY_LIVE_FLOORS={",".join(live)}
"""
(ROOT / "luxury_building.env").write_text(body)
print("wrote luxury_building.env floors", len(live), "peer", peer)
# prove edge policy sees floors
import sys
sys.path.insert(0, str(ROOT / "bot"))
import edge_live_policy as elp
live_set, blocked = elp._luxury_sets()
print("edge_live_policy live_count", len(live_set), "blocked", sorted(blocked))
print("has_JUN19", "JUN19" in live_set, "has_JUN20", "JUN20" in live_set)
# mode with forced env
import os
os.environ["EDGE_POLICY_MODE"] = "luxury"
v = elp.evaluate("GOLDEN", "blue", ["@rqdados"], source_floor="JUN19")
print("sample_verdict_JUN19", v)
PY

echo "========== [6/7] restart supervisor =========="
set -a
# shellcheck disable=SC1091
source ./luxury_building.env
set +a
export TELEGRAM_SESSION_STRING="$(tr -d '\n' < .telegram_session_string)"
export TELEGRAM_TARGET_PEER="$PEER"
# Explicit force — do not inherit Secret=shadow
export EDGE_POLICY_MODE=luxury
export EDGE_LUXURY_FLOOR_GATE=1
export FALLBACKS_ENABLED=1
export LUXURY_NO_HOUR_BLOCKS=1

nohup env EDGE_POLICY_MODE=luxury EDGE_LUXURY_FLOOR_GATE=1 FALLBACKS_ENABLED=1 \
  FALLBACK_SEND_BLOCKED=0 LUXURY_NO_HOUR_BLOCKS=1 BOT_TZ=America/Sao_Paulo \
  TELEGRAM_SESSION_STRING="$TELEGRAM_SESSION_STRING" \
  TELEGRAM_TARGET_PEER="$PEER" \
  $PY -u bot/runtime_supervisor.py > /tmp/luxury_supervisor.log 2>&1 &
echo "supervisor pid=$!"

echo "========== [7/7] settle 55s + verdict =========="
sleep 25
pgrep -af 'runtime_supervisor|bacbo_royal|fallback_' || echo NONE
sleep 30

$PY <<'PY'
import os, json, sqlite3, subprocess
from pathlib import Path

print("--- supervisor log head ---")
print(Path("/tmp/luxury_supervisor.log").read_text(errors="replace")[:800])

# Process env of bacbo
pid = subprocess.getoutput("pgrep -n -f 'bacbo_royal_complete.py'").strip()
print("bacbo_pid", pid)
if pid.isdigit():
    try:
        env = Path(f"/proc/{pid}/environ").read_bytes().split(b"\0")
        kv = {}
        for e in env:
            if b"=" in e:
                k, v = e.split(b"=", 1)
                kv[k.decode(errors="replace")] = v.decode(errors="replace")
        for k in ("EDGE_POLICY_MODE", "EDGE_LUXURY_FLOOR_GATE", "FALLBACKS_ENABLED", "LUXURY_LIVE_FLOORS"):
            val = kv.get(k, "(unset)")
            if k == "LUXURY_LIVE_FLOORS" and len(val) > 80:
                val = val[:80] + f"...({len(val.split(','))} floors)"
            print(f"proc_{k}", val)
    except Exception as exc:
        print("proc_env_error", exc)

allow = json.loads(Path("bot/data/luxury_live_floors.json").read_text())
live = allow.get("live_floors") or allow.get("live_building_floors") or []
print("json_live_floors", len(live), "sample", live[:12])
print("peak_lock", allow.get("peak_lock"))
print("aliases", len(allow.get("gate_aliases") or {}))

db = Path("bot/bacbo.db") if Path("bot/bacbo.db").exists() else Path("bacbo.db")
con = sqlite3.connect(str(db))
print("floors_last_6h", list(con.execute(
    "select coalesce(source_floor,'NULL'), count(*) from consensus_signals "
    "where fired_at>=datetime('now','-6 hours') group by 1 order by 2 desc")))
print("last8", list(con.execute(
    "select id,fired_at,signal_kind,source_floor from consensus_signals order by id desc limit 8")))

print("--- EdgePolicy / floor lines (post boot) ---")
log = Path("logs/bot_live.log")
lines = log.read_text(errors="replace").splitlines() if log.exists() else []
cut = 0
for i, ln in enumerate(lines):
    if "[BootFilter]" in ln or "EDGE_POLICY_MODE" in ln:
        cut = i
post = lines[cut:]
for ln in post:
    if "EdgePolicy" in ln or "source_floor" in ln or "get_floor" in ln or "FLOOR" in ln and "LUXURY" in ln:
        print(ln)
# also last few EdgePolicy from whole file
print("--- last EdgePolicy anywhere ---")
print(subprocess.getoutput("grep -E 'EdgePolicy|EDGE_LUXURY|\\[Floor' logs/bot_live.log | tail -n 15"))
print("--- last 12 bot ---")
for ln in lines[-12:]:
    print(ln)
PY

echo
echo "VERDICT:"
echo "  - proc_EDGE_POLICY_MODE must be luxury (not shadow/unset)"
echo "  - json_live_floors should be ~30+"
echo "  - new fires may still show LIVE until floor rotator advances; watch for JUN19/JUN20 in source_floor"
echo
echo "DONE. Paste ALL output."
