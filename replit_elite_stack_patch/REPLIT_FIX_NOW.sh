#!/usr/bin/env bash
# ONE command: repair broken bacbo + restart. Safe to re-run.
set -euo pipefail
cd /home/runner/workspace

SHA="${LUXURY_PATCH_SHA:-cursor/add-engine-gate-registry-d5ba}"
BASE="https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/${SHA}/replit_elite_stack_patch"
PY=python3

echo "========== stop =========="
pkill -9 -f 'bacbo_royal_complete.py' 2>/dev/null || true
pkill -9 -f 'runtime_supervisor.py' 2>/dev/null || true
pkill -9 -f 'fallback_signal_sender.py' 2>/dev/null || true
pkill -9 -f 'fallback_result_sender.py' 2>/dev/null || true
sleep 2

echo "========== download =========="
mkdir -p bot/data logs
curl -fsSL -H "Cache-Control: no-cache" -o bot/lux_sqlite_harden.py "$BASE/bot/lux_sqlite_harden.py"
curl -fsSL -H "Cache-Control: no-cache" -o bot/runtime_supervisor.py "$BASE/bot/runtime_supervisor.py"
$PY -m py_compile bot/lux_sqlite_harden.py bot/runtime_supervisor.py

echo "========== repair bacbo =========="
$PY <<'PY'
import ast, re, sqlite3
from pathlib import Path

ROOT = Path("/home/runner/workspace")
p = ROOT / "bacbo_royal_complete.py"
src = p.read_text(encoding="utf-8", errors="replace")

def ok(t):
    try:
        ast.parse(t)
        return True
    except SyntaxError as e:
        print("parse_fail:", e)
        return False

if not ok(src):
    print("BROKEN — restore from bak")
    for c in sorted(ROOT.glob("bacbo_royal_complete.py.bak*"), key=lambda x: x.stat().st_mtime, reverse=True):
        t = c.read_text(encoding="utf-8", errors="replace")
        if ok(t):
            p.write_text(t, encoding="utf-8")
            src = t
            print("RESTORED", c.name)
            break
    else:
        raise SystemExit("no good bak")

# Fix empty except Exception as _re/_we: immediately followed by else:
src = re.sub(
    r"(^[ \t]*)except Exception as (_re|_we)[ \t]*:[ \t]*\n([ \t]*)else:[ \t]*\n",
    r"\1except Exception as \2:\n\1    log.error('[Watchdog] Reconnect failed: %s' % (\2,))\n\3else:\n",
    src,
    flags=re.M,
)

# Remove luxury watchdog soft blocks → plain log.error
src = re.sub(
    r"^[ \t]*# --- LUXURY_WATCHDOG_DBLOCK \(auto\) ---\n"
    r"^[ \t]*if \"database is locked\"[^\n]*\n"
    r"^[ \t]*log\.warning\([^\n]*\n"
    r"^[ \t]*else:\n"
    r"^([ \t]*)log\.error\([^\n]*Reconnect failed[^\n]*\n"
    r"^[ \t]*# --- end LUXURY_WATCHDOG_DBLOCK ---\n",
    r"\1log.error('[Watchdog] Reconnect failed')\n",
    src,
    flags=re.M,
)

# Also restore proper log.error with var if we oversimplified — fix _re/_we excepts that only have generic message
# Prefer: after except as VAR, ensure a body line exists
src = re.sub(
    r"(^[ \t]*)except Exception as (_re|_we)[ \t]*:[ \t]*\n(?=[ \t]*else:)",
    r"\1except Exception as \2:\n\1    log.error('[Watchdog] Reconnect failed: %s' % (\2,))\n",
    src,
    flags=re.M,
)

# Strip crashguard block (re-add clean)
src = re.sub(
    r"^[ \t]*# --- LUXURY_CRASHGUARD_DBLOCK \(auto\) ---\n"
    r"(?:^[ \t]+.*\n)*?"
    r"^[ \t]*# --- end LUXURY_CRASHGUARD_DBLOCK ---\n",
    "",
    src,
    flags=re.M,
)

