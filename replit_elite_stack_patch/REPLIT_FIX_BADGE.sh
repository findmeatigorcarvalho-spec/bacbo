#!/usr/bin/env bash
# Fix: floor_tracker missing get_floor_badge (AccumHold crash)
# + rebind database.get_floor so source_floor follows rotator (JUN19…)
set -euo pipefail
cd /home/runner/workspace
PY=python3
SHA="${LUXURY_PATCH_SHA:-cursor/add-engine-gate-registry-d5ba}"
BASE="https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/${SHA}/replit_elite_stack_patch"
PEER="${TELEGRAM_TARGET_PEER:-6774605259}"

echo "========== [1/5] hard-stop =========="
pkill -9 -f 'bacbo_royal_complete.py' 2>/dev/null || true
pkill -9 -f 'runtime_supervisor.py' 2>/dev/null || true
pkill -9 -f 'fallback_signal_sender.py' 2>/dev/null || true
pkill -9 -f 'fallback_result_sender.py' 2>/dev/null || true
sleep 3
pgrep -af 'runtime_supervisor|bacbo_royal|fallback_' || echo clean

echo "========== [2/5] download rotator =========="
mkdir -p bot/data logs
curl -fsSL -H "Cache-Control: no-cache" -o bot/lux_floor_rotate.py "$BASE/bot/lux_floor_rotate.py"
curl -fsSL -H "Cache-Control: no-cache" -o bot/runtime_supervisor.py "$BASE/bot/runtime_supervisor.py"
$PY -m py_compile bot/lux_floor_rotate.py

echo "========== [3/5] patch database + floor_tracker + early bacbo import =========="
$PY <<'PY'
import ast, re, time
from pathlib import Path

ROOT = Path("/home/runner/workspace")
BOT = ROOT / "bot"

# 1) Append get_floor_badge to floor_tracker if still missing (belt+suspenders)
ft = BOT / "floor_tracker.py"
if ft.exists():
    src = ft.read_text(encoding="utf-8", errors="replace")
    bak = Path(str(ft) + f".bak_pre_badge_{int(time.time())}")
    if "def get_floor_badge" not in src:
        bak.write_text(src, encoding="utf-8")
        append = '''

# --- LUXURY_GET_FLOOR_BADGE (auto) ---
try:
    FLOOR_META
except NameError:
    FLOOR_META = {}

def get_floor_badge() -> str:
    """Postcard tag for active floor — required by AccumHold / signal cards."""
    try:
        fid = get_floor()
    except Exception:
        fid = "LIVE"
    meta = FLOOR_META.get(fid, {}) if isinstance(FLOOR_META, dict) else {}
    label = meta.get("label", fid)
    peak_wr = meta.get("peak_wr")
    if peak_wr is not None:
        try:
            return f"🏛️ **{fid} — {label}** · Pico {float(peak_wr):.1f}%"
        except Exception:
            pass
    if str(fid).upper() == "LIVE":
        return "🏛️ **Motor Live** · configuração dinâmica"
    return f"🏛️ **{fid} — {label}**"
# --- end LUXURY_GET_FLOOR_BADGE ---
'''
        ft.write_text(src + append, encoding="utf-8")
        print("appended get_floor_badge to floor_tracker")
    else:
        print("floor_tracker already has get_floor_badge")
else:
    print("WARN no floor_tracker.py")

# 2) Patch database.py so get_floor always goes through floor_tracker module attr
p = BOT / "database.py"
if not p.exists():
    print("skip missing database.py")
else:
    src = p.read_text(encoding="utf-8", errors="replace")
    orig = src
    marker = "LUXURY_GET_FLOOR_REBIND"
    if marker in src:
        print("database.py already has get_floor rebind")
    else:
        block = f'''
# --- {marker} (auto) ---
try:
    import floor_tracker as _lux_ft_mod
    def get_floor(*_a, **_k):
        return _lux_ft_mod.get_floor()
    def get_floor_badge(*_a, **_k):
        fn = getattr(_lux_ft_mod, "get_floor_badge", None)
        if callable(fn):
            return fn()
        return f"🏛️ **{{_lux_ft_mod.get_floor()}}**"
except Exception as _lux_gf_exc:
    print("[LUXURY] database get_floor rebind skipped:", _lux_gf_exc)
# --- end {marker} ---
'''
        # Place after floor_tracker imports if present, else near top
        m = re.search(r"^(?:from floor_tracker import[^\n]*|import floor_tracker[^\n]*)\n", src, re.M)
        if m:
            src = src[: m.end()] + block + src[m.end() :]
        else:
            lines = src.splitlines(True)
            idx = 0
            for i, ln in enumerate(lines[:60]):
                if ln.startswith("import ") or ln.startswith("from ") or not ln.strip() or ln.strip().startswith("#") or ln.startswith("from __future__"):
                    idx = i + 1
                else:
                    break
            lines.insert(idx, "import floor_tracker\n" + block)
            src = "".join(lines)
        Path(str(p) + f".bak_pre_badge_{int(time.time())}").write_text(orig, encoding="utf-8")
        try:
            ast.parse(src)
        except SyntaxError as e:
            print("database patch syntax fail — skip", e)
        else:
            p.write_text(src, encoding="utf-8")
            print("patched database.py with get_floor rebind")

