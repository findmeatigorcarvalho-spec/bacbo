#!/usr/bin/env python3
"""
peak_fidelity_ranker.py — cross-compare every live floor vs its peak-day system
and rank floors by strength using result-card truth.

Idea (operator):
  - Each floor must fire like its peak day (same gate family, same/more winning volume).
  - Rank by most profitable / assertive / WR / G0.
  - Result cards are ground truth: loss on RED ⇒ actual was BLUE ⇒ blue callers were right
    (and vice versa). Multi-floor agreement on the winning color = extra trust.

Reads:
  bot/data/peak_lock_config.json
  bot/data/historical_luxury_seed.json
  bot/data/luxury_live_floors.json
  bot/bacbo.db (or --db)

Writes:
  bot/data/peak_fidelity_ranker_report.json
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DEFAULT_DB = HERE / "bacbo.db"
REPORT_PATH = DATA / "peak_fidelity_ranker_report.json"

# Prefer export DB when local bot DB is thin/missing.
_EXPORT_DB = Path("/workspace/replit_exports/db/bot/bacbo.db")


def actual_color(predicted: str, outcome: str) -> str:
    """Result-card truth: win keeps predicted; loss flips red↔blue."""
    predicted = (predicted or "").lower().strip()
    outcome = (outcome or "").lower().strip()
    if outcome == "tie":
        return "tie"
    if outcome == "win":
        return predicted
    if outcome == "loss":
        if predicted == "blue":
            return "red"
        if predicted == "red":
            return "blue"
    return "unknown"


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _connect(db_path: Path) -> sqlite3.Connection | None:
    if not db_path.exists():
        return None
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=60)
    conn.row_factory = sqlite3.Row
    return conn


def _parse_floor_list(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        s = raw.strip()
        if not s:
            return []
        if s.startswith("["):
            try:
                return [str(x).strip().upper() for x in json.loads(s) if str(x).strip()]
            except Exception:
                pass
        return [p.strip().upper() for p in s.replace(";", ",").split(",") if p.strip()]
    if isinstance(raw, (list, tuple, set)):
        return [str(x).strip().upper() for x in raw if str(x).strip()]
    return []


def _tower_index(peak_lock: dict, seed: dict, live: dict) -> list[dict[str, Any]]:
    """One row per live floor with peak baseline + gate lock."""
    towers = {str(t.get("floor", "")).upper(): t for t in (peak_lock.get("towers") or [])}
    seed_by = {str(f.get("floor", "")).upper(): f for f in (seed.get("floors") or [])}
    aliases = dict(peak_lock.get("gate_aliases") or live.get("gate_aliases") or {})
    blocked = {
        str(x).upper()
        for x in (live.get("blocked") or peak_lock.get("blocked") or seed.get("hard_block") or [])
    }
    live_floors = [str(x).upper() for x in (live.get("live_floors") or peak_lock.get("live_building_floors") or [])]
    if not live_floors:
        live_floors = sorted(set(towers) | set(seed_by))

    out: list[dict[str, Any]] = []
    for floor in live_floors:
        t = towers.get(floor) or {}
        s = seed_by.get(floor) or {}
        gate = str(t.get("gate") or aliases.get(floor) or floor)
        peak_day = str(t.get("peak_day") or s.get("max_day") or "")
        peak_n = int(t.get("peak_n") or s.get("max_day_signals") or s.get("total") or 0)
        peak_wr = float(t.get("peak_wr") or s.get("max_day_wr") or s.get("final_wr") or 0.0)
        hist_n = int(t.get("historical_n") or s.get("total") or peak_n or 0)
        hist_wr = float(t.get("historical_wr") or s.get("final_wr") or peak_wr or 0.0)
        g0_wr = float(s.get("g0_wr") or 0.0)
        out.append(
            {
                "floor": floor,
                "blocked": floor in blocked,
                "gate": gate,
                "gate_file": t.get("gate_file") or f"_gates_{gate}.py",
                "gate_is_peak_locked": bool(
                    str(gate).endswith("_peak")
                    or "perfect" in str(gate).lower()
                    or "golden" in str(gate).lower()
                    or gate in {"ELITE_V2_PEAK", "ULTIMATE", "ELITE_V2"}
                ),
                "lane": t.get("lane") or s.get("lane") or "UNKNOWN",
                "peak_day": peak_day,
                "peak_n": peak_n,
                "peak_wr": round(peak_wr, 2),
                "historical_n": hist_n,
                "historical_wr": round(hist_wr, 2),
                "historical_g0_wr": round(g0_wr, 2),
                "force_live": bool(t.get("force_live") or s.get("force_live")),
            }
        )
    return out


def _live_floor_stats(conn: sqlite3.Connection) -> dict[str, dict[str, Any]]:
    stats: dict[str, dict[str, Any]] = {}
    rows = conn.execute(
        """
        SELECT COALESCE(NULLIF(UPPER(TRIM(source_floor)), ''), 'UNATTRIBUTED') AS floor,
               COUNT(*) AS n,
               SUM(CASE WHEN outcome='win' THEN 1 ELSE 0 END) AS wins,
               SUM(CASE WHEN outcome='loss' THEN 1 ELSE 0 END) AS losses,
               SUM(CASE WHEN outcome='win' AND COALESCE(won_at_gale,0)=0 THEN 1 ELSE 0 END) AS g0_wins,
               SUM(CASE WHEN outcome IN ('win','loss') THEN 1 ELSE 0 END) AS decided,
               MIN(substr(fired_at,1,10)) AS first_day,
               MAX(substr(fired_at,1,10)) AS last_day
        FROM consensus_signals
        WHERE outcome IS NOT NULL AND outcome != ''
        GROUP BY 1
        """
    ).fetchall()
    for r in rows:
        floor = str(r["floor"])
        decided = int(r["decided"] or 0)
        wins = int(r["wins"] or 0)
        g0 = int(r["g0_wins"] or 0)
        losses = int(r["losses"] or 0)
        wr = round(100.0 * wins / decided, 2) if decided else None
        g0_wr = round(100.0 * g0 / decided, 2) if decided else None
        # profit units ≈ G0 + 0.65*G1_proxy − losses; G1 approx = wins-g0
        g1 = max(0, wins - g0)
        profit = round(g0 + 0.65 * g1 - losses, 2)
        stats[floor] = {
            "live_n": int(r["n"] or 0),
            "live_wins": wins,
            "live_losses": losses,
            "live_g0": g0,
            "live_wr": wr,
            "live_g0_wr": g0_wr,
            "live_profit": profit,
            "first_day": r["first_day"],
            "last_day": r["last_day"],
        }
    return stats


def _blocked_stats(conn: sqlite3.Connection) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    rows = conn.execute(
        """
        SELECT COALESCE(NULLIF(UPPER(TRIM(source_floor)), ''), 'UNATTRIBUTED') AS floor,
               COUNT(*) AS n,
               SUM(CASE WHEN outcome='win' THEN 1 ELSE 0 END) AS blocked_wins,
               SUM(CASE WHEN outcome='loss' THEN 1 ELSE 0 END) AS blocked_losses
        FROM blocked_signals
        GROUP BY 1
        """
    ).fetchall()
    for r in rows:
        out[str(r["floor"])] = {
            "blocked_n": int(r["n"] or 0),
            "blocked_wins": int(r["blocked_wins"] or 0),
            "blocked_losses": int(r["blocked_losses"] or 0),
        }
    return out


def _result_truth_credits(conn: sqlite3.Connection) -> dict[str, dict[str, int]]:
    """
    For each resolved fire:
      actual = result-card truth color
      source_floor credited if its predicted color == actual (win) or flipped logic via outcome
      agreeing_floors (when present) each credited if listed — treated as same predicted color
        as the fire (coalition on that signal).
    """
    credits: dict[str, dict[str, int]] = {}

    def bump(floor: str, key: str) -> None:
        floor = floor.upper()
        slot = credits.setdefault(
            floor,
            {
                "truth_right": 0,
                "truth_wrong": 0,
                "truth_tie": 0,
                "truth_g0_right": 0,
                "as_source": 0,
                "as_agreer": 0,
            },
        )
        slot[key] = int(slot.get(key, 0)) + 1

    rows = conn.execute(
        """
        SELECT color, outcome, source_floor, agreeing_floors, COALESCE(won_at_gale,0) AS g0
        FROM consensus_signals
        WHERE outcome IN ('win','loss','tie')
        """
    ).fetchall()
    for r in rows:
        predicted = (r["color"] or "").lower()
        outcome = (r["outcome"] or "").lower()
        actual = actual_color(predicted, outcome)
        source = (r["source_floor"] or "").strip().upper()
        agreers = _parse_floor_list(r["agreeing_floors"])
        involved = []
        if source:
            involved.append((source, "as_source"))
        for f in agreers:
            if f and f != source:
                involved.append((f, "as_agreer"))
        if not involved and source:
            involved = [(source, "as_source")]

        for floor, role in involved:
            bump(floor, role)
            if actual == "tie":
                bump(floor, "truth_tie")
            elif outcome == "win":
                # predicted == actual
                bump(floor, "truth_right")
                if int(r["g0"] or 0) == 0:
                    bump(floor, "truth_g0_right")
            elif outcome == "loss":
                # predicted != actual — this floor (on predicted side) was wrong
                bump(floor, "truth_wrong")
    return credits


def _peak_day_slice(conn: sqlite3.Connection, peak_day: str, floor: str) -> dict[str, Any]:
    if not peak_day:
        return {"peak_day_db_n": 0, "peak_day_db_wr": None, "peak_day_db_g0": 0}
    # Prefer rows attributed to this floor on peak day; also count all fires that day
    # as volume reference (thin DBs often leave source_floor null).
    row_floor = conn.execute(
        """
        SELECT COUNT(*) n,
               SUM(CASE WHEN outcome='win' THEN 1 ELSE 0 END) wins,
               SUM(CASE WHEN outcome IN ('win','loss') THEN 1 ELSE 0 END) decided,
               SUM(CASE WHEN outcome='win' AND COALESCE(won_at_gale,0)=0 THEN 1 ELSE 0 END) g0
        FROM consensus_signals
        WHERE substr(fired_at,1,10)=?
          AND UPPER(TRIM(COALESCE(source_floor,'')))=?
        """,
        (peak_day, floor),
    ).fetchone()
    row_day = conn.execute(
        """
        SELECT COUNT(*) n,
               SUM(CASE WHEN outcome='win' THEN 1 ELSE 0 END) wins,
               SUM(CASE WHEN outcome IN ('win','loss') THEN 1 ELSE 0 END) decided,
               SUM(CASE WHEN outcome='win' AND COALESCE(won_at_gale,0)=0 THEN 1 ELSE 0 END) g0
        FROM consensus_signals
        WHERE substr(fired_at,1,10)=?
        """,
        (peak_day,),
    ).fetchone()
    decided = int(row_floor["decided"] or 0)
    wr = round(100.0 * int(row_floor["wins"] or 0) / decided, 2) if decided else None
    return {
        "peak_day_db_n_attributed": int(row_floor["n"] or 0),
        "peak_day_db_wr": wr,
        "peak_day_db_g0": int(row_floor["g0"] or 0),
        "peak_day_db_all_floors_n": int(row_day["n"] or 0),
    }


def _fidelity_verdict(row: dict[str, Any]) -> str:
    if row.get("blocked"):
        return "HARD_BLOCK"
    if not row.get("gate_is_peak_locked"):
        return "GATE_NOT_PEAK_LOCKED"
    peak_n = int(row.get("peak_n") or 0)
    live_n = int(row.get("live_n") or 0)
    day_n = int(row.get("peak_day_db_n_attributed") or 0)
    # Historical peak lives in seed; thin live DB cannot replay full peak volume.
    if peak_n >= 100 and day_n == 0 and live_n < max(10, int(0.05 * peak_n)):
        return "VOLUME_GAP_VS_PEAK"  # not firing peak-day style volume under this floor name
    if live_n == 0:
        return "NO_LIVE_ATTRIBUTION"  # silent in current attributed stream
    live_wr = row.get("live_wr")
    peak_wr = float(row.get("peak_wr") or 0)
    if live_wr is not None and peak_wr and live_wr + 5 < peak_wr and live_n >= 20:
        return "WR_BELOW_PEAK"
    if live_n >= max(20, int(0.5 * peak_n)) if peak_n else live_n >= 20:
        return "FIDELITY_OK_OR_BETTER"
    return "PARTIAL_LIVE_SAMPLE"


def _strength_score(row: dict[str, Any]) -> float:
    """Higher = stronger floor for coalition priority."""
    if row.get("blocked"):
        return -1e9
    peak_wr = float(row.get("peak_wr") or row.get("historical_wr") or 0)
    peak_n = float(row.get("peak_n") or row.get("historical_n") or 0)
    g0_wr = float(row.get("historical_g0_wr") or 0)
    live_profit = float(row.get("live_profit") or 0)
    truth_right = int(row.get("truth_right") or 0)
    truth_wrong = int(row.get("truth_wrong") or 0)
    truth_n = truth_right + truth_wrong
    assertiveness = (truth_right / truth_n) if truth_n else 0.0
    blocked_wins = int(row.get("blocked_wins") or 0)
    # Peak economics dominate (seed is day-one truth); live/truth adjust.
    score = (
        peak_wr * 2.0
        + min(peak_n, 5000) / 50.0
        + g0_wr * 1.5
        + live_profit * 0.5
        + assertiveness * 40.0
        + truth_right * 0.25
        - blocked_wins * 0.15  # wins left on floor = missed value
    )
    if row.get("gate_is_peak_locked"):
        score += 5.0
    if row.get("fidelity") == "FIDELITY_OK_OR_BETTER":
        score += 8.0
    elif row.get("fidelity") == "VOLUME_GAP_VS_PEAK":
        score -= 3.0  # still valuable historically; flag for v2 proposers
    return round(score, 2)


def build_report(db_path: Path) -> dict[str, Any]:
    peak_lock = _load_json(DATA / "peak_lock_config.json")
    seed = _load_json(DATA / "historical_luxury_seed.json")
    live = _load_json(DATA / "luxury_live_floors.json")
    towers = _tower_index(peak_lock, seed, live)

    conn = _connect(db_path)
    live_stats = _live_floor_stats(conn) if conn else {}
    blocked = _blocked_stats(conn) if conn else {}
    truth = _result_truth_credits(conn) if conn else {}

    floors_out: list[dict[str, Any]] = []
    for t in towers:
        floor = t["floor"]
        row = dict(t)
        row.update(live_stats.get(floor, {
            "live_n": 0, "live_wins": 0, "live_losses": 0, "live_g0": 0,
            "live_wr": None, "live_g0_wr": None, "live_profit": 0.0,
            "first_day": None, "last_day": None,
        }))
        row.update(blocked.get(floor, {"blocked_n": 0, "blocked_wins": 0, "blocked_losses": 0}))
        row.update(truth.get(floor, {
            "truth_right": 0, "truth_wrong": 0, "truth_tie": 0,
            "truth_g0_right": 0, "as_source": 0, "as_agreer": 0,
        }))
        if conn:
            row.update(_peak_day_slice(conn, row.get("peak_day") or "", floor))
        else:
            row.update({
                "peak_day_db_n_attributed": 0,
                "peak_day_db_wr": None,
                "peak_day_db_g0": 0,
                "peak_day_db_all_floors_n": 0,
            })
        tr = int(row["truth_right"])
        tw = int(row["truth_wrong"])
        row["assertiveness"] = round(100.0 * tr / (tr + tw), 2) if (tr + tw) else None
        row["fidelity"] = _fidelity_verdict(row)
        row["strength_score"] = _strength_score(row)
        # Volume gap vs peak (what operator asked: same or more winning volume)
        peak_n = int(row.get("peak_n") or 0)
        row["volume_vs_peak_pct"] = (
            round(100.0 * int(row.get("live_n") or 0) / peak_n, 2) if peak_n else None
        )
        floors_out.append(row)

    if conn:
        conn.close()

    floors_out.sort(key=lambda r: r.get("strength_score") or 0, reverse=True)
    for i, r in enumerate(floors_out, 1):
        r["rank"] = i

    by_fidelity: dict[str, list[str]] = {}
    for r in floors_out:
        by_fidelity.setdefault(r["fidelity"], []).append(r["floor"])

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "db_path": str(db_path),
        "note": (
            "Peak baselines come from historical seed / peak_lock_config (day-one truth). "
            "Live Replit DB is often truncated — VOLUME_GAP / NO_LIVE_ATTRIBUTION means the "
            "floor is not presenting peak-day opinions in the attributed stream (v1 LIVE bottleneck), "
            "not that the peak day never happened. "
            "Result-card truth: loss on red ⇒ actual blue ⇒ blue side was right."
        ),
        "truth_rule": {
            "win": "actual_color = predicted",
            "loss_on_red": "actual_color = blue → blue floors/opinions right",
            "loss_on_blue": "actual_color = red → red floors/opinions right",
            "multi_floor_same_color": "more trust (coalition confirmation)",
        },
        "counts": {
            "floors": len(floors_out),
            "hard_blocked": sum(1 for r in floors_out if r["blocked"]),
            "peak_gate_locked": sum(1 for r in floors_out if r["gate_is_peak_locked"]),
            "volume_gap_vs_peak": len(by_fidelity.get("VOLUME_GAP_VS_PEAK") or []),
            "no_live_attribution": len(by_fidelity.get("NO_LIVE_ATTRIBUTION") or []),
        },
        "fidelity_groups": by_fidelity,
        "ranking": floors_out,
        "top10": [
            {
                "rank": r["rank"],
                "floor": r["floor"],
                "strength_score": r["strength_score"],
                "peak_day": r["peak_day"],
                "peak_n": r["peak_n"],
                "peak_wr": r["peak_wr"],
                "historical_g0_wr": r["historical_g0_wr"],
                "gate": r["gate"],
                "fidelity": r["fidelity"],
                "assertiveness": r["assertiveness"],
                "blocked_wins": r["blocked_wins"],
            }
            for r in floors_out[:10]
        ],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--db",
        default="",
        help="Path to bacbo.db (default: bot/bacbo.db or export DB)",
    )
    ap.add_argument("--out", default=str(REPORT_PATH), help="Report JSON path")
    args = ap.parse_args()

    db = Path(args.db) if args.db else DEFAULT_DB
    if not db.exists() and _EXPORT_DB.exists():
        db = _EXPORT_DB
    if not db.exists():
        # still emit seed-only ranking
        print(f"[peak_fidelity] WARN no db at {db}; seed/peak_lock only")

    report = build_report(db)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"[peak_fidelity] wrote {out}")
    print("[peak_fidelity] counts", json.dumps(report["counts"]))
    print("[peak_fidelity] top10:")
    for r in report["top10"]:
        print(
            f"  #{r['rank']:02d} {r['floor']:<18} score={r['strength_score']:<8} "
            f"peak={r['peak_day']} n={r['peak_n']:<5} wr={r['peak_wr']} "
            f"gate={r['gate']} fid={r['fidelity']}"
        )
    gaps = report["fidelity_groups"].get("VOLUME_GAP_VS_PEAK") or []
    silent = report["fidelity_groups"].get("NO_LIVE_ATTRIBUTION") or []
    if gaps:
        print(f"[peak_fidelity] VOLUME_GAP_VS_PEAK ({len(gaps)}):", ", ".join(gaps[:20]))
    if silent:
        print(f"[peak_fidelity] NO_LIVE_ATTRIBUTION ({len(silent)}):", ", ".join(silent[:20]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
