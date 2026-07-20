#!/usr/bin/env bash
# ONE paste: full clean fix. Room resolve uses dialog peer_id+access_hash (no ResolveUsername).
set -euo pipefail
cd /home/runner/workspace
PY=python3

echo "========== [1/8] kill stale =========="
pkill -9 -f 'runtime_supervisor.py' 2>/dev/null || true
pkill -9 -f 'bacbo_royal_complete.py' 2>/dev/null || true
pkill -9 -f 'fallback_signal_sender.py' 2>/dev/null || true
pkill -9 -f 'fallback_result_sender.py' 2>/dev/null || true
sleep 2
pgrep -af 'bacbo_royal|fallback_|runtime_supervisor' || echo "(clear)"

echo "========== [2/8] tz + session + env =========="
$PY <<'PY'
from pathlib import Path
import os
ROOT = Path("/home/runner/workspace")
TZ = '''"""Timezone helpers."""
from __future__ import annotations
import os
from datetime import datetime, timezone
try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None
_BOT_TZ = os.environ.get("BOT_TZ") or "America/Sao_Paulo"
DISPLAY_TZ = _BOT_TZ
def _zone():
    if ZoneInfo is None: return timezone.utc
    try: return ZoneInfo(_BOT_TZ)
    except Exception: return timezone.utc
def now_local(): return datetime.now(tz=_zone())
local_now = now_local
def now_utc(): return datetime.now(timezone.utc)
def local_hour(dt=None):
    d = now_local() if dt is None else dt
    if getattr(d,"tzinfo",None) is None: d=d.replace(tzinfo=timezone.utc)
    return d.astimezone(_zone()).hour
def today_iso(dt=None):
    d = now_local() if dt is None else dt
    if getattr(d,"tzinfo",None) is None: d=d.replace(tzinfo=timezone.utc)
    return d.astimezone(_zone()).date().isoformat()
def ts(dt=None):
    d = now_local() if dt is None else dt
    if getattr(d,"tzinfo",None) is None: d=d.replace(tzinfo=timezone.utc).astimezone(_zone())
    else: d=d.astimezone(_zone())
    return d.strftime("%Y-%m-%d %H:%M:%S")
def dts(dt=None):
    d = now_local() if dt is None else dt
    if getattr(d,"tzinfo",None) is None: d=d.replace(tzinfo=timezone.utc).astimezone(_zone())
    else: d=d.astimezone(_zone())
    return d.isoformat(sep=" ", timespec="seconds")
'''
(ROOT/"tz_utils.py").write_text(TZ)
(ROOT/"bot"/"tz_utils.py").write_text(TZ)

# session
sp = ROOT/".telegram_session_string"
if not sp.exists() or len(sp.read_text(errors="ignore").strip())<=50:
    env={}
    if (ROOT/".env").exists():
        for ln in (ROOT/".env").read_text().splitlines():
            if "=" in ln and not ln.strip().startswith("#"):
                k,v=ln.split("=",1); env[k.strip()]=v.strip().strip('"').strip("'")
    for key in ("TELEGRAM_SESSION_STRING","TELEGRAM_STRING_SESSION"):
        v=(os.environ.get(key) or env.get(key) or "").strip()
        if len(v)>50: sp.write_text(v+"\n"); break
    else:
        if (ROOT/"userbot_session.session").exists():
            from telethon.sync import TelegramClient
            from telethon.sessions import StringSession
            api_id=os.environ.get("TELEGRAM_API_ID") or env.get("TELEGRAM_API_ID")
            api_hash=os.environ.get("TELEGRAM_API_HASH") or env.get("TELEGRAM_API_HASH")
            c=TelegramClient(str(ROOT/"userbot_session"), int(api_id), api_hash); c.connect()
            if c.is_user_authorized():
                s=StringSession.save(c.session); sp.write_text(s+"\n"); print("converted session", len(s))
            c.disconnect()
print("session_len", len(sp.read_text().strip()))

