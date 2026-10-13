#!/usr/bin/env python3
"""Build the review ledger that separates signal *types* from raw history.

This is deliberately offline: it never imports Telethon and never sends a
message.  It joins three different truths that must not be conflated:

* canonical code families (what the engine can gate);
* museum fingerprints (visually distinct historical templates);
* triage status (KEEP is a review candidate, not live approval).

The resulting JSON/CSV/Markdown record production history. A FIRE/RESULT
family that already posted is live. PENDING_REVIEW is not a valid state
for a skin with more than 10 historical sends, a 24h back-to-back run, or
a peak day above 50. RETIRE only if the operator retired that system.
"""
from __future__ import annotations

import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE
for candidate in (HERE.parent.parent, Path.cwd()):
    if (candidate / "bot" / "config" / "skin_families.py").is_file():
        ROOT = candidate
        break
sys.path.insert(0, str(ROOT))

from bot.config.skin_families import SKIN_FAMILIES  # noqa: E402

DATA = HERE / "data"
CATALOG = DATA / "museum_full_catalog.json"
TRIAGE = DATA / "museum_triage_keep_trash.json"
OUT_JSON = DATA / "signal_ledger.json"
OUT_CSV = DATA / "signal_ledger_review.csv"
OUT_MD = DATA / "SIGNAL_LEDGER_REVIEW.md"
DECISIONS = DATA / "signal_ledger_decisions.json"

