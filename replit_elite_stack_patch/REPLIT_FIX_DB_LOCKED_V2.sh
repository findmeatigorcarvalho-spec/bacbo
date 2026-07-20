#!/usr/bin/env bash
# V2: locks returned after WAL harden — bacbo-only + soft-skip CrashGuard reconnect on DB lock.
set -euo pipefail
cd /home/runner/workspace

SHA="${LUXURY_PATCH_SHA:-cursor/add-engine-gate-registry-d5ba}"
BASE="https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/${SHA}/replit_elite_stack_patch"
PY="${PYTHON:-python3}"

echo "========== [1/6] stop all bot procs =========="
pkill -9 -f 'bacbo_royal_complete.py' 2>/dev/null || true
pkill -9 -f 'runtime_supervisor.py' 2>/dev/null || true
pkill -9 -f 'fallback_signal_sender.py' 2>/dev/null || true
pkill -9 -f 'fallback_result_sender.py' 2>/dev/null || true
sleep 2

echo "========== [2/6] download harden + supervisor (fallbacks OFF) =========="
mkdir -p bot/data logs
curl -fsSL -H "Cache-Control: no-cache" -o bot/lux_sqlite_harden.py "$BASE/bot/lux_sqlite_harden.py"
curl -fsSL -H "Cache-Control: no-cache" -o bot/runtime_supervisor.py "$BASE/bot/runtime_supervisor.py"
$PY -m py_compile bot/lux_sqlite_harden.py bot/runtime_supervisor.py
echo "downloaded OK"

echo "========== [3/6] WAL checkpoint + soft-patch CrashGuard/Watchdog =========="
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


def soft_wrap_file(text: str) -> tuple[str, int]:
    """Wrap CrashGuard/Watchdog except-bodies so DB lock skips Telegram reconnect."""
    lines = text.splitlines(True)
    needles = ("[CrashGuard] Bot crashed", "[Watchdog] Reconnect failed")
    blocks: list[tuple[int, int, str, str]] = []
    for i, ln in enumerate(lines):
        if not any(n in ln for n in needles):
            continue
        exc_i = None
        var = None
        indent = ""
        for j in range(i, max(-1, i - 50), -1):
            m = re.match(r"^([ \t]*)except Exception as (\w+)\s*:\s*$", lines[j])
            if m:
                exc_i, var, indent = j, m.group(2), m.group(1)
                break
        if exc_i is None:
            continue
        if "LUXURY_DBLOCK_SOFTWRAP" in "".join(lines[exc_i : i + 1]):
            continue
        end = len(lines)
        k = exc_i + 1
        while k < len(lines):
            ln2 = lines[k]
            if ln2.strip() == "":
                k += 1
                continue
            cur = re.match(r"^([ \t]*)", ln2).group(1)
            if len(cur) <= len(indent):
                end = k
                break
            k += 1
        blocks.append((exc_i, end, var, indent))

    hits = 0
    for exc_i, end, var, indent in sorted(set(blocks), reverse=True):
        body = lines[exc_i + 1 : end]
        if not body or any("LUXURY_DBLOCK_SOFTWRAP" in x for x in body):
            continue
        bi = indent + "    "
        soft_head = [
            f"{bi}# LUXURY_DBLOCK_SOFTWRAP\n",
            f'{bi}_lux_dblock = ("database is locked" in str({var}).lower()) or ("database is busy" in str({var}).lower())\n',
            f"{bi}if _lux_dblock:\n",
            f"{bi}    try:\n",
            f'{bi}        log.warning("[CrashGuard] soft DB lock (no reconnect): %s", {var})\n',
            f"{bi}    except Exception:\n",
            f'{bi}        print("[CrashGuard] soft DB lock (no reconnect)", {var})\n',
            f"{bi}    await asyncio.sleep(2)\n",
            f"{bi}else:\n",
        ]
        wrapped = [("    " + bl) if bl.strip() else bl for bl in body]
        lines[exc_i + 1 : end] = soft_head + wrapped
        hits += 1
    return "".join(lines), hits


