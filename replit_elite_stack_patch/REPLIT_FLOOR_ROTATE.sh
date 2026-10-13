#!/usr/bin/env bash
# Force multi-floor tagging: rotate get_floor / source_floor off LIVE-only.
# Prerequisite: luxury building already installed (32 floors, MODE=luxury).
# Also kills duplicate supervisors left by peak-lock nested restart.
set -euo pipefail
cd /home/runner/workspace
PY=python3
SHA="${LUXURY_PATCH_SHA:-cursor/add-engine-gate-registry-d5ba}"
BASE="https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/${SHA}/replit_elite_stack_patch"
PEER="${TELEGRAM_TARGET_PEER:-6774605259}"

echo "========== [1/6] hard-stop ALL bot procs (no dup supervisors) =========="
pkill -9 -f 'bacbo_royal_complete.py' 2>/dev/null || true
pkill -9 -f 'runtime_supervisor.py' 2>/dev/null || true
pkill -9 -f 'fallback_signal_sender.py' 2>/dev/null || true
pkill -9 -f 'fallback_result_sender.py' 2>/dev/null || true
sleep 3
pgrep -af 'runtime_supervisor|bacbo_royal|fallback_' || echo "clean"

echo "========== [2/6] download rotator + supervisor =========="
mkdir -p bot/data logs
for rel in \
  bot/lux_floor_rotate.py \
  bot/lux_floor_expand.py \
  bot/gate_alias_resolve.py \
  bot/runtime_supervisor.py \
  bot/fallback_signal_sender.py \
  bot/fallback_result_sender.py
do
  curl -fsSL -H "Cache-Control: no-cache" -o "$rel" "$BASE/$rel"
done
$PY -m py_compile bot/lux_floor_rotate.py bot/lux_floor_expand.py bot/runtime_supervisor.py

echo "========== [3/6] diagnose floor_tracker + patch source_floor LIVE hardcodes =========="
$PY <<'PY'
import ast, re, time
from pathlib import Path

ROOT = Path("/home/runner/workspace")
BOT = ROOT / "bot"

# --- diagnose floor_tracker ---
ft = BOT / "floor_tracker.py"
if ft.exists():
    src = ft.read_text(encoding="utf-8", errors="replace")
    print("floor_tracker bytes", len(src))
    for pat in ("def get_floor", "def set_floor", "ENABLED_FLOORS", "LIVE_FLOORS", "CURRENT_FLOOR", "source_floor"):
        print(f"  has_{pat.replace(' ','_')}", pat in src)
    # show get_floor body snippet
    m = re.search(r"def get_floor\([^)]*\):([\s\S]{0,400})", src)
    if m:
        print("--- get_floor snippet ---")
        print(m.group(0)[:450])
else:
    print("WARN floor_tracker.py MISSING")

# --- replace hardcoded source_floor='LIVE' with get_floor() in key files ---
targets = [
    BOT / "signal_handler.py",
    ROOT / "bacbo_royal_complete.py",
]
changed_files = []
for p in targets:
    if not p.exists():
        print("skip missing", p.name)
        continue
    src = p.read_text(encoding="utf-8", errors="replace")
    orig = src
    # common hardcodes
    repls = [
        (r'source_floor\s*=\s*["\']LIVE["\']', 'source_floor=get_floor()'),
        (r'source_floor\s*=\s*["\']live["\']', 'source_floor=get_floor()'),
        (r'(["\']source_floor["\']\s*:\s*)["\']LIVE["\']', r'\1get_floor()'),
    ]
    n = 0
    for pat, rep in repls:
        src2, c = re.subn(pat, rep, src)
        if c:
            src = src2
            n += c
    if n and "from floor_tracker import get_floor" not in src and "import floor_tracker" not in src:
        # ensure get_floor import near top
        lines = src.splitlines(True)
        idx = 0
        for i, ln in enumerate(lines[:80]):
            if ln.startswith("import ") or ln.startswith("from ") or not ln.strip() or ln.strip().startswith("#"):
                idx = i + 1
            else:
                break
        lines.insert(idx, "from floor_tracker import get_floor  # LUXURY floor-rotate\n")
        src = "".join(lines)
        print(p.name, "added get_floor import")
    if src != orig:
        bak = Path(str(p) + f".bak_pre_floor_rotate_{int(time.time())}")
        bak.write_text(orig, encoding="utf-8")
        try:
            ast.parse(src)
        except SyntaxError as e:
            print(p.name, "SYNTAX after replace — skip", e)
            continue
        p.write_text(src, encoding="utf-8")
        changed_files.append((p.name, n))
        print(p.name, "replaced hardcoded LIVE source_floor x", n, "bak", bak.name)
    else:
        print(p.name, "no LIVE source_floor hardcodes matched")

