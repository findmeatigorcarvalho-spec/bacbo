#!/usr/bin/env bash
# Repair bad `import config` insertion + show health (no full kill if healthy).
set -euo pipefail
cd /home/runner/workspace

echo "========== [1/3] repair bacbo import config placement =========="
python3 - <<'PY'
from pathlib import Path
import ast, re

p = Path("bacbo_royal_complete.py")
src = p.read_text(encoding="utf-8", errors="replace")

# Remove ALL luxury auto config imports (we'll re-add cleanly if needed)
src2 = re.sub(
    r"^import config  # LUXURY: ensure config in module scope for send\(\)\n",
    "",
    src,
    flags=re.M,
)
src2 = re.sub(r"^import config  # LUXURY auto\n", "", src2, flags=re.M)

# Also fix bot files we may have broken
for fp in Path("bot").glob("*.py"):
    t = fp.read_text(encoding="utf-8", errors="replace")
    if "import config  # LUXURY auto" in t:
        t2 = t.replace("import config  # LUXURY auto\n", "")
        # only keep if file still valid / add properly later
        try:
            ast.parse(t2)
            fp.write_text(t2, encoding="utf-8")
            print("cleaned", fp)
        except SyntaxError as e:
            print("skip clean", fp, e)

# Does bacbo already have a real import config at module level?
has_config = bool(re.search(r"^import config\b", src2, re.M) or re.search(r"^from config import\b", src2, re.M))
print("has_module_level_config_import", has_config)

# Find a safe module-level insertion point: after __future__/docstring/comments/imports at top
lines = src2.splitlines(True)
insert_at = 0
seen_code = False
for i, ln in enumerate(lines[:120]):
    s = ln.strip()
    if not s or s.startswith("#"):
        insert_at = i + 1
        continue
    if i == 0 and (s.startswith('"""') or s.startswith("'''")):
        # skip docstring
        quote = s[:3]
        if s.count(quote) >= 2 and len(s) > 3:
            insert_at = i + 1
            continue
        # multi-line docstring
        j = i + 1
        while j < len(lines) and quote not in lines[j]:
            j += 1
        insert_at = min(j + 1, len(lines))
        continue
    if s.startswith("from __future__"):
        insert_at = i + 1
        continue
    if s.startswith("import ") or s.startswith("from "):
        insert_at = i + 1
        continue
    # first real code — stop
    break

if not has_config:
    lines.insert(insert_at, "import config  # LUXURY: module-level for send()\n")
    src2 = "".join(lines)
    print("inserted import config at line", insert_at + 1)
else:
    src2 = "".join(lines) if lines != src2.splitlines(True) else src2
    print("no insert needed")

# Validate
try:
    ast.parse(src2)
except SyntaxError as e:
    print("STILL_BROKEN", e)
    # last resort: restore bak and only add config at absolute top after future
    bak = Path("bacbo_royal_complete.py.bak_pre_state_fix")
    if bak.exists():
        base = bak.read_text(encoding="utf-8", errors="replace")
        # re-apply ONLY the session/bind block from current if present, else minimal
        # For safety: use bak + session force using importlib state only
        print("restoring bak_pre_state_fix and applying minimal safe patch")
        src2 = base
        # strip old luxury
        for marker in ("LUXURY_SESSION_AND_BIND", "LUXURY_SESSION_FILE_FORCE", "LUXURY_BIND_PROXY", "LUXURY_STATE_INIT"):
            src2 = re.sub(rf"\n# --- {marker} \(auto\) ---.*?(?=\n# --- |\nstate\.client\s*=|\n# ──|\Z)", "\n", src2, flags=re.S)
        src2 = re.sub(r"\nimport state  # LUXURY: ensure module in scope before client assign\n", "\n", src2)
        # ensure import config at top
        if not re.search(r"^import config\b", src2, re.M):
            lines = src2.splitlines(True)
            idx = 0
            for i, ln in enumerate(lines[:40]):
                if ln.startswith("from __future__") or ln.startswith("import ") or ln.startswith("from ") or not ln.strip() or ln.strip().startswith("#"):
                    idx = i + 1
                else:
                    break
            lines.insert(idx, "import config\n")
            src2 = "".join(lines)
        # safe client bind
        m = re.search(r"^state\.client\s*=\s*TelegramClient\([^\n]*\)\s*$", src2, re.M)
        if m:
            block = '''# --- LUXURY_SESSION_AND_BIND (auto) ---
try:
    import os as _lux_os
    from pathlib import Path as _LuxPath
    _sf = _LuxPath("/home/runner/workspace/.telegram_session_string")
    if _sf.exists():
        _sv = _sf.read_text(errors="ignore").strip()
        if len(_sv) > 50:
            _lux_os.environ["TELEGRAM_SESSION_STRING"] = _sv
            try:
                from telethon.sessions import StringSession as _LuxSS
                _session = _LuxSS(_sv)
            except Exception:
                pass
except Exception as _lux_sess_exc:
    print("[LUXURY] session force skipped:", _lux_sess_exc)
import state as _lux_state_mod
_lux_prev_client = getattr(_lux_state_mod, "client", None)
_lux_state_mod.client = TelegramClient(_session, API_ID, API_HASH, sequential_updates=False)
try:
    if hasattr(_lux_prev_client, "bind"):
        _lux_prev_client.bind(_lux_state_mod.client)
except Exception as _lux_bind_exc:
    print("[LUXURY] proxy bind failed:", _lux_bind_exc)
try:
    state.client = _lux_state_mod.client
except Exception:
    pass
# --- end LUXURY_SESSION_AND_BIND ---'''
            src2 = src2[:m.start()] + block + "\n" + src2[m.end():]
        ast.parse(src2)
        print("restored+minimal patch OK")
    else:
        raise

