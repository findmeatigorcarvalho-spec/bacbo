#!/usr/bin/env python3
"""Rebuild museum_full_catalog.json in first-existence chronological order.

Axis (locked):
  1st skin that ever existed/fired → 1 example
  2nd → 2nd example
  …
  Skins built in code but never fired still appear, AFTER dated ones,
  in SKIN_FAMILIES registry (build) order.

RESULT under FIRE only when a historical pair originally had one.
"""
from __future__ import annotations

import csv
import json
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

HERE = Path(__file__).resolve().parent
ROOT = HERE
for p in (HERE.parent.parent, Path.cwd()):
    if (p / "bot" / "config" / "skin_families.py").exists():
        ROOT = p
        break
sys.path.insert(0, str(ROOT))

from bot.config.skin_families import (  # noqa: E402
    SKIN_FAMILIES,
    canonical_family_id,
    classify_telegram_skin,
    get_skin_family,
)

UTC = timezone.utc
SKIP_IDS = {
    "ROOM_RELAY",
    "UNKNOWN",
    "EMPTY",
    "CODE_FRAGMENT",
    "CARD_BODY_LINE",
}

TYPES_CANDIDATES = [
    Path("/tmp/tg_arch_final/tg_arch_catalog_20260803T234517Z/types_first_seen.csv"),
    ROOT / "bot" / "data" / "tg_arch_final_snapshot" / "types_first_seen.csv",
]
CENSUS = ROOT / "bot" / "data" / "skin_floor_census.json"
CHRONO_PAIRS = HERE / "data" / "museum_chrono_all_pairs.json"
OUT = HERE / "data" / "museum_full_catalog.json"


def parse_dt(s: str) -> Optional[datetime]:
    s = (s or "").strip()
    if not s:
        return None
    m = re.match(
        r"(\d{2})\.(\d{2})\.(\d{4})\s+(\d{2}):(\d{2}):(\d{2})(?:\s*UTC([+-]\d{2}):?(\d{2})?)?",
        s,
    )
    if m:
        dt = datetime(
            int(m.group(3)),
            int(m.group(2)),
            int(m.group(1)),
            int(m.group(4)),
            int(m.group(5)),
            int(m.group(6)),
        )
        if m.group(7):
            sign = 1 if str(m.group(7)).startswith("+") else -1
            oh = abs(int(m.group(7)))
            om = int(m.group(8) or 0)
            off = timezone(sign * timedelta(hours=oh, minutes=om))
            return dt.replace(tzinfo=off).astimezone(UTC)
        return dt.replace(tzinfo=UTC)
    m2 = re.match(r"(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2}):(\d{2})", s)
    if m2:
        return datetime(
            int(m2.group(1)),
            int(m2.group(2)),
            int(m2.group(3)),
            int(m2.group(4)),
            int(m2.group(5)),
            int(m2.group(6)),
            tzinfo=UTC,
        )
    return None


