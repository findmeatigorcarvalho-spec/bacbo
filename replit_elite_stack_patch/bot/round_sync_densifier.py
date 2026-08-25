#!/usr/bin/env python3
"""Round Sync Densifier — 1 signal/round (min 1/2) + perfect time-to-bet release.

Mission
-------
Use every spare second of prep (30s…400s+) to pick the best signal, then fire it
at the exact bet window so the user always has time to click — aligned to the
BacBo ~10s interval. Results prefer the next interval-start so color cards map
to the round that just closed.

Phases (per interval)
---------------------
  INTERVAL_OPEN  — interval just started; post RESULT of prior round + arm FIRE
  BET_WINDOW     — TTB remaining in [TTB_RELEASE_MIN, TTB_RELEASE_MAX]; FIRE NOW
  LOCKED         — too late to bet this round (DO NOT BET / skip new fires)
  RESULTING      — waiting for color; hold result cards until next INTERVAL_OPEN
                   when ROUND_SYNC_RESULT_ALIGN=1

Density
-------
  Target: 1 FIRE per chat per round
  Minimum: 1 FIRE per chat per 2 rounds (gap → densify / spill fill)
  Same round + same chat: keep highest-score signal only

Env
---
  ROUND_SYNC=1
  ROUND_INTERVAL_SECS=10
  TTB_IDEAL_SECS=10
  TTB_RELEASE_MAX_SECS=12
  TTB_RELEASE_MIN_SECS=3
  PREP_INVEST_MAX_SECS=400
  ROUND_SYNC_RESULT_ALIGN=1
  ROUND_SYNC_HOLD_PATH=bot/data/round_sync_hold.json
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
HOLD_PATH = Path(
    os.environ.get("ROUND_SYNC_HOLD_PATH")
    or str(DATA / "round_sync_hold.json")
)
STATE_PATH = DATA / "round_sync_state.json"
DENSITY_PATH = DATA / "round_sync_density.json"

_COLOR_RE = re.compile(r"\b(RED|BLUE|VERMELHO|AZUL|TIE|EMPATE)\b|🔴|🔵|🟡", re.I)
_ENTER_RE = re.compile(
    r"ENTER\s+NOW|APOSTE\s+AGORA|ENTRE\s+AGORA|APOSTAR\s+AGORA|"
    r"JANELA\s*[:=]|🟢\s*\d+\s*s|Sinal\s+Retido",
    re.I,
)
_RESULT_RE = re.compile(
    r"\bWIN\b|\bLOSS\b|GANHOU|PERDEU|G0\s*WIN|G1\s*WIN|RESUMIDO\s+FORENSE|"
    r"GREEN\s*·|❌\s*LOSS|✅\s*WIN",
    re.I,
)
_DO_NOT_BET_RE = re.compile(
    r"DO\s+NOT\s+BET|N[AÃ]O\s+APOSTE|RODADA\s+J[AÁ]\s+PASSOU|JANELA\s+FECHADA|EXPIROU",
    re.I,
)


def enabled() -> bool:
    return os.environ.get("ROUND_SYNC", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def _fenv(name: str, default: float) -> float:
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def interval_secs() -> float:
    return max(3.0, _fenv("ROUND_INTERVAL_SECS", 10.0))


def ttb_ideal() -> float:
    return max(1.0, _fenv("TTB_IDEAL_SECS", 10.0))


def ttb_release_max() -> float:
    return max(ttb_release_min() + 0.5, _fenv("TTB_RELEASE_MAX_SECS", 12.0))


def ttb_release_min() -> float:
    return max(0.5, _fenv("TTB_RELEASE_MIN_SECS", 3.0))


def prep_invest_max() -> float:
    return max(30.0, _fenv("PREP_INVEST_MAX_SECS", 400.0))


def result_align() -> bool:
    return os.environ.get("ROUND_SYNC_RESULT_ALIGN", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def printed_secs_are_outcome() -> bool:
    """Printed N on the FIRE card is the outcome timer. Do not HOLD for TTB window."""
    try:
        from reality_law import printed_secs_are_outcome as _ps

        return bool(_ps())
    except Exception:
        return os.environ.get("PRINTED_SECS_ARE_OUTCOME", "1").strip().lower() not in {
            "0",
            "false",
            "no",
            "off",
        }


def result_attach_immediate() -> bool:
    """RESULT under its own FIRE now — default ON (zero intentional delay)."""
    return os.environ.get("RESULT_ATTACH_IMMEDIATE", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


# ── Round phase clock ───────────────────────────────────────────────────────


@dataclass
class PhaseInfo:
    phase: str  # INTERVAL_OPEN | BET_WINDOW | LOCKED | RESULTING
    round_id: int
    interval_start: float
    secs_into_interval: float
    ttb_remaining: float
    next_interval_start: float
    reason: str

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


class RoundPhaseClock:
    """Infer a rolling ~10s grid from anchor + optional DB resolves."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._anchor = self._load_anchor()

    def _load_anchor(self) -> float:
        try:
            if STATE_PATH.is_file():
                data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
                a = float(data.get("anchor") or 0)
                if a > 0:
                    return a
        except Exception:
            pass
        # Align anchor to a clean grid from now
        iv = interval_secs()
        now = time.time()
        return now - (now % iv)

    def _save_anchor(self) -> None:
        try:
            DATA.mkdir(parents=True, exist_ok=True)
            STATE_PATH.write_text(
                json.dumps(
                    {
                        "anchor": self._anchor,
                        "interval_secs": interval_secs(),
                        "ttb_ideal": ttb_ideal(),
                        "updated_at": time.time(),
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
        except Exception:
            pass

    def nudge_from_resolve(self, resolved_at: float) -> None:
        """Snap grid toward observed resolve timestamps (learning)."""
        if resolved_at <= 0:
            return
        iv = interval_secs()
        with self._lock:
            # New anchor = resolved_at floored to interval grid nearest current
            candidate = resolved_at - (resolved_at % iv)
            # Blend lightly so one outlier doesn't wreck the clock
            if abs(candidate - self._anchor) > iv * 3:
                self._anchor = candidate
            else:
                self._anchor = 0.85 * self._anchor + 0.15 * candidate
            self._save_anchor()

    def phase_at(self, now: Optional[float] = None) -> PhaseInfo:
        now = time.time() if now is None else float(now)
        iv = interval_secs()
        with self._lock:
            anchor = self._anchor
        # How far into current interval
        if now < anchor:
            # clock skew — reset
            with self._lock:
                self._anchor = now - (now % iv)
                anchor = self._anchor
                self._save_anchor()
        elapsed_total = now - anchor
        round_id = int(elapsed_total // iv)
        interval_start = anchor + round_id * iv
        secs_into = now - interval_start
        next_start = interval_start + iv
        # TTB = seconds left until interval ends (= next result / lock)
        ttb = max(0.0, next_start - now)

        ideal = ttb_ideal()
        rmax = ttb_release_max()
        rmin = ttb_release_min()

        if secs_into <= 1.0:
            phase = "INTERVAL_OPEN"
            reason = "interval just started — RESULT+FIRE arm"
        elif ttb <= rmax and ttb >= rmin:
            phase = "BET_WINDOW"
            reason = f"TTB {ttb:.1f}s in [{rmin:.0f},{rmax:.0f}] — FIRE NOW"
        elif ttb < rmin:
            phase = "LOCKED"
            reason = f"TTB {ttb:.1f}s < {rmin:.0f}s — too late to bet"
        elif secs_into < (iv - ideal):
            phase = "RESULTING"
            reason = f"prep/invest zone — hold until TTB≤{rmax:.0f}s"
        else:
            phase = "BET_WINDOW"
            reason = f"approaching ideal TTB={ideal:.0f}s"

        return PhaseInfo(
            phase=phase,
            round_id=round_id,
            interval_start=interval_start,
            secs_into_interval=round(secs_into, 3),
            ttb_remaining=round(ttb, 3),
            next_interval_start=next_start,
            reason=reason,
        )


_CLOCK = RoundPhaseClock()


def get_clock() -> RoundPhaseClock:
    return _CLOCK


# ── Hold queue + density ────────────────────────────────────────────────────


@dataclass
class HeldFire:
    fire_key: str
    text: str
    color: str
    family_id: str
    signal_kind: str
    score: float
    chat: str
    clock_a_secs: Optional[float]
    detected_at: float
    ideal_release_at: float
    round_id: int
    source: str = "engine"
    meta: Dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _load_hold() -> List[dict]:
    try:
        if HOLD_PATH.is_file():
            data = json.loads(HOLD_PATH.read_text(encoding="utf-8"))
            return list(data.get("items") or [])
    except Exception:
        pass
    return []


def _save_hold(items: List[dict]) -> None:
    try:
        DATA.mkdir(parents=True, exist_ok=True)
        HOLD_PATH.write_text(
            json.dumps({"items": items, "updated_at": time.time()}, indent=2) + "\n",
            encoding="utf-8",
        )
    except Exception:
        pass


def _load_density() -> Dict[str, Any]:
    try:
        if DENSITY_PATH.is_file():
            return json.loads(DENSITY_PATH.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {"by_chat_round": {}, "fires": []}


def _save_density(data: Dict[str, Any]) -> None:
    try:
        DATA.mkdir(parents=True, exist_ok=True)
        # prune old rounds
        phase = _CLOCK.phase_at()
        keep_after = phase.round_id - 200
        bcr = data.get("by_chat_round") or {}
        data["by_chat_round"] = {
            k: v
            for k, v in bcr.items()
            if int(str(k).split("#")[-1] or 0) >= keep_after
        }
        DENSITY_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    except Exception:
        pass


def extract_color(text: str) -> str:
    t = text or ""
    if "🔴" in t or re.search(r"\b(RED|VERMELHO)\b", t, re.I):
        if "🔵" not in t and not re.search(r"\b(BLUE|AZUL)\b", t, re.I):
            return "red"
    if "🔵" in t or re.search(r"\b(BLUE|AZUL)\b", t, re.I):
        if "🔴" not in t and not re.search(r"\b(RED|VERMELHO)\b", t, re.I):
            return "blue"
    if "🟡" in t or re.search(r"\b(TIE|EMPATE)\b", t, re.I):
        return "tie"
    # both colors present — unknown
    return ""


def extract_clock_a(text: str) -> Optional[float]:
    try:
        from bot.config.skin_families import _extract_clock_n

        n = _extract_clock_n(text or "")
        return float(n) if n is not None else None
    except Exception:
        pass
    m = re.search(r"JANELA\s*[:=]\s*(\d+)\s*s|🟢\s*(\d+)\s*s\s*🟢", text or "", re.I)
    if m:
        try:
            return float(m.group(1) or m.group(2))
        except Exception:
            return None
    return None


def is_fire_text(text: str) -> bool:
    try:
        from sequence_family_wake import forensic_is_live_fire

        if forensic_is_live_fire(text):
            return True
    except Exception:
        pass
    if _DO_NOT_BET_RE.search(text or ""):
        return False
    if _RESULT_RE.search(text or "") and not _ENTER_RE.search(text or ""):
        return False
    return bool(_ENTER_RE.search(text or ""))


def is_result_text(text: str) -> bool:
    if _ENTER_RE.search(text or "") and not _RESULT_RE.search(text or ""):
        return False
    return bool(_RESULT_RE.search(text or ""))


@dataclass
class SyncDecision:
    action: str
    # FIRE_NOW | HOLD_PREP | TOO_LATE | DEDUP | SKIP_NON_FIRE | HOLD_RESULT | RESULT_NOW
    reason: str
    phase: str = ""
    round_id: int = 0
    ttb_remaining: float = 0.0
    chat: str = ""
    held: bool = False
    fire_key: str = ""

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


class RoundSyncDensifier:
    """Decide HOLD vs FIRE_NOW and track per-chat density."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def _chat_for(self, text: str, preferred: Optional[str] = None) -> str:
        if preferred:
            return preferred
        try:
            from chat_shelves import SHELF_COUNTDOWN, SHELF_SNIPER, resolve_shelf

            shelf = resolve_shelf(text)
            if shelf.shelf_id in {SHELF_COUNTDOWN, SHELF_SNIPER}:
                return "UNIQUE_g1"
        except Exception:
            pass
        if extract_clock_a(text) is not None:
            return "UNIQUE_g1"
        return "UNIQUE_g1"

    def _density_key(self, chat: str, round_id: int) -> str:
        return f"{chat}#{round_id}"

    def chat_round_count(self, chat: str, round_id: int) -> int:
        data = _load_density()
        return int((data.get("by_chat_round") or {}).get(self._density_key(chat, round_id), 0))

    def record_fire(self, chat: str, round_id: int, fire_key: str, score: float) -> None:
        data = _load_density()
        bcr = data.setdefault("by_chat_round", {})
        key = self._density_key(chat, round_id)
        bcr[key] = int(bcr.get(key, 0)) + 1
        fires = data.setdefault("fires", [])
        fires.append(
            {
                "chat": chat,
                "round_id": round_id,
                "fire_key": fire_key,
                "score": score,
                "at": time.time(),
            }
        )
        data["fires"] = fires[-500:]
        _save_density(data)

    def densify_gaps(self, chats: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Chats below 1-per-2-rounds minimum over last 4 rounds."""
        chats = chats or ["UNIQUE_g1", "UNIQUE_g2", "UNIQUE_g3", "UNIQUE_g4", "UNIQUE_g5"]
        phase = _CLOCK.phase_at()
        data = _load_density()
        bcr = data.get("by_chat_round") or {}
        gaps = []
        for chat in chats:
            total = 0
            for rid in range(max(0, phase.round_id - 3), phase.round_id + 1):
                total += int(bcr.get(self._density_key(chat, rid), 0))
            # 4 rounds → min 2 fires (1 per 2)
            if total < 2:
                gaps.append(
                    {
                        "chat": chat,
                        "fires_last_4_rounds": total,
                        "need": 2 - total,
                        "target": "1_per_round_min_1_per_2",
                    }
                )
        return gaps

    def decide_fire(
        self,
        text: str,
        *,
        score: float = 0.0,
        signal_kind: str = "",
        family_id: str = "",
        chat: Optional[str] = None,
        fire_key: Optional[str] = None,
        source: str = "engine",
        now: Optional[float] = None,
        force_now: bool = False,
    ) -> SyncDecision:
        if not enabled():
            return SyncDecision("FIRE_NOW", "round_sync_off")
        body = text or ""
        if _DO_NOT_BET_RE.search(body):
            return SyncDecision("SKIP_NON_FIRE", "do_not_bet_skin")
        if not is_fire_text(body):
            return SyncDecision("SKIP_NON_FIRE", "not_enter_fire")

        now = time.time() if now is None else float(now)
        phase = _CLOCK.phase_at(now)
        chat_name = self._chat_for(body, chat)
        key = fire_key or f"{chat_name}:{phase.round_id}:{hash(body) & 0xFFFFFFFF:x}"
        clock_a = extract_clock_a(body)

        # Same-round density: already have a fire in this chat this round?
        # Extra signals → fill gap chats (1/round everywhere) before DEDUP drop.
        existing = self.chat_round_count(chat_name, phase.round_id)
        gap_filled = False
        if existing >= 1 and not force_now:
            gaps = self.densify_gaps()
            for gap in gaps:
                alt = gap.get("chat") or ""
                if alt and alt != chat_name and self.chat_round_count(alt, phase.round_id) < 1:
                    chat_name = alt
                    key = fire_key or f"{chat_name}:{phase.round_id}:{hash(body) & 0xFFFFFFFF:x}"
                    gap_filled = True
                    break
            else:
                try:
                    from human_return_path import record as _hr

                    _hr("late_prevented", "DEDUP — no gap chat; avoided double-burn", chat=chat_name)
                except Exception:
                    pass
                return SyncDecision(
                    "DEDUP",
                    f"already {existing} fire(s) in {chat_name} round {phase.round_id}; no gap chat",
                    phase=phase.phase,
                    round_id=phase.round_id,
                    ttb_remaining=phase.ttb_remaining,
                    chat=chat_name,
                    fire_key=key,
                )

        # Printed N is the outcome timer. Do not HOLD until a 12s TTB remainder.
        if printed_secs_are_outcome():
            force_now = True

        # Long Clock A (30s…400s): always invest spare seconds until live TTB.
        # Card still shows ORIGINAL seconds; we only release when remaining ≤ max.
        if (
            not force_now
            and clock_a is not None
            and float(clock_a) > ttb_release_max()
        ):
            delay = max(0.0, float(clock_a) - ttb_ideal())
            delay = min(delay, prep_invest_max())
            ideal = now + delay
            self._enqueue(
                HeldFire(
                    fire_key=key,
                    text=body,
                    color=extract_color(body),
                    family_id=family_id,
                    signal_kind=signal_kind,
                    score=score,
                    chat=chat_name,
                    clock_a_secs=clock_a,
                    detected_at=now,
                    ideal_release_at=ideal,
                    round_id=phase.round_id,
                    source=source,
                    meta={
                        "from_phase": phase.phase,
                        "invest_secs": round(delay, 2),
                        "clock_a": clock_a,
                    },
                )
            )
            try:
                from human_return_path import record as _hr

                _hr(
                    "prep_hold",
                    f"Clock A={clock_a:.0f}s invest {delay:.1f}s → TTB≈{ttb_ideal():.0f}s",
                    chat=chat_name,
                )
            except Exception:
                pass
            return SyncDecision(
                "HOLD_PREP",
                f"Clock A={clock_a:.0f}s → invest {delay:.1f}s → release at TTB≈{ttb_ideal():.0f}s",
                phase=phase.phase,
                round_id=phase.round_id,
                ttb_remaining=phase.ttb_remaining,
                chat=chat_name,
                held=True,
                fire_key=key,
            )

        if force_now or phase.phase in {"BET_WINDOW", "INTERVAL_OPEN"}:
            # INTERVAL_OPEN / BET_WINDOW: arm so user has full TTB to click
            self.record_fire(chat_name, phase.round_id, key, score)
            try:
                from human_return_path import record as _hr

                _hr(
                    "ttb_fire",
                    phase.reason,
                    chat=chat_name,
                    ttb=phase.ttb_remaining,
                )
                if gap_filled:
                    _hr("gap_fill", f"filled quiet chat {chat_name}", chat=chat_name)
            except Exception:
                pass
            try:
                from factual_card_contract import check_card

                cc = check_card(body)
                if not cc.ok_for_fire:
                    # Still fire if timed — but note missing factual subject gaps
                    print(
                        f"[FACT-CONTRACT] FIRE gaps={cc.gaps} subject={cc.stated_subject_of_matter}"
                    )
            except Exception:
                pass
            return SyncDecision(
                "FIRE_NOW",
                phase.reason,
                phase=phase.phase,
                round_id=phase.round_id,
                ttb_remaining=phase.ttb_remaining,
                chat=chat_name,
                fire_key=key,
            )

        if phase.phase == "LOCKED":
            # Invest into NEXT round instead of burning a late fire
            next_round = phase.round_id + 1
            ideal = phase.next_interval_start + 0.2  # fire at next interval open
            self._enqueue(
                HeldFire(
                    fire_key=key,
                    text=body,
                    color=extract_color(body),
                    family_id=family_id,
                    signal_kind=signal_kind,
                    score=score,
                    chat=chat_name,
                    clock_a_secs=clock_a,
                    detected_at=now,
                    ideal_release_at=ideal,
                    round_id=next_round,
                    source=source,
                    meta={"from_phase": "LOCKED"},
                )
            )
            return SyncDecision(
                "HOLD_PREP",
                f"too late this round — hold for next interval @+{ideal - now:.1f}s",
                phase=phase.phase,
                round_id=next_round,
                ttb_remaining=phase.ttb_remaining,
                chat=chat_name,
                held=True,
                fire_key=key,
            )

        # RESULTING / prep zone — invest spare seconds until TTB window
        # Ideal release: when ttb hits ttb_ideal (or at interval open if clock_a set)
        if clock_a is not None and clock_a > ttb_release_max():
            # Long JANELA: release when remaining clock_a enters release max
            # Approximate: release_at = now + (clock_a - ttb_ideal)
            delay = max(0.0, float(clock_a) - ttb_ideal())
            delay = min(delay, prep_invest_max())
            ideal = now + delay
        else:
            # Untimed ENTER or short clock — aim for current interval's BET_WINDOW
            # Release when ttb_remaining would equal ttb_ideal
            ideal = phase.next_interval_start - ttb_ideal()
            if ideal < now:
                ideal = now  # already in window
            # Cap prep investment
            if ideal - now > prep_invest_max():
                ideal = now + prep_invest_max()

        self._enqueue(
            HeldFire(
                fire_key=key,
                text=body,
                color=extract_color(body),
                family_id=family_id,
                signal_kind=signal_kind,
                score=score,
                chat=chat_name,
                clock_a_secs=clock_a,
                detected_at=now,
                ideal_release_at=ideal,
                round_id=phase.round_id,
                source=source,
                meta={"from_phase": phase.phase, "invest_secs": round(ideal - now, 2)},
            )
        )
        return SyncDecision(
            "HOLD_PREP",
            f"invest {ideal - now:.1f}s prep → release at TTB≈{ttb_ideal():.0f}s ({phase.reason})",
            phase=phase.phase,
            round_id=phase.round_id,
            ttb_remaining=phase.ttb_remaining,
            chat=chat_name,
            held=True,
            fire_key=key,
        )

    def decide_result(
        self,
        text: str,
        *,
        now: Optional[float] = None,
        force_now: bool = False,
    ) -> SyncDecision:
        # Locked law: RESULT attaches under its FIRE immediately — no delay.
        # FIRE↔RESULT law + RESULT_ATTACH_IMMEDIATE: glue RESULT under FIRE now.
        _law_now = False
        try:
            from bot.config.fire_result_law import result_skin_required

            _law_now = result_skin_required()
        except Exception:
            _law_now = True
        if force_now or result_attach_immediate() or _law_now:
            return SyncDecision(
                "RESULT_NOW",
                "attach_immediate_under_fire",
            )
        if not enabled() or not result_align():
            return SyncDecision("RESULT_NOW", "result_align_off")
        if not is_result_text(text or ""):
            return SyncDecision("RESULT_NOW", "not_result")
        now = time.time() if now is None else float(now)
        phase = _CLOCK.phase_at(now)
        if phase.phase == "INTERVAL_OPEN":
            return SyncDecision(
                "RESULT_NOW",
                "interval open — post color for closed round",
                phase=phase.phase,
                round_id=phase.round_id,
                ttb_remaining=phase.ttb_remaining,
            )
        # Legacy align path (only if RESULT_ATTACH_IMMEDIATE=0)
        return SyncDecision(
            "HOLD_RESULT",
            f"align result to next interval in {phase.next_interval_start - now:.1f}s",
            phase=phase.phase,
            round_id=phase.round_id,
            ttb_remaining=phase.ttb_remaining,
            held=True,
        )

    def _enqueue(self, held: HeldFire) -> None:
        with self._lock:
            items = _load_hold()
            # Same chat+round: keep higher score only
            kept: List[dict] = []
            replaced = False
            for it in items:
                same = (
                    it.get("chat") == held.chat
                    and int(it.get("round_id") or -1) == held.round_id
                )
                if same:
                    if float(it.get("score") or 0) >= held.score and not replaced:
                        kept.append(it)
                        replaced = True  # incoming loses
                    elif float(it.get("score") or 0) < held.score:
                        continue  # drop weaker
                    else:
                        kept.append(it)
                else:
                    kept.append(it)
            if not replaced:
                # Check if we already decided incoming loses
                still_has_stronger = any(
                    it.get("chat") == held.chat
                    and int(it.get("round_id") or -1) == held.round_id
                    and float(it.get("score") or 0) >= held.score
                    for it in kept
                )
                if not still_has_stronger:
                    kept.append(held.as_dict())
            # Drop expired prep (> prep_invest_max past detected)
            now = time.time()
            kept = [
                it
                for it in kept
                if now - float(it.get("detected_at") or now) <= prep_invest_max() + 30
            ]
            _save_hold(kept)

    def pop_ready(self, now: Optional[float] = None) -> List[HeldFire]:
        """Return held fires whose ideal_release_at has arrived and phase allows."""
        if not enabled():
            return []
        now = time.time() if now is None else float(now)
        phase = _CLOCK.phase_at(now)
        ready: List[HeldFire] = []
        with self._lock:
            items = _load_hold()
            keep: List[dict] = []
            for it in items:
                ideal = float(it.get("ideal_release_at") or 0)
                # Release when ideal hit AND we're in BET_WINDOW or INTERVAL_OPEN
                # Or ideal overdue by >1s (never miss — force release)
                overdue = now >= ideal
                phase_ok = phase.phase in {"BET_WINDOW", "INTERVAL_OPEN"} or (
                    overdue and now >= ideal + 0.5
                )
                if overdue and phase_ok and phase.phase != "LOCKED":
                    ready.append(
                        HeldFire(
                            fire_key=str(it.get("fire_key") or ""),
                            text=str(it.get("text") or ""),
                            color=str(it.get("color") or ""),
                            family_id=str(it.get("family_id") or ""),
                            signal_kind=str(it.get("signal_kind") or ""),
                            score=float(it.get("score") or 0),
                            chat=str(it.get("chat") or "UNIQUE_g1"),
                            clock_a_secs=it.get("clock_a_secs"),
                            detected_at=float(it.get("detected_at") or now),
                            ideal_release_at=float(it.get("ideal_release_at") or now),
                            round_id=int(it.get("round_id") or phase.round_id),
                            source=str(it.get("source") or "hold"),
                            meta=dict(it.get("meta") or {}),
                        )
                    )
                    self.record_fire(
                        str(it.get("chat") or "UNIQUE_g1"),
                        int(it.get("round_id") or phase.round_id),
                        str(it.get("fire_key") or ""),
                        float(it.get("score") or 0),
                    )
                elif phase.phase == "LOCKED" and overdue:
                    # Push to next round instead of dropping
                    it = dict(it)
                    it["ideal_release_at"] = phase.next_interval_start + 0.2
                    it["round_id"] = phase.round_id + 1
                    keep.append(it)
                else:
                    keep.append(it)
            _save_hold(keep)
        return ready

    def status(self) -> Dict[str, Any]:
        phase = _CLOCK.phase_at()
        hold = _load_hold()
        return {
            "enabled": enabled(),
            "phase": phase.as_dict(),
            "interval_secs": interval_secs(),
            "ttb_ideal": ttb_ideal(),
            "ttb_release_max": ttb_release_max(),
            "ttb_release_min": ttb_release_min(),
            "prep_invest_max": prep_invest_max(),
            "hold_queue": len(hold),
            "density_gaps": self.densify_gaps(),
            "hold_preview": [
                {
                    "chat": h.get("chat"),
                    "round_id": h.get("round_id"),
                    "score": h.get("score"),
                    "ideal_in": round(float(h.get("ideal_release_at") or 0) - time.time(), 1),
                    "clock_a": h.get("clock_a_secs"),
                    "family_id": h.get("family_id"),
                }
                for h in hold[:12]
            ],
        }


_DENSIFIER = RoundSyncDensifier()


def get_densifier() -> RoundSyncDensifier:
    return _DENSIFIER


def decide_fire(*args, **kwargs) -> SyncDecision:
    return _DENSIFIER.decide_fire(*args, **kwargs)


def decide_result(*args, **kwargs) -> SyncDecision:
    return _DENSIFIER.decide_result(*args, **kwargs)


def pop_ready(*args, **kwargs) -> List[HeldFire]:
    return _DENSIFIER.pop_ready(*args, **kwargs)


def status() -> Dict[str, Any]:
    return _DENSIFIER.status()


def main() -> int:
    """CLI: print phase + density status; optional demo hold/release."""
    import argparse

    ap = argparse.ArgumentParser(description="Round sync densifier status")
    ap.add_argument("--demo", action="store_true")
    args = ap.parse_args()
    d = get_densifier()
    if args.demo:
        t0 = time.time()
        # Long prep JANELA 87s
        print(
            "87s janela:",
            d.decide_fire(
                "⏳ Sinal Retido → Liberado\nJANELA: 87s para apostar\n🔵 BLUE",
                score=9.0,
                family_id="FIRE_SINAL_RETIDO_LIBERADO",
                now=t0,
            ),
        )
        print(
            "ENTER NOW:",
            d.decide_fire(
                "🏆 GOLDEN SIGNAL — ENTER NOW 🏆\n🔴 RED",
                score=8.0,
                family_id="FIRE_GOLDEN_ENTER",
                now=t0,
            ),
        )
        print("status:", json.dumps(d.status(), indent=2)[:1200])
    else:
        print(json.dumps(d.status(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
