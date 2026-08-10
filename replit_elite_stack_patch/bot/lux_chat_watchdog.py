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
    — installed AFTER subscribe settle (boot-time CALL wrap can disturb auth)

Env:
  LUX_CHAT_WATCHDOG=1     (default on)
  LUX_BLOCK_ESTUDO=1
  LUX_SEND_DEDUP_SECS=90
  LUX_CHAT_WATCH_CALL=0                 # boot-time class patch (keep 0 until connect)
  LUX_CHAT_WATCH_CALL_ON_CONNECT=1      # arm ESTUDO-only __call__ immediately on connect
  LUX_CHAT_WATCH_CALL_AFTER_SETTLE=1    # reaffirm CALL wrap post-settle
  LUX_CHAT_WATCH_CALL_EARLY_SECS=12     # backup early arm after AuthKey settle window
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
from typing import Any, Iterator, Optional

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
    "call_wrap": 0,
}
_PATCHED = False
_CALL_PATCHED = False
_ANNOUNCED = False
_REPATCH_STARTED = False
_SETTLE_CALL_ARMED = False
_EARLY_CALL_ARMED = False
_ZW_RE = re.compile(r"[\u200b\u200c\u200d\ufeff\u00ad]")
# Cyrillic/Greek lookalikes that slip past naive "ESTUDO" string checks
_HOMO_MAP = str.maketrans(
    {
        "Е": "E",
        "е": "e",
        "Ε": "E",
        "ε": "e",
        "Ѕ": "S",
        "ѕ": "s",
        "Τ": "T",
        "τ": "t",
        "Т": "T",
        "т": "t",
        "Ο": "O",
        "ο": "o",
        "О": "O",
        "о": "o",
        "Ⅾ": "D",
        "ⅾ": "d",
        "Ι": "I",
        "ι": "i",
        "І": "I",
        "і": "i",
    }
)
_ESTUDO_RE = re.compile(
    r"(?:G\s*[0-9]+\s*ESTUDO|\bESTUDO\b\s*[|：:/]|🔷\s*G\s*[0-9]+\s*ESTUDO)",
    re.IGNORECASE,
)
_SIGNALISH_RE = re.compile(
    r"(?:🔴|🔵|🟡|RED|BLUE|G0|G1|G2|NEUTRO|PROMISSORA|EMPATE|BAIXA|@\w+)",
    re.IGNORECASE,
)
_SEND_NAMES = frozenset(
    {
        "SendMessageRequest",
        "SendMediaRequest",
        "SendMultiMediaRequest",
        "SendInlineBotResultRequest",
    }
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
    try:
        t = t.translate(_HOMO_MAP)
    except Exception:
        pass
    # "E S T U D O" / "E.S.T.U.D.O" style evasion → ESTUDO
    t = re.sub(r"\bE[\s.\-_]*S[\s.\-_]*T[\s.\-_]*U[\s.\-_]*D[\s.\-_]*O\b", "ESTUDO", t, flags=re.I)
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
    raw = _clean(str(msg))
    u = raw.upper()
    # Hard needles (post-normalize)
    for n in (
        "G2 ESTUDO",
        "G1 ESTUDO",
        "G3 ESTUDO",
        "G0 ESTUDO",
        "G4 ESTUDO",
        "G5 ESTUDO",
        "ESTUDO |",
        "ESTUDO :",
        "ESTUDO：",
        "ESTUDO /",
        "🔷 G2 ESTUDO",
        "🔷 G1 ESTUDO",
        "🔷 G3 ESTUDO",
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
    # Any outbound with ESTUDO + tipster @handles (classic G2 study flood)
    if "ESTUDO" in u and raw.count("@") >= 1:
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


def _coerce_text(v: Any) -> Optional[str]:
    if isinstance(v, str):
        return v
    if isinstance(v, (bytes, bytearray)):
        try:
            return v.decode("utf-8", "ignore")
        except Exception:
            return None
    # Telethon Message / custom builders
    for attr in ("message", "text", "raw_text", "caption"):
        try:
            inner = getattr(v, attr, None)
        except Exception:
            inner = None
        if isinstance(inner, str) and inner.strip():
            return inner
    return None


def _extract_text_from_send(args: tuple, kwargs: dict) -> Optional[str]:
    # send_message(entity, message, ...)
    if len(args) >= 2:
        t = _coerce_text(args[1])
        if t is not None:
            return t
    for key in ("message", "msg", "text", "body", "caption"):
        t = _coerce_text(kwargs.get(key))
        if t is not None:
            return t
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


def _iter_tl_requests(request: Any) -> Iterator[Any]:
    """Yield request + nested TLRequest wrappers (InvokeWithLayer, etc.)."""
    seen: set[int] = set()
    stack: list[Any] = [request]
    while stack:
        cur = stack.pop()
        if cur is None:
            continue
        cid = id(cur)
        if cid in seen:
            continue
        seen.add(cid)
        yield cur
        for attr in ("request", "query", "data", "msg_request"):
            try:
                inner = getattr(cur, attr, None)
            except Exception:
                inner = None
            if inner is not None and id(inner) not in seen:
                stack.append(inner)


def _request_text(req: Any) -> Optional[str]:
    for attr in ("message", "caption", "text", "msg"):
        try:
            v = getattr(req, attr, None)
        except Exception:
            v = None
        if isinstance(v, str) and v.strip():
            return v
        # rare: message is bytes
        if isinstance(v, (bytes, bytearray)):
            try:
                return v.decode("utf-8", "ignore")
            except Exception:
                pass
    # SendMultiMediaRequest: multi_media[].message
    try:
        multi = getattr(req, "multi_media", None) or []
        parts = []
        for item in multi:
            m = getattr(item, "message", None)
            if isinstance(m, str) and m.strip():
                parts.append(m)
        if parts:
            return "\n".join(parts)
    except Exception:
        pass
    return None


def _dropped_updates() -> Any:
    """Return a harmless Updates so callers don't crash/retry-spam on DROP."""
    try:
        from telethon.tl.types import Updates  # type: ignore

        return Updates(
            updates=[],
            users=[],
            chats=[],
            date=int(time.time()),
            seq=0,
        )
    except Exception:
        return None


def _call_wrap_wanted() -> bool:
    return os.environ.get("LUX_CHAT_WATCH_CALL", "0").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _wrap_call(orig):
    if getattr(orig, "_lux_chat_watchdog", False):
        return orig

    @functools.wraps(orig)
    async def _wrapped(self: Any, request: Any, *args: Any, **kwargs: Any):
        # Nuclear safety net ONLY for ESTUDO/trash.
        # Do NOT run full gate_outbound(dedup) here: send_message already
        # commits dedup with final=True, then Telethon hits __call__ — a second
        # dedup pass false-drops the real send (empty Updates / never lands).
        if enabled() and request is not None:
            for req in _iter_tl_requests(request):
                name = type(req).__name__
                if name not in _SEND_NAMES:
                    continue
                msg = _request_text(req)
                if not isinstance(msg, str):
                    continue
                peer = getattr(req, "peer", None)
                peer_l = _peer_label(peer)
                if estudo_blocked(msg):
                    _bump("drop_estudo", peer_l)
                    _append(
                        {
                            "type": "drop",
                            "why": "ESTUDO",
                            "path": f"__call__:{name}",
                            "peer": peer_l,
                            "ts": time.time(),
                            "preview": _clean(msg)[:160],
                        }
                    )
                    print(
                        f"[CHAT-WATCH] DROP ESTUDO via __call__:{name} peer={peer_l}"
                    )
                    return _dropped_updates()
                try:
                    try:
                        from config.keep_allowlist import should_block_as_trash
                    except ImportError:
                        from bot.config.keep_allowlist import should_block_as_trash

                    hit, why = should_block_as_trash(text=_clean(msg))
                    if hit:
                        _bump("drop_trash", peer_l)
                        _append(
                            {
                                "type": "drop",
                                "why": why,
                                "path": f"__call__:{name}",
                                "peer": peer_l,
                                "ts": time.time(),
                                "preview": _clean(msg)[:160],
                            }
                        )
                        print(
                            f"[CHAT-WATCH] DROP trash via __call__:{name} "
                            f"{why} peer={peer_l}"
                        )
                        return _dropped_updates()
                except Exception:
                    pass
        return await orig(self, request, *args, **kwargs)

    _wrapped._lux_chat_watchdog = True  # type: ignore[attr-defined]
    return _wrapped


def _patch_message_methods() -> bool:
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
    return ok


def install_call_wrap(*, force_env: bool = True) -> bool:
    """Install TelegramClient.__call__ gate (safe AFTER subscribe settle)."""
    global _CALL_PATCHED
    if force_env:
        os.environ["LUX_CHAT_WATCH_CALL"] = "1"
    if not _call_wrap_wanted():
        return False
    ok = False
    targets: list[Any] = []
    try:
        from telethon import TelegramClient  # type: ignore

        targets.append(TelegramClient)
    except Exception as exc:
        print("[CHAT-WATCH] TelegramClient import skip:", repr(exc))
    try:
        from telethon.client.telegrambaseclient import TelegramBaseClient  # type: ignore

        targets.append(TelegramBaseClient)
    except Exception:
        pass
    for cls in targets:
        try:
            call = getattr(cls, "__call__", None)
            if callable(call):
                setattr(cls, "__call__", _wrap_call(call))
                ok = True
        except Exception as exc:
            print(f"[CHAT-WATCH] {getattr(cls, '__name__', cls)}.__call__ skip:", repr(exc))
    if ok:
        _CALL_PATCHED = True
        with _LOCK:
            _STATS["call_wrap"] = 1
        print("[CHAT-WATCH] __call__ ESTUDO gate ON (SendMessage*/nested)", flush=True)
    return ok


def patch(*, force: bool = False) -> bool:
    global _PATCHED
    if _PATCHED and not force and (not _call_wrap_wanted() or _CALL_PATCHED):
        return True
    ok = _patch_message_methods()
    # __call__ wrap: OFF at boot by default; ON when env says so (post-settle).
    if _call_wrap_wanted():
        if install_call_wrap(force_env=False):
            ok = True
    _PATCHED = ok
    return ok


def arm_call_wrap_immediate(*, reason: str = "connect") -> bool:
    """Arm ESTUDO-only __call__ gate NOW (safe — no dedup on this path)."""
    if os.environ.get("LUX_CHAT_WATCH_CALL_ON_CONNECT", "1").strip().lower() in {
        "0",
        "false",
        "no",
        "off",
    }:
        return False
    try:
        ok = bool(install_call_wrap(force_env=True))
        patch(force=True)
        print(
            f"[CHAT-WATCH] __call__ ESTUDO gate IMMEDIATE ({reason}) ok={int(ok)}",
            flush=True,
        )
        return ok
    except Exception as exc:
        print(
            f"[CHAT-WATCH] immediate CALL wrap fail ({reason}):",
            repr(exc),
            flush=True,
        )
        return False


def arm_call_wrap_early() -> None:
    """Backup early arm — closes the pre-settle ESTUDO window without waiting 70s+."""
    global _EARLY_CALL_ARMED
    if _EARLY_CALL_ARMED:
        return
    _EARLY_CALL_ARMED = True
    try:
        delay = float(os.environ.get("LUX_CHAT_WATCH_CALL_EARLY_SECS", "12") or "12")
    except Exception:
        delay = 12.0
    delay = max(5.0, delay)

    def _go() -> None:
        arm_call_wrap_immediate(reason=f"early_t+{delay:.0f}s")

    try:
        threading.Timer(delay, _go).start()
        print(f"[CHAT-WATCH] CALL wrap early-arm t+{delay:.0f}s", flush=True)
    except Exception as exc:
        print("[CHAT-WATCH] early CALL arm skip:", repr(exc), flush=True)


def arm_call_wrap_after_settle() -> None:
    """Reaffirm CALL wrap after OUTBOX settle."""
    global _SETTLE_CALL_ARMED
    if _SETTLE_CALL_ARMED:
        return
    if os.environ.get("LUX_CHAT_WATCH_CALL_AFTER_SETTLE", "1").strip().lower() in {
        "0",
        "false",
        "no",
        "off",
    }:
        return
    _SETTLE_CALL_ARMED = True
    try:
        settle = float(os.environ.get("OUTBOX_INLINE_SETTLE_SECS", "70") or "70")
    except Exception:
        settle = 70.0
    delay = max(45.0, settle + 8.0)

    def _go() -> None:
        try:
            install_call_wrap(force_env=True)
            patch(force=True)
            print("[CHAT-WATCH] post-settle CALL wrap reaffirmed", flush=True)
        except Exception as exc:
            print("[CHAT-WATCH] post-settle CALL wrap fail:", repr(exc), flush=True)

    try:
        threading.Timer(delay, _go).start()
        print(
            f"[CHAT-WATCH] CALL wrap reaffirm armed for t+{delay:.0f}s (post-settle)",
            flush=True,
        )
    except Exception as exc:
        print("[CHAT-WATCH] arm CALL wrap skip:", repr(exc), flush=True)


def _rebind_engine_send() -> None:
    """Re-wrap megafile send() — bacbo often defines it late / rebinds it."""
    try:
        import lux_send_config_bind as scb

        scb.apply(silent=True)
    except Exception:
        pass


def _start_forever_repatch() -> None:
    global _REPATCH_STARTED
    if _REPATCH_STARTED:
        return
    _REPATCH_STARTED = True

    def _loop() -> None:
        # Burst early, then steady forever — survive late telethon / send rebinds.
        t0 = time.monotonic()
        for d in (1.0, 3.0, 8.0, 20.0, 45.0, 90.0):
            left = d - (time.monotonic() - t0)
            if left > 0:
                time.sleep(left)
            try:
                patch(force=True)
                _rebind_engine_send()
                if _call_wrap_wanted():
                    install_call_wrap(force_env=False)
            except Exception:
                pass
        while True:
            time.sleep(15.0)
            try:
                patch(force=True)
                _rebind_engine_send()
                if _call_wrap_wanted():
                    install_call_wrap(force_env=False)
            except Exception:
                pass

    try:
        threading.Thread(target=_loop, name="lux_chat_watch_repatch", daemon=True).start()
    except Exception:
        for d in (1.0, 3.0, 8.0, 20.0, 45.0, 90.0):
            try:
                threading.Timer(d, lambda: patch(force=True)).start()
            except Exception:
                pass


def snapshot() -> dict[str, Any]:
    with _LOCK:
        return dict(_STATS)


def apply(*, quiet: bool = False) -> bool:
    """Best-effort Telethon patch; gate functions always usable."""
    global _ANNOUNCED
    ok = patch(force=True)
    _start_forever_repatch()
    arm_call_wrap_early()
    arm_call_wrap_after_settle()
    if not quiet and not _ANNOUNCED:
        _ANNOUNCED = True
        if ok:
            print("[CHAT-WATCH] nuclear ESTUDO + chat ledger ON")
        else:
            print("[CHAT-WATCH] gate ready (Telethon patch pending/retry)")
    return True


# Auto-apply on import (before bacbo main)
if enabled():
    apply()