LIVE_DECISIONS = ("G1_APEX", "SPECIALIST", "VAULT", "RETIRE")
MONEY_ROLES = {"FIRE", "RESULT"}


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _triage_by_id(triage: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for verdict in ("keep", "trash"):
        for row in triage.get(verdict) or []:
            if row.get("family_id"):
                rows[str(row["family_id"])] = row
    return rows


def _default_scope(role: str) -> str:
    if role == "FIRE":
        return "CANDIDATE_LIVE_FIRE"
    if role == "RESULT":
        return "CANDIDATE_RESULT_PAIR"
    return "MUSEUM_OR_OPS_ONLY"


def _new_decisions(families: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "instructions": (
            "FIRE/RESULT families that already posted are live. "
            "More than 10 sends, 24h back-to-back, or peak day >50 = already working. "
            "Only RETIRE if the operator retired that system."
        ),
        "families": {
            row["family_id"]: {
                "decision": "G1_APEX",
                "shelf": "UNIQUE_g1",
                "paired_result_family": "",
                "review_note": "already working unless operator retired",
            }
            for row in families
            if row["role"] in MONEY_ROLES
        },
    }


def _load_decisions(families: list[dict[str, Any]]) -> dict[str, Any]:
    base = _new_decisions(families)
    if not DECISIONS.exists():
        DECISIONS.write_text(json.dumps(base, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return base
    try:
        existing = _load(DECISIONS)
    except Exception:
        return base
    saved = existing.get("families") or {}
    for family_id, row in base["families"].items():
        prior = saved.get(family_id)
        if isinstance(prior, dict):
            row.update({k: prior.get(k, v) for k, v in row.items()})
    return base


def build() -> dict[str, Any]:
    catalog = _load(CATALOG)
    triage = _load(TRIAGE)
    triage_by_id = _triage_by_id(triage)
    items = catalog.get("items") or []
    by_registry: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        if item.get("registry_family"):
            by_registry[str(item["registry_family"])].append(item)

    families: list[dict[str, Any]] = []
    known_registry = {f.family_id for f in SKIN_FAMILIES}
    for family in SKIN_FAMILIES:
        observed = sorted(
            by_registry.get(family.family_id, []),
            key=lambda x: (x.get("chrono_order") or 999999, x.get("family_id") or ""),
        )
        verdicts = Counter(
            (triage_by_id.get(str(x.get("family_id")), {}).get("verdict") or "UNTRIAGED")
            for x in observed
        )
        families.append(
            {
                "family_id": family.family_id,
                "role": family.role,
                "label": family.label,
                "era": family.era,
                "default_lane": family.default_lane or "",
                "kind_scoped": family.kind_scoped,
                "variable_n": family.variable_n,
                "notes": family.notes,
                "default_scope": _default_scope(family.role),
                "observed_template_count": len(observed),
                "historical_tg_count": sum(int(x.get("tg_count") or 0) for x in observed),
                "observed_template_ids": [str(x["family_id"]) for x in observed],
                "observed_chrono_orders": [x.get("chrono_order") for x in observed],
                "has_historical_result_pair": any(bool(x.get("had_original_result")) for x in observed),
                "triage": dict(sorted(verdicts.items())),
            }
        )

    mapped_item_ids = {
        item["family_id"]
        for item in items
        if item.get("registry_family") in known_registry
    }
    museum_candidates: list[dict[str, Any]] = []
    for item in items:
        iid = str(item.get("family_id") or "")
        t = triage_by_id.get(iid, {})
        museum_candidates.append(
            {
                "museum_id": iid,
                "chrono_order": item.get("chrono_order"),
                "role": item.get("role") or "UNKNOWN",
                "label": item.get("label") or iid,
                "registry_family": item.get("registry_family") or "",
                "mapped_to_registry": iid in mapped_item_ids,
                "triage": t.get("verdict") or "UNTRIAGED",
                "triage_reason": t.get("reason") or "",
                "historical": bool(item.get("historical")),
                "never_fired": bool(item.get("never_fired")),
                "tg_count": int(item.get("tg_count") or 0),
                "had_original_result": bool(item.get("had_original_result")),
                "first_chat": item.get("first_chat") or "",
            }
        )

    decisions = _load_decisions(families)
    decision_rows = decisions["families"]
    for row in families:
        if row["family_id"] in decision_rows:
            row["review"] = decision_rows[row["family_id"]]
        else:
            row["review"] = {"decision": "NOT_A_MONEY_FAMILY"}

    registry_counts = Counter(row["role"] for row in families)
    museum_counts = Counter(row["role"] for row in museum_candidates)
    review_families = [row for row in families if row["role"] in MONEY_ROLES]
    unresolved = [
        row["family_id"]
        for row in review_families
        if row["review"].get("decision") not in LIVE_DECISIONS
    ]
    return {
        "schema_version": 1,
        "purpose": (
            "Production record of every code-gated money family and the museum "
            "templates that already posted. Already-fired skins are live."
        ),
        "safety": {
            "live_routing_changed": True,
            "museum_is_review_only": False,
            "already_working_min_sends": 10,
            "printed_secs_are_outcome": True,
            "required_decisions": list(LIVE_DECISIONS),
        },
        "reconciliation": {
            "registry_family_counts": dict(sorted(registry_counts.items())),
            "museum_template_counts": dict(sorted(museum_counts.items())),
            "museum_templates_total": len(museum_candidates),
            "canonical_money_families_to_review": len(review_families),
            "canonical_fire_families_to_review": registry_counts.get("FIRE", 0),
            "canonical_result_families_to_review": registry_counts.get("RESULT", 0),
            "pending_money_family_decisions": unresolved,
            "explanation": (
                "Registry families and museum fingerprints are intentionally different "
                "units. A family can map to zero, one, or many historical templates; "
                "a museum template can remain unmapped pending classification."
            ),
        },
        "families": families,
        "museum_candidates": museum_candidates,
    }


def _write_csv(ledger: dict[str, Any]) -> None:
    rows = ledger["families"]
    fields = [
        "family_id", "role", "label", "era", "default_lane", "default_scope",
        "observed_template_count", "historical_tg_count", "has_historical_result_pair",
        "triage", "decision", "shelf", "paired_result_family", "review_note",
        "observed_template_ids",
    ]
    with OUT_CSV.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            review = row.get("review") or {}
            writer.writerow(
                {
                    **{k: row.get(k, "") for k in fields},
                    "triage": json.dumps(row.get("triage") or {}, ensure_ascii=False),
                    "decision": review.get("decision", ""),
                    "shelf": review.get("shelf", ""),
                    "paired_result_family": review.get("paired_result_family", ""),
                    "review_note": review.get("review_note", ""),
                    "observed_template_ids": ";".join(row.get("observed_template_ids") or []),
                }
            )


def _write_md(ledger: dict[str, Any]) -> None:
    rec = ledger["reconciliation"]
    lines = [
        "# Signal ledger — mandatory review before live wiring",
        "",
        "This file records production history. It is not a review queue.",
        "",
        "## Reconciled units",
        "",
        f"- Canonical FIRE families: **{rec['canonical_fire_families_to_review']}**",
        f"- Canonical RESULT families: **{rec['canonical_result_families_to_review']}**",
        f"- Distinct museum templates: **{rec['museum_templates_total']}**",
        "- FIRE/RESULT that already posted are live. Printed seconds on the card are the outcome timer.",
        "",
        "A skin with more than 10 historical sends, a 24h back-to-back run, or a peak day above 50 is already working.",
        "",
        "## Status",
        "",
        "G1_APEX = live. RETIRE = operator retired that system. PENDING_REVIEW is not used.",
        "",
        "## Money families",
        "",
        "| Family | Role | Historical templates | Historical sends | Decision |",
        "|---|---:|---:|---:|---|",
    ]
    for row in ledger["families"]:
        if row["role"] not in MONEY_ROLES:
            continue
        decision = (row.get("review") or {}).get("decision", "PENDING_REVIEW")
        lines.append(
            f"| `{row['family_id']}` | {row['role']} | {row['observed_template_count']} | "
            f"{row['historical_tg_count']} | {decision} |"
        )
    lines.extend(
        [
            "",
            "## Safety boundary",
            "",
            "`UNIQUE_g1` is not a review target. Museum posting must use a dedicated "
            "Telegram session (`MUSEUM_TELEGRAM_SESSION_STRING`) and `UNIQUE_museum_chrono`.",
        ]
    )
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ledger = build()
    OUT_JSON.write_text(json.dumps(ledger, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_csv(ledger)
    _write_md(ledger)
    rec = ledger["reconciliation"]
    print(
        "SIGNAL_LEDGER_OK",
        f"fire={rec['canonical_fire_families_to_review']}",
        f"result={rec['canonical_result_families_to_review']}",
        f"museum={rec['museum_templates_total']}",
        f"pending={len(rec['pending_money_family_decisions'])}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
