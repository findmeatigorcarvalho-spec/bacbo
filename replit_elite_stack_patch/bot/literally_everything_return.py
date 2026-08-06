#!/usr/bin/env python3
"""Literally Everything → intended return.

Every fragment must carry an intended result toward max human return.
Ambition: as much as possible per chat (north star $100k+/day/chat when
volume+WR+density allow). Not a guarantee — a direction for every piece.

Builds: bot/data/literally_everything_return.json
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
OUT = DATA / "literally_everything_return.json"
ROOTS = [HERE.parent.parent, Path("/workspace"), Path("/home/runner/workspace")]


def _boot() -> None:
    for root in ROOTS:
        if (root / "bot" / "config" / "skin_families.py").is_file():
            s = str(root)
            if s not in sys.path:
                sys.path.insert(0, s)
            return


def _load(p: Path) -> Any:
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _piece(
    fragment_id: str,
    kind: str,
    intended_result: str,
    lever: str,
    *,
    chat: str = "",
    ambition: str = "max_capture",
    status: str = "WIRED",
    meta: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    return {
        "fragment_id": fragment_id,
        "kind": kind,
        "intended_result": intended_result,
        "lever": lever,  # how this piece turns potential → real
        "chat": chat,
        "ambition": ambition,
        "status": status,  # WIRED | CAN_BECOME_REAL | GAP
        "meta": meta or {},
    }


def build() -> Dict[str, Any]:
    _boot()
    from bot.config.skin_families import SKIN_FAMILIES
    from bot.config.profit_skyscraper import distribution_plan, chat_map

    triage = _load(DATA / "museum_triage_keep_trash.json") or {}
    allow = _load(DATA / "keep_allowlist.json") or {}
    floors = _load(DATA / "luxury_live_floors.json") or {}
    brain = _load(DATA / "profit_skyscraper_brain.json") or {}

    pieces: List[Dict[str, Any]] = []

    # Chats — each must earn its keep toward max return
    pieces.append(
        _piece(
            "chat:Mr_iv4",
            "chat",
            "Densest money path — max ENTER/gale capture at min stake",
            "money_first + soft-cap spill out, never delay in",
            chat="Mr_iv4",
            ambition="$100k+/day when volume+WR allow; else max possible",
        )
    )
    pieces.append(
        _piece(
            "chat:UNIQUE_g1",
            "chat",
            "Every timed window used — human bets before 0",
            "countdown shelf + TTB release",
            chat="UNIQUE_g1",
            ambition="max timed-window capture / day",
        )
    )
    for n in range(2, 6):
        pieces.append(
            _piece(
                f"chat:UNIQUE_g{n}",
                "chat",
                "No dead shelf — overflow opportunities still pay",
                "soft-cap spill / densifier gap fill",
                chat=f"UNIQUE_g{n}",
                ambition="fill to 1/round or 1/2 rounds minimum",
                status="CAN_BECOME_REAL",
            )
        )

    # KEEP / TRASH
    keep_n = len(allow.get("keep_family_ids") or triage.get("keep") or [])
    trash_n = len(allow.get("trash_family_ids") or triage.get("trash") or [])
    pieces.append(
        _piece(
            "triage:KEEP",
            "inventory",
            f"All {keep_n} valuable templates remain wire-eligible",
            "keep_allowlist + skin_gate allow",
        )
    )
    pieces.append(
        _piece(
            "triage:TRASH",
            "inventory",
            f"All {trash_n} junk templates never steal attention",
            "TELEGRAM_TRASH_BLOCK",
        )
    )

    # Registry skins — each family an intended result
    for fam in SKIN_FAMILIES:
        role = fam.role
        if role == "FIRE":
            ir = "Human gets a clear ENTER/color chance with time to act"
            lever = "round_sync TTB + shelf route"
        elif role == "RESULT":
            ir = "Human understands win/loss/gale — round closes clean"
            lever = "result glue + interval align"
        elif role == "OPS":
            ir = "Human protected / informed — no false bet from ops alone"
            lever = "ops→money / read-only play rule"
        elif role == "ROOM_RELAY":
            ir = "Edge/info retained for AI filter — not raw bet spam"
            lever = "keep + later filter"
            status = "CAN_BECOME_REAL"
        elif role == "ONLINE":
            ir = "Human knows the path is alive"
            lever = "boot banner / pin cards"
            status = "WIRED"
        else:
            ir = "Classified so nothing valuable is invisible"
            lever = "museum + classifier"
            status = "CAN_BECOME_REAL"
        pieces.append(
            _piece(
                f"skin:{fam.family_id}",
                "skin",
                ir,
                lever,
                status=status if role in {"ROOM_RELAY", "UNKNOWN"} else "WIRED",
                meta={"role": role, "era": fam.era},
            )
        )

    # Floors / gates
    live = floors.get("live_floors") or []
    for fl in live:
        pieces.append(
            _piece(
                f"floor:{fl}",
                "floor",
                "Peak edge proposes ENTER when cells allow",
                "luxury_live_floors + edge policy",
                ambition="contribute WR×volume to chat max return",
            )
        )
    for alias, stem in (floors.get("gate_aliases") or {}).items():
        pieces.append(
            _piece(
                f"gate:{alias}",
                "gate",
                "Named peak system stays addressable — never casually deleted",
                f"alias→{stem}",
                status="CAN_BECOME_REAL",
            )
        )

    # Timing / path wires
    for fid, ir, lever in (
        (
            "wire:round_sync",
            "Long prep → release at time-to-bet; never late burn",
            "round_sync_densifier",
        ),
        (
            "wire:human_return_path",
            "Existence + clarity + help spoken; intended results tracked",
            "human_return_path",
        ),
        (
            "wire:chat_router_spill",
            "Capacity never delays a bet window",
            "chat_router soft-cap→UNIQUE_gN",
        ),
        (
            "wire:money_first",
            "Mr_iv4 remains densest money path",
            "HUB_MONEY_FIRST",
        ),
    ):
        pieces.append(_piece(fid, "wire", ir, lever))

    # Distribution plan pieces
    for key, plan in distribution_plan().items():
        pieces.append(
            _piece(
                f"dist:{key}",
                "distribution",
                f"User action: {plan.get('user')}",
                f"chat={plan.get('chat')} shelf={plan.get('shelf')}",
                chat=str(plan.get("chat") or ""),
            )
        )

    wired = sum(1 for p in pieces if p["status"] == "WIRED")
    becoming = sum(1 for p in pieces if p["status"] == "CAN_BECOME_REAL")
    gap = sum(1 for p in pieces if p["status"] == "GAP")

    return {
        "built_at": datetime.now(timezone.utc).isoformat(),
        "law": "Only when a path is real — or can become turned into real — we'll know.",
        "always_on": {
            "on_time_every_round_TRUTHFULLY": (
                "On time for every round we have. "
                "Misses we 'couldn't' ≈ nothing next to what we got — center delivery."
            ),
            "TRUE_Enlightenment_every_time": (
                "One card · one job · one color · one action. Every time. All the time."
            ),
            "Truthfully_Helpful_every_time": (
                "Min stake · max honest use · protection. Every time. All the time."
            ),
        },
        "intended_results_XXX": (
            "Proof-as-vanity does not matter. "
            "Always the actual mattered literal correct stated "
            "EFFECT/AFFECT/OUTCOME (stated·transmitted·promised·guaranteed) — "
            "subject of the matter for that pretended/stated result. "
            "Every time. All the time."
        ),
        "ambition_XXX": {
            "outcome": "get_it_all",
            "even_when_disempowered": "get_the_most_that_moment_can_yield",
            "per_chat_day_usd_north_star": 100_000,
            "mode": "literally_everything_available",
            "honesty": (
                "Direction under volume+WR+density — not a fake certificate. "
                "Floor = max honest capture of everything available in that moment."
            ),
        },
        "stats": {
            "pieces": len(pieces),
            "WIRED": wired,
            "CAN_BECOME_REAL": becoming,
            "GAP": gap,
            "keep_templates": keep_n,
            "trash_templates": trash_n,
            "registry_skins": len(SKIN_FAMILIES),
            "live_floors": len(live),
        },
        "chat_map": chat_map(),
        "pieces": pieces,
        "brain_inventory": (brain.get("inventory") or {}),
    }


def main() -> int:
    pack = build()
    DATA.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(pack, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "law": pack["law"],
                "always_on": pack["always_on"],
                "intended_results_XXX": pack["intended_results_XXX"],
                "ambition_XXX": pack["ambition_XXX"],
                "stats": pack["stats"],
                "wrote": str(OUT),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
