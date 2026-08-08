"""HUB impact learner / watchdog.

Watches every singular gate fire AND every coalition fire → RESULT.
Learns impact (WR, volume contribution, opp-lock harm) so the hub stays
the most resourceful: better primary picks, better spill, better volume.

Attribution keys:
  floor:<NAME>           — peak floor / camada
  room:@handle           — singular room in coalition
  origin:SOLO_FACT       — solo peak fire
  origin:COALITION       — multi-room fire
  kind:GOLDEN|SOLO|…     — signal kind

Env:
  HUB_IMPACT_LEARNER=1   (default on)
"""
from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any, Iterable, Optional

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
SCORES = DATA / "hub_impact_scores.json"
LEDGER = DATA / "hub_impact_ledger.jsonl"
_LOCK = threading.Lock()
_CACHE: dict[str, Any] | None = None


def enabled() -> bool:
    return os.environ.get("HUB_IMPACT_LEARNER", "1").strip().lower() not in {
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
        _CACHE = json.loads(SCORES.read_text(encoding="utf-8"))
    except Exception:
        _CACHE = {"version": 1, "updated_at": 0, "keys": {}}
    return _CACHE


def _save(data: dict[str, Any]) -> None:
    global _CACHE
    DATA.mkdir(parents=True, exist_ok=True)
    data["updated_at"] = time.time()
    tmp = SCORES.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(SCORES)
    _CACHE = data


def _append(event: dict[str, Any]) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, ensure_ascii=False) + "\n")


def _bump(keys: dict[str, Any], key: str, *, win: bool, tie: bool) -> None:
    row = keys.setdefault(
        key,
        {"n": 0, "wins": 0, "losses": 0, "ties": 0, "score": 50.0, "last_ts": 0.0},
    )
    row["n"] = int(row.get("n") or 0) + 1
    if tie:
        row["ties"] = int(row.get("ties") or 0) + 1
    elif win:
        row["wins"] = int(row.get("wins") or 0) + 1
    else:
        row["losses"] = int(row.get("losses") or 0) + 1
    n = max(1, int(row["n"]))
    wr = (int(row["wins"]) + 0.5 * int(row.get("ties") or 0)) / n
    # Resourcefulness score: WR weight + volume presence (log-ish)
    vol = min(40.0, 8.0 * (n ** 0.5))
    row["score"] = round(100.0 * wr * 0.7 + vol * 0.3, 3)
    row["last_ts"] = time.time()
    row["wr"] = round(100.0 * wr, 2)


def observe_fire(
    *,
    signal_id: Any = None,
    floors: Optional[Iterable[str]] = None,
    rooms: Optional[Iterable[str]] = None,
    color: str = "",
    kind: str = "",
    origin: str = "",
    primary_floor: str = "",
) -> None:
    """Watchdog: a fire left the hub (singular or coalition)."""
    if not enabled():
        return
    floors_l = [str(f).upper() for f in (floors or []) if str(f).strip()]
    rooms_l = [str(r).strip().lower().lstrip("@") for r in (rooms or []) if str(r).strip()]
    origin_u = (origin or ("COALITION" if len(rooms_l) >= 2 else "SOLO_FACT")).upper()
    ev = {
        "type": "fire",
        "ts": time.time(),
        "signal_id": signal_id,
        "floors": floors_l,
        "rooms": rooms_l,
        "color": (color or "").lower(),
        "kind": (kind or "").upper(),
        "origin": origin_u,
        "primary_floor": (primary_floor or "").upper(),
    }
    with _LOCK:
        _append(ev)


def observe_result(
    *,
    signal_id: Any = None,
    outcome: str,
    predicted: str = "",
    floors: Optional[Iterable[str]] = None,
    rooms: Optional[Iterable[str]] = None,
    kind: str = "",
    origin: str = "",
    primary_floor: str = "",
) -> None:
    """Learn from RESULT: update impact scores for every attributed proposer."""
    if not enabled():
        return
    outc = (outcome or "").lower()
    win = outc == "win"
    tie = outc == "tie"
    loss = outc == "loss"
    if not (win or tie or loss):
        return
    floors_l = [str(f).upper() for f in (floors or []) if str(f).strip()]
    rooms_l = [str(r).strip().lower().lstrip("@") for r in (rooms or []) if str(r).strip()]
    origin_u = (origin or ("COALITION" if len(rooms_l) >= 2 else "SOLO_FACT")).upper()
    kind_u = (kind or "").upper()
    attrib: list[str] = []
    for f in floors_l:
        attrib.append(f"floor:{f}")
    if primary_floor:
        attrib.append(f"floor:{str(primary_floor).upper()}")
    for r in rooms_l:
        attrib.append(f"room:@{r}")
    attrib.append(f"origin:{origin_u}")
    if kind_u:
        attrib.append(f"kind:{kind_u}")
    # unique
    seen: set[str] = set()
    keys_list = []
    for a in attrib:
        if a not in seen:
            seen.add(a)
            keys_list.append(a)

    with _LOCK:
        data = _load()
        bucket = data.setdefault("keys", {})
        for k in keys_list:
            _bump(bucket, k, win=win, tie=tie)
        _save(data)
        _append(
            {
                "type": "result",
                "ts": time.time(),
                "signal_id": signal_id,
                "outcome": outc,
                "predicted": (predicted or "").lower(),
                "floors": floors_l,
                "rooms": rooms_l,
                "origin": origin_u,
                "kind": kind_u,
                "attributed": keys_list,
            }
        )


def impact_score(key: str, default: float = 50.0) -> float:
    data = _load()
    row = (data.get("keys") or {}).get(key) or {}
    try:
        return float(row.get("score") or default)
    except Exception:
        return default


def floor_boost(floor: str) -> float:
    return impact_score(f"floor:{str(floor).upper()}", 50.0)


def room_boost(room: str) -> float:
    r = str(room).strip().lower().lstrip("@")
    return impact_score(f"room:@{r}", 50.0)


def origin_boost(origin: str) -> float:
    return impact_score(f"origin:{str(origin).upper()}", 50.0)


def enrich_proposal_score(proposal: dict[str, Any]) -> float:
    """Combine static proposal score with live impact learning."""
    base = float(proposal.get("score") or 0.0)
    fl = str(proposal.get("floor") or "").upper()
    boost = floor_boost(fl) if fl else 50.0
    rooms = proposal.get("rooms") or []
    if isinstance(rooms, (list, tuple)) and rooms:
        boost = 0.6 * boost + 0.4 * (
            sum(room_boost(r) for r in rooms) / max(1, len(rooms))
        )
        origin = "COALITION" if len(rooms) >= 2 else "SOLO_FACT"
    else:
        origin = str(proposal.get("origin") or "SOLO_FACT")
    boost = 0.85 * boost + 0.15 * origin_boost(origin)
    # blend: keep base rank but let learner move picks
    return base + (boost - 50.0) * 0.35
