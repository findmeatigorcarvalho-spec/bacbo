#!/usr/bin/env bash
# ONE paste: clean restore + session/peer + room dialog cache + luxury restart.
set -euo pipefail
cd /home/runner/workspace
PY=python3

echo "========== [1/7] kill stale processes =========="
pkill -9 -f 'runtime_supervisor.py' 2>/dev/null || true
pkill -9 -f 'bacbo_royal_complete.py' 2>/dev/null || true
pkill -9 -f 'fallback_signal_sender.py' 2>/dev/null || true
pkill -9 -f 'fallback_result_sender.py' 2>/dev/null || true
sleep 2
pgrep -af 'bacbo_royal|fallback_|runtime_supervisor' || echo "(clear)"

echo "========== [2/7] tz_utils + telegram session + peer =========="
$PY <<'PY'
from pathlib import Path
import os, shutil

ROOT = Path("/home/runner/workspace")

# --- tz_utils full API on ROOT (script dir wins) ---
TZ = '''"""Timezone helpers (root — bacbo loads this first)."""
from __future__ import annotations
import os
from datetime import datetime, timezone
try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None  # type: ignore

_BOT_TZ = os.environ.get("BOT_TZ") or "America/Sao_Paulo"
DISPLAY_TZ = _BOT_TZ
TZ_NAME = DISPLAY_TZ

def _zone():
    if ZoneInfo is None:
        return timezone.utc
    try:
        return ZoneInfo(_BOT_TZ)
    except Exception:
        return timezone.utc

def now_utc():
    return datetime.now(timezone.utc)

def now_local():
    return datetime.now(tz=_zone())

local_now = now_local

def local_hour(dt=None):
    if dt is None:
        return now_local().hour
    if getattr(dt, "tzinfo", None) is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(_zone()).hour

def today_iso(dt=None):
    if dt is None:
        return now_local().date().isoformat()
    if getattr(dt, "tzinfo", None) is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(_zone()).date().isoformat()

def ts(dt=None):
    d = now_local() if dt is None else dt
    if getattr(d, "tzinfo", None) is None:
        d = d.replace(tzinfo=timezone.utc).astimezone(_zone())
    else:
        d = d.astimezone(_zone())
    return d.strftime("%Y-%m-%d %H:%M:%S")

def dts(dt=None):
    d = now_local() if dt is None else dt
    if getattr(d, "tzinfo", None) is None:
        d = d.replace(tzinfo=timezone.utc).astimezone(_zone())
    else:
        d = d.astimezone(_zone())
    return d.isoformat(sep=" ", timespec="seconds")
'''
(ROOT / "tz_utils.py").write_text(TZ, encoding="utf-8")
(ROOT / "bot" / "tz_utils.py").write_text(TZ, encoding="utf-8")
print("tz_utils OK")

# --- session from file or convert userbot_session.session ---
sess_path = ROOT / ".telegram_session_string"
need = not sess_path.exists() or len(sess_path.read_text(errors="ignore").strip()) <= 50
if need:
    # try env
    for key in ("TELEGRAM_SESSION_STRING", "TELEGRAM_STRING_SESSION"):
        v = (os.environ.get(key) or "").strip()
        if len(v) > 50:
            sess_path.write_text(v + "\n"); need = False; print("session from env", key); break
if need and (ROOT / "userbot_session.session").exists():
    # load api from .env
    env = {}
    if (ROOT / ".env").exists():
        for ln in (ROOT / ".env").read_text().splitlines():
            if "=" in ln and not ln.strip().startswith("#"):
                k, v = ln.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    api_id = os.environ.get("TELEGRAM_API_ID") or env.get("TELEGRAM_API_ID")
    api_hash = os.environ.get("TELEGRAM_API_HASH") or env.get("TELEGRAM_API_HASH")
    if api_id and api_hash:
        from telethon.sync import TelegramClient
        from telethon.sessions import StringSession
        c = TelegramClient(str(ROOT / "userbot_session"), int(api_id), api_hash)
        c.connect()
        if c.is_user_authorized():
            s = StringSession.save(c.session)
            sess_path.write_text(s + "\n")
            print("converted userbot_session.session len", len(s))
        c.disconnect()
print("session_len", len(sess_path.read_text().strip()) if sess_path.exists() else 0)

