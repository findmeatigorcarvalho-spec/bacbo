"""Replit flat wrapper for bot.config.chat_shelves."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, Optional


def _bootstrap() -> None:
    here = Path(__file__).resolve().parent
    for root in (here.parent, here.parent.parent, Path("/workspace"), Path("/home/runner/workspace")):
        if (root / "bot" / "config" / "chat_shelves.py").is_file():
            s = str(root)
            if s not in sys.path:
                sys.path.insert(0, s)
            return


def _impl():
    try:
        from bot.config import chat_shelves as cs  # type: ignore

        return cs
    except ImportError:
        pass
    _bootstrap()
    try:
        from bot.config import chat_shelves as cs  # type: ignore

        return cs
    except ImportError:
        return None


def resolve_shelf(*args, **kwargs):
    cs = _impl()
    if cs is None:
        class _D:
            shelf_id = "SHELF_OVERFLOW"
            family_id = "UNKNOWN"
            role = "UNKNOWN"
            kind = None
            lane = None
            peer = None
            follow_parent = False
            band_hint = "UNRANKED"
            reason = "chat_shelves_unavailable"

            def as_dict(self):
                return {"shelf_id": self.shelf_id, "reason": self.reason}

        return _D()
    return cs.resolve_shelf(*args, **kwargs)


def shelf_catalog():
    cs = _impl()
    return cs.shelf_catalog() if cs else ()


def shelf_for_family(family_id: str) -> str:
    cs = _impl()
    return cs.shelf_for_family(family_id) if cs else "SHELF_OVERFLOW"
