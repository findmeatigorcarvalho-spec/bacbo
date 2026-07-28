#!/usr/bin/env python3
"""
hub_dispatch.py — Gunique-first trust routing + original-style cards.

When HUB_MAX=1 / HUB_GUNIQUE_FIRST=1:
  - Score each fire by TRUST (kind, score, rooms, floor)
  - HIGH trust  → @UNIQUE_g1 (priority #1, 24/7)
  - LOWER trust → Mr_iv4 money chat (#2)
  - Results follow parent peer

Card skins: original family look (GOLDEN / SOLO / SEQUENCE), facts refreshed.
Catch-up throttle: do not dump a huge backlog in one tick.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
PEER_STATE = DATA / "hub_peer_by_signal.json"
TRUST_LOG = DATA / "hub_trust_dispatch.jsonl"

_KIND_TRUST = {
    "SOLO_ELITE": 88,
    "GOLDEN": 85,
    "PLATINUM": 82,
    "SEQUENCE": 80,
    "FLASH": 72,
    "COUNTDOWN": 90,
    "CD_TIMER": 90,
}

GUNIQUE_TRUST_MIN = float(os.environ.get("HUB_GUNIQUE_TRUST_MIN", "78"))
CATCHUP_MAX_PER_TICK = int(os.environ.get("HUB_CATCHUP_MAX_PER_TICK", "4"))


def hub_enabled() -> bool:
    return os.environ.get("HUB_MAX", "0").strip() not in {"0", "false", "no", "off"}


def gunique_first() -> bool:
    return os.environ.get("HUB_GUNIQUE_FIRST", "1").strip() not in {"0", "false", "no", "off"}


def _room_n(rooms: Any) -> int:
    if rooms is None:
        return 0
    if isinstance(rooms, (list, tuple, set)):
        return len([x for x in rooms if str(x).strip()])
    s = str(rooms).strip()
    if not s or s.lower() == "engine":
        return 0
    if s.isdigit():
        return int(s)
    return len([p for p in s.replace(";", ",").split(",") if p.strip()])


def trust_score(
    *,
    signal_kind: str | None,
    score: float,
    rooms_agreed: Any = None,
    source_floor: str | None = None,
    color: str | None = None,
) -> dict[str, Any]:
    kind = (signal_kind or "").strip().upper()
    base = float(_KIND_TRUST.get(kind, 65))
    sc = float(score or 0.0)
    if sc <= 12:
        score_pts = min(20.0, sc * 2.0)
    else:
        score_pts = min(20.0, sc / 5.0)
    rooms = _room_n(rooms_agreed)
    if rooms >= 3:
        room_pts, origin = 8.0, "COALITION"
    elif rooms == 2:
        room_pts, origin = 5.0, "COALITION"
    elif rooms == 1:
        room_pts = 6.0 if kind in {"SOLO_ELITE", "PLATINUM"} else 3.0
        origin = "SOLO"
    else:
        room_pts, origin = 2.0, "UNKNOWN"
    floor = (source_floor or "").strip().upper()
    floor_pts = 3.0 if floor and floor not in {"LIVE", ""} else 0.0
    if kind == "SOLO_ELITE" and sc >= 70:
        base += 4
    if kind == "GOLDEN" and rooms >= 2:
        base += 3
    total = min(100.0, base + score_pts + room_pts + floor_pts)
    to_gunique = bool(gunique_first() and total >= GUNIQUE_TRUST_MIN)
    return {
        "trust": round(total, 2),
        "to_gunique": to_gunique,
        "peer_slot": "GUNIQUE" if to_gunique else "MONEY",
        "origin": origin,
        "kind": kind,
        "floor": floor or "LIVE",
        "rooms": rooms,
        "color": (color or "").lower(),
        "threshold": GUNIQUE_TRUST_MIN,
        "reason": (
            f"trust {total:.1f}>={GUNIQUE_TRUST_MIN} → Gunique #1"
            if to_gunique
            else f"trust {total:.1f}<{GUNIQUE_TRUST_MIN} → money #2"
        ),
    }


def _load_peers() -> dict[str, str]:
    try:
        if PEER_STATE.exists():
            d = json.loads(PEER_STATE.read_text(encoding="utf-8"))
            if isinstance(d, dict):
                return {str(k): str(v).upper() for k, v in d.items()}
    except Exception:
        pass
    return {}


def _save_peers(m: dict[str, str]) -> None:
    try:
        DATA.mkdir(parents=True, exist_ok=True)
        if len(m) > 20000:
            keys = sorted(m.keys(), key=lambda x: int(x) if str(x).isdigit() else 0)
            m = {k: m[k] for k in keys[-20000:]}
        PEER_STATE.write_text(json.dumps(m), encoding="utf-8")
    except Exception:
        pass


def persist_peer_slot(signal_id: int | str, slot: str) -> None:
    slot = "GUNIQUE" if str(slot).upper() == "GUNIQUE" else "MONEY"
    m = _load_peers()
    m[str(signal_id)] = slot
    _save_peers(m)
    try:
        from dual_lane_router import persist_fire_lane

        persist_fire_lane(signal_id, "COUNTDOWN" if slot == "GUNIQUE" else "MONEY")
    except Exception:
        pass


def parent_peer_slot(signal_id: int | str) -> str | None:
    v = _load_peers().get(str(signal_id))
    if v in {"GUNIQUE", "MONEY"}:
        return v
    try:
        from dual_lane_router import parent_lane_for

        lane = parent_lane_for(signal_id)
        if lane == "COUNTDOWN":
            return "GUNIQUE"
        if lane == "MONEY":
            return "MONEY"
    except Exception:
        pass
    return None


def log_dispatch(signal_id: Any, info: dict[str, Any]) -> None:
    try:
        DATA.mkdir(parents=True, exist_ok=True)
        row = {"ts": time.time(), "id": signal_id, **{k: v for k, v in info.items() if k != "card_text"}}
        with TRUST_LOG.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        pass


def throttle_rows(rows: list) -> list:
    if not rows:
        return []
    max_n = max(1, CATCHUP_MAX_PER_TICK)
    if len(rows) <= max_n:
        return list(rows)
    ranked = sorted(rows, key=lambda r: int(r["id"]), reverse=True)
    return list(reversed(ranked[:max_n]))


def _row_get(row: Any, key: str, default: Any = None) -> Any:
    try:
        return row[key]
    except Exception:
        return default


def fmt_original_fire(row: Any, *, floor: str, trust: dict[str, Any]) -> str:
    kind = str(_row_get(row, "signal_kind") or trust.get("kind") or "SIGNAL").upper()
    color = str(_row_get(row, "color") or trust.get("color") or "").lower()
    rooms = _row_get(row, "rooms_agreed") or ""
    score = 0.0
    for key in ("total_score", "final_score", "confidence_pct", "calibrated_pct"):
        v = _row_get(row, key)
        if v is None:
            continue
        try:
            f = float(v)
        except Exception:
            continue
        if f != 0:
            score = f
            break
    color_label = "Azul" if color == "blue" else "Vermelho" if color == "red" else color.upper()
    emoji = "🔵" if color == "blue" else "🔴" if color == "red" else "🟡"
    origin = trust.get("origin") or "SIGNAL"
    trust_n = trust.get("trust")
    slot = trust.get("peer_slot")

    if kind == "GOLDEN" or (origin == "COALITION" and kind in {"GOLDEN", "FLASH"}):
        return (
            "🏆 GOLDEN SIGNAL — ENTER NOW 🏆\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 Enter: {emoji} {color_label}\n"
            "   └ _Primary bet — full bankroll_\n"
            "🟡 + Tie _Empate_ as protection\n"
            "   └ _Side bet — 10% of bankroll_\n\n"
            f"📊 Score: {score:.0f} · Trust {trust_n}\n"
            f"🏛 Floor: {floor} · {origin}\n"
            f"🏠 Rooms: {rooms or '—'}\n"
            f"📡 Route: {slot} (Gunique-first by trust)\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "⚡ ENTER NOW\n"
            "_After result: /win · /loss · /tie_"
        )

    if kind == "SOLO_ELITE" or (origin == "SOLO" and kind not in {"SEQUENCE", "GOLDEN"}):
        return (
            "💎 SOLO ELITE SIGNAL 💎\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 Enter: {emoji} {color_label}\n"
            "   └ _Primary bet — full bankroll_\n"
            "🟡 + Tie as protection (10%)\n\n"
            f"🏆 Room: {rooms or 'solo'}\n"
            f"📊 Score: {score:.2f} · Trust {trust_n}\n"
            f"🏛 Floor: {floor}\n"
            "📌 SOLO FACT — not multi-room consensus\n"
            f"📡 Route: {slot}\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "⚡ ENTER NOW — HIGH-PERFORMANCE\n"
            "_After result: /win · /loss · /tie_"
        )

    if kind == "SEQUENCE":
        return (
            "🔥 SEQUÊNCIA — ENTER NOW 🔥\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 Cor: {emoji} {color_label}\n"
            f"📊 Score: {score:.0f} · Trust {trust_n}\n"
            f"🏛 Floor: {floor} · Room: {rooms or '—'}\n"
            f"📡 Route: {slot}\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "⚡ ENTER NOW\n"
            "_After result: /win · /loss · /tie_"
        )

    return (
        f"⚡ {kind} SIGNAL — ENTER NOW ⚡\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎯 Enter: {emoji} {color_label}\n"
        f"📊 Score: {score:.0f} · Trust {trust_n}\n"
        f"🏛 Floor: {floor} · {origin}\n"
        f"🏠 Rooms: {rooms or '—'}\n"
        f"📡 Route: {slot}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "⚡ ENTER NOW\n"
        "_After result: /win · /loss · /tie_"
    )


def dispatch_fire(row: Any, *, floor: str, score: float) -> dict[str, Any]:
    kind = _row_get(row, "signal_kind")
    color = _row_get(row, "color")
    rooms = _row_get(row, "rooms_agreed")
    sid = _row_get(row, "id")
    info = trust_score(
        signal_kind=str(kind or ""),
        score=score,
        rooms_agreed=rooms,
        source_floor=floor,
        color=str(color or ""),
    )
    body = fmt_original_fire(row, floor=floor, trust=info)
    if sid is not None:
        persist_peer_slot(sid, info["peer_slot"])
        log_dispatch(sid, info)
    info["card_text"] = body
    return info


if __name__ == "__main__":
    class R(dict):
        pass

    demo = R(id=1, signal_kind="SOLO_ELITE", color="blue", rooms_agreed="@x8sinais", total_score=99)
    print(json.dumps({k: v for k, v in dispatch_fire(demo, floor="JUN19", score=99).items() if k != "card_text"}, indent=2))
    print("---")
    print(dispatch_fire(demo, floor="JUN19", score=99)["card_text"][:400])
