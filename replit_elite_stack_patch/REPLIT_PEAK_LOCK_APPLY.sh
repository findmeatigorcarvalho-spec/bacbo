#!/usr/bin/env bash
# Peak-lock luxury towers on Replit.
# 1) Undo bad get_floor()->gate-stem remap (breaks EdgePolicy DENY_FLOOR)
# 2) Bind logical floors to peak _gates_*.py files
# 3) Persist luxury mode + restart supervisor
set -euo pipefail
cd /home/runner/workspace
PY="${PYTHON:-python3}"
export PYTHONPATH="/home/runner/workspace${PYTHONPATH:+:$PYTHONPATH}"

echo "========== [1/6] write gate aliases + peak_lock_config =========="
$PY <<'PY'
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path("/home/runner/workspace")
BOT = ROOT / "bot"
DATA = BOT / "data"
DATA.mkdir(parents=True, exist_ok=True)

ALIASES = {
    "LIVE": "ELITE_V2",
    "JUN19": "JUN19_peak",
    "JUN20": "JUN20_peak",
    "JUN08": "JUN08_peak",
    "JUN10": "JUN10_peak",
    "JUN26": "JUN26",
    "JUN27": "JUN27_peak",
    "JUN06": "JUN06_peak",
    "MAY19": "MAY19_peak",
    "MAY10": "MAY10_peak",
    "MAY11": "MAY11_peak",
    "MAY01": "MAY01_peak",
    "MAY20": "MAY20_peak",
    "MAY21": "MAY21_peak",
    "MAY22": "MAY22_peak",
    "MAY23": "MAY23_peak",
    "MAY24": "MAY24_peak",
    "MAY25": "MAY25_peak",
    "MAY26": "MAY26_peak",
    "MAY27": "MAY27_peak",
    "APR19": "APR19_golden",
    "APR20": "APR20_perfect",
    "APR20_MAX": "APR20_perfect",
    "APR22": "APR22",
    "APR26": "APR27",
    "APR27": "APR27",
    "APR28": "APR28_complex",
    "APR29": "APR29",
    "APR30": "APR30_peak",
    "JUN12A": "JUN12_avalanche",
    "JUN12B": "JUN12_eliteguard",
    "ELITE_V2_PEAK": "ELITE_V2_PEAK",
    "ELITE_V2": "ELITE_V2",
    "ULTIMATE": "ULTIMATE",
    "MAR19": "MAR19",
    "MAR20": "MAR20",
    "MAR21": "MAR21",
    "MAY04": "MAY04",
    "AITEST_ULTIMATE": "ULTIMATE",
    "AITEST_APR20_MAX": "APR20_perfect",
    "AITEST_LIVE": "ELITE_V2",
    "AITEST_APR20": "APR20_perfect",
    "AITEST_MAR21": "MAR21",
}
LIVE = [
    "ELITE_V2_PEAK", "ELITE_V2", "APR20", "APR26", "APR27", "APR29", "JUN10",
    "AITEST_ULTIMATE", "AITEST_APR20_MAX", "LIVE", "MAY01", "JUN20", "AITEST_LIVE",
    "APR22", "JUN19", "APR20_MAX", "JUN26", "MAY19", "MAY10", "JUN27", "APR28",
    "MAY11", "AITEST_APR20", "AITEST_MAR21", "JUN08", "APR30", "MAY04", "APR19",
    "ULTIMATE", "MAR19", "MAR21", "MAR20",
]
BLOCKED = ["JUN12A", "JUN12B"]
PEAKS = ["JUN19", "JUN20", "JUN08", "JUN10", "JUN26", "JUN27", "MAY19", "MAY10"]

# merge prior live list if luxury stack already installed
lux_path = DATA / "luxury_building_stack.json"
live_floors = list(LIVE)
if lux_path.exists():
    try:
        lux = json.loads(lux_path.read_text())
        live_floors = lux.get("live_building_floors") or live_floors
    except Exception:
        pass

# merge prior aliases
prior = {}
allow_path = DATA / "luxury_live_floors.json"
if allow_path.exists():
    try:
        prior = json.loads(allow_path.read_text())
        old = prior.get("gate_aliases") or {}
        if isinstance(old, dict):
            merged = dict(old)
            merged.update(ALIASES)
            ALIASES = {str(k).upper(): str(v) for k, v in merged.items()}
        if prior.get("live_floors"):
            live_floors = prior["live_floors"]
    except Exception:
        pass