def dt_key(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S")


def _load_old_bodies() -> Dict[str, dict]:
    """Prefer committed catalog bodies so rebuilds keep full card text."""
    try:
        raw = subprocess.check_output(
            ["git", "show", "HEAD:replit_elite_stack_patch/bot/data/museum_full_catalog.json"],
            cwd=str(ROOT),
        )
        data = json.loads(raw)
        return {it["family_id"]: it for it in data.get("items") or []}
    except Exception:
        if OUT.exists():
            data = json.loads(OUT.read_text(encoding="utf-8"))
            return {it["family_id"]: it for it in data.get("items") or []}
    return {}


def build() -> dict:
    old_by = _load_old_bodies()
    census_by = {}
    if CENSUS.exists():
        census_by = {
            f["floor_id"]: f for f in json.loads(CENSUS.read_text(encoding="utf-8")).get("floors") or []
        }
    pairs: List[dict] = []
    if CHRONO_PAIRS.exists():
        pairs = json.loads(CHRONO_PAIRS.read_text(encoding="utf-8")).get("pairs") or []

    types_path = next((p for p in TYPES_CANDIDATES if p.exists()), None)
    earliest: Dict[str, dict] = {}

    def consider(
        fid: str,
        dt: Optional[datetime],
        source: str,
        first_line: str = "",
        raw_type: str = "",
        tg_count: int = 0,
        first_chat: str = "",
    ) -> None:
        if not fid or not dt or fid in SKIP_IDS:
            return
        prev = earliest.get(fid)
        if prev is None or dt < prev["dt"]:
            earliest[fid] = {
                "dt": dt,
                "existence_at": dt_key(dt),
                "source": source,
                "first_line": first_line,
                "raw_type": raw_type,
                "tg_count_type": tg_count,
                "first_chat": first_chat,
            }

    if types_path:
        for r in csv.DictReader(types_path.open(encoding="utf-8", errors="ignore")):
            role = r.get("role") or ""
            if role in ("ROOM_RELAY", "EMPTY", "MEDIA"):
                continue
            tid = r["type_id"]
            fl = r.get("first_line") or ""
            dt = parse_dt(r.get("first_date_utc") or "")
            cands: List[str] = []
            cid = canonical_family_id(tid)
            if get_skin_family(cid) or cid in old_by:
                cands.append(cid)
            if fl:
                try:
                    m = classify_telegram_skin(fl)
                    if m and m.family_id not in ("UNKNOWN", "ROOM_RELAY", "EMPTY"):
                        cands.append(m.family_id)
                except Exception:
                    pass
            for fid in dict.fromkeys(cands):
                consider(
                    fid,
                    dt,
                    "tg_types_first_seen",
                    fl,
                    tid,
                    int(r.get("count") or 0),
                    r.get("first_chat") or "",
                )

    for fid, f in census_by.items():
        for k, src in (("tg_first_seen", "census_tg"), ("db_first_fired", "census_db")):
            consider(
                fid,
                parse_dt(f.get(k) or ""),
                src,
                f.get("tg_example") or "",
                fid,
                int(f.get("tg_count") or 0),
            )

    pair_first: Dict[str, dict] = {}
    for p in pairs:
        text = p.get("fire_text") or ""
        if not text.strip():
            continue
        try:
            m = classify_telegram_skin(text)
        except Exception:
            m = None
        if not m or m.family_id in ("UNKNOWN", "ROOM_RELAY", "EMPTY"):
            continue
        fid = m.family_id
        dt = parse_dt(p.get("fire_at") or "")
        if not dt:
            continue
        prev = pair_first.get(fid)
        if prev is None or dt < prev["dt"]:
            pair_first[fid] = {
                "dt": dt,
                "fire_text": text,
                "result_text": p.get("result_text") or "",
                "result_at": p.get("result_at"),
                "gap_secs": p.get("gap_secs"),
                "fire_at": p.get("fire_at"),
            }
        if fid not in earliest:
            consider(fid, dt, "museum_chrono_pairs", text.splitlines()[0], fid)

    universe: List[str] = []
    seen = set()
    for fid in ("ONLINE_BANNER",):
        if get_skin_family(fid) or fid in earliest:
            universe.append(fid)
            seen.add(fid)
    for fam in SKIN_FAMILIES:
        if fam.family_id in SKIP_IDS or fam.family_id in seen:
            continue
        seen.add(fam.family_id)
        universe.append(fam.family_id)
    for fid in old_by:
        if fid in SKIP_IDS or fid in seen:
            continue
        seen.add(fid)
        universe.append(fid)

    items_dated: List[dict] = []
    items_never: List[dict] = []
    for fid in universe:
        fam = get_skin_family(fid)
        old_it = old_by.get(fid) or {}
        cen = census_by.get(fid) or {}
        ear = earliest.get(fid)
        pf = pair_first.get(fid)

        body = (old_it.get("body") or "").strip()
        if not body and pf:
            body = pf["fire_text"].strip()
        if not body:
            body = (
                cen.get("tg_example")
                or (fam.example_first_line if fam else "")
                or (ear or {}).get("first_line")
                or fid
            ).strip()

        follow_ups = list(old_it.get("follow_ups") or [])
        had = bool(old_it.get("had_original_result"))
        if not follow_ups and pf and (pf.get("result_text") or "").strip():
            follow_ups = [
                {
                    "family_id": "UNKNOWN",
                    "role": "RESULT",
                    "label": "original result",
                    "body": pf["result_text"],
                    "historical": True,
                    "result_at": pf.get("result_at"),
                    "gap_secs": pf.get("gap_secs"),
                    "source": "museum_chrono_all_pairs.json",
                }
            ]
            had = True

        role = (fam.role if fam else None) or old_it.get("role") or "?"
        item: Dict[str, Any] = {
            "family_id": fid,
            "role": role,
            "label": (old_it.get("label") or (fam.label if fam else fid)),
            "lane": old_it.get("lane") or (fam.default_lane if fam else None) or "-",
            "era": old_it.get("era") or (fam.era if fam else None),
            "example_first_line": old_it.get("example_first_line")
            or (fam.example_first_line if fam else (body.splitlines()[0] if body else fid)),
            "body": body,
            "tg_count": int(
                old_it.get("tg_count")
                or cen.get("tg_count")
                or (ear or {}).get("tg_count_type")
                or 0
            ),
            "historical": bool(
                ear or old_it.get("historical") or cen.get("seen_telegram") or cen.get("in_db")
            ),
            "had_original_result": had if role == "FIRE" else False,
            "follow_ups": (follow_ups if role == "FIRE" else []),
            "existence_source": (ear or {}).get("source")
            or ("code_registry" if fam else "catalog_only"),
        }
        if ear:
            item["existence_at"] = ear["existence_at"]
            item["fire_at"] = old_it.get("fire_at") or (pf or {}).get("fire_at") or ear["existence_at"]
            item["first_chat"] = ear.get("first_chat") or ""
            items_dated.append(item)
        else:
            item["existence_at"] = None
            item["never_fired"] = True
            item["historical"] = False
            items_never.append(item)

    items_dated.sort(key=lambda x: (x["existence_at"], x["family_id"]))
    reg_order = {f.family_id: i for i, f in enumerate(SKIN_FAMILIES)}
    items_never.sort(key=lambda x: (reg_order.get(x["family_id"], 10_000), x["family_id"]))

    items: List[dict] = []
    for order, it in enumerate(items_dated + items_never, start=1):
        row = dict(it)
        row["chrono_order"] = order
        items.append(row)

    return {
        "title": "UNIQUE_museum_chrono — first existence order (1 example each)",
        "chat_title": "UNIQUE_museum_chrono",
        "chat_username": "UNIQUE_museum_chrono",
        "axis": "CHRONO_FIRST_EXISTENCE",
        "rule": (
            "One example per skin, ordered by first existence (UTC). "
            "Never-fired skins follow in code-registry order. "
            "RESULT under FIRE only if that historical signal originally had one."
        ),
        "understanding": (
            "1st skin that ever existed/fired → example #1; 2nd → #2; … "
            "Even skins never fired still appear, after fired ones, in build/registry order."
        ),
        "note_scrape": (
            "Do not re-scrape Mr_iv4 for this — Mar17→Aug3 types_first_seen "
            "already supplies first-seen UTC dates."
        ),
        "types_csv": str(types_path) if types_path else None,
        "stats": {
            "total": len(items),
            "with_existence_date": len(items_dated),
            "never_fired_code_order": len(items_never),
            "fires_with_original_result": sum(1 for x in items if x.get("had_original_result")),
        },
        "items": items,
    }


def main() -> int:
    pack = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(pack, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Wrote", OUT)
    print(json.dumps(pack["stats"], indent=2))
    for it in pack["items"][:15]:
        print(
            f"{it['chrono_order']:3} {it.get('existence_at') or 'NEVER':19} "
            f"{it['family_id']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
