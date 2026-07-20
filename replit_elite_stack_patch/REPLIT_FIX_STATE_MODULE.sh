#!/usr/bin/env bash
# CRITICAL: commands.py uses `import state` (bot/state.py module).
# Our _LuxBotState shadowed it — client was set on the wrong object.
set -euo pipefail
cd /home/runner/workspace

echo "========== [1/5] restore bacbo_royal_complete.py from pre-state-fix backup =========="
python3 - <<'PY'
from pathlib import Path
import re, ast, shutil

p = Path("bacbo_royal_complete.py")
bak = Path("bacbo_royal_complete.py.bak_pre_state_fix")
if not bak.exists():
    raise SystemExit("MISSING backup bacbo_royal_complete.py.bak_pre_state_fix")

# Keep a copy of the broken current for forensics
Path("bacbo_royal_complete.py.bak_broken_luxstate").write_bytes(p.read_bytes())
shutil.copy2(bak, p)
src = p.read_text(encoding="utf-8", errors="replace")

# Strip ANY leftover luxury state class injections if backup somehow had them
src = re.sub(r"\nclass _LuxBotState:.*?\nstate = _LuxBotState\(\)\n+", "\n", src, flags=re.S)
src = re.sub(r"\n# --- LUXURY_STATE_INIT \(auto\) ---.*?(?=\n# --- |\nstate\.client\s*=|\n# ──|\Z)", "\n", src, flags=re.S)
src = re.sub(r"\n# --- LUXURY_COMMANDS_GUARD \(auto\) ---.*?(?=\nimport |\n# --- |\Z)", "\n", src, flags=re.S)

# Ensure session force exists (safe) without shadowing state module
if "LUXURY_SESSION_FILE_FORCE" not in src:
    m = re.search(r"^state\.client\s*=\s*TelegramClient\(", src, re.M)
    if not m:
        raise SystemExit("backup missing state.client = TelegramClient — unexpected")
    force = '''
# --- LUXURY_SESSION_FILE_FORCE (auto) ---
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

'''
    src = src[: m.start()] + force + src[m.start():]

# Verify no local `state =` shadows the module before client assign
before = src.split("state.client = TelegramClient")[0]
shadows = re.findall(r"^(state\s*=\s*.+)$", before, re.M)
print("shadow_assigns_before_client", shadows[:10])
if shadows:
    # remove only our lux ones; if real code assigns state, print warning
    for s in shadows:
        if "_LuxBotState" in s or "SimpleNamespace" in s:
            src = src.replace(s + "\n", "\n")
            print("removed shadow", s)

# Must have `import state` somewhere
if not re.search(r"^import state\b", src, re.M) and not re.search(r"^from state import\b", src, re.M):
    # insert near top after other imports
    lines = src.splitlines(True)
    idx = 0
    for i, ln in enumerate(lines[:100]):
        if ln.startswith("import ") or ln.startswith("from "):
            idx = i + 1
    lines.insert(idx, "import state\n")
    src = "".join(lines)
    print("inserted import state")

p.write_text(src, encoding="utf-8")
ast.parse(src)
print("bacbo restored+session-force OK; has import state:", bool(re.search(r"^import state\b", src, re.M)))
# show lines around client assign
for i, ln in enumerate(src.splitlines(), 1):
    if "state.client = TelegramClient" in ln:
        for j in range(max(1, i-8), min(len(src.splitlines()), i+3)+1):
            print(f"{j}: {src.splitlines()[j-1][:140]}")
        break
PY

echo "========== [2/5] fix bot/state.py client proxy (for import-time decorators) =========="
python3 - <<'PY'
from pathlib import Path
import ast, re

# locate state module
candidates = [Path("bot/state.py"), Path("state.py")]
sp = next((p for p in candidates if p.exists()), None)
if sp is None:
    raise SystemExit("MISSING state.py module")
print("state_module", sp)
src = sp.read_text(encoding="utf-8", errors="replace")
bak = sp.with_suffix(".py.bak_pre_proxy")
if not bak.exists():
    bak.write_text(src, encoding="utf-8")

