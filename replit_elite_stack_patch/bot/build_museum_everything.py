#!/usr/bin/env python3
"""Literally-everything museum — final triage (fingerprint-first).

#1 rule: do not lose any Telegram-bound signal that could be valuable.
Anything built / taught / shadowed with intent to reach a Telegram chat
is a signal — not only color ENTER. Warnings, news, updates, heartbeats,
floors, results, relays: one example of each distinct template.

SOLO/GOLDEN/etc. are just kinds of templates among many — we do NOT
collapse distinct skins into those family buckets for this parade.

Collapse ONLY room / date / number parameter noise on the same template.
Code-only never-fired registry skins still append at the end.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Tuple

HERE = Path(__file__).resolve().parent
ROOT = HERE
for p in (HERE.parent.parent, Path.cwd()):
    if (p / "bot" / "config" / "skin_families.py").exists():
        ROOT = p
        break
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))

from bot.config.skin_families import (  # noqa: E402
    SKIN_FAMILIES,
    classify_telegram_skin,
    get_skin_family,
)
from build_museum_chrono_existence import (  # noqa: E402
    _load_old_bodies,
    dt_key,
    parse_dt,
)

OUT = HERE / "data" / "museum_full_catalog.json"
TYPES_CANDIDATES = [
    Path("/tmp/tg_arch_final/tg_arch_catalog_20260803T234517Z/types_first_seen.csv"),
    ROOT / "bot" / "data" / "tg_arch_final_snapshot" / "types_first_seen.csv",
]
SKIP_ROLES = {"EMPTY", "MEDIA"}
SKIP_IDS = {"UNKNOWN", "EMPTY", "CODE_FRAGMENT", "CARD_BODY_LINE"}


def norm_text(text: str) -> str:
    """Strip only parameter noise — keep structure/words that make a skin distinct."""
    t = (text or "").strip()
    t = re.sub(r"@\w+", "@ROOM", t)
    t = re.sub(r"\d{1,2}/\d{1,2}/\d{4}", "DATE", t)
    t = re.sub(r"\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(?::\d{2})?", "DATE", t)
    t = re.sub(r"\d{1,2}:\d{2}(?::\d{2})?", "TIME", t)
    t = re.sub(r"\d+\.?\d*", "N", t)
    t = re.sub(r"\s+", " ", t).strip().casefold()
    return t


def relay_template(type_id: str) -> str:
    m = re.match(r"^(RELAY_[A-Z0-9]+)", type_id or "")
    if not m:
        return "ROOM_RELAY"
    base = m.group(1)
    return "RELAY_OTHER" if base.startswith("RELAY_OTHER") else base


def bucket_key(role: str, type_id: str, first_line: str) -> Tuple[str, str]:
    """Fingerprint-first: each distinct template is its own signal.

    Do NOT merge into FIRE_SOLO_ELITE / GOLDEN family ids — those are labels only.
    """
    role = role or "UNKNOWN"
    tid = type_id or ""
    fl = first_line or ""

    if role == "ROOM_RELAY" or tid.startswith("RELAY_"):
        return relay_template(tid), "relay_template"

    nt = norm_text(fl or tid)
    digest = hashlib.md5(nt.encode("utf-8", errors="ignore")).hexdigest()[:12]
    return f"{role}__{digest}", "fingerprint"


def annotate_family(first_line: str, type_id: str) -> str:
    """Optional registry label — never used as the museum identity key."""
    fl = first_line or ""
    if fl.strip():
        try:
            m = classify_telegram_skin(fl)
            if m and m.family_id not in ("UNKNOWN", "EMPTY"):
                return m.family_id
        except Exception:
            pass
    return ""


def build() -> dict:
    old_by = _load_old_bodies()
    types_path = next((p for p in TYPES_CANDIDATES if p.exists()), None)
    if not types_path:
        raise SystemExit("missing types_first_seen.csv")

    buckets: Dict[str, dict] = {}
    raw_rows = 0
    reasons: Dict[str, int] = defaultdict(int)

    for r in csv.DictReader(types_path.open(encoding="utf-8", errors="ignore")):
        role = r.get("role") or ""
        if role in SKIP_ROLES:
            continue
        raw_rows += 1
        tid = r.get("type_id") or ""
        fl = r.get("first_line") or ""
        key, reason = bucket_key(role, tid, fl)
        reasons[reason] += 1
        if key in SKIP_IDS:
            continue
        dt = parse_dt(r.get("first_date_utc") or "")
        if not dt:
            continue
        cnt = int(r.get("count") or 0)
        prev = buckets.get(key)
        reg = annotate_family(fl, tid)
        if prev is None or dt < prev["dt"]:
            body = fl or tid
            # Prefer longer historical body from old catalog if same key
            old = old_by.get(key) or old_by.get(reg) or {}
            if (old.get("body") or "").strip() and len(old["body"]) > len(body or ""):
                body = old["body"]
            label = (fl.strip().splitlines()[0][:80] if fl.strip() else key)
            buckets[key] = {
                "dt": dt,
                "existence_at": dt_key(dt),
                "family_id": key,
                "registry_family": reg,
                "role": role,
                "label": label,
                "example_first_line": fl or tid,
                "body": body,
                "tg_count": cnt,
                "raw_type_first": tid,
                "first_chat": r.get("first_chat") or "",
                "existence_source": reason,
                "historical": True,
                "never_fired": False,
                "follow_ups": (old.get("follow_ups") or [])
                if role == "FIRE"
                else [],
                "had_original_result": bool(old.get("had_original_result"))
                if role == "FIRE"
                else False,
            }
        else:
            prev["tg_count"] = int(prev.get("tg_count") or 0) + cnt

    # Code / taught / shadowed skins never seen as their own TG template
    seen_reg = {b.get("registry_family") for b in buckets.values() if b.get("registry_family")}
    for fam in SKIN_FAMILIES:
        if fam.family_id in SKIP_IDS:
            continue
        if fam.family_id in seen_reg:
            continue
        # also skip if fingerprint already used exact example line
        ex = norm_text(fam.example_first_line or "")
        already = False
        for b in buckets.values():
            if norm_text(b.get("example_first_line") or "") == ex and ex:
                already = True
                break
        if already:
            continue
        old = old_by.get(fam.family_id) or {}
        buckets[fam.family_id] = {
            "dt": None,
            "existence_at": None,
            "family_id": fam.family_id,
            "registry_family": fam.family_id,
            "role": fam.role,
            "label": fam.label,
            "example_first_line": fam.example_first_line,
            "body": old.get("body") or fam.example_first_line or fam.family_id,
            "tg_count": 0,
            "raw_type_first": "",
            "first_chat": "",
            "existence_source": "code_registry_or_taught",
            "historical": False,
            "never_fired": True,
            "follow_ups": [],
            "had_original_result": False,
            "era": fam.era,
        }

    dated = [b for b in buckets.values() if b.get("existence_at")]
    never = [b for b in buckets.values() if not b.get("existence_at")]
    dated.sort(key=lambda x: (x["existence_at"], x["family_id"]))
    reg_order = {f.family_id: i for i, f in enumerate(SKIN_FAMILIES)}
    never.sort(key=lambda x: (reg_order.get(x["family_id"], 10_000), x["family_id"]))

    items: List[dict] = []
    for order, b in enumerate(dated + never, start=1):
        role = b.get("role") or "?"
        items.append(
            {
                "chrono_order": order,
                "family_id": b["family_id"],
                "registry_family": b.get("registry_family") or "",
                "role": role,
                "label": b.get("label") or b["family_id"],
                "lane": "-",
                "era": b.get("era"),
                "example_first_line": b.get("example_first_line") or b["family_id"],
                "body": b.get("body") or b.get("example_first_line") or b["family_id"],
                "tg_count": int(b.get("tg_count") or 0),
                "historical": bool(b.get("historical")),
                "never_fired": bool(b.get("never_fired")),
                "had_original_result": bool(b.get("had_original_result"))
                if role == "FIRE"
                else False,
                "follow_ups": (b.get("follow_ups") or []) if role == "FIRE" else [],
                "existence_at": b.get("existence_at"),
                "existence_source": b.get("existence_source") or "tg",
                "first_chat": b.get("first_chat") or "",
                "raw_type_first": b.get("raw_type_first") or "",
            }
        )

    by_role: Dict[str, int] = defaultdict(int)
    for it in items:
        by_role[it["role"]] += 1

    return {
        "title": "UNIQUE_museum_chrono — LITERALLY EVERY TEMPLATE (final triage)",
        "chat_title": "UNIQUE_museum_chrono",
        "chat_username": "UNIQUE_museum_chrono",
        "axis": "CHRONO_EVERYTHING_EXISTENCE",
        "goal": (
            "One example of every distinct Telegram-bound skin/template/floor "
            "since Mar 17 — warnings, news, updates, results, fires, relays — "
            "fired or not. Judge impact in the NEW result system (including "
            "inverse value when prediction≠result). Never lose a potentially "
            "valuable signal type."
        ),
        "rule": (
            "Identity = distinct template (fingerprint). SOLO/GOLDEN/etc. are "
            "labels, not buckets that merge skins. Collapse only @room/date/N. "
            "RESULT glued under FIRE only if that historical signal had one."
        ),
        "understanding": (
            "If it was built/taught/shadowed to reach Telegram, it is in this "
            "parade. Floors are singular systems that get to prove themselves. "
            "Wrong color predictions can still be valuable when result cards "
            "tell the true outcome (bet the contrary)."
        ),
        "types_csv": str(types_path),
        "stats": {
            "total": len(items),
            "with_existence_date": len(dated),
            "never_fired_code_order": len(never),
            "raw_tg_types_scanned": raw_rows,
            "bucket_reasons": dict(reasons),
            "by_role": dict(by_role),
            "fires_with_original_result": sum(
                1 for x in items if x.get("had_original_result")
            ),
        },
        "items": items,
    }


def main() -> int:
    pack = build()
    OUT.write_text(json.dumps(pack, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Wrote", OUT)
    print(json.dumps(pack["stats"], indent=2))
    print("FIRST 12:")
    for it in pack["items"][:12]:
        print(
            f"{it['chrono_order']:4} {it.get('existence_at') or 'NEVER':19} "
            f"{it['role']:10} {(it.get('label') or '')[:50]}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
