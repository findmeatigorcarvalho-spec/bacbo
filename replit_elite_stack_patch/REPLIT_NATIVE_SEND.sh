#!/usr/bin/env bash
# Fix native send(): name 'config' is not defined
# Keeps peak-pure (hour blocks OFF) + fallbacks ON as safety net.
set -euo pipefail
cd /home/runner/workspace
PY=python3
SHA="${LUXURY_PATCH_SHA:-cursor/add-engine-gate-registry-d5ba}"
BASE="https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/${SHA}/replit_elite_stack_patch"
PEER="${TELEGRAM_TARGET_PEER:-6774605259}"

echo "========== [1/5] stop =========="
pkill -9 -f 'bacbo_royal_complete.py' 2>/dev/null || true
pkill -9 -f 'runtime_supervisor.py' 2>/dev/null || true
pkill -9 -f 'fallback_signal_sender.py' 2>/dev/null || true
pkill -9 -f 'fallback_result_sender.py' 2>/dev/null || true
sleep 2

echo "========== [2/5] refresh fallbacks + supervisor =========="
mkdir -p bot/data logs
curl -fsSL -H "Cache-Control: no-cache" -o bot/runtime_supervisor.py "$BASE/bot/runtime_supervisor.py"
curl -fsSL -H "Cache-Control: no-cache" -o bot/fallback_signal_sender.py "$BASE/bot/fallback_signal_sender.py"
curl -fsSL -H "Cache-Control: no-cache" -o bot/fallback_result_sender.py "$BASE/bot/fallback_result_sender.py"
curl -fsSL -H "Cache-Control: no-cache" -o bot/lux_no_hour_blocks.py "$BASE/bot/lux_no_hour_blocks.py"
curl -fsSL -H "Cache-Control: no-cache" -o bot/lux_sqlite_harden.py "$BASE/bot/lux_sqlite_harden.py"
$PY -m py_compile bot/runtime_supervisor.py bot/fallback_signal_sender.py bot/fallback_result_sender.py bot/lux_no_hour_blocks.py

echo "========== [3/5] insert module-level import config (no bak wipe) =========="
$PY <<'PY'
import ast, re
from pathlib import Path

p = Path("bacbo_royal_complete.py")
src = p.read_text(encoding="utf-8", errors="replace")

# Strip prior luxury config inserts so we don't duplicate
src = re.sub(
    r"^import config  # LUXURY:[^\n]*\n",
    "",
    src,
    flags=re.M,
)
src = re.sub(r"^import config  # LUXURY auto\n", "", src, flags=re.M)

has = bool(
    re.search(r"^import config\b", src, re.M)
    or re.search(r"^from config import\b", src, re.M)
)
print("has_module_level_config_import", has)

if not has:
    lines = src.splitlines(True)
    insert_at = 0
    i = 0
    # skip module docstring
    if lines and lines[0].lstrip().startswith(('"""', "'''")):
        quote = '"""' if '"""' in lines[0] else "'''"
        if lines[0].count(quote) >= 2 and len(lines[0].strip()) > 3:
            insert_at = 1
            i = 1
        else:
            j = 1
            while j < len(lines) and quote not in lines[j]:
                j += 1
            insert_at = min(j + 1, len(lines))
            i = insert_at
    for k in range(i, min(len(lines), 150)):
        s = lines[k].strip()
        if not s or s.startswith("#") or s.startswith("from __future__") or s.startswith("import ") or s.startswith("from "):
            insert_at = k + 1
            continue
        break
    lines.insert(insert_at, "import config  # LUXURY: module-level for send()\n")
    src = "".join(lines)
    print("inserted import config at line", insert_at + 1)
else:
    print("no insert needed")

# Ensure peak-pure injector still present
if "LUXURY_NO_HOUR_BLOCKS" not in src:
    block = '''
# --- LUXURY_NO_HOUR_BLOCKS (auto) ---
try:
    import lux_no_hour_blocks  # noqa: F401
    print("[LUXURY] peak-pure: hour blocks OFF (peak floors kept)")
except Exception as _lux_nhb_exc:
    print("[LUXURY] no_hour_blocks skipped:", _lux_nhb_exc)
# --- end LUXURY_NO_HOUR_BLOCKS ---
'''
    # inject near other LUXURY blocks or before run_forever
    m = re.search(r"# --- LUXURY_SQLITE_HARDEN", src)
    if m:
        src = src[: m.start()] + block + "\n" + src[m.start() :]
        print("re-injected LUXURY_NO_HOUR_BLOCKS before sqlite harden")
    else:
        m2 = re.search(r"^if __name__", src, re.M)
        if m2:
            src = src[: m2.start()] + block + "\n" + src[m2.start() :]
            print("re-injected LUXURY_NO_HOUR_BLOCKS before __main__")
        else:
            src = src + "\n" + block
            print("appended LUXURY_NO_HOUR_BLOCKS")

