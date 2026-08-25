#!/usr/bin/env python3
"""
timing_presence_catalog.py — START AXIS the user wants.

NOT the main split: 🟢 1s 🟢 / JANELA Ns (that = Clock A = seconds to PLACE the bet).

START AXIS (PT+EN, every card ever, good or bad, even if n=1):
  WITH_TIMING  — card body carries a duration / countdown / Intervalo / Ns span
                 (31.3s, 200s, 400s, 30s, 40s, rodadas+tempo, etc.)
  NO_TIMING    — fire or result template with no such duration marker

Also separates ROLE: FIRE vs RESULT, and tags Clock A separately.

Reads Vany CSV (or any message export). Writes:
  bot/data/timing_presence_catalog.json
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DEFAULT_CSV = Path("/workspace/vany_video_telegram_chat_history.csv")
REPORT = DATA / "timing_presence_catalog.json"

# Clock A — entry urgency ("you have Ns to bet") — NOT the start axis
_CLOCK_A = re.compile(
    r"(?is)("
    r"JANELA\s*:\s*\d+\s*s|"
    r"\d{1,3}\s*s\s+para\s+apostar|"
    r"🟢\s*\d{1,3}\s*s\s*🟢|"
    r"apostar\s+agora|"
    r"Sinal\s+Retido\s*→\s*Liberado"
    r")"
)

# Duration / countdown / Intervalo presence (START AXIS) — PT+EN
_DURATION = re.compile(
    r"(?is)("
    r"⏱\s*Intervalo\s*:\s*[\d.,]+\s*s?|"
    r"\bIntervalo\s*:\s*[\d.,]+\s*s\b|"
    r"\bintervalo\b\s*[\d.,]+\s*s|"
    r"secs_to_result|"
    r"\bcountdown\b|"
    r"\b\d{1,4}(?:[.,]\d+)?\s*(?:s|sec|secs|seg|segs|segundos?|seconds?)\b|"
    r"⏱\s*\d{1,3}\s*rodada|"
    r"\d+\s*rodada\(s\)\s*·\s*\d+\s*s|"
    r"rodada\(s\)\s*·\s*\d+\s*s|"
    r"em\s+\d{1,4}\s*(?:s|sec|seg|seconds?|segundos?)\b|"
    r"\b\d{2,4}\s*\+\s*s\b|"  # 200+ s style chatter
    r"CD_FIRE_|CD_RES_"
    r")"
)

_RESULT = re.compile(
    r"(?is)("
    r"RESUMIDO\s+FORENSE|"
    r"🔔\s*[✅❌🟡]|"
    r"GANHOU\s+NO\s+G|"
    r"G0\s*WIN|G1\s*WIN|G2\s*WIN|"
    r"✅\s*WIN\s*—|"
    r"❌\s*(?:LOSS|PERDEU)|"
    r"G1\s+EXPIROU|G2\s+MISS|"
    r"Apostou\s*:|"
    r"Resultado\s*:\s*[✅❌]"
    r")"
)

_FIRE = re.compile(
    r"(?is)("
    r"ENTER\s+NOW|"
    r"GOLDEN\s+SIGNAL|"
    r"COR\s+DA\s+APOSTA|"
    r"APOSTAR\s+[🔴🔵]|"
    r"SOLO\s+ELITE|"
    r"SINAL\s+(?:GOLDEN|PLATINUM|SEQUENCE)|"
    r"BAC\s*BO\s+SIGNAL|"
    r"Camada\s*#\d|"
    r"CONFIRMED\s+ENTRY|"
    r"👉👉👉\s*[🔴🔵]"
    r")"
)

# Normalize template fingerprint (strip volatile numbers/times)
_STRIP_NUMS = re.compile(r"\d+(?:[.,]\d+)?")
_STRIP_IDS = re.compile(r"#\d+")
_STRIP_TIMES = re.compile(
    r"\d{1,2}:\d{2}(?::\d{2})?|\d{4}-\d{2}-\d{2}|[0️⃣1️⃣2️⃣3️⃣4️⃣5️⃣6️⃣7️⃣8️⃣9️⃣]+"
)


def _role(text: str) -> str:
    is_r = bool(_RESULT.search(text))
    is_f = bool(_FIRE.search(text))
    if is_r and not is_f:
        return "RESULT"
    if is_f and not is_r:
        return "FIRE"
    if is_r and is_f:
        return "MIXED"
    return "OTHER"


def _has_duration(text: str) -> bool:
    return bool(_DURATION.search(text))


def _has_clock_a(text: str) -> bool:
    return bool(_CLOCK_A.search(text))


def _extract_durations(text: str) -> list[float]:
    vals: list[float] = []
    for m in re.finditer(
        r"(?i)(?:Intervalo\s*:\s*|⏱\s*)?(\d{1,4}(?:[.,]\d+)?)\s*(?:s|sec|secs|seg|segs|segundos?|seconds?)\b",
        text,
    ):
        try:
            vals.append(float(m.group(1).replace(",", ".")))
        except Exception:
            pass
    return vals


def _fingerprint(text: str) -> str:
    t = text.strip()
    t = _STRIP_IDS.sub("#N", t)
    t = _STRIP_TIMES.sub("T", t)
    t = _STRIP_NUMS.sub("N", t)
    # keep structure lines
    lines = [ln.strip() for ln in t.splitlines() if ln.strip()][:18]
    body = "\n".join(lines)
    h = hashlib.sha1(body.encode("utf-8", errors="ignore")).hexdigest()[:12]
    head = lines[0][:60] if lines else "?"
    return f"{h}|{head}"


def _bucket_secs(v: float) -> str:
    if v < 5:
        return "0-5s"
    if v < 15:
        return "5-15s"
    if v < 30:
        return "15-30s"
    if v < 60:
        return "30-60s"
    if v < 120:
        return "60-120s"
    if v < 200:
        return "120-200s"
    if v < 400:
        return "200-400s"
    return "400s+"


def scan_csv(path: Path, limit: int = 0) -> dict[str, Any]:
    stats = Counter()
    role_timing = Counter()  # ROLE|WITH/NO
    templates: dict[str, dict[str, Any]] = {}
    duration_buckets = Counter()
    clock_a_only = 0
    daily_with = Counter()
    daily_cd_fireish = Counter()  # FIRE + duration or clock A — binge finder
    examples: dict[str, list[str]] = defaultdict(list)

    with path.open(newline="", encoding="utf-8", errors="replace") as fh:
        reader = csv.DictReader(fh)
        for i, row in enumerate(reader, 1):
            if limit and i > limit:
                break
            text = row.get("text") or ""
            if len(text) < 25:
                stats["skip_short"] += 1
                continue
            stats["scanned"] += 1
            role = _role(text)
            has_d = _has_duration(text)
            has_a = _has_clock_a(text)
            axis = "WITH_TIMING" if has_d else "NO_TIMING"
            stats[axis] += 1
            if has_a:
                stats["CLOCK_A_ENTRY"] += 1
                if not has_d:
                    clock_a_only += 1
            role_timing[f"{role}|{axis}"] += 1

            dt = (row.get("datetime") or row.get("date_display") or "")[:10]
            if has_d:
                daily_with[dt] += 1
                for v in _extract_durations(text):
                    duration_buckets[_bucket_secs(v)] += 1
            if role == "FIRE" and (has_d or has_a):
                daily_cd_fireish[dt] += 1

            fp = _fingerprint(text)
            key = f"{role}|{axis}|{fp}"
            slot = templates.get(key)
            if not slot:
                slot = {
                    "role": role,
                    "timing_axis": axis,
                    "clock_a_entry": has_a,
                    "n": 0,
                    "fingerprint": fp,
                    "sample_head": text[:280].replace("\n", " | "),
                    "duration_examples": [],
                }
                templates[key] = slot
            slot["n"] += 1
            if has_a:
                slot["clock_a_entry"] = True
            if has_d and len(slot["duration_examples"]) < 5:
                for v in _extract_durations(text)[:2]:
                    if v not in slot["duration_examples"]:
                        slot["duration_examples"].append(v)
            ex_key = f"{role}|{axis}"
            if len(examples[ex_key]) < 3:
                examples[ex_key].append(text[:400])

    # Rank templates
    ranked = sorted(templates.values(), key=lambda x: -x["n"])
    with_t = [t for t in ranked if t["timing_axis"] == "WITH_TIMING"]
    no_t = [t for t in ranked if t["timing_axis"] == "NO_TIMING"]

    top_binge = sorted(daily_cd_fireish.items(), key=lambda x: -x[1])[:25]
    top_with = sorted(daily_with.items(), key=lambda x: -x[1])[:25]

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_csv": str(path),
        "understanding": {
            "clock_a": (
                "🟢 1s 🟢 / JANELA: 1s para apostar = seconds YOU HAVE TO PLACE THE BET "
                "(entry urgency). NOT 'when the casino hit arrives'."
            ),
            "start_axis": (
                "WITH_TIMING vs NO_TIMING on EVERY fire+result template that ever fired — "
                "Intervalo 31.3s, 200s, 400s, rodadas·Ns, countdown durations — PT or EN. "
                "Good or bad, n=1 counts."
            ),
        },
        "stats": dict(stats),
        "clock_a_without_other_duration": clock_a_only,
        "role_timing": dict(role_timing),
        "duration_buckets": dict(duration_buckets),
        "template_counts": {
            "with_timing": len(with_t),
            "no_timing": len(no_t),
            "total_fingerprints": len(ranked),
        },
        "top_with_timing_templates": with_t[:80],
        "top_no_timing_templates": no_t[:80],
        "top_days_with_timing_msgs": top_with,
        "top_days_timed_fireish": top_binge,
        "examples": {k: v for k, v in examples.items()},
        "next": [
            "Use WITH_TIMING fire templates as countdown-value family (historical binge days)",
            "Use NO_TIMING fires as ENTER NOW / plain color-coming family",
            "Map each WITH_TIMING system secs→implied rounds (secs/30) = true G0 lag",
            "Re-run g0_offset_oracle per kind×floor for offset 1..6",
        ],
    }
    DATA.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


def mine_secs_as_rounds(db_path: str, round_secs: float = 30.0) -> dict[str, Any]:
    """Per signal_kind: Intervalo/secs_to_result → implied round offset distribution."""
    import sqlite3

    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT signal_kind, COALESCE(source_floor,'LIVE') floor,
               secs_to_result, outcome, COALESCE(won_at_gale,0) gale
        FROM consensus_signals
        WHERE secs_to_result IS NOT NULL AND secs_to_result >= 0
        """
    ).fetchall()
    conn.close()
    by: dict[str, list[float]] = defaultdict(list)
    for r in rows:
        key = f"{r['signal_kind']}|{r['floor']}"
        by[key].append(float(r["secs_to_result"]))

    out_rows = []
    for key, vals in sorted(by.items(), key=lambda x: -len(x[1])):
        vals_s = sorted(vals)
        n = len(vals_s)
        avg = sum(vals_s) / n
        med = vals_s[n // 2]
        implied = [max(1, int(round(v / round_secs))) for v in vals_s]
        ic = Counter(implied)
        kind, floor = key.split("|", 1)
        out_rows.append(
            {
                "signal_kind": kind,
                "floor": floor,
                "n": n,
                "secs_avg": round(avg, 1),
                "secs_median": round(med, 1),
                "secs_p90": round(vals_s[int(n * 0.9)], 1) if n else None,
                "secs_max": round(vals_s[-1], 1),
                "implied_round_mode": ic.most_common(1)[0][0] if ic else None,
                "implied_round_dist": dict(ic.most_common(8)),
                "note": (
                    "If mode≥3, labeled G0 often resolved ~3+ table rounds after fire "
                    f"(assuming ~{round_secs:.0f}s/round)."
                ),
            }
        )
    path = DATA / "g0_secs_round_offset_report.json"
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "db_path": db_path,
        "round_secs_assumed": round_secs,
        "cells": out_rows,
        "insight": (
            "Systems with high median secs_to_result are profitable-as-labeled-G0 "
            "but mechanically delayed — true hit may be round +3/+5, not next round."
        ),
    }
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default=os.environ.get("VANY_CSV", str(DEFAULT_CSV)))
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument(
        "--db",
        default=os.environ.get("BACBO_DB", "/workspace/replit_exports/db/bot/bacbo.db"),
    )
    args = ap.parse_args()
    csv_path = Path(args.csv)
    print("Scanning", csv_path)
    rep = scan_csv(csv_path, limit=args.limit)
    print(
        json.dumps(
            {
                "scanned": rep["stats"].get("scanned"),
                "WITH_TIMING": rep["stats"].get("WITH_TIMING"),
                "NO_TIMING": rep["stats"].get("NO_TIMING"),
                "CLOCK_A_ENTRY": rep["stats"].get("CLOCK_A_ENTRY"),
                "templates_with": rep["template_counts"]["with_timing"],
                "templates_no": rep["template_counts"]["no_timing"],
                "role_timing": rep["role_timing"],
                "duration_buckets": rep["duration_buckets"],
                "top_timed_fire_days": rep["top_days_timed_fireish"][:8],
            },
            indent=2,
        )
    )
    if Path(args.db).exists():
        sec = mine_secs_as_rounds(args.db)
        print("secs→rounds top:", json.dumps(sec["cells"][:8], indent=2))


if __name__ == "__main__":
    main()
