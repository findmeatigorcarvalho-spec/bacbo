#!/usr/bin/env bash
# Fix: bacbo NameError(state) + short SESSION in .env + fallback FloodWait on username resolve.
set -euo pipefail
cd /home/runner/workspace

echo "========== [1/5] scrub short TELEGRAM_SESSION_STRING from .env =========="
python3 - <<'PY'
from pathlib import Path
import os

ROOT = Path("/home/runner/workspace")
sess_file = ROOT / ".telegram_session_string"
sess = sess_file.read_text(errors="ignore").strip() if sess_file.exists() else ""
print("session_file_len", len(sess))

env_path = ROOT / ".env"
lines = env_path.read_text(errors="ignore").splitlines() if env_path.exists() else []
out = []
removed = 0
for ln in lines:
    if ln.startswith("TELEGRAM_SESSION_STRING=") or ln.startswith("TELEGRAM_STRING_SESSION="):
        val = ln.split("=", 1)[1].strip().strip('"').strip("'")
        if len(val) <= 50:
            removed += 1
            continue  # drop short/bad
        out.append(ln)
    else:
        out.append(ln)

# Prefer file as source of truth — do not put huge session in .env (bacbo may still read env first).
# Ensure process env for children comes from supervisor reading the file.
# If a long session already in .env keep it; else rely on file.
long_in_env = any(
    ln.startswith("TELEGRAM_SESSION_STRING=") and len(ln.split("=",1)[1].strip().strip('"').strip("'")) > 50
    for ln in out
)
print("removed_short_session_env_lines", removed, "long_in_env", long_in_env)

# keep edge keys
def upsert(lines, key, value):
    lines = [ln for ln in lines if not ln.startswith(key + "=")]
    lines.append(f"{key}={value}")
    return lines

out = upsert(out, "EDGE_POLICY_MODE", "luxury")
out = upsert(out, "EDGE_LUXURY_FLOOR_GATE", "1")
out = upsert(out, "FALLBACK_SEND_BLOCKED", "0")
out = upsert(out, "BOT_TZ", "America/Sao_Paulo")
env_path.write_text("\n".join(out) + "\n", encoding="utf-8")

# also clear bad short values from current process env file used by replit secrets mirror if any
for bad in ("None", "null", "false", "true", ""):
    pass
print("env scrubbed")
PY

echo "========== [2/5] fix bacbo_royal_complete.py state NameError =========="
python3 - <<'PY'
from __future__ import annotations
import re
from pathlib import Path

p = Path("/home/runner/workspace/bacbo_royal_complete.py")
if not p.exists():
    raise SystemExit("MISSING bacbo_royal_complete.py")

src = p.read_text(encoding="utf-8", errors="replace")
bak = p.with_suffix(".py.bak_pre_state_fix")
if not bak.exists():
    bak.write_text(src, encoding="utf-8")

# Show context around client assignment
lines = src.splitlines()
hit = [i for i, ln in enumerate(lines) if "state.client" in ln or "TelegramClient(_session" in ln]
print("state.client lines:", [i+1 for i in hit[:10]])
for i in hit[:3]:
    a, b = max(0, i-15), min(len(lines), i+5)
    print(f"----- context {a+1}-{b} -----")
    for j in range(a, b):
        print(f"{j+1}: {lines[j]}")

# Detect if state is assigned anywhere
has_state_assign = bool(re.search(r"^\s*state\s*=\s*", src, re.M))
has_state_class = "class " in src and "State" in src
print("has_state_assign", has_state_assign)

# Common patterns in this codebase
# 1) state = BotState() / AppState() / SimpleNamespace()
# 2) state defined inside a function but used at module level (bug)
# 3) previous patch deleted state init

# Find BotState / AppState / class definitions
class_names = re.findall(r"class\s+(\w*State\w*)\s*[\(:]", src)
print("state_classes", class_names[:10])

# If state.client used at module level but state never assigned — inject before first state.client
if "state.client" in src and not has_state_assign:
    # Prefer existing class
    ctor = None
    for name in class_names or ["BotState", "AppState"]:
        if re.search(rf"class\s+{name}\b", src):
            ctor = name
            break
    if ctor is None:
        # inject a tiny state object
        inject_cls = '''
class _LuxBotState:
    def __init__(self):
        self.client = None
        self.me = None
        self.running = True

'''
        # place after imports block roughly before first state.client
        idx = src.find("state.client")
        src = src[:idx] + inject_cls + "state = _LuxBotState()\n\n" + src[idx:]
        print("injected _LuxBotState + state = _LuxBotState()")
    else:
        idx = src.find("state.client")
        # walk back to insert just before the TelegramClient block
        insert_at = src.rfind("\n", 0, idx)
        injection = f"\n# --- LUXURY_STATE_INIT (auto) ---\nif 'state' not in globals() or state is None:\n    state = {ctor}()\n"
        # simpler unconditional if missing
        injection = f"\n# --- LUXURY_STATE_INIT (auto) ---\nstate = {ctor}()\n"
        src = src[:insert_at] + injection + src[insert_at:]
        print(f"injected state = {ctor}() before state.client")
