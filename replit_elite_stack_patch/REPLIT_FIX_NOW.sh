#!/usr/bin/env bash
# Bulletproof recovery: restore parseable bak, minimal patches only, restart.
# Safe to re-run. Does NOT touch Watchdog except-bodies (that caused IndentationError).
set -euo pipefail
cd /home/runner/workspace

SHA="${LUXURY_PATCH_SHA:-cursor/add-engine-gate-registry-d5ba}"
BASE="https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/${SHA}/replit_elite_stack_patch"
PY=python3

echo "========== [1/4] stop =========="
pkill -9 -f 'bacbo_royal_complete.py' 2>/dev/null || true
pkill -9 -f 'runtime_supervisor.py' 2>/dev/null || true
pkill -9 -f 'fallback_signal_sender.py' 2>/dev/null || true
pkill -9 -f 'fallback_result_sender.py' 2>/dev/null || true
sleep 2

echo "========== [2/4] download runtime bits =========="
mkdir -p bot/data logs
curl -fsSL -H "Cache-Control: no-cache" -o bot/lux_sqlite_harden.py "$BASE/bot/lux_sqlite_harden.py"
curl -fsSL -H "Cache-Control: no-cache" -o bot/runtime_supervisor.py "$BASE/bot/runtime_supervisor.py"
$PY -m py_compile bot/lux_sqlite_harden.py bot/runtime_supervisor.py

echo "========== [3/4] restore bak + minimal patch =========="
$PY <<'PY'
import ast, re, sqlite3
from pathlib import Path

ROOT = Path("/home/runner/workspace")
p = ROOT / "bacbo_royal_complete.py"

def parses(t: str):
    try:
        ast.parse(t)
        return True, None
    except SyntaxError as e:
        return False, e

# Collect candidates: preferred names first, then all baks by mtime
preferred = [
    ROOT / "bacbo_royal_complete.py.bak_pre_state_fix",
    ROOT / "bacbo_royal_complete.py.bak_pre_client_fix",
    ROOT / "bacbo_royal_complete.py.bak_pre_v4",
    ROOT / "bacbo_royal_complete.py.bak_pre_session_fix",
]
cands = []
for c in preferred:
    if c.exists():
        cands.append(c)
for c in sorted(ROOT.glob("bacbo_royal_complete.py.bak*"), key=lambda x: x.stat().st_mtime, reverse=True):
    if c not in cands:
        cands.append(c)
if p.exists():
    cands.insert(0, p)  # try current first only if it parses

src = None
src_path = None
for c in cands:
    t = c.read_text(encoding="utf-8", errors="replace")
    good, err = parses(t)
    print("candidate", c.name, "OK" if good else f"BAD:{err}")
    if good:
        # Prefer files that already have luxury session bind / are large
        src, src_path = t, c
        # If this is current and good, use it; else keep looking for bak_pre_state_fix
        if c.name == "bacbo_royal_complete.py.bak_pre_state_fix":
            break
        if c == p and good:
            # current parses — still prefer bak_pre_state_fix if available later in loop
            # but if we're first and good, remember and continue for preferred bak
            if any(x.name == "bacbo_royal_complete.py.bak_pre_state_fix" and x.exists() for x in preferred):
                continue
            break
        if "LUXURY_SESSION_AND_BIND" in t or "state = _lux_state_mod" in t or c.stat().st_size > 2_000_000:
            # good enough working luxury file
            if c.name.startswith("bacbo_royal_complete.py.bak"):
                break

if src is None:
    raise SystemExit("FATAL: no parseable bacbo or bak")

