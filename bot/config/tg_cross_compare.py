"""Cross-compare Telegram archaeology (Mr_iv4 + UNIQUE_g1) vs skin inventory.

Reads `types_first_seen.csv` from a Telethon scrape and classifies every distinct
type with `classify_telegram_skin` so we can see product skins that landed in
chat but are still UNKNOWN / unmapped in the family registry.

Usage:
  python3 -m bot.config.tg_cross_compare \\
    --types /tmp/tg_arch_final/.../types_first_seen.csv \\
    --out bot/data/tg_cross_compare
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from bot.config.skin_families import (
    SKIN_FAMILIES,
    canonical_family_id,
    classify_telegram_skin,
    family_ids,
)


_NOISE_ROLES = {"ROOM_RELAY", "EMPTY", "MEDIA", "ONLINE"}
_NOISE_LINE = re.compile(
    r"Auto-quarantine|Quarantine ended|RELAY\s+RESTORED|SKYSCRAPER|"
    r"LUXURY\s+OUTBOX\s+ONLINE|Bot\s+Ativo|curl\s+-s",
    re.I,
)
_NOISE_TYPE = re.compile(
    r"^(OPS_AUTO_QUARANTINE|OPS_QUARANTINE_ENDED|RELAY_|UNKNOWN_CURL_|UNKNOWN_WORKSPACE_)",
    re.I,
)
_PRODUCT_HINT = re.compile(
    r"(ENTER\s+NOW|APOSTAR|SOLO\s*ELITE|GOLDEN|SEQUENCE|PLATINUM|FLASH|"
    r"Sinal\s+Retido|JANELA|GANHOU|PERDEU|FORENSE|G0\s*WIN|G1\s*EXPIROU|"
    r"G2\s*MISS|GALE|EMPATE|WIN\s*—|LOSS\s*—|RETENTATIVA|Entre\s+novamente|"
    r"PREPARE\s+O\s+G1|ULTRA\s+TIE|CD_FIRE|COUNTDOWN|SIGNAL\s*#|"
    r"CONFIRMED|MARTINGALE|VERMELHO|AZUL|Banker|Player|"
    r"SATURA|SELF-CARE|3\s+PERDAS|PREDICTION|"
    r"[🔵🔴🟨]{8,})",
    re.I,
)


def _load_types(path: Path) -> List[Dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _body_for(row: Dict[str, str]) -> str:
    # Prefer richer text when present; else first_line + note.
    parts = [
        row.get("text_head") or "",
        row.get("first_line") or "",
        row.get("note") or "",
        row.get("type_id") or "",
    ]
    return "\n".join(p for p in parts if p)


def compare_types(rows: Iterable[Dict[str, str]]) -> Dict[str, Any]:
    by_chat_first = Counter()
    by_chat_msgs = Counter()
    by_role = Counter()
    family_hits: Counter = Counter()
    unknown_product: List[Dict[str, Any]] = []
    mapped_examples: Dict[str, Dict[str, Any]] = {}
    alias_hits: Counter = Counter()

    known = set(family_ids())
    total_types = 0
    product_types = 0
    mapped_product = 0
    product_msgs_total = 0
    mapped_msgs_total = 0
    unmapped_msgs_total = 0

    for row in rows:
        total_types += 1
        role = (row.get("role") or "").upper()
        chat = row.get("first_chat") or "?"
        count = int(row.get("count") or 0)
        by_chat_first[chat] += 1
        by_chat_msgs[chat] += count
        by_role[role] += 1

        body = _body_for(row)
        fl = row.get("first_line") or ""
        tid = row.get("type_id") or ""

        # Skip pure room-relay / quarantine flood for product gap reporting
        is_noise = (
            role in _NOISE_ROLES
            or tid.startswith("RELAY_")
            or bool(_NOISE_TYPE.match(tid or ""))
            or bool(_NOISE_LINE.search(fl))
            or bool(_NOISE_LINE.search(body))
        )
        # Resolve early so UNKNOWN archaeology ids with aliases still count.
        canon = canonical_family_id(tid) if tid else tid
        looks_product = bool(
            (not is_noise)
            and (
                role in {"FIRE", "RESULT", "OPS"}
                or canon in known
                or _PRODUCT_HINT.search(fl)
                or _PRODUCT_HINT.search(body)
                or tid.startswith(("FIRE_", "RESULT_", "OPS_", "RES_", "CD_"))
            )
        )
        if not looks_product:
            continue

        product_types += 1
        product_msgs = count or 1
        product_msgs_total += product_msgs
        # Resolve: archaeology type_id alias → else text classify.
        match = classify_telegram_skin(body, signal_kind=None)
        fam = match.family_id
        if canon in known:
            if fam not in known:
                alias_hits[canon] += 1
            fam = canon
        elif fam not in known:
            fam = "UNKNOWN"

        if fam in known:
            mapped_product += 1
            mapped_msgs_total += product_msgs
            family_hits[fam] += product_msgs
            mapped_examples.setdefault(
                fam,
                {
                    "family_id": fam,
                    "tg_type_id": tid,
                    "first_line": fl[:160],
                    "first_chat": chat,
                    "first_date_utc": row.get("first_date_utc"),
                    "count": count,
                },
            )
        else:
            unmapped_msgs_total += product_msgs
            unknown_product.append(
                {
                    "tg_type_id": tid,
                    "role": role,
                    "lane": row.get("lane"),
                    "first_line": fl[:160],
                    "first_chat": chat,
                    "first_date_utc": row.get("first_date_utc"),
                    "count": count,
                    "classified_as": fam,
                }
            )

    # Families in registry never seen in this TG dump (may be CREATED_ONLY / muted)
    seen_fams = set(family_hits) | {
        e["family_id"] for e in mapped_examples.values()
    }
    never_in_tg = sorted(
        f.family_id
        for f in SKIN_FAMILIES
        if f.family_id not in seen_fams
        and (f.default_lane or "") not in {"NOISE", "SINK"}
        and f.role not in {"ROOM_RELAY", "ONLINE"}
    )

    # Sort gaps by count desc
    unknown_product.sort(key=lambda r: (-int(r.get("count") or 0), r.get("tg_type_id") or ""))

    return {
        "total_distinct_types": total_types,
        "product_looking_types": product_types,
        "mapped_product_types": mapped_product,
        "unmapped_product_types": len(unknown_product),
        "map_rate_product": round(mapped_product / product_types, 4) if product_types else 0.0,
        "product_msgs": product_msgs_total,
        "mapped_msgs": mapped_msgs_total,
        "unmapped_msgs": unmapped_msgs_total,
        "map_rate_msgs": round(mapped_msgs_total / product_msgs_total, 4)
        if product_msgs_total
        else 0.0,
        "by_first_chat_types": dict(by_chat_first),
        "by_first_chat_msg_counts": dict(by_chat_msgs),
        "by_role_type_rows": dict(by_role),
        "family_msg_hits_top": family_hits.most_common(80),
        "registry_families": len(known),
        "registry_never_seen_in_this_tg_dump": never_in_tg,
        "registry_never_seen_count": len(never_in_tg),
        "alias_rescue_hits": dict(alias_hits),
        "unmapped_product_top": unknown_product[:200],
        "mapped_family_examples": list(mapped_examples.values())[:200],
        "coverage_note": (
            "first_chat = chat where type FIRST appeared. Duplicate later posts "
            "on UNIQUE_g1 of the same type_id still count under mr_iv4 first_chat. "
            "Re-run dual-chat scan with per_chat_counts for true Gunique volume."
        ),
    }


def write_report(result: Dict[str, Any], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "tg_cross_compare.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    gaps = result.get("unmapped_product_top") or []
    never = result.get("registry_never_seen_in_this_tg_dump") or []
    lines = [
        "# Telegram ↔ Skin inventory cross-compare",
        "",
        f"- Distinct TG types: **{result['total_distinct_types']}**",
        f"- Product-looking types: **{result['product_looking_types']}**",
        f"- Mapped types: **{result['mapped_product_types']}** "
        f"({result['map_rate_product']:.1%} of types)",
        f"- Mapped messages (weighted): **{result['mapped_msgs']}** / "
        f"**{result['product_msgs']}** ({result['map_rate_msgs']:.1%})",
        f"- Unmapped product types: **{result['unmapped_product_types']}** "
        f"({result['unmapped_msgs']} msgs)",
        f"- Registry families: **{result['registry_families']}**",
        f"- Registry families never seen in this TG dump: **{result['registry_never_seen_count']}** "
        "(CREATED_ONLY / muted / never reached chat — keep, do not delete)",
        "",
        "## Chats in scrape (first-appearance attribution)",
        "",
        f"```\n{json.dumps(result['by_first_chat_msg_counts'], indent=2)}\n```",
        "",
        f"_{result['coverage_note']}_",
        "",
        "## Top unmapped product-looking TG types",
        "",
        "| count | chat | role | first_line | tg_type_id |",
        "|---|---|---|---|---|",
    ]
    for g in gaps[:80]:
        fl = (g.get("first_line") or "").replace("|", "\\|")[:80]
        lines.append(
            f"| {g.get('count')} | {g.get('first_chat')} | {g.get('role')} | "
            f"{fl} | `{g.get('tg_type_id')}` |"
        )
    lines.extend(
        [
            "",
            "## Registry families not in this TG dump (sample)",
            "",
        ]
    )
    for fam in never[:60]:
        lines.append(f"- `{fam}`")
    if len(never) > 60:
        lines.append(f"- … +{len(never) - 60} more")
    (out_dir / "TG_CROSS_COMPARE.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    with (out_dir / "unmapped_product.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "count",
                "first_chat",
                "role",
                "lane",
                "first_date_utc",
                "first_line",
                "tg_type_id",
                "classified_as",
            ],
        )
        w.writeheader()
        for g in gaps:
            w.writerow(g)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--types",
        required=True,
        help="Path to types_first_seen.csv from TG archaeology",
    )
    ap.add_argument(
        "--out",
        default="bot/data/tg_cross_compare",
        help="Output directory",
    )
    args = ap.parse_args(argv)
    rows = _load_types(Path(args.types))
    result = compare_types(rows)
    write_report(result, Path(args.out))
    print(
        f"OK types={result['total_distinct_types']} product={result['product_looking_types']} "
        f"mapped={result['mapped_product_types']} unmapped={result['unmapped_product_types']} "
        f"never_in_tg={result['registry_never_seen_count']} → {args.out}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
