"""Multi-chat runtime router — capacity, elastic overflow, sticky result gluing.

`chat_shelves.resolve_shelf()` decides *which shelf* a card belongs to.
This module decides *which actual chat* it lands in, and guarantees:

1. **Never drop a fire.** If a shelf is at capacity the card spills to
   OVERFLOW_1, OVERFLOW_2, … (elastic). If every overflow chat is saturated the
   card is *delayed*, never discarded.
2. **Results follow their parent to the exact chat.** A fire that spilled into
   overflow chat #2 has its WIN/LOSS/forensic/G1-EXPIROU cards delivered to
   overflow chat #2 — not merely to the same shelf.
3. **Nothing is deleted.** CREATED_ONLY / never-fired templates keep a VAULT
   target so they stay addressable when revived.

Config is env-driven and fail-open: with no env set, everything resolves to the
existing default peers and capacity limits are generous.
"""
from __future__ import annotations

import os
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, List, Optional, Tuple

from bot.config.chat_shelves import (
    SHELF_OVERFLOW,
    SHELF_SINK,
    SHELF_VAULT,
    ShelfDecision,
    resolve_shelf,
)

# ── Capacity defaults (cards per minute, per shelf) ─────────────────────────
# Money shelves stay readable; countdown tolerates more because cards are short.
_DEFAULT_CAPACITY: Dict[str, float] = {
    "SHELF_PENTHOUSE_MONEY": 3.0,
    "SHELF_UPPER_MONEY": 3.0,
    "SHELF_COUNTDOWN": 6.0,
    "SHELF_SNIPER": 2.0,
    "SHELF_GALE": 3.0,
    "SHELF_OPS_EXPIRE": 4.0,
    SHELF_OVERFLOW: 8.0,
    SHELF_VAULT: 0.0,  # no live send
    SHELF_SINK: 0.0,  # suppressed
}

_WINDOW_SECONDS = 60.0
_MAX_OVERFLOW_CHATS = 8


def _env_float(name: str, default: float) -> float:
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def capacity_for(shelf_id: str) -> float:
    """Cards/minute allowed on a shelf. `TELEGRAM_CAP_<SHELF>` overrides."""
    key = f"TELEGRAM_CAP_{shelf_id.replace('SHELF_', '')}"
    return _env_float(key, _DEFAULT_CAPACITY.get(shelf_id, 3.0))


# Default overflow shelves when env is unset: UNIQUE_g2 … UNIQUE_g5
# (UNIQUE_g1 is the primary countdown/sniper chat; Mr_iv4 is money.)
_DEFAULT_OVERFLOW_PEERS: Tuple[str, ...] = (
    "UNIQUE_g2",
    "UNIQUE_g3",
    "UNIQUE_g4",
    "UNIQUE_g5",
)


def overflow_peers() -> List[str]:
    """Elastic overflow chats: TELEGRAM_SHELF_OVERFLOW_1..N (comma list also ok).

    Unset env → UNIQUE_g2, UNIQUE_g3, UNIQUE_g4, UNIQUE_g5.
    Money stays on Mr_iv4; countdown/sniper primary stays on UNIQUE_g1.
    """
    peers: List[str] = []
    multi = (os.environ.get("TELEGRAM_SHELF_OVERFLOW_PEERS") or "").strip()
    if multi:
        peers.extend(p.strip().lstrip("@") for p in multi.split(",") if p.strip())
    for i in range(1, _MAX_OVERFLOW_CHATS + 1):
        raw = (os.environ.get(f"TELEGRAM_SHELF_OVERFLOW_{i}") or "").strip()
        if raw:
            peers.append(raw.lstrip("@"))
    if not peers:
        base = (os.environ.get("TELEGRAM_SHELF_OVERFLOW") or "").strip()
        if base:
            peers.append(base.lstrip("@"))
    if not peers:
        peers.extend(_DEFAULT_OVERFLOW_PEERS)
    # de-dupe preserving order
    seen = set()
    out: List[str] = []
    for p in peers:
        key = p.lstrip("@").lower()
        if key in seen or not p:
            continue
        seen.add(key)
        out.append(p.lstrip("@"))
    return out


