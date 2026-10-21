"""
tri_brain_score.py — Win/Loss/Tie tri-brain replay scorer.

Purpose:
    Build a practical "one brain with three heads":
      * win_score
      * loss_risk_score
      * tie_risk_score

It learns empirical feature lifts from the DB and re-scores recent or historical
signals.  This is shadow/report mode; it does not alter live firing.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any


HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(HERE, "bacbo.db")
REPORT_PATH = os.path.join(HERE, "data", "tri_brain_report.json")


FEATURE_SQL = {
    "kind": "signal_kind",
    "floor": "COALESCE(source_floor,'LIVE')",
    "color": "color",
    "hour": "CAST(strftime('%H', fired_at) AS INT)",
    "confidence": "CASE WHEN confidence_pct IS NULL THEN 'null' WHEN confidence_pct<70 THEN '<70' WHEN confidence_pct<80 THEN '70-79' WHEN confidence_pct<90 THEN '80-89' ELSE '90+' END",
    "secs": "CASE WHEN secs_to_result IS NULL THEN 'null' WHEN secs_to_result<5 THEN '<5s' WHEN secs_to_result<20 THEN '5-20s' WHEN secs_to_result<90 THEN '20-90s' ELSE '90s+' END",
    "rooms_count": "COALESCE(rooms_count,0)",
}


@dataclass
class ScoredSignal:
    id: int
    fired_at: str
    outcome: str
    signal_kind: str
    source_floor: str
    color: str
    room: str
    win_score: float
    loss_risk_score: float
    tie_risk_score: float
    verdict: str
    reasons: list[str]


def _connect(db_path: str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def _first_room_sql() -> str:
    return """
    lower(replace(
      CASE
        WHEN instr(coalesce(rooms_agreed,''), ',') > 0
        THEN substr(rooms_agreed, 1, instr(rooms_agreed, ',') - 1)
        ELSE coalesce(rooms_agreed, '')
      END, '@', ''))
    """


def _feature_value(row: sqlite3.Row, feature: str) -> str:
    if feature == "kind":
        return str(row["signal_kind"] or "")
    if feature == "floor":
        return str(row["source_floor"] or "LIVE")
    if feature == "color":
        return str(row["color"] or "")
    if feature == "hour":
        return str(row["hour"])
    if feature == "confidence":
        c = row["confidence_pct"]
        if c is None:
            return "null"
        c = int(c)
        if c < 70:
            return "<70"
        if c < 80:
            return "70-79"
        if c < 90:
            return "80-89"
        return "90+"
    if feature == "secs":
        s = row["secs_to_result"]
        if s is None:
            return "null"
        s = float(s)
        if s < 5:
            return "<5s"
        if s < 20:
            return "5-20s"
        if s < 90:
            return "20-90s"
        return "90s+"
    if feature == "rooms_count":
        return str(row["rooms_count"] or 0)
    return ""


def learn_feature_table(db_path: str = DB_PATH, days: int = 9999, min_n: int = 20) -> dict[str, dict[str, dict[str, Any]]]:
    where = "" if days >= 9999 else "AND fired_at >= datetime('now', ?)"
    params = () if days >= 9999 else (f"-{int(days)} days",)
    table: dict[str, dict[str, dict[str, Any]]] = {}
    with _connect(db_path) as conn:
        base = conn.execute(
            f"""
            SELECT COUNT(*) n,
                   1.0*SUM(outcome='win')/COUNT(*) win_rate,
                   1.0*SUM(outcome='loss')/COUNT(*) loss_rate,
                   1.0*SUM(outcome='tie')/COUNT(*) tie_rate
            FROM consensus_signals
            WHERE outcome IN ('win','loss','tie') {where}
            """,
            params,
        ).fetchone()
        base_rates = {
            "win": float(base["win_rate"] or 0.0),
            "loss": float(base["loss_rate"] or 0.0),
            "tie": float(base["tie_rate"] or 0.0),
        }
        for feature, expr in FEATURE_SQL.items():
            rows = conn.execute(
                f"""
                SELECT CAST({expr} AS TEXT) val,
                       COUNT(*) n,
                       1.0*SUM(outcome='win')/COUNT(*) win_rate,
                       1.0*SUM(outcome='loss')/COUNT(*) loss_rate,
                       1.0*SUM(outcome='tie')/COUNT(*) tie_rate
                FROM consensus_signals
                WHERE outcome IN ('win','loss','tie') {where}
                GROUP BY val
                HAVING n >= ?
                """,
                (*params, int(min_n)),
            ).fetchall()
            table[feature] = {}
            for r in rows:
                table[feature][str(r["val"])] = {
                    "n": int(r["n"] or 0),
                    "win_lift": (float(r["win_rate"] or 0.0) / base_rates["win"]) if base_rates["win"] else 1.0,
                    "loss_lift": (float(r["loss_rate"] or 0.0) / base_rates["loss"]) if base_rates["loss"] else 1.0,
                    "tie_lift": (float(r["tie_rate"] or 0.0) / base_rates["tie"]) if base_rates["tie"] else 1.0,
                    "win_pct": round(100.0 * float(r["win_rate"] or 0.0), 2),
                    "loss_pct": round(100.0 * float(r["loss_rate"] or 0.0), 2),
                    "tie_pct": round(100.0 * float(r["tie_rate"] or 0.0), 2),
                }
    return table


def _recent_signals(conn: sqlite3.Connection, days: int, limit: int) -> list[sqlite3.Row]:
    return conn.execute(
        f"""
        SELECT id, fired_at, outcome, signal_kind, COALESCE(source_floor,'LIVE') source_floor,
               color, confidence_pct, secs_to_result, COALESCE(rooms_count,0) rooms_count,
               CAST(strftime('%H', fired_at) AS INT) hour,
               {_first_room_sql()} room
        FROM consensus_signals
        WHERE outcome IN ('win','loss','tie')
          AND fired_at >= datetime('now', ?)
        ORDER BY fired_at DESC
        LIMIT ?
        """,
        (f"-{int(days)} days", int(limit)),
    ).fetchall()


def score_row(row: sqlite3.Row, feature_table: dict[str, dict[str, dict[str, Any]]]) -> ScoredSignal:
    win_score = 50.0
    loss_risk = 50.0
    tie_risk = 50.0
    reasons: list[str] = []

    for feature in FEATURE_SQL:
        val = _feature_value(row, feature)
        data = feature_table.get(feature, {}).get(val)
        if not data:
            continue
        win_delta = (data["win_lift"] - 1.0) * 28.0
        loss_delta = (data["loss_lift"] - 1.0) * 28.0
        tie_delta = (data["tie_lift"] - 1.0) * 28.0
        win_score += win_delta
        loss_risk += loss_delta
        tie_risk += tie_delta
        if abs(win_delta) >= 2.0 or abs(loss_delta) >= 2.0 or abs(tie_delta) >= 2.0:
            reasons.append(
                f"{feature}={val} win{win_delta:+.1f} loss{loss_delta:+.1f} tie{tie_delta:+.1f}"
            )

    # Clamp
    win_score = max(0.0, min(100.0, win_score))
    loss_risk = max(0.0, min(100.0, loss_risk))
    tie_risk = max(0.0, min(100.0, tie_risk))

    if tie_risk >= 68 and loss_risk < 58:
        verdict = "SHADOW_TIE"
    elif win_score >= 58 and loss_risk <= 48 and tie_risk < 65:
        verdict = "FIRE_COLOR_G0"
    elif loss_risk >= 60:
        verdict = "BLOCK_LOSS_RISK"
    elif win_score >= 54 and loss_risk < 55:
        verdict = "SHADOW_COLOR"
    else:
        verdict = "WAIT"

    return ScoredSignal(
        id=int(row["id"]),
        fired_at=row["fired_at"],
        outcome=row["outcome"],
        signal_kind=row["signal_kind"] or "",
        source_floor=row["source_floor"] or "LIVE",
        color=row["color"] or "",
        room=row["room"] or "",
        win_score=round(win_score, 2),
        loss_risk_score=round(loss_risk, 2),
        tie_risk_score=round(tie_risk, 2),
        verdict=verdict,
        reasons=reasons[:8],
    )


def build_report(db_path: str = DB_PATH, train_days: int = 9999, score_days: int = 7, limit: int = 500) -> dict[str, Any]:
    table = learn_feature_table(db_path=db_path, days=train_days)
    with _connect(db_path) as conn:
        rows = _recent_signals(conn, score_days, limit)
    scored = [score_row(row, table) for row in rows]

    verdict_counts: dict[str, int] = {}
    outcome_by_verdict: dict[str, dict[str, int]] = {}
    for s in scored:
        verdict_counts[s.verdict] = verdict_counts.get(s.verdict, 0) + 1
        outcome_by_verdict.setdefault(s.verdict, {"win": 0, "loss": 0, "tie": 0})
        outcome_by_verdict[s.verdict][s.outcome] += 1

    verdict_stats = {}
    for verdict, counts in outcome_by_verdict.items():
        n = sum(counts.values())
        verdict_stats[verdict] = {
            **counts,
            "n": n,
            "win_pct": round(100.0 * counts["win"] / max(n, 1), 2),
            "loss_pct": round(100.0 * counts["loss"] / max(n, 1), 2),
            "tie_pct": round(100.0 * counts["tie"] / max(n, 1), 2),
        }

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "train_days": train_days,
        "score_days": score_days,
        "scored_n": len(scored),
        "verdict_counts": verdict_counts,
        "verdict_stats": verdict_stats,
        "top_fire_candidates": [asdict(s) for s in scored if s.verdict == "FIRE_COLOR_G0"][:50],
        "top_tie_candidates": [asdict(s) for s in scored if s.verdict == "SHADOW_TIE"][:50],
        "blocked_loss_risk": [asdict(s) for s in scored if s.verdict == "BLOCK_LOSS_RISK"][:50],
        "feature_table": feature_table_compact(table),
    }


def feature_table_compact(table: dict[str, dict[str, dict[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for feature, values in table.items():
        ranked = []
        for val, d in values.items():
            ranked.append({"value": val, **d})
        ranked.sort(key=lambda r: (r["win_lift"], -r["loss_lift"], r["n"]), reverse=True)
        out[feature] = ranked[:20]
    return out


def save_report(db_path: str = DB_PATH, train_days: int = 9999, score_days: int = 7, limit: int = 500, path: str = REPORT_PATH) -> dict:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    report = build_report(db_path, train_days, score_days, limit)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    os.replace(tmp, path)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Tri-Brain win/loss/tie score report")
    parser.add_argument("--db", default=DB_PATH)
    parser.add_argument("--train-days", type=int, default=9999)
    parser.add_argument("--score-days", type=int, default=7)
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--report", default=REPORT_PATH)
    args = parser.parse_args()
    report = save_report(args.db, args.train_days, args.score_days, args.limit, args.report)
    print(json.dumps({
        "generated_at": report["generated_at"],
        "scored_n": report["scored_n"],
        "verdict_counts": report["verdict_counts"],
        "verdict_stats": report["verdict_stats"],
        "top_fire_candidates": report["top_fire_candidates"][:10],
        "top_tie_candidates": report["top_tie_candidates"][:10],
    }, indent=2, ensure_ascii=False))
    print(f"report={args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