elif has_state_assign:
    # state assigned somewhere — maybe after use, or conditional
    first_use = src.find("state.client")
    first_assign = re.search(r"^\s*state\s*=\s*", src, re.M)
    if first_assign and first_use >= 0 and first_assign.start() > first_use:
        print("state assigned AFTER use — moving/injecting early init")
        # inject early init before first use
        ctor = class_names[0] if class_names else None
        insert_at = src.rfind("\n", 0, first_use)
        if ctor:
            injection = f"\n# --- LUXURY_STATE_INIT (auto) ---\nstate = {ctor}()\n"
        else:
            injection = "\n# --- LUXURY_STATE_INIT (auto) ---\nfrom types import SimpleNamespace\nstate = SimpleNamespace(client=None, me=None, running=True)\n"
        src = src[:insert_at] + injection + src[insert_at:]
    else:
        # Maybe state init is inside `if False` / failed try
        # Ensure a guard right before state.client
        if "LUXURY_STATE_INIT" not in src:
            first_use = src.find("state.client")
            insert_at = src.rfind("\n", 0, first_use)
            ctor = class_names[0] if class_names else None
            if ctor:
                injection = (
                    f"\n# --- LUXURY_STATE_INIT (auto) ---\n"
                    f"try:\n    state\nexcept NameError:\n    state = {ctor}()\n"
                )
            else:
                injection = (
                    "\n# --- LUXURY_STATE_INIT (auto) ---\n"
                    "try:\n    state\nexcept NameError:\n"
                    "    from types import SimpleNamespace\n"
                    "    state = SimpleNamespace(client=None, me=None, running=True)\n"
                )
            src = src[:insert_at] + injection + src[insert_at:]
            print("injected NameError guard before state.client")
        else:
            print("LUXURY_STATE_INIT already present")

# Also: if TELEGRAM_SESSION_STRING short warning — force load from file before client create
if "LUXURY_SESSION_FILE_FORCE" not in src:
    needle = "TelegramClient(_session"
    idx = src.find(needle)
    if idx < 0:
        idx = src.find("TelegramClient(")
    if idx >= 0:
        insert_at = src.rfind("\n", 0, idx)
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
        src = src[:insert_at] + force + src[insert_at:]
        print("injected session file force before TelegramClient")

p.write_text(src, encoding="utf-8")

# syntax check
import ast
ast.parse(p.read_text(encoding="utf-8"))
print("bacbo_royal_complete.py syntax OK")
PY

echo "========== [3/5] patch fallback: avoid ResolveUsername FloodWait =========="
python3 - <<'PY'
from pathlib import Path
import re

HELPER = '''
async def _resolve_target(client, target):
    """Resolve Telegram target without hammering ResolveUsername (FloodWait)."""
    import os, json
    from pathlib import Path
    cache = Path(__file__).resolve().parent / "data" / "telegram_target_entity.json"
    cache.parent.mkdir(parents=True, exist_ok=True)

    # numeric id / -100... peer
    if target is None:
        raise RuntimeError("TARGET missing in config")
    if isinstance(target, int) or (isinstance(target, str) and target.lstrip("-").isdigit()):
        return await client.get_entity(int(target))

    # env override peer id
    peer = os.environ.get("TELEGRAM_TARGET_PEER") or os.environ.get("TARGET_PEER_ID")
    if peer and str(peer).lstrip("-").isdigit():
        return await client.get_entity(int(peer))

    # cached entity id from prior successful resolve
    if cache.exists():
        try:
            data = json.loads(cache.read_text())
            if data.get("target") == str(target) and data.get("id") is not None:
                return await client.get_entity(int(data["id"]))
        except Exception:
            pass

    # try dialogs match (no ResolveUsername)
    tnorm = str(target).lstrip("@").lower()
    try:
        async for d in client.iter_dialogs():
            ent = d.entity
            uname = (getattr(ent, "username", None) or "").lower()
            title = (getattr(ent, "title", None) or getattr(ent, "first_name", None) or "").lower()
            if uname == tnorm or title == tnorm or (tnorm and tnorm in uname):
                try:
                    cache.write_text(json.dumps({"target": str(target), "id": int(ent.id)}))
                except Exception:
                    pass
                return ent
    except Exception as e:
        print("[Fallback] dialogs scan failed:", e)

    # last resort: get_entity (may FloodWait)
    try:
        from telethon.errors import FloodWaitError
    except Exception:
        FloodWaitError = Exception  # type: ignore
    try:
        ent = await client.get_entity(target)
        try:
            cache.write_text(json.dumps({"target": str(target), "id": int(ent.id)}))
        except Exception:
            pass
        return ent
    except FloodWaitError as e:
        print("[Fallback] FloodWait on ResolveUsername — set TELEGRAM_TARGET_PEER to numeric chat id. seconds=", getattr(e, "seconds", "?"))
        raise
'''