ast.parse(src)
p.write_text(src, encoding="utf-8")
print("bacbo syntax OK bytes", len(src))
for i, ln in enumerate(src.splitlines()[:50], 1):
    if "import config" in ln or "config" in ln and ("import" in ln or "from" in ln):
        print(f"  L{i}: {ln[:110]}")
PY

echo "========== [4/5] env + restart =========="
cat > luxury_building.env <<EOF
export EDGE_POLICY_MODE=luxury
export EDGE_LUXURY_FLOOR_GATE=1
export FALLBACKS_ENABLED=1
export FALLBACK_SEND_BLOCKED=0
export LUXURY_NO_HOUR_BLOCKS=1
export BOT_TZ=America/Sao_Paulo
export TELEGRAM_TARGET_PEER=${PEER}
EOF
set -a
# shellcheck disable=SC1091
source ./luxury_building.env
set +a
export TELEGRAM_SESSION_STRING="$(tr -d '\n' < .telegram_session_string)"
export TELEGRAM_TARGET_PEER="$PEER"
export FALLBACKS_ENABLED=1
export LUXURY_NO_HOUR_BLOCKS=1

nohup env EDGE_POLICY_MODE=luxury EDGE_LUXURY_FLOOR_GATE=1 FALLBACKS_ENABLED=1 \
  FALLBACK_SEND_BLOCKED=0 LUXURY_NO_HOUR_BLOCKS=1 BOT_TZ=America/Sao_Paulo \
  TELEGRAM_SESSION_STRING="$TELEGRAM_SESSION_STRING" \
  TELEGRAM_TARGET_PEER="$PEER" \
  $PY -u bot/runtime_supervisor.py > /tmp/luxury_supervisor.log 2>&1 &
echo "supervisor pid=$!"

echo "========== [5/5] settle 55s + verdict =========="
sleep 25
echo "----- 25s procs -----"
pgrep -af 'runtime_supervisor|bacbo_royal|fallback_' || echo NONE
sleep 30
echo "----- 55s procs -----"
pgrep -af 'runtime_supervisor|bacbo_royal|fallback_' || echo NONE

echo "--- config import check ---"
$PY <<'PY'
import re
from pathlib import Path
src = Path("bacbo_royal_complete.py").read_text(encoding="utf-8", errors="replace")
m = re.search(r"^(import config|from config import)\b.*$", src, re.M)
print("config_line", m.group(0) if m else "MISSING")
print("no_hour_blocks_block", "LUXURY_NO_HOUR_BLOCKS" in src)
PY

echo "--- send/config errors (post-boot only) ---"
$PY <<'PY'
from pathlib import Path
from datetime import datetime, timezone
log = Path("logs/bot_live.log")
if not log.exists():
    print("no bot_live.log")
    raise SystemExit
lines = log.read_text(errors="replace").splitlines()
# Prefer lines after last BootFilter / BootGrace
cut = 0
for i, ln in enumerate(lines):
    if "[BootFilter]" in ln or "[BootGrace]" in ln or "starting run_forever" in ln:
        cut = i
post = lines[cut:]
cfg_err = [ln for ln in post if "name 'config' is not defined" in ln or "send() failed" in ln]
print("post_boot_send_config_errors", len(cfg_err))
for ln in cfg_err[-8:]:
    print(ln)
name_state = [ln for ln in post if "NameError: name 'state'" in ln]
print("post_boot_state_NameError", len(name_state))
print("run_forever", any("run_forever" in ln for ln in post[-80:]))
print("--- last 18 ---")
for ln in lines[-18:]:
    print(ln)
PY

echo "--- consensus / floors ---"
$PY <<'PY'
import sqlite3
from pathlib import Path
db = Path("bot/bacbo.db") if Path("bot/bacbo.db").exists() else Path("bacbo.db")
con = sqlite3.connect(str(db))
rows = list(con.execute(
    "select id, fired_at, signal_kind, color, source_floor, total_score, outcome "
    "from consensus_signals order by id desc limit 10"
))
for r in rows:
    print(r)
floors = {}
for r in con.execute(
    "select coalesce(source_floor,'NULL'), count(*) from consensus_signals "
    "where fired_at >= datetime('now','-2 hours') group by 1"
):
    floors[r[0]] = r[1]
print("floors_last_2h", floors)
PY

echo "--- fallback tails ---"
tail -n 8 logs/fallback_sender.log 2>/dev/null || true
tail -n 6 logs/fallback_result_sender.log 2>/dev/null || true

echo
echo "VERDICT: native send needs ZERO 'name config is not defined' after boot."
echo "If clean: watch Telegram — peak templates may replace fallback cards."
echo "Fallbacks stay ON as backup until native cards look right."
echo
echo "DONE. Paste ALL output."
