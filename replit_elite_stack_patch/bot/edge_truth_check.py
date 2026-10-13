"""
edge_truth_check.py — read-only. Does any system hold an edge once you only
count signals that can be pinned to the round they named?

Opens the DB read-only, sends nothing, writes nothing to it.

The headline win rates in this repo count every graded signal, however long the
grader took to find a matching result. A Bac Bo round is ~30s, so a signal
graded 10 minutes later was matched against some later round, and a win rate
built that way measures the search, not the call.

This splits each system three ways:
  FORWARD   graded inside one round of firing (the call plausibly preceded it)
  INSTANT   graded in under FAST_SECS (the result was already known)
  STRAY     graded beyond one round (matched to a round it did not name)

If a system's FORWARD win rate collapses toward the ~49% an even-money Bac Bo
bet pays while its overall rate stays high, the edge lives in STRAY/INSTANT and
is an artifact. If FORWARD stays high on real volume, that is the first number
in this project worth acting on.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sqlite3
from datetime import datetime, timezone


HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(HERE, "bacbo.db")
REPORT_PATH = os.path.join(HERE, "data", "edge_truth_check.json")

ROUND_SECS = 35.0
FAST_SECS = 5.0
MIN_N = 30

# Bac Bo player/banker pays even money against a house edge near 2.7%.
BREAKEVEN_WR = 0.5


def _connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    return bool(
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
        ).fetchone()
    )


def _wilson(wins: int, n: int) -> tuple[float, float] | None:
    """95% CI for a proportion; small samples need it to avoid reading noise."""
    if n <= 0:
        return None
    z = 1.96
    p = wins / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (round(100 * (centre - half), 2), round(100 * (centre + half), 2))


def _bucket_case() -> str:
    return f"""
        CASE
            WHEN secs_to_result IS NULL THEN 'UNKNOWN'
            WHEN secs_to_result < {FAST_SECS} THEN 'INSTANT'
            WHEN secs_to_result <= {ROUND_SECS} THEN 'FORWARD'
            ELSE 'STRAY'
        END
    """


def ground_truth(conn: sqlite3.Connection) -> dict:
    out = {"casino_round_results": None, "signal_truth_matches": None}
    for table in out:
        if _table_exists(conn, table):
            out[table] = conn.execute(f"SELECT COUNT(*) c FROM {table}").fetchone()["c"]
    out["has_ground_truth"] = bool(out["casino_round_results"])
    return out


def by_kind(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        f"""
        SELECT signal_kind AS kind,
               {_bucket_case()} AS bucket,
               COUNT(*) AS n,
               SUM(outcome='win')  AS wins,
               SUM(outcome='loss') AS losses,
               SUM(outcome='tie')  AS ties,
               ROUND(AVG(secs_to_result), 1) AS avg_secs,
               ROUND(MIN(secs_to_result), 1) AS min_secs,
               ROUND(MAX(secs_to_result), 1) AS max_secs
        FROM consensus_signals
        WHERE outcome IN ('win','loss','tie')
        GROUP BY kind, bucket
        """
    ).fetchall()

    agg: dict[str, dict] = {}
    for r in rows:
        kind = r["kind"] or "UNKNOWN"
        entry = agg.setdefault(kind, {"signal_kind": kind, "buckets": {}, "total": 0})
        decided = int(r["n"]) - int(r["ties"] or 0)
        wins = int(r["wins"] or 0)
        entry["buckets"][r["bucket"]] = {
            "n": int(r["n"]),
            "decided": decided,
            "wins": wins,
            "losses": int(r["losses"] or 0),
            "ties": int(r["ties"] or 0),
            "wr_pct": round(100.0 * wins / decided, 2) if decided else None,
            "wr_ci95": _wilson(wins, decided) if decided >= MIN_N else None,
            "avg_secs": r["avg_secs"],
            "min_secs": r["min_secs"],
            "max_secs": r["max_secs"],
        }
        entry["total"] += int(r["n"])

    out = []
    for entry in agg.values():
        fwd = entry["buckets"].get("FORWARD") or {}
        every = [b for b in entry["buckets"].values()]
        dec_all = sum(b["decided"] for b in every)
        win_all = sum(b["wins"] for b in every)
        entry["overall_wr_pct"] = round(100.0 * win_all / dec_all, 2) if dec_all else None
        entry["forward_wr_pct"] = fwd.get("wr_pct")
        entry["forward_n"] = fwd.get("decided", 0)
        entry["verdict"] = _verdict(entry["forward_n"], fwd.get("wr_ci95"))
        out.append(entry)
    out.sort(key=lambda e: -e["total"])
    return out


def _verdict(n: int, ci: tuple[float, float] | None) -> str:
    if n < MIN_N or ci is None:
        return "INSUFFICIENT_FORWARD_SAMPLE"
    low, _high = ci
    if low > 100 * BREAKEVEN_WR:
        return "EDGE_SURVIVES_FORWARD_FILTER"
    return "NO_EDGE_AT_95PCT"


def lag_shape(conn: sqlite3.Connection) -> dict:
    row = conn.execute(
        f"""
        SELECT COUNT(*) n,
               SUM({_bucket_case()}='INSTANT') instant,
               SUM({_bucket_case()}='FORWARD') forward,
               SUM({_bucket_case()}='STRAY')   stray,
               SUM({_bucket_case()}='UNKNOWN') unknown
        FROM consensus_signals
        WHERE outcome IN ('win','loss','tie')
        """
    ).fetchone()
    n = int(row["n"] or 0)
    pct = lambda v: round(100.0 * int(v or 0) / n, 2) if n else None  # noqa: E731
    return {
        "graded_total": n,
        "instant": int(row["instant"] or 0),
        "forward": int(row["forward"] or 0),
        "stray": int(row["stray"] or 0),
        "unknown": int(row["unknown"] or 0),
        "instant_pct": pct(row["instant"]),
        "forward_pct": pct(row["forward"]),
        "stray_pct": pct(row["stray"]),
        "round_secs": ROUND_SECS,
        "fast_secs": FAST_SECS,
    }


def derived_color_check(conn: sqlite3.Connection) -> dict:
    """If 'actual' colour is derived from the win label, wins mirror the call exactly."""
    row = conn.execute(
        """
        SELECT SUM(outcome='win' AND color='blue')  AS win_blue,
               SUM(outcome='win' AND color='red')   AS win_red,
               SUM(outcome='loss' AND color='blue') AS loss_blue,
               SUM(outcome='loss' AND color='red')  AS loss_red
        FROM consensus_signals
        WHERE outcome IN ('win','loss') AND color IN ('blue','red')
        """
    ).fetchone()
    wb, wr_ = int(row["win_blue"] or 0), int(row["win_red"] or 0)
    lb, lr = int(row["loss_blue"] or 0), int(row["loss_red"] or 0)
    # Derived actual: win -> called colour, loss -> the other colour.
    blue_actual = wb + lr
    red_actual = wr_ + lb
    total = blue_actual + red_actual
    return {
        "note": (
            "Actual colour is reconstructed as call-on-win / opposite-on-loss, so this "
            "is the bot's believed round history, not an observed one."
        ),
        "blue_actual": blue_actual,
        "red_actual": red_actual,
        "blue_pct": round(100.0 * blue_actual / total, 2) if total else None,
        "calls_blue": wb + lb,
        "calls_red": wr_ + lr,
    }


def build_report(db_path: str = DB_PATH) -> dict:
    with _connect(db_path) as conn:
        if not _table_exists(conn, "consensus_signals"):
            return {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "db_path": db_path,
                "error": "consensus_signals missing — wrong DB file",
            }
        total = conn.execute("SELECT COUNT(*) c FROM consensus_signals").fetchone()["c"]
        span = conn.execute(
            "SELECT MIN(fired_at) lo, MAX(fired_at) hi FROM consensus_signals"
        ).fetchone()
        kinds = by_kind(conn)
        rep = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "db_path": db_path,
            "db_bytes": os.path.getsize(db_path) if os.path.exists(db_path) else None,
            "consensus_rows": total,
            "fired_span": {"first": span["lo"], "last": span["hi"]},
            "ground_truth": ground_truth(conn),
            "lag_shape": lag_shape(conn),
            "by_kind": kinds,
            "derived_color_check": derived_color_check(conn),
        }

    surviving = [k for k in kinds if k["verdict"] == "EDGE_SURVIVES_FORWARD_FILTER"]
    rep["conclusion"] = {
        "systems_examined": len(kinds),
        "systems_with_surviving_edge": [k["signal_kind"] for k in surviving],
        "breakeven_wr_pct": 100 * BREAKEVEN_WR,
        "summary": (
            "No system's forward-gradeable win rate is above breakeven at 95% confidence."
            if not surviving
            else "Forward-gradeable edge claimed by: "
            + ", ".join(k["signal_kind"] for k in surviving)
            + " — confirm against captured casino rounds before betting."
        ),
    }
    return rep


def render(rep: dict) -> str:
    if rep.get("error"):
        return f"[EDGE-TRUTH] ERROR {rep['error']}"
    lines = []
    add = lines.append
    gt = rep["ground_truth"]
    lag = rep["lag_shape"]

    add("========== EDGE TRUTH CHECK (read-only) ==========")
    add(f"db            : {rep['db_path']} ({(rep['db_bytes'] or 0) / 1e9:.2f} GB)")
    add(f"consensus rows: {rep['consensus_rows']:,}")
    add(f"fired span    : {rep['fired_span']['first']} -> {rep['fired_span']['last']}")
    add("")
    add("-- ground truth --")
    add(f"casino_round_results rows : {gt['casino_round_results']}")
    add(f"signal_truth_matches rows : {gt['signal_truth_matches']}")
    add(f"has independent truth     : {gt['has_ground_truth']}")
    add("")
    add(f"-- grading lag (round={lag['round_secs']}s, fast<{lag['fast_secs']}s) --")
    add(f"graded total : {lag['graded_total']:,}")
    add(f"INSTANT      : {lag['instant']:,} ({lag['instant_pct']}%)  result already known")
    add(f"FORWARD      : {lag['forward']:,} ({lag['forward_pct']}%)  pinned to its round")
    add(f"STRAY        : {lag['stray']:,} ({lag['stray_pct']}%)  matched to a later round")
    add("")
    add("-- per system: overall WR vs forward-only WR --")
    add(f"{'system':<14}{'graded':>8}{'overall':>9}{'fwd n':>8}{'fwd WR':>8}  {'fwd 95% CI':<18}verdict")
    for k in rep["by_kind"]:
        fwd = k["buckets"].get("FORWARD") or {}
        ci = fwd.get("wr_ci95")
        ci_txt = f"{ci[0]}–{ci[1]}%" if ci else "—"
        add(
            f"{k['signal_kind']:<14}{k['total']:>8,}"
            f"{(str(k['overall_wr_pct']) + '%') if k['overall_wr_pct'] is not None else '—':>9}"
            f"{k['forward_n']:>8,}"
            f"{(str(k['forward_wr_pct']) + '%') if k['forward_wr_pct'] is not None else '—':>8}"
            f"  {ci_txt:<18}{k['verdict']}"
        )
    add("")
    add(f"breakeven for an even-money bet: {rep['conclusion']['breakeven_wr_pct']}%")
    add(f"CONCLUSION: {rep['conclusion']['summary']}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only edge verification")
    parser.add_argument("--db", default=DB_PATH)
    parser.add_argument("--report", default=REPORT_PATH)
    args = parser.parse_args()

    rep = build_report(args.db)
    print(render(rep))
    try:
        os.makedirs(os.path.dirname(args.report), exist_ok=True)
        with open(args.report, "w", encoding="utf-8") as fh:
            json.dump(rep, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        print(f"\nreport: {args.report}")
    except OSError as exc:
        print(f"\nreport not written: {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