print("USING", src_path.name, "size", len(src))
# Save broken current
if p.exists():
    broken = ROOT / "bacbo_royal_complete.py.bak_broken_pre_fixnow2"
    if not broken.exists():
        broken.write_text(p.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")
        print("saved broken ->", broken.name)

# Start clean from chosen source
text = src

# Remove ALL prior luxury auto patches that we will re-apply (safe markers only)
for marker in (
    "LUXURY_SQLITE_HARDEN",
    "LUXURY_CRASHGUARD_DBLOCK",
    "LUXURY_STATE_NAME_FORCE",
    "LUXURY_DBLOCK_SOFT",
):
    text = re.sub(
        rf"\n# --- {marker} \(auto\) ---.*?--- end {marker} ---\n",
        "\n",
        text,
        flags=re.S,
    )

# Strip V2 softwrap if present
if "LUXURY_DBLOCK_SOFTWRAP" in text:
    lines = text.splitlines(True)
    out = []
    i = 0
    while i < len(lines):
        if lines[i].lstrip().startswith("# LUXURY_DBLOCK_SOFTWRAP"):
            indent = re.match(r"^([ \t]*)", lines[i]).group(1)
            j = i + 1
            while j < len(lines) and not re.match("^" + re.escape(indent) + r"else:\s*$", lines[j]):
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
                out.append(ln[4:] if ln.startswith("    ") else ln)
                j += 1
            i = j
            continue
        out.append(lines[i]); i += 1
    text = "".join(out)
    print("stripped softwrap")

# Strip LUXURY_WATCHDOG_DBLOCK by restoring the log.error line only (line-based, safe)
lines = text.splitlines(True)
out = []
i = 0
while i < len(lines):
    if "# --- LUXURY_WATCHDOG_DBLOCK (auto) ---" in lines[i]:
        # skip until end marker; keep the log.error line inside else if present
        j = i + 1
        kept = None
        while j < len(lines) and "# --- end LUXURY_WATCHDOG_DBLOCK ---" not in lines[j]:
            if "Reconnect failed" in lines[j] and "log.error" in lines[j]:
                # dedent to match surrounding except body (remove one level if under else)
                ln = lines[j]
                if ln.startswith("    "):
                    # try to match indent of the marker line
                    ind = re.match(r"^([ \t]*)", lines[i]).group(1)
                    kept = ind + ln.lstrip()
                else:
                    kept = ln
            j += 1
        if j < len(lines) and "# --- end LUXURY_WATCHDOG_DBLOCK ---" in lines[j]:
            j += 1
        if kept:
            out.append(kept if kept.endswith("\n") else kept + "\n")
        else:
            # synthesize
            ind = re.match(r"^([ \t]*)", lines[i]).group(1)
            out.append(ind + "log.error('[Watchdog] Reconnect failed')\n")
        i = j
        continue
    out.append(lines[i]); i += 1
text = "".join(out)

good, err = parses(text)
if not good:
    print("after strip still bad:", err)
    # fall back to raw chosen source with NO strips except harden later
    text = src
    for marker in ("LUXURY_SQLITE_HARDEN", "LUXURY_CRASHGUARD_DBLOCK", "LUXURY_STATE_NAME_FORCE"):
        text = re.sub(
            rf"\n# --- {marker} \(auto\) ---.*?--- end {marker} ---\n",
            "\n",
            text,
            flags=re.S,
        )
    good, err = parses(text)
    if not good:
        raise SystemExit(f"cannot recover parseable source: {err}")

# --- minimal patches ---
# 1) sqlite harden
harden = (
    "\n# --- LUXURY_SQLITE_HARDEN (auto) ---\n"
    "try:\n"
    "    import lux_sqlite_harden  # noqa: F401\n"
    '    print("[LUXURY] sqlite harden applied (WAL/busy_timeout/retry)")\n'
    "except Exception as _lux_sql_exc:\n"
    '    print("[LUXURY] sqlite harden skipped:", _lux_sql_exc)\n'
    "# --- end LUXURY_SQLITE_HARDEN ---\n"
)
lines = text.splitlines(True)
idx = 0
for i, ln in enumerate(lines):
    if "[BOOT] all imports OK" in ln or "[BOOT] stdlib imports OK" in ln:
        idx = i + 1
        break
if idx == 0:
    idx = min(40, len(lines))
lines.insert(idx, harden)
text = "".join(lines)

# 2) state name force before state.engine
if not re.search(r"^state\s*=\s*_lux_state_mod\s*$", text, re.M):
    force = (
        "# --- LUXURY_STATE_NAME_FORCE (auto) ---\n"
        "import state as _lux_state_mod\n"
        "state = _lux_state_mod\n"
        "# --- end LUXURY_STATE_NAME_FORCE ---\n"
    )
    if re.search(r"^state\.engine\s*=", text, re.M):
        text = re.sub(r"^(state\.engine\s*=)", force + r"\1", text, count=1, flags=re.M)
        print("state force inserted")

# Ensure SESSION_AND_BIND assigns state=
if "LUXURY_SESSION_AND_BIND" in text:
    chunk = text.split("LUXURY_SESSION_AND_BIND", 1)[1][:1000]
    if "state = _lux_state_mod" not in chunk:
        text = text.replace(
            'print("[LUXURY] proxy bind failed:", _lux_bind_exc)\n# --- end LUXURY_SESSION_AND_BIND ---',
            'print("[LUXURY] proxy bind failed:", _lux_bind_exc)\nstate = _lux_state_mod\n# --- end LUXURY_SESSION_AND_BIND ---',
        )
        print("added state= to SESSION_AND_BIND")

# 3) CrashGuard soft-skip — insert ONLY before the Bot crashed log.error, no except wrapping
if "LUXURY_CRASHGUARD_DBLOCK" not in text:
    m = re.search(
        r"^([ \t]*)log\.error\(\s*\n[ \t]*f\"\[CrashGuard\] Bot crashed \(attempt #\{_consecutive_failures\}\): \{exc\}\.",
        text,
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
        text = text[: m.start()] + block + text[m.start() :]
        print("injected CRASHGUARD_DBLOCK")
    else:
        print("WARN: CrashGuard pattern missing — skip")

good, err = parses(text)
if not good:
    raise SystemExit(f"patched file invalid: {err}")

p.write_text(text, encoding="utf-8")
print("WROTE bacbo", p.stat().st_size)
print("has_harden", "LUXURY_SQLITE_HARDEN" in text)
print("has_state", "state = _lux_state_mod" in text)
print("has_crashguard", "LUXURY_CRASHGUARD_DBLOCK" in text)

db = ROOT / "bot" / "bacbo.db"
if db.exists():
    con = sqlite3.connect(str(db), timeout=60)
    print("journal_mode", con.execute("PRAGMA journal_mode=WAL").fetchone()[0])
    con.close()
PY

echo "========== compile =========="
$PY -m py_compile bacbo_royal_complete.py
echo "compile OK"

echo "========== [4/4] restart =========="
set -a
source ./luxury_building.env 2>/dev/null || true
set +a
export TELEGRAM_SESSION_STRING="$(tr -d '\n' < .telegram_session_string 2>/dev/null || true)"
export TELEGRAM_TARGET_PEER="${TELEGRAM_TARGET_PEER:-6774605259}"
export FALLBACKS_ENABLED=0
export EDGE_POLICY_MODE=luxury
export EDGE_LUXURY_FLOOR_GATE=1
export BOT_TZ=America/Sao_Paulo
export PYTHONPATH="/home/runner/workspace/bot:/home/runner/workspace:${PYTHONPATH:-}"

echo "===== FIX_NOW2 marker $(date -u +%Y-%m-%dT%H:%M:%SZ) =====" >> logs/bot_live.log

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
grep -E 'sqlite harden|run_forever|NameError|IndentationError|SyntaxError|FIRED|GameCoach' logs/bot_live.log | tail -n 25 || true
sleep 40

$PY <<'PY'
from pathlib import Path
import re, subprocess
log = Path("logs/bot_live.log").read_text(errors="ignore")
idx = log.rfind("===== FIX_NOW2 marker")
chunk = log[idx:] if idx >= 0 else log[-8000:]
print("run_forever", "run_forever" in chunk)
print("harden", "sqlite harden applied" in chunk)
print("NameError", "NameError: name 'state'" in chunk)
print("IndentationError", "IndentationError" in chunk)
print("SyntaxError", "SyntaxError" in chunk)
print("CrashGuard", len(re.findall(r"\[CrashGuard\] Bot crashed", chunk)))
print("--- procs ---")
print(subprocess.getoutput("pgrep -af 'runtime_supervisor|bacbo_royal' || echo NONE"))
print("--- last 22 ---")
print("\n".join(Path("logs/bot_live.log").read_text(errors="ignore").splitlines()[-22:]))
procs = subprocess.getoutput("pgrep -af bacbo_royal || true")
ok = ("run_forever" in chunk and "bacbo_royal" in procs
      and "IndentationError" not in chunk and "NameError: name 'state'" not in chunk
      and "SyntaxError" not in chunk)
print("VERDICT:", "OK" if ok else "BAD — paste ALL output")
PY

echo
echo "DONE. Paste ALL output."
echo "IGNORE any command containing V3 or cf7303 or 571d09."