if "LUXURY_CLIENT_PROXY" not in src:
    proxy = '''
# --- LUXURY_CLIENT_PROXY (auto) ---
class _LuxClientProxy:
    """Placeholder so @state.client.on works before TelegramClient is assigned."""
    def __init__(self):
        self._client = None
        self._pending = []  # (event, func)

    def bind(self, client):
        self._client = client
        pending = list(self._pending)
        self._pending.clear()
        for event, func in pending:
            try:
                client.add_event_handler(func, event)
            except Exception as e:
                print("[LUXURY] pending handler bind failed:", e)
        return client

    def on(self, event):
        def deco(func):
            if self._client is not None:
                self._client.add_event_handler(func, event)
            else:
                self._pending.append((event, func))
            return func
        return deco

    def __bool__(self):
        return self._client is not None

    def __getattr__(self, name):
        if name in ("_client", "_pending", "bind", "on"):
            raise AttributeError(name)
        if self._client is None:
            raise AttributeError(f"Telegram client not ready yet (getattr {name})")
        return getattr(self._client, name)

# Install proxy if client missing/None
try:
    client
except NameError:
    client = None
if client is None or not hasattr(client, "on"):
    client = _LuxClientProxy()
# --- end LUXURY_CLIENT_PROXY ---
'''
    # Insert near end of module OR after `client = None` assignment
    if re.search(r"^client\s*=\s*None\s*$", src, re.M):
        src = re.sub(r"^client\s*=\s*None\s*$", "client = None\n" + proxy + "\nif client is None or not hasattr(client, 'on'):\n    client = _LuxClientProxy()\n", src, count=1, flags=re.M)
        # Avoid double-assign — cleaner approach: replace client=None with proxy init
        # Re-read and do cleaner
        src = bak.read_text(encoding="utf-8")
        src = re.sub(
            r"^client\s*=\s*None\s*$",
            "client = None  # set by bacbo_royal_complete\n" + proxy,
            src,
            count=1,
            flags=re.M,
        )
    else:
        # append proxy + ensure client exists
        src = src.rstrip() + "\n" + proxy + "\n"
        if not re.search(r"^client\s*=", src, re.M):
            src += "\nclient = _LuxClientProxy()\n"

    sp.write_text(src, encoding="utf-8")
    ast.parse(src)
    print("patched", sp)
else:
    print("proxy already in", sp)

# Show client-related lines
for i, ln in enumerate(sp.read_text().splitlines(), 1):
    if "client" in ln.lower() and i < 80:
        print(f"{i}: {ln[:140]}")
PY

echo "========== [3/5] restore/fix commands.py + bind proxy on client assign =========="
python3 - <<'PY'
from pathlib import Path
import re, ast

# Restore commands from backup if our defer patch is messy; then apply clean fix
cmd = Path("bot/commands.py")
bak = Path("bot/commands.py.bak_pre_client_fix")
if bak.exists():
    cmd.write_text(bak.read_text(encoding="utf-8"), encoding="utf-8")
    print("restored commands.py from bak_pre_client_fix")

src = cmd.read_text(encoding="utf-8", errors="replace")
# With state.client as proxy, @state.client.on works at import — no commands change needed
# But ensure register_commands / bacbo binds proxy when real client assigned

