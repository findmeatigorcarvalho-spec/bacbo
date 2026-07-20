#!/usr/bin/env bash
# V4: repair IndentationError from V3 re-run + restart bacbo-only.
# Root cause: stripping LUXURY_WATCHDOG_DBLOCK deleted the log.error and left empty except.
set -euo pipefail
cd /home/runner/workspace

SHA="${LUXURY_PATCH_SHA:-cursor/add-engine-gate-registry-d5ba}"
BASE="https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/${SHA}/replit_elite_stack_patch"
PY="${PYTHON:-python3}"

echo "========== [1/5] stop procs =========="
pkill -9 -f 'bacbo_royal_complete.py' 2>/dev/null || true
pkill -9 -f 'runtime_supervisor.py' 2>/dev/null || true
pkill -9 -f 'fallback_signal_sender.py' 2>/dev/null || true
pkill -9 -f 'fallback_result_sender.py' 2>/dev/null || true
sleep 2

echo "========== [2/5] download harden + supervisor =========="
mkdir -p bot/data logs
curl -fsSL -H "Cache-Control: no-cache" -o bot/lux_sqlite_harden.py "$BASE/bot/lux_sqlite_harden.py"
curl -fsSL -H "Cache-Control: no-cache" -o bot/runtime_supervisor.py "$BASE/bot/runtime_supervisor.py"
$PY -m py_compile bot/lux_sqlite_harden.py bot/runtime_supervisor.py

echo "========== [3/5] repair bacbo (idempotent) =========="
$PY <<'PY'
import ast, re, sqlite3, shutil
from pathlib import Path

ROOT = Path("/home/runner/workspace")
p = ROOT / "bacbo_royal_complete.py"
src = p.read_text(encoding="utf-8", errors="replace")

# Backup current (even if broken)
bak = ROOT / f"bacbo_royal_complete.py.bak_pre_v4"
if not bak.exists():
    bak.write_text(src, encoding="utf-8")
    print("saved", bak)

# If file does not parse, try restore from best bak that parses
def parses(t: str) -> bool:
    try:
        ast.parse(t)
        return True
    except SyntaxError as e:
        print("parse_fail", e)
        return False

if not parses(src):
    print("bacbo BROKEN — searching bak restore")
    candidates = sorted(ROOT.glob("bacbo_royal_complete.py.bak*"), key=lambda x: x.stat().st_mtime, reverse=True)
    # Prefer pre_state_fix / pre_v2 / largest recent good
    restored = False
    for c in candidates:
        t = c.read_text(encoding="utf-8", errors="replace")
        if parses(t):
            # Prefer baks that still have LUXURY session bind if possible
            p.write_text(t, encoding="utf-8")
            src = t
            print("RESTORED from", c.name, "size", c.stat().st_size)
            restored = True
            break
    if not restored:
        raise SystemExit("no parseable bacbo bak found")

# --- Fix empty except left by V3 watchdog strip ---
# Pattern:
#   except Exception as _re:
#   <blank or comment>
#   else:
src2 = re.sub(
    r"(^[ \t]*except Exception as (_re|_we)\s*:\s*\n)"
    r"(?:[ \t]*# --- LUXURY_WATCHDOG_DBLOCK[\s\S]*?# --- end LUXURY_WATCHDOG_DBLOCK ---\n)?",
    lambda m: (
        f"{m.group(1)}"
        f"{re.match(r'^[ \t]*', m.group(1)).group(0)}    "
        f"log.error(f\"[Watchdog] Reconnect failed: {{{m.group(2)}}}\")\n"
    ),
    src,
    flags=re.M,
)

# More direct: empty except before else
src2 = re.sub(
    r"(^[ \t]*)except Exception as (_re|_we)\s*:\s*\n([ \t]*)else:\s*\n",
    r"\1except Exception as \2:\n\1    log.error(f\"[Watchdog] Reconnect failed: {\2}\")\n\3else:\n",
    src2,
    flags=re.M,
)

