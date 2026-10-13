"""
total_census.py — one reconciled census of every card/system/floor ever built,
plus the verification status of each one's win rate.

Every other report in bot/data covers a single facet (museum templates, floor
ranks, martingale shape, timing offsets). This consolidates them and answers the
only question that decides routing: for each system that ever fired, is its win
rate verified against casino truth, or inferred from the bot's own labels?

Reads committed artifacts only, so it runs without bacbo.db present.
"""
from __future__ import annotations

import argparse
import collections
import json
import os
from datetime import datetime, timezone


HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
REPO = os.path.dirname(os.path.dirname(HERE))

JSON_PATH = os.path.join(DATA, "total_census.json")
MD_PATH = os.path.join(os.path.dirname(HERE), "TOTAL_CENSUS.md")

MIN_CELL_N = 50

# skin_floor_census.json and result_essence_atlas.json live under the repo-root
# bot/data tree; the rest were written next to this module.
ALT_DATA = os.path.join(REPO, "bot", "data")


def _load(name: str, *, alt: bool = False) -> dict | None:
    for base in ((ALT_DATA, DATA) if alt else (DATA, ALT_DATA)):
        path = os.path.join(base, name)
        if os.path.exists(path):
            with open(path, encoding="utf-8") as fh:
                return json.load(fh)
    return None


def _load_text(relpath: str) -> str | None:
    path = os.path.join(REPO, relpath)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def inventory() -> dict:
    """Count every distinct thing that was ever created, seen, or catalogued."""
    census = _load("skin_floor_census.json", alt=True) or {}
    ledger = _load("signal_ledger.json") or {}
    museum = _load("museum_full_catalog.json") or {}
    triage = _load("museum_triage_keep_trash.json") or {}
    progress = _load(os.path.join("tg_arch_final_snapshot", "progress.json"), alt=True)

    if progress is None:
        path = os.path.join(ALT_DATA, "tg_arch_final_snapshot", "progress.json")
        progress = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {}

    floors = census.get("floors") or []
    families = ledger.get("families") or []

    return {
        "telegram_scan": {
            "chats": ["Mr_iv4", "UNIQUE_g1", "UNIQUE_museum_chrono"],
            "messages_scanned": progress.get("total"),
            "oldest": progress.get("oldest_date_utc"),
            "newest": progress.get("newest_date_utc"),
            "complete_to_first_day": progress.get("coverage_complete_to_mar17"),
            "distinct_type_fingerprints": progress.get("distinct_types"),
            "by_role": progress.get("by_role") or {},
        },
        "floors": {
            "total": len(floors),
            "created_in_code": census.get("totals", {}).get("created_in_code"),
            "seen_in_telegram": census.get("totals", {}).get("seen_telegram"),
            "reached_database": census.get("totals", {}).get("in_db"),
            "created_only_never_seen": census.get("totals", {}).get("created_only_never_seen"),
            "by_band": census.get("totals", {}).get("by_band") or {},
            "by_role": census.get("totals", {}).get("by_role") or {},
        },
        "registry_families": {
            "total": len(families),
            "by_role": dict(collections.Counter(f.get("role") for f in families)),
            "eras": len({f.get("era") for f in families}),
        },
        "museum_templates": {
            "total": museum.get("stats", {}).get("total"),
            "by_role": museum.get("stats", {}).get("by_role") or {},
            "with_existence_date": museum.get("stats", {}).get("with_existence_date"),
            "never_fired": museum.get("stats", {}).get("never_fired_code_order"),
            "fires_with_original_result": museum.get("stats", {}).get("fires_with_original_result"),
            "triage_keep": triage.get("stats", {}).get("keep"),
            "triage_trash": triage.get("stats", {}).get("trash"),
        },
    }