print("changed", changed_files)

# --- inject lux_floor_rotate into bacbo ---
bacbo = ROOT / "bacbo_royal_complete.py"
bsrc = bacbo.read_text(encoding="utf-8", errors="replace")
if "LUXURY_FLOOR_ROTATE" not in bsrc:
    block = '''
# --- LUXURY_FLOOR_ROTATE (auto) ---
try:
    import lux_floor_rotate  # noqa: F401
    print("[LUXURY] floor-rotate module loaded")
except Exception as _lux_fr_exc:
    print("[LUXURY] floor-rotate skipped:", _lux_fr_exc)
# --- end LUXURY_FLOOR_ROTATE ---
'''
    # prefer before __main__ / after floor expand
    m = re.search(r"# --- end LUXURY_FLOOR_EXPAND ---", bsrc)
    if m:
        bsrc = bsrc[: m.end()] + "\n" + block + bsrc[m.end() :]
    else:
        m2 = re.search(r"^if __name__", bsrc, re.M)
        if m2:
            bsrc = bsrc[: m2.start()] + block + "\n" + bsrc[m2.start() :]
        else:
            bsrc = bsrc + "\n" + block
    ast.parse(bsrc)
    bacbo.write_text(bsrc, encoding="utf-8")
    print("injected LUXURY_FLOOR_ROTATE into bacbo")
else:
    print("bacbo already has LUXURY_FLOOR_ROTATE")

# also ensure expand present
if "LUXURY_FLOOR_EXPAND" not in bacbo.read_text(encoding="utf-8", errors="replace"):
    block = '''
# --- LUXURY_FLOOR_EXPAND (auto) ---
try:
    import lux_floor_expand  # noqa: F401
except Exception as _lux_fe_exc:
    print("[LUXURY] floor-expand skipped:", _lux_fe_exc)
# --- end LUXURY_FLOOR_EXPAND ---
'''
    t = bacbo.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"# --- LUXURY_FLOOR_ROTATE", t)
    if m:
        t = t[: m.start()] + block + "\n" + t[m.start() :]
    else:
        t = t + "\n" + block
    bacbo.write_text(t, encoding="utf-8")
    print("injected LUXURY_FLOOR_EXPAND")
PY

echo "========== [4/6] force luxury env =========="
$PY <<PY
import json, re
from pathlib import Path
ROOT = Path("/home/runner/workspace")
allow = json.loads((ROOT/"bot/data/luxury_live_floors.json").read_text())
live = allow.get("live_floors") or allow.get("live_building_floors") or []
peer = "${PEER}"
(ROOT/"luxury_building.env").write_text(f"""# Luxury + floor rotate
export EDGE_POLICY_MODE=luxury
export EDGE_LUXURY_FLOOR_GATE=1
export EDGE_LEGACY_355_WARN=1
export FALLBACKS_ENABLED=1
export FALLBACK_SEND_BLOCKED=0
export LUXURY_NO_HOUR_BLOCKS=1
export LUXURY_FLOOR_ROTATE=1
export LUXURY_FLOOR_ROTATE_SECS=180
export BOT_TZ=America/Sao_Paulo
export TELEGRAM_TARGET_PEER={peer}
export LUXURY_LIVE_FLOORS={",".join(live)}
""")
envp = ROOT/".env"
lines=[]
if envp.exists():
    for ln in envp.read_text(errors="ignore").splitlines():
        if re.match(r"^\s*(export\s+)?(EDGE_POLICY_MODE|EDGE_LUXURY_FLOOR_GATE|FALLBACKS_ENABLED|FALLBACK_SEND_BLOCKED|LUXURY_NO_HOUR_BLOCKS|LUXURY_FLOOR_ROTATE)\s*=", ln):
            continue
        lines.append(ln)
lines += [
    "EDGE_POLICY_MODE=luxury",
    "EDGE_LUXURY_FLOOR_GATE=1",
    "FALLBACKS_ENABLED=1",
    "FALLBACK_SEND_BLOCKED=0",
    "LUXURY_NO_HOUR_BLOCKS=1",
    "LUXURY_FLOOR_ROTATE=1",
    "LUXURY_FLOOR_ROTATE_SECS=180",
]
envp.write_text("\n".join(lines).rstrip()+"\n")
print("env forced floors", len(live))
PY