# peer + luxury env
PEER = "6774605259"
(ROOT / "bot" / "data").mkdir(parents=True, exist_ok=True)
(ROOT / "bot" / "data" / "telegram_target_entity.json").write_text(
    '{"target":"@Mr_iv4","id":6774605259}\n'
)
(ROOT / "luxury_building.env").write_text(
    "export EDGE_POLICY_MODE=luxury\n"
    "export EDGE_LUXURY_FLOOR_GATE=1\n"
    "export FALLBACK_SEND_BLOCKED=0\n"
    "export BOT_TZ=America/Sao_Paulo\n"
    f"export TELEGRAM_TARGET_PEER={PEER}\n"
)
# scrub short session from .env; set edge keys
envp = ROOT / ".env"
lines = []
if envp.exists():
    for ln in envp.read_text().splitlines():
        if ln.startswith("TELEGRAM_SESSION_STRING="):
            val = ln.split("=", 1)[1].strip().strip('"').strip("'")
            if len(val) <= 50:
                continue
        if ln.startswith(("EDGE_POLICY_MODE=", "EDGE_LUXURY_FLOOR_GATE=", "FALLBACK_SEND_BLOCKED=", "BOT_TZ=", "TELEGRAM_TARGET_PEER=")):
            continue
        lines.append(ln)
lines += [
    "EDGE_POLICY_MODE=luxury",
    "EDGE_LUXURY_FLOOR_GATE=1",
    "FALLBACK_SEND_BLOCKED=0",
    "BOT_TZ=America/Sao_Paulo",
    f"TELEGRAM_TARGET_PEER={PEER}",
]
envp.write_text("\n".join(lines) + "\n")
print("env OK peer", PEER)
PY

echo "========== [3/7] restore bacbo + safe patches only =========="
$PY <<'PY'
from pathlib import Path
import re, ast, shutil

ROOT = Path("/home/runner/workspace")
p = ROOT / "bacbo_royal_complete.py"
bak = ROOT / "bacbo_royal_complete.py.bak_pre_state_fix"
if not bak.exists():
    raise SystemExit("MISSING bak_pre_state_fix")
shutil.copy2(bak, p)
src = p.read_text(encoding="utf-8", errors="replace")

# strip any leftover luxury junk if backup somehow had it
for marker in (
    "LUXURY_STATE_INIT", "LUXURY_SESSION_FILE_FORCE", "LUXURY_BIND_PROXY",
    "LUXURY_SESSION_AND_BIND", "LUXURY_GET_ENTITY_MONKEYPATCH", "LUXURY_COMMANDS_GUARD",
    "LUXURY_ROOM_CACHE_RESOLVE",
):
    src = re.sub(rf"\n# --- {marker} \(auto\) ---.*?(?=\n# --- |\nstate\.client\s*=|\n# ──|\Z)", "\n", src, flags=re.S)
src = re.sub(r"\nclass _LuxBotState:.*?\nstate = _LuxBotState\(\)\n+", "\n", src, flags=re.S)
src = re.sub(r"\nimport state  # LUXURY:[^\n]*\n", "\n", src)
src = re.sub(r"\nimport config  # LUXURY:[^\n]*\n", "\n", src)

# early import config after __future__
if not re.search(r"^import config\b", "\n".join(src.splitlines()[:50]), re.M):
    lines = src.splitlines(True)
    idx = 0
    for i, ln in enumerate(lines[:40]):
        if ln.startswith("from __future__"):
            idx = i + 1
            break
    lines.insert(idx, "import config\n")
    src = "".join(lines)
    print("added early import config")

# monkeypatch get_entity — insert after telethon import
monkey = '''
# --- LUXURY_GET_ENTITY_MONKEYPATCH (auto) ---
try:
    import json as _lux_json
    from pathlib import Path as _LuxPath
    from telethon import TelegramClient as _LuxTGClient

    def _lux_cached_entity_id(username):
        try:
            p = _LuxPath("/home/runner/workspace/bot/data/room_entity_cache.json")
            if not p.exists():
                return None
            data = _lux_json.loads(p.read_text(encoding="utf-8"))
            m = data.get("by_username") or {}
            key = str(username or "").strip().lower()
            for k in (key, key.lstrip("@"), "@" + key.lstrip("@")):
                if k in m:
                    return int(m[k])
        except Exception:
            return None
        return None

    _lux_orig_get_entity = _LuxTGClient.get_entity

    async def _lux_get_entity(self, entity):
        if isinstance(entity, str) and not str(entity).lstrip("-").isdigit():
            eid = _lux_cached_entity_id(entity)
            if eid is not None:
                entity = eid
        return await _lux_orig_get_entity(self, entity)

    _LuxTGClient.get_entity = _lux_get_entity  # type: ignore
    print("[LUXURY] get_entity uses room_entity_cache (FloodWait bypass)")
except Exception as _lux_mp_exc:
    print("[LUXURY] get_entity monkeypatch skipped:", _lux_mp_exc)
# --- end LUXURY_GET_ENTITY_MONKEYPATCH ---
'''