# Strip ALL luxury watchdog dblock wrappers and restore plain log.error
src2 = re.sub(
    r"^[ \t]*# --- LUXURY_WATCHDOG_DBLOCK \(auto\) ---\n"
    r"^[ \t]*if \"database is locked\"[^\n]*\n"
    r"^[ \t]*log\.warning\(\"[Watchdog\] soft DB lock[^\n]*\n"
    r"^[ \t]*else:\s*\n"
    r"^([ \t]*)log\.error\(f\"\[Watchdog\] Reconnect failed: \{(_re|_we)\}\"\)\s*\n"
    r"^[ \t]*# --- end LUXURY_WATCHDOG_DBLOCK ---\n",
    r"\1log.error(f\"[Watchdog] Reconnect failed: {\2}\")\n",
    src2,
    flags=re.M,
)

# Strip crashguard dblock (re-apply cleanly once)
src2 = re.sub(
    r"^[ \t]*# --- LUXURY_CRASHGUARD_DBLOCK \(auto\) ---\n"
    r"^[ \t]*if \"database is locked\"[\s\S]*?"
    r"^[ \t]*# --- end LUXURY_CRASHGUARD_DBLOCK ---\n",
    "",
    src2,
    flags=re.M,
)

# Strip V2 softwrap leftovers if any
if "LUXURY_DBLOCK_SOFTWRAP" in src2:
    lines = src2.splitlines(True)
    out = []
    i = 0
    while i < len(lines):
        if lines[i].lstrip().startswith("# LUXURY_DBLOCK_SOFTWRAP"):
            indent = re.match(r"^([ \t]*)", lines[i]).group(1)
            j = i + 1
            while j < len(lines) and not re.match(rf"^{re.escape(indent)}else:\s*$", lines[j]):
                j += 1
            if j >= len(lines):
                out.append(lines[i]); i += 1; continue
            j += 1
            while j < len(lines):
                ln = lines[j]
                if ln.strip() == "":
                    out.append(ln); j += 1; continue
                cur = re.match(r"^([ \t]*)", ln).group(1)
                if len(cur) <= len(indent):
                    break
                if ln.startswith(indent + "    "):
                    out.append(indent + ln[len(indent)+4:])
                elif ln.startswith("    "):
                    out.append(ln[4:])
                else:
                    out.append(ln)
                j += 1
            i = j
            continue
        out.append(lines[i]); i += 1
    src2 = "".join(out)
    print("stripped softwrap leftovers")

# Ensure harden once
harden = '''
# --- LUXURY_SQLITE_HARDEN (auto) ---
try:
    import lux_sqlite_harden  # noqa: F401
    print("[LUXURY] sqlite harden applied (WAL/busy_timeout/retry)")
except Exception as _lux_sql_exc:
    print("[LUXURY] sqlite harden skipped:", _lux_sql_exc)
# --- end LUXURY_SQLITE_HARDEN ---
'''
src2 = re.sub(
    r"\n# --- LUXURY_SQLITE_HARDEN \(auto\) ---.*?--- end LUXURY_SQLITE_HARDEN ---\n",
    "\n",
    src2,
    flags=re.S,
)
lines = src2.splitlines(True)
idx = 0
for i, ln in enumerate(lines):
    if "[BOOT] all imports OK" in ln or "[BOOT] stdlib imports OK" in ln:
        idx = i + 1
        break
if idx == 0:
    idx = min(40, len(lines))
lines.insert(idx, harden)
src2 = "".join(lines)