echo "========== [5/6] restart SINGLE supervisor =========="
set -a
# shellcheck disable=SC1091
source ./luxury_building.env
set +a
export TELEGRAM_SESSION_STRING="$(tr -d '\n' < .telegram_session_string)"
export TELEGRAM_TARGET_PEER="$PEER"
export EDGE_POLICY_MODE=luxury
export LUXURY_FLOOR_ROTATE=1
export LUXURY_FLOOR_ROTATE_SECS=180

nohup env EDGE_POLICY_MODE=luxury EDGE_LUXURY_FLOOR_GATE=1 FALLBACKS_ENABLED=1 \
  FALLBACK_SEND_BLOCKED=0 LUXURY_NO_HOUR_BLOCKS=1 \
  LUXURY_FLOOR_ROTATE=1 LUXURY_FLOOR_ROTATE_SECS=180 \
  BOT_TZ=America/Sao_Paulo \
  TELEGRAM_SESSION_STRING="$TELEGRAM_SESSION_STRING" \
  TELEGRAM_TARGET_PEER="$PEER" \
  $PY -u bot/runtime_supervisor.py > /tmp/luxury_supervisor.log 2>&1 &
echo "supervisor pid=$!"
sleep 2
# assert only one supervisor
nsup=$(pgrep -fc 'runtime_supervisor.py' || true)
echo "supervisor_count=$nsup"
if [ "${nsup:-0}" -gt 1 ]; then
  echo "WARN multiple supervisors — killing extras, keeping newest"
  newest=$(pgrep -n -f 'runtime_supervisor.py')
  for p in $(pgrep -f 'runtime_supervisor.py'); do
    if [ "$p" != "$newest" ]; then kill -9 "$p" 2>/dev/null || true; fi
  done
fi

echo "========== [6/6] settle 50s + verdict =========="
sleep 25
pgrep -af 'runtime_supervisor|bacbo_royal|fallback_' || echo NONE
sleep 25

$PY <<'PY'
import sqlite3, subprocess, re
from pathlib import Path

print("--- supervisor ---")
print(Path("/tmp/luxury_supervisor.log").read_text(errors="replace")[:900])
print("supervisor_count", subprocess.getoutput("pgrep -fc runtime_supervisor.py"))
print("bacbo_count", subprocess.getoutput("pgrep -fc bacbo_royal_complete.py"))

# boot lines for rotate
log = Path("logs/bot_live.log")
text = log.read_text(errors="replace") if log.exists() else ""
for key in ("floor-rotate", "FLOOR_ROTATE", "get_floor", "EdgePolicy"):
    hits = [ln for ln in text.splitlines() if key in ln]
    print(f"log_{key}_hits", len(hits))
    for ln in hits[-5:]:
        print(ln)

# probe get_floor via import in same env as bot would
import sys
sys.path.insert(0, "bot"); sys.path.insert(0, ".")
try:
    import lux_floor_rotate as lfr
    print("rotate_current", lfr.current_floor())
    print("rotate_list_head", lfr._rotation_list()[:10])
except Exception as e:
    print("rotate_probe_err", e)
try:
    import floor_tracker as ft
    if hasattr(ft, "get_floor"):
        print("get_floor()", ft.get_floor())
        print("wrapped", getattr(ft.get_floor, "_lux_floor_rotate", False))
except Exception as e:
    print("ft_probe", e)

db = Path("bot/bacbo.db") if Path("bot/bacbo.db").exists() else Path("bacbo.db")
con = sqlite3.connect(str(db))
print("floors_last_2h", list(con.execute(
    "select coalesce(source_floor,'NULL'), count(*) from consensus_signals "
    "where fired_at>=datetime('now','-2 hours') group by 1 order by 2 desc")))
print("last8", list(con.execute(
    "select id,fired_at,signal_kind,source_floor from consensus_signals order by id desc limit 8")))
print("--- last 15 bot ---")
for ln in text.splitlines()[-15:]:
    print(ln)
PY

echo
echo "VERDICT:"
echo "  - supervisor_count must be 1"
echo "  - log should show [LUXURY] floor-rotate ON start=JUN19 (or other peak)"
echo "  - NEW consensus after this boot should leave LIVE (JUN19/JUN20/...)"
echo "  - Telegram fallback cards will show new FLOOR once source_floor changes"
echo
echo "DONE. Paste ALL output."
