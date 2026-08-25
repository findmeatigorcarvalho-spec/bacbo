#!/usr/bin/env bash
# Fix CrashGuard "database is locked" after luxury boot.
# - stop all writers/readers
# - single bacbo.db + WAL + busy_timeout
# - oracle db path parents
# - inject lux_sqlite_harden into bacbo
# - refresh fallbacks + supervisor (RO reads, delayed start)
# - restart and verify no CrashGuard lock for ~90s
set -euo pipefail
cd /home/runner/workspace

SHA="${LUXURY_PATCH_SHA:-cursor/add-engine-gate-registry-d5ba}"
BASE="https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/${SHA}/replit_elite_stack_patch"
PY="${PYTHON:-python3}"

echo "========== [1/7] stop all bot procs =========="
pkill -9 -f 'bacbo_royal_complete.py' 2>/dev/null || true
pkill -9 -f 'runtime_supervisor.py' 2>/dev/null || true
pkill -9 -f 'fallback_signal_sender.py' 2>/dev/null || true
pkill -9 -f 'fallback_result_sender.py' 2>/dev/null || true
sleep 2
# leftover holders
for pat in bacbo_royal fallback_signal fallback_result runtime_supervisor; do
  pgrep -af "$pat" || true
done

echo "========== [2/7] download harden + fallbacks + supervisor =========="
mkdir -p bot/data logs
curl -fsSL -H "Cache-Control: no-cache" -o bot/lux_sqlite_harden.py "$BASE/bot/lux_sqlite_harden.py"
curl -fsSL -H "Cache-Control: no-cache" -o bot/fallback_signal_sender.py "$BASE/bot/fallback_signal_sender.py"
curl -fsSL -H "Cache-Control: no-cache" -o bot/fallback_result_sender.py "$BASE/bot/fallback_result_sender.py"
curl -fsSL -H "Cache-Control: no-cache" -o bot/runtime_supervisor.py "$BASE/bot/runtime_supervisor.py"
$PY -m py_compile bot/lux_sqlite_harden.py bot/fallback_signal_sender.py bot/fallback_result_sender.py bot/runtime_supervisor.py
echo "downloaded OK"

echo "========== [3/7] unify DB paths + enable WAL =========="
$PY <<'PY'
import os, sqlite3, time
from pathlib import Path

ROOT = Path("/home/runner/workspace")
bot_db = ROOT / "bot" / "bacbo.db"
root_db = ROOT / "bacbo.db"
data_db = ROOT / "bot" / "data" / "bacbo.db"

# Prefer the larger existing file as canonical
cands = [p for p in (bot_db, root_db, data_db) if p.exists() and not p.is_symlink()]
if not cands and bot_db.exists():
    cands = [bot_db.resolve()]
canonical = max(cands, key=lambda p: p.stat().st_size) if cands else bot_db
canonical.parent.mkdir(parents=True, exist_ok=True)
if not canonical.exists():
    # create empty shell so WAL pragma can run later after restore
    sqlite3.connect(str(canonical)).close()
print("canonical", canonical, "size", canonical.stat().st_size if canonical.exists() else 0)

def link_to(src: Path, dest: Path) -> None:
    if dest.resolve() == src.resolve():
        print("ok", dest)
        return
    if dest.exists() or dest.is_symlink():
        if dest.is_symlink() or dest.stat().st_size <= 4096:
            dest.unlink()
        elif dest.resolve() != src.resolve():
            # keep larger; if dest bigger, swap canonical later — here just warn
            if dest.stat().st_size > src.stat().st_size:
                print("WARN dest larger than canonical, leaving", dest)
                return
            bak = dest.with_suffix(dest.suffix + f".bak_pre_wal_{int(time.time())}")
            dest.rename(bak)
            print("backed up", dest, "->", bak)
    try:
        rel = os.path.relpath(src, dest.parent)
        dest.symlink_to(rel)
        print("symlinked", dest, "->", rel)
    except Exception as e:
        print("symlink failed", dest, e)

link_to(canonical, bot_db)
link_to(canonical, root_db)
data_db.parent.mkdir(parents=True, exist_ok=True)
link_to(canonical, data_db)