PEER="6774605259"
(ROOT/"bot"/"data").mkdir(parents=True, exist_ok=True)
(ROOT/"bot"/"data"/"telegram_target_entity.json").write_text('{"target":"@Mr_iv4","id":6774605259}\n')
(ROOT/"luxury_building.env").write_text(
    "export EDGE_POLICY_MODE=luxury\nexport EDGE_LUXURY_FLOOR_GATE=1\n"
    "export FALLBACK_SEND_BLOCKED=0\nexport BOT_TZ=America/Sao_Paulo\n"
    f"export TELEGRAM_TARGET_PEER={PEER}\n"
)
lines=[]
if (ROOT/".env").exists():
    for ln in (ROOT/".env").read_text().splitlines():
        if ln.startswith("TELEGRAM_SESSION_STRING=") and len(ln.split("=",1)[1].strip().strip('"').strip("'"))<=50:
            continue
        if ln.startswith(("EDGE_POLICY_MODE=","EDGE_LUXURY_FLOOR_GATE=","FALLBACK_SEND_BLOCKED=","BOT_TZ=","TELEGRAM_TARGET_PEER=")):
            continue
        lines.append(ln)
lines += ["EDGE_POLICY_MODE=luxury","EDGE_LUXURY_FLOOR_GATE=1","FALLBACK_SEND_BLOCKED=0","BOT_TZ=America/Sao_Paulo",f"TELEGRAM_TARGET_PEER={PEER}"]
(ROOT/".env").write_text("\n".join(lines)+"\n")
print("env OK")
PY

echo "========== [3/8] rich room cache (peer_id + access_hash + type) =========="
$PY <<'PY'
import asyncio, json, os, sys
from pathlib import Path
ROOT = Path("/home/runner/workspace")
sys.path.insert(0, str(ROOT/"bot"))
for ln in (ROOT/".env").read_text().splitlines() if (ROOT/".env").exists() else []:
    if "=" in ln and not ln.strip().startswith("#"):
        k,v=ln.split("=",1); os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

from telethon import TelegramClient, utils
from telethon.sessions import StringSession
from telethon.tl.types import User, Chat, Channel

sess=(ROOT/".telegram_session_string").read_text().strip()
client=TelegramClient(StringSession(sess), int(os.environ["TELEGRAM_API_ID"]), os.environ["TELEGRAM_API_HASH"])

