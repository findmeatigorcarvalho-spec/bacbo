#!/usr/bin/env bash
# Fix commands.py import-time state.client=None + fallback FloodWait backoff.
set -euo pipefail
cd /home/runner/workspace

echo "========== [1/6] inspect state + commands =========="
python3 - <<'PY'
from pathlib import Path
import re

bacbo = Path("bacbo_royal_complete.py")
cmd = Path("bot/commands.py")
src = bacbo.read_text(encoding="utf-8", errors="replace")
csrc = cmd.read_text(encoding="utf-8", errors="replace") if cmd.exists() else ""

print("--- state assignments in bacbo (first 30) ---")
for i, ln in enumerate(src.splitlines(), 1):
    if re.search(r"\bstate\s*=", ln) or re.search(r"class\s+\w+", ln) and "State" in ln:
        if i < 250 or "state =" in ln:
            print(f"{i}: {ln[:160]}")

print("--- commands.py how state is imported ---")
for i, ln in enumerate(csrc.splitlines()[:120], 1):
    if "state" in ln or "import" in ln or "@" in ln:
        print(f"{i}: {ln[:160]}")
PY

echo "========== [2/6] restore bacbo state init cleanly =========="
python3 - <<'PY'
from pathlib import Path
import re, ast

p = Path("bacbo_royal_complete.py")
src = p.read_text(encoding="utf-8", errors="replace")
# Prefer original backup if present
for bak_name in [
    "bacbo_royal_complete.py.bak_pre_state_fix",
    "bacbo_royal_complete.py.bak_pre_tz_fix",
]:
    bak = Path(bak_name)
    if bak.exists() and bak.stat().st_size > 10000:
        print("found backup", bak, "bytes", bak.stat().st_size)

# Strip prior auto-inject markers (session force re-added cleanly below)
for marker in ("LUXURY_STATE_INIT", "LUXURY_SESSION_FILE_FORCE", "LUXURY_COMMANDS_GUARD"):
    src = re.sub(
        rf"\n# --- {marker} \(auto\) ---.*?(?=\n# --- |\nstate\.client\s*=|\n# ──|\Z)",
        "\n",
        src,
        flags=re.S,
    )

# Also remove injected _LuxBotState class if present
src = re.sub(
    r"\nclass _LuxBotState:.*?state = _LuxBotState\(\)\n+",
    "\n",
    src,
    flags=re.S,
)

# Find an existing real state construction earlier in file
assigns = list(re.finditer(r"^(state\s*=\s*.+)$", src, re.M))
print("state_assign_count", len(assigns))
for m in assigns[:15]:
    line_no = src[:m.start()].count("\n") + 1
    print(f"  L{line_no}: {m.group(1)[:120]}")

# Find first state.client = TelegramClient
mclient = re.search(r"^state\.client\s*=\s*TelegramClient\(", src, re.M)
if not mclient:
    raise SystemExit("cannot find state.client = TelegramClient")

# Ensure there is a state object BEFORE client assignment
before = src[: mclient.start()]
if not re.search(r"^state\s*=\s*", before, re.M):
    # invent minimal state with attribute bag used by this bot
    init = '''
# --- LUXURY_STATE_INIT (auto) ---
class _LuxBotState:
    def __init__(self):
        self.client = None
        self.engine = None
        self.learner = None
        self._markov_engine = None
        self._color_markov = None
        self._room_tier_cache = {}
        self.me = None
        self.running = True

state = _LuxBotState()

'''
    src = before + init + src[mclient.start():]
    print("inserted fresh _LuxBotState before client assign")
else:
    print("state assignment already exists before client assign")

# Re-add session force immediately before client assign (after state exists)
if "LUXURY_SESSION_FILE_FORCE" not in src:
    mclient = re.search(r"^state\.client\s*=\s*TelegramClient\(", src, re.M)
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
    src = src[: mclient.start()] + force + src[mclient.start():]
    print("re-inserted session force")

# After client assign, assert client is not None before importing commands
if "LUXURY_COMMANDS_GUARD" not in src:
    # insert just before `import commands`
    mcmd = re.search(r"^(import commands)\s*$", src, re.M)
    if mcmd:
        guard = '''# --- LUXURY_COMMANDS_GUARD (auto) ---
if getattr(state, "client", None) is None:
    raise RuntimeError("state.client is None before import commands — session/client init failed")

'''
        src = src[: mcmd.start()] + guard + src[mcmd.start():]
        print("inserted commands guard")

Path("bacbo_royal_complete.py").write_text(src, encoding="utf-8")
ast.parse(src)
print("bacbo syntax OK")
PY

echo "========== [3/6] fix commands.py: defer @state.client.on decorators =========="
python3 - <<'PY'
from pathlib import Path
import re, ast

