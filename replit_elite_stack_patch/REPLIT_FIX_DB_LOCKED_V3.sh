#!/usr/bin/env bash
# V3: surgical DB-lock fix. V2 died mid-patch (watchdog syntax) and left bot stopped.
# - do NOT softwrap watchdog.py
# - targeted CrashGuard / Watchdog soft-skip in bacbo only
# - FALLBACKS_ENABLED=0, restart, verify
set -euo pipefail
cd /home/runner/workspace

SHA="${LUXURY_PATCH_SHA:-cursor/add-engine-gate-registry-d5ba}"
BASE="https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/${SHA}/replit_elite_stack_patch"
PY="${PYTHON:-python3}"

echo "========== [1/6] stop procs =========="
pkill -9 -f 'bacbo_royal_complete.py' 2>/dev/null || true
pkill -9 -f 'runtime_supervisor.py' 2>/dev/null || true
pkill -9 -f 'fallback_signal_sender.py' 2>/dev/null || true
pkill -9 -f 'fallback_result_sender.py' 2>/dev/null || true
sleep 2

echo "========== [2/6] download harden + supervisor =========="
mkdir -p bot/data logs
curl -fsSL -H "Cache-Control: no-cache" -o bot/lux_sqlite_harden.py "$BASE/bot/lux_sqlite_harden.py"
curl -fsSL -H "Cache-Control: no-cache" -o bot/runtime_supervisor.py "$BASE/bot/runtime_supervisor.py"
$PY -m py_compile bot/lux_sqlite_harden.py bot/runtime_supervisor.py
# Restore watchdog if V2 corrupted it — prefer bak, else leave alone if it still parses
$PY <<'PY'
import ast
from pathlib import Path
wd = Path("bot/watchdog.py")
if not wd.exists():
    print("no watchdog.py")
else:
    try:
        ast.parse(wd.read_text(encoding="utf-8", errors="replace"))
        print("watchdog.py parses OK — leave it")
    except SyntaxError as e:
        print("watchdog.py BROKEN", e)
        for bak in sorted(Path("bot").glob("watchdog.py.bak*"), reverse=True):
            try:
                t = bak.read_text(encoding="utf-8", errors="replace")
                ast.parse(t)
                wd.write_text(t)
                print("restored watchdog from", bak)
                break
            except Exception:
                continue
        else:
            # strip luxury softwrap junk if present
            t = wd.read_text(encoding="utf-8", errors="replace")
            if "LUXURY_DBLOCK_SOFTWRAP" in t or "LUXURY_SQLITE_HARDEN" in t:
                import re
                t2 = re.sub(r"\n# --- LUXURY_SQLITE_HARDEN \(auto\) ---.*?--- end LUXURY_SQLITE_HARDEN ---\n", "\n", t, flags=re.S)
                # too risky to auto-unsoftwrap; just report
                print("WARN: watchdog broken and no bak — manual check needed")
            raise SystemExit("watchdog.py broken")
PY

echo "========== [3/6] surgical bacbo patch =========="
$PY <<'PY'
import ast, re, sqlite3
from pathlib import Path

ROOT = Path("/home/runner/workspace")
db = ROOT / "bot" / "bacbo.db"
if db.exists():
    con = sqlite3.connect(str(db), timeout=120)
    con.execute("PRAGMA busy_timeout=120000")
    print("journal_mode", con.execute("PRAGMA journal_mode=WAL").fetchone()[0])
    try:
        print("checkpoint", con.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone())
    except Exception as e:
        print("checkpoint_fail", e)
    con.close()

p = ROOT / "bacbo_royal_complete.py"
src = p.read_text(encoding="utf-8", errors="replace")

def strip_softwraps(text: str) -> str:
    if "LUXURY_DBLOCK_SOFTWRAP" not in text:
        return text
    lines = text.splitlines(True)
    out: list[str] = []
    i = 0
    removed = 0
    while i < len(lines):
        if lines[i].lstrip().startswith("# LUXURY_DBLOCK_SOFTWRAP"):
            indent = re.match(r"^([ \t]*)", lines[i]).group(1)
            j = i + 1
            # skip to else:
            while j < len(lines) and not re.match(rf"^{re.escape(indent)}else:\s*$", lines[j]):
                j += 1
            if j >= len(lines):
                out.append(lines[i])
                i += 1
                continue
            j += 1  # skip else:
            while j < len(lines):
                ln = lines[j]
                if ln.strip() == "":
                    out.append(ln)
                    j += 1
                    continue
                cur = re.match(r"^([ \t]*)", ln).group(1)
                if len(cur) <= len(indent):
                    break
                # dedent 4 spaces
                if ln.startswith(indent + "    "):
                    out.append(indent + ln[len(indent) + 4 :])
                elif ln.startswith("    "):
                    out.append(ln[4:])
                else:
                    out.append(ln)
                j += 1
            removed += 1
            i = j
            continue
        out.append(lines[i])
        i += 1
    print("stripped_softwrap_blocks", removed)
    return "".join(out)