# Inject CrashGuard soft-skip ONCE (idempotent)
if "LUXURY_CRASHGUARD_DBLOCK" not in src2:
    m = re.search(
        r"^([ \t]*)log\.error\(\s*\n([ \t]*)f\"\[CrashGuard\] Bot crashed \(attempt #\{_consecutive_failures\}\): \{exc\}\.",
        src2,
        flags=re.M,
    )
    if m:
        ind = m.group(1)
        block = (
            f"{ind}# --- LUXURY_CRASHGUARD_DBLOCK (auto) ---\n"
            f"{ind}if \"database is locked\" in str(exc).lower() or \"database is busy\" in str(exc).lower():\n"
            f"{ind}    log.warning(\"[CrashGuard] soft DB lock (no reconnect): %s\", exc)\n"
            f"{ind}    await asyncio.sleep(2)\n"
            f"{ind}    continue\n"
            f"{ind}# --- end LUXURY_CRASHGUARD_DBLOCK ---\n"
        )
        src2 = src2[: m.start()] + block + src2[m.start() :]
        print("injected CRASHGUARD_DBLOCK")
    else:
        print("WARN: CrashGuard log.error not found")

# Watchdog soft — wrap log.error only if not already wrapped (look behind)
def soft_watchdog_line(text: str, var: str) -> str:
    lines = text.splitlines(True)
    out = []
    i = 0
    hits = 0
    needle = f'[Watchdog] Reconnect failed: {{{var}}}'
    while i < len(lines):
        ln = lines[i]
        if "log.error" in ln and needle in ln and ln.strip().endswith(")"):
            prev = "".join(lines[max(0, i - 6) : i])
            if "LUXURY_WATCHDOG_DBLOCK" in prev:
                out.append(ln)
                i += 1
                continue
            ind = re.match(r"^([ \t]*)", ln).group(1)
            out.append(f"{ind}# --- LUXURY_WATCHDOG_DBLOCK (auto) ---\n")
            out.append(
                f"{ind}if \"database is locked\" in str({var}).lower() or \"database is busy\" in str({var}).lower():\n"
            )
            out.append(f"{ind}    log.warning(\"[Watchdog] soft DB lock (no reconnect): %s\", {var})\n")
            out.append(f"{ind}else:\n")
            out.append(f"{ind}    log.error(f\"[Watchdog] Reconnect failed: {{{var}}}\")\n")
            out.append(f"{ind}# --- end LUXURY_WATCHDOG_DBLOCK ---\n")
            hits += 1
            i += 1
            continue
        out.append(ln)
        i += 1
    print(f"watchdog_soft_{var}", hits)
    return "".join(out)

src2 = soft_watchdog_line(src2, "_re")
src2 = soft_watchdog_line(src2, "_we")

# state force
if "state = _lux_state_mod" not in src2:
    force = (
        "# --- LUXURY_STATE_NAME_FORCE (auto) ---\n"
        "import state as _lux_state_mod\n"
        "state = _lux_state_mod\n"
        "# --- end LUXURY_STATE_NAME_FORCE ---\n"
    )
    src2 = re.sub(
        r"\n# --- LUXURY_STATE_NAME_FORCE \(auto\) ---.*?--- end LUXURY_STATE_NAME_FORCE ---\n",
        "\n",
        src2,
        flags=re.S,
    )
    if re.search(r"^state\.engine\s*=", src2, re.M):
        src2 = re.sub(r"^(state\.engine\s*=)", force + r"\1", src2, count=1, flags=re.M)
        print("reinserted STATE_NAME_FORCE")

if "LUXURY_SESSION_AND_BIND" in src2:
    chunk = src2.split("LUXURY_SESSION_AND_BIND", 1)[1][:900]
    if "state = _lux_state_mod" not in chunk:
        src2 = src2.replace(
            'print("[LUXURY] proxy bind failed:", _lux_bind_exc)\n# --- end LUXURY_SESSION_AND_BIND ---',
            'print("[LUXURY] proxy bind failed:", _lux_bind_exc)\nstate = _lux_state_mod\n# --- end LUXURY_SESSION_AND_BIND ---',
        )

if not parses(src2):
    raise SystemExit("bacbo still broken after repair")

p.write_text(src2, encoding="utf-8")
print("bacbo OK", p.stat().st_size)
print("has_harden", "LUXURY_SQLITE_HARDEN" in src2)
print("has_crashguard", "LUXURY_CRASHGUARD_DBLOCK" in src2)
print("has_state", "state = _lux_state_mod" in src2)

