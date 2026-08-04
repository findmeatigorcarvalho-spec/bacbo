#!/usr/bin/env python3
"""Literally-everything museum catalog — final triage inventory.

User goal (locked):
  Evaluate every signal type / skin / template / family ever built since
  Mar 17 — FIRE, RESULT, OPS, ONLINE, news/update, heartbeats — fired or
  not — one example each — so trash vs profit / noise vs value can be judged.
  This is the last stage of the project.

Raw archaeology ≈ 39k type_ids (room/date/N variants). We keep every
*distinct template* (normalized fingerprint), not every parameter variant.
Code-only never-fired registry skins still append.

Output: data/museum_full_catalog.json
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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
    canonical_family_id,
    classify_telegram_skin,
    get_skin_family,
)
from build_museum_chrono_existence import (  # noqa: E402
    MENU_ORDER,
    ONLINE_MENU_LINES,
    ONLINE_MENU_SKINS,
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
    if base.startswith("RELAY_OTHER"):
        return "RELAY_OTHER"
    return base


def bucket_key(role: str, type_id: str, first_line: str) -> Tuple[str, str]:
    """Stable template key + human id hint."""
    role = role or "UNKNOWN"
    tid = type_id or ""
    fl = first_line or ""

    # Prefer registry family when classifier/canonical knows it
    if fl.strip():
        try:
            m = classify_telegram_skin(fl)
            if m and m.family_id not in ("UNKNOWN", "EMPTY", "ROOM_RELAY"):
                return m.family_id, "classify"
        except Exception:
            pass
    cid = canonical_family_id(tid)
    if get_skin_family(cid) and cid not in ("ROOM_RELAY", "UNKNOWN", "EMPTY"):
        return cid, "canonical"

    if role == "ROOM_RELAY" or tid.startswith("RELAY_"):
        return relay_template(tid), "relay_template"

    # Distinct message template (rooms/dates/numbers normalized).
    # Key by role+digest only — do NOT include raw type_id (that re-explodes variants).
    nt = norm_text(fl or tid)
    digest = hashlib.md5(nt.encode("utf-8", errors="ignore")).hexdigest()[:12]
    return f"{role}__{digest}", "fingerprint"


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
        fam = get_skin_family(key)
        if prev is None or dt < prev["dt"]:
            body = fl or tid
            old = old_by.get(key) or {}
            if (old.get("body") or "").strip() and len(old["body"]) > len(body):
                body = old["body"]
            buckets[key] = {
                "dt": dt,
                "existence_at": dt_key(dt),
                "family_id": key,
                "role": fam.role if fam else role,
                "label": (fam.label if fam else None) or key,
                "example_first_line": fl or (fam.example_first_line if fam else tid),
                "body": body,
                "tg_count": cnt,
                "raw_type_first": tid,
                "first_chat": r.get("first_chat") or "",
                "existence_source": reason,
                "historical": True,
                "never_fired": False,
                "follow_ups": old.get("follow_ups") or [],
                "had_original_result": bool(old.get("had_original_result")),
                "norm": norm_text(fl or tid),
            }
        else:
            prev["tg_count"] = int(prev.get("tg_count") or 0) + cnt

    # ONLINE menu = skins already existed at first ONLINE
    online = buckets.get("ONLINE_BANNER")
    if online:
        for fid in ONLINE_MENU_SKINS:
            fam = get_skin_family(fid)
            line = ONLINE_MENU_LINES.get(fid, fid)
            prev = buckets.get(fid)
            old = old_by.get(fid) or {}
            body = (old.get("body") or "").strip()
            if not body:
                body = (
                    "🟢 BacBo Royal UserBot ONLINE 🟢\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    "Sinais por score de probabilidade:\n"
                    f"{line}\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    "_Named in first ONLINE — skin already existed_"
                )
            if prev is None or online["dt"] <= prev["dt"]:
                buckets[fid] = {
                    "dt": online["dt"],
                    "existence_at": online["existence_at"],
                    "family_id": fid,
                    "role": fam.role if fam else "FIRE",
                    "label": fam.label if fam else fid,
                    "example_first_line": (fam.example_first_line if fam else line),
                    "body": body,
                    "tg_count": int((prev or {}).get("tg_count") or 0),
                    "raw_type_first": "ONLINE_BANNER",
                    "first_chat": online.get("first_chat") or "",
                    "existence_source": "online_banner_menu",
                    "historical": True,
                    "never_fired": False,
                    "follow_ups": old.get("follow_ups") or [],
                    "had_original_result": bool(old.get("had_original_result")),
                }

    # Registry skins never seen as their own template
    for fam in SKIN_FAMILIES:
        if fam.family_id in SKIP_IDS or fam.family_id in buckets:
            continue
        old = old_by.get(fam.family_id) or {}
        buckets[fam.family_id] = {
            "dt": None,
            "existence_at": None,
            "family_id": fam.family_id,
            "role": fam.role,
            "label": fam.label,
            "example_first_line": fam.example_first_line,
            "body": old.get("body") or fam.example_first_line or fam.family_id,
            "tg_count": 0,
            "raw_type_first": "",
            "first_chat": "",
            "existence_source": "code_registry",
            "historical": False,
            "never_fired": True,
            "follow_ups": [],
            "had_original_result": False,
            "era": fam.era,
        }

    dated = [b for b in buckets.values() if b.get("existence_at")]
    never = [b for b in buckets.values() if not b.get("existence_at")]

    def sort_dated(x: dict) -> tuple:
        fid = x["family_id"]
        return (
            x["existence_at"],
            0 if fid == "ONLINE_BANNER" else 1,
            MENU_ORDER.get(fid, 1000),
            fid,
        )

    dated.sort(key=sort_dated)
    reg_order = {f.family_id: i for i, f in enumerate(SKIN_FAMILIES)}
    never.sort(key=lambda x: (reg_order.get(x["family_id"], 10_000), x["family_id"]))

    items: List[dict] = []
    for order, b in enumerate(dated + never, start=1):
        fam = get_skin_family(b["family_id"])
        role = b.get("role") or (fam.role if fam else "?")
        label = b.get("label") or (fam.label if fam else None)
        if not label or label == b["family_id"]:
            fl0 = (b.get("example_first_line") or "").strip().splitlines()[0][:80]
            label = fl0 or b["family_id"]
        items.append(
            {
                "chrono_order": order,
                "family_id": b["family_id"],
                "role": role,
                "label": label,
                "lane": (fam.default_lane if fam else None) or "-",
                "era": b.get("era") or (fam.era if fam else None),
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
        "title": "UNIQUE_museum_chrono — LITERALLY EVERYTHING (final triage)",
        "chat_title": "UNIQUE_museum_chrono",
        "chat_username": "UNIQUE_museum_chrono",
        "axis": "CHRONO_EVERYTHING_EXISTENCE",
        "goal": (
            "Last-stage inventory: one example of every distinct signal "
            "type/skin/template/family since Mar 17 — including news/update — "
            "fired or not — to judge impact, trash vs profit, noise vs value."
        ),
        "rule": (
            "Distinct templates kept; room/date/number variants collapse. "
            "RESULT under FIRE only if that historical signal originally had one."
        ),
        "understanding": (
            "Raw TG type_ids ≈ 39k. Parade = distinct templates + code-only skins. "
            "ONLINE #1; menu-named skins share that existence timestamp."
        ),
        "online_menu_skins": list(ONLINE_MENU_SKINS),
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
    print("FIRST 15:")
    for it in pack["items"][:15]:
        print(
            f"{it['chrono_order']:4} {it.get('existence_at') or 'NEVER':19} "
            f"{it['role']:10} {it['family_id'][:50]}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