allow = {
    "live_floors": live_floors,
    "blocked": BLOCKED,
    "peak_day_floors": PEAKS,
    "virtual_setups": prior.get("virtual_setups")
    or ["SOLO_ELITE|BLUE", "GOLDEN|BLUE", "SEQUENCE|BLUE", "PLATINUM|BLUE", "SEQUENCE"],
    "gate_aliases": ALIASES,
    "peak_lock": True,
}
allow_path.write_text(json.dumps(allow, indent=2) + "\n")

peak_cfg = {
    "mode": "luxury_peak_lock",
    "blocked_floors": BLOCKED,
    "towers": {k: {"gate": v} for k, v in sorted(ALIASES.items()) if k not in BLOCKED},
}
(DATA / "peak_lock_config.json").write_text(json.dumps(peak_cfg, indent=2) + "\n")
(ROOT / "peak_lock_config.json").write_text(json.dumps(peak_cfg, indent=2) + "\n")

helper = '''\
"""Resolve luxury floor name -> real _gates_*.py stem.

Logical floor names stay for EdgePolicy. Only gate file load uses aliases.
"""
from __future__ import annotations
import json
from pathlib import Path

_PATH = Path(__file__).resolve().parent / "data" / "luxury_live_floors.json"
if not _PATH.exists():
    _PATH = Path(__file__).resolve().parent / "luxury_live_floors.json"

def resolve_gate(floor: str) -> str:
    name = (floor or "LIVE").strip().upper()
    try:
        data = json.loads(_PATH.read_text(encoding="utf-8"))
    except Exception:
        data = {}
    blocked = {str(x).upper() for x in (data.get("blocked") or [])}
    if name in blocked:
        return name
    aliases = data.get("gate_aliases") or {}
    return str(aliases.get(name, name)).strip() or name

resolve_gate_stem = resolve_gate

def live_floors():
    try:
        data = json.loads(_PATH.read_text(encoding="utf-8"))
        return [str(x).upper() for x in (data.get("live_floors") or [])]
    except Exception:
        return ["LIVE"]
'''
(BOT / "gate_alias_resolve.py").write_text(helper)
(DATA / "gate_alias_resolve.py").write_text(helper)

print("live_floors", len(live_floors))
print("blocked", BLOCKED)
print("aliases", len(ALIASES))
PY

echo "========== [2/6] undo bad floor_tracker get_floor remap =========="
$PY <<'PY'
from pathlib import Path
import re

ft = Path("/home/runner/workspace/bot/floor_tracker.py")
if not ft.exists():
    print("WARN: floor_tracker.py missing — skip")
    raise SystemExit(0)

src = ft.read_text(encoding="utf-8", errors="replace")
orig = src
# Only strip the auto-appended DO_EVERYTHING block (safe: marker to EOF)
src = re.sub(
    r"\n# --- LUXURY_GATE_ALIAS_RESOLVE ---[\s\S]*\Z",
    "\n",
    src,
)
src = re.sub(
    r"\n# --- (?:peak|luxury) gate alias resolve[^\n]*---[\s\S]*\Z",
    "\n",
    src,
)

if src != orig:
    bak = ft.with_suffix(".py.bak_pre_peak_lock")
    if not bak.exists():
        bak.write_text(orig, encoding="utf-8")
    ft.write_text(src, encoding="utf-8")
    print("removed get_floor->gate-stem remap from floor_tracker.py")
    print("backup:", bak)
else:
    print("floor_tracker already clean (no bad remap block)")

txt = ft.read_text(encoding="utf-8", errors="replace")
if "LUXURY_GATE_ALIAS_RESOLVE" in txt:
    print("WARN: marker still present — manual check needed")
else:
    print("floor_tracker marker clear OK")
PY

echo "========== [3/6] peak-lock: bind logical _gates_X.py -> peak file =========="
$PY <<'PY'
from __future__ import annotations
import json
import shutil
from pathlib import Path

BOT = Path("/home/runner/workspace/bot")
DATA = BOT / "data"
allow = json.loads((DATA / "luxury_live_floors.json").read_text())
aliases = {str(k).upper(): str(v) for k, v in (allow.get("gate_aliases") or {}).items()}
blocked = {str(x).upper() for x in (allow.get("blocked") or [])}