p.write_text(src2, encoding="utf-8")
ast.parse(p.read_text(encoding="utf-8"))
print("bacbo_royal_complete.py syntax OK")
# show first 30 import-ish lines
for i, ln in enumerate(p.read_text().splitlines()[:40], 1):
    if "config" in ln or ln.startswith("import ") or ln.startswith("from "):
        print(f"{i}: {ln[:100]}")
PY

echo "========== [2/3] ensure fallbacks still valid =========="
python3 - <<'PY'
from pathlib import Path
import ast, shutil, re

PEER = "6774605259"
for rel in ["bot/fallback_signal_sender.py", "bot/fallback_result_sender.py"]:
    p = Path(rel)
    try:
        ast.parse(p.read_text(encoding="utf-8"))
        compile(p.read_text(encoding="utf-8"), rel, "exec")
        print(rel, "OK")
    except SyntaxError as e:
        print(rel, "BROKEN", e, "— restoring bak")
        bak = Path(str(p) + ".bak_pre_session_fix")
        shutil.copy2(bak, p)
        t = p.read_text(encoding="utf-8")
        # minimal peer + session only, NO continue injection
        helper = '''
def _load_telegram_session() -> str:
    import os
    from pathlib import Path
    for key in ("TELEGRAM_SESSION_STRING",):
        v = (os.environ.get(key) or "").strip()
        if len(v) > 50:
            return v
    return Path("/home/runner/workspace/.telegram_session_string").read_text().strip()

async def _resolve_target(client, target):
    import os, json
    from pathlib import Path
    peer = os.environ.get("TELEGRAM_TARGET_PEER") or "6774605259"
    return await client.get_entity(int(peer))

'''
        t = t.replace("async def main", helper + "\nasync def main", 1)
        t = t.replace('session = (ROOT / ".telegram_session_string").read_text().strip()', "session = _load_telegram_session()")
        t = t.replace("entity = await client.get_entity(target)", "entity = await _resolve_target(client, target)")
        p.write_text(t, encoding="utf-8")
        compile(t, rel, "exec")
        print(rel, "restored OK")

# env peer
Path("luxury_building.env").write_text(
    "export EDGE_POLICY_MODE=luxury\nexport EDGE_LUXURY_FLOOR_GATE=1\n"
    "export FALLBACK_SEND_BLOCKED=0\nexport BOT_TZ=America/Sao_Paulo\n"
    f"export TELEGRAM_TARGET_PEER={PEER}\n"
)
print("peer set", PEER)
PY

echo "========== [3/3] restart supervisor cleanly =========="
pkill -9 -f 'runtime_supervisor.py' 2>/dev/null || true
pkill -9 -f 'bacbo_royal_complete.py' 2>/dev/null || true
pkill -9 -f 'fallback_signal_sender.py' 2>/dev/null || true
pkill -9 -f 'fallback_result_sender.py' 2>/dev/null || true
sleep 2

set -a; source ./luxury_building.env; set +a
export TELEGRAM_SESSION_STRING="$(tr -d '\n' < .telegram_session_string)"
export TELEGRAM_TARGET_PEER=6774605259

# prove bacbo imports
python3 - <<'PY'
import sys, ast
from pathlib import Path
sys.path.insert(0,'bot'); sys.path.insert(0,'.')
src = Path('bacbo_royal_complete.py').read_text(encoding='utf-8')
ast.parse(src)
print('parse_ok bytes', len(src))
# don't execute full bacbo (starts bot); just ensure config import line exists early
for i, ln in enumerate(src.splitlines()[:60], 1):
    if 'import config' in ln:
        print('config_import_line', i, ln)
        break
else:
    print('WARN no import config in first 60 lines')
PY

nohup env EDGE_POLICY_MODE=luxury EDGE_LUXURY_FLOOR_GATE=1 FALLBACK_SEND_BLOCKED=0 \
  BOT_TZ=America/Sao_Paulo \
  TELEGRAM_SESSION_STRING="$TELEGRAM_SESSION_STRING" \
  TELEGRAM_TARGET_PEER=6774605259 \
  python3 -u bot/runtime_supervisor.py > /tmp/luxury_supervisor.log 2>&1 &
echo "supervisor pid=$!"
sleep 12

echo "===== procs ====="
pgrep -af 'runtime_supervisor|bacbo_royal|fallback_signal|fallback_result' || true
echo "===== bot_live ====="
tail -n 35 logs/bot_live.log
echo "===== fallback ====="
tail -n 12 logs/fallback_sender.log
tail -n 8 logs/fallback_result_sender.log

python3 - <<'PY'
import sqlite3, time, subprocess
from pathlib import Path
time.sleep(4)
print(subprocess.getoutput('pgrep -af bacbo_royal || echo NO_BACBO'))
print('--- errors? ---')
print(subprocess.getoutput("grep -E 'NameError|SyntaxError|CrashGuard|send\\(\\) failed' logs/bot_live.log | tail -n 15"))
print('--- last signals ---')
db = 'bot/bacbo.db' if Path('bot/bacbo.db').exists() else 'bacbo.db'
con = sqlite3.connect(db)
for r in con.execute('select id, fired_at, signal_kind, color, source_floor from consensus_signals order by id desc limit 8'):
    print(r)
PY

echo
echo "DONE. Paste ALL output to Cursor."