if "LUXURY_GET_ENTITY_MONKEYPATCH" not in src:
    lines = src.splitlines(True)
    idx = 0
    for i, ln in enumerate(lines[:100]):
        if "telethon" in ln and (ln.startswith("import ") or ln.startswith("from ")):
            idx = i + 1
    if idx == 0:
        for i, ln in enumerate(lines[:60]):
            if ln.startswith("import ") or ln.startswith("from "):
                idx = i + 1
    lines.insert(idx, monkey + "\n")
    src = "".join(lines)
    print("injected get_entity monkeypatch")

# session + bind using importlib state module (never shadow with local state=)
bind = '''
# --- LUXURY_SESSION_AND_BIND (auto) ---
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
# --- end LUXURY_SESSION_AND_BIND ---
'''

m = re.search(r"^state\.client\s*=\s*TelegramClient\([^\n]*\)\s*$", src, re.M)
if not m:
    raise SystemExit("cannot find state.client = TelegramClient line in backup")
if "LUXURY_SESSION_AND_BIND" not in src:
    src = src[: m.start()] + bind + "\n" + src[m.end() :]
    print("injected session+bind")

p.write_text(src, encoding="utf-8")
ast.parse(src)
print("bacbo syntax OK bytes", p.stat().st_size)
PY

echo "========== [4/7] state.py client proxy + clean commands/fallbacks =========="
$PY <<'PY'
from pathlib import Path
import ast, shutil, re

ROOT = Path("/home/runner/workspace")

# state.py proxy
sp = ROOT / "bot" / "state.py"
st = sp.read_text(encoding="utf-8", errors="replace")
bak = sp.with_suffix(".py.bak_pre_proxy")
if not bak.exists():
    bak.write_text(st, encoding="utf-8")
# reset to backup if we have one without broken stuff, then apply proxy clean
if bak.exists() and "LUXURY_CLIENT_PROXY" in st:
    # rewrite cleanly from bak
    st = bak.read_text(encoding="utf-8")

if "LUXURY_CLIENT_PROXY" not in st:
    proxy = '''
# --- LUXURY_CLIENT_PROXY (auto) ---
class _LuxClientProxy:
    def __init__(self):
        self._client = None
        self._pending = []

    def bind(self, client):
        self._client = client
        for event, func in list(self._pending):
            try:
                client.add_event_handler(func, event)
            except Exception as e:
                print("[LUXURY] pending handler failed:", e)
        self._pending.clear()
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
        if self._client is None:
            raise AttributeError(f"client not ready ({name})")
        return getattr(self._client, name)

if client is None or not hasattr(client, "on"):
    client = _LuxClientProxy()
# --- end LUXURY_CLIENT_PROXY ---
'''
    if re.search(r"^client\s*=\s*None\s*$", st, re.M):
        st = re.sub(r"^client\s*=\s*None\s*$", "client = None\n" + proxy, st, count=1, flags=re.M)
    else:
        st = st.rstrip() + "\nclient = None\n" + proxy + "\n"
    sp.write_text(st, encoding="utf-8")
    ast.parse(st)
    print("state.py proxy OK")
else:
    print("state.py already proxied")

# commands clean
cbak = ROOT / "bot" / "commands.py.bak_pre_client_fix"
if cbak.exists():
    shutil.copy2(cbak, ROOT / "bot" / "commands.py")
    print("commands restored")
ast.parse((ROOT / "bot" / "commands.py").read_text(encoding="utf-8"))

