#!/usr/bin/env bash
# Peak-pure fire mode:
# - keep peak-lock floors (peak day engines)
# - DISABLE hour blocks / AutoCHB dynamic hour bans / AutoIntel bad hours
# - fallbacks ON (signal card + result card to TARGET)
set -euo pipefail
cd /home/runner/workspace
PY=python3
SHA="${LUXURY_PATCH_SHA:-cursor/add-engine-gate-registry-d5ba}"
BASE="https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/${SHA}/replit_elite_stack_patch"

echo "========== [1/5] stop =========="
pkill -9 -f 'bacbo_royal_complete.py' 2>/dev/null || true
pkill -9 -f 'runtime_supervisor.py' 2>/dev/null || true
pkill -9 -f 'fallback_signal_sender.py' 2>/dev/null || true
pkill -9 -f 'fallback_result_sender.py' 2>/dev/null || true
sleep 2

echo "========== [2/5] download peak-pure bits =========="
mkdir -p bot/data logs
curl -fsSL -H "Cache-Control: no-cache" -o bot/lux_no_hour_blocks.py "$BASE/bot/lux_no_hour_blocks.py"
curl -fsSL -H "Cache-Control: no-cache" -o bot/lux_sqlite_harden.py "$BASE/bot/lux_sqlite_harden.py"
curl -fsSL -H "Cache-Control: no-cache" -o bot/runtime_supervisor.py "$BASE/bot/runtime_supervisor.py"
curl -fsSL -H "Cache-Control: no-cache" -o bot/fallback_signal_sender.py "$BASE/bot/fallback_signal_sender.py"
curl -fsSL -H "Cache-Control: no-cache" -o bot/fallback_result_sender.py "$BASE/bot/fallback_result_sender.py"
$PY -m py_compile bot/lux_no_hour_blocks.py bot/lux_sqlite_harden.py bot/runtime_supervisor.py

echo "========== [3/5] clear hour-block state + inject into bacbo =========="
$PY <<'PY'
import ast, json, re
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path("/home/runner/workspace")
DATA = ROOT / "bot" / "data"
DATA.mkdir(parents=True, exist_ok=True)

# 1) Empty dynamic color-hour blocks (AutoCHB)
chb = {
    "rev": "luxury-peak-pure",
    "updated_at": datetime.now(timezone.utc).isoformat(),
    "note": "Hour blocks disabled for luxury peak-pure fire mode.",
    "dynamic_additions": {"GOLDEN": [], "SOLO_ELITE": [], "FLASH": [], "PLATINUM": []},
}
(DATA / "color_hour_blocks.json").write_text(json.dumps(chb, indent=2) + "\n")
print("cleared color_hour_blocks.json")

# 2) Clear AutoIntel bad hours (keep good pairs)
intel = DATA / "intelligence_state.json"
if intel.exists():
    try:
        d = json.loads(intel.read_text())
    except Exception:
        d = {}
else:
    d = {}
d["dynamic_platinum_bad_hrs"] = []
d["dynamic_solo_bad_hrs"] = []
d["dynamic_golden_bad_hrs"] = []
# common alt keys
for k in list(d.keys()):
    if "bad_hr" in k.lower() or "bad_hour" in k.lower():
        if isinstance(d[k], list):
            d[k] = []
        elif isinstance(d[k], dict):
            d[k] = {}
intel.write_text(json.dumps(d, indent=2) + "\n")
print("cleared intelligence bad hours", {k: d.get(k) for k in d if "bad" in k.lower() or "pair" in k.lower()})

# 3) Inject lux_no_hour_blocks into bacbo next to sqlite harden
p = ROOT / "bacbo_royal_complete.py"
src = p.read_text(encoding="utf-8", errors="replace")
block = '''
# --- LUXURY_NO_HOUR_BLOCKS (auto) ---
try:
    import lux_no_hour_blocks  # noqa: F401
    print("[LUXURY] peak-pure: hour blocks OFF (peak floors kept)")
except Exception as _lux_nhb_exc:
    print("[LUXURY] no_hour_blocks skipped:", _lux_nhb_exc)
# --- end LUXURY_NO_HOUR_BLOCKS ---
'''
src = re.sub(
    r"\n# --- LUXURY_NO_HOUR_BLOCKS \(auto\) ---.*?--- end LUXURY_NO_HOUR_BLOCKS ---\n",
    "\n",
    src,
    flags=re.S,
)
# Prefer insert right after sqlite harden end, else after BOOT
if "LUXURY_SQLITE_HARDEN" in src:
    src = src.replace(
        "# --- end LUXURY_SQLITE_HARDEN ---\n",
        "# --- end LUXURY_SQLITE_HARDEN ---\n" + block,
        1,
    )
else:
    lines = src.splitlines(True)
    idx = 0
    for i, ln in enumerate(lines):
        if "[BOOT] all imports OK" in ln or "[BOOT] stdlib imports OK" in ln:
            idx = i + 1
            break
    lines.insert(idx or 40, block)
    src = "".join(lines)