@dataclass
class ChatTarget:
    """Final delivery address for one card."""

    shelf_id: str
    peer: Optional[str]
    overflow_index: int = 0  # 0 = primary shelf chat
    delayed_seconds: float = 0.0
    family_id: str = ""
    role: str = ""
    kind: Optional[str] = None
    lane: Optional[str] = None
    follow_parent: bool = False
    suppressed: bool = False
    reason: str = ""

    @property
    def target_id(self) -> str:
        """Stable id for sticky parent mapping (shelf + overflow slot)."""
        return f"{self.shelf_id}#{self.overflow_index}"

    def as_dict(self) -> Dict[str, Any]:
        return {
            "shelf_id": self.shelf_id,
            "peer": self.peer,
            "overflow_index": self.overflow_index,
            "target_id": self.target_id,
            "delayed_seconds": round(self.delayed_seconds, 2),
            "family_id": self.family_id,
            "role": self.role,
            "kind": self.kind,
            "lane": self.lane,
            "follow_parent": self.follow_parent,
            "suppressed": self.suppressed,
            "reason": self.reason,
        }


@dataclass
class _Window:
    stamps: Deque[float] = field(default_factory=deque)

    def prune(self, now: float) -> None:
        cutoff = now - _WINDOW_SECONDS
        while self.stamps and self.stamps[0] < cutoff:
            self.stamps.popleft()

    def count(self, now: float) -> int:
        self.prune(now)
        return len(self.stamps)

    def add(self, now: float) -> None:
        self.stamps.append(now)


