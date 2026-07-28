#!/usr/bin/env python3
"""
window_packer.py — fit signal families into time gaps (max profitable merge).

User example:
  Countdown fire at T=0 with 35s window.
  Another family at T=3s..30s should still be able to FIRE (usually other chat),
  instead of globally silencing the organism for 35s.

Rules:
  - Different chat → allow (pack the gap)
  - Same chat + opposite color + overlap → lock (keep higher score)
  - HUB is strict on opposite-color money doubles
  - Result glue is out of scope here (outbox parent lane)

Env:
  PACKER_HUB_CHAT=HUB
  PACKER_SAME_COLOR_BURST=1   allow same-color multi in one chat
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class OpenFire:
    fire_id: str
    family: str
    color: str
    chat: str
    t0: float
    window_secs: float
    score: float = 0.0

    def open_until(self) -> float:
        return self.t0 + max(0.0, float(self.window_secs))

    def overlaps(self, t: float) -> bool:
        return self.t0 <= t <= self.open_until()


@dataclass
class PackDecision:
    action: str  # ALLOW | LOCK_KEEP_EXISTING | LOCK_REPLACE | HOLD_HUB
    reason: str
    chat: str
    fire_id: str | None = None
    replaces: str | None = None
    packed_gap: bool = False


@dataclass
class WindowPacker:
    hub_chat: str = field(
        default_factory=lambda: os.environ.get("PACKER_HUB_CHAT", "HUB").upper()
    )
    same_color_burst: bool = field(
        default_factory=lambda: os.environ.get("PACKER_SAME_COLOR_BURST", "1").strip()
        not in {"0", "false", "no"}
    )
    open: list[OpenFire] = field(default_factory=list)

    def _purge(self, now: float) -> None:
        self.open = [f for f in self.open if f.open_until() >= now]

    def admit(
        self,
        *,
        fire_id: str,
        family: str,
        color: str,
        chat: str,
        window_secs: float,
        score: float = 0.0,
        now: float | None = None,
    ) -> PackDecision:
        now = time.time() if now is None else float(now)
        self._purge(now)
        color = (color or "").lower().strip()
        chat = (chat or "HUB").upper().strip()
        family = (family or "UNKNOWN").upper().strip()
        window_secs = float(window_secs or 0.0)

        same_chat = [f for f in self.open if f.chat == chat and f.overlaps(now)]
        opp = [f for f in same_chat if f.color in {"red", "blue"} and color in {"red", "blue"} and f.color != color]
        same = [f for f in same_chat if f.color == color]

        # HUB opposite-color strict even if window tiny
        if chat == self.hub_chat and opp:
            best = max(opp, key=lambda f: f.score)
            if score > best.score:
                self.open = [f for f in self.open if f.fire_id != best.fire_id]
                self.open.append(
                    OpenFire(fire_id, family, color, chat, now, window_secs, score)
                )
                return PackDecision(
                    "LOCK_REPLACE",
                    "hub opposite-color — replace weaker open",
                    chat,
                    fire_id,
                    replaces=best.fire_id,
                )
            return PackDecision(
                "HOLD_HUB",
                "hub opposite-color — keep existing",
                chat,
                fire_id=best.fire_id,
            )

        if opp:
            best = max(opp, key=lambda f: f.score)
            if score > best.score:
                self.open = [f for f in self.open if f.fire_id != best.fire_id]
                self.open.append(
                    OpenFire(fire_id, family, color, chat, now, window_secs, score)
                )
                return PackDecision(
                    "LOCK_REPLACE",
                    "same-chat opposite-color — replace weaker",
                    chat,
                    fire_id,
                    replaces=best.fire_id,
                )
            return PackDecision(
                "LOCK_KEEP_EXISTING",
                "same-chat opposite-color — keep existing",
                chat,
                fire_id=best.fire_id,
            )

        if same and not self.same_color_burst:
            best = max(same, key=lambda f: f.score)
            if score > best.score:
                self.open = [f for f in self.open if f.fire_id != best.fire_id]
                self.open.append(
                    OpenFire(fire_id, family, color, chat, now, window_secs, score)
                )
                return PackDecision(
                    "LOCK_REPLACE",
                    "same-color coalesce — replace weaker",
                    chat,
                    fire_id,
                    replaces=best.fire_id,
                )
            return PackDecision(
                "LOCK_KEEP_EXISTING",
                "same-color coalesce — keep existing",
                chat,
                fire_id=best.fire_id,
            )

        # Different chat OR empty slot OR same-color burst → PACK / ALLOW
        other_open = [f for f in self.open if f.chat != chat and f.overlaps(now)]
        packed = bool(other_open)
        self.open.append(OpenFire(fire_id, family, color, chat, now, window_secs, score))
        return PackDecision(
            "ALLOW",
            (
                f"packed into gap while {other_open[0].chat} window still open"
                if packed
                else "slot free — fire"
            ),
            chat,
            fire_id=fire_id,
            packed_gap=packed,
        )

    def snapshot(self, now: float | None = None) -> list[dict[str, Any]]:
        now = time.time() if now is None else float(now)
        self._purge(now)
        return [
            {
                "fire_id": f.fire_id,
                "family": f.family,
                "color": f.color,
                "chat": f.chat,
                "secs_left": round(max(0.0, f.open_until() - now), 1),
                "window_secs": f.window_secs,
                "score": f.score,
            }
            for f in self.open
        ]


def demo() -> None:
    """User example: 35s countdown + other family at +3s..+30s."""
    p = WindowPacker()
    t0 = 1_000_000.0
    d1 = p.admit(
        fire_id="cd1",
        family="COUNTDOWN",
        color="red",
        chat="COUNTDOWN",
        window_secs=35,
        score=5.0,
        now=t0,
    )
    d2 = p.admit(
        fire_id="solo1",
        family="SOLO_ELITE",
        color="blue",
        chat="SOLO",
        window_secs=25,
        score=4.0,
        now=t0 + 3,
    )
    d3 = p.admit(
        fire_id="seq1",
        family="SEQUENCE",
        color="red",
        chat="SEQUENCE",
        window_secs=20,
        score=3.5,
        now=t0 + 12,
    )
    d4 = p.admit(
        fire_id="hub_opp",
        family="GOLDEN",
        color="blue",
        chat="HUB",
        window_secs=30,
        score=6.0,
        now=t0 + 5,
    )
    d5 = p.admit(
        fire_id="hub_opp2",
        family="GOLDEN",
        color="red",
        chat="HUB",
        window_secs=30,
        score=4.0,
        now=t0 + 8,
    )
    for label, d in [
        ("CD 35s", d1),
        ("SOLO @+3s", d2),
        ("SEQ @+12s", d3),
        ("HUB blue", d4),
        ("HUB red (should HOLD)", d5),
    ]:
        print(f"{label}: {d.action} — {d.reason} packed_gap={d.packed_gap}")
    print("open:", p.snapshot(t0 + 15))


if __name__ == "__main__":
    demo()
