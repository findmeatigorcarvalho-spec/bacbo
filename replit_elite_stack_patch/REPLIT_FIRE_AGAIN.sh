#!/usr/bin/env bash
# Diagnose quiet stretch + switch floor-rotate to TAG-ONLY (engines stay LIVE,
# DB/cards get JUN19+) + restart single supervisor.
set -euo pipefail
cd /home/runner/workspace
PY=python3
SHA="${LUXURY_PATCH_SHA:-cursor/add-engine-gate-registry-d5ba}"
BASE="https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/${SHA}/replit_elite_stack_patch"
PEER="${TELEGRAM_TARGET_PEER:-6774605259}"

echo "========== [1/6] why quiet since last boot? (read-only) =========="
$PY <<'PY'
import re, sqlite3, subprocess
from pathlib import Path
from datetime import datetime, timezone

logp = Path("logs/bot_live.log")
lines = logp.read_text(errors="replace").splitlines() if logp.exists() else []
cut = 0
for i, ln in enumerate(lines):
    if "[BootFilter]" in ln or "floor-rotate early-load" in ln or "starting run_forever" in ln:
        cut = i
post = lines[cut:]
print("utc_now", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))
print("post_boot_lines", len(post), "cut_at", cut)
for pat, label in [
    (r"SIGNAL FIRED|SEQUENCE/FIRED", "fired"),
    (r"QUIET — no signal fired", "quiet"),
    (r"EdgePolicy.*BLOCK|FLOOR_BLOCKED|DENY", "block"),
    (r"EdgePolicy.*ALLOW", "allow"),
    (r"AccumHold.*CRASH|Traceback|NameError|AttributeError", "crash"),
    (r"get_floor_badge", "badge_mentions"),
    (r"BootGrace|BootFilter", "boot"),
    (r"GaleTrack|gale1|gale2", "gale"),
]:
    print(label, len(re.findall(pat, "\n".join(post), re.I)))
print("--- crash/error tail ---")
for ln in post:
    if re.search(r"CRASH|Traceback|NameError|AttributeError|ERROR.*bacbo|ERROR.*BacBo", ln):
        print(ln[:220])
print("--- last FIRED/QUIET/ALLOW anywhere (20) ---")
hits = [ln for ln in lines if re.search(r"FIRED|QUIET —|EdgePolicy", ln)]
for ln in hits[-20:]:
    print(ln[:220])
print("--- procs ---")
print(subprocess.getoutput("pgrep -af 'runtime_supervisor|bacbo_royal|fallback_' || echo NONE"))
db = Path("bot/bacbo.db") if Path("bot/bacbo.db").exists() else Path("bacbo.db")
con = sqlite3.connect(str(db))
print("last8", list(con.execute(
    "select id,fired_at,signal_kind,source_floor from consensus_signals order by id desc limit 8")))
print("mins_since_last", list(con.execute(
    "select cast((julianday('now')-julianday(fired_at))*24*60 as int) from consensus_signals order by id desc limit 1")))
PY

echo "========== [2/6] hard-stop =========="
pkill -9 -f 'bacbo_royal_complete.py' 2>/dev/null || true
pkill -9 -f 'runtime_supervisor.py' 2>/dev/null || true
pkill -9 -f 'fallback_signal_sender.py' 2>/dev/null || true
pkill -9 -f 'fallback_result_sender.py' 2>/dev/null || true
sleep 3

echo "========== [3/6] install TAG-ONLY rotator + fix database rebind =========="
curl -fsSL -H "Cache-Control: no-cache" -o bot/lux_floor_rotate.py "$BASE/bot/lux_floor_rotate.py"
curl -fsSL -H "Cache-Control: no-cache" -o bot/runtime_supervisor.py "$BASE/bot/runtime_supervisor.py"
$PY -m py_compile bot/lux_floor_rotate.py

$PY <<'PY'
import ast, re, time
from pathlib import Path

ROOT = Path("/home/runner/workspace")
BOT = ROOT / "bot"

# Ensure badge on floor_tracker
ft = BOT / "floor_tracker.py"
if ft.exists():
    src = ft.read_text(encoding="utf-8", errors="replace")
    if "def get_floor_badge" not in src:
        src += '''

# --- LUXURY_GET_FLOOR_BADGE (auto) ---
try:
    FLOOR_META
except NameError:
    FLOOR_META = {}

def get_floor_badge() -> str:
    try:
        from lux_floor_rotate import _get_floor_badge_impl
        return _get_floor_badge_impl()
    except Exception:
        try:
            fid = get_floor()
        except Exception:
            fid = "LIVE"
        return f"🏛️ **{fid}**"
# --- end LUXURY_GET_FLOOR_BADGE ---
'''
        ft.write_text(src, encoding="utf-8")
        print("ensured get_floor_badge")
    else:
        print("badge present")

