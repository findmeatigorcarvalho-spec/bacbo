#!/usr/bin/env bash
# ONE paste: wire peak aliases, persist luxury mode, restart bot, upload all zips.
set -euo pipefail
cd /home/runner/workspace

echo "========== [1/6] force aliases + luxury allowlist =========="
python3 - <<'PY'
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path("/home/runner/workspace")
BOT = ROOT / "bot"
DATA = BOT / "data"
DATA.mkdir(parents=True, exist_ok=True)

ALIASES = {
    "JUN19": "JUN19_peak", "JUN20": "JUN20_peak", "JUN08": "JUN08_peak", "JUN10": "JUN10_peak",
    "JUN26": "JUN26", "JUN27": "JUN27_peak", "MAY19": "MAY19_peak", "MAY10": "MAY10_peak",
    "MAY11": "MAY11_peak", "MAY01": "MAY01_peak", "APR19": "APR19_golden", "APR20": "APR20_perfect",
    "APR30": "APR30_peak", "JUN12A": "JUN12_avalanche", "JUN12B": "JUN12_eliteguard",
    "ELITE_V2_PEAK": "ELITE_V2_PEAK", "ELITE_V2": "ELITE_V2", "ULTIMATE": "ULTIMATE",
    "MAR19": "MAR19", "MAR20": "MAR20", "MAR21": "MAR21",
}
LIVE = [
    "ELITE_V2_PEAK","ELITE_V2","APR20","APR26","APR27","APR29","JUN10","AITEST_ULTIMATE",
    "AITEST_APR20_MAX","LIVE","MAY01","JUN20","AITEST_LIVE","APR22","JUN19","APR20_MAX",
    "JUN26","MAY19","MAY10","JUN27","APR28","MAY11","AITEST_APR20","AITEST_MAR21","JUN08",
    "APR30","MAY04","APR19","ULTIMATE","MAR19","MAR21","MAR20",
]
BLOCKED = ["JUN12A", "JUN12B"]
PEAKS = ["JUN19","JUN20","JUN08","JUN10","JUN26","JUN27","MAY19","MAY10"]

seed_path = DATA / "historical_luxury_seed.json"
seed = {}
if seed_path.exists():
    try: seed = json.loads(seed_path.read_text())
    except Exception: seed = {}
seed["hard_block"] = BLOCKED
seed["gate_aliases"] = ALIASES
seed_path.write_text(json.dumps(seed, indent=2) + "\n")

lux_path = DATA / "luxury_building_stack.json"
live_floors = LIVE
if lux_path.exists():
    try:
        lux = json.loads(lux_path.read_text())
        live_floors = lux.get("live_building_floors") or LIVE
    except Exception:
        pass

allow = {
    "live_floors": live_floors,
    "blocked": BLOCKED,
    "peak_day_floors": PEAKS,
    "virtual_setups": ["SOLO_ELITE|BLUE","GOLDEN|BLUE","SEQUENCE|BLUE","PLATINUM|BLUE","SEQUENCE"],
    "gate_aliases": ALIASES,
}
(DATA / "luxury_live_floors.json").write_text(json.dumps(allow, indent=2) + "\n")

# Helper imported by floor_tracker / gates
(DATA / "gate_alias_resolve.py").write_text('''\
"""Resolve luxury floor name -> real _gates_*.py stem."""
from __future__ import annotations
import json
from pathlib import Path

_PATH = Path(__file__).resolve().parent / "luxury_live_floors.json"

def resolve_gate(floor: str) -> str:
    name = (floor or "LIVE").strip().upper()
    try:
        data = json.loads(_PATH.read_text(encoding="utf-8"))
    except Exception:
        data = {}
    blocked = {str(x).upper() for x in (data.get("blocked") or [])}
    if name in blocked:
        return name  # caller should refuse fire
    aliases = data.get("gate_aliases") or {}
    return str(aliases.get(name, name)).strip() or name

def live_floors():
    try:
        data = json.loads(_PATH.read_text(encoding="utf-8"))
        return [str(x).upper() for x in (data.get("live_floors") or [])]
    except Exception:
        return ["LIVE"]
''')

