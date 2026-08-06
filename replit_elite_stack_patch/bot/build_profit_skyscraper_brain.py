#!/usr/bin/env python3
"""Build the Profit Skyscraper brain — full-system map + KEEP allowlist + playbooks.

Unifies:
  - museum_full_catalog.json (827 templates)
  - museum_triage_keep_trash.json (KEEP/TRASH)
  - bot.config.skin_families (120 registry skins)
  - luxury_live_floors / peak_lock (gate floors)
  - chat shelves + never-delay spill
  - kid-simple per-chat play cards

Outputs under bot/data/:
  keep_allowlist.json
  profit_skyscraper_brain.json
  CHAT_PROFIT_PLAYBOOK.md
  chat_playbook_cards.json
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
ROOTS = [
    HERE.parent.parent,  # /workspace
    Path("/workspace"),
    Path("/home/runner/workspace"),
]


def _boot_path() -> None:
    for root in ROOTS:
        if (root / "bot" / "config" / "skin_families.py").is_file():
            s = str(root)
            if s not in sys.path:
                sys.path.insert(0, s)
            return


def _load(path: Path) -> Any:
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    _boot_path()
    from bot.config.profit_skyscraper import (
        PLAY_RULES_SIMPLE,
        STAKE_POLICY,
        chat_map,
        distribution_plan,
        playbook_card,
    )
    from bot.config.skin_families import SKIN_FAMILIES

    triage = _load(DATA / "museum_triage_keep_trash.json") or {}
    catalog = _load(DATA / "museum_full_catalog.json") or {}
    floors = _load(DATA / "luxury_live_floors.json") or {}
    peak = _load(DATA / "peak_lock_config.json") or {}

    keep_rows = triage.get("keep") or []
    trash_rows = triage.get("trash") or []

    keep_family_ids = sorted({str(r["family_id"]) for r in keep_rows if r.get("family_id")})
    trash_family_ids = sorted({str(r["family_id"]) for r in trash_rows if r.get("family_id")})
    keep_reg = sorted(
        {str(r["registry_family"]) for r in keep_rows if r.get("registry_family")}
    )
    trash_reg = sorted(
        {str(r["registry_family"]) for r in trash_rows if r.get("registry_family")}
    )

    trash_needles = sorted(
        {
            str(r.get("label") or r.get("example_first_line") or "").splitlines()[0].strip()[:100]
            for r in trash_rows
            if (r.get("label") or r.get("example_first_line"))
        }
    )
    trash_needles = [n for n in trash_needles if len(n) >= 3]

    allowlist = {
        "version": 1,
        "built_at": datetime.now(timezone.utc).isoformat(),
        "source": "museum_triage_keep_trash.json",
        "rules": triage.get("rules")
        or {
            "KEEP": "edge OR ops OR result/timing/room — any angle",
            "TRASH": "no edge AND no value",
        },
        "stats": {
            "keep": len(keep_family_ids),
            "trash": len(trash_family_ids),
            "keep_registry": len(keep_reg),
            "trash_registry": len(trash_reg),
            "trash_text_needles": len(trash_needles),
        },
        "keep_family_ids": keep_family_ids,
        "trash_family_ids": trash_family_ids,
        "keep_registry_families": keep_reg,
        "trash_registry_families": trash_reg,
        "trash_text_needles": trash_needles,
    }
    (DATA / "keep_allowlist.json").write_text(
        json.dumps(allowlist, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    # Registry skin map
    registry: List[Dict[str, Any]] = []
    role_c: Counter = Counter()
    for fam in SKIN_FAMILIES:
        role_c[fam.role] += 1
        registry.append(
            {
                "family_id": fam.family_id,
                "role": fam.role,
                "era": fam.era,
                "label": fam.label,
                "default_lane": fam.default_lane,
                "example_first_line": fam.example_first_line,
                "in_keep_registry": fam.family_id in set(keep_reg),
            }
        )

    # Museum KEEP by role / reason
    keep_by_role: Counter = Counter()
    keep_by_reason: Counter = Counter()
    for r in keep_rows:
        keep_by_role[r.get("role") or "?"] += 1
        keep_by_reason[r.get("reason") or "?"] += 1

    # Floors / gates
    live_floors = floors.get("live_floors") or peak.get("live_building_floors") or []
    gate_aliases = floors.get("gate_aliases") or peak.get("gate_aliases") or {}
    blocked_floors = floors.get("blocked") or []

    # Top volume KEEP (money density)
    top_keep = sorted(keep_rows, key=lambda x: -(x.get("tg_count") or 0))[:60]

    brain = {
        "version": 1,
        "built_at": datetime.now(timezone.utc).isoformat(),
        "name": "PROFIT_SKYSCRAPER_OS",
        "mission": (
            "Understand every Telegram-bound skin/template/gate; distribute KEEP "
            "across Mr_iv4 (money penthouse) → UNIQUE_g1 (countdown) → UNIQUE_gN "
            "(overflow, never delay); block TRASH; kid-simple play rules so every "
            "chat is fully usable even at 5 signals/day."
        ),
        "honesty": (
            "Dollar outcomes depend on platform stakes, volume, and WR — not guaranteed. "
            "This OS maximizes capture of every real ENTER/GALE window at minimum stake "
            "and keeps every chat readable and actionable."
        ),
        "inventory": {
            "museum_templates": len(catalog.get("items") or []),
            "keep": allowlist["stats"]["keep"],
            "trash": allowlist["stats"]["trash"],
            "registry_skins": len(registry),
            "registry_by_role": dict(role_c),
            "keep_by_role": dict(keep_by_role),
            "keep_by_reason_top": dict(keep_by_reason.most_common(25)),
            "live_floors": live_floors,
            "gate_aliases": gate_aliases,
            "blocked_floors": blocked_floors,
        },
        "chat_map": chat_map(),
        "distribution": distribution_plan(),
        "registry_skins": registry,
        "top_keep_by_volume": [
            {
                "chrono_order": r.get("chrono_order"),
                "role": r.get("role"),
                "label": r.get("label"),
                "tg_count": r.get("tg_count"),
                "reason": r.get("reason"),
                "registry_family": r.get("registry_family"),
                "family_id": r.get("family_id"),
            }
            for r in top_keep
        ],
        "runtime": {
            "PROFIT_SKYSCRAPER": "1",
            "HUB_MONEY_FIRST": "1",
            "TELEGRAM_TRASH_BLOCK": "1",
            "TELEGRAM_SKIN_GATE": "1",
            "never_delay": True,
            "soft_cap_spills_to": "UNIQUE_g2…gN",
        },
        "play_rules": PLAY_RULES_SIMPLE,
        "stake_policy": STAKE_POLICY,
    }
    (DATA / "profit_skyscraper_brain.json").write_text(
        json.dumps(brain, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    cards = {
        "mr_iv4": playbook_card("mr_iv4"),
        "unique_g1": playbook_card("unique_g1"),
        "unique_gn": playbook_card("overflow"),
    }
    (DATA / "chat_playbook_cards.json").write_text(
        json.dumps(cards, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    # Markdown playbook
    lines = [
        "# Profit Skyscraper — how to use every chat (simple)",
        "",
        "Built from the full museum (827 templates) → **KEEP 777 / TRASH 50**, "
        "plus 120 registry skins and live floors/gates.",
        "",
        "## The building",
        "",
        "| Chat | Job | What you do |",
        "|---|---|---|",
        "| **Mr_iv4** | Money penthouse (most profit) | ENTER + color → min bet; gale → same color min; WIN/LOSS ends round |",
        "| **UNIQUE_g1** | Countdown / sniper | Bet before the timer hits 0 |",
        "| **UNIQUE_g2…gN** | Overflow when busy | Same rules — never wait for a free slot |",
        "",
        "## Universal rules (even a 12-year-old)",
        "",
    ]
    for i, rule in enumerate(PLAY_RULES_SIMPLE, 1):
        lines += [
            f"### {i}. When: {rule['when']}",
            f"- **Do:** {rule['do']}",
            f"- **Stop:** {rule['stop']}",
            "",
        ]
    lines += [
        "## Stake policy",
        "",
        f"- Mode: `{STAKE_POLICY['mode']}`",
        f"- {STAKE_POLICY['rule']}",
        f"- Gale: {STAKE_POLICY['gale_ladder']}",
        f"- Never: {STAKE_POLICY['never']}",
        f"- Worst chat (5 signals/day): {STAKE_POLICY['worst_case_5_signals']}",
        "",
        "## What the system does (autonomous)",
        "",
        "1. Blocks TRASH (shell pastes, agent meta, UI crumbs).",
        "2. Sends KEEP fires: money → Mr_iv4, countdown → UNIQUE_g1.",
        "3. Soft-cap → spill to UNIQUE_gN **immediately** (never delay a bet window).",
        "4. Results glue to the exact chat of the parent fire.",
        "5. Peak floors (JUN10, ELITE_V2, …) stay as gates; their skins ride the shelves.",
        "",
        "## Inventory snapshot",
        "",
        f"- Museum templates: {brain['inventory']['museum_templates']}",
        f"- KEEP: {brain['inventory']['keep']} · TRASH: {brain['inventory']['trash']}",
        f"- Registry skins: {brain['inventory']['registry_skins']} → {dict(role_c)}",
        f"- Live floors: {', '.join(str(x) for x in live_floors) or '(see peak_lock)'}",
        "",
        "## Pin these cards in each chat",
        "",
        "### Mr_iv4",
        "```",
        cards["mr_iv4"],
        "```",
        "",
        "### UNIQUE_g1",
        "```",
        cards["unique_g1"],
        "```",
        "",
        "### UNIQUE_gN",
        "```",
        cards["unique_gn"],
        "```",
        "",
        "## Machine files",
        "",
        "- `keep_allowlist.json` — live trash block list",
        "- `profit_skyscraper_brain.json` — full system map",
        "- `chat_playbook_cards.json` — pin texts",
        "- Regenerator: `python3 bot/build_profit_skyscraper_brain.py`",
        "",
    ]
    (DATA / "CHAT_PROFIT_PLAYBOOK.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "keep_allowlist": allowlist["stats"],
                "registry_skins": len(registry),
                "wrote": [
                    "keep_allowlist.json",
                    "profit_skyscraper_brain.json",
                    "chat_playbook_cards.json",
                    "CHAT_PROFIT_PLAYBOOK.md",
                ],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
