"""Per-chat vertical signal bundles (FIRE → RESULT → gale).

Stores fire Telegram message ids so RESULT can reply_to the parent FIRE
and sit visually under it. Hermetic: keyed by (peer, signal_id).
"""
from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any, Optional

HERE = Path(__file__).resolve().parent
# bot/config → bot/data
DATA = HERE.parent / "data"
STORE = DATA / "signal_bundle_fire_msgs.json"

_LOCK = threading.Lock()
_CACHE: dict[str, Any] | None = None


def enabled() -> bool:
    try:
        try:
            from bot.config.emanation_laws import signal_bundle_vertical
        except ImportError:
            from config.emanation_laws import signal_bundle_vertical

        return bool(signal_bundle_vertical())
    except Exception:
        return os.environ.get("SIGNAL_BUNDLE_VERTICAL", "1").strip().lower() not in {
            "0",
            "false",
            "no",
            "off",
        }


def _load() -> dict[str, Any]:
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    try:
        _CACHE = json.loads(STORE.read_text(encoding="utf-8"))
    except Exception:
        _CACHE = {"version": 1, "by_signal": {}, "updated_at": 0}
    return _CACHE


def _save(data: dict[str, Any]) -> None:
    global _CACHE
    DATA.mkdir(parents=True, exist_ok=True)
    data["updated_at"] = time.time()
    # prune old (>6h)
    cutoff = time.time() - 6 * 3600
    by = data.setdefault("by_signal", {})
    for k, row in list(by.items()):
        try:
            if float(row.get("ts") or 0) < cutoff:
                by.pop(k, None)
        except Exception:
            by.pop(k, None)
    STORE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    _CACHE = data


def remember_fire(
    signal_id: Any,
    *,
    message_id: int,
    peer: str = "",
    chat_id: Any = None,
) -> None:
    if not enabled() or signal_id is None or not message_id:
        return
    key = str(int(signal_id))
    with _LOCK:
        data = _load()
        data.setdefault("by_signal", {})[key] = {
            "message_id": int(message_id),
            "peer": str(peer or ""),
            "chat_id": chat_id,
            "ts": time.time(),
        }
        _save(data)


def fire_message_id(signal_id: Any) -> Optional[int]:
    if signal_id is None:
        return None
    with _LOCK:
        row = (_load().get("by_signal") or {}).get(str(int(signal_id))) or {}
    mid = row.get("message_id")
    try:
        return int(mid) if mid is not None else None
    except Exception:
        return None


def fire_peer(signal_id: Any) -> str:
    if signal_id is None:
        return ""
    with _LOCK:
        row = (_load().get("by_signal") or {}).get(str(int(signal_id))) or {}
    return str(row.get("peer") or "")