# 3) Move LUXURY_FLOOR_ROTATE import EARLY in bacbo (before heavy imports if possible)
bacbo = ROOT / "bacbo_royal_complete.py"
bsrc = bacbo.read_text(encoding="utf-8", errors="replace")
# strip old blocks
bsrc2 = re.sub(
    r"\n# --- LUXURY_FLOOR_ROTATE \(auto\) ---[\s\S]*?# --- end LUXURY_FLOOR_ROTATE ---\n?",
    "\n",
    bsrc,
)
early = '''
# --- LUXURY_FLOOR_ROTATE (auto) ---
try:
    import sys as _lux_sys
    from pathlib import Path as _LuxP
    _lux_sys.path.insert(0, str(_LuxP("/home/runner/workspace/bot")))
    import lux_floor_rotate  # noqa: F401
    print("[LUXURY] floor-rotate early-load OK")
except Exception as _lux_fr_exc:
    print("[LUXURY] floor-rotate early-load skipped:", _lux_fr_exc)
# --- end LUXURY_FLOOR_ROTATE ---
'''
# insert after first import cluster
lines = bsrc2.splitlines(True)
idx = 0
for i, ln in enumerate(lines[:100]):
    s = ln.strip()
    if not s or s.startswith("#") or s.startswith("from __future__") or s.startswith("import ") or s.startswith("from "):
        idx = i + 1
        continue
    break
lines.insert(idx, early + "\n")
bsrc2 = "".join(lines)
ast.parse(bsrc2)
bacbo.write_text(bsrc2, encoding="utf-8")
print("bacbo early floor-rotate inject at line", idx + 1)

# smoke: floor_tracker badge
import sys
sys.path.insert(0, str(BOT))
sys.path.insert(0, str(ROOT))
import importlib
import floor_tracker
importlib.reload(floor_tracker)
import lux_floor_rotate
importlib.reload(lux_floor_rotate)
print("smoke get_floor", floor_tracker.get_floor())
print("smoke badge", floor_tracker.get_floor_badge()[:80])
print("has_badge", hasattr(floor_tracker, "get_floor_badge"))
PY

echo "========== [4/5] env + single supervisor =========="
set -a
# shellcheck disable=SC1091
source ./luxury_building.env 2>/dev/null || true
set +a
export TELEGRAM_SESSION_STRING="$(tr -d '\n' < .telegram_session_string)"
export TELEGRAM_TARGET_PEER="$PEER"
export EDGE_POLICY_MODE=luxury
export EDGE_LUXURY_FLOOR_GATE=1
export FALLBACKS_ENABLED=1
export LUXURY_FLOOR_ROTATE=1
export LUXURY_FLOOR_ROTATE_SECS=180

nohup env EDGE_POLICY_MODE=luxury EDGE_LUXURY_FLOOR_GATE=1 FALLBACKS_ENABLED=1 \
  LUXURY_FLOOR_ROTATE=1 LUXURY_FLOOR_ROTATE_SECS=180 LUXURY_NO_HOUR_BLOCKS=1 \
  BOT_TZ=America/Sao_Paulo \
  TELEGRAM_SESSION_STRING="$TELEGRAM_SESSION_STRING" \
  TELEGRAM_TARGET_PEER="$PEER" \
  $PY -u bot/runtime_supervisor.py > /tmp/luxury_supervisor.log 2>&1 &
echo "supervisor pid=$!"
sleep 2
echo "supervisor_count=$(pgrep -fc runtime_supervisor.py || true)"

echo "========== [5/5] settle 55s + verdict =========="
sleep 30
pgrep -af 'runtime_supervisor|bacbo_royal|fallback_' || echo NONE
sleep 25

$PY <<'PY'
import sqlite3, subprocess, re
from pathlib import Path
log = Path("logs/bot_live.log").read_text(errors="replace") if Path("logs/bot_live.log").exists() else ""
cut = 0
for i, ln in enumerate(log.splitlines()):
    if "[BootFilter]" in ln or "floor-rotate" in ln:
        cut = i
post = log.splitlines()[cut:]
badge_err = [ln for ln in post if "get_floor_badge" in ln]
accum = [ln for ln in post if "AccumHold" in ln and ("CRASH" in ln or "ERROR" in ln)]
rotate = [ln for ln in post if "floor-rotate" in ln]
print("post_badge_errors", len(badge_err))
for ln in badge_err[-5:]:
    print(ln)
print("post_accum_crash", len(accum))
for ln in accum[-5:]:
    print(ln)
print("rotate_lines", len(rotate))
for ln in rotate[-6:]:
    print(ln)
print("supervisor_count", subprocess.getoutput("pgrep -fc runtime_supervisor.py"))
db = Path("bot/bacbo.db") if Path("bot/bacbo.db").exists() else Path("bacbo.db")
con = sqlite3.connect(str(db))
print("floors_since_boot_hint", list(con.execute(
    "select coalesce(source_floor,'NULL'), count(*) from consensus_signals "
    "where fired_at>=datetime('now','-30 minutes') group by 1 order by 2 desc")))
print("last8", list(con.execute(
    "select id,fired_at,signal_kind,source_floor from consensus_signals order by id desc limit 8")))
print("--- last 12 ---")
for ln in log.splitlines()[-12:]:
    print(ln)
PY

echo
echo "VERDICT: want post_badge_errors 0, rotate ON, then NEW fires with JUN19/JUN20 source_floor"
echo "DONE. Paste ALL output."
