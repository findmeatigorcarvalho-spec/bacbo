#!/usr/bin/env bash
# Hard fix: state module bind order + clean fallback restore (no broken continue).
set -euo pipefail
cd /home/runner/workspace

echo "========== [1/4] kill everything =========="
pkill -9 -f 'runtime_supervisor.py' 2>/dev/null || true
pkill -9 -f 'bacbo_royal_complete.py' 2>/dev/null || true
pkill -9 -f 'fallback_signal_sender.py' 2>/dev/null || true
pkill -9 -f 'fallback_result_sender.py' 2>/dev/null || true
sleep 2
pgrep -af 'bacbo_royal|fallback_|runtime_supervisor' || echo "(all clear)"

echo "========== [2/4] fix bacbo: import state BEFORE client; bind proxy correctly =========="
python3 - <<'PY'
from pathlib import Path
import re, ast, shutil

p = Path("bacbo_royal_complete.py")
bak = Path("bacbo_royal_complete.py.bak_pre_state_fix")
if bak.exists():
    shutil.copy2(bak, p)
    print("restored from bak_pre_state_fix")

src = p.read_text(encoding="utf-8", errors="replace")

# Strip all prior luxury injects
for marker in (
    "LUXURY_STATE_INIT", "LUXURY_SESSION_FILE_FORCE", "LUXURY_COMMANDS_GUARD",
    "LUXURY_BIND_PROXY", "LUXURY_CLIENT_PROXY",
):
    src = re.sub(
        rf"\n# --- {marker} \(auto\) ---.*?(?=\n# --- |\nstate\.client\s*=|\n# ──|\n\[BOOT\]|\Z)",
        "\n",
        src,
        flags=re.S,
    )
src = re.sub(r"\nclass _LuxBotState:.*?\nstate = _LuxBotState\(\)\n+", "\n", src, flags=re.S)
src = re.sub(
    r"\n_lux_prev_client = getattr\(state, \"client\", None\)\nstate\.client = TelegramClient\([^\n]*\)\ntry:\n    if hasattr\(_lux_prev_client, \"bind\"\):[\s\S]*?print\(\"\[LUXURY\] proxy bind failed:.*?\)\n",
    "\nstate.client = TelegramClient(_session, API_ID, API_HASH, sequential_updates=False)\n",
    src,
)

# Find import state line #
lines = src.splitlines()
import_idxs = [i for i, ln in enumerate(lines) if re.match(r"^import state\b", ln) or re.match(r"^from state import\b", ln)]
client_idxs = [i for i, ln in enumerate(lines) if re.match(r"^state\.client\s*=\s*TelegramClient\(", ln)]
print("import_state_lines", [i+1 for i in import_idxs])
print("client_assign_lines", [i+1 for i in client_idxs])

if not client_idxs:
    # maybe multiline left from bad wrap
    client_idxs = [i for i, ln in enumerate(lines) if "TelegramClient(_session" in ln and "state.client" in ln]
    print("alt client lines", [i+1 for i in client_idxs])

if not client_idxs:
    # search any TelegramClient assign to state
    for i, ln in enumerate(lines):
        if "TelegramClient" in ln and "client" in ln:
            if i < 250:
                print(f"cand {i+1}: {ln[:120]}")
    raise SystemExit("cannot find state.client = TelegramClient")

ci = client_idxs[0]

# Ensure `import state` appears BEFORE client assign
if not import_idxs or min(import_idxs) > ci:
    # insert import state just before client assign
    lines.insert(ci, "import state  # LUXURY: ensure module in scope before client assign")
    ci += 1
    print("inserted import state before client assign")
else:
    print("import state OK before client at", min(import_idxs)+1)

# Rebuild src
src = "\n".join(lines) + "\n"
# re-find ci
lines = src.splitlines()
ci = next(i for i, ln in enumerate(lines) if re.match(r"^state\.client\s*=\s*TelegramClient\(", ln) or (
    "state.client" in ln and "TelegramClient(_session" in ln
))

# Replace client assign with session-force + proxy-safe bind using importlib
old_line = lines[ci]
# Extract original TelegramClient(...) call args if possible
m = re.search(r"state\.client\s*=\s*(TelegramClient\(.+\))\s*$", old_line)
ctor = m.group(1) if m else "TelegramClient(_session, API_ID, API_HASH, sequential_updates=False)"