# Ensure SESSION_AND_BIND + state force still present
if "LUXURY_SESSION_AND_BIND" not in src:
    raise SystemExit("SESSION_AND_BIND missing — run FIX_NOW / GO.sh first")
if "state = _lux_state_mod" not in src:
    force = (
        "# --- LUXURY_STATE_NAME_FORCE (auto) ---\n"
        "import state as _lux_state_mod\n"
        "state = _lux_state_mod\n"
        "# --- end LUXURY_STATE_NAME_FORCE ---\n"
    )
    src = re.sub(r"^(state\.engine\s*=)", force + r"\1", src, count=1, flags=re.M)

ast.parse(src)
p.write_text(src, encoding="utf-8")
print("bacbo patched", p.stat().st_size)
print("has_no_hour_blocks", "LUXURY_NO_HOUR_BLOCKS" in src)
print("has_session_bind", "LUXURY_SESSION_AND_BIND" in src)
PY

echo "========== [4/5] env peak-pure + fallbacks =========="
cat > luxury_building.env <<'EOF'
export EDGE_POLICY_MODE=luxury
export EDGE_LUXURY_FLOOR_GATE=1
export LUXURY_NO_HOUR_BLOCKS=1
export FALLBACK_SEND_BLOCKED=0
export FALLBACKS_ENABLED=1
export FALLBACK_START_DELAY_SECS=15
export TELEGRAM_TARGET_PEER=6774605259
export BOT_TZ=America/Sao_Paulo
EOF

set -a
source ./luxury_building.env
set +a
export TELEGRAM_SESSION_STRING="$(tr -d '\n' < .telegram_session_string)"
export PYTHONPATH="/home/runner/workspace/bot:/home/runner/workspace:${PYTHONPATH:-}"

$PY -m py_compile bacbo_royal_complete.py
echo "compile OK"

echo "===== PEAK_PURE marker $(date -u +%Y-%m-%dT%H:%M:%SZ) =====" >> logs/bot_live.log

nohup env EDGE_POLICY_MODE=luxury EDGE_LUXURY_FLOOR_GATE=1 LUXURY_NO_HOUR_BLOCKS=1 \
  FALLBACKS_ENABLED=1 FALLBACK_START_DELAY_SECS=15 FALLBACK_SEND_BLOCKED=0 \
  BOT_TZ=America/Sao_Paulo \
  TELEGRAM_SESSION_STRING="$TELEGRAM_SESSION_STRING" \
  TELEGRAM_TARGET_PEER=6774605259 \
  PYTHONPATH="$PYTHONPATH" \
  python3 -u bot/runtime_supervisor.py > /tmp/luxury_supervisor.log 2>&1 &
echo "supervisor pid=$!"

echo "========== [5/5] settle + verdict =========="
sleep 25
pgrep -af 'runtime_supervisor|bacbo_royal|fallback_' || true
grep -E 'NO_HOUR_BLOCKS|peak-pure|run_forever|NameError|FIRED|Blocked-hour|QUIET|FallbackSender' logs/bot_live.log | tail -n 40 || true
sleep 40

$PY <<'PY'
from pathlib import Path
import re, subprocess, json
log = Path("logs/bot_live.log").read_text(errors="ignore")
idx = log.rfind("===== PEAK_PURE marker")
chunk = log[idx:] if idx >= 0 else log[-10000:]
print("no_hour_blocks_boot", "NO_HOUR_BLOCKS" in chunk or "peak-pure" in chunk)
print("run_forever", "run_forever" in chunk or "starting run_forever()" in chunk)
print("NameError_state", "NameError: name 'state'" in chunk)
print("Blocked-hour_post", len(re.findall(r"Blocked-hour", chunk)))
print("FIRED_post", len(re.findall(r"FIRED|SEQUENCE/FIRED", chunk)))
print("QUIET_post", len(re.findall(r"QUIET — no signal fired", chunk)))
chb = json.loads(Path("bot/data/color_hour_blocks.json").read_text())
print("dynamic_blocks", chb.get("dynamic_additions"))
intel = json.loads(Path("bot/data/intelligence_state.json").read_text()) if Path("bot/data/intelligence_state.json").exists() else {}
print("solo_bad_hrs", intel.get("dynamic_solo_bad_hrs"))
print("plat_bad_hrs", intel.get("dynamic_platinum_bad_hrs"))
print("--- procs ---")
print(subprocess.getoutput("pgrep -af 'runtime_supervisor|bacbo_royal|fallback_' || echo NONE"))
print("--- last 22 ---")
print("\n".join(Path("logs/bot_live.log").read_text(errors="ignore").splitlines()[-22:]))
procs = subprocess.getoutput("pgrep -af 'bacbo_royal|fallback_signal' || true")
ok = "bacbo_royal" in procs and "fallback_signal" in procs and "NameError: name 'state'" not in chunk and ("NO_HOUR_BLOCKS" in chunk or "peak-pure" in chunk)
print("VERDICT:", "OK — peak-pure + fallbacks (no hour blocks)" if ok else "BAD — paste ALL output")
PY

echo
echo "DONE. Paste ALL output."
echo "Policy: peak floors kept; hour blocks OFF; signal+result fallbacks ON."