class ChatRouter:
    """Capacity-aware multi-chat router with sticky parent mapping."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._windows: Dict[str, _Window] = {}
        # signal_id → target_id chosen for that signal's FIRE
        self._parent_targets: Dict[str, ChatTarget] = {}
        self._parent_order: Deque[str] = deque()
        self._max_parents = 5000

    # ── internals ───────────────────────────────────────────────────────────
    def _window(self, target_id: str) -> _Window:
        w = self._windows.get(target_id)
        if w is None:
            w = _Window()
            self._windows[target_id] = w
        return w

    def _has_room(self, shelf_id: str, target_id: str, now: float) -> bool:
        cap = capacity_for(shelf_id)
        if cap <= 0:
            return False
        return self._window(target_id).count(now) < cap

    def _remember_parent(self, signal_id: str, target: ChatTarget) -> None:
        if not signal_id:
            return
        if signal_id not in self._parent_targets:
            self._parent_order.append(signal_id)
            while len(self._parent_order) > self._max_parents:
                old = self._parent_order.popleft()
                self._parent_targets.pop(old, None)
        self._parent_targets[signal_id] = target

    # ── public API ──────────────────────────────────────────────────────────
    def parent_target(self, signal_id: Optional[str]) -> Optional[ChatTarget]:
        if not signal_id:
            return None
        with self._lock:
            return self._parent_targets.get(str(signal_id))

    def route(
        self,
        text: Optional[str] = None,
        *,
        signal_id: Optional[str] = None,
        signal_kind: Optional[str] = None,
        meta: Optional[Dict[str, Any]] = None,
        now: Optional[float] = None,
        commit: bool = True,
    ) -> ChatTarget:
        """Resolve one card to a concrete chat, spilling to overflow as needed."""
        now = time.time() if now is None else now
        sid = str(signal_id) if signal_id else ""

        with self._lock:
            parent = self._parent_targets.get(sid) if sid else None
            decision: ShelfDecision = resolve_shelf(
                text,
                signal_kind=signal_kind,
                meta=meta,
                parent_shelf=parent.shelf_id if parent else None,
                parent_lane=parent.lane if parent else None,
            )

            # RESULT / ops-result glue straight back to the parent's exact chat.
            if decision.follow_parent and parent is not None:
                target = ChatTarget(
                    shelf_id=parent.shelf_id,
                    peer=parent.peer,
                    overflow_index=parent.overflow_index,
                    family_id=decision.family_id,
                    role=decision.role,
                    kind=decision.kind,
                    lane=parent.lane,
                    follow_parent=True,
                    reason=f"glue_parent:{parent.target_id}",
                )
                if commit:
                    self._window(target.target_id).add(now)
                return target

            shelf = decision.shelf_id

            # Vault / sink never send live, but stay addressable (never dropped).
            if shelf in (SHELF_VAULT, SHELF_SINK):
                return ChatTarget(
                    shelf_id=shelf,
                    peer=decision.peer,
                    family_id=decision.family_id,
                    role=decision.role,
                    kind=decision.kind,
                    lane=decision.lane,
                    suppressed=True,
                    reason=f"{'vault_created_only' if shelf == SHELF_VAULT else 'noise_sink'}",
                )

            # Primary shelf chat if it has room.
            primary_id = f"{shelf}#0"
            if self._has_room(shelf, primary_id, now):
                target = ChatTarget(
                    shelf_id=shelf,
                    peer=decision.peer,
                    overflow_index=0,
                    family_id=decision.family_id,
                    role=decision.role,
                    kind=decision.kind,
                    lane=decision.lane,
                    reason=decision.reason,
                )
                if commit:
                    self._window(primary_id).add(now)
                    if decision.role == "FIRE" and sid:
                        self._remember_parent(sid, target)
                return target

            # Shelf saturated → spill across elastic overflow chats.
            peers = overflow_peers()
            for idx, peer in enumerate(peers, start=1):
                of_id = f"{SHELF_OVERFLOW}#{idx}"
                if self._has_room(SHELF_OVERFLOW, of_id, now):
                    target = ChatTarget(
                        shelf_id=SHELF_OVERFLOW,
                        peer=peer,
                        overflow_index=idx,
                        family_id=decision.family_id,
                        role=decision.role,
                        kind=decision.kind,
                        lane=decision.lane,
                        reason=f"overflow_from:{shelf}",
                    )
                    if commit:
                        self._window(of_id).add(now)
                        if decision.role == "FIRE" and sid:
                            self._remember_parent(sid, target)
                    return target

            # Everything saturated → DELAY on the primary shelf. Never drop.
            w = self._window(primary_id)
            w.prune(now)
            oldest = w.stamps[0] if w.stamps else now
            wait = max(0.0, (oldest + _WINDOW_SECONDS) - now)
            target = ChatTarget(
                shelf_id=shelf,
                peer=decision.peer,
                overflow_index=0,
                delayed_seconds=wait,
                family_id=decision.family_id,
                role=decision.role,
                kind=decision.kind,
                lane=decision.lane,
                reason=f"delayed_all_saturated:{round(wait, 1)}s",
            )
            if commit:
                w.add(now)
                if decision.role == "FIRE" and sid:
                    self._remember_parent(sid, target)
            return target

    def load(self, now: Optional[float] = None) -> Dict[str, Any]:
        """Current per-chat load for /shelves style diagnostics."""
        now = time.time() if now is None else now
        with self._lock:
            out: Dict[str, Any] = {}
            for target_id, w in sorted(self._windows.items()):
                shelf = target_id.split("#")[0]
                out[target_id] = {
                    "used": w.count(now),
                    "capacity_per_min": capacity_for(shelf),
                }
            return {
                "window_seconds": _WINDOW_SECONDS,
                "overflow_chats": len(overflow_peers()),
                "tracked_parents": len(self._parent_targets),
                "chats": out,
            }

    def reset(self) -> None:
        with self._lock:
            self._windows.clear()
            self._parent_targets.clear()
            self._parent_order.clear()


_ROUTER = ChatRouter()


def get_router() -> ChatRouter:
    return _ROUTER


def route_card(
    text: Optional[str] = None,
    *,
    signal_id: Optional[str] = None,
    signal_kind: Optional[str] = None,
    meta: Optional[Dict[str, Any]] = None,
) -> ChatTarget:
    """Module-level convenience wrapper around the shared router."""
    return _ROUTER.route(
        text, signal_id=signal_id, signal_kind=signal_kind, meta=meta
    )
