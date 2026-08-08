"""KEEP vs TRASH allowlist for live Telegram sends.

Source: museum triage (`museum_triage_keep_trash.json`) + registry families.
Rules (user-locked):
  KEEP  = edge OR ops OR result/timing/room indication — any angle.
  TRASH = no edge AND no value (UI crumbs, shell pastes, agent meta).

Env:
  TELEGRAM_TRASH_BLOCK=1   (default on) — block known TRASH fingerprints
  TELEGRAM_KEEP_ALLOWLIST_PATH — override JSON path
"""
from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional, Set, Tuple


def _candidates() -> Tuple[Path, ...]:
    env = (os.environ.get("TELEGRAM_KEEP_ALLOWLIST_PATH") or "").strip()
    here = Path(__file__).resolve()
    roots = [
        here.parents[2],  # /workspace
        Path("/home/runner/workspace"),
        Path("/workspace"),
    ]
    out = []
    if env:
        out.append(Path(env))
    for root in roots:
        out.append(root / "replit_elite_stack_patch" / "bot" / "data" / "keep_allowlist.json")
        out.append(root / "bot" / "data" / "keep_allowlist.json")
        out.append(
            root
            / "replit_elite_stack_patch"
            / "bot"
            / "data"
            / "museum_triage_keep_trash.json"
        )
    return tuple(out)


@lru_cache(maxsize=4)
def _load_pack(path_str: str = "") -> Dict[str, Any]:
    paths = [Path(path_str)] if path_str else list(_candidates())
    for p in paths:
        if not p or not p.is_file():
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        # Normalized allowlist shape
        if "trash_family_ids" in data or "keep_family_ids" in data:
            data["_source_path"] = str(p)
            return data
        # Raw triage shape → normalize
        trash_ids = {
            str(r.get("family_id"))
            for r in (data.get("trash") or [])
            if r.get("family_id")
        }
        keep_ids = {
            str(r.get("family_id"))
            for r in (data.get("keep") or [])
            if r.get("family_id")
        }
        trash_reg = {
            str(r.get("registry_family"))
            for r in (data.get("trash") or [])
            if r.get("registry_family")
        }
        keep_reg = {
            str(r.get("registry_family"))
            for r in (data.get("keep") or [])
            if r.get("registry_family")
        }
        return {
            "trash_family_ids": sorted(trash_ids),
            "keep_family_ids": sorted(keep_ids),
            "trash_registry_families": sorted(trash_reg),
            "keep_registry_families": sorted(keep_reg),
            "stats": data.get("stats") or {},
            "_source_path": str(p),
        }
    return {
        "trash_family_ids": [],
        "keep_family_ids": [],
        "trash_registry_families": [],
        "keep_registry_families": [],
        "stats": {},
        "_source_path": "",
    }


def trash_block_enabled() -> bool:
    return os.environ.get("TELEGRAM_TRASH_BLOCK", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def reload() -> None:
    _load_pack.cache_clear()


def pack() -> Dict[str, Any]:
    return _load_pack()


def _sets() -> Tuple[Set[str], Set[str], Set[str], Set[str]]:
    p = pack()
    return (
        set(p.get("trash_family_ids") or []),
        set(p.get("keep_family_ids") or []),
        set(p.get("trash_registry_families") or []),
        set(p.get("keep_registry_families") or []),
    )


def is_trash_family(
    family_id: Optional[str] = None,
    *,
    registry_family: Optional[str] = None,
) -> bool:
    """True when fingerprint/registry is explicitly on the TRASH list."""
    trash_ids, _keep_ids, trash_reg, _keep_reg = _sets()
    fid = (family_id or "").strip()
    reg = (registry_family or "").strip()
    if fid and fid in trash_ids:
        return True
    if reg and reg in trash_reg:
        return True
    return False


def is_keep_family(
    family_id: Optional[str] = None,
    *,
    registry_family: Optional[str] = None,
) -> bool:
    trash_ids, keep_ids, trash_reg, keep_reg = _sets()
    fid = (family_id or "").strip()
    reg = (registry_family or "").strip()
    if fid and fid in trash_ids:
        return False
    if reg and reg in trash_reg:
        return False
    if fid and fid in keep_ids:
        return True
    if reg and reg in keep_reg:
        return True
    # Unknown to triage → fail-open KEEP (bias live product)
    return True


def trash_text_needles() -> Set[str]:
    """Distinct first-line needles from TRASH rows (for live text match)."""
    p = pack()
    needles = set(p.get("trash_text_needles") or [])
    # Also derive from triage file if present in pack via family dump
    return {n for n in needles if n and len(n) >= 3}


# Live study/shadow spam — never wire to UNIQUE_g1 (not a bettable ENTER).
_HARD_TRASH_TEXT = (
    "G2 ESTUDO",
    "G1 ESTUDO",
    "G3 ESTUDO",
    "G0 ESTUDO",
    "ESTUDO |",
    "ESTUDO :",
    "🔷 G2 ESTUDO",
    "🔷 G1 ESTUDO",
)


def should_block_as_trash(
    family_id: Optional[str] = None,
    *,
    registry_family: Optional[str] = None,
    text: Optional[str] = None,
) -> Tuple[bool, str]:
    if not trash_block_enabled():
        return False, "trash_block_off"
    if is_trash_family(family_id, registry_family=registry_family):
        return True, f"trash_blocked:{family_id or registry_family or '?'}"
    body = (text or "").strip()
    if body:
        # Hard block engine study spam (duplicate NEUTRO/PROMISSORA floods)
        upper = body.upper()
        for needle in _HARD_TRASH_TEXT:
            if needle.upper() in upper:
                return True, f"trash_estudo:{needle}"
        first_line = body.splitlines()[0].upper() if body else ""
        if "ESTUDO" in first_line:
            return True, "trash_estudo:first_line"
        first = body.splitlines()[0].strip()[:120]
        for needle in trash_text_needles():
            if not needle:
                continue
            # Short needles (UI crumbs) must match the whole first line.
            if len(needle) < 12:
                if first.casefold() == needle.casefold():
                    return True, f"trash_text:{needle[:40]}"
            elif needle in first:
                return True, f"trash_text:{needle[:40]}"
    return False, "allow"
