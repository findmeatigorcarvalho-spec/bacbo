#!/usr/bin/env python3
"""
window_packer.py — Hub intake + ≤30s real-countdown release + elastic chat pack.

User rules (locked):
  - Any window length is fine (35s was only an example).
  - If window > 30s → NOT a real countdown fire yet → HOLD in hub.
  - Release when remaining ≤ 30s; card still shows ORIGINAL seconds.
  - Hub sees EVERY signal from EVERY system config/setup (floors later).
  - Hub dispatches to whichever chat fits best now (timing/profit/WR/volume).
  - As many chats as needed — never drop a signal.
  - Pack other families into gaps; merge only true conflicts.
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Any


REAL_COUNTDOWN_MAX = float(os.environ.get("PACKER_REAL_COUNTDOWN_MAX", "30"))


@dataclass
class SignalCandidate:
    fire_id: str
    family: str
    color: str
    original_secs: float | None  # None = untimed ENTER NOW / etc.
    score: float = 0.0
    wr: float = 0.0
    volume_weight: float = 1.0
    preferred_chat: str | None = None
    detected_at: float = 0.0


@dataclass
class OpenFire:
    fire_id: str
    family: str
    color: str
    chat: str
    t0: float
    window_secs: float  # live window used for packing (≤ REAL_COUNTDOWN_MAX for CD)
    original_secs: float | None = None
    score: float = 0.0

    def open_until(self) -> float:
        return self.t0 + max(0.0, float(self.window_secs))

    def overlaps(self, t: float) -> bool:
        return self.t0 <= t <= self.open_until()


@dataclass
class PackDecision:
    action: str
    # HOLD_UNTIL_REAL | ALLOW | LOCK_KEEP_EXISTING | LOCK_REPLACE | HOLD_HUB | QUEUE_SPAWN
    reason: str
    chat: str | None = None
    fire_id: str | None = None
    replaces: str | None = None
    packed_gap: bool = False
    original_secs: float | None = None
    live_secs: float | None = None
    card_timing_note: str | None = None


@dataclass
class WindowPacker:
    """Hub brain: hold>30s, release≤30s, dispatch to best chat, pack gaps."""

    real_max: float = REAL_COUNTDOWN_MAX
    hub_play_chat: str = field(
        default_factory=lambda: os.environ.get("PACKER_HUB_CHAT", "PLAY").upper()
    )
    same_color_burst: bool = field(
        default_factory=lambda: os.environ.get("PACKER_SAME_COLOR_BURST", "1").strip()
        not in {"0", "false", "no"}
    )
    open: list[OpenFire] = field(default_factory=list)
    hold_queue: list[dict[str, Any]] = field(default_factory=list)
    chats: list[str] = field(
        default_factory=lambda: [
            x.strip().upper()
            for x in (
                os.environ.get("PACKER_CHATS")
                or "PLAY,COUNTDOWN,SOLO,GOLDEN,SEQUENCE"
            ).split(",")
            if x.strip()
        ]
    )

    def _purge(self, now: float) -> None:
        self.open = [f for f in self.open if f.open_until() >= now]

    def _remaining(self, cand: SignalCandidate, now: float) -> float | None:
        if cand.original_secs is None:
            return None
        elapsed = max(0.0, now - (cand.detected_at or now))
        return max(0.0, float(cand.original_secs) - elapsed)

    def _card_note(self, original: float | None, live: float | None) -> str | None:
        if original is None:
            return None
        if live is None or abs(original - live) < 0.05:
            return f"⏱ {original:.0f}s"
        return f"⏱ Original: {original:.0f}s · Live countdown: {live:.0f}s"

    def intake(self, cand: SignalCandidate, now: float | None = None) -> PackDecision:
        """Every config signal enters here first."""
        now = time.time() if now is None else float(now)
        if cand.detected_at <= 0:
            cand.detected_at = now
        rem = self._remaining(cand, now)

        # >30s → hold until real countdown window
        if rem is not None and rem > self.real_max:
            self.hold_queue.append({"cand": cand, "queued_at": now})
            return PackDecision(
                action="HOLD_UNTIL_REAL",
                reason=f"window {rem:.0f}s > {self.real_max:.0f}s — wait for real countdown ≤{self.real_max:.0f}s",
                fire_id=cand.fire_id,
                original_secs=cand.original_secs,
                live_secs=rem,
                card_timing_note=self._card_note(cand.original_secs, rem),
            )

        live = rem if rem is not None else None
        chat = self.pick_chat(cand, now=now, live_secs=live)
        return self.admit_to_chat(
            cand,
            chat=chat,
            live_secs=live if live is not None else (cand.original_secs or 0.0),
            now=now,
        )

    def release_ready(self, now: float | None = None) -> list[PackDecision]:
        """Promote held >30s signals once remaining ≤30s."""
        now = time.time() if now is None else float(now)
        out: list[PackDecision] = []
        keep: list[dict[str, Any]] = []
        for item in self.hold_queue:
            cand: SignalCandidate = item["cand"]
            rem = self._remaining(cand, now)
            if rem is None or rem <= self.real_max:
                out.append(self.intake(cand, now=now))
            else:
                keep.append(item)
        self.hold_queue = keep
        return out

    def pick_chat(
        self,
        cand: SignalCandidate,
        *,
        now: float,
        live_secs: float | None,
    ) -> str:
        """Choose best ready chat for this signal right now (elastic)."""
        self._purge(now)
        family = (cand.family or "").upper()
        color = (cand.color or "").lower()

        # Affinity map (configs → preferred specialist); hub can override
        affinity = {
            "COUNTDOWN": "COUNTDOWN",
            "CD_TIMER": "COUNTDOWN",
            "CLOCK_A": "COUNTDOWN",
            "SOLO_ELITE": "SOLO",
            "GOLDEN": "GOLDEN",
            "COALITION": "GOLDEN",
            "SEQUENCE": "SEQUENCE",
            "PLATINUM": "SOLO",
        }
        preferred = (cand.preferred_chat or affinity.get(family) or "PLAY").upper()
        if preferred not in self.chats:
            self.chats.append(preferred)  # elastic spawn

        def chat_score(chat: str) -> float:
            open_here = [f for f in self.open if f.chat == chat and f.overlaps(now)]
            opp = [
                f
                for f in open_here
                if f.color in {"red", "blue"}
                and color in {"red", "blue"}
                and f.color != color
            ]
            s = 0.0
            if chat == preferred:
                s += 5.0
            s += float(cand.score) * 0.1 + float(cand.wr) * 0.05 + float(cand.volume_weight)
            if not open_here:
                s += 3.0  # free slot
            if opp:
                s -= 10.0  # bad fit
            if live_secs is not None and live_secs <= self.real_max:
                if chat == "COUNTDOWN":
                    s += 2.0
            if chat == self.hub_play_chat and opp:
                s -= 20.0
            return s

        best = max(self.chats, key=chat_score)
        # If all terrible (opp everywhere), spawn fresh chat
        if chat_score(best) < -5:
            spawned = f"AUTO_{family or 'SIG'}_{len(self.chats)+1}"
            self.chats.append(spawned)
            return spawned
        return best

    def admit_to_chat(
        self,
        cand: SignalCandidate,
        *,
        chat: str,
        live_secs: float,
        now: float,
    ) -> PackDecision:
        self._purge(now)
        color = (cand.color or "").lower().strip()
        chat = (chat or "PLAY").upper().strip()
        family = (cand.family or "UNKNOWN").upper().strip()
        window_secs = float(live_secs or 0.0)
        score = float(cand.score or 0.0)
        note = self._card_note(cand.original_secs, live_secs if cand.original_secs else None)

        same_chat = [f for f in self.open if f.chat == chat and f.overlaps(now)]
        opp = [
            f
            for f in same_chat
            if f.color in {"red", "blue"} and color in {"red", "blue"} and f.color != color
        ]
        same = [f for f in same_chat if f.color == color]

        if chat == self.hub_play_chat and opp:
            best = max(opp, key=lambda f: f.score)
            if score > best.score:
                self.open = [f for f in self.open if f.fire_id != best.fire_id]
                self.open.append(
                    OpenFire(
                        cand.fire_id, family, color, chat, now, window_secs, cand.original_secs, score
                    )
                )
                return PackDecision(
                    "LOCK_REPLACE",
                    "PLAY chat opposite-color — replace weaker",
                    chat,
                    cand.fire_id,
                    replaces=best.fire_id,
                    original_secs=cand.original_secs,
                    live_secs=live_secs,
                    card_timing_note=note,
                )
            return PackDecision(
                "HOLD_HUB",
                "PLAY chat opposite-color — keep existing",
                chat,
                fire_id=best.fire_id,
                original_secs=cand.original_secs,
                live_secs=live_secs,
                card_timing_note=note,
            )

        if opp:
            best = max(opp, key=lambda f: f.score)
            if score > best.score:
                self.open = [f for f in self.open if f.fire_id != best.fire_id]
                self.open.append(
                    OpenFire(
                        cand.fire_id, family, color, chat, now, window_secs, cand.original_secs, score
                    )
                )
                return PackDecision(
                    "LOCK_REPLACE",
                    "same-chat opposite-color — replace weaker",
                    chat,
                    cand.fire_id,
                    replaces=best.fire_id,
                    original_secs=cand.original_secs,
                    live_secs=live_secs,
                    card_timing_note=note,
                )
            return PackDecision(
                "LOCK_KEEP_EXISTING",
                "same-chat opposite-color — keep existing",
                chat,
                fire_id=best.fire_id,
                original_secs=cand.original_secs,
                live_secs=live_secs,
                card_timing_note=note,
            )

        if same and not self.same_color_burst:
            best = max(same, key=lambda f: f.score)
            if score <= best.score:
                return PackDecision(
                    "LOCK_KEEP_EXISTING",
                    "same-color coalesce — keep existing",
                    chat,
                    fire_id=best.fire_id,
                    original_secs=cand.original_secs,
                    live_secs=live_secs,
                    card_timing_note=note,
                )

        other_open = [f for f in self.open if f.chat != chat and f.overlaps(now)]
        packed = bool(other_open)
        self.open.append(
            OpenFire(
                cand.fire_id, family, color, chat, now, window_secs, cand.original_secs, score
            )
        )
        return PackDecision(
            "ALLOW",
            (
                f"dispatched → {chat}; packed while {other_open[0].chat} still open"
                if packed
                else f"dispatched → {chat}"
            ),
            chat,
            fire_id=cand.fire_id,
            packed_gap=packed,
            original_secs=cand.original_secs,
            live_secs=live_secs,
            card_timing_note=note,
        )


def demo() -> None:
    p = WindowPacker()
    t0 = 2_000_000.0

    # 87s window — NOT real fire yet
    c_long = SignalCandidate(
        fire_id="long1",
        family="COUNTDOWN",
        color="red",
        original_secs=87,
        score=5,
        wr=78,
        detected_at=t0,
    )
    print("intake 87s:", p.intake(c_long, now=t0))

    # Solo untimed while long is held — still dispatches
    c_solo = SignalCandidate(
        fire_id="solo1",
        family="SOLO_ELITE",
        color="blue",
        original_secs=None,
        score=4,
        wr=80,
        detected_at=t0 + 3,
    )
    print("solo @+3s:", p.intake(c_solo, now=t0 + 3))

    # After 60s elapsed → remaining 27s → real countdown release
    print("release @+60s:", p.release_ready(now=t0 + 60))
    for d in p.release_ready(now=t0 + 60):
        print(" ", d)


if __name__ == "__main__":
    demo()
