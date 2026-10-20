import re
import sys

p = sys.argv[1] if len(sys.argv) > 1 else "utils.py"
s = open(p, encoding="utf-8").read()
if "_cache_input_peer" in s:
    print("already patched")
    sys.exit(0)

helper = '''def _cache_input_peer(handle):
    import json as _j
    import os as _o
    from telethon.tl import types as _t
    try:
        with open(_o.path.join(_o.path.dirname(__file__), "data", "room_entity_cache.json"), encoding="utf-8") as _f:
            _m = _j.load(_f).get("by_username") or {}
    except Exception:
        return None
    _key = str(handle).strip().lstrip("@").lower()
    _r = _m.get(_key) or _m.get("@" + _key)
    if not isinstance(_r, dict):
        return None
    _raw = int(_r.get("raw_id") or 0)
    _hash = _r.get("access_hash")
    _pid = int(_r.get("peer_id") or 0)
    _typ = str(_r.get("type") or "").lower()
    if not _raw:
        return None
    if _typ == "user" and _hash is not None:
        return _t.InputPeerUser(_raw, int(_hash))
    if (_typ in ("channel", "supergroup", "megagroup") or _pid < -1000000000000) and _hash is not None:
        return _t.InputPeerChannel(_raw, int(_hash))
    if _typ in ("chat", "group") and _pid < 0:
        return _t.InputPeerChat(_raw)
    return None


'''

m = re.search(r"^async def resolve_room\(handle: str\)[^\n]*\n", s, re.M)
if not m:
    sys.exit("resolve_room not found")
body_end = m.end() + 900
seg = s[m.end():body_end]
if "entity = await client.get_entity(handle)" not in seg:
    sys.exit("get_entity(handle) line not found in resolve_room")
seg = seg.replace(
    "entity = await client.get_entity(handle)",
    "entity = await client.get_entity(_cache_input_peer(handle) or handle)",
    1,
)
s = s[:m.start()] + helper + s[m.start():m.end()] + seg + s[body_end:]
open(p, "w", encoding="utf-8").write(s)
print("patched resolve_room: cached rooms resolve without username lookups")