p = Path("bot/commands.py")
src = p.read_text(encoding="utf-8", errors="replace")
bak = p.with_suffix(".py.bak_pre_client_fix")
if not bak.exists():
    bak.write_text(src, encoding="utf-8")

# How is state imported?
print("state import lines:")
for ln in src.splitlines()[:80]:
    if "state" in ln and ("import" in ln or "=" in ln):
        print(" ", ln)

# Replace module-level @state.client.on(...) with deferred registration pattern
# Strategy: convert
#   @state.client.on(events.X(...))
#   async def foo(...):
# into storing callbacks and registering in register_commands(client)

if "LUXURY_DEFER_CLIENT_ON" in src:
    print("commands already deferred")
else:
    # Ensure we don't evaluate state.client at import
    # Common pattern in this file: from bacbo_royal_complete import state  OR import state
    # Soften: create a proxy that delays .on until client exists

    preamble = '''
# --- LUXURY_DEFER_CLIENT_ON (auto) ---
class _LuxClientProxy:
    """Allow @state.client.on at import time even before TelegramClient exists."""
    def __init__(self):
        self._client = None
        self._pending = []  # list[(args, kwargs, func)]

    def bind(self, client):
        self._client = client
        for args, kwargs, func in self._pending:
            client.add_event_handler(func, args[0] if args else kwargs.get("event"))
            # Telethon's .on decorator style: client.on(event)(func)
            # pending stores (event, func)
        # re-register properly
        pending = list(self._pending)
        self._pending.clear()
        for event, func in pending:
            client.add_event_handler(func, event)
        return client

    def on(self, event):
        def deco(func):
            if self._client is not None:
                self._client.add_event_handler(func, event)
            else:
                self._pending.append((event, func))
            return func
        return deco

    def __getattr__(self, name):
        if self._client is None:
            raise AttributeError(f"state.client not bound yet (asked {name})")
        return getattr(self._client, name)

def _lux_ensure_state_client_proxy():
    import sys
    # Find the state object used by this module
    st = globals().get("state")
    if st is None:
        # try common modules
        for modname in ("bacbo_royal_complete", "bot_state", "state", "app_state"):
            mod = sys.modules.get(modname)
            if mod is not None and hasattr(mod, "state"):
                st = getattr(mod, "state")
                globals()["state"] = st
                break
    if st is None:
        return
    client = getattr(st, "client", None)
    if isinstance(client, _LuxClientProxy):
        return
    proxy = _LuxClientProxy()
    if client is not None:
        proxy.bind(client)
    st.client = proxy

_lux_ensure_state_client_proxy()
# --- end LUXURY_DEFER_CLIENT_ON ---
'''

    # Insert preamble after imports / state import
    # Find last of the early import block containing state
    lines = src.splitlines(True)
    insert_at = 0
    for i, ln in enumerate(lines[:120]):
        if "import state" in ln or "from " in ln and "state" in ln or ln.startswith("state ="):
            insert_at = i + 1
        if "from telethon" in ln or "import events" in ln:
            insert_at = max(insert_at, i + 1)
    if insert_at == 0:
        # after first non-future import chunk
        for i, ln in enumerate(lines[:80]):
            if ln.startswith("import ") or ln.startswith("from "):
                insert_at = i + 1
    lines.insert(insert_at, preamble + "\n")
    src2 = "".join(lines)

    # Patch register_commands to bind real client into proxy
    if "def register_commands" in src2 and "LUXURY_BIND_CLIENT" not in src2:
        src2 = src2.replace(
            "def register_commands",
            "def register_commands",
            1,
        )
        src2 = re.sub(
            r"def register_commands\(([^)]*)\):\n",
            r"def register_commands(\1):\n"
            r"    # --- LUXURY_BIND_CLIENT (auto) ---\n"
            r"    try:\n"
            r"        _c = \1.split(',')[0].strip() if False else None\n"
            r"    except Exception:\n"
            r"        pass\n",
            src2,
            count=1,
        )
        # Better explicit patch:
        src2 = re.sub(
            r"(def register_commands\((\w+)\s*(?:,[^)]*)?\):\n)",
            (
                r"\1"
                r"    # --- LUXURY_BIND_CLIENT (auto) ---\n"
                r"    try:\n"
                r"        _proxy = getattr(state, 'client', None)\n"
                r"        if isinstance(_proxy, _LuxClientProxy):\n"
                r"            _proxy.bind(\2)\n"
                r"            state.client = \2\n"
                r"        elif getattr(state, 'client', None) is None:\n"
                r"            state.client = \2\n"
                r"    except Exception as _lux_bind_exc:\n"
                r"        print('[LUXURY] bind client failed', _lux_bind_exc)\n"
            ),
            src2,
            count=1,
        )

    p.write_text(src2, encoding="utf-8")
    try:
        ast.parse(src2)
        print("commands.py syntax OK")
    except SyntaxError as e:
        print("SYNTAX FAIL, restoring backup", e)
        p.write_text(bak.read_text(encoding="utf-8"), encoding="utf-8")
        raise