def systems_that_fired() -> list[dict]:
    """The only systems with graded outcomes, with their claimed win rate."""
    census = _load("skin_floor_census.json", alt=True) or {}
    rows: dict[str, dict] = {}

    for floor in census.get("floors") or []:
        if not floor.get("in_db"):
            continue
        outcomes = floor.get("db_with_outcome") or 0
        if outcomes <= 0:
            continue
        # FIRE_X_ENTER and SIGNAL_KIND_X are two census views of one db kind.
        kind = None
        for part in (floor.get("notes") or "").split(";"):
            part = part.strip()
            if part.startswith("db_kind="):
                kind = part.split("=", 1)[1]
                break
        kind = kind or floor["floor_id"]
        prev = rows.get(kind)
        if prev is None or (floor.get("tg_count") or 0) > (prev["telegram_cards"] or 0):
            rows[kind] = {
                "db_kind": kind,
                "floor_id": floor["floor_id"],
                "label": floor.get("label"),
                "rank_band": floor.get("rank_band"),
                "telegram_cards": floor.get("tg_count") or 0,
                "first_fired": floor.get("db_first_fired"),
                "fired": floor.get("db_fired") or 0,
                "graded_outcomes": outcomes,
                "graded_wins": floor.get("db_wins") or 0,
            }

    out = []
    for row in rows.values():
        row["claimed_wr_pct"] = round(100.0 * row["graded_wins"] / row["graded_outcomes"], 2)
        out.append(row)
    out.sort(key=lambda r: -r["graded_outcomes"])
    return out


def verification() -> dict:
    """How the win/loss labels behind every claimed WR were actually produced."""
    truth = _load("truth_verification_report.json") or {}
    early = _load("early_result_audit.json") or {}
    mart = _load("martingale_audit.json") or {}
    offsets = _load("g0_secs_round_offset_report.json") or {}

    levels = truth.get("truth_levels") or {}
    overall = early.get("overall") or {}
    mart_overall = mart.get("overall") or {}

    # A 3-sample cell can show any median, so only rank cells with real volume.
    cells = [c for c in (offsets.get("cells") or []) if (c.get("n") or 0) >= MIN_CELL_N]
    fastest = min(cells, key=lambda c: c.get("secs_median", 9e9)) if cells else {}

    return {
        "verdict": truth.get("verdict"),
        "direct_casino_rows": levels.get("direct_casino_rows_total"),
        "signal_truth_matches": levels.get("signal_truth_matches_total"),
        "labels_inferred_from_bot_db": levels.get("inferred_from_bot_db_recent"),
        "actual_color_rule": (
            "actual_color(predicted, outcome) returns `predicted` whenever outcome=='win', "
            "so a WIN card's 'Saiu'/'TRUTH THIS ROUND' field cannot disagree with the call."
        ),
        "actual_color_definitions": [
            "bot/telegram_outbox.py:actual_color",
            "bot/fallback_result_sender.py:actual_color",
            "bot/peak_fidelity_ranker.py:actual_color",
            "bot/config/emanation_laws.py:factual_color_from_outcome",
        ],
        "resolve_lag": {
            "avg_secs": overall.get("avg_secs"),
            "min_secs": overall.get("min_secs"),
            "max_secs": overall.get("max_secs"),
            "oracle_safe_n": overall.get("oracle_safe_n"),
            "oracle_safe_pct": overall.get("oracle_safe_pct"),
            "late_risk_n": overall.get("late_risk_n"),
            "fastest_cell": {
                "signal_kind": fastest.get("signal_kind"),
                "floor": fastest.get("floor"),
                "n": fastest.get("n"),
                "secs_median": fastest.get("secs_median"),
                "min_n": MIN_CELL_N,
            },
            "note": (
                "A ~30s table round with a 0.0s minimum and a 6560s maximum resolve lag means "
                "the grader matched some fires to rounds far outside the round they named."
            ),
        },
        "martingale": {
            "g0_wr": mart_overall.get("g0_wr"),
            "final_wr": mart_overall.get("final_wr"),
            "recovery_wr": mart_overall.get("recovery_wr"),
            "losses": mart_overall.get("losses"),
            "ties": mart_overall.get("ties"),
        },
        "required_to_verify": truth.get("required_to_confirm_100pct_claim") or [],
    }