block = f'''# --- LUXURY_SESSION_AND_BIND (auto) ---
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
_lux_state_mod.client = {ctor}
try:
    if hasattr(_lux_prev_client, "bind"):
        _lux_prev_client.bind(_lux_state_mod.client)
except Exception as _lux_bind_exc:
    print("[LUXURY] proxy bind failed:", _lux_bind_exc)
# keep bare name `state` working if already imported
try:
    state.client = _lux_state_mod.client
except Exception:
    pass
# --- end LUXURY_SESSION_AND_BIND ---'''

lines[ci] = block
src = "\n".join(lines) + "\n"
p.write_text(src, encoding="utf-8")
ast.parse(src)
print("bacbo OK")
# show context
lines = src.splitlines()
for i, ln in enumerate(lines):
    if "LUXURY_SESSION_AND_BIND" in ln or (i > 0 and "TelegramClient(_session" in ln and i < 220):
        for j in range(max(0, i-3), min(len(lines), i+20)):
            print(f"{j+1}: {lines[j][:140]}")
        break
PY

echo "========== [3/4] restore fallbacks from bak + peer-only patch =========="
python3 - <<'PY'
from pathlib import Path
import ast, shutil, os

PEER = "6774605259"
Path("bot/data").mkdir(parents=True, exist_ok=True)
Path("bot/data/telegram_target_entity.json").write_text(
    '{"target":"@Mr_iv4","id":6774605259}\n', encoding="utf-8"
)

def write_env():
    Path("luxury_building.env").write_text(
        "export EDGE_POLICY_MODE=luxury\n"
        "export EDGE_LUXURY_FLOOR_GATE=1\n"
        "export FALLBACK_SEND_BLOCKED=0\n"
        "export BOT_TZ=America/Sao_Paulo\n"
        f"export TELEGRAM_TARGET_PEER={PEER}\n",
        encoding="utf-8",
    )
    env = Path(".env")
    lines = []
    if env.exists():
        for ln in env.read_text().splitlines():
            if ln.startswith("TELEGRAM_TARGET_PEER=") or ln.startswith("EDGE_POLICY_MODE=") \
               or ln.startswith("EDGE_LUXURY_FLOOR_GATE=") or ln.startswith("FALLBACK_SEND_BLOCKED=") \
               or ln.startswith("BOT_TZ=") or ln.startswith("TELEGRAM_SESSION_STRING="):
                continue
            lines.append(ln)
    lines += [
        "EDGE_POLICY_MODE=luxury",
        "EDGE_LUXURY_FLOOR_GATE=1",
        "FALLBACK_SEND_BLOCKED=0",
        "BOT_TZ=America/Sao_Paulo",
        f"TELEGRAM_TARGET_PEER={PEER}",
    ]
    env.write_text("\n".join(lines) + "\n", encoding="utf-8")

write_env()

RESOLVE = '''
def _load_telegram_session() -> str:
    import os
    from pathlib import Path
    for key in ("TELEGRAM_SESSION_STRING", "TELEGRAM_STRING_SESSION", "STRING_SESSION"):
        v = (os.environ.get(key) or "").strip()
        if len(v) > 50:
            return v
    p = Path("/home/runner/workspace/.telegram_session_string")
    if p.exists():
        v = p.read_text(errors="ignore").strip()
        if len(v) > 50:
            return v
    raise FileNotFoundError("Telegram session missing")


async def _resolve_target(client, target):
    """Resolve using cached/numeric peer only — never ResolveUsername while flooded."""
    import os, json
    from pathlib import Path
    peer = os.environ.get("TELEGRAM_TARGET_PEER") or os.environ.get("TARGET_PEER_ID")
    if peer and str(peer).lstrip("-").isdigit():
        return await client.get_entity(int(peer))
    cache = Path(__file__).resolve().parent / "data" / "telegram_target_entity.json"
    if cache.exists():
        data = json.loads(cache.read_text())
        if data.get("id") is not None:
            return await client.get_entity(int(data["id"]))
    if isinstance(target, int) or (isinstance(target, str) and str(target).lstrip("-").isdigit()):
        return await client.get_entity(int(target))
    # dialogs only
    tnorm = str(target).lstrip("@").lower()
    async for d in client.iter_dialogs():
        ent = d.entity
        if (getattr(ent, "username", None) or "").lower() == tnorm:
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(json.dumps({"target": str(target), "id": int(ent.id)}))
            return ent
    raise RuntimeError("set TELEGRAM_TARGET_PEER numeric id")

'''

