"""Nuclear Telegram chat watchdog + ESTUDO kill.

Always knows what is happening (or NOT) in money/APEX chats:
  · every outbound attempt → ledger (sent / dropped / why)
  · G2 ESTUDO / study spam → HARD DROP on every Telethon path
  · near-duplicate floods → DROP
  · opp-lock + hub decisions stay visible via hub_impact_learner

Patches (and re-patches):
  MessageMethods.send_message
  MessageMethods.send_file          (caption)
  TelegramClient.__call__           (SendMessageRequest / SendMediaRequest)

Env:
  LUX_CHAT_WATCHDOG=1     (default on)
  LUX_BLOCK_ESTUDO=1
  LUX_SEND_DEDUP_SECS=90
"""
from __future__ import annotations

import functools
import hashlib
import json
import os
import re
import threading
import time
import unicodedata
from pathlib import Path
from typing import Any, Optional

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
LEDGER = DATA / "chat_watchdog_ledger.jsonl"
STATS = DATA / "chat_watchdog_stats.json"

_LOCK = threading.Lock()
_RECENT: dict[str, float] = {}
_STATS: dict[str, Any] = {
    "sent": 0,
    "drop_estudo": 0,
    "drop_dedup": 0,
    "drop_trash": 0,
    "by_peer": {},
    "updated_at": 0,
}
_PATCHED = False
_ZW_RE = re.compile(r"[\u200b\u200c\u200d\ufeff\u00ad]")
_ESTUDO_RE = re.compile(
    r"(?:G\s*[0-9]+\s*ESTUDO|\bESTUDO\b\s*[|：:]|🔷\s*G\s*[0-9]+\s*ESTUDO)",
    re.IGNORECASE,
)
_SIGNALISH_RE = re.compile(
    r"(?:🔴|🔵|RED|BLUE|G0|G1|G2|NEUTRO|PROMISSORA|EMPATE)",
    re.IGNORECASE,
)