# Also: if decorators already evaluated against None, the proxy approach only works
# if proxy was installed BEFORE decorators. preamble is before decorators — good.
print("commands defer patch applied")
PY

echo "========== [4/6] fallback FloodWait backoff + cache @Mr_iv4 peer =========="
python3 - <<'PY'
from pathlib import Path
import re

# Patch both fallback senders: on FloodWait sleep; never tight-loop send
for rel in ["bot/fallback_signal_sender.py", "bot/fallback_result_sender.py"]:
    p = Path(rel)
    t = p.read_text(encoding="utf-8", errors="replace")
    if "LUXURY_FLOOD_BACKOFF" not in t:
        # wrap send paths: replace bare raise / print error loops
        # Add helper after imports
        helper = '''
# --- LUXURY_FLOOD_BACKOFF (auto) ---
import asyncio as _lux_asyncio
async def _lux_sleep_flood(err, label="fallback"):
    secs = int(getattr(err, "seconds", 0) or 0)
    # Cap single sleep so supervisor liveness continues; still avoid hammering.
    sleep_for = min(max(secs, 1), 900)
    print(f"[{label}] FloodWait {secs}s — sleeping {sleep_for}s")
    await _lux_asyncio.sleep(sleep_for)
'''
        if "async def main" in t:
            t = t.replace("async def main", helper + "\nasync def main", 1)
        # In error handlers, if FloodWaitError — sleep
        t = t.replace(
            "print(f\"[FallbackResultSender] error: {e!r}\")",
            "print(f\"[FallbackResultSender] error: {e!r}\")\n"
            "            if e.__class__.__name__ == 'FloodWaitError' or 'FloodWait' in e.__class__.__name__:\n"
            "                await _lux_sleep_flood(e, 'FallbackResultSender')\n"
            "                continue",
        )
        t = t.replace(
            "print(f\"[FallbackSender] error: {e!r}\")",
            "print(f\"[FallbackSender] error: {e!r}\")\n"
            "            if e.__class__.__name__ == 'FloodWaitError' or 'FloodWait' in e.__class__.__name__:\n"
            "                await _lux_sleep_flood(e, 'FallbackSender')\n"
            "                continue",
        )
        # generic except Exception as e blocks
        if "FloodWaitError" in t and "await _lux_sleep_flood" not in t:
            t = re.sub(
                r"except Exception as (e|err|ex):\n(\s+)print\(([^\n]+)\)",
                r"except Exception as \1:\n\2print(\3)\n\2if 'FloodWait' in type(\1).__name__:\n\2    await _lux_sleep_flood(\1)\n\2    continue",
                t,
                count=2,
            )
        p.write_text(t, encoding="utf-8")
        print("flood backoff patched", rel)
    else:
        print("already", rel)