# Copy helper next to bot modules too
(BOT / "gate_alias_resolve.py").write_text((DATA / "gate_alias_resolve.py").read_text())

ok = miss = 0
print("live_floors", len(live_floors))
print("blocked", BLOCKED)
for k, v in sorted(ALIASES.items()):
    g = BOT / f"_gates_{v}.py"
    st = "OK" if g.exists() else "MISSING"
    ok += g.exists(); miss += (not g.exists())
    print(f"  {k} -> {v}  {st}")
print(f"alias_gates_ok={ok} missing={miss}")
PY

echo "========== [2/6] patch floor_tracker to use peak gate aliases =========="
python3 - <<'PY'
from pathlib import Path
ft = Path('/home/runner/workspace/bot/floor_tracker.py')
if not ft.exists():
    print('WARN: floor_tracker.py missing')
    raise SystemExit(0)
src = ft.read_text(encoding='utf-8', errors='replace')
marker = 'LUXURY_GATE_ALIAS_RESOLVE'
if marker in src:
    print('floor_tracker already has gate alias resolve')
else:
    append = f'''

# --- {marker} ---
try:
    from gate_alias_resolve import resolve_gate as _lux_resolve_gate, live_floors as _lux_live_floors
    _orig_get_floor = globals().get('get_floor')
    if callable(_orig_get_floor):
        def get_floor(*a, **k):
            f = _orig_get_floor(*a, **k)
            try:
                return _lux_resolve_gate(f)
            except Exception:
                return f
    # expand enabled sets if present
    _lux = set(_lux_live_floors())
    for _name in ('ENABLED_FLOORS', 'LIVE_FLOORS', 'ACTIVE_FLOORS', 'FLOOR_ALLOWLIST'):
        if _name in globals() and isinstance(globals()[_name], (set, list, tuple)):
            _cur = globals()[_name]
            if isinstance(_cur, set):
                globals()[_name] = set(_cur) | _lux
            else:
                globals()[_name] = list(dict.fromkeys(list(_cur) + list(_lux)))
except Exception as _lux_alias_exc:
    try:
        print('luxury gate alias patch skipped:', _lux_alias_exc)
    except Exception:
        pass
'''
    ft.write_text(src + append)
    print('patched floor_tracker.py with gate alias resolve')
PY

echo "========== [3/6] persist EDGE_POLICY_MODE=luxury =========="
cat > /home/runner/workspace/luxury_building.env <<'EOF'
export EDGE_POLICY_MODE=luxury
export EDGE_LUXURY_FLOOR_GATE=1
export FALLBACK_SEND_BLOCKED=0
EOF
# shell + common env files
grep -q 'EDGE_POLICY_MODE' /home/runner/workspace/.env 2>/dev/null || true
if [ -f /home/runner/workspace/.env ]; then
  sed -i '/^EDGE_POLICY_MODE=/d;/^EDGE_LUXURY_FLOOR_GATE=/d;/^FALLBACK_SEND_BLOCKED=/d' /home/runner/workspace/.env || true
  cat >> /home/runner/workspace/.env <<'EOF'
EDGE_POLICY_MODE=luxury
EDGE_LUXURY_FLOOR_GATE=1
FALLBACK_SEND_BLOCKED=0
EOF
  echo "updated .env"
else
  cat > /home/runner/workspace/.env <<'EOF'
EDGE_POLICY_MODE=luxury
EDGE_LUXURY_FLOOR_GATE=1
FALLBACK_SEND_BLOCKED=0
EOF
  echo "created .env"
fi
# ensure Replit always sources it on boot if main.sh / replit.nix style exists
if [ -f /home/runner/workspace/main.py ] || [ -f /home/runner/workspace/bot/bacbo_royal_complete.py ]; then
  WRAP=/home/runner/workspace/start_luxury.sh
  cat > "$WRAP" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
