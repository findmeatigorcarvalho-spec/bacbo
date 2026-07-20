#!/usr/bin/env bash
# Bypass Telegram ResolveUsername FloodWait by caching room peers from dialogs.
set -euo pipefail
cd /home/runner/workspace

echo "========== [1/4] build room entity cache from dialogs (no ResolveUsername) =========="
python3 - <<'PY'
import asyncio, json, os, sys
from pathlib import Path

ROOT = Path("/home/runner/workspace")
sys.path.insert(0, str(ROOT / "bot"))
sys.path.insert(0, str(ROOT))

# load .env
for line in (ROOT / ".env").read_text().splitlines() if (ROOT / ".env").exists() else []:
    if "=" in line and not line.strip().startswith("#"):
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

sess = (ROOT / ".telegram_session_string").read_text().strip()
api_id = os.environ["TELEGRAM_API_ID"]
api_hash = os.environ["TELEGRAM_API_HASH"]

from telethon import TelegramClient
from telethon.sessions import StringSession

cache_path = ROOT / "bot" / "data" / "room_entity_cache.json"
cache_path.parent.mkdir(parents=True, exist_ok=True)

async def main():
    client = TelegramClient(StringSession(sess), int(api_id), api_hash)
    await client.connect()
    if not await client.is_user_authorized():
        raise SystemExit("session not authorized")
    by_user = {}
    by_id = {}
    n = 0
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
    data = {"by_username": by_user, "by_id": by_id, "dialogs_scanned": n}
    cache_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print("dialogs_scanned", n, "usernames_cached", len(by_user) // 2, "wrote", cache_path)
    # show a few expected rooms
    for u in ["rqdados", "m8sinais", "bacbo", "coringadados", "mr_iv4"]:
        print(" ", u, "->", by_user.get(u) or by_user.get("@" + u))

asyncio.run(main())
PY

echo "========== [2/4] patch resolve paths to use cache before ResolveUsername =========="
python3 - <<'PY'
from pathlib import Path
import re, ast

ROOT = Path("/home/runner/workspace")
HELPER = r'''
# --- LUXURY_ROOM_CACHE_RESOLVE (auto) ---
def _lux_cached_entity_id(username):
    """Return cached numeric id for @username from dialogs cache, or None."""
    try:
        import json
        from pathlib import Path
        p = Path("/home/runner/workspace/bot/data/room_entity_cache.json")
        if not p.exists():
            return None
        data = json.loads(p.read_text(encoding="utf-8"))
        key = str(username or "").strip()
        low = key.lower()
        m = data.get("by_username") or {}
        if low in m:
            return int(m[low])
        if low.lstrip("@") in m:
            return int(m[low.lstrip("@")])
        if ("@" + low.lstrip("@")) in m:
            return int(m["@" + low.lstrip("@")])
    except Exception:
        return None
    return None
'''

patched = []
# Patch any .py that logs "Could not resolve" or calls get_entity on room usernames
candidates = list(ROOT.glob("*.py")) + list((ROOT / "bot").glob("*.py"))
for fp in candidates:
    if fp.name.startswith("_gates_"):
        continue
    try:
        t = fp.read_text(encoding="utf-8", errors="replace")
    except Exception:
        continue
    if "Could not resolve" not in t and "ResolveUsername" not in t and "get_entity" not in t:
        continue
    if "LUXURY_ROOM_CACHE_RESOLVE" in t:
        continue
    # Only touch files that look like room resolvers
    if not any(x in t for x in ("Could not resolve", "failed first resolve", "get_entity(", "ResolveUsername")):
        continue
    if "Could not resolve" not in t and "failed first resolve" not in t:
        # skip generic get_entity files unless bacbo main / utils / auto_discover
        if fp.name not in ("bacbo_royal_complete.py", "utils.py", "auto_discover.py", "signal_handler.py", "background.py"):
            continue

    orig = t
    # inject helper near top after imports
    if "def _lux_cached_entity_id" not in t:
        # place after future/imports
        lines = t.splitlines(True)
        idx = 0
        for i, ln in enumerate(lines[:100]):
            if ln.startswith("from __future__") or ln.startswith("import ") or ln.startswith("from ") or not ln.strip() or ln.strip().startswith("#") or ln.strip().startswith('"""') or ln.strip().startswith("'''"):
                idx = i + 1
            elif i < 5:
                idx = i + 1
            else:
                break
        lines.insert(idx, HELPER + "\n")
        t = "".join(lines)

    # Wrap common patterns: await client.get_entity("@foo") / get_entity(room)
    # Replace: await X.get_entity(Y) when Y looks like username variable — too broad.
    # Instead patch functions that contain "Could not resolve"
    if "Could not resolve" in t and "_lux_cached_entity_id(" not in orig:
        # Before get_entity calls in resolve loops, try cache.
        # Pattern used by many bots:
        #   entity = await client.get_entity(uname)
        #   entity = await self.client.get_entity(room)
        def repl_get_entity(match):
            prefix = match.group(1)  # await ...
            client_expr = match.group(2)
            arg = match.group(3)
            return (
                f"{prefix}("
                f"_lux_cached_entity_id({arg}) if _lux_cached_entity_id({arg}) is not None "
                f"else {arg})"
            )
        # Safer explicit rewrite for `await <expr>.get_entity(<arg>)`
        t2 = re.sub(
            r"(await\s+)([A-Za-z_][\w\.]*?)\.get_entity\(([^)]+)\)",
            r"\1\2.get_entity((_lux_id := _lux_cached_entity_id(\3)) if _lux_id is not None else \3)",
            t,
        )
        # walrus in await may be ok in 3.11; but nested assign in call is fine
        # Actually simplify — avoid walrus issues in some contexts:
        t2 = t
        # Only rewrite inside functions that mention Could not resolve — line based
        lines = t.splitlines(True)
        out = []
        in_resolveish = False
        depth_hint = 0
        for ln in lines:
            if "def " in ln and any(k in ln for k in ("resolve", "Resolve", "join", "room", "startup", "bootstrap")):
                in_resolveish = True
            if in_resolveish and re.search(r"await\s+.+\.get_entity\(", ln) and "_lux_cached_entity_id" not in ln:
                # transform single-line get_entity
                m = re.search(r"^(?P<ind>\s*)(?P<left>[^=]*=\s*)?await\s+(?P<cli>[A-Za-z_][\w\.]*?)\.get_entity\((?P<arg>[^)]+)\)(?P<rest>.*)$", ln)
                if m:
                    ind = m.group("ind")
                    left = m.group("left") or ""
                    cli = m.group("cli")
                    arg = m.group("arg")
                    rest = m.group("rest")
                    block = (
                        f"{ind}_lux_eid = _lux_cached_entity_id({arg})\n"
                        f"{ind}{left}await {cli}.get_entity(_lux_eid if _lux_eid is not None else {arg}){rest}\n"
                    )
                    out.append(block)
                    continue
            out.append(ln)
        t = "".join(out)

    if t != orig:
        bak = fp.with_suffix(fp.suffix + ".bak_pre_room_cache")
        if not bak.exists():
            bak.write_text(orig, encoding="utf-8")
        try:
            ast.parse(t)
            fp.write_text(t, encoding="utf-8")
            patched.append(fp.name)
        except SyntaxError as e:
            print("SKIP syntax", fp.name, e)

print("patched_files", patched or ["(none — injecting sitecustomize-style hook in bacbo)"])

# Always inject a bootstrap in bacbo that monkeypatches TelegramClient.get_entity
bacbo = Path("bacbo_royal_complete.py")
bsrc = bacbo.read_text(encoding="utf-8", errors="replace")
if "LUXURY_GET_ENTITY_MONKEYPATCH" not in bsrc:
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
            if key in m:
                return int(m[key])
            k2 = key.lstrip("@")
            if k2 in m:
                return int(m[k2])
            if ("@" + k2) in m:
                return int(m["@" + k2])
        except Exception:
            return None
        return None

    _lux_orig_get_entity = _LuxTGClient.get_entity

    async def _lux_get_entity(self, entity):
        # If string username / @user — prefer dialog cache to avoid ResolveUsername FloodWait
        if isinstance(entity, str) and not entity.lstrip("-").isdigit():
            eid = _lux_cached_entity_id(entity)
            if eid is not None:
                entity = eid
        return await _lux_orig_get_entity(self, entity)

    _LuxTGClient.get_entity = _lux_get_entity  # type: ignore
    print("[LUXURY] TelegramClient.get_entity monkeypatched to use room_entity_cache")
except Exception as _lux_mp_exc:
    print("[LUXURY] get_entity monkeypatch skipped:", _lux_mp_exc)
# --- end LUXURY_GET_ENTITY_MONKEYPATCH ---
'''
    # insert after telethon imports if possible, else after first import block
    lines = bsrc.splitlines(True)
    idx = 0
    for i, ln in enumerate(lines[:120]):
        if "telethon" in ln and (ln.startswith("import ") or ln.startswith("from ")):
            idx = i + 1
        elif ln.startswith("import ") or ln.startswith("from ") or ln.startswith("from __future__"):
            if idx == 0 or i < 80:
                idx = i + 1
    if idx == 0:
        idx = 20
    lines.insert(idx, monkey + "\n")
    bsrc2 = "".join(lines)
    try:
        ast.parse(bsrc2)
        bacbo.write_text(bsrc2, encoding="utf-8")
        print("injected get_entity monkeypatch into bacbo_royal_complete.py")
    except SyntaxError as e:
        print("monkeypatch inject failed", e)
else:
    print("monkeypatch already present")
PY

echo "========== [3/4] ensure early import config + luxury env =========="
python3 - <<'PY'
from pathlib import Path
import re, ast
p = Path("bacbo_royal_complete.py")
src = p.read_text(encoding="utf-8", errors="replace")
# Force real `import config` within first 40 lines if missing
head = "\n".join(src.splitlines()[:40])
if not re.search(r"^(import config|from config import)\b", head, re.M):
    lines = src.splitlines(True)
    # after __future__
    idx = 0
    for i, ln in enumerate(lines[:30]):
        if ln.startswith("from __future__"):
            idx = i + 1
            break
    lines.insert(idx, "import config\n")
    src = "".join(lines)
    p.write_text(src, encoding="utf-8")
    ast.parse(src)
    print("inserted early import config")
else:
    print("early config import OK")

Path("luxury_building.env").write_text(
    "export EDGE_POLICY_MODE=luxury\n"
    "export EDGE_LUXURY_FLOOR_GATE=1\n"
    "export FALLBACK_SEND_BLOCKED=0\n"
    "export BOT_TZ=America/Sao_Paulo\n"
    "export TELEGRAM_TARGET_PEER=6774605259\n"
)
print("luxury env written")
PY

echo "========== [4/4] restart + verify =========="
pkill -9 -f 'runtime_supervisor.py' 2>/dev/null || true
pkill -9 -f 'bacbo_royal_complete.py' 2>/dev/null || true
pkill -9 -f 'fallback_signal_sender.py' 2>/dev/null || true
pkill -9 -f 'fallback_result_sender.py' 2>/dev/null || true
sleep 2

set -a; source ./luxury_building.env; set +a
export TELEGRAM_SESSION_STRING="$(tr -d '\n' < .telegram_session_string)"
export TELEGRAM_TARGET_PEER=6774605259

nohup env EDGE_POLICY_MODE=luxury EDGE_LUXURY_FLOOR_GATE=1 FALLBACK_SEND_BLOCKED=0 \
  BOT_TZ=America/Sao_Paulo \
  TELEGRAM_SESSION_STRING="$TELEGRAM_SESSION_STRING" \
  TELEGRAM_TARGET_PEER=6774605259 \
  python3 -u bot/runtime_supervisor.py > /tmp/luxury_supervisor.log 2>&1 &
echo "supervisor pid=$!"
sleep 15

echo "===== procs ====="
pgrep -af 'runtime_supervisor|bacbo_royal|fallback_signal|fallback_result' || true
echo "===== bot boot / resolve ====="
grep -E 'monkeypatch|room_entity|failed first resolve|Could not resolve|run_forever|BootGrace|GameCoach|ERROR|FloodWait' logs/bot_live.log | tail -n 40
echo "===== tail ====="
tail -n 30 logs/bot_live.log
echo "===== fallback ====="
tail -n 10 logs/fallback_sender.log
tail -n 8 logs/fallback_result_sender.log

python3 - <<'PY'
import json
from pathlib import Path
c=json.loads(Path('bot/data/room_entity_cache.json').read_text())
print('cache_usernames', len(c.get('by_username') or {})//2, 'dialogs', c.get('dialogs_scanned'))
# how many of the failed rooms are cached?
failed = ['rqdados','m8sinais','bacbo','coringadados','isadados','sinal_bac_bo','x8sinais']
m=c.get('by_username') or {}
for u in failed:
    print(u, m.get(u) or m.get('@'+u))
PY

echo
echo "DONE. Paste ALL output to Cursor."
echo "Expect: monkeypatch line + fewer 'Could not resolve' (cache hits)."
echo "FloodWait on ResolveUsername should stop; rooms in your dialogs will work."