# Rewrite database rebind to use lux_floor_rotate.tag_floor (tag-only)
dbp = BOT / "database.py"
if dbp.exists():
    src = dbp.read_text(encoding="utf-8", errors="replace")
    # strip old luxury rebind blocks
    src2 = re.sub(
        r"\n# --- LUXURY_GET_FLOOR_REBIND \(auto\) ---[\s\S]*?# --- end LUXURY_GET_FLOOR_REBIND ---\n?",
        "\n",
        src,
    )
    block = '''
# --- LUXURY_GET_FLOOR_REBIND (auto) ---
# Tag-only: source_floor column uses rotator; engine ContextVar stays via real get_floor.
try:
    import lux_floor_rotate as _lux_fr
    def get_floor(*_a, **_k):
        return _lux_fr.tag_floor()
    def get_floor_badge(*_a, **_k):
        return _lux_fr._get_floor_badge_impl()
except Exception as _lux_gf_exc:
    print("[LUXURY] database tag-floor rebind skipped:", _lux_gf_exc)
# --- end LUXURY_GET_FLOOR_REBIND ---
'''
    m = re.search(r"^(?:from floor_tracker import[^\n]*|import floor_tracker[^\n]*)\n", src2, re.M)
    if m:
        src2 = src2[: m.end()] + block + src2[m.end() :]
    else:
        src2 = "import floor_tracker\n" + block + src2
    Path(str(dbp) + f".bak_pre_tag_{int(time.time())}").write_text(src, encoding="utf-8")
    ast.parse(src2)
    dbp.write_text(src2, encoding="utf-8")
    print("database tag-floor rebind OK")
else:
    print("WARN no database.py")

# LATE+DEFER lux_floor_rotate (early inject kills bacbo ~60s after subscribe)
bacbo = ROOT / "bacbo_royal_complete.py"
bsrc = bacbo.read_text(encoding="utf-8", errors="replace")
bsrc2 = re.sub(
    r"\n# --- LUXURY_FLOOR_ROTATE \(auto\) ---[\s\S]*?# --- end LUXURY_FLOOR_ROTATE ---\n?",
    "\n",
    bsrc,
)
late = '''
# --- LUXURY_FLOOR_ROTATE (auto) ---
try:
    import os as _lux_os
    import sys as _lux_sys
    from pathlib import Path as _LuxP
    _lux_os.environ.setdefault("LUXURY_FLOOR_ROTATE_DEFER_APPLY", "1")
    _lux_os.environ.setdefault("LUXURY_FLOOR_ROTATE_APPLY_DELAY_SECS", "45")
    _lux_os.environ.setdefault("LUXURY_FLOOR_ROTATE_MODE", "tag")
    _lux_sys.path.insert(0, str(_LuxP("/home/runner/workspace/bot")))
    import lux_floor_rotate  # noqa: F401
    print("[LUXURY] floor-rotate LATE+DEFER OK mode=tag")
except Exception as _lux_fr_exc:
    print("[LUXURY] floor-rotate LATE+DEFER skipped:", _lux_fr_exc)
# --- end LUXURY_FLOOR_ROTATE ---
'''
m = re.search(r"^if __name__", bsrc2, re.M)
if m:
    out = bsrc2[: m.start()] + late + "\n" + bsrc2[m.start() :]
    print("bacbo LATE inject before __main__")
else:
    out = bsrc2 + "\n" + late
    print("bacbo LATE inject at EOF")
ast.parse(out)
bacbo.write_text(out, encoding="utf-8")
print("bacbo LATE+DEFER inject OK")

# smoke
import sys
sys.path.insert(0, str(BOT))
import importlib
import lux_floor_rotate
importlib.reload(lux_floor_rotate)
print("tag_floor", lux_floor_rotate.tag_floor())
print("mode", lux_floor_rotate._mode())
import floor_tracker
print("engine_get_floor", floor_tracker.get_floor())
print("badge", floor_tracker.get_floor_badge()[:70])
PY

