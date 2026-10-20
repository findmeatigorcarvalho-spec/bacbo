import json, os
from telethon.tl import types as t
_P = os.path.join(os.path.dirname(__file__), "data", "room_entity_cache.json")
def peer(handle):
    try:
        m = json.load(open(_P)).get("by_username") or {}
    except Exception:
        return None
    k = str(handle).strip().lstrip("@").lower()
    r = m.get(k) or m.get("@" + k)
    if not r or r.get("access_hash") is None:
        return None
    raw, h = int(r["raw_id"]), int(r["access_hash"])
    return t.InputPeerUser(raw, h) if r.get("type") == "user" else t.InputPeerChannel(raw, h)