# fallbacks: restore bak + peer/session ONLY (no continue hacks)
HELPER = '''
def _load_telegram_session() -> str:
    import os
    from pathlib import Path
    for key in ("TELEGRAM_SESSION_STRING", "TELEGRAM_STRING_SESSION"):
        v = (os.environ.get(key) or "").strip()
        if len(v) > 50:
            return v
    return Path("/home/runner/workspace/.telegram_session_string").read_text().strip()

async def _resolve_target(client, target):
    import os
    peer = os.environ.get("TELEGRAM_TARGET_PEER") or "6774605259"
    return await client.get_entity(int(peer))

'''
for rel in ["bot/fallback_signal_sender.py", "bot/fallback_result_sender.py"]:
    p = ROOT / rel
    bak = Path(str(p) + ".bak_pre_session_fix")
    if bak.exists():
        shutil.copy2(bak, p)
    t = p.read_text(encoding="utf-8", errors="replace")
    # strip prior luxury
    t = re.sub(r"\n# --- LUXURY_[\w]+ \(auto\) ---.*?(?=\nasync def |\ndef |\Z)", "\n", t, flags=re.S)
    t = re.sub(r"\nasync def _resolve_target\([\s\S]*?\n(?=async def main)", "\n", t)
    t = re.sub(r"\ndef _load_telegram_session\([\s\S]*?\n(?=async def |\ndef )", "\n", t)
    t = re.sub(r"\nasync def _lux_sleep_flood\([\s\S]*?\n(?=async def |\ndef )", "\n", t)
    t = re.sub(r"\n[ \t]+if 'FloodWait' in type\(\w+\)\.__name__:[\s\S]*?continue\n", "\n", t)
    if "def _load_telegram_session" not in t:
        t = t.replace("async def main", HELPER + "\nasync def main", 1)
    t = t.replace('session = (ROOT / ".telegram_session_string").read_text().strip()', "session = _load_telegram_session()")
    t = t.replace("entity = await client.get_entity(target)", "entity = await _resolve_target(client, target)")
    p.write_text(t, encoding="utf-8")
    compile(t, rel, "exec")
    print(rel, "OK")
PY

echo "========== [5/7] build room dialog cache (FloodWait bypass) =========="
$PY <<'PY'
import asyncio, json, os, sys
from pathlib import Path
ROOT = Path("/home/runner/workspace")
sys.path.insert(0, str(ROOT / "bot"))
for ln in (ROOT / ".env").read_text().splitlines() if (ROOT / ".env").exists() else []:
    if "=" in ln and not ln.strip().startswith("#"):
        k, v = ln.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

from telethon import TelegramClient
from telethon.sessions import StringSession

sess = (ROOT / ".telegram_session_string").read_text().strip()
api_id = os.environ["TELEGRAM_API_ID"]
api_hash = os.environ["TELEGRAM_API_HASH"]
cache_path = ROOT / "bot" / "data" / "room_entity_cache.json"