for rel in ["bot/fallback_signal_sender.py", "bot/fallback_result_sender.py"]:
    p = Path(rel)
    bak = Path(str(p) + ".bak_pre_session_fix")
    if bak.exists():
        shutil.copy2(bak, p)
        print("restored", rel, "from", bak.name)
    else:
        print("WARN no bak for", rel, "— patching in place")

    t = p.read_text(encoding="utf-8", errors="replace")
    # Strip any prior luxury injections entirely
    import re
    t = re.sub(r"\n# --- LUXURY_[\w]+ \(auto\) ---.*?(?=\nasync def |\ndef |\n# --- |\Z)", "\n", t, flags=re.S)
    t = re.sub(r"\nasync def _resolve_target\([\s\S]*?\n(?=async def main)", "\n", t)
    t = re.sub(r"\ndef _load_telegram_session\([\s\S]*?\n(?=async def |\ndef )", "\n", t)
    t = re.sub(r"\nasync def _lux_sleep_flood\([\s\S]*?\n(?=async def |\ndef |# ---)", "\n", t)
    # remove orphan flood if/continue blocks
    t = re.sub(
        r"\n[ \t]+if 'FloodWait' in type\(\w+\)\.__name__:\n[ \t]+await _lux_sleep_flood\([^\n]+\)\n[ \t]+continue\n",
        "\n",
        t,
    )
    t = re.sub(
        r"\n[ \t]+if e\.__class__\.__name__ == 'FloodWaitError'[^\n]*\n[ \t]+await _lux_sleep_flood[^\n]+\n[ \t]+continue\n",
        "\n",
        t,
    )

    if "def _load_telegram_session" not in t:
        t = t.replace("async def main", RESOLVE + "\nasync def main", 1)
    t = t.replace(
        'session = (ROOT / ".telegram_session_string").read_text().strip()',
        "session = _load_telegram_session()",
    )
    t = t.replace(
        "entity = await client.get_entity(target)",
        "entity = await _resolve_target(client, target)",
    )
    # FloodWait inside while-loop: sleep using asyncio.sleep without broken continue injection
    # Add safe helper + patch common error print inside `while True`
    if "async def _lux_sleep_flood" not in t:
        t = t.replace(
            "async def main",
            "async def _lux_sleep_flood(err, label='fallback'):\n"
            "    import asyncio\n"
            "    secs = int(getattr(err, 'seconds', 0) or 0)\n"
            "    sleep_for = min(max(secs, 1), 300)\n"
            "    print(f'[{label}] FloodWait {secs}s — sleeping {sleep_for}s')\n"
            "    await asyncio.sleep(sleep_for)\n\n"
            "async def main",
            1,
        )
    # Only inject into except blocks that are indented under while (heuristic: 8+ spaces before except)
    def inject_flood(text: str, label: str) -> str:
        pattern = rf"(while True:\n[\s\S]*?except Exception as (\w+):\n)([ \t]+)print\([^\n]*{label}[^\n]*\n)"
        def repl(m):
            indent = m.group(3)
            var = m.group(2)
            return (
                m.group(1)
                + f"{indent}print(f'[{label}] error: {{{var}!r}}')\n"
                + f"{indent}if 'FloodWait' in type({var}).__name__:\n"
                + f"{indent}    await _lux_sleep_flood({var}, '{label}')\n"
                + f"{indent}    continue\n"
            )
        # safer: don't use complex replace if already has _lux_sleep_flood call in file under while
        if "await _lux_sleep_flood" in text:
            return text
        # simple line-based injection for known print patterns
        out_lines = []
        lines = text.splitlines(True)
        i = 0
        in_while = 0
        while i < len(lines):
            ln = lines[i]
            if ln.strip().startswith("while True"):
                in_while += 1
            out_lines.append(ln)
            if in_while and re.match(r"[ \t]+except Exception as (\w+):\s*$", ln):
                var = re.match(r"[ \t]+except Exception as (\w+):\s*$", ln).group(1)
                indent = re.match(r"([ \t]+)", ln).group(1) + "    "
                # peek next print
                if i + 1 < len(lines) and "print(" in lines[i + 1]:
                    out_lines.append(lines[i + 1]); i += 2
                    out_lines.append(f"{indent}if 'FloodWait' in type({var}).__name__:\n")
                    out_lines.append(f"{indent}    await _lux_sleep_flood({var}, '{label}')\n")
                    out_lines.append(f"{indent}    continue\n")
                    continue
            i += 1
        return "".join(out_lines)

    label = "FallbackSender" if "signal_sender" in rel else "FallbackResultSender"
    t = inject_flood(t, label)

    p.write_text(t, encoding="utf-8")
    ast.parse(t)
    # compile check catch continue-not-in-loop
    compile(t, rel, "exec")
    print(rel, "OK")