# Drop stale journals only when no procs hold DB (we killed them)
for p in list(ROOT.glob("*.session-journal")) + list((ROOT/"bot").glob("*.session-journal")):
    try:
        p.unlink()
        print("removed", p)
    except Exception as e:
        print("skip remove", p, e)

# Enable WAL + busy timeout on canonical
con = sqlite3.connect(str(canonical), timeout=60)
con.execute("PRAGMA busy_timeout=60000")
mode = con.execute("PRAGMA journal_mode=WAL").fetchone()[0]
con.execute("PRAGMA synchronous=NORMAL")
con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
con.commit()
con.close()
print("journal_mode", mode)

# Oracle paths — create parents + empty db so "unable to open database file" stops
for rel in [
    "bot/oracle.db",
    "bot/data/oracle.db",
    "bot/data/oracle_mind.db",
    "bot/oracle_mind.db",
    "oracle.db",
]:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        try:
            sqlite3.connect(str(path)).close()
            print("created", path)
        except Exception as e:
            print("oracle create fail", path, e)
PY

echo "========== [4/7] inject sqlite harden + keep state name force =========="
$PY <<'PY'
from pathlib import Path
import ast, re

p = Path("bacbo_royal_complete.py")
src = p.read_text(encoding="utf-8", errors="replace")

harden = '''
# --- LUXURY_SQLITE_HARDEN (auto) ---
try:
    import lux_sqlite_harden  # noqa: F401
    print("[LUXURY] sqlite harden applied (WAL/busy_timeout/min-timeout)")
except Exception as _lux_sql_exc:
    print("[LUXURY] sqlite harden skipped:", _lux_sql_exc)
# --- end LUXURY_SQLITE_HARDEN ---
'''

src = re.sub(
    r"\n# --- LUXURY_SQLITE_HARDEN \(auto\) ---.*?--- end LUXURY_SQLITE_HARDEN ---\n",
    "\n",
    src,
    flags=re.S,
)

# Insert after first BOOT print or near top after imports
lines = src.splitlines(True)
idx = 0
for i, ln in enumerate(lines):
    if "[BOOT] all imports OK" in ln or "[BOOT] stdlib imports OK" in ln:
        idx = i + 1
        break
if idx == 0:
    for i, ln in enumerate(lines):
        if ln.startswith("import ") or ln.startswith("from "):
            idx = i + 1
    idx = min(idx, 80)

lines.insert(idx, harden if harden.startswith("\n") else "\n" + harden)
src2 = "".join(lines)

# Ensure state name force still present before state.engine
if "LUXURY_STATE_NAME_FORCE" not in src2 or "state = _lux_state_mod" not in src2:
    force = (
        "# --- LUXURY_STATE_NAME_FORCE (auto) ---\n"
        "import state as _lux_state_mod\n"
        "state = _lux_state_mod  # bare name for state.engine / state.learner / ...\n"
        "# --- end LUXURY_STATE_NAME_FORCE ---\n"
    )
    src2 = re.sub(
        r"\n# --- LUXURY_STATE_NAME_FORCE \(auto\) ---.*?--- end LUXURY_STATE_NAME_FORCE ---\n",
        "\n",
        src2,
        flags=re.S,
    )
    src2 = re.sub(
        r"^(state\.engine\s*=)",
        force + r"\1",
        src2,
        count=1,
        flags=re.M,
    )
    print("re-inserted STATE_NAME_FORCE")

# Ensure SESSION_AND_BIND assigns state=
if "LUXURY_SESSION_AND_BIND" in src2:
    chunk = src2.split("LUXURY_SESSION_AND_BIND", 1)[1][:900]
    if "state = _lux_state_mod" not in chunk:
        src2 = src2.replace(
            'print("[LUXURY] proxy bind failed:", _lux_bind_exc)\n# --- end LUXURY_SESSION_AND_BIND ---',
            'print("[LUXURY] proxy bind failed:", _lux_bind_exc)\nstate = _lux_state_mod\n# --- end LUXURY_SESSION_AND_BIND ---',
        )
        print("added state= into SESSION_AND_BIND")

ast.parse(src2)
p.write_text(src2, encoding="utf-8")
print("bacbo patched", p.stat().st_size)
print("has_sqlite_harden", "LUXURY_SQLITE_HARDEN" in src2)
print("has_state_force", "LUXURY_STATE_NAME_FORCE" in src2 or "state = _lux_state_mod" in src2)
PY