ok = miss = same = wrapped = 0
for logical, stem in sorted(aliases.items()):
    if logical in blocked:
        print(f"  SKIP blocked {logical}")
        continue
    peak = BOT / f"_gates_{stem}.py"
    logical_path = BOT / f"_gates_{logical}.py"
    if not peak.exists():
        print(f"  MISSING peak {logical} -> {stem}  ({peak.name})")
        miss += 1
        continue
    ok += 1
    if logical == stem:
        print(f"  {logical} -> {stem}  SAME")
        same += 1
        continue
    # Backup logical gate once, then install thin loader that execs peak
    if logical_path.exists() and not logical_path.with_suffix(".py.bak_pre_peak").exists():
        shutil.copy2(logical_path, logical_path.with_suffix(".py.bak_pre_peak"))
    loader = f'''# AUTO peak-lock loader — logical floor {logical} -> gate {stem}
# EdgePolicy still sees floor={logical}. Do not edit by hand.
from pathlib import Path
import runpy

_PEAK = Path(__file__).with_name("_gates_{stem}.py")
if not _PEAK.exists():
    raise ImportError(f"peak gate missing: {{_PEAK}}")
_g = runpy.run_path(str(_PEAK), run_name=__name__)
globals().update({{k: v for k, v in _g.items() if not k.startswith("__")}})
'''
    logical_path.write_text(loader, encoding="utf-8")
    wrapped += 1
    print(f"  {logical} -> {stem}  LOCKED via loader")

print(f"peak_ok={ok} missing={miss} same={same} locked_loaders={wrapped}")
PY

echo "========== [4/6] patch gate loaders to resolve aliases (belt+suspenders) =========="
$PY <<'PY'
from pathlib import Path
import re

marker = "PEAK_LOCK_GATE_RESOLVE"
inject = '''
# --- PEAK_LOCK_GATE_RESOLVE ---
try:
    from gate_alias_resolve import resolve_gate as _peak_resolve_gate
except Exception:
    try:
        from bot.gate_alias_resolve import resolve_gate as _peak_resolve_gate
    except Exception:
        def _peak_resolve_gate(x):
            return x
'''

patched = []
for p in Path("/home/runner/workspace/bot").glob("*.py"):
    if p.name.startswith("_gates_"):
        continue
    try:
        t = p.read_text(encoding="utf-8", errors="replace")
    except Exception:
        continue
    if "_gates_" not in t:
        continue
    if marker in t:
        continue
    # wrap f"_gates_{floor}.py" / "_gates_%s" patterns
    newt = t
    newt2 = re.sub(
        r'f(["\'])_gates_\{([^}]+)\}\.py\1',
        r'f"_gates_{_peak_resolve_gate(\2)}.py"',
        newt,
    )
    newt2 = re.sub(
        r'(["\'])_gates_%s\.py\1\s*%\s*\(([^)]+)\)',
        r'("_gates_%s.py" % (_peak_resolve_gate(\2),))',
        newt2,
    )
    newt2 = re.sub(
        r'(["\'])_gates_\{\}\.py\1\.format\(([^)]+)\)',
        r'("_gates_{}.py".format(_peak_resolve_gate(\2)))',
        newt2,
    )
    if newt2 == t:
        continue
    # prepend inject near top
    if newt2.lstrip().startswith("from __future__"):
        lines = newt2.splitlines(True)
        # after first future import line
        out = [lines[0]]
        i = 1
        while i < len(lines) and (lines[i].startswith("from __future__") or lines[i].strip() == ""):
            out.append(lines[i]); i += 1
        out.append(inject + "\n")
        out.extend(lines[i:])
        newt2 = "".join(out)
    else:
        newt2 = inject + "\n" + newt2
    bak = p.with_suffix(p.suffix + ".bak_pre_peak_lock")
    if not bak.exists():
        bak.write_text(t, encoding="utf-8")
    p.write_text(newt2, encoding="utf-8")
    patched.append(p.name)

print("patched_gate_loaders", patched or ["(none — loaders already via _gates_ logical wrappers)"])
PY

echo "========== [5/6] persist luxury env + restart =========="
cat > /home/runner/workspace/luxury_building.env <<'EOF'
export EDGE_POLICY_MODE=luxury
export EDGE_LUXURY_FLOOR_GATE=1
export FALLBACK_SEND_BLOCKED=0
EOF
if [ -f /home/runner/workspace/.env ]; then
  sed -i '/^EDGE_POLICY_MODE=/d;/^EDGE_LUXURY_FLOOR_GATE=/d;/^FALLBACK_SEND_BLOCKED=/d' /home/runner/workspace/.env || true
fi
cat >> /home/runner/workspace/.env <<'EOF'
EDGE_POLICY_MODE=luxury
EDGE_LUXURY_FLOOR_GATE=1
FALLBACK_SEND_BLOCKED=0
EOF
cat > /home/runner/workspace/start_luxury.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
cd /home/runner/workspace
source ./luxury_building.env
export EDGE_POLICY_MODE=luxury EDGE_LUXURY_FLOOR_GATE=1 FALLBACK_SEND_BLOCKED=0
if [ -f bot/runtime_supervisor.py ]; then
  exec python3 -u bot/runtime_supervisor.py
elif [ -f bot/bacbo_royal_complete.py ]; then
  exec python3 -u bot/bacbo_royal_complete.py