echo "========== [4/6] force env TAG mode =========="
$PY <<PY
from pathlib import Path
import json, re
ROOT = Path("/home/runner/workspace")
allow = json.loads((ROOT/"bot/data/luxury_live_floors.json").read_text())
live = allow.get("live_floors") or allow.get("live_building_floors") or []
peer = "${PEER}"
(ROOT/"luxury_building.env").write_text(f"""export EDGE_POLICY_MODE=luxury
export EDGE_LUXURY_FLOOR_GATE=1
export FALLBACKS_ENABLED=1
export FALLBACK_SEND_BLOCKED=0
export LUXURY_NO_HOUR_BLOCKS=1
export LUXURY_FLOOR_ROTATE=1
export LUXURY_FLOOR_ROTATE_MODE=tag
export LUXURY_FLOOR_ROTATE_SECS=180
export BOT_TZ=America/Sao_Paulo
export TELEGRAM_TARGET_PEER={peer}
export LUXURY_LIVE_FLOORS={",".join(live)}
""")
envp = ROOT/".env"
lines=[]
if envp.exists():
    for ln in envp.read_text(errors="ignore").splitlines():
        if re.match(r"^\s*(export\s+)?(EDGE_POLICY_MODE|LUXURY_FLOOR_ROTATE|FALLBACKS_ENABLED|EDGE_LUXURY_FLOOR_GATE|FALLBACK_SEND_BLOCKED|LUXURY_NO_HOUR_BLOCKS)\s*=", ln):
            continue
        lines.append(ln)
lines += [
    "EDGE_POLICY_MODE=luxury",
    "EDGE_LUXURY_FLOOR_GATE=1",
    "FALLBACKS_ENABLED=1",
    "FALLBACK_SEND_BLOCKED=0",
    "LUXURY_NO_HOUR_BLOCKS=1",
    "LUXURY_FLOOR_ROTATE=1",
    "LUXURY_FLOOR_ROTATE_MODE=tag",
    "LUXURY_FLOOR_ROTATE_SECS=180",
]
envp.write_text("\n".join(lines).rstrip()+"\n")
print("env tag mode floors", len(live))
PY

echo "========== [5/6] restart single supervisor =========="
set -a
# shellcheck disable=SC1091
source ./luxury_building.env
set +a
export TELEGRAM_SESSION_STRING="$(tr -d '\n' < .telegram_session_string)"
export TELEGRAM_TARGET_PEER="$PEER"
export LUXURY_FLOOR_ROTATE_MODE=tag

nohup env EDGE_POLICY_MODE=luxury EDGE_LUXURY_FLOOR_GATE=1 FALLBACKS_ENABLED=1 \
  LUXURY_FLOOR_ROTATE=1 LUXURY_FLOOR_ROTATE_MODE=tag LUXURY_FLOOR_ROTATE_SECS=180 \
  LUXURY_NO_HOUR_BLOCKS=1 BOT_TZ=America/Sao_Paulo \
  TELEGRAM_SESSION_STRING="$TELEGRAM_SESSION_STRING" \
  TELEGRAM_TARGET_PEER="$PEER" \
  $PY -u bot/runtime_supervisor.py > /tmp/luxury_supervisor.log 2>&1 &
echo "supervisor pid=$!"
sleep 2
echo "supervisor_count=$(pgrep -fc runtime_supervisor.py || true)"

echo "========== [6/6] settle 70s + verdict =========="
sleep 35
pgrep -af 'runtime_supervisor|bacbo_royal|fallback_' || echo NONE
sleep 35

$PY <<'PY'
import re, sqlite3, subprocess
from pathlib import Path
log = Path("logs/bot_live.log").read_text(errors="replace") if Path("logs/bot_live.log").exists() else ""
cut=0
for i,ln in enumerate(log.splitlines()):
    if "[BootFilter]" in ln or "floor-rotate" in ln:
        cut=i
post=log.splitlines()[cut:]
print("mode_line", [ln for ln in post if "floor-rotate" in ln][-3:])
print("post_fired", len(re.findall(r"SIGNAL FIRED|SEQUENCE/FIRED", "\n".join(post))))
print("post_quiet", len(re.findall(r"QUIET —", "\n".join(post))))
print("post_crash", len(re.findall(r"AccumHold.*CRASH|get_floor_badge|AttributeError", "\n".join(post))))
print("supervisor_count", subprocess.getoutput("pgrep -fc runtime_supervisor.py"))
print("bacbo_count", subprocess.getoutput("pgrep -fc bacbo_royal_complete.py"))
db = Path("bot/bacbo.db") if Path("bot/bacbo.db").exists() else Path("bacbo.db")
con=sqlite3.connect(str(db))
print("last8", list(con.execute(
    "select id,fired_at,signal_kind,source_floor from consensus_signals order by id desc limit 8")))
print("--- last 15 ---")
for ln in log.splitlines()[-15:]:
    print(ln)
PY

echo
echo "VERDICT:"
echo "  - smoke: engine_get_floor should be LIVE (or room ContextVar), tag_floor=JUN19"
echo "  - mode=tag in boot line"
echo "  - wait for next FIRED; source_floor should be JUN19+ while engine stays healthy"
echo
echo "DONE. Paste ALL output."