src = strip_softwraps(src)

# Ensure sqlite harden (bacbo only)
harden = '''
# --- LUXURY_SQLITE_HARDEN (auto) ---
try:
    import lux_sqlite_harden  # noqa: F401
    print("[LUXURY] sqlite harden applied (WAL/busy_timeout/retry)")
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

# Targeted CrashGuard soft-skip: before the Bot crashed log.error in else branch
src = re.sub(
    r"\n[ \t]*# --- LUXURY_CRASHGUARD_DBLOCK \(auto\) ---.*?--- end LUXURY_CRASHGUARD_DBLOCK ---\n",
    "\n",
    src,
    flags=re.S,
)
if "LUXURY_CRASHGUARD_DBLOCK" not in src:
    # Insert immediately before the log.error( that contains Bot crashed
    m = re.search(
        r"^([ \t]*)log\.error\(\s*\n([ \t]*)f\"\[CrashGuard\] Bot crashed \(attempt #\{_consecutive_failures\}\): \{exc\}\.",
        src,
        flags=re.M,
    )
    if not m:
        m = re.search(
            r"^([ \t]*)log\.error\(\s*f\"\[CrashGuard\] Bot crashed",
            src,
            flags=re.M,
        )
    if m:
        indent = m.group(1)
        block = (
            f"{indent}# --- LUXURY_CRASHGUARD_DBLOCK (auto) ---\n"
            f"{indent}if \"database is locked\" in str(exc).lower() or \"database is busy\" in str(exc).lower():\n"
            f"{indent}    log.warning(\"[CrashGuard] soft DB lock (no reconnect): %s\", exc)\n"
            f"{indent}    await asyncio.sleep(2)\n"
            f"{indent}    continue\n"
            f"{indent}# --- end LUXURY_CRASHGUARD_DBLOCK ---\n"
        )
        src = src[: m.start()] + block + src[m.start() :]
        print("injected CRASHGUARD_DBLOCK")
    else:
        print("WARN: CrashGuard Bot crashed log.error not found")

# Watchdog: soft-skip only the Reconnect failed log lines (keep following statements)
src = re.sub(
    r"\n[ \t]*# --- LUXURY_WATCHDOG_DBLOCK \(auto\) ---.*?--- end LUXURY_WATCHDOG_DBLOCK ---\n",
    "\n",
    src,
    flags=re.S,
)
n_wd = 0
for var in ("_re", "_we"):
    pat = re.compile(
        rf"^([ \t]*)log\.error\(f\"\[Watchdog\] Reconnect failed: \{{{var}\}}\"\)\s*$",
        flags=re.M,
    )

    def make_repl(v: str):
        def repl(m: re.Match) -> str:
            nonlocal n_wd
            ind = m.group(1)
            n_wd += 1
            return (
                f"{ind}# --- LUXURY_WATCHDOG_DBLOCK (auto) ---\n"
                f"{ind}if \"database is locked\" in str({v}).lower() or \"database is busy\" in str({v}).lower():\n"
                f"{ind}    log.warning(\"[Watchdog] soft DB lock (no reconnect): %s\", {v})\n"
                f"{ind}else:\n"
                f"{ind}    log.error(f\"[Watchdog] Reconnect failed: {{{v}}}\")\n"
                f"{ind}# --- end LUXURY_WATCHDOG_DBLOCK ---"
            )
        return repl

    src, c = pat.subn(make_repl(var), src)
    print(f"watchdog_soft_{var}", c)
print("watchdog_soft_total", n_wd)

# state name force
if "LUXURY_STATE_NAME_FORCE" not in src or "state = _lux_state_mod" not in src:
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
    src = re.sub(r"^(state\.engine\s*=)", force + r"\1", src, count=1, flags=re.M)
    print("reinserted STATE_NAME_FORCE")

if "LUXURY_SESSION_AND_BIND" in src:
    chunk = src.split("LUXURY_SESSION_AND_BIND", 1)[1][:900]
    if "state = _lux_state_mod" not in chunk:
        src = src.replace(
            'print("[LUXURY] proxy bind failed:", _lux_bind_exc)\n# --- end LUXURY_SESSION_AND_BIND ---',
            'print("[LUXURY] proxy bind failed:", _lux_bind_exc)\nstate = _lux_state_mod\n# --- end LUXURY_SESSION_AND_BIND ---',
        )

ast.parse(src)
p.write_text(src, encoding="utf-8")
print("bacbo OK", p.stat().st_size)
print("has_harden", "LUXURY_SQLITE_HARDEN" in src)
print("has_crashguard_dblock", "LUXURY_CRASHGUARD_DBLOCK" in src)
print("has_state_force", "state = _lux_state_mod" in src)

# Show patched CrashGuard context
lines = src.splitlines()
for i, ln in enumerate(lines):
    if "LUXURY_CRASHGUARD_DBLOCK" in ln or ("Bot crashed (attempt" in ln):
        a, b = max(0, i - 3), min(len(lines), i + 8)
        print(f"----- patched {a+1}-{b} -----")
        for j in range(a, b):
            print(f"{j+1}: {lines[j][:160]}")
        if "Bot crashed" in ln:
            break
PY

echo "========== [4/6] compile checks =========="
$PY -m py_compile bacbo_royal_complete.py bot/lux_sqlite_harden.py bot/runtime_supervisor.py
$PY -c "import ast; ast.parse(open('bot/watchdog.py',encoding='utf-8',errors='replace').read()); print('watchdog OK')"
echo "compile OK"

echo "========== [5/6] restart bacbo-only =========="
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

echo "===== DB_LOCK_FIX_V3 marker $(date -u +%Y-%m-%dT%H:%M:%SZ) =====" >> logs/bot_live.log

nohup env EDGE_POLICY_MODE=luxury EDGE_LUXURY_FLOOR_GATE=1 FALLBACKS_ENABLED=0 \
  BOT_TZ=America/Sao_Paulo \
  TELEGRAM_SESSION_STRING="$TELEGRAM_SESSION_STRING" \
  TELEGRAM_TARGET_PEER="$TELEGRAM_TARGET_PEER" \
  PYTHONPATH="$PYTHONPATH" \
  python3 -u bot/runtime_supervisor.py > /tmp/luxury_supervisor.log 2>&1 &
echo "supervisor pid=$!"

echo "========== [6/6] settle 90s + verdict =========="
sleep 25
echo "----- 25s -----"
pgrep -af 'runtime_supervisor|bacbo_royal|fallback_' || true
grep -E 'sqlite harden|soft DB lock|run_forever|NameError|CrashGuard|SEQUENCE/FIRED|SyntaxError' logs/bot_live.log | tail -n 30 || true
sleep 40
echo "----- 65s -----"
pgrep -af 'runtime_supervisor|bacbo_royal|fallback_' || true
sleep 30

$PY <<'PY'
from pathlib import Path
import re, subprocess, sqlite3
log = Path("logs/bot_live.log").read_text(errors="ignore")
idx = log.rfind("===== DB_LOCK_FIX_V3 marker")
chunk = log[idx:] if idx >= 0 else log[-12000:]
print("post_fix_run_forever", "run_forever" in chunk)
print("post_fix_sqlite_harden", "sqlite harden applied" in chunk)
print("post_fix_state_NameError", "NameError: name 'state'" in chunk)
print("post_fix_crashguard_bot_crashed", len(re.findall(r"\[CrashGuard\] Bot crashed", chunk)))
print("post_fix_soft_dblock", len(re.findall(r"soft DB lock", chunk)))
print("post_fix_database_is_locked", len(re.findall(r"database is locked", chunk)))
print("--- procs ---")
print(subprocess.getoutput("pgrep -af 'runtime_supervisor|bacbo_royal|fallback_' || echo NONE"))
print("--- last 25 ---")
print("\n".join(Path("logs/bot_live.log").read_text(errors="ignore").splitlines()[-25:]))
con = sqlite3.connect("file:bot/bacbo.db?mode=ro", uri=True, timeout=30)
print("journal_mode", con.execute("PRAGMA journal_mode").fetchone()[0])
con.close()
procs = subprocess.getoutput("pgrep -af 'runtime_supervisor|bacbo_royal|fallback_' || true")
ok = (
    "run_forever" in chunk
    and "NameError: name 'state'" not in chunk
    and "bacbo_royal" in procs
    and "fallback_signal" not in procs
    and len(re.findall(r"\[CrashGuard\] Bot crashed", chunk)) == 0
)
print("VERDICT:", "OK — bacbo up, no CrashGuard storm" if ok else "STILL_BAD — paste ALL output")
PY

echo
echo "DONE. Paste ALL output."