# Patch bacbo so after state.client = TelegramClient(...), bind pending handlers
bacbo = Path("bacbo_royal_complete.py")
bsrc = bacbo.read_text(encoding="utf-8", errors="replace")
if "LUXURY_BIND_PROXY" not in bsrc:
    # After `state.client = TelegramClient(...)` line, bind if proxy
    # The assignment replaces proxy — so we need to CAPTURE pending first
    # Better: wrap assignment
    old = None
    m = re.search(r"^(state\.client\s*=\s*TelegramClient\([^\n]+)\n", bsrc, re.M)
    if not m:
        # multiline assign?
        m = re.search(r"^(state\.client\s*=\s*TelegramClient\([\s\S]*?\))\s*\n", bsrc, re.M)
    if m:
        replacement = (
            "# --- LUXURY_BIND_PROXY (auto) ---\n"
            "_lux_prev_client = getattr(state, 'client', None)\n"
            f"{m.group(1) if m.lastindex else m.group(0).rstrip()}\n"
            "try:\n"
            "    if hasattr(_lux_prev_client, 'bind') and hasattr(_lux_prev_client, '_pending'):\n"
            "        _lux_prev_client.bind(state.client)\n"
            "except Exception as _lux_bind_exc:\n"
            "    print('[LUXURY] proxy bind failed:', _lux_bind_exc)\n"
        )
        # cleaner explicit
        block = '''# --- LUXURY_BIND_PROXY (auto) ---
_lux_prev_client = getattr(state, "client", None)
state.client = TelegramClient(_session, API_ID, API_HASH, sequential_updates=False)
try:
    if hasattr(_lux_prev_client, "bind"):
        _lux_prev_client.bind(state.client)
except Exception as _lux_bind_exc:
    print("[LUXURY] proxy bind failed:", _lux_bind_exc)
'''
        # replace only the single assignment line
        bsrc2 = re.sub(
            r"^state\.client\s*=\s*TelegramClient\([^\n]*\)\s*$",
            block.rstrip(),
            bsrc,
            count=1,
            flags=re.M,
        )
        if bsrc2 == bsrc:
            print("WARN: could not wrap state.client assignment")
        else:
            bsrc = bsrc2
            bacbo.write_text(bsrc, encoding="utf-8")
            print("wrapped state.client assignment with proxy bind")
    else:
        print("WARN: state.client assignment not found for bind wrap")
ast.parse(bacbo.read_text(encoding="utf-8"))
ast.parse(cmd.read_text(encoding="utf-8"))
print("syntax OK bacbo+commands")
PY

echo "========== [4/5] fix fallback senders (syntax + use peer id) =========="
python3 - <<'PY'
from pathlib import Path
import re, ast, shutil

PEER = "6774605259"
# write peer into env files
for envp in [Path(".env"), Path("luxury_building.env")]:
    if envp.exists():
        lines = [ln for ln in envp.read_text().splitlines() if not ln.startswith("TELEGRAM_TARGET_PEER=") and not ln.startswith("export TELEGRAM_TARGET_PEER=")]
    else:
        lines = []
    if envp.name.endswith(".env") and "luxury" in envp.name:
        lines.append(f"export TELEGRAM_TARGET_PEER={PEER}")
    else:
        lines.append(f"TELEGRAM_TARGET_PEER={PEER}")
    # luxury_building.env should use export
    if envp.name == "luxury_building.env":
        lines = [ln for ln in lines if "TELEGRAM_TARGET_PEER" not in ln]
        lines += [
            "export EDGE_POLICY_MODE=luxury",
            "export EDGE_LUXURY_FLOOR_GATE=1",
            "export FALLBACK_SEND_BLOCKED=0",
            "export BOT_TZ=America/Sao_Paulo",
            f"export TELEGRAM_TARGET_PEER={PEER}",
        ]
    envp.write_text("\n".join(lines) + "\n", encoding="utf-8")
print("TELEGRAM_TARGET_PEER", PEER)