echo "========== [5/7] env + restart supervisor =========="
set -a
source ./luxury_building.env 2>/dev/null || true
set +a
export TELEGRAM_SESSION_STRING="$(tr -d '\n' < .telegram_session_string)"
export TELEGRAM_TARGET_PEER="${TELEGRAM_TARGET_PEER:-6774605259}"
export FALLBACK_START_DELAY_SECS="${FALLBACK_START_DELAY_SECS:-45}"
export EDGE_POLICY_MODE=luxury
export EDGE_LUXURY_FLOOR_GATE=1
export FALLBACK_SEND_BLOCKED="${FALLBACK_SEND_BLOCKED:-0}"
export BOT_TZ=America/Sao_Paulo
export PYTHONPATH="/home/runner/workspace/bot:/home/runner/workspace:${PYTHONPATH:-}"

# mark log so we can measure post-fix CrashGuard only
echo "===== DB_LOCK_FIX marker $(date -u +%Y-%m-%dT%H:%M:%SZ) =====" >> logs/bot_live.log

nohup env EDGE_POLICY_MODE=luxury EDGE_LUXURY_FLOOR_GATE=1 FALLBACK_SEND_BLOCKED="$FALLBACK_SEND_BLOCKED" \
  FALLBACK_START_DELAY_SECS="$FALLBACK_START_DELAY_SECS" \
  BOT_TZ=America/Sao_Paulo \
  TELEGRAM_SESSION_STRING="$TELEGRAM_SESSION_STRING" \
  TELEGRAM_TARGET_PEER="$TELEGRAM_TARGET_PEER" \
  PYTHONPATH="$PYTHONPATH" \
  python3 -u bot/runtime_supervisor.py > /tmp/luxury_supervisor.log 2>&1 &
echo "supervisor pid=$!"

echo "========== [6/7] wait for run_forever + settle (90s) =========="
sleep 20
echo "----- 20s procs -----"
pgrep -af 'runtime_supervisor|bacbo_royal|fallback_signal|fallback_result' || true
grep -E 'sqlite harden|run_forever|NameError|database is locked|CrashGuard' logs/bot_live.log | tail -n 30 || true

sleep 40
echo "----- 60s procs -----"
pgrep -af 'runtime_supervisor|bacbo_royal|fallback_signal|fallback_result' || true

sleep 35
echo "========== [7/7] post-fix verdict =========="
$PY <<'PY'
from pathlib import Path
import re, subprocess

log = Path("logs/bot_live.log").read_text(errors="ignore")
# Only analyze after last marker
marker = "===== DB_LOCK_FIX marker"
idx = log.rfind(marker)
chunk = log[idx:] if idx >= 0 else log[-8000:]
locks = len(re.findall(r"database is locked", chunk))
crashes = len(re.findall(r"\[CrashGuard\] Bot crashed", chunk))
run_ok = "run_forever" in chunk or "BOT_ENABLED=true — starting run_forever()" in chunk
harden = "sqlite harden applied" in chunk
nameerr = "NameError: name 'state'" in chunk
print("post_fix_run_forever", run_ok)
print("post_fix_sqlite_harden", harden)
print("post_fix_state_NameError", nameerr)
print("post_fix_database_is_locked_count", locks)
print("post_fix_crashguard_bot_crashed_count", crashes)
print("--- last 35 bot lines ---")
print("\n".join(Path("logs/bot_live.log").read_text(errors="ignore").splitlines()[-35:]))
print("--- procs ---")
print(subprocess.getoutput("pgrep -af 'runtime_supervisor|bacbo_royal|fallback_signal|fallback_result' || echo NONE"))
print("--- journal ---")
import sqlite3
from pathlib import Path as P
db = P("bot/bacbo.db")
con = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=10)
print("journal_mode", con.execute("PRAGMA journal_mode").fetchone()[0])
con.close()
if locks == 0 and crashes == 0 and run_ok and not nameerr:
    print("VERDICT: OK — no post-fix DB lock CrashGuard")
else:
    print("VERDICT: STILL_BAD — paste ALL output")
PY

echo
echo "DONE. Paste ALL output."