# Strip softwrap leftovers
if "LUXURY_DBLOCK_SOFTWRAP" in src:
    lines = src.splitlines(True)
    out = []
    i = 0
    while i < len(lines):
        if lines[i].lstrip().startswith("# LUXURY_DBLOCK_SOFTWRAP"):
            indent = re.match(r"^([ \t]*)", lines[i]).group(1)
            j = i + 1
            while j < len(lines) and not re.match("^" + re.escape(indent) + r"else:\s*$", lines[j]):
                j += 1
            if j >= len(lines):
                out.append(lines[i])
                i += 1
                continue
            j += 1
            while j < len(lines):
                ln = lines[j]
                if ln.strip() == "":
                    out.append(ln)
                    j += 1
                    continue
                cur = re.match(r"^([ \t]*)", ln).group(1)
                if len(cur) <= len(indent):
                    break
                if ln.startswith("    "):
                    out.append(ln[4:])
                else:
                    out.append(ln)
                j += 1
            i = j
            continue
        out.append(lines[i])
        i += 1
    src = "".join(out)
    print("stripped softwrap")

# Harden once
harden = (
    "\n# --- LUXURY_SQLITE_HARDEN (auto) ---\n"
    "try:\n"
    "    import lux_sqlite_harden  # noqa: F401\n"
    '    print("[LUXURY] sqlite harden applied (WAL/busy_timeout/retry)")\n'
    "except Exception as _lux_sql_exc:\n"
    '    print("[LUXURY] sqlite harden skipped:", _lux_sql_exc)\n'
    "# --- end LUXURY_SQLITE_HARDEN ---\n"
)
src = re.sub(
    r"\n# --- LUXURY_SQLITE_HARDEN \(auto\) ---.*?--- end LUXURY_SQLITE_HARDEN ---\n",
    "\n",
    src,
    flags=re.S,
)
lines = src.splitlines(True)
idx = 0
for i, ln in enumerate(lines):
    if "[BOOT] all imports OK" in ln or "[BOOT] stdlib imports OK" in ln:
        idx = i + 1
        break
if idx == 0:
    idx = min(40, len(lines))
lines.insert(idx, harden)
src = "".join(lines)

# CrashGuard soft-skip once
if "LUXURY_CRASHGUARD_DBLOCK" not in src:
    m = re.search(
        r"^([ \t]*)log\.error\(\s*\n[ \t]*f\"\[CrashGuard\] Bot crashed \(attempt #\{_consecutive_failures\}\): \{exc\}\.",
        src,
        flags=re.M,
    )
    if m:
        ind = m.group(1)
        block = (
            ind + "# --- LUXURY_CRASHGUARD_DBLOCK (auto) ---\n"
            + ind + 'if "database is locked" in str(exc).lower() or "database is busy" in str(exc).lower():\n'
            + ind + '    log.warning("[CrashGuard] soft DB lock (no reconnect): %s", exc)\n'
            + ind + "    await asyncio.sleep(2)\n"
            + ind + "    continue\n"
            + ind + "# --- end LUXURY_CRASHGUARD_DBLOCK ---\n"
        )
        src = src[: m.start()] + block + src[m.start() :]
        print("injected CRASHGUARD_DBLOCK")
    else:
        print("WARN: CrashGuard pattern not found")

# state force
if "state = _lux_state_mod" not in src:
    force = (
        "# --- LUXURY_STATE_NAME_FORCE (auto) ---\n"
        "import state as _lux_state_mod\n"
        "state = _lux_state_mod\n"
        "# --- end LUXURY_STATE_NAME_FORCE ---\n"
    )
    src = re.sub(
        r"\n# --- LUXURY_STATE_NAME_FORCE \(auto\) ---.*?--- end LUXURY_STATE_NAME_FORCE ---\n",
        "\n",
        src,
        flags=re.S,
    )
    if re.search(r"^state\.engine\s*=", src, re.M):
        src = re.sub(r"^(state\.engine\s*=)", force + r"\1", src, count=1, flags=re.M)
        print("state force inserted")