for rel in ["bot/fallback_signal_sender.py", "bot/fallback_result_sender.py"]:
    p = Path(rel)
    # Prefer bak before our broken flood patch
    for bakn in [p.with_suffix(".py.bak_pre_session_fix"), Path(str(p)+".bak_pre_session_fix")]:
        pass
    baks = sorted(Path("bot").glob(p.name + ".bak*"))
    print(rel, "backups", [b.name for b in baks])

    # Start from current and fix syntax: remove bad `continue` not in loop
    t = p.read_text(encoding="utf-8", errors="replace")
    # Remove LUXURY_FLOOD_BACKOFF broken injections
    t = re.sub(r"\n# --- LUXURY_FLOOD_BACKOFF \(auto\) ---.*?(?=\nasync def |\nDef |\ndef |\n# --- |\Z)", "\n", t, flags=re.S)
    # Remove orphan continue lines we may have inserted after prints
    t = re.sub(
        r'(print\(f?"\[Fallback[^\n]+\)\n)([ \t]+)if e\.__class__\.__name__ == \'FloodWaitError\'[^\n]+\n([ \t]+)await _lux_sleep_flood[^\n]+\n([ \t]+)continue\n',
        r'\1',
        t,
    )
    t = re.sub(
        r"([ \t]+)if e\.__class__\.__name__ == 'FloodWaitError'[^\n]+\n([ \t]+)await _lux_sleep_flood[^\n]+\n([ \t]+)continue\n",
        "",
        t,
    )
    # Ensure _resolve_target exists and uses peer; ensure call site
    if "_resolve_target" not in t:
        helper = '''
async def _resolve_target(client, target):
    import os, json
    from pathlib import Path
    cache = Path(__file__).resolve().parent / "data" / "telegram_target_entity.json"
    peer = os.environ.get("TELEGRAM_TARGET_PEER") or os.environ.get("TARGET_PEER_ID")
    if peer and str(peer).lstrip("-").isdigit():
        return await client.get_entity(int(peer))
    if cache.exists():
        try:
            data = json.loads(cache.read_text())
            if data.get("id") is not None:
                return await client.get_entity(int(data["id"]))
        except Exception:
            pass
    if isinstance(target, int) or (isinstance(target, str) and str(target).lstrip("-").isdigit()):
        return await client.get_entity(int(target))
    # dialogs scan — never ResolveUsername while flooded
    tnorm = str(target).lstrip("@").lower()
    async for d in client.iter_dialogs():
        ent = d.entity
        uname = (getattr(ent, "username", None) or "").lower()
        if uname == tnorm:
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(json.dumps({"target": str(target), "id": int(ent.id)}))
            return ent
    raise RuntimeError(f"Cannot resolve target {target} without ResolveUsername; set TELEGRAM_TARGET_PEER")
'''
        t = t.replace("async def main", helper + "\nasync def main", 1)
    t = t.replace("entity = await client.get_entity(target)", "entity = await _resolve_target(client, target)")

    # Proper flood backoff INSIDE the while True loop's except
    if "LUXURY_FLOOD_BACKOFF" not in t:
        # add helper function
        flood_helper = '''
# --- LUXURY_FLOOD_BACKOFF (auto) ---
import asyncio as _lux_asyncio
async def _lux_sleep_flood(err, label="fallback"):
    secs = int(getattr(err, "seconds", 0) or 0)
    sleep_for = min(max(secs, 1), 900)
    print(f"[{label}] FloodWait {secs}s — sleeping {sleep_for}s (capped)")
    await _lux_asyncio.sleep(sleep_for)
'''
        if "async def _resolve_target" in t:
            t = t.replace("async def _resolve_target", flood_helper + "\nasync def _resolve_target", 1)
        else:
            t = t.replace("async def main", flood_helper + "\nasync def main", 1)

    # Patch except Exception blocks that are inside while True to sleep on flood
    # Look for pattern in result sender
    t2 = t
    # Only add if not present
    if "await _lux_sleep_flood" not in t:
        t2 = re.sub(
            r"(except Exception as (\w+):\n)([ \t]+)(print\([^\n]*Fallback[^\n]*\n)",
            r"\1\3\4\3if 'FloodWait' in type(\2).__name__:\n\3    await _lux_sleep_flood(\2)\n\3    continue\n",
            t2,
            count=3,
        )
    t = t2

    p.write_text(t, encoding="utf-8")
    try:
        ast.parse(t)
        print(rel, "syntax OK")
    except SyntaxError as e:
        print(rel, "SYNTAX FAIL", e)
        # last resort: restore from bak_pre_session_fix and re-apply minimal peer resolve only
        bak = Path(str(p) + ".bak_pre_session_fix")
        if not bak.exists():
            bak = Path("bot") / (p.name + ".bak_pre_session_fix")
        if bak.exists():
            t = bak.read_text(encoding="utf-8")
            # minimal patch
            if "_load_telegram_session" not in t:
                pass
            helper = '''
async def _resolve_target(client, target):
    import os, json
    from pathlib import Path
    peer = os.environ.get("TELEGRAM_TARGET_PEER")
    if peer and str(peer).lstrip("-").isdigit():
        return await client.get_entity(int(peer))
    cache = Path(__file__).resolve().parent / "data" / "telegram_target_entity.json"
    if cache.exists():
        data = json.loads(cache.read_text()); return await client.get_entity(int(data["id"]))
    raise RuntimeError("set TELEGRAM_TARGET_PEER")
'''
            t = t.replace("async def main", helper + "\nasync def main", 1)
            t = t.replace("entity = await client.get_entity(target)", "entity = await _resolve_target(client, target)")
            if "session = (ROOT / \".telegram_session_string\").read_text().strip()" in t:
                # add loader
                load = '''
def _load_telegram_session() -> str:
    import os
    from pathlib import Path
    for key in ("TELEGRAM_SESSION_STRING",):
        v=(os.environ.get(key) or "").strip()
        if len(v)>50: return v
    p=Path("/home/runner/workspace/.telegram_session_string")
    return p.read_text().strip()
'''
                t = t.replace("async def main", load + "\nasync def main", 1)
                t = t.replace('session = (ROOT / ".telegram_session_string").read_text().strip()', "session = _load_telegram_session()")
            p.write_text(t, encoding="utf-8")
            ast.parse(t)
            print(rel, "restored from bak + minimal peer fix OK")
        else:
            raise
