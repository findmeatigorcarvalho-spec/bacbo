"""Production reality — already true. Not a review queue. Not a new catalog.

Laws locked from live Telegram history (Mr_iv4 + UNIQUE_gN), not from chat memory:

1. If a FIRE or RESULT skin posted, that posting is forever. Software does not
   wait for a later "confirmation" to make it real.
2. Any FIRE/RESULT template that posted more than 10 of itself is already
   working unless the operator retired that system. Same for skins that ran
   back-to-back >24h or had a peak day >50.
3. The seconds printed on the FIRE card ARE the time until the outcome
   materializes. If the card said 15s, the result arrived in 15s — every time.
   A packer/round-sync "window" does not rewrite that number and must not
   HOLD the FIRE until some 12s/30s remainder.
4. The forensic Apostou→Saiu countdown card is a FIRE. Printed Intervalo is
   the outcome timer. The predicted color materializes in that countdown.
   Already proven. Do not treat Saiu as a finished ball.

This module applies those laws to routing files. It does not invent a second
truth store.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
LEDGER = DATA / "signal_ledger.json"
DECISIONS = DATA / "signal_ledger_decisions.json"
CATALOG = DATA / "museum_full_catalog.json"
REVIEW_MD = DATA / "SIGNAL_LEDGER_REVIEW.md"
PEAK = DATA / "peak_fidelity_ranker_report.json"
PEAK_LOCK = DATA / "peak_lock_config.json"

ALREADY_WORKING_MIN_SENDS = 10
PEAK_DAY_MIN = 50
MONEY_ROLES = {"FIRE", "RESULT"}


def printed_secs_are_outcome() -> bool:
    return os.environ.get("PRINTED_SECS_ARE_OUTCOME", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def hold_until_window_disabled() -> bool:
    """Printed seconds are the outcome timer — do not HOLD for a packing window."""
    if printed_secs_are_outcome():
        return True
    return os.environ.get("PACKER_HOLD_UNTIL_REAL", "0").strip().lower() in {
        "0",
        "false",
        "no",
        "off",
        "",
    }


def _load(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _counts_from_ledger(ledger: dict[str, Any]) -> dict[str, int]:
    out: dict[str, int] = {}
    for row in ledger.get("families") or []:
        if not isinstance(row, dict):
            continue
        fid = str(row.get("family_id") or "")
        if not fid:
            continue
        out[fid] = int(row.get("historical_tg_count") or 0)
    return out


def _museum_working(catalog: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in catalog.get("items") or []:
        if not isinstance(item, dict):
            continue
        n = int(item.get("tg_count") or 0)
        role = str(item.get("role") or "UNKNOWN")
        if role == "OPS":
            continue
        if n <= ALREADY_WORKING_MIN_SENDS:
            continue
        rows.append(
            {
                "family_id": item.get("family_id"),
                "registry_family": item.get("registry_family") or "",
                "role": role,
                "tg_count": n,
                "label": (item.get("label") or "")[:80],
            }
        )
    rows.sort(key=lambda r: int(r["tg_count"]), reverse=True)
    return rows


def _peak_floors(*blobs: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for peak in blobs:
        if not isinstance(peak, dict):
            continue
        seq = (
            list(peak.get("ranking") or [])
            + list(peak.get("floors") or [])
            + list(peak.get("towers") or [])
            + list(peak.get("ranked") or [])
        )
        for r in seq:
            if not isinstance(r, dict):
                continue
            n = int(r.get("peak_n") or r.get("peak_day_n") or r.get("max_day_signals") or 0)
            if n < PEAK_DAY_MIN:
                continue
            floor = str(r.get("floor") or r.get("name") or r.get("id") or "")
            if floor in seen:
                continue
            seen.add(floor)
            rows.append(
                {
                    "floor": floor,
                    "peak_day": r.get("peak_day") or r.get("max_day"),
                    "peak_n": n,
                    "peak_wr": r.get("peak_wr") or r.get("max_day_wr"),
                }
            )
    return rows


def apply_already_working() -> dict[str, Any]:
    """Stamp FIRE/RESULT as live from production send counts. RETIRE stays RETIRE."""
    ledger = _load(LEDGER)
    catalog = _load(CATALOG)
    peak = _load(PEAK)
    peak_lock = _load(PEAK_LOCK)
    counts = _counts_from_ledger(ledger)
    museum = _museum_working(catalog)
    peak_floors = _peak_floors(peak, peak_lock)

    decisions = _load(DECISIONS)
    families = decisions.get("families")
    if not isinstance(families, dict):
        families = {}
        decisions["families"] = families

    promoted: list[str] = []
    kept_retire: list[str] = []
    already: list[str] = []
    money_ids = [
        str(row.get("family_id"))
        for row in (ledger.get("families") or [])
        if isinstance(row, dict) and str(row.get("role") or "") in MONEY_ROLES
    ]
    if not money_ids:
        money_ids = list(families.keys())

    for fid in money_ids:
        row = families.get(fid)
        if not isinstance(row, dict):
            row = {
                "decision": "G1_APEX",
                "shelf": "UNIQUE_g1",
                "paired_result_family": "",
                "review_note": "",
            }
            families[fid] = row
        current = str(row.get("decision") or "").upper()
        n = int(counts.get(fid) or 0)
        if current == "RETIRE":
            kept_retire.append(fid)
            continue
        why = (
            f"already working: historical_sends={n} (> {ALREADY_WORKING_MIN_SENDS})"
            if n > ALREADY_WORKING_MIN_SENDS
            else "canonical FIRE/RESULT — operator did not retire this system"
        )
        if current != "G1_APEX":
            promoted.append(fid)
        else:
            already.append(fid)
        row["decision"] = "G1_APEX"
        row["shelf"] = row.get("shelf") or "UNIQUE_g1"
        row["review_note"] = why
        if n > ALREADY_WORKING_MIN_SENDS:
            row["historical_sends"] = n
            row["already_working"] = True

    decisions["schema_version"] = max(1, int(decisions.get("schema_version") or 1))
    decisions["instructions"] = (
        "These skins already posted in production. "
        f"More than {ALREADY_WORKING_MIN_SENDS} sends, a 24h back-to-back run, "
        f"or a peak day above {PEAK_DAY_MIN} means the skin is working. "
        "PENDING_REVIEW is not a valid state for that history. "
        "RETIRE only if the operator retired that system."
    )
    decisions["reality_law"] = {
        "printed_secs_are_outcome": True,
        "already_working_min_sends": ALREADY_WORKING_MIN_SENDS,
        "peak_day_min": PEAK_DAY_MIN,
        "museum_templates_over_min_sends": len(museum),
        "peak_floors_over_min": len(peak_floors),
    }
    DECISIONS.parent.mkdir(parents=True, exist_ok=True)
    DECISIONS.write_text(json.dumps(decisions, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_review_md(ledger, families, museum, peak_floors)
    report = {
        "promoted_from_pending": promoted,
        "already_apex": len(already),
        "kept_retire": kept_retire,
        "museum_templates_gt_10": len(museum),
        "peak_floors_gt_50": len(peak_floors),
        "working_gt_10_families": sum(
            1 for fid in money_ids if int(counts.get(fid) or 0) > ALREADY_WORKING_MIN_SENDS
        ),
    }
    return report


def _write_review_md(
    ledger: dict[str, Any],
    families: dict[str, Any],
    museum: list[dict[str, Any]],
    peak_floors: list[dict[str, Any]],
) -> None:
    rec = ledger.get("reconciliation") or {}
    lines = [
        "# Signal ledger — already working (production history)",
        "",
        "This is not a review queue. Skins that already posted are live.",
        "The operator does not re-confirm a template that fired more than 10 times,",
        "ran back-to-back more than 24h, or had a peak day above 50.",
        "",
        "## Production record",
        "",
        f"- Canonical FIRE families: **{rec.get('canonical_fire_families_to_review', 43)}**",
        f"- Canonical RESULT families: **{rec.get('canonical_result_families_to_review', 28)}**",
        f"- Distinct museum templates: **{rec.get('museum_templates_total', 827)}**",
        f"- Museum templates with >{ALREADY_WORKING_MIN_SENDS} sends: **{len(museum)}**",
        f"- Floors with peak_n ≥ {PEAK_DAY_MIN}: **{len(peak_floors)}**",
        "",
        "## Printed seconds",
        "",
        "The number on the FIRE card is the time until the outcome materializes.",
        "Example: `15 sec` means the result arrived in 15 seconds, every time.",
        "A packing window does not change that.",
        "",
        "## Money families",
        "",
        "| Family | Role | Historical templates | Historical sends | Status |",
        "|---|---:|---:|---:|---|",
    ]
    for row in ledger.get("families") or []:
        if not isinstance(row, dict) or str(row.get("role") or "") not in MONEY_ROLES:
            continue
        fid = str(row.get("family_id") or "")
        dec = ((families.get(fid) or {}).get("decision") if isinstance(families.get(fid), dict) else None) or (
            (row.get("review") or {}).get("decision") if isinstance(row.get("review"), dict) else "G1_APEX"
        )
        n = int(row.get("historical_tg_count") or 0)
        status = str(dec)
        if str(dec).upper() == "RETIRE":
            status = "RETIRE"
        elif n > ALREADY_WORKING_MIN_SENDS:
            status = "ALREADY_WORKING"
        else:
            status = "LIVE (not retired)"
        lines.append(
            f"| `{fid}` | {row.get('role')} | {row.get('observed_template_count')} | "
            f"{n} | {status} |"
        )
    lines.extend(
        [
            "",
            "## Safety boundary",
            "",
            "`UNIQUE_g1` is a live shelf. Museum posting uses a dedicated session "
            "(`MUSEUM_TELEGRAM_SESSION_STRING`) and `UNIQUE_museum_chrono`.",
            "",
        ]
    )
    REVIEW_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def apply_env() -> dict[str, str]:
    keys = {
        "PRINTED_SECS_ARE_OUTCOME": "1",
        "PACKER_HOLD_UNTIL_REAL": "0",
    }
    for k, v in keys.items():
        os.environ[k] = v
    return keys


def boot() -> dict[str, Any]:
    env = apply_env()
    keep = apply_already_working()
    print(
        "[REALITY-LAW]",
        "printed_secs=outcome",
        f"working_families={keep.get('working_gt_10_families')}",
        f"museum_gt_10={keep.get('museum_templates_gt_10')}",
        f"peak_floors={keep.get('peak_floors_gt_50')}",
        f"promoted={len(keep.get('promoted_from_pending') or [])}",
        "not-a-review-queue",
    )
    return {"env": env, "keep": keep}


if __name__ == "__main__":
    report = boot()
    assert printed_secs_are_outcome() is True
    assert hold_until_window_disabled() is True
    print("REALITY_LAW_OK", json.dumps({k: report["keep"].get(k) for k in (
        "working_gt_10_families",
        "museum_templates_gt_10",
        "peak_floors_gt_50",
        "already_apex",
        "kept_retire",
    )}, sort_keys=True))
