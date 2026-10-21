"""Stop ResolveUsername FloodWait: resolve @rooms via dialog cache / InputPeer.

Load BEFORE bacbo room join loop (run_bacbo_live). Never hammer Telegram
username resolve while flooded — use room_entity_cache.json + warm dialogs.

LUX_DIALOG_WARM:
  cache (default) — skip iter_dialogs when cache already has peers (low RSS)
  full            — always iter_dialogs (heavy; can OOM on Replit)
  0 / off         — never warm; cache-only resolve
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional

HERE = Path(__file__).resolve().parent
CACHE = HERE / "data" / "room_entity_cache.json"
_PATCHED = False


def _warm_mode() -> str:
    v = (os.environ.get("LUX_DIALOG_WARM", "cache") or "cache").strip().lower()
    if v in {"0", "false", "no", "off", "none"}:
        return "off"
    if v in {"1", "true", "yes", "full", "always"}:
        return "full"
    return "cache"


def _cache_count() -> int:
    try:
        if not CACHE.is_file():
            return 0
        data = json.loads(CACHE.read_text(encoding="utf-8"))
        m = data.get("by_username") or {}
        return len(m) if isinstance(m, dict) else 0
    except Exception:
        return 0


def _cache_rec(username: str) -> Optional[dict[str, Any]]:
    try:
        if not CACHE.is_file():
            return None
        data = json.loads(CACHE.read_text(encoding="utf-8"))
        m = data.get("by_username") or {}
        key = str(username or "").strip().lower()
        for k in (key, key.lstrip("@"), "@" + key.lstrip("@")):
            if k in m:
                rec = m[k]
                if isinstance(rec, dict):
                    return rec
                if isinstance(rec, int) or (isinstance(rec, str) and str(rec).lstrip("-").isdigit()):
                    return {"peer_id": int(rec)}
    except Exception:
        return None
    return None


def _input_peer(rec: dict[str, Any]):
    try:
        from telethon.tl.types import InputPeerChannel, InputPeerChat, InputPeerUser
    except Exception:
        return None
    et = rec.get("type")
    ah = rec.get("access_hash")
    raw = rec.get("raw_id")
    peer_id = rec.get("peer_id")
    try:
        if et == "channel" and raw is not None and ah is not None:
            return InputPeerChannel(int(raw), int(ah))
        if et == "user" and raw is not None and ah is not None:
            return InputPeerUser(int(raw), int(ah))
        if et == "chat" and raw is not None:
            return InputPeerChat(int(raw))
        if peer_id is not None:
            return int(peer_id)
    except Exception:
        return None
    return None


def apply() -> bool:
    global _PATCHED
    if _PATCHED:
        return True
    try:
        from telethon import TelegramClient
        from telethon.errors import FloodWaitError
    except Exception as exc:
        print("[LUXURY] dialog-resolve skip (no telethon):", repr(exc))
        return False

    orig = TelegramClient.get_entity
    if getattr(orig, "_lux_dialog_resolve", False):
        _PATCHED = True
        return True

    async def _get_entity(self, entity):  # noqa: ANN001
        # Last-line target safety: a direct engine path may bypass config
        # routing. Never pass a blank peer to Telethon.
        if entity is None or (isinstance(entity, str) and not entity.strip().strip("@")):
            try:
                from hub_engine_route import apex_target

                entity = apex_target()
            except Exception:
                entity = "@UNIQUE_g1"
            print(f"[LUXURY] blank get_entity repaired → {entity!r}", flush=True)

        if not getattr(self, "_lux_dialogs_warmed", False):
            mode = _warm_mode()
            cached = _cache_count()
            # Hot cache: skip iter_dialogs — this was spiking RSS at subscribe time
            if mode == "off" or (mode == "cache" and cached >= 80):
                print(
                    f"[LUXURY] dialogs warm SKIP mode={mode} cache_usernames={cached}",
                    flush=True,
                )
                self._lux_dialogs_warmed = True
            else:
                try:
                    from telethon import utils as _tu

                    by_u: dict[str, Any] = {}
                    n = 0
                    # Cap low — full 500-dialog warm correlated with SIGKILL -9 on Replit
                    cap = 120 if mode == "cache" else 200
                    async for d in self.iter_dialogs():
                        n += 1
                        ent = d.entity
                        uname = (getattr(ent, "username", None) or "").strip().lower()
                        if uname:
                            try:
                                peer_id = int(_tu.get_peer_id(ent))
                            except Exception:
                                peer_id = int(getattr(ent, "id", 0) or 0)
                            ah = getattr(ent, "access_hash", None)
                            et = "user"
                            raw_id = int(getattr(ent, "id", 0) or 0)
                            cls = type(ent).__name__
                            if "Channel" in cls or "megagroup" in cls.lower():
                                et = "channel"
                            elif "Chat" in cls and "User" not in cls:
                                et = "chat"
                            rec = {
                                "peer_id": peer_id,
                                "raw_id": raw_id,
                                "access_hash": int(ah) if ah is not None else None,
                                "type": et,
                            }
                            by_u[uname] = rec
                            by_u["@" + uname] = rec
                        if n >= cap:
                            break
                    try:
                        CACHE.parent.mkdir(parents=True, exist_ok=True)
                        old: dict[str, Any] = {}
                        if CACHE.is_file():
                            old = json.loads(CACHE.read_text(encoding="utf-8"))
                        m = dict(old.get("by_username") or {})
                        m.update(by_u)
                        CACHE.write_text(
                            json.dumps({"by_username": m, "from_dialogs": n}),
                            encoding="utf-8",
                        )
                        print(
                            f"[LUXURY] dialogs warmed n={n} "
                            f"cached_usernames={len(m)}",
                            flush=True,
                        )
                    except Exception as ce:
                        print("[LUXURY] dialog cache write fail:", ce, flush=True)
                    by_u.clear()
                except Exception as e:
                    print("[LUXURY] dialog warm failed:", e, flush=True)
                self._lux_dialogs_warmed = True

        if isinstance(entity, str) and not str(entity).lstrip("-").isdigit():
            rec = _cache_rec(entity)
            if rec is not None:
                inp = _input_peer(rec)
                if inp is not None:
                    try:
                        return await orig(self, inp)
                    except Exception as e1:
                        try:
                            return await orig(self, int(rec["peer_id"]))
                        except Exception as e2:
                            print(
                                f"[LUXURY] cache resolve fail {entity}: {e1!r}/{e2!r}",
                                flush=True,
                            )
            # Flooded sessions: never ResolveUsername — soft skip
            if os.environ.get("LUX_SKIP_RESOLVE_USERNAME", "1").strip().lower() not in {
                "0",
                "false",
                "no",
                "off",
            }:
                raise ValueError(f"LUXURY_SKIP_RESOLVE_USERNAME:{entity}")

        try:
            return await orig(self, entity)
        except FloodWaitError:
            raise

    _get_entity._lux_dialog_resolve = True  # type: ignore[attr-defined]
    TelegramClient.get_entity = _get_entity  # type: ignore[method-assign]
    _PATCHED = True
    print(
        "[LUXURY] get_entity: dialog cache + InputPeer (no ResolveUsername for @rooms)",
        flush=True,
    )
    return True


apply()