PY

echo "========== [5/5] restart + verify =========="
set -a
source ./luxury_building.env
set +a
export TELEGRAM_SESSION_STRING="$(tr -d '\n' < .telegram_session_string)"
export TELEGRAM_TARGET_PEER="${TELEGRAM_TARGET_PEER:-6774605259}"
echo "SESSION_LEN=${#TELEGRAM_SESSION_STRING} PEER=$TELEGRAM_TARGET_PEER MODE=$EDGE_POLICY_MODE"

pkill -f 'runtime_supervisor.py' 2>/dev/null || true
pkill -f 'bacbo_royal_complete.py' 2>/dev/null || true
pkill -f 'fallback_signal_sender.py' 2>/dev/null || true
pkill -f 'fallback_result_sender.py' 2>/dev/null || true
sleep 2

nohup env EDGE_POLICY_MODE=luxury EDGE_LUXURY_FLOOR_GATE=1 FALLBACK_SEND_BLOCKED=0 \
  BOT_TZ=America/Sao_Paulo \
  TELEGRAM_SESSION_STRING="$TELEGRAM_SESSION_STRING" \
  TELEGRAM_TARGET_PEER="$TELEGRAM_TARGET_PEER" \
  python3 -u bot/runtime_supervisor.py > /tmp/luxury_supervisor.log 2>&1 &
echo "supervisor pid=$!"
sleep 10

echo "===== procs ====="
pgrep -af 'runtime_supervisor|bacbo_royal|fallback_signal|fallback_result' || true
echo "===== bot_live tail ====="
tail -n 50 logs/bot_live.log
echo "===== fallback_sender tail ====="
tail -n 25 logs/fallback_sender.log
echo "===== fallback_result tail ====="
tail -n 20 logs/fallback_result_sender.log

python3 - <<'PY'
import ast, time, subprocess
from pathlib import Path
ast.parse(Path('bacbo_royal_complete.py').read_text(encoding='utf-8'))
ast.parse(Path('bot/state.py').read_text(encoding='utf-8'))
ast.parse(Path('bot/commands.py').read_text(encoding='utf-8'))
ast.parse(Path('bot/fallback_signal_sender.py').read_text(encoding='utf-8'))
ast.parse(Path('bot/fallback_result_sender.py').read_text(encoding='utf-8'))
print('all_syntax_ok')
# confirm state module client is proxy-capable
import sys
sys.path.insert(0,'bot')
import importlib
if 'state' in sys.modules: del sys.modules['state']
import state
print('state.client type', type(state.client), 'has_on', hasattr(state.client,'on'), 'has_bind', hasattr(state.client,'bind'))
time.sleep(6)
print(subprocess.getoutput('pgrep -af bacbo_royal || echo NO_BACBO'))
print('--- last bot lines ---')
print(subprocess.getoutput('tail -n 20 logs/bot_live.log'))
PY

echo
echo "DONE. Paste ALL output to Cursor."
