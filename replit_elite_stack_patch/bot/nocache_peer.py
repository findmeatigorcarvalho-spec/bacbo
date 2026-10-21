import asyncio, json, os
from telethon import utils as tu
from telethon.tl import types as t

_P = os.path.join(os.path.dirname(__file__), "data", "room_entity_cache.json")
_warm = None


def _key(handle):
    return str(handle).strip().lstrip("@").lower()


def _from_json(k):
    try:
        m = json.load(open(_P)).get("by_username") or {}
    except Exception:
        return None
    r = m.get(k) or m.get("@" + k)
    if not r or r.get("access_hash") is None:
        return None
    raw, h = int(r["raw_id"]), int(r["access_hash"])
    return t.InputPeerUser(raw, h) if r.get("type") == "user" else t.InputPeerChannel(raw, h)


def peer(handle):
    return _from_json(_key(handle))


def _from_session(client, k):
    try:
        row = client.session.get_entity_rows_by_username(k)
    except Exception:
        return None
    if not row:
        return None
    eid, h = tu.resolve_id(row[0])[0], row[1]
    kind = tu.resolve_id(row[0])[1]
    if kind is t.PeerChannel:
        return t.InputPeerChannel(eid, h)
    if kind is t.PeerUser:
        return t.InputPeerUser(eid, h)
    return None


def _save(k, ip):
    try:
        try:
            d = json.load(open(_P))
        except Exception:
            d = {}
        m = d.setdefault("by_username", {})
        if isinstance(ip, t.InputPeerChannel):
            rec = {"peer_id": -1000000000000 - ip.channel_id, "raw_id": ip.channel_id,
                   "access_hash": ip.access_hash, "type": "channel"}
        else:
            rec = {"peer_id": ip.user_id, "raw_id": ip.user_id,
                   "access_hash": ip.access_hash, "type": "user"}
        m[k] = rec
        m["@" + k] = rec
        tmp = _P + ".tmp"
        json.dump(d, open(tmp, "w"))
        os.replace(tmp, _P)
    except Exception:
        pass


async def _warm_dialogs(client):
    global _warm
    if _warm is None:
        _warm = asyncio.ensure_future(client.get_dialogs(limit=None))
    try:
        await asyncio.shield(_warm)
    except Exception:
        _warm = None


async def peer_async(handle, client):
    k = _key(handle)
    ip = _from_json(k)
    if ip:
        return ip
    ip = _from_session(client, k)
    if not ip:
        await _warm_dialogs(client)
        ip = _from_session(client, k)
    if ip:
        _save(k, ip)
    return ip