if "LUXURY_SESSION_AND_BIND" in src:
    chunk = src.split("LUXURY_SESSION_AND_BIND", 1)[1][:900]
    if "state = _lux_state_mod" not in chunk:
        src = src.replace(
            'print("[LUXURY] proxy bind failed:", _lux_bind_exc)\n# --- end LUXURY_SESSION_AND_BIND ---',
            'print("[LUXURY] proxy bind failed:", _lux_bind_exc)\nstate = _lux_state_mod\n# --- end LUXURY_SESSION_AND_BIND ---',
        )

if not ok(src):
    raise SystemExit("still broken after repair")

p.write_text(src, encoding="utf-8")
print("bacbo OK", p.stat().st_size)

db = ROOT / "bot" / "bacbo.db"
if db.exists():
    con = sqlite3.connect(str(db), timeout=60)
    print("journal_mode", con.execute("PRAGMA journal_mode=WAL").fetchone()[0])
    con.close()
PY

echo "========== compile =========="
$PY -m py_compile bacbo_royal_complete.py
echo "compile OK"

echo "========== restart =========="
set -a
source ./luxury_building.env 2>/dev/null || true
set +a
export TELEGRAM_SESSION_STRING="$(tr -d '\n' < .telegram_session_string)"
export TELEGRAM_TARGET_PEER="${TELEGRAM_TARGET_PEER:-6774605259}"
export FALLBACKS_ENABLED=0
export EDGE_POLICY_MODE=luxury
export EDGE_LUXURY_FLOOR_GATE=1
export BOT_TZ=America/Sao_Paulo
export PYTHONPATH="/home/runner/workspace/bot:/home/runner/workspace:${PYTHONPATH:-}"

echo "===== FIX_NOW marker $(date -u +%Y-%m-%dT%H:%M:%SZ) =====" >> logs/bot_live.log

nohup env EDGE_POLICY_MODE=luxury EDGE_LUXURY_FLOOR_GATE=1 FALLBACKS_ENABLED=0 \
  BOT_TZ=America/Sao_Paulo \
  TELEGRAM_SESSION_STRING="$TELEGRAM_SESSION_STRING" \
  TELEGRAM_TARGET_PEER="$TELEGRAM_TARGET_PEER" \
  PYTHONPATH="$PYTHONPATH" \
  python3 -u bot/runtime_supervisor.py > /tmp/luxury_supervisor.log 2>&1 &
echo "supervisor pid=$!"

sleep 25
echo "----- 25s -----"
pgrep -af 'runtime_supervisor|bacbo_royal' || true
sleep 45

$PY <<'PY'
from pathlib import Path
import re, subprocess
log = Path("logs/bot_live.log").read_text(errors="ignore")
idx = log.rfind("===== FIX_NOW marker")
chunk = log[idx:] if idx >= 0 else log[-6000:]
print("run_forever", "run_forever" in chunk)
print("harden", "sqlite harden applied" in chunk)
print("NameError", "NameError: name 'state'" in chunk)
print("IndentationError", "IndentationError" in chunk)
print("CrashGuard", len(re.findall(r"\[CrashGuard\] Bot crashed", chunk)))
print("--- procs ---")
print(subprocess.getoutput("pgrep -af 'runtime_supervisor|bacbo_royal' || echo NONE"))
print("--- last 20 ---")
print("\n".join(Path("logs/bot_live.log").read_text(errors="ignore").splitlines()[-20:]))
procs = subprocess.getoutput("pgrep -af bacbo_royal || true")
ok = ("run_forever" in chunk and "bacbo_royal" in procs
      and "IndentationError" not in chunk and "NameError: name 'state'" not in chunk)
print("VERDICT:", "OK" if ok else "BAD — paste ALL output")
PY

echo
echo "DONE. Paste ALL output."
echo "Do NOT paste old V2/V3/V4 commands."