else
  exec python3 -u main.py
fi
EOF
chmod +x /home/runner/workspace/start_luxury.sh
source /home/runner/workspace/luxury_building.env
echo "MODE=$EDGE_POLICY_MODE"

pkill -f 'runtime_supervisor.py' 2>/dev/null || true
pkill -f 'bacbo_royal_complete.py' 2>/dev/null || true
pkill -f 'fallback_signal_sender.py' 2>/dev/null || true
pkill -f 'fallback_result_sender.py' 2>/dev/null || true
sleep 1
if [ -f bot/runtime_supervisor.py ]; then
  nohup env EDGE_POLICY_MODE=luxury EDGE_LUXURY_FLOOR_GATE=1 FALLBACK_SEND_BLOCKED=0 \
    python3 -u bot/runtime_supervisor.py > /tmp/luxury_supervisor.log 2>&1 &
  echo "started runtime_supervisor pid=$!"
  sleep 2
  tail -n 40 /tmp/luxury_supervisor.log || true
else
  echo "WARN: runtime_supervisor.py missing — press Replit Stop/Run"
fi
ps aux | grep -E 'runtime_supervisor|bacbo_royal|fallback_' | grep -v grep || echo "(no bot procs yet)"

echo "========== [6/6] final verify =========="
$PY <<'PY'
import json, os, sys
from pathlib import Path

root = Path("/home/runner/workspace")
sys.path.insert(0, str(root))
sys.path.insert(0, str(root / "bot"))
try:
    from gate_alias_resolve import resolve_gate
except Exception:
    from bot.gate_alias_resolve import resolve_gate

allow = json.loads((root / "bot/data/luxury_live_floors.json").read_text())
print("EDGE_POLICY_MODE", os.environ.get("EDGE_POLICY_MODE"))
print("live", len(allow.get("live_floors") or []), "blocked", allow.get("blocked"))
print("aliases", len(allow.get("gate_aliases") or {}), "peak_lock", allow.get("peak_lock"))
# critical: logical != stem for JUN19, but EdgePolicy floor stays JUN19
assert resolve_gate("JUN19") == "JUN19_peak"
assert resolve_gate("LIVE") == "ELITE_V2"
assert "JUN19" in [str(x).upper() for x in allow["live_floors"]]
assert "JUN19_peak" not in [str(x).upper() for x in allow["live_floors"]]
# loaders exist
for logical, stem in [("JUN19", "JUN19_peak"), ("JUN20", "JUN20_peak"), ("LIVE", "ELITE_V2")]:
    lp = root / "bot" / f"_gates_{logical}.py"
    pp = root / "bot" / f"_gates_{stem}.py"
    print(f"  loader {logical}: exists={lp.exists()} peak={pp.exists()}")
# fill missing MAY23_peak from nearest May peak if absent
may23 = root / "bot" / "_gates_MAY23_peak.py"
if not may23.exists():
    for cand in ("MAY22_peak", "MAY24_peak", "MAY19_peak", "MAY10_peak"):
        src = root / "bot" / f"_gates_{cand}.py"
        if src.exists():
            may23.write_text(
                f'# AUTO stub peak — cloned from {cand} until real MAY23_peak exists\n'
                f'from pathlib import Path\nimport runpy\n'
                f'_PEAK = Path(__file__).with_name("_gates_{cand}.py")\n'
                f'_g = runpy.run_path(str(_PEAK), run_name=__name__)\n'
                f'globals().update({{k: v for k, v in _g.items() if not k.startswith("__")}})\n',
                encoding="utf-8",
            )
            # also lock logical MAY23 loader if alias present
            logical = root / "bot" / "_gates_MAY23.py"
            logical.write_text(
                '# AUTO peak-lock loader — logical floor MAY23 -> gate MAY23_peak\n'
                'from pathlib import Path\nimport runpy\n'
                '_PEAK = Path(__file__).with_name("_gates_MAY23_peak.py")\n'
                'if not _PEAK.exists():\n'
                '    raise ImportError(f"peak gate missing: {_PEAK}")\n'
                '_g = runpy.run_path(str(_PEAK), run_name=__name__)\n'
                'globals().update({k: v for k, v in _g.items() if not k.startswith("__")})\n',
                encoding="utf-8",
            )
            print(f"filled MISSING MAY23_peak from {cand}")
            break
    else:
        print("WARN: could not fill MAY23_peak")
else:
    print("MAY23_peak present")
print("peak_lock_smoke_ok")
PY

echo
echo "DONE peak-lock. Logical floors stay for EdgePolicy; peak gates are bound."
echo "If bot did not stay up: Replit Stop then Run, or: bash start_luxury.sh"