cd /home/runner/workspace
source ./luxury_building.env
export EDGE_POLICY_MODE=luxury EDGE_LUXURY_FLOOR_GATE=1 FALLBACK_SEND_BLOCKED=0
# prefer supervisor if present, else common entrypoints
if [ -f bot/runtime_supervisor.py ]; then
  exec python3 -u bot/runtime_supervisor.py
elif [ -f bot/bacbo_royal_complete.py ]; then
  exec python3 -u bot/bacbo_royal_complete.py
else
  exec python3 -u main.py
fi
EOF
  chmod +x "$WRAP"
  echo "wrote start_luxury.sh"
fi
source /home/runner/workspace/luxury_building.env
echo "MODE=$EDGE_POLICY_MODE"

echo "========== [4/6] restart bot processes =========="
# kill old bot/supervisor (best effort)
pkill -f 'runtime_supervisor.py' 2>/dev/null || true
pkill -f 'bacbo_royal_complete.py' 2>/dev/null || true
pkill -f 'fallback_signal_sender.py' 2>/dev/null || true
pkill -f 'fallback_result_sender.py' 2>/dev/null || true
sleep 1
# start supervisor in background if available
if [ -f bot/runtime_supervisor.py ]; then
  nohup env EDGE_POLICY_MODE=luxury EDGE_LUXURY_FLOOR_GATE=1 FALLBACK_SEND_BLOCKED=0 \
    python3 -u bot/runtime_supervisor.py > /tmp/luxury_supervisor.log 2>&1 &
  echo "started runtime_supervisor pid=$!"
  sleep 2
  tail -n 30 /tmp/luxury_supervisor.log || true
else
  echo "WARN: runtime_supervisor.py missing — use Replit Stop/Start Run button now"
fi
ps aux | grep -E 'runtime_supervisor|bacbo_royal|signal_handler' | grep -v grep || echo "(no bot procs visible yet — press Run if needed)"

echo "========== [5/6] upload zips (litterbox 72h) =========="
python3 - <<'PY'
import subprocess, json, time
from pathlib import Path
root = Path('/home/runner/workspace')
files = [
    'luxury_export_light.zip',
    'may_jul_export.zip',
    'luxury_full_pack.zip',
    'bacbo_db_only.zip',
]
out = {}
for name in files:
    p = root / name
    if not p.exists():
        print('MISSING', name)
        out[name] = None
        continue
    print(f'UPLOAD {name} size={p.stat().st_size}')
    # litterbox 72h — handles large files
    cmd = [
        'curl', '-sS', '-m', '1800',
        '-F', 'reqtype=fileupload',
        '-F', 'time=72h',
        '-F', f'fileToUpload=@{p}',
        'https://litterbox.catbox.moe/resources/internals/api.php',
    ]
    try:
        r = subprocess.check_output(cmd, text=True).strip()
    except Exception as e:
        r = f'ERROR:{e}'
    print(' ->', r)
    out[name] = r
    time.sleep(1)
(root / 'UPLOAD_LINKS.json').write_text(json.dumps(out, indent=2) + '\n')
print('WROTE UPLOAD_LINKS.json')
print('===== PASTE THESE LINKS TO CURSOR =====')
for k,v in out.items():
    print(f'{k}: {v}')
PY

echo "========== [6/6] final check =========="
python3 - <<'PY'
import json, os
from pathlib import Path
root=Path('/home/runner/workspace')
print('EDGE_POLICY_MODE', os.environ.get('EDGE_POLICY_MODE'))
live=json.loads((root/'bot/data/luxury_live_floors.json').read_text())
print('live', len(live.get('live_floors') or []), 'blocked', live.get('blocked'))
print('aliases', len(live.get('gate_aliases') or {}))
links=json.loads((root/'UPLOAD_LINKS.json').read_text()) if (root/'UPLOAD_LINKS.json').exists() else {}
print('UPLOAD_LINKS')
for k,v in links.items():
    print(' ', k, v)
PY

echo
echo "DONE. Copy the UPLOAD_LINKS block above and paste it into Cursor chat."
echo "If bot did not stay up: press Replit Stop then Run (or: bash start_luxury.sh)."
