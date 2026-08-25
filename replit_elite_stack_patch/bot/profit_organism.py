#!/usr/bin/env python3
"""
profit_organism.py — living max-EV brain.

Aggregates peak fidelity, vault patterns, card economics, zero-miss, dual-lane
into one operating directive + $/day projection scaffold.

  python3 bot/profit_organism.py --db bot/bacbo.db --stake 10
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
ROOT = HERE.parent
REPORT = DATA / "profit_organism_report.json"
_EXPORT_DB = Path("/workspace/replit_exports/db/bot/bacbo.db")


def _load(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _run(script: str, db: Path) -> None:
    cmd = [sys.executable, str(HERE / script), "--db", str(db)]
    try:
        subprocess.run(cmd, check=False, cwd=str(ROOT), capture_output=True, text=True, timeout=120)
    except Exception as exc:
        print(f"[organism] warn {script}: {exc}")


def _vault_perfect(vault: dict | None) -> list[dict]:
    if not vault:
        return []
    out = []
    for p in vault.get("vault_patterns") or []:
        w = int(p.get("alltime_W") or 0)
        l = int(p.get("alltime_L") or 0)
        if w >= 8 and l == 0:
            out.append(
                {
                    "keys": p.get("keys"),
                    "values": p.get("values"),
                    "W": w,
                    "L": l,
                    "recent_W": p.get("recent_W"),
                    "recent_L": p.get("recent_L"),
                }
            )
    out.sort(key=lambda x: -int(x["W"]))
    return out[:40]


def _dollar_projection(peak_g0_day: float, capture: float, stake: float, floors_active: int) -> dict:
    """
    Honest scaffold:
      base = best single-day G0 from forensics
      multi_floor_uplift = min(2.5, 1 + 0.04 * floors_that_can_propose)  # not magic; capture of parallel opinions
      expected_g0 = base * capture * uplift
      $ = expected_g0 * stake   (G0 unit ≈ 1 stake win; losses not subtracted here — WR gate assumed)
    """
    uplift = min(2.5, 1.0 + 0.04 * max(0, floors_active))
    cap = max(0.05, min(1.0, capture))
    exp_g0 = peak_g0_day * cap * uplift
    return {
        "assumptions": {
            "peak_g0_reference_day": peak_g0_day,
            "win_capture_rate": cap,
            "multi_floor_uplift": round(uplift, 3),
            "stake_per_g0_unit_usd": stake,
            "note": "Projection of G0 density × stake. Not a guarantee. Losses/bankroll mgmt separate.",
        },
        "expected_g0_per_day": round(exp_g0, 1),
        "expected_usd_per_day_g0_only": round(exp_g0 * stake, 2),
        "band_usd": {
            "conservative": round(exp_g0 * stake * 0.5, 2),
            "target_low": 5000,
            "target_high": 20000,
            "hits_5k": bool(exp_g0 * stake >= 5000),
            "hits_20k": bool(exp_g0 * stake >= 20000),
            "stake_needed_for_5k": round(5000 / exp_g0, 2) if exp_g0 else None,
            "stake_needed_for_20k": round(20000 / exp_g0, 2) if exp_g0 else None,
        },
    }


def build(db: Path, stake: float) -> dict[str, Any]:
    # Refresh dependent reports
    _run("peak_fidelity_ranker.py", db)
    _run("zero_miss_ledger.py", db)

    fidelity = _load(DATA / "peak_fidelity_ranker_report.json") or {}
    zero = _load(DATA / "zero_miss_report.json") or {}
    vault = _load(DATA / "vault_patterns.json")
    if vault is None:
        vault = _load(
            Path("/workspace/replit_exports/light/luxury_export_20260720T073013Z/bot_data/vault_patterns.json")
        )
    cards = _load(Path("/opt/cursor/artifacts/profitable_types_ranked.json")) or _load(
        DATA / "profitable_types_ranked.json"
    )
    setups = _load(Path("/opt/cursor/artifacts/telegram_best_setups_g0.json")) or {}
    lane_scan = _load(DATA / "mega_lane_split_scan.json") or {}

    ranking = fidelity.get("ranking") or []
    top = fidelity.get("top10") or ranking[:10]
    gaps = (fidelity.get("fidelity_groups") or {}).get("VOLUME_GAP_VS_PEAK") or []
    silent = (fidelity.get("fidelity_groups") or {}).get("NO_LIVE_ATTRIBUTION") or []
    not_locked = (fidelity.get("fidelity_groups") or {}).get("GATE_NOT_PEAK_LOCKED") or []

    zc = zero.get("counts") or {}
    capture = float(zc.get("win_capture_rate_pct") or 0) / 100.0
    if capture <= 0:
        capture = 0.55  # unknown → assume leaky until proven

    # Best G0 day from telegram forensics
    peak_g0 = 505.0
    if setups.get("top_g0_days"):
        try:
            peak_g0 = float(setups["top_g0_days"][0][1])
        except Exception:
            pass

    floors_active = len([r for r in ranking if not r.get("blocked")])
    dollars = _dollar_projection(peak_g0, min(0.95, capture + 0.25), stake, floors_active)

    perfect = _vault_perfect(vault if isinstance(vault, dict) else None)

    directives = [
        "DUAL_LANE: money fires (no timer) → Mr_iv4 coalition; countdown-seconds fires → Gunique + CD result glue",
        "V2_PROPOSERS: every live floor must propose (close VOLUME_GAP / NO_LIVE_ATTRIBUTION)",
        "ZERO_MISS: blocked_wins must trend to 0 except HARD_BLOCK floors",
        "VAULT_FORCE: promote 0-loss vault patterns into propose score / whitelist",
        "RESULT_TRUTH: loss on red ⇒ blue was right; weight coalition toward actual color learners",
        "PEAK_LOCK: finish gate aliases for GATE_NOT_PEAK_LOCKED floors",
        "USER_UX: one money chat + one countdown chat; result always under its fire; no AUTO relay spam",
        "STAKE: set unit stake so expected_g0_per_day × stake enters $5k–$20k band when capture≥0.9",
    ]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "organism": "PROFIT_ORGANISM_v1",
        "db_path": str(db),
        "mission": {
            "max_wr": True,
            "max_g0": True,
            "max_volume": True,
            "zero_missed_winners": True,
            "each_floor_ge_peak_day": True,
            "usd_day_target": [5000, 20000],
            "user_friendly_dual_chat": True,
        },
        "vitals": {
            "floors_ranked": len(ranking),
            "volume_gap_floors": gaps,
            "silent_floors": silent,
            "gates_not_peak_locked": not_locked,
            "zero_miss": zc,
            "vault_perfect_0L_patterns": len(perfect),
            "lane_scan_msgs": lane_scan.get("messages_scanned"),
            "lane_scan_stats": lane_scan.get("stats"),
        },
        "strength_top10": top,
        "vault_perfect_top": perfect[:15],
        "dollar_projection": dollars,
        "directives": directives,
        "next_build": [
            "Wire dual_lane_router into telegram_outbox (TELEGRAM_COUNTDOWN_PEER=Gunique)",
            "v2 floor proposers feeding money-lane coalition",
            "Score proposers with vault_perfect + peak_fidelity strength_score",
            "Live zero_miss hooks on every BLOCK/SEND/RESOLVE",
            "Full room-post pattern mine with holdout (promote only durable edges)",
        ],
        "hard_block": ["JUN12A", "JUN12B"],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="")
    ap.add_argument("--stake", type=float, default=10.0, help="USD per G0 unit for projection")
    ap.add_argument("--out", default=str(REPORT))
    args = ap.parse_args()
    db = Path(args.db) if args.db else (HERE / "bacbo.db")
    if not db.exists() and _EXPORT_DB.exists():
        db = _EXPORT_DB
    report = build(db, args.stake)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("[organism] wrote", out)
    print("[organism] directives:")
    for d in report["directives"]:
        print(" -", d)
    print("[organism] $/day projection", json.dumps(report["dollar_projection"]["band_usd"]))
    print("[organism] expected_g0/day", report["dollar_projection"]["expected_g0_per_day"])
    print("[organism] volume_gap", len(report["vitals"]["volume_gap_floors"]), "silent", len(report["vitals"]["silent_floors"]))
    print("[organism] vault 0L patterns", report["vitals"]["vault_perfect_0L_patterns"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