# Try to resolve @Mr_iv4 via dialogs once and cache peer id (no ResolveUsername)
import asyncio, os, json, sys
sys.path.insert(0, "bot")
async def cache_peer():
    from pathlib import Path
    from telethon import TelegramClient
    from telethon.sessions import StringSession
    sess = Path(".telegram_session_string").read_text().strip()
    api_id = os.environ.get("TELEGRAM_API_ID")
    api_hash = os.environ.get("TELEGRAM_API_HASH")
    # load .env
    for line in Path(".env").read_text().splitlines() if Path(".env").exists() else []:
        if "=" in line and not line.startswith("#"):
            k,v=line.split("=",1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    api_id = os.environ.get("TELEGRAM_API_ID")
    api_hash = os.environ.get("TELEGRAM_API_HASH")
    if not (sess and api_id and api_hash):
        print("skip peer cache — missing creds")
        return
    target = "@Mr_iv4"
    try:
        import config
        target = getattr(config, "TARGET", target) or target
    except Exception:
        pass
    cache = Path("bot/data/telegram_target_entity.json")
    cache.parent.mkdir(parents=True, exist_ok=True)
    client = TelegramClient(StringSession(sess), int(api_id), api_hash)
    await client.connect()
    tnorm = str(target).lstrip("@").lower()
    found = None
    async for d in client.iter_dialogs():
        ent = d.entity
        uname = (getattr(ent, "username", None) or "").lower()
        if uname == tnorm:
            found = int(ent.id)
            break
    await client.disconnect()
    if found is not None:
        cache.write_text(json.dumps({"target": str(target), "id": found}))
        # also write env hint file
        Path("luxury_building.env").write_text(
            Path("luxury_building.env").read_text() + f"\nexport TELEGRAM_TARGET_PEER={found}\n"
            if Path("luxury_building.env").exists() else
            f"export TELEGRAM_TARGET_PEER={found}\n"
        )
        # append to .env
        env = Path(".env")
        lines = [ln for ln in env.read_text().splitlines() if not ln.startswith("TELEGRAM_TARGET_PEER=")] if env.exists() else []
        lines.append(f"TELEGRAM_TARGET_PEER={found}")
        env.write_text("\n".join(lines) + "\n")
        print("CACHED_PEER", target, found)
    else:
        print("PEER_NOT_IN_DIALOGS", target)

try:
    asyncio.run(cache_peer())
except Exception as e:
    print("peer_cache_fail", type(e).__name__, e)
PY

echo "========== [5/6] fix Oracle DB path warning (best-effort) =========="
python3 - <<'PY'
from pathlib import Path
# Ensure bot/bacbo.db exists / symlink common locations
root = Path('.')
candidates = [Path('bot/bacbo.db'), Path('bacbo.db'), Path('bot/data/bacbo.db')]
existing = [p for p in candidates if p.exists()]
print("db_existing", existing)
if Path('bot/bacbo.db').exists() and not Path('bacbo.db').exists():
    try:
        Path('bacbo.db').symlink_to('bot/bacbo.db')
        print("symlinked ./bacbo.db -> bot/bacbo.db")
    except Exception as e:
        print("symlink_fail", e)
# Oracle sometimes wants bot/data/
data = Path('bot/data')
data.mkdir(parents=True, exist_ok=True)
if Path('bot/bacbo.db').exists() and not (data/'bacbo.db').exists():
    try:
        (data/'bacbo.db').symlink_to('../bacbo.db')
        print("symlinked bot/data/bacbo.db")
    except Exception as e:
        print("data symlink", e)
PY

echo "========== [6/6] restart with backoff (slow children) =========="
cat > luxury_building.env <<'EOF'
export EDGE_POLICY_MODE=luxury
export EDGE_LUXURY_FLOOR_GATE=1
export FALLBACK_SEND_BLOCKED=0
export BOT_TZ=America/Sao_Paulo
EOF
# keep peer if cached
if grep -q TELEGRAM_TARGET_PEER .env 2>/dev/null; then
  echo "export $(grep '^TELEGRAM_TARGET_PEER=' .env)" >> luxury_building.env
fi
set -a; source ./luxury_building.env; set +a
export TELEGRAM_SESSION_STRING="$(tr -d '\n' < .telegram_session_string)"

pkill -f 'runtime_supervisor.py' 2>/dev/null || true
pkill -f 'bacbo_royal_complete.py' 2>/dev/null || true
pkill -f 'fallback_signal_sender.py' 2>/dev/null || true
pkill -f 'fallback_result_sender.py' 2>/dev/null || true
sleep 2

# Temporarily stop fallback_result from spamming while flood cools — start supervisor only with bot_live?
# Keep all but with longer first sleep via env
export FALLBACK_START_DELAY_SEC=120

nohup env EDGE_POLICY_MODE=luxury EDGE_LUXURY_FLOOR_GATE=1 FALLBACK_SEND_BLOCKED=0 \
  BOT_TZ=America/Sao_Paulo \
  TELEGRAM_SESSION_STRING="$TELEGRAM_SESSION_STRING" \
  ${TELEGRAM_TARGET_PEER:+TELEGRAM_TARGET_PEER=$TELEGRAM_TARGET_PEER} \
  python3 -u bot/runtime_supervisor.py > /tmp/luxury_supervisor.log 2>&1 &
echo "supervisor pid=$!"
sleep 8

echo "===== procs ====="
pgrep -af 'runtime_supervisor|bacbo_royal|fallback_signal|fallback_result' || true
echo "===== bot_live ====="
tail -n 80 logs/bot_live.log | tail -n 80
echo "===== fallback_sender ====="
tail -n 30 logs/fallback_sender.log
echo "===== fallback_result ====="
tail -n 20 logs/fallback_result_sender.log

python3 - <<'PY'
from pathlib import Path
import ast
ast.parse(Path('bacbo_royal_complete.py').read_text(encoding='utf-8'))
ast.parse(Path('bot/commands.py').read_text(encoding='utf-8'))
print('syntax_ok bacbo+commands')
print('peer_cache', Path('bot/data/telegram_target_entity.json').read_text() if Path('bot/data/telegram_target_entity.json').exists() else None)
# check if bot_live stayed up
import time, subprocess
time.sleep(5)
print(subprocess.getoutput("pgrep -af bacbo_royal || echo NO_BACBO"))
print(subprocess.getoutput("tail -n 15 logs/bot_live.log"))
PY

echo
echo "DONE. Paste ALL output to Cursor."