for rel in ["bot/fallback_signal_sender.py", "bot/fallback_result_sender.py"]:
    p = Path(rel)
    t = p.read_text(encoding="utf-8", errors="replace")
    if "_resolve_target" not in t:
        # insert before async def main or after _load_telegram_session
        if "async def main" in t:
            t = t.replace("async def main", HELPER + "\nasync def main", 1)
        else:
            t = HELPER + "\n" + t
    t2 = t.replace(
        "entity = await client.get_entity(target)",
        "entity = await _resolve_target(client, target)",
    )
    if t2 == t and "entity = await _resolve_target" not in t:
        print("WARN no get_entity site", rel)
    p.write_text(t2, encoding="utf-8")
    print("patched", rel)
PY

echo "========== [4/5] ensure supervisor exports session from file =========="
python3 - <<'PY'
from pathlib import Path
p = Path("bot/runtime_supervisor.py")
t = p.read_text(encoding="utf-8", errors="replace")
# make sure short env session cannot override file
needle = 'if session_path.exists():\n        env["TELEGRAM_SESSION_STRING"] = session_path.read_text(errors="ignore").strip()'
better = '''if session_path.exists():
        _sv = session_path.read_text(errors="ignore").strip()
        if len(_sv) > 50:
            env["TELEGRAM_SESSION_STRING"] = _sv
        elif len((env.get("TELEGRAM_SESSION_STRING") or "").strip()) <= 50:
            env.pop("TELEGRAM_SESSION_STRING", None)
    # drop short session values from inherited env
    if len((env.get("TELEGRAM_SESSION_STRING") or "").strip()) <= 50:
        env.pop("TELEGRAM_SESSION_STRING", None)'''
if "len(_sv) > 50" not in t and needle in t:
    t = t.replace(needle, better)
    p.write_text(t, encoding="utf-8")
    print("patched runtime_supervisor session length guard")
elif "len(_sv) > 50" in t:
    print("supervisor session guard already present")
else:
    print("WARN: supervisor pattern not found — check manually")
PY

echo "========== [5/5] restart + verify =========="
cat > luxury_building.env <<'EOF'
export EDGE_POLICY_MODE=luxury
export EDGE_LUXURY_FLOOR_GATE=1
export FALLBACK_SEND_BLOCKED=0
export BOT_TZ=America/Sao_Paulo
EOF
set -a; source ./luxury_building.env; set +a

pkill -f 'runtime_supervisor.py' 2>/dev/null || true
pkill -f 'bacbo_royal_complete.py' 2>/dev/null || true
pkill -f 'fallback_signal_sender.py' 2>/dev/null || true
pkill -f 'fallback_result_sender.py' 2>/dev/null || true
sleep 1

# export session into supervisor parent env (length-safe)
export TELEGRAM_SESSION_STRING="$(tr -d '\n' < .telegram_session_string)"
echo "exported TELEGRAM_SESSION_STRING len=${#TELEGRAM_SESSION_STRING}"

nohup env EDGE_POLICY_MODE=luxury EDGE_LUXURY_FLOOR_GATE=1 FALLBACK_SEND_BLOCKED=0 \
  BOT_TZ=America/Sao_Paulo \
  TELEGRAM_SESSION_STRING="$TELEGRAM_SESSION_STRING" \
  python3 -u bot/runtime_supervisor.py > /tmp/luxury_supervisor.log 2>&1 &
echo "supervisor pid=$!"
sleep 7

echo "===== procs ====="
pgrep -af 'runtime_supervisor|bacbo_royal|fallback_signal|fallback_result' || true
echo "===== bot_live ====="
tail -n 60 logs/bot_live.log 2>/dev/null || true
echo "===== fallback_sender ====="
tail -n 40 logs/fallback_sender.log 2>/dev/null || true
echo "===== fallback_result ====="
tail -n 25 logs/fallback_result_sender.log 2>/dev/null || true

python3 - <<'PY'
import ast
from pathlib import Path
src = Path('bacbo_royal_complete.py').read_text(encoding='utf-8')
ast.parse(src)
print('bacbo_syntax_ok')
print('has_LUXURY_STATE_INIT', 'LUXURY_STATE_INIT' in src)
print('has_session_force', 'LUXURY_SESSION_FILE_FORCE' in src)
print('session_len', len(Path('.telegram_session_string').read_text().strip()))
# show TARGET from config if possible
import sys
sys.path.insert(0,'bot')
try:
    import config
    print('TARGET', getattr(config,'TARGET',None), type(getattr(config,'TARGET',None)))
except Exception as e:
    print('config_TARGET_fail', e)
PY

echo
echo "DONE. Paste ALL output to Cursor."
echo "If fallback still FloodWait: set Secret TELEGRAM_TARGET_PEER=<numeric chat id> (e.g. -100...)."