def ensure_harden_and_soft(path: Path) -> None:
    if not path.exists():
        print("missing", path)
        return
    src = path.read_text(encoding="utf-8", errors="replace")
    original = src

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
        idx = min(60, len(lines))
    lines.insert(idx, harden)
    src = "".join(lines)

    src3, nsoft = soft_wrap_file(src)
    print(path.name, "dblock_softwraps", nsoft)

    if "state = _lux_state_mod" not in src3 or "LUXURY_STATE_NAME_FORCE" not in src3:
        force = (
            "# --- LUXURY_STATE_NAME_FORCE (auto) ---\n"
            "import state as _lux_state_mod\n"
            "state = _lux_state_mod\n"
            "# --- end LUXURY_STATE_NAME_FORCE ---\n"
        )
        src3 = re.sub(
            r"\n# --- LUXURY_STATE_NAME_FORCE \(auto\) ---.*?--- end LUXURY_STATE_NAME_FORCE ---\n",
            "\n",
            src3,
            flags=re.S,
        )
        if re.search(r"^state\.engine\s*=", src3, re.M):
            src3 = re.sub(r"^(state\.engine\s*=)", force + r"\1", src3, count=1, flags=re.M)
            print(path.name, "reinserted STATE_NAME_FORCE")

    if "LUXURY_SESSION_AND_BIND" in src3:
        chunk = src3.split("LUXURY_SESSION_AND_BIND", 1)[1][:900]
        if "state = _lux_state_mod" not in chunk:
            src3 = src3.replace(
                'print("[LUXURY] proxy bind failed:", _lux_bind_exc)\n# --- end LUXURY_SESSION_AND_BIND ---',
                'print("[LUXURY] proxy bind failed:", _lux_bind_exc)\nstate = _lux_state_mod\n# --- end LUXURY_SESSION_AND_BIND ---',
            )

    try:
        ast.parse(src3)
    except SyntaxError as e:
        print("SYNTAX_FAIL", path, e)
        # keep harden-only if softwrap broke parse
        src_safe = "".join(lines)
        if "state = _lux_state_mod" not in src_safe and re.search(r"^state\.engine\s*=", src_safe, re.M):
            force = (
                "# --- LUXURY_STATE_NAME_FORCE (auto) ---\n"
                "import state as _lux_state_mod\n"
                "state = _lux_state_mod\n"
                "# --- end LUXURY_STATE_NAME_FORCE ---\n"
            )
            src_safe = re.sub(r"^(state\.engine\s*=)", force + r"\1", src_safe, count=1, flags=re.M)
        ast.parse(src_safe)
        path.write_text(src_safe, encoding="utf-8")
        print("WROTE harden-only (softwrap skipped)", path)
        return

    if src3 != original:
        path.write_text(src3, encoding="utf-8")
        print("WROTE", path, path.stat().st_size)
    else:
        print("unchanged", path)


bacbo = ROOT / "bacbo_royal_complete.py"
text = bacbo.read_text(encoding="utf-8", errors="replace") if bacbo.exists() else ""
for i, ln in enumerate(text.splitlines()):
    if "Bot crashed (attempt" in ln or "Reconnect failed" in ln or "after 3 attempts" in ln:
        lines = text.splitlines()
        a, b = max(0, i - 10), min(len(lines), i + 8)
        print(f"----- context {bacbo.name}:{a+1}-{b} -----")
        for j in range(a, b):
            print(f"{j+1}: {lines[j][:160]}")
        print()

ensure_harden_and_soft(bacbo)
wd = ROOT / "bot" / "watchdog.py"
if wd.exists():
    ensure_harden_and_soft(wd)
    print("patched watchdog.py")
else:
    print("no bot/watchdog.py")

for p in sorted((ROOT / "bot").glob("*.py")):
    t = p.read_text(encoding="utf-8", errors="replace")
    if p.name == "watchdog.py":
        continue
    if "[CrashGuard] Bot crashed" in t or "[Watchdog] Reconnect failed" in t:
        ensure_harden_and_soft(p)
PY