async def main():
    await client.connect()
    by_user={}
    n=0
    async for d in client.iter_dialogs():
        ent=d.entity
        n+=1
        uname=(getattr(ent,"username",None) or "").lower()
        if not uname:
            continue
        peer_id=int(utils.get_peer_id(ent))
        access_hash=getattr(ent,"access_hash",None)
        if isinstance(ent, Channel):
            et="channel"; raw_id=int(ent.id)
        elif isinstance(ent, Chat):
            et="chat"; raw_id=int(ent.id); access_hash=None
        elif isinstance(ent, User):
            et="user"; raw_id=int(ent.id)
        else:
            et="unknown"; raw_id=int(getattr(ent,"id",0) or 0)
        rec={
            "peer_id": peer_id,
            "raw_id": raw_id,
            "access_hash": int(access_hash) if access_hash is not None else None,
            "type": et,
            "title": getattr(ent,"title",None) or getattr(ent,"first_name",None) or "",
        }
        by_user[uname]=rec
        by_user["@"+uname]=rec
    await client.disconnect()
    path=ROOT/"bot"/"data"/"room_entity_cache.json"
    path.write_text(json.dumps({"by_username": by_user, "dialogs_scanned": n, "version": 2}, indent=2)+"\n")
    print("dialogs", n, "cached_usernames", len(by_user)//2)
    for u in ["rqdados","m8sinais","bacbo","coringadados","isadados","sinal_bac_bo","m8sinais"]:
        print(" ", u, "->", by_user.get(u))

asyncio.run(main())
PY

echo "========== [4/8] restore bacbo + CORRECT get_entity patch (no ResolveUsername fallback) =========="
$PY <<'PY'
from pathlib import Path
import re, ast, shutil
ROOT=Path("/home/runner/workspace")
p=ROOT/"bacbo_royal_complete.py"
bak=ROOT/"bacbo_royal_complete.py.bak_pre_state_fix"
shutil.copy2(bak, p)
src=p.read_text(encoding="utf-8", errors="replace")
for marker in ("LUXURY_STATE_INIT","LUXURY_SESSION_FILE_FORCE","LUXURY_BIND_PROXY","LUXURY_SESSION_AND_BIND","LUXURY_GET_ENTITY_MONKEYPATCH","LUXURY_COMMANDS_GUARD","LUXURY_ROOM_CACHE_RESOLVE"):
    src=re.sub(rf"\n# --- {marker} \(auto\) ---.*?(?=\n# --- |\nstate\.client\s*=|\n# ──|\Z)", "\n", src, flags=re.S)
src=re.sub(r"\nclass _LuxBotState:.*?\nstate = _LuxBotState\(\)\n+", "\n", src, flags=re.S)
src=re.sub(r"\nimport state  # LUXURY:[^\n]*\n", "\n", src)
src=re.sub(r"\nimport config  # LUXURY:[^\n]*\n", "\n", src)
src=re.sub(r"^import config\n", "", src, count=1, flags=re.M)

# early config
lines=src.splitlines(True)
idx=0
for i,ln in enumerate(lines[:40]):
    if ln.startswith("from __future__"):
        idx=i+1; break
lines.insert(idx, "import config\n")
src="".join(lines)

monkey='''
# --- LUXURY_GET_ENTITY_MONKEYPATCH (auto) ---
try:
    import json as _lux_json
    from pathlib import Path as _LuxPath
    from telethon import TelegramClient as _LuxTGClient
    from telethon.tl.types import InputPeerUser, InputPeerChannel, InputPeerChat
    from telethon.errors import FloodWaitError as _LuxFloodWait

    def _lux_cache_rec(username):
        try:
            p = _LuxPath("/home/runner/workspace/bot/data/room_entity_cache.json")
            data = _lux_json.loads(p.read_text(encoding="utf-8"))
            m = data.get("by_username") or {}
            key = str(username or "").strip().lower()
            for k in (key, key.lstrip("@"), "@" + key.lstrip("@")):
                if k in m:
                    return m[k]
        except Exception:
            return None
        return None

    def _lux_input_peer(rec):
        if not isinstance(rec, dict):
            return None
        et = rec.get("type")
        ah = rec.get("access_hash")
        raw = rec.get("raw_id")
        peer_id = rec.get("peer_id")
        if et == "channel" and raw is not None and ah is not None:
            return InputPeerChannel(int(raw), int(ah))
        if et == "user" and raw is not None and ah is not None:
            return InputPeerUser(int(raw), int(ah))
        if et == "chat" and raw is not None:
            return InputPeerChat(int(raw))
        if peer_id is not None:
            return int(peer_id)
        return None

    _lux_orig_get_entity = _LuxTGClient.get_entity

    async def _lux_get_entity(self, entity):
        # Warm dialogs once so session entity cache is populated
        if not getattr(self, "_lux_dialogs_warmed", False):
            try:
                async for _ in self.iter_dialogs():
                    pass
            except Exception as e:
                print("[LUXURY] dialog warm failed:", e)
            self._lux_dialogs_warmed = True

        if isinstance(entity, str) and not str(entity).lstrip("-").isdigit():
            rec = _lux_cache_rec(entity)
            if rec is not None:
                # 1) InputPeer with access_hash (best)
                inp = _lux_input_peer(rec)
                if inp is not None:
                    try:
                        return await _lux_orig_get_entity(self, inp)
                    except Exception as e1:
                        # 2) marked peer_id
                        try:
                            return await _lux_orig_get_entity(self, int(rec["peer_id"]))
                        except Exception as e2:
                            print(f"[LUXURY] cache resolve failed for {entity}: {e1!r} / {e2!r}")
                            raise
            # NOT cached: do NOT call ResolveUsername while flooded — raise soft error
            raise ValueError(f"LUXURY_SKIP_RESOLVE_USERNAME:{entity}")

        try:
            return await _lux_orig_get_entity(self, entity)
        except _LuxFloodWait:
            raise

    _LuxTGClient.get_entity = _lux_get_entity  # type: ignore
    print("[LUXURY] get_entity: dialog cache + InputPeer (no ResolveUsername for @rooms)")
except Exception as _lux_mp_exc:
    print("[LUXURY] get_entity monkeypatch skipped:", _lux_mp_exc)
# --- end LUXURY_GET_ENTITY_MONKEYPATCH ---
'''

# insert after telethon import
lines=src.splitlines(True)
idx=0
for i,ln in enumerate(lines[:120]):
    if "telethon" in ln and (ln.startswith("import ") or ln.startswith("from ")):
        idx=i+1
if idx==0:
    idx=30
lines.insert(idx, monkey+"\n")
src="".join(lines)

# session+bind
bind='''
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
# Critical: bare `state.engine = ...` lines below need this name
state = _lux_state_mod
# --- end LUXURY_SESSION_AND_BIND ---
'''
m=re.search(r"^state\.client\s*=\s*TelegramClient\([^\n]*\)\s*$", src, re.M)
if not m:
    raise SystemExit("missing state.client assign")
src=src[:m.start()]+bind+"\n"+src[m.end():]

# Soft-catch LUXURY_SKIP in resolve loops if present — patch "Could not resolve" printers to ignore skip
# (optional; ValueError will be caught by existing except)

p.write_text(src, encoding="utf-8")
ast.parse(src)
print("bacbo OK", p.stat().st_size)
PY

echo "========== [5/8] state proxy + commands restore + fallbacks =========="
$PY <<'PY'
from pathlib import Path
import ast, shutil, re
ROOT=Path("/home/runner/workspace")

# restore commands if broken
cbak=ROOT/"bot"/"commands.py.bak_pre_client_fix"
cmd=ROOT/"bot"/"commands.py"
if cbak.exists():
    shutil.copy2(cbak, cmd)
    print("commands restored from bak")
else:
    # try remove luxury junk
    t=cmd.read_text(encoding="utf-8", errors="replace")
    t2=re.sub(r"\n# --- LUXURY_[\w]+ \(auto\) ---.*?(?=\n@|\nasync def |\ndef |\Z)", "\n", t, flags=re.S)
    try:
        ast.parse(t2); cmd.write_text(t2); print("commands cleaned")
    except SyntaxError:
        print("WARN commands still broken — check manually")
ast.parse(cmd.read_text(encoding="utf-8"))

# state proxy
sp=ROOT/"bot"/"state.py"
st_bak=ROOT/"bot"/"state.py.bak_pre_proxy"
if st_bak.exists():
    st=st_bak.read_text(encoding="utf-8")
else:
    st=sp.read_text(encoding="utf-8", errors="replace")
    if not st_bak.exists():
        st_bak.write_text(sp.read_text(encoding="utf-8", errors="replace"))
st=re.sub(r"\n# --- LUXURY_CLIENT_PROXY \(auto\) ---.*?(?=\Z)", "\n", st, flags=re.S)
proxy='''
# --- LUXURY_CLIENT_PROXY (auto) ---
class _LuxClientProxy:
    def __init__(self):
        self._client=None; self._pending=[]
    def bind(self, client):
        self._client=client
        for event, func in list(self._pending):
            try: client.add_event_handler(func, event)
            except Exception as e: print("[LUXURY] pending handler failed:", e)
        self._pending.clear(); return client
    def on(self, event):
        def deco(func):
            if self._client is not None: self._client.add_event_handler(func, event)
            else: self._pending.append((event, func))
            return func
        return deco
    def __bool__(self): return self._client is not None
    def __getattr__(self, name):
        if self._client is None: raise AttributeError(name)
        return getattr(self._client, name)
if client is None or not hasattr(client, "on"):
    client = _LuxClientProxy()
# --- end LUXURY_CLIENT_PROXY ---
'''
if re.search(r"^client\s*=\s*None\s*$", st, re.M):
    st=re.sub(r"^client\s*=\s*None\s*$", "client = None\n"+proxy, st, count=1, flags=re.M)
else:
    st=st.rstrip()+"\nclient = None\n"+proxy+"\n"
sp.write_text(st); ast.parse(st); print("state proxy OK")

HELPER='''
def _load_telegram_session() -> str:
    import os
    from pathlib import Path
    for key in ("TELEGRAM_SESSION_STRING", "TELEGRAM_STRING_SESSION"):
        v=(os.environ.get(key) or "").strip()
        if len(v)>50: return v
    return Path("/home/runner/workspace/.telegram_session_string").read_text().strip()

async def _resolve_target(client, target):
    import os
    peer=os.environ.get("TELEGRAM_TARGET_PEER") or "6774605259"
    return await client.get_entity(int(peer))
'''
for rel in ["bot/fallback_signal_sender.py","bot/fallback_result_sender.py"]:
    p=ROOT/rel
    bak=Path(str(p)+".bak_pre_session_fix")
    if bak.exists(): shutil.copy2(bak,p)
    t=p.read_text(encoding="utf-8", errors="replace")
    t=re.sub(r"\n# --- LUXURY_[\w]+ \(auto\) ---.*?(?=\nasync def |\ndef |\Z)", "\n", t, flags=re.S)
    t=re.sub(r"\nasync def _resolve_target\([\s\S]*?\n(?=async def main)", "\n", t)
    t=re.sub(r"\ndef _load_telegram_session\([\s\S]*?\n(?=async def |\ndef )", "\n", t)
    t=re.sub(r"\nasync def _lux_sleep_flood\([\s\S]*?\n(?=async def |\ndef )", "\n", t)
    t=re.sub(r"\n[ \t]+if 'FloodWait' in type\(\w+\)\.__name__:[\s\S]*?continue\n", "\n", t)
    if "def _load_telegram_session" not in t:
        t=t.replace("async def main", HELPER+"\nasync def main", 1)
    t=t.replace('session = (ROOT / ".telegram_session_string").read_text().strip()', "session = _load_telegram_session()")
    t=t.replace("entity = await client.get_entity(target)", "entity = await _resolve_target(client, target)")
    p.write_text(t); compile(t, rel, "exec"); print(rel, "OK")

# restore utils if room-flood broke it
ubak=ROOT/"bot"/"utils.py.bak_pre_room_cache"
if ubak.exists():
    shutil.copy2(ubak, ROOT/"bot"/"utils.py")
    print("utils restored from pre_room_cache bak")
PY

echo "========== [6/8] peak-lock loaders + allowlist =========="
$PY <<'PY'
import json
from pathlib import Path
ROOT=Path("/home/runner/workspace"); DATA=ROOT/"bot"/"data"
allow_path=DATA/"luxury_live_floors.json"
allow=json.loads(allow_path.read_text()) if allow_path.exists() else {}
allow.setdefault("blocked", ["JUN12A","JUN12B"])
allow["peak_lock"]=True
ga=allow.setdefault("gate_aliases", {})
ga.update({"LIVE":"ELITE_V2","JUN19":"JUN19_peak","JUN20":"JUN20_peak","JUN08":"JUN08_peak","JUN10":"JUN10_peak","MAY19":"MAY19_peak","MAY10":"MAY10_peak","MAY11":"MAY11_peak","MAY01":"MAY01_peak","APR19":"APR19_golden","APR20":"APR20_perfect","APR30":"APR30_peak","ELITE_V2":"ELITE_V2","ULTIMATE":"ULTIMATE"})
locked=0
for logical, stem in ga.items():
    if logical in ("JUN12A","JUN12B") or logical==stem: continue
    peak=ROOT/"bot"/f"_gates_{stem}.py"
    if peak.exists():
        (ROOT/"bot"/f"_gates_{logical}.py").write_text(
            f'from pathlib import Path\nimport runpy\n_g=runpy.run_path(str(Path(__file__).with_name("_gates_{stem}.py")), run_name=__name__)\nglobals().update({{k:v for k,v in _g.items() if not k.startswith("__")}})\n'
        ); locked+=1
allow_path.write_text(json.dumps(allow, indent=2)+"\n")
print("peak_loaders", locked, "live", len(allow.get("live_floors") or []))
PY

echo "========== [7/8] patch room-resolve to treat LUXURY_SKIP as soft fail =========="
$PY <<'PY'
from pathlib import Path
import re
# In bacbo/utils, if except logs "Could not resolve", also ignore LUXURY_SKIP
for fp in [Path("bacbo_royal_complete.py"), Path("bot/utils.py")]:
    if not fp.exists(): continue
    t=fp.read_text(encoding="utf-8", errors="replace")
    if "LUXURY_SKIP_RESOLVE_USERNAME" in t and "soft skip" in t:
        print(fp, "already soft"); continue
    # add helper note near monkeypatch is enough; resolve loops usually `except Exception as e: log Could not resolve`
    # Improve log line to not look like hard flood when skip:
    t2=t.replace(
        'Could not resolve',
        'Could not resolve',
    )
    # Inject into except blocks that format Could not resolve — prepend skip check via replace of common pattern
    pat=r'(except Exception as (\w+):\n)([ \t]+)(log\.|logger\.|print\()([^\n]*Could not resolve[^\n]*)'
    def repl(m):
        ind=m.group(3); var=m.group(2)
        return (
            f"{m.group(1)}"
            f"{ind}if 'LUXURY_SKIP_RESOLVE_USERNAME' in str({var}):\n"
            f"{ind}    pass  # soft skip — not in dialog cache; do not ResolveUsername\n"
            f"{ind}else:\n"
            f"{ind}    {m.group(4)}{m.group(5)}"
        )
    t3=re.sub(pat, repl, t2, count=20)
    # continue only valid in loops — if this breaks syntax, skip
    try:
        compile(t3, str(fp), "exec")
        fp.write_text(t3); print(fp, "soft-skip injected", t3!=t)
    except SyntaxError:
        print(fp, "soft-skip skipped (syntax)")
PY

echo "========== [8/8] start + verify =========="
set -a; source ./luxury_building.env; set +a
export TELEGRAM_SESSION_STRING="$(tr -d '\n' < .telegram_session_string)"
export TELEGRAM_TARGET_PEER=6774605259

nohup env EDGE_POLICY_MODE=luxury EDGE_LUXURY_FLOOR_GATE=1 FALLBACK_SEND_BLOCKED=0 \
  BOT_TZ=America/Sao_Paulo \
  TELEGRAM_SESSION_STRING="$TELEGRAM_SESSION_STRING" \
  TELEGRAM_TARGET_PEER=6774605259 \
  python3 -u bot/runtime_supervisor.py > /tmp/luxury_supervisor.log 2>&1 &
echo "supervisor pid=$!"
sleep 18

echo "===== PROCS ====="
pgrep -af 'runtime_supervisor|bacbo_royal|fallback_signal|fallback_result' || true

echo "===== KEY LOGS ====="
grep -E 'get_entity: dialog cache|InputPeer|failed first resolve|ResolveUsername|run_forever|BootGrace|GameCoach|CrashGuard|NameError|SyntaxError|rooms failed|joined|Listening' logs/bot_live.log | tail -n 50 || true
echo "----- tail -----"
tail -n 40 logs/bot_live.log

echo "===== FALLBACK ====="
tail -n 8 logs/fallback_sender.log
tail -n 6 logs/fallback_result_sender.log

$PY <<'PY'
import json, re, subprocess, time
from pathlib import Path
time.sleep(5)
print("PROCS", subprocess.getoutput('pgrep -af "bacbo_royal|fallback_signal|fallback_result|runtime_supervisor"'))
c=json.loads(Path("bot/data/room_entity_cache.json").read_text())
print("cache_v", c.get("version"), "dialogs", c.get("dialogs_scanned"), "users", len(c.get("by_username") or {})//2)
log=Path("logs/bot_live.log").read_text(errors="ignore")
# count flood vs cache-fail vs success after last supervisor start
tail=log.split("supervisor starting bot_live")[-1] if "supervisor starting bot_live" in log else log[-20000:]
flood=len(re.findall(r"ResolveUsernameRequest", tail))
peer_miss=len(re.findall(r"Could not find the input entity", tail))
skip=len(re.findall(r"LUXURY_SKIP_RESOLVE_USERNAME", tail))
print("since_last_start ResolveUsername hits", flood, "PeerUser miss", peer_miss, "skip", skip)
print("monkeypatch_line", "dialog cache + InputPeer" in tail or "get_entity: dialog cache" in log[-5000:])
# failed count line
m=re.findall(r"(\d+) rooms failed first resolve", tail)
print("rooms_failed_first_resolve", m[-1] if m else "?")
PY

echo
echo "DONE. Paste ALL output to Cursor."
echo "WIN = ResolveUsername hits near 0, rooms_failed much lower than 78, bot stays on run_forever."
