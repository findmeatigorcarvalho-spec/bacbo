"""HUB impact learner / watchdog — always the most resourceful.

Watches EVERY:
  · singular gate / floor / camada signal fire → RESULT
  · coalition of signal fires (many same-color proposers) → RESULT
  · opposite-color same-window LOCKS (and whether the lock was right)

Learns impact / affect / effect / result so the hub betters:
  volume, WR, primary picks, spill choices, opp locks, decisions.

Laws (locked):
  · Same color from many machines = normal (coalition strength)
  · Opposite color same window = LOCK
  · Floors are only ONE class of proposer

Attribution keys:
  floor:<NAME>                 — peak floor / camada / system
  room:@handle                 — singular room in coalition
  origin:SOLO_FACT|COALITION   — fire shape
  mode:SINGULAR|COALITION      — explicit watchdog tag
  kind:GOLDEN|SOLO|…           — signal kind
  lock:OPP_COLOR               — opp-lock correctness

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
        _CACHE = {
            "version": 2,
            "updated_at": 0,
            "keys": {},
            "opportunities": {
                "same_color_coalitions": 0,
                "singular_fires": 0,
                "opp_locks": 0,
                "opp_locks_correct": 0,
                "opp_locks_wrong": 0,
                "primary_wins": 0,
                "primary_losses": 0,
            },
        }
    return _CACHE


def _save(data: dict[str, Any]) -> None:
    global _CACHE
    DATA.mkdir(parents=True, exist_ok=True)
    data["updated_at"] = time.time()
    data.setdefault("version", 2)
    tmp = SCORES.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(SCORES)
    _CACHE = data


def _append(event: dict[str, Any]) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, ensure_ascii=False) + "\n")


def _fire_mode(rooms: list[str], floors: list[str], origin: str = "") -> str:
    origin_u = (origin or "").upper()
    if origin_u == "COALITION" or len(rooms) >= 2 or len(floors) >= 2:
        return "COALITION"
    return "SINGULAR"


def _bump(
    keys: dict[str, Any],
    key: str,
    *,
    win: bool,
    tie: bool,
    weight: float = 1.0,
) -> None:
    row = keys.setdefault(
        key,
        {
            "n": 0,
            "wins": 0,
            "losses": 0,
            "ties": 0,
            "score": 50.0,
            "last_ts": 0.0,
            "volume": 0.0,
        },
    )
    w = max(0.25, float(weight))
    row["n"] = float(row.get("n") or 0) + w
    if tie:
        row["ties"] = float(row.get("ties") or 0) + w
    elif win:
        row["wins"] = float(row.get("wins") or 0) + w
    else:
        row["losses"] = float(row.get("losses") or 0) + w
    row["volume"] = float(row.get("volume") or 0) + w
    n = max(0.25, float(row["n"]))
    wr = (float(row["wins"]) + 0.5 * float(row.get("ties") or 0)) / n
    # Resourcefulness: WR + volume presence + recent activity bias
    vol = min(40.0, 8.0 * (n ** 0.5))
    row["score"] = round(100.0 * wr * 0.7 + vol * 0.3, 3)
    row["last_ts"] = time.time()
    row["wr"] = round(100.0 * wr, 2)


def _opp_inc(data: dict[str, Any], key: str, n: float = 1.0) -> None:
    opp = data.setdefault(
        "opportunities",
        {
            "same_color_coalitions": 0,
            "singular_fires": 0,
            "opp_locks": 0,
            "opp_locks_correct": 0,
            "opp_locks_wrong": 0,
            "primary_wins": 0,
            "primary_losses": 0,
        },
    )
    opp[key] = float(opp.get(key) or 0) + n


def observe_fire(
    *,
    signal_id: Any = None,
    floors: Optional[Iterable[str]] = None,
    rooms: Optional[Iterable[str]] = None,
    color: str = "",
    kind: str = "",
    origin: str = "",
    primary_floor: str = "",
    mode: str = "",
) -> None:
    """Watchdog: a fire left the hub (singular or coalition of signal fires)."""
    if not enabled():
        return
    floors_l = [str(f).upper() for f in (floors or []) if str(f).strip()]
    rooms_l = [str(r).strip().lower().lstrip("@") for r in (rooms or []) if str(r).strip()]
    mode_u = (mode or _fire_mode(rooms_l, floors_l, origin)).upper()
    origin_u = (
        origin
        or ("COALITION" if mode_u == "COALITION" else "SOLO_FACT")
    ).upper()
    ev = {
        "type": "fire",
        "ts": time.time(),
        "signal_id": signal_id,
        "floors": floors_l,
        "rooms": rooms_l,
        "color": (color or "").lower(),
        "kind": (kind or "").upper(),
        "origin": origin_u,
        "mode": mode_u,
        "primary_floor": (primary_floor or "").upper(),
        "n_proposers": max(len(floors_l), len(rooms_l), 1),
    }
    with _LOCK:
        data = _load()
        if mode_u == "COALITION":
            _opp_inc(data, "same_color_coalitions")
        else:
            _opp_inc(data, "singular_fires")
        _save(data)
        _append(ev)


def observe_hub_decision(decision: dict[str, Any]) -> None:
    """Watchdog every hub pick: primary + same-color spill + opp locks.

    This is the 'coalition of signal fires' moment — many proposers in,
    one win color out, opp locked.
    """
    if not enabled() or not isinstance(decision, dict):
        return
    primary = decision.get("primary") or {}
    spill = list(decision.get("spill") or [])
    dropped = list(decision.get("dropped_opp") or [])
    color = str(decision.get("color") or primary.get("color") or "").lower()
    n_same = 1 + len(spill) if primary else len(spill)
    mode_u = "COALITION" if n_same >= 2 or dropped else "SINGULAR"
    floors = []
    if primary.get("floor"):
        floors.append(str(primary["floor"]).upper())
    for p in spill:
        if p.get("floor"):
            floors.append(str(p["floor"]).upper())
    rooms: list[str] = []
    for p in [primary, *spill]:
        for r in p.get("rooms") or []:
            rooms.append(str(r).strip().lower().lstrip("@"))
    color_map = decision.get("color_map") or {}
    opp_colors = list(decision.get("opp_locked_colors") or [])
    if not opp_colors:
        opp_colors = sorted(
            {
                str(p.get("color") or "").lower()
                for p in dropped
                if str(p.get("color") or "").strip()
            }
        )
    ev = {
        "type": "hub_decision",
        "ts": time.time(),
        "color": color,
        "mode": mode_u,
        "why": str(decision.get("why") or ""),
        "n_in": int(decision.get("n_in") or 0),
        "n_same_color": n_same,
        "n_opp_locked": len(dropped),
        "primary_floor": str(primary.get("floor") or "").upper(),
        "primary_score": float(primary.get("score") or 0.0),
        "spill_floors": [str(p.get("floor") or "").upper() for p in spill],
        "opp_locked_floors": [
            str(p.get("floor") or "").upper() for p in dropped
        ],
        "opp_locked_colors": opp_colors,
        # which proposers said which color (for result causality later)
        "color_map": color_map,
        "floors": floors,
        "rooms": rooms,
        "understand": (
            f"picked={color} locked={opp_colors or ['none']} "
            f"same={n_same} opp_n={len(dropped)}"
        ),
    }
    with _LOCK:
        data = _load()
        if mode_u == "COALITION":
            _opp_inc(data, "same_color_coalitions")
        else:
            _opp_inc(data, "singular_fires")
        if dropped:
            _opp_inc(data, "opp_locks", float(len(dropped)))
        _save(data)
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
    mode: str = "",
    opp_locked_floors: Optional[Iterable[str]] = None,
    actual_color: str = "",
) -> None:
    """Learn from RESULT: update impact for every attributed proposer + locks."""
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
    mode_u = (mode or _fire_mode(rooms_l, floors_l, origin)).upper()
    origin_u = (
        origin
        or ("COALITION" if mode_u == "COALITION" else "SOLO_FACT")
    ).upper()
    kind_u = (kind or "").upper()
    pred = (predicted or "").lower()
    actual = (actual_color or "").lower()
    attrib: list[str] = []
    for f in floors_l:
        attrib.append(f"floor:{f}")
    if primary_floor:
        attrib.append(f"floor:{str(primary_floor).upper()}")
    for r in rooms_l:
        attrib.append(f"room:@{r}")
    attrib.append(f"origin:{origin_u}")
    attrib.append(f"mode:{mode_u}")
    if kind_u:
        attrib.append(f"kind:{kind_u}")

    # Opp-lock learning: if we know actual color, was locking the opposite right?
    opp_floors = [
        str(f).upper() for f in (opp_locked_floors or []) if str(f).strip()
    ]
    lock_correct: Optional[bool] = None
    if actual and pred:
        # primary predicted color; lock correct if actual != opposite of pred
        # i.e. if result matches pred (win) lock was right; if loss and actual
        # equals the locked side, lock was wrong (missed opportunity).
        if win:
            lock_correct = True
        elif loss and actual and actual != pred:
            lock_correct = False
        elif loss:
            lock_correct = True  # loss but not because opp was the winner color

    if opp_floors:
        attrib.append("lock:OPP_COLOR")

    seen: set[str] = set()
    keys_list = []
    for a in attrib:
        if a not in seen:
            seen.add(a)
            keys_list.append(a)

    # Coalition fires weigh a bit more (more evidence / resourcefulness signal)
    weight = 1.25 if mode_u == "COALITION" else 1.0

    with _LOCK:
        data = _load()
        bucket = data.setdefault("keys", {})
        for k in keys_list:
            _bump(bucket, k, win=win, tie=tie, weight=weight)
        # If opp lock was wrong, gently boost the locked floors so hub
        # considers that color strength next time (resourceful, not flip-flop).
        if lock_correct is False:
            _opp_inc(data, "opp_locks_wrong")
            for f in opp_floors:
                _bump(bucket, f"floor:{f}", win=True, tie=False, weight=0.5)
                _bump(bucket, "lock:OPP_COLOR", win=False, tie=False, weight=0.75)
        elif lock_correct is True and opp_floors:
            _opp_inc(data, "opp_locks_correct")
            _bump(bucket, "lock:OPP_COLOR", win=True, tie=False, weight=0.75)
        if win:
            _opp_inc(data, "primary_wins")
        elif loss:
            _opp_inc(data, "primary_losses")
        # Persist factual winning color for hub orchestrate (LAW 1)
        if actual in {"blue", "red", "tie"}:
            data["last_factual"] = {
                "color": actual,
                "ts": time.time(),
                "signal_id": signal_id,
                "predicted": pred,
                "outcome": outc,
            }
        _save(data)
        _append(
            {
                "type": "result",
                "ts": time.time(),
                "signal_id": signal_id,
                "outcome": outc,
                "predicted": pred,
                "actual": actual,
                "floors": floors_l,
                "rooms": rooms_l,
                "origin": origin_u,
                "mode": mode_u,
                "kind": kind_u,
                "attributed": keys_list,
                "opp_locked_floors": opp_floors,
                "lock_correct": lock_correct,
                "weight": weight,
            }
        )


def latest_factual_color(*, max_age_secs: float = 120.0) -> str:
    """Most recent RESULT-derived actual winning color (LAW: factual truth).

    Used by hub_orchestrate when committee must defer to reality.
    Returns '' when unknown / stale.
    """
    try:
        if not LEDGER.is_file():
            return ""
        lines = LEDGER.read_text(encoding="utf-8").splitlines()[-80:]
    except Exception:
        return ""
    now = time.time()
    for ln in reversed(lines):
        try:
            row = json.loads(ln)
        except Exception:
            continue
        if row.get("type") != "result":
            continue
        actual = str(row.get("actual") or "").strip().lower()
        if actual not in {"blue", "red"}:
            continue
        ts = float(row.get("ts") or 0)
        if ts and (now - ts) > max_age_secs:
            return ""
        return actual
    # fallback: scores blob
    with _LOCK:
        data = _load()
        fc = str((data.get("last_factual") or {}).get("color") or "").lower()
        ts = float((data.get("last_factual") or {}).get("ts") or 0)
    if fc in {"blue", "red"} and ts and (now - ts) <= max_age_secs:
        return fc
    return ""


def last_opp_locked_floors() -> list[str]:
    """Opp-locked floors from the most recent hub_decision (for RESULT learn)."""
    try:
        if not LEDGER.is_file():
            return []
        lines = LEDGER.read_text(encoding="utf-8").splitlines()[-60:]
    except Exception:
        return []
    for ln in reversed(lines):
        try:
            row = json.loads(ln)
        except Exception:
            continue
        if row.get("type") != "hub_decision":
            continue
        floors = row.get("opp_locked_floors") or []
        return [str(f).upper() for f in floors if str(f).strip()]
    return []


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


def mode_boost(mode: str) -> float:
    return impact_score(f"mode:{str(mode).upper()}", 50.0)


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
        mode = "COALITION" if len(rooms) >= 2 else "SINGULAR"
        origin = "COALITION" if mode == "COALITION" else "SOLO_FACT"
    else:
        origin = str(proposal.get("origin") or "SOLO_FACT")
        mode = "COALITION" if origin.upper() == "COALITION" else "SINGULAR"
    boost = 0.75 * boost + 0.15 * origin_boost(origin) + 0.10 * mode_boost(mode)
    # blend: keep base rank but let learner move picks (resourceful)
    return base + (boost - 50.0) * 0.40


def resourcefulness_snapshot() -> dict[str, Any]:
    """What the watchdog currently believes helps volume / WR / choices."""
    data = _load()
    keys = data.get("keys") or {}
    floors = [
        (k, v)
        for k, v in keys.items()
        if str(k).startswith("floor:")
    ]
    floors.sort(key=lambda kv: float(kv[1].get("score") or 0), reverse=True)
    rooms = [
        (k, v)
        for k, v in keys.items()
        if str(k).startswith("room:")
    ]
    rooms.sort(key=lambda kv: float(kv[1].get("score") or 0), reverse=True)
    opp = data.get("opportunities") or {}
    return {
        "updated_at": data.get("updated_at"),
        "opportunities": opp,
        "top_floors": [
            {"key": k, "score": v.get("score"), "wr": v.get("wr"), "n": v.get("n")}
            for k, v in floors[:12]
        ],
        "top_rooms": [
            {"key": k, "score": v.get("score"), "wr": v.get("wr"), "n": v.get("n")}
            for k, v in rooms[:12]
        ],
        "lock_opp_score": impact_score("lock:OPP_COLOR", 50.0),
        "mode_coalition": impact_score("mode:COALITION", 50.0),
        "mode_singular": impact_score("mode:SINGULAR", 50.0),
        "emanate": (
            "same-color coalitions scored; opp locks audited "
            "(which color won / which locked / what RESULT did); "
            "primary picks biased toward proven volume+WR proposers; "
            "chat watchdog knows what lands or never leaves"
        ),
    }


def understand_lock_matrix(limit: int = 40) -> dict[str, Any]:
    """Read recent hub_decision + result pairs: which/when/what happened or didn't."""
    rows: list[dict[str, Any]] = []
    try:
        if LEDGER.is_file():
            lines = LEDGER.read_text(encoding="utf-8").splitlines()[-max(50, limit * 3) :]
            for ln in lines:
                try:
                    rows.append(json.loads(ln))
                except Exception:
                    continue
    except Exception:
        pass
    decisions = [r for r in rows if r.get("type") == "hub_decision"][-limit:]
    results = [r for r in rows if r.get("type") == "result"][-limit:]
    return {
        "recent_decisions": [
            {
                "understand": d.get("understand"),
                "color": d.get("color"),
                "opp_locked_colors": d.get("opp_locked_colors"),
                "primary_floor": d.get("primary_floor"),
                "mode": d.get("mode"),
                "n_same_color": d.get("n_same_color"),
                "n_opp_locked": d.get("n_opp_locked"),
            }
            for d in decisions
        ],
        "recent_results": [
            {
                "outcome": r.get("outcome"),
                "predicted": r.get("predicted"),
                "actual": r.get("actual"),
                "lock_correct": r.get("lock_correct"),
                "mode": r.get("mode"),
                "floors": r.get("floors"),
            }
            for r in results
        ],
        "opportunities": (_load().get("opportunities") or {}),
    }
