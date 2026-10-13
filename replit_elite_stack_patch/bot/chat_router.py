"""Replit flat wrapper for bot.config.chat_router."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


def _bootstrap() -> None:
    here = Path(__file__).resolve().parent
    for root in (
        here.parent,
        here.parent.parent,
        Path("/workspace"),
        Path("/home/runner/workspace"),
    ):
        if (root / "bot" / "config" / "chat_router.py").is_file():
            s = str(root)
            if s not in sys.path:
                sys.path.insert(0, s)
            return


def _impl():
    try:
        from bot.config import chat_router as cr  # type: ignore

        return cr
    except ImportError:
        pass
    _bootstrap()
    try:
        from bot.config import chat_router as cr  # type: ignore

        return cr
    except ImportError:
        return None


def overflow_peers() -> List[str]:
    cr = _impl()
    if cr is None:
        return ["UNIQUE_g2", "UNIQUE_g3", "UNIQUE_g4", "UNIQUE_g5"]
    return cr.overflow_peers()


def route_card(*args, **kwargs):
    cr = _impl()
    if cr is None:
        class _T:
            shelf_id = "SHELF_OVERFLOW"
            peer = "UNIQUE_g2"
            overflow_index = 1
            delayed_seconds = 0.0
            family_id = "UNKNOWN"
            role = "UNKNOWN"
            kind = None
            lane = None
            follow_parent = False
            suppressed = False
            reason = "chat_router_unavailable"

            @property
            def target_id(self) -> str:
                return f"{self.shelf_id}#{self.overflow_index}"

            def as_dict(self) -> Dict[str, Any]:
                return {"peer": self.peer, "reason": self.reason}

        return _T()
    return cr.route_card(*args, **kwargs)


def get_router():
    cr = _impl()
    return cr.get_router() if cr else None
