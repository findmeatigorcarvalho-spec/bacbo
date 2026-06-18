"""
elite_stack_audit.py — one command to audit rooms, OmniScore, and early edge.

Run from Replit shell:

    cd bot
    python elite_stack_audit.py

It writes:
    bot/data/elite_stack_audit.json
    bot/data/room_cleaner_report.json
    bot/data/omni_score_report.json
    bot/data/early_result_audit.json
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone

import early_result_audit
import martingale_audit
import omni_score
import result_lag_miner
import room_cleaner
import truth_verifier


HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(HERE, "bacbo.db")
REPORT_PATH = os.path.join(HERE, "data", "elite_stack_audit.json")


def build_audit(db_path: str = DB_PATH, recent: int = 100) -> dict:
    rooms = room_cleaner.analyze_rooms(db_path)
    room_report = room_cleaner.save_report(rooms)

    omni_results = omni_score.score_recent_fired(recent, db_path)
    omni_report = omni_score.save_report(omni_results)

    early_report = early_result_audit.save_report(db_path=db_path)
    lag_report = result_lag_miner.save_report(db_path=db_path)
    martingale_report = martingale_audit.save_report(db_path=db_path)
    truth_report = truth_verifier.save_report(db_path=db_path)

    strongest_rooms = [
        row for row in room_report["rooms"]
        if row["action"] == "KEEP"
        and row.get("fired_n7", 0) >= 20
        and (row.get("fired_wr7") or 0) >= 75
    ]
    strongest_rooms.sort(key=lambda r: (-(r.get("fired_wr7") or 0), -r.get("fired_n7", 0)))

    cleanup_actions = [
        row for row in room_report["rooms"]
        if row["action"] != "KEEP"
    ]
    cleanup_actions.sort(key=lambda r: (r["action"], r["handle"].lower()))

    top_early_cells = early_report["cells"][:12]
    top_omni = sorted(
        omni_report["results"],
        key=lambda r: (-r["score"], r["room"], r["color"]),
    )[:20]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "room_summary": room_report["summary"],
        "strongest_rooms": strongest_rooms[:20],
        "cleanup_actions": cleanup_actions[:80],
        "omni_summary": {
            "recent_scored": omni_report["count"],
            "verdict_counts": omni_report["verdict_counts"],
            "top": top_omni,
        },
        "early_result_summary": early_report["overall"],
        "top_early_cells": top_early_cells,
        "result_lag_summary": {
            "stream_n": lag_report["stream_n"],
            "lag5": lag_report["lag5"],
            "best_lag": lag_report["best_lag"],
        },
        "martingale_summary": {
            "overall": martingale_report["overall"],
            "top_rooms": martingale_report["by_room"][:10],
            "top_room_color": martingale_report["by_room_color"][:10],
        },
        "truth_summary": truth_report,
        "next_steps": [
            "Review cleanup_actions, then run room_cleaner.py --apply if correct.",
            "Use strongest_rooms as the first Elite Stack source whitelist.",
            "Only promote early-result cells with high oracle_safe_pct and strong WR.",
            "Use result_lag_summary to validate/deny the lag-5 repeat hypothesis before live betting it.",
            "Use martingale_summary to allow gale only where recovery is proven.",
            "Use truth_summary to keep direct Twin225 truth separate from Telegram/DB inferred truth.",
            "Wire omni_score.score_signal into signal_handler before final fire.",
            "Run Telegram live discovery only after stale/weak rooms are cleaned.",
        ],
    }


def save_audit(audit: dict, path: str = REPORT_PATH) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(audit, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    os.replace(tmp, path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Elite Stack audit")
    parser.add_argument("--db", default=DB_PATH)
    parser.add_argument("--recent", type=int, default=100)
    parser.add_argument("--report", default=REPORT_PATH)
    args = parser.parse_args()

    audit = build_audit(db_path=args.db, recent=args.recent)
    save_audit(audit, args.report)
    print(json.dumps(
        {
            "generated_at": audit["generated_at"],
            "room_summary": audit["room_summary"],
            "strongest_rooms": [
                {
                    "handle": row["handle"],
                    "tier": row["gale_tier"],
                    "fired_n7": row["fired_n7"],
                    "fired_wr7": row["fired_wr7"],
                }
                for row in audit["strongest_rooms"][:10]
            ],
            "cleanup_actions_count": len(audit["cleanup_actions"]),
            "omni_summary": audit["omni_summary"]["verdict_counts"],
            "early_result_summary": audit["early_result_summary"],
            "result_lag_summary": audit["result_lag_summary"],
            "martingale_summary": audit["martingale_summary"]["overall"],
            "truth_verdict": audit["truth_summary"]["verdict"],
        },
        indent=2,
        ensure_ascii=False,
    ))
    print(f"report={args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