def enabled() -> bool:
    return os.environ.get("LUX_CHAT_WATCHDOG", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def _clean(text: str) -> str:
    t = unicodedata.normalize("NFKC", text or "")
    t = _ZW_RE.sub("", t)
    # collapse weird spaces
    t = re.sub(r"[\u00a0\u1680\u2000-\u200a\u202f\u205f\u3000]", " ", t)
    return t


def estudo_blocked(msg: Optional[str]) -> bool:
    if not msg:
        return False
    if os.environ.get("LUX_BLOCK_ESTUDO", "1").strip().lower() in {
        "0",
        "false",
        "no",
        "off",
    }:
        return False
    raw = _clean(msg)
    u = raw.upper()
    # Hard needles (post-normalize)
    for n in (
        "G2 ESTUDO",
        "G1 ESTUDO",
        "G3 ESTUDO",
        "G0 ESTUDO",
        "G4 ESTUDO",
        "ESTUDO |",
        "ESTUDO :",
        "ESTUDO：",
        "🔷 G2 ESTUDO",
        "🔷 G1 ESTUDO",
    ):
        if n.upper() in u:
            return True
    if "ESTUDO" in u and _SIGNALISH_RE.search(raw):
        return True
    first = raw.splitlines()[0] if raw else ""
    if _ESTUDO_RE.search(first) or _ESTUDO_RE.search(raw[:200]):
        return True
    if "ESTUDO" in first.upper():
        return True
    return False


def _norm_dedup(msg: str) -> str:
    lines = []
    for ln in _clean(msg).strip().splitlines():
        ln = re.sub(r"\b\d+\.\d{1,3}\b\s*$", "", ln).rstrip()
        lines.append(ln)
    return "\n".join(lines).casefold()


def _dedup_secs() -> float:
    try:
        return float(os.environ.get("LUX_SEND_DEDUP_SECS", "90") or "90")
    except Exception:
        return 90.0


def dedup_hit(msg: Optional[str], *, commit: bool = True) -> bool:
    """True if duplicate within window. commit=True records this attempt."""
    if not msg or not str(msg).strip():
        return False
    secs = _dedup_secs()
    if secs <= 0:
        return False
    key = hashlib.sha1(_norm_dedup(msg).encode("utf-8", "ignore")).hexdigest()
    now = time.monotonic()
    with _LOCK:
        if len(_RECENT) > 500:
            cutoff = now - max(secs, 60.0)
            for k, t in list(_RECENT.items()):
                if t < cutoff:
                    _RECENT.pop(k, None)
        prev = _RECENT.get(key)
        if prev is not None and (now - prev) < secs:
            return True
        if commit:
            _RECENT[key] = now
    return False


def _peer_label(entity: Any) -> str:
    if entity is None:
        return "?"
    for attr in ("username", "title", "first_name"):
        v = getattr(entity, attr, None)
        if v:
            return str(v)
    try:
        return str(getattr(entity, "id", entity))
    except Exception:
        return repr(entity)[:80]


def _extract_text_from_send(args: tuple, kwargs: dict) -> Optional[str]:
    # send_message(entity, message, ...)
    if len(args) >= 2 and isinstance(args[1], str):
        return args[1]
    for key in ("message", "msg", "text", "body", "caption"):
        v = kwargs.get(key)
        if isinstance(v, str):
            return v
    return None


def _extract_entity(args: tuple, kwargs: dict) -> Any:
    if args:
        return args[0]
    return kwargs.get("entity") or kwargs.get("peer")


def _bump(stat: str, peer: str = "") -> None:
    with _LOCK:
        _STATS[stat] = int(_STATS.get(stat) or 0) + 1
        if peer:
            bp = _STATS.setdefault("by_peer", {})
            row = bp.setdefault(peer, {"sent": 0, "drop_estudo": 0, "drop_dedup": 0, "drop_trash": 0})
            row[stat] = int(row.get(stat) or 0) + 1
        _STATS["updated_at"] = time.time()
        try:
            DATA.mkdir(parents=True, exist_ok=True)
            STATS.write_text(json.dumps(_STATS, indent=2), encoding="utf-8")
        except Exception:
            pass


def _append(ev: dict[str, Any]) -> None:
    try:
        DATA.mkdir(parents=True, exist_ok=True)
        with LEDGER.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(ev, ensure_ascii=False) + "\n")
    except Exception:
        pass


def gate_outbound(
    *,
    msg: Optional[str],
    entity: Any = None,
    path: str = "send_message",
    final: bool = True,
) -> tuple[bool, str]:
    """Return (allow, reason). False = DROP.

    final=True  → Telethon edge (commit dedup + record sent)
    final=False → pre-check in engine send() (no dedup commit / no sent bump)
    """
    peer = _peer_label(entity)
    body = _clean(msg) if msg else ""
    if estudo_blocked(body):
        _bump("drop_estudo", peer)
        _append(
            {
                "type": "drop",
                "why": "ESTUDO",
                "path": path,
                "peer": peer,
                "ts": time.time(),
                "preview": body[:160],
            }
        )
        print(f"[CHAT-WATCH] DROP ESTUDO via {path} peer={peer}")
        return False, "ESTUDO"
    try:
        from config.keep_allowlist import should_block_as_trash

        hit, why = should_block_as_trash(text=body)
        if hit:
            _bump("drop_trash", peer)
            _append(
                {
                    "type": "drop",
                    "why": why,
                    "path": path,
                    "peer": peer,
                    "ts": time.time(),
                    "preview": body[:160],
                }
            )
            print(f"[CHAT-WATCH] DROP trash via {path} {why} peer={peer}")
            return False, why
    except Exception:
        pass
    if dedup_hit(body, commit=final):
        _bump("drop_dedup", peer)
        _append(
            {
                "type": "drop",
                "why": "DEDUP",
                "path": path,
                "peer": peer,
                "ts": time.time(),
                "preview": body[:160],
            }
        )
        print(f"[CHAT-WATCH] DROP DEDUP via {path} peer={peer}")
        return False, "DEDUP"
    if final:
        _bump("sent", peer)
        _append(
            {
                "type": "sent",
                "path": path,
                "peer": peer,
                "ts": time.time(),
                "preview": body[:160],
                "n_lines": body.count("\n") + 1 if body else 0,
            }
        )
    return True, "allow"