# Ensure state.py still has proxy (from previous fix)
sp = Path("bot/state.py")
st = sp.read_text(encoding="utf-8", errors="replace")
if "LUXURY_CLIENT_PROXY" not in st:
    print("WARN: state.py missing proxy — re-applying")
    # minimal append if client=None exists
    if "client = None" in st and "_LuxClientProxy" not in st:
        st = st.replace(
            "client = None",
            "client = None\n\n"
            "class _LuxClientProxy:\n"
            "    def __init__(self):\n"
            "        self._client=None; self._pending=[]\n"
            "    def bind(self, client):\n"
            "        self._client=client\n"
            "        for event, func in list(self._pending):\n"
            "            client.add_event_handler(func, event)\n"
            "        self._pending.clear(); return client\n"
            "    def on(self, event):\n"
            "        def deco(func):\n"
            "            if self._client is not None: self._client.add_event_handler(func, event)\n"
            "            else: self._pending.append((event, func))\n"
            "            return func\n"
            "        return deco\n"
            "    def __bool__(self): return self._client is not None\n"
            "    def __getattr__(self, name):\n"
            "        if self._client is None: raise AttributeError(name)\n"
            "        return getattr(self._client, name)\n"
            "if client is None or not hasattr(client, 'on'):\n"
            "    client = _LuxClientProxy()\n",
            1,
        )
        sp.write_text(st, encoding="utf-8")
        ast.parse(st)
        print("state proxy re-applied")
else:
    print("state.py proxy OK")

# restore commands clean
cbak = Path("bot/commands.py.bak_pre_client_fix")
if cbak.exists():
    shutil.copy2(cbak, Path("bot/commands.py"))
    print("commands.py restored clean")
ast.parse(Path("bot/commands.py").read_text(encoding="utf-8"))
print("all compile checks passed")
PY

echo "========== [4/4] start supervisor =========="
set -a
source ./luxury_building.env
set +a
export TELEGRAM_SESSION_STRING="$(tr -d '\n' < .telegram_session_string)"
export TELEGRAM_TARGET_PEER=6774605259
export EDGE_POLICY_MODE=luxury
export EDGE_LUXURY_FLOOR_GATE=1
export FALLBACK_SEND_BLOCKED=0

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
tail -n 40 logs/bot_live.log
echo "===== fallback_sender ====="
tail -n 20 logs/fallback_sender.log
echo "===== fallback_result ====="
tail -n 15 logs/fallback_result_sender.log

python3 - <<'PY'
import time, subprocess, ast
from pathlib import Path
for f in ['bacbo_royal_complete.py','bot/state.py','bot/commands.py','bot/fallback_signal_sender.py','bot/fallback_result_sender.py']:
    ast.parse(Path(f).read_text(encoding='utf-8'))
print('syntax_ok')
time.sleep(5)
print(subprocess.getoutput('pgrep -af "bacbo_royal|fallback_signal|fallback_result|runtime_supervisor" || true'))
print('--- bot_live last 25 ---')
print(subprocess.getoutput('tail -n 25 logs/bot_live.log'))
print('--- fallback last 15 ---')
print(subprocess.getoutput('tail -n 15 logs/fallback_sender.log'))
PY

echo
echo "DONE. Paste ALL output to Cursor."