def build_report() -> dict:
    inv = inventory()
    fired = systems_that_fired()
    ver = verification()

    graded = sum(r["graded_outcomes"] for r in fired)
    wins = sum(r["graded_wins"] for r in fired)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "question": (
            "Which fire systems, out of everything ever built in 6 months, have a "
            "profitable win rate that survives independent verification?"
        ),
        "answer": (
            "None are verified. Infrastructure to verify exists (casino_round_results, "
            "signal_truth_matches) and holds zero rows, so every win rate below is the "
            "bot grading its own labels."
        ),
        "inventory": inv,
        "systems_that_fired": fired,
        "systems_that_fired_totals": {
            "distinct_db_kinds": len(fired),
            "graded_outcomes": graded,
            "graded_wins": wins,
            "claimed_wr_pct": round(100.0 * wins / graded, 2) if graded else None,
            "verified_wr_pct": None,
        },
        "verification": ver,
    }


def render_markdown(rep: dict) -> str:
    inv = rep["inventory"]
    tg = inv["telegram_scan"]
    fl = inv["floors"]
    mus = inv["museum_templates"]
    ver = rep["verification"]
    tot = rep["systems_that_fired_totals"]

    lines: list[str] = []
    add = lines.append

    add("# TOTAL CENSUS — everything ever built, and what its numbers are worth")
    add("")
    add(f"Generated {rep['generated_at']}. Reproduce with `python3 bot/total_census.py`.")
    add("")
    add("## The question this answers")
    add("")
    add(rep["question"])
    add("")
    add(f"**{rep['answer']}**")
    add("")

    add("## 1. Scale of what exists")
    add("")
    add("| Layer | Count |")
    add("| --- | --- |")
    add(f"| Telegram messages scanned ({', '.join(tg['chats'])}) | {tg['messages_scanned']:,} |")
    add(f"| Distinct card type fingerprints | {tg['distinct_type_fingerprints']:,} |")
    add(f"| Museum templates catalogued | {mus['total']} |")
    add(f"| Floors / camadas / systems | {fl['total']} |")
    add(f"| Registry families | {inv['registry_families']['total']} |")
    add(f"| Systems that ever reached the database | {fl['reached_database']} |")
    add(f"| Distinct systems with graded outcomes | {tot['distinct_db_kinds']} |")
    add("")
    add(f"Coverage runs {tg['oldest']} → {tg['newest']}, complete back to day one.")
    add("")
    add("The funnel is the headline. Of "
        f"{fl['total']} floors, {fl['created_in_code']} were written in code, "
        f"{fl['seen_in_telegram']} ever appeared in Telegram, "
        f"{fl['reached_database']} reached the database, and "
        f"{tot['distinct_db_kinds']} produced graded outcomes. "
        f"{fl['created_only_never_seen']} were built and never fired once.")
    add("")
    add("Telegram traffic by role:")
    add("")
    add("| Role | Messages |")
    add("| --- | --- |")
    for role, n in sorted((tg["by_role"] or {}).items(), key=lambda kv: -kv[1]):
        add(f"| {role} | {n:,} |")
    add("")
    add(f"Only {(tg['by_role'] or {}).get('FIRE', 0):,} of {tg['messages_scanned']:,} messages "
        f"were fire cards. The largest share is ROOM_RELAY — copies of other rooms' traffic.")
    add("")

    add("## 2. Every system that ever fired")
    add("")
    add("| System | Band | TG cards | Fired | Graded | Wins | Claimed WR | Verified WR |")
    add("| --- | --- | --- | --- | --- | --- | --- | --- |")
    for r in rep["systems_that_fired"]:
        add(f"| {r['db_kind']} | {r['rank_band']} | {r['telegram_cards']:,} | {r['fired']:,} "
            f"| {r['graded_outcomes']:,} | {r['graded_wins']:,} | {r['claimed_wr_pct']}% | — |")
    add(f"| **TOTAL** | | | | {tot['graded_outcomes']:,} | {tot['graded_wins']:,} "
        f"| **{tot['claimed_wr_pct']}%** | **none** |")
    add("")
    add("That is the complete list. Everything else in the census never produced a "
        "single graded outcome.")
    add("")

    add("## 3. Why the claimed win rates cannot be used")
    add("")
    add(f"`truth_verification_report.json` verdict: **{ver['verdict']}**")
    add("")
    add("| Truth level | Rows |")
    add("| --- | --- |")
    add(f"| Direct casino results captured | {ver['direct_casino_rows']} |")
    add(f"| Signals matched to a casino round | {ver['signal_truth_matches']} |")
    add(f"| Outcomes inferred from the bot's own DB | {ver['labels_inferred_from_bot_db']:,} |")
    add("")
    add("### The card cannot show a miss on a win")
    add("")
    add(ver["actual_color_rule"])
    add("")
    add("Defined identically in:")
    add("")
    for site in ver["actual_color_definitions"]:
        add(f"- `{site}`")
    add("")
    add("So `Apostou: 🔵 BLUE → Saiu: 🔵 BLUE` is not an observation of the dice. On any "
        "card labelled WIN the two fields are the same value printed twice. A win card "
        "showing a matching outcome is arithmetic, not evidence, and it has been that way "
        "for every win card ever rendered.")
    add("")
    lag = ver["resolve_lag"]
    add("### The grading window was unbounded")
    add("")
    add(f"A Bac Bo round takes about 30 seconds. Observed resolve lag averages "
        f"{lag['avg_secs']}s with a minimum of {lag['min_secs']}s and a maximum of "
        f"{lag['max_secs']}s. Only {lag['oracle_safe_pct']}% of signals "
        f"({lag['oracle_safe_n']:,}) resolved inside a window that pins them to the round "
        f"they named; {lag['late_risk_n']:,} are flagged late-risk.")
    add("")
    fc = lag["fastest_cell"]
    if fc.get("signal_kind"):
        add(f"Among cells with at least {fc['min_n']} samples, the lowest-lag one is "
            f"{fc['signal_kind']} on floor {fc['floor']} (n={fc['n']}) at a median of "
            f"{fc['secs_median']}s — the result landed in the DB effectively the same instant "
            f"as the call, which is the shape you get when the outcome was already known.")
        add("")
    add(lag["note"])
    add("")
    mart = ver["martingale"]
    add("### The headline rate is also a martingale rate")
    add("")
    add(f"G0 win rate {mart['g0_wr']}% rises to {mart['final_wr']}% final only by counting "
        f"gale recoveries, on {mart['losses']:,} losses and {mart['ties']:,} ties. Recovery "
        f"wins cost escalating stakes, so final WR overstates return even if the labels "
        f"were sound.")
    add("")

    add("## 4. What would make a verified answer possible")
    add("")
    for step in ver["required_to_verify"]:
        add(f"- {step}")
    add("")
    add("Until `casino_round_results` holds independently observed rounds and "
        "`signal_truth_matches` joins calls to them with the call timestamped before "
        "betting closed, no system in this repo has a measured win rate. Opening a "
        "sala de sinais per system would publish the claimed column above as if it were "
        "the verified column.")
    add("")
    add("## 5. Standing note on the underlying bet")
    add("")
    add("Bac Bo is dice. Player/Banker pays about even money against a house edge near "
        "2.7%, and rolls are independent, so no arrangement of floors, gates, coalitions "
        "or skins shifts the next roll. A genuine 77% rate on an even-money independent "
        "event is not a strong edge, it is a signal that the measurement is wrong.")
    add("")
    return "\n".join(lines)


def save_report(json_path: str = JSON_PATH, md_path: str = MD_PATH) -> dict:
    rep = build_report()
    for path, payload in (
        (json_path, json.dumps(rep, indent=2, ensure_ascii=False) + "\n"),
        (md_path, render_markdown(rep)),
    ):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(payload)
        os.replace(tmp, path)
    return rep


def main() -> int:
    parser = argparse.ArgumentParser(description="Reconcile every census source into one report")
    parser.add_argument("--json", default=JSON_PATH)
    parser.add_argument("--md", default=MD_PATH)
    parser.add_argument("--print", action="store_true")
    args = parser.parse_args()

    rep = save_report(args.json, args.md)
    if args.print:
        print(render_markdown(rep))
    else:
        tot = rep["systems_that_fired_totals"]
        print(
            "[TOTAL-CENSUS]",
            f"floors={rep['inventory']['floors']['total']}",
            f"museum={rep['inventory']['museum_templates']['total']}",
            f"fired_systems={tot['distinct_db_kinds']}",
            f"claimed_wr={tot['claimed_wr_pct']}%",
            f"verified_wr={tot['verified_wr_pct']}",
            f"verdict={rep['verification']['verdict']}",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