echo "========== [4/6] restart bacbo ONLY (FALLBACKS_ENABLED=0) =========="
set -a
source ./luxury_building.env 2>/dev/null || true
set +a
export TELEGRAM_SESSION_STRING="$(tr -d '\n' < .telegram_session_string)"
export TELEGRAM_TARGET_PEER="${TELEGRAM_TARGET_PEER:-6774605259}"
export FALLBACKS_ENABLED=0
export FALLBACK_START_DELAY_SECS=999999
export EDGE_POLICY_MODE=luxury
export EDGE_LUXURY_FLOOR_GATE=1
export FALLBACK_SEND_BLOCKED=0
export BOT_TZ=America/Sao_Paulo
export PYTHONPATH="/home/runner/workspace/bot:/home/runner/workspace:${PYTHONPATH:-}"

echo "===== DB_LOCK_FIX_V2 marker $(date -u +%Y-%m-%dT%H:%M:%SZ) =====" >> logs/bot_live.log

nohup env EDGE_POLICY_MODE=luxury EDGE_LUXURY_FLOOR_GATE=1 FALLBACKS_ENABLED=0 \
  FALLBACK_START_DELAY_SECS=999999 FALLBACK_SEND_BLOCKED=0 \
  BOT_TZ=America/Sao_Paulo \
  TELEGRAM_SESSION_STRING="$TELEGRAM_SESSION_STRING" \
  TELEGRAM_TARGET_PEER="$TELEGRAM_TARGET_PEER" \
  PYTHONPATH="$PYTHONPATH" \
  python3 -u bot/runtime_supervisor.py > /tmp/luxury_supervisor.log 2>&1 &
echo "supervisor pid=$!"

echo "========== [5/6] settle 100s =========="
sleep 25
echo "----- 25s -----"
pgrep -af 'runtime_supervisor|bacbo_royal|fallback_signal|fallback_result' || true
grep -E 'sqlite harden|soft DB lock|run_forever|NameError|database is locked|CrashGuard|SEQUENCE/FIRED|EdgePolicy|ALLOW' logs/bot_live.log | tail -n 40 || true
sleep 45
echo "----- 70s -----"
pgrep -af 'runtime_supervisor|bacbo_royal|fallback_signal|fallback_result' || true
sleep 35

echo "========== [6/6] verdict =========="
$PY <<'PY'
from pathlib import Path
import re, subprocess, sqlite3

log = Path("logs/bot_live.log").read_text(errors="ignore")
idx = log.rfind("===== DB_LOCK_FIX_V2 marker")
chunk = log[idx:] if idx >= 0 else log[-12000:]
locks = len(re.findall(r"database is locked", chunk))
crashes = len(re.findall(r"\[CrashGuard\] Bot crashed", chunk))
soft = len(re.findall(r"soft DB lock", chunk))
run_ok = "run_forever" in chunk
harden = "sqlite harden applied" in chunk
nameerr = "NameError: name 'state'" in chunk
fired = len(re.findall(r"FIRED|EdgePolicy.*ALLOW|SEQUENCE/FIRED", chunk))
print("post_fix_run_forever", run_ok)
print("post_fix_sqlite_harden", harden)
print("post_fix_state_NameError", nameerr)
print("post_fix_database_is_locked_count", locks)
print("post_fix_crashguard_bot_crashed_count", crashes)
print("post_fix_soft_dblock_count", soft)
print("post_fix_fire_or_allow_hits", fired)
print("--- procs ---")
print(subprocess.getoutput("pgrep -af 'runtime_supervisor|bacbo_royal|fallback_signal|fallback_result' || echo NONE"))
print("--- last 30 ---")
print("\n".join(Path("logs/bot_live.log").read_text(errors="ignore").splitlines()[-30:]))
db = Path("bot/bacbo.db")
con = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=30)
print("journal_mode", con.execute("PRAGMA journal_mode").fetchone()[0])
con.close()
has_fb = bool(subprocess.getoutput("pgrep -af fallback_signal || true").strip())
if run_ok and not nameerr and crashes == 0 and not has_fb:
    print("VERDICT: OK — bacbo-only, no CrashGuard reconnect storm")
elif run_ok and crashes == 0:
    print("VERDICT: MOSTLY_OK — check locks/soft")
else:
    print("VERDICT: STILL_BAD — paste ALL output")
PY

echo
echo "DONE. Paste ALL output."