async def main():
    client = TelegramClient(StringSession(sess), int(api_id), api_hash)
    await client.connect()
    by_user, by_id, n = {}, {}, 0
    async for d in client.iter_dialogs():
        ent = d.entity
        n += 1
        uid = int(getattr(ent, "id", 0) or 0)
        uname = (getattr(ent, "username", None) or "").lower()
        title = getattr(ent, "title", None) or getattr(ent, "first_name", None) or ""
        if uid:
            by_id[str(uid)] = {"id": uid, "username": uname, "title": title}
        if uname:
            by_user[uname] = uid
            by_user["@" + uname] = uid
    await client.disconnect()
    cache_path.write_text(json.dumps({"by_username": by_user, "by_id": by_id, "dialogs_scanned": n}, indent=2) + "\n")
    print("dialogs", n, "usernames", len(by_user) // 2)
    for u in ["rqdados", "m8sinais", "bacbo", "coringadados", "sinal_bac_bo", "x8sinais", "isadados"]:
        print(" ", u, "->", by_user.get(u))

asyncio.run(main())
PY

echo "========== [6/7] peak-lock files present + luxury allowlist =========="
$PY <<'PY'
import json
from pathlib import Path
ROOT = Path("/home/runner/workspace")
DATA = ROOT / "bot" / "data"
DATA.mkdir(parents=True, exist_ok=True)
allow_path = DATA / "luxury_live_floors.json"
if allow_path.exists():
    allow = json.loads(allow_path.read_text())
else:
    allow = {}
allow.setdefault("blocked", ["JUN12A", "JUN12B"])
allow.setdefault("peak_lock", True)
allow.setdefault("gate_aliases", {})
ga = allow["gate_aliases"]
ga.update({
    "LIVE": "ELITE_V2", "JUN19": "JUN19_peak", "JUN20": "JUN20_peak",
    "JUN08": "JUN08_peak", "JUN10": "JUN10_peak", "MAY19": "MAY19_peak",
    "MAY10": "MAY10_peak", "MAY11": "MAY11_peak", "MAY01": "MAY01_peak",
    "APR19": "APR19_golden", "APR20": "APR20_perfect", "APR30": "APR30_peak",
    "ELITE_V2": "ELITE_V2", "ULTIMATE": "ULTIMATE",
})
# keep loaders for key floors if peaks exist
for logical, stem in list(ga.items()):
    if logical in ("JUN12A", "JUN12B"):
        continue
    peak = ROOT / "bot" / f"_gates_{stem}.py"
    logical_p = ROOT / "bot" / f"_gates_{logical}.py"
    if peak.exists() and logical != stem:
        logical_p.write_text(
            f'# AUTO peak-lock loader {logical} -> {stem}\n'
            f'from pathlib import Path\nimport runpy\n'
            f'_g = runpy.run_path(str(Path(__file__).with_name("_gates_{stem}.py")), run_name=__name__)\n'
            f'globals().update({{k:v for k,v in _g.items() if not k.startswith("__")}})\n',
            encoding="utf-8",
        )
allow_path.write_text(json.dumps(allow, indent=2) + "\n")
print("live_floors", len(allow.get("live_floors") or []), "aliases", len(ga), "peak_lock", allow.get("peak_lock"))

# gate_alias_resolve helper
(ROOT / "bot" / "gate_alias_resolve.py").write_text('''\
from __future__ import annotations
import json
from pathlib import Path
_PATH = Path(__file__).resolve().parent / "data" / "luxury_live_floors.json"

def resolve_gate(floor: str) -> str:
    name = (floor or "LIVE").strip().upper()
    try:
        data = json.loads(_PATH.read_text(encoding="utf-8"))
    except Exception:
        data = {}
    if name in {str(x).upper() for x in (data.get("blocked") or [])}:
        return name
    return str((data.get("gate_aliases") or {}).get(name, name))

resolve_gate_stem = resolve_gate

def live_floors():
    try:
        data = json.loads(_PATH.read_text(encoding="utf-8"))
        return [str(x).upper() for x in (data.get("live_floors") or [])]
    except Exception:
        return ["LIVE"]
''')
print("gate_alias_resolve OK")
PY

echo "========== [7/7] start supervisor + verify =========="
set -a; source ./luxury_building.env; set +a
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
sleep 16

echo "===== PROCS ====="
pgrep -af 'runtime_supervisor|bacbo_royal|fallback_signal|fallback_result' || true

echo "===== BOT (key lines) ====="
grep -E 'get_entity uses room_entity|monkeypatch|failed first resolve|Could not resolve|run_forever|BootGrace|GameCoach|CrashGuard|NameError|SyntaxError|send\(\) failed' logs/bot_live.log | tail -n 40 || true
echo "----- tail -----"
tail -n 25 logs/bot_live.log

echo "===== FALLBACK ====="
tail -n 12 logs/fallback_sender.log
tail -n 8 logs/fallback_result_sender.log

$PY <<'PY'
import json, sqlite3, time, subprocess
from pathlib import Path
time.sleep(3)
print("PROCS", subprocess.getoutput('pgrep -af "bacbo_royal|fallback_signal|fallback_result|runtime_supervisor"'))
c = json.loads(Path("bot/data/room_entity_cache.json").read_text())
print("cache dialogs", c.get("dialogs_scanned"), "usernames", len(c.get("by_username") or {}) // 2)
db = "bot/bacbo.db" if Path("bot/bacbo.db").exists() else "bacbo.db"
con = sqlite3.connect(db)
print("LAST_SIGNALS")
for r in con.execute(
    "select id, fired_at, signal_kind, color, source_floor from consensus_signals order by id desc limit 10"
):
    print(r)
print("ERRORS_RECENT")
print(subprocess.getoutput("grep -E 'NameError|SyntaxError|CrashGuard|send\\(\\) failed' logs/bot_live.log | tail -n 8"))
PY

echo
echo "DONE. Paste ALL of this output back to Cursor."
echo "Success look: all 4 procs up, 'get_entity uses room_entity_cache', few/no new Could not resolve."