def _wrap_send_message(orig):
    if getattr(orig, "_lux_chat_watchdog", False):
        return orig

    @functools.wraps(orig)
    async def _wrapped(self: Any, *args: Any, **kwargs: Any):
        if enabled():
            msg = _extract_text_from_send(args, kwargs)
            ent = _extract_entity(args, kwargs)
            ok, _why = gate_outbound(msg=msg, entity=ent, path="send_message")
            if not ok:
                return None
        return await orig(self, *args, **kwargs)

    _wrapped._lux_chat_watchdog = True  # type: ignore[attr-defined]
    return _wrapped


def _wrap_send_file(orig):
    if getattr(orig, "_lux_chat_watchdog", False):
        return orig

    @functools.wraps(orig)
    async def _wrapped(self: Any, *args: Any, **kwargs: Any):
        if enabled():
            cap = kwargs.get("caption")
            if isinstance(cap, str):
                ent = _extract_entity(args, kwargs)
                ok, _why = gate_outbound(msg=cap, entity=ent, path="send_file")
                if not ok:
                    return None
        return await orig(self, *args, **kwargs)

    _wrapped._lux_chat_watchdog = True  # type: ignore[attr-defined]
    return _wrapped


def _wrap_call(orig):
    if getattr(orig, "_lux_chat_watchdog", False):
        return orig

    @functools.wraps(orig)
    async def _wrapped(self: Any, request: Any, *args: Any, **kwargs: Any):
        if enabled() and request is not None:
            name = type(request).__name__
            if name in {
                "SendMessageRequest",
                "SendMediaRequest",
                "SendMultiMediaRequest",
            }:
                msg = getattr(request, "message", None)
                if not isinstance(msg, str):
                    msg = getattr(request, "caption", None)
                peer = getattr(request, "peer", None)
                if isinstance(msg, str):
                    ok, _why = gate_outbound(
                        msg=msg, entity=peer, path=f"__call__:{name}"
                    )
                    if not ok:
                        return None
        return await orig(self, request, *args, **kwargs)

    _wrapped._lux_chat_watchdog = True  # type: ignore[attr-defined]
    return _wrapped


def patch(*, force: bool = False) -> bool:
    global _PATCHED
    if _PATCHED and not force:
        return True
    ok = False
    try:
        from telethon.client.messages import MessageMethods  # type: ignore

        sm = getattr(MessageMethods, "send_message", None)
        if callable(sm):
            MessageMethods.send_message = _wrap_send_message(sm)  # type: ignore
            ok = True
        sf = getattr(MessageMethods, "send_file", None)
        if callable(sf):
            MessageMethods.send_file = _wrap_send_file(sf)  # type: ignore
            ok = True
    except Exception as exc:
        print("[CHAT-WATCH] MessageMethods patch skip:", repr(exc))
    try:
        from telethon import TelegramClient  # type: ignore

        call = getattr(TelegramClient, "__call__", None)
        if callable(call):
            TelegramClient.__call__ = _wrap_call(call)  # type: ignore
            ok = True
    except Exception as exc:
        print("[CHAT-WATCH] TelegramClient.__call__ patch skip:", repr(exc))
    _PATCHED = ok
    return ok


def snapshot() -> dict[str, Any]:
    with _LOCK:
        return dict(_STATS)


def apply() -> bool:
    """Best-effort Telethon patch; gate functions always usable."""
    ok = patch(force=True)
    # Keep the gate on top even if something else rebinds telethon methods later.
    try:
        delays = (2.0, 8.0, 20.0, 45.0, 90.0)

        def _re():
            try:
                patch(force=True)
            except Exception:
                pass

        for d in delays:
            threading.Timer(d, _re).start()
    except Exception:
        pass
    if ok:
        print("[CHAT-WATCH] nuclear ESTUDO + chat ledger ON")
    else:
        print("[CHAT-WATCH] gate ready (Telethon patch pending/retry)")
    return True


# Auto-apply on import (before bacbo main)
if enabled():
    apply()
