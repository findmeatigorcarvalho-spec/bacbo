"""Collapse a G2 ESTUDO burst into one money card.

The 7:03–7:08 PM UNIQUE_g1 flood was not 80 independent rooms. It was the
same 3 rooms repeating the same color with score flicker:

    @sinaisbacboangola  RED   1.54 / 1.55   (×14)
    @sinal_bac_bo       mixed 0.49 / 0.50 / 0.53 / 0.54
    @martinswinbacbo    BLUE  1.59 / 1.78   (×14)

Counting every repeat as a vote fakes a coalition. This module:

  * parses one G2 ESTUDO body
  * groups by (room, color) inside a short window
  * keeps DISTINCT scores only (1.78 and 1.59 are two observations;
    fourteen copies of 1.78 are one)
  * opposite colors in the same room+window become a LOCK, not a blend
  * returns ONE card after the window closes; followers are dropped

Env:
  LUX_G2_COALITION_TO_G1=1   rewrite ESTUDO bursts into one card (default on)
  LUX_G2_COALITION_WINDOW=3.5  seconds to collect score variants
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

HERE = Path(__file__).resolve().parent
LEDGER = HERE / "data" / "g2_coalition.jsonl"

_ROOM_RE = re.compile(
    r"G2\s+ESTUDO\s*\|\s*@?(?P<room>[A-Za-z0-9_]+)",
    re.IGNORECASE,
)
_COLOR_RE = re.compile(r"(?P<emoji>[🔴🔵🟡])\s*(?P<name>RED|BLUE|TIE|EMPATE)", re.IGNORECASE)
_SCORE_RE = re.compile(
    r"(?:NEUTRO|PROMISSORA|BAIXA|CONTR[AÁ]RIO[?]?)[^\d]{0,8}(?P<score>\d+\.\d{1,3})",
    re.IGNORECASE,
)
_SCORE_TAIL = re.compile(r"(?P<score>\d+\.\d{1,3})\s*$")
_INVERT_RE = re.compile(r"INVERTIDO\s*\(\s*original:\s*[🔴🔵🟡]\s*(?P<orig>RED|BLUE)", re.I)


def enabled() -> bool:
    return os.environ.get("LUX_G2_COALITION_TO_G1", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def window_secs() -> float:
    try:
        return max(0.8, float(os.environ.get("LUX_G2_COALITION_WINDOW", "3.5") or "3.5"))
    except Exception:
        return 3.5


@dataclass
class Observation:
    room: str
    color: str
    score: float
    inverted: bool
    original_color: str
    raw: str
    ts: float = field(default_factory=time.time)


def parse(msg: str | None) -> Optional[Observation]:
    if not msg or "ESTUDO" not in msg.upper():
        return None
    room_m = _ROOM_RE.search(msg)
    if not room_m:
        return None
    color_m = _COLOR_RE.search(msg)
    if not color_m:
        return None
    color = color_m.group("name").upper()
    if color == "EMPATE":
        color = "TIE"
    score = 0.0
    sm = _SCORE_RE.search(msg) or _SCORE_TAIL.search(msg.strip())
    if sm:
        try:
            score = float(sm.group("score"))
        except Exception:
            score = 0.0
    inv = _INVERT_RE.search(msg)
    orig = inv.group("orig").upper() if inv else color
    return Observation(
        room=room_m.group("room").lower(),
        color=color,
        score=score,
        inverted=bool(inv),
        original_color=orig,
        raw=msg.strip()[:500],
    )


def _append_ledger(obs: Observation) -> None:
    try:
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        rec = {
            "ts": obs.ts,
            "room": obs.room,
            "color": obs.color,
            "score": obs.score,
            "inverted": obs.inverted,
            "original_color": obs.original_color,
        }
        with LEDGER.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        pass


def coalition_score(scores: list[float]) -> dict:
    """Distinct scores only — copies of the same number do not add votes."""
    uniq: list[float] = []
    seen: set[str] = set()
    for s in scores:
        key = f"{s:.4f}"
        if key in seen:
            continue
        seen.add(key)
        uniq.append(s)
    if not uniq:
        return {"n_raw": len(scores), "n_distinct": 0, "score": 0.0, "min": 0.0, "max": 0.0}
    return {
        "n_raw": len(scores),
        "n_distinct": len(uniq),
        "score": round(sum(uniq) / len(uniq), 4),
        "min": min(uniq),
        "max": max(uniq),
        "distinct": uniq,
    }


def format_card(items: list[Observation]) -> str:
    if not items:
        return ""
    room = items[0].room
    colors = {i.color for i in items}
    by_color: dict[str, list[Observation]] = {}
    for it in items:
        by_color.setdefault(it.color, []).append(it)

    if len(colors) > 1:
        # Same room, opposite colors in one window = LOCK, not a blend.
        parts = ["🔐 G2 LOCK | @{0}".format(room)]
        for col in sorted(colors):
            cs = coalition_score([x.score for x in by_color[col]])
            emoji = "🔵" if col == "BLUE" else "🔴" if col == "RED" else "🟡"
            parts.append(
                f"{emoji} {col}  distinct={cs['n_distinct']}  "
                f"score={cs['score']:.2f}  range={cs['min']:.2f}–{cs['max']:.2f}  "
                f"raw×{cs['n_raw']}"
            )
        parts.append("🧭 opposite colors in one window — do not blend; wait for RESULT")
        parts.append("🧾 copies of the same score were not counted as extra votes")
        return "\n".join(parts)

    col = next(iter(colors))
    cs = coalition_score([x.score for x in items])
    emoji = "🔵" if col == "BLUE" else "🔴" if col == "RED" else "🟡"
    inverted = any(x.inverted for x in items)
    inv_line = ""
    if inverted:
        orig = items[0].original_color
        inv_line = f"\n🔄 some variants INVERTIDO (original {orig})"
    distinct_txt = ", ".join(f"{s:.2f}" for s in cs.get("distinct") or [])
    return (
        f"🔷 G2 COALITION | @{room}\n"
        f"{emoji} {col} G0\n"
        f"📊 distinct scores: {distinct_txt or '—'}\n"
        f"🧮 coalition score {cs['score']:.2f}  "
        f"(mean of {cs['n_distinct']} distinct · raw copies {cs['n_raw']})\n"
        f"🧾 same-score repeats were collapsed — not extra votes"
        f"{inv_line}"
    )


_groups: dict[tuple[str, str], dict] = {}


def _bucket_key(obs: Observation) -> tuple[str, str]:
    # Room is the identity. Color is part of the key so a later opposite-color
    # burst does not merge into the first color; format_card still LOCK-detects
    # if we also fold by room-only. Use room-only so opp-color in the same
    # window becomes one LOCK card.
    return (obs.room, "_")


async def hold_until_window(msg: str | None) -> Optional[str]:
    """Record this ESTUDO body. Leader waits WINDOW seconds then returns ONE card.

    Followers return None (drop). Disabled → always None (raw ESTUDO stays blocked).
    """
    obs = parse(msg)
    if obs is None:
        return None
    _append_ledger(obs)
    if not enabled():
        return None

    key = _bucket_key(obs)
    rec = _groups.setdefault(key, {"items": [], "leader": False})
    rec["items"].append(obs)
    if rec.get("leader"):
        return None
    rec["leader"] = True
    try:
        await asyncio.sleep(window_secs())
        items = list(rec.get("items") or [])
        return format_card(items) or None
    finally:
        _groups.pop(key, None)


def is_g2_estudo(msg: str | None) -> bool:
    if not msg:
        return False
    u = msg.upper()
    return "G2 ESTUDO" in u or bool(_ROOM_RE.search(msg))