# WAL
db = ROOT / "bot" / "bacbo.db"
if db.exists():
    con = sqlite3.connect(str(db), timeout=60)
    print("journal_mode", con.execute("PRAGMA journal_mode=WAL").fetchone()[0])
    con.close()
PY

echo "========== [4/5] compile + restart =========="
$PY -m py_compile bacbo_royal_complete.py bot/lux_sqlite_harden.py bot/runtime_supervisor.py
echo "compile OK"

set -a; source ./luxury_building.env 2>/dev/null || true; set +a
export TELEGRAM_SESSION_STRING="$(tr -d '\n' < .telegram_session_string)"
export TELEGRAM_TARGET_PEER="${TELEGRAM_TARGET_PEER:-6774605259}"
export FALLBACKS_ENABLED=0
export EDGE_POLICY_MODE=luxury
export EDGE_LUXURY_FLOOR_GATE=1
export BOT_TZ=America/Sao_Paulo
export PYTHONPATH="/home/runner/workspace/bot:/home/runner/workspace:${PYTHONPATH:-}"

echo "===== DB_LOCK_FIX_V4 marker $(date -u +%Y-%m-%dT%H:%M:%SZ) =====" >> logs/bot_live.log

nohup env EDGE_POLICY_MODE=luxury EDGE_LUXURY_FLOOR_GATE=1 FALLBACKS_ENABLED=0 \
  BOT_TZ=America/Sao_Paulo \
  TELEGRAM_SESSION_STRING="$TELEGRAM_SESSION_STRING" \
  TELEGRAM_TARGET_PEER="$TELEGRAM_TARGET_PEER" \
  PYTHONPATH="$PYTHONPATH" \
  python3 -u bot/runtime_supervisor.py > /tmp/luxury_supervisor.log 2>&1 &
echo "supervisor pid=$!"

echo "========== [5/5] settle 70s =========="
sleep 20
pgrep -af 'runtime_supervisor|bacbo_royal|fallback_' || true
sleep 50

$PY <<'PY'
from pathlib import Path
import re, subprocess
log = Path("logs/bot_live.log").read_text(errors="ignore")
idx = log.rfind("===== DB_LOCK_FIX_V4 marker")
chunk = log[idx:] if idx >= 0 else log[-8000:]
print("run_forever", "run_forever" in chunk)
print("harden", "sqlite harden applied" in chunk)
print("NameError_state", "NameError: name 'state'" in chunk)
print("IndentationError", "IndentationError" in chunk)
print("CrashGuard_bot_crashed", len(re.findall(r"\[CrashGuard\] Bot crashed", chunk)))
print("QUIET", len(re.findall(r"QUIET — no signal fired", chunk)))
print("FIRED", len(re.findall(r"FIRED|EdgePolicy.*ALLOW", chunk)))
print("GameCoach_sent", len(re.findall(r"GameCoach.*sent", chunk)))
print("--- procs ---")
print(subprocess.getoutput("pgrep -af 'runtime_supervisor|bacbo_royal|fallback_' || echo NONE"))
print("--- last 30 ---")
print("\n".join(Path("logs/bot_live.log").read_text(errors="ignore").splitlines()[-30:]))
procs = subprocess.getoutput("pgrep -af bacbo_royal || true")
ok = "run_forever" in chunk and "bacbo_royal" in procs and "IndentationError" not in chunk and "NameError: name 'state'" not in chunk
print("VERDICT:", "OK — bot up" if ok else "STILL_BAD — paste ALL output")
print()
print("NOTE: RoundAudit QUIET = gates/consensus not firing yet (Telegram send works if GameCoach sent).")
print("Signals to chat need FIRED/ALLOW — not just room Recv.")
PY

echo
echo "DONE. Paste ALL output. Do NOT re-run V2/V3."
