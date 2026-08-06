"""Result Essence Engine — Profit Family AI (the 2000% better layer).

1000% better (already live): one organizer distributes by what chats BECOME.
2000% better (this module): every placement / invent / update is grounded in
the true essence of EVERY signal + RESULT we ever had — peak impact, volume,
WR floors, never-fired potential, comprovation pairs — then the whole bundle
and skin system is built/updated toward most volume + most profit period.

Purpose: invent the most profitable Family AI Bac Bo money-printing system.

Sources (offline atlas + live consult):
  museum_full_catalog.json          — every template (827)
  museum_triage_keep_trash.json     — KEEP 777 / TRASH 50
  peak_fidelity_ranker_report.json  — peak_day / peak_n / peak_wr / strength
  profit_organism_report.json       — vault perfect / dollar scaffold
  vault_patterns.json               — W/L patterns when present

Env:
  RESULT_ESSENCE_ENGINE=1           (default on)
  PROFIT_FAMILY_AI=1                (alias)
"""
from __future__ import annotations

import json
import math
import os
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


_DATA_CANDIDATES = [
    Path(__file__).resolve().parents[2] / "replit_elite_stack_patch" / "bot" / "data",
    Path(__file__).resolve().parents[1] / "data",
    Path("/home/runner/workspace/bot/data"),
    Path("/workspace/replit_elite_stack_patch/bot/data"),
    Path("/workspace/bot/data"),
]


def engine_enabled() -> bool:
    for key in ("RESULT_ESSENCE_ENGINE", "PROFIT_FAMILY_AI"):
        raw = os.environ.get(key)
        if raw is not None:
            return raw.strip().lower() not in {"0", "false", "no", "off"}
    return True


def _find_data() -> Path:
    for p in _DATA_CANDIDATES:
        if (p / "museum_triage_keep_trash.json").is_file() or (
            p / "museum_full_catalog.json"
        ).is_file():
            return p
    return _DATA_CANDIDATES[0]


def _load(path: Path) -> Any:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


# Role → profit-family weight (what makes money / protects money / proves money)
_ROLE_WEIGHT = {
    "FIRE": 1.0,
    "RESULT": 0.85,
    "OPS": 0.55,
    "ROOM_RELAY": 0.25,
    "ONLINE": 0.1,
    "UNKNOWN": 0.2,
}

# Registry / family needles → preferred BECOMES (essence of use)
_BECOMES_HINTS = (
    (re.compile(r"FLASH|ULTRA_TIE|EMPATE_DIRETO|SNIPER|DEPTH", re.I), "PRECISION"),
    (re.compile(r"GALE|RETENTATIVA|PREPARE_G1|AGUARDANDO", re.I), "ASSERTIVE"),
    (re.compile(r"RESULT|FORENSE|GANHOU|PERDEU|WIN_TIER|COLOR_BANNER", re.I), "IMPACT"),
    (re.compile(r"JANELA|RETIDO|COUNTDOWN|CD_FIRE|TIMER", re.I), "APEX"),
    (re.compile(r"GOLDEN|SOLO|SEQUENCE|PLATINUM|ENTER|APOSTAR", re.I), "APEX"),
)


@dataclass
class EssenceCard:
    """True essence of one signal/template — what makes it what it is."""

    family_id: str
    registry_family: str
    role: str
    label: str
    tg_count: int
    never_fired: bool
    had_original_result: bool
    existence_at: str
    reason: str
    # Derived
    essence: str
    impact_class: str  # PEAK_PROVEN | VOLUME_PROVEN | LATENT | PROTECT | PROOF | FILTER
    profit_score: float
    volume_score: float
    peak_boost: float
    potential_if_never_fired: float
    becomes_home: str  # APEX|PRECISION|VOLUME|ASSERTIVE|IMPACT|ELASTIC
    how_to_use: str
    how_to_update: str
    dimensions: Dict[str, float] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _peak_index(peak_report: Optional[dict]) -> Dict[str, dict]:
    out: Dict[str, dict] = {}
    if not peak_report:
        return out
    for row in peak_report.get("ranking") or []:
        floor = str(row.get("floor") or "").upper()
        if floor:
            out[floor] = row
    return out


def _match_peak(label: str, registry: str, peaks: Dict[str, dict]) -> Tuple[float, str]:
    blob = f"{label} {registry}".upper()
    best = 0.0
    which = ""
    for floor, row in peaks.items():
        if floor and floor in blob:
            # strength_score + peak_wr + log peak_n
            strength = float(row.get("strength_score") or 0)
            wr = float(row.get("peak_wr") or row.get("historical_wr") or 0)
            n = float(row.get("peak_n") or row.get("historical_n") or 0)
            boost = (strength / 100.0) + (wr / 25.0) + math.log1p(n) / 5.0
            if boost > best:
                best = boost
                which = (
                    f"{floor} peak_day={row.get('peak_day')} "
                    f"peak_n={row.get('peak_n')} peak_wr={row.get('peak_wr')}"
                )
    return best, which


def _becomes_home(role: str, family_id: str, registry: str, label: str) -> str:
    blob = f"{family_id} {registry} {label}"
    for rx, becomes in _BECOMES_HINTS:
        if rx.search(blob):
            return becomes
    role_u = (role or "").upper()
    if role_u == "RESULT":
        return "IMPACT"
    if role_u == "FIRE":
        return "APEX"
    if role_u == "OPS":
        return "IMPACT"
    if role_u == "ROOM_RELAY":
        return "VOLUME"  # density fuel / filter, not primary ENTER
    return "APEX"


def _essence_text(role: str, impact: str, never: bool, had_res: bool) -> str:
    bits = [f"role={role}", f"impact={impact}"]
    if never:
        bits.append("LATENT—never fired; potential unproven in live path")
    if had_res:
        bits.append("has_original_RESULT_pair—comprovation DNA")
    return "; ".join(bits)


def score_row(
    row: dict,
    *,
    peaks: Dict[str, dict],
    vault_boost: float = 0.0,
) -> EssenceCard:
    role = str(row.get("role") or "UNKNOWN")
    family_id = str(row.get("family_id") or "")
    registry = str(row.get("registry_family") or "")
    label = str(row.get("label") or row.get("example_first_line") or "")[:160]
    tg = int(row.get("tg_count") or 0)
    never = bool(row.get("never_fired"))
    had_res = bool(row.get("had_original_result"))
    reason = str(row.get("reason") or "")

    role_w = _ROLE_WEIGHT.get(role.upper(), 0.2)
    volume_score = math.log1p(tg) * role_w
    peak_boost, peak_note = _match_peak(label, registry, peaks)

    # Never fired KEEP FIRE/RESULT = latent money — invent/update priority
    potential = 0.0
    if never:
        if role.upper() == "FIRE":
            potential = 6.0 + min(4.0, math.log1p(tg))
        elif role.upper() == "RESULT":
            potential = 3.5
        else:
            potential = 2.0

    result_pair = 2.5 if had_res else 0.0
    # RESULT templates with huge tg_count = proven comprovation surfaces
    if role.upper() == "RESULT":
        result_pair += min(5.0, math.log1p(tg) / 2.0)

    profit_score = (
        volume_score * 1.4
        + peak_boost * 1.2
        + potential * 1.5
        + result_pair * 1.3
        + vault_boost
        + role_w * 2.0
    )

    becomes = _becomes_home(role, family_id, registry, label)
    if role.upper() == "FIRE" and tg >= 5000 and becomes == "APEX":
        impact = "VOLUME_PROVEN"
    elif peak_boost >= 3.0:
        impact = "PEAK_PROVEN"
    elif never and role.upper() == "FIRE":
        impact = "LATENT"
    elif role.upper() == "RESULT":
        impact = "PROOF"
    elif role.upper() == "OPS":
        impact = "PROTECT"
    elif role.upper() == "ROOM_RELAY":
        impact = "FILTER"
    else:
        impact = "VOLUME_PROVEN" if tg >= 100 else "LATENT"

    how_use = {
        "APEX": "Primary ENTER/clock/gale surface — fire on time at min stake",
        "PRECISION": "Sniper only — high-assertiveness; protect APEX from noise",
        "VOLUME": "Absorb density / overflow — never delay the window",
        "ASSERTIVE": "Gale/recovery stated — same color, min stake",
        "IMPACT": "RESULT comprovation / ops truth — glue under parent FIRE",
        "ELASTIC": "Mint under pressure — capture leftover honest chances",
    }.get(becomes, "Place where BECOMES maximizes profit")

    how_update = (
        "Raise priority / revive into live path; attach RESULT immediately"
        if never
        else (
            "Keep dense on home chat; soft-cap spill never delay; update pin cards "
            "from live WR if DB available"
            if tg >= 1000
            else "Maintain; promote if live WR/volume rises"
        )
    )
    if peak_note:
        how_update += f" | peak:{peak_note}"

    dims = {
        "Profit": round(profit_score, 3),
        "Volume": round(volume_score, 3),
        "WR": round(peak_boost, 3),
        "Precision": 1.0 if becomes == "PRECISION" else 0.4,
        "Assertiveness": 1.0 if role.upper() == "FIRE" else 0.3,
        "Existence": 0.2 if never else 1.0,
        "Essence": round(role_w + (0.5 if had_res else 0), 3),
        "Impact": round(peak_boost + (potential / 2), 3),
        "Results": round(result_pair, 3),
    }

    return EssenceCard(
        family_id=family_id,
        registry_family=registry,
        role=role,
        label=label,
        tg_count=tg,
        never_fired=never,
        had_original_result=had_res,
        existence_at=str(row.get("existence_at") or ""),
        reason=reason,
        essence=_essence_text(role, impact, never, had_res),
        impact_class=impact,
        profit_score=round(profit_score, 3),
        volume_score=round(volume_score, 3),
        peak_boost=round(peak_boost, 3),
        potential_if_never_fired=round(potential, 3),
        becomes_home=becomes,
        how_to_use=how_use,
        how_to_update=how_update,
        dimensions=dims,
    )


def build_atlas(data_dir: Optional[Path] = None) -> Dict[str, Any]:
    """Build the full Result Essence Atlas from every KEEP (+ catalog enrich)."""
    data = data_dir or _find_data()
    triage = _load(data / "museum_triage_keep_trash.json") or {}
    catalog = _load(data / "museum_full_catalog.json") or {}
    peak = _load(data / "peak_fidelity_ranker_report.json") or {}
    organism = _load(data / "profit_organism_report.json") or {}
    vault = _load(data / "vault_patterns.json") or {}

    peaks = _peak_index(peak)
    cat_by_fid = {
        str(i.get("family_id")): i
        for i in (catalog.get("items") or [])
        if i.get("family_id")
    }

    vault_boost = 0.0
    perfect = organism.get("vault_perfect_top") or []
    if perfect:
        vault_boost = min(8.0, math.log1p(sum(int(p.get("W") or 0) for p in perfect[:10])))

    cards: List[EssenceCard] = []
    for row in triage.get("keep") or []:
        fid = str(row.get("family_id") or "")
        enrich = dict(row)
        if fid in cat_by_fid:
            c = cat_by_fid[fid]
            enrich.setdefault("had_original_result", c.get("had_original_result"))
            enrich.setdefault("never_fired", c.get("never_fired"))
            enrich.setdefault("tg_count", c.get("tg_count"))
            enrich.setdefault("label", c.get("label"))
        cards.append(score_row(enrich, peaks=peaks, vault_boost=vault_boost * 0.05))

    cards.sort(key=lambda c: (-c.profit_score, -c.tg_count))

    by_becomes: Dict[str, List[dict]] = {}
    for c in cards:
        by_becomes.setdefault(c.becomes_home, []).append(
            {
                "family_id": c.family_id,
                "label": c.label,
                "profit_score": c.profit_score,
                "tg_count": c.tg_count,
                "impact_class": c.impact_class,
                "never_fired": c.never_fired,
            }
        )

    invent = _invent_directives(cards, peaks, organism)
    top_fire = [c.as_dict() for c in cards if c.role.upper() == "FIRE"][:40]
    top_result = [c.as_dict() for c in cards if c.role.upper() == "RESULT"][:40]
    latent = [c.as_dict() for c in cards if c.never_fired][:40]

    atlas = {
        "version": 1,
        "name": "RESULT_ESSENCE_ATLAS",
        "purpose": (
            "Family AI Bac Bo money-printing system — every chat/skin/update "
            "grounded in every signal+RESULT essence, peak impact, and latent potential."
        ),
        "ambition": "most volume possible · most profit possible · period",
        "law_1000": "One organizer distributes by what chats BECOME.",
        "law_2000": (
            "Know every part of every signal+RESULT — true essence, peak-day impact, "
            "never-fired potential — then invent/update the whole bundle FROM results."
        ),
        "stats": {
            "keep_scored": len(cards),
            "trash_blocked": len(triage.get("trash") or []),
            "catalog_items": len(catalog.get("items") or []),
            "peak_floors": len(peaks),
            "vault_perfect": len(perfect),
            "latent_never_fired": sum(1 for c in cards if c.never_fired),
            "fire_keep": sum(1 for c in cards if c.role.upper() == "FIRE"),
            "result_keep": sum(1 for c in cards if c.role.upper() == "RESULT"),
        },
        "peak_floors_top": [
            {
                "floor": r.get("floor"),
                "peak_day": r.get("peak_day"),
                "peak_n": r.get("peak_n"),
                "peak_wr": r.get("peak_wr"),
                "strength_score": r.get("strength_score"),
                "historical_g0_wr": r.get("historical_g0_wr"),
            }
            for r in (peak.get("top10") or [])[:10]
        ],
        "by_becomes_top": {
            k: v[:15] for k, v in sorted(by_becomes.items(), key=lambda kv: -len(kv[1]))
        },
        "top_profit_fire": top_fire,
        "top_profit_result": top_result,
        "latent_invent": latent,
        "invent_directives": invent,
        "family_index": {
            c.family_id: {
                "profit_score": c.profit_score,
                "becomes_home": c.becomes_home,
                "impact_class": c.impact_class,
                "tg_count": c.tg_count,
                "never_fired": c.never_fired,
            }
            for c in cards
            if c.family_id
        },
        "registry_index": _registry_rollup(cards),
        "honesty": (
            "Dollar totals depend on platform stake/volume/WR — not guaranteed. "
            "This atlas maximizes honest capture from every proven + latent fragment."
        ),
        "reality": "Make It Real / It Is Real, Really. It Is Real truthfully.",
    }
    return atlas


def _registry_rollup(cards: List[EssenceCard]) -> Dict[str, Any]:
    out: Dict[str, Dict[str, Any]] = {}
    for c in cards:
        key = c.registry_family or c.family_id or "?"
        bucket = out.setdefault(
            key,
            {
                "n": 0,
                "tg_sum": 0,
                "profit_sum": 0.0,
                "never_fired": 0,
                "roles": {},
                "best_becomes": c.becomes_home,
            },
        )
        bucket["n"] += 1
        bucket["tg_sum"] += c.tg_count
        bucket["profit_sum"] += c.profit_score
        if c.never_fired:
            bucket["never_fired"] += 1
        bucket["roles"][c.role] = bucket["roles"].get(c.role, 0) + 1
    # sort keys by profit
    ranked = sorted(out.items(), key=lambda kv: -kv[1]["profit_sum"])
    return {
        k: {
            **v,
            "profit_sum": round(v["profit_sum"], 3),
            "avg_profit": round(v["profit_sum"] / max(1, v["n"]), 3),
        }
        for k, v in ranked[:80]
    }


def _invent_directives(
    cards: List[EssenceCard],
    peaks: Dict[str, dict],
    organism: dict,
) -> List[Dict[str, Any]]:
    """What to invent / update / densify — built FROM results + peak truth."""
    dirs: List[Dict[str, Any]] = []

    # 1) Densify proven peak floors into APEX
    for floor, row in sorted(
        peaks.items(), key=lambda kv: -float(kv[1].get("strength_score") or 0)
    )[:8]:
        dirs.append(
            {
                "action": "DENSIFY_PEAK_FLOOR",
                "target_chat_becomes": "APEX",
                "floor": floor,
                "why": (
                    f"peak_day={row.get('peak_day')} n={row.get('peak_n')} "
                    f"wr={row.get('peak_wr')} strength={row.get('strength_score')}"
                ),
                "how": "Keep gate live; prefer skins from this floor on UNIQUE_g1",
                "profit_period": "max when volume approaches peak_n at peak_wr",
            }
        )

    # 2) Revive latent never-fired FIRE KEEP
    for c in cards:
        if c.never_fired and c.role.upper() == "FIRE":
            dirs.append(
                {
                    "action": "INVENT_LATENT_FIRE",
                    "family_id": c.family_id,
                    "label": c.label,
                    "target_chat_becomes": c.becomes_home,
                    "why": f"never_fired KEEP FIRE potential={c.potential_if_never_fired}",
                    "how": c.how_to_update,
                    "profit_period": "uncapped upside until first live WR sample",
                }
            )
        if len([d for d in dirs if d["action"] == "INVENT_LATENT_FIRE"]) >= 25:
            break

    # 3) RESULT comprovation surfaces → IMPACT + glue law
    for c in cards:
        if c.role.upper() == "RESULT" and c.tg_count >= 500:
            dirs.append(
                {
                    "action": "LOCK_RESULT_COMPROVATION",
                    "family_id": c.family_id,
                    "label": c.label,
                    "target_chat_becomes": "IMPACT",
                    "why": f"tg_count={c.tg_count} proven RESULT surface",
                    "how": "Attach immediately under parent FIRE — zero delay",
                    "profit_period": "compounds trust → more human volume on APEX",
                }
            )
        if len([d for d in dirs if d["action"] == "LOCK_RESULT_COMPROVATION"]) >= 20:
            break

    # 4) Top FIRE by profit → APEX / PRECISION / VOLUME split
    fires = [c for c in cards if c.role.upper() == "FIRE"][:30]
    for c in fires:
        dirs.append(
            {
                "action": "PRIORITIZE_FIRE_SKIN",
                "family_id": c.family_id,
                "label": c.label,
                "target_chat_becomes": c.becomes_home,
                "why": (
                    f"profit_score={c.profit_score} tg={c.tg_count} "
                    f"impact={c.impact_class}"
                ),
                "how": c.how_to_use,
                "profit_period": "core printing skins — densest honest capture",
            }
        )

    # 5) Organism vault perfect patterns
    for p in (organism.get("vault_perfect_top") or [])[:10]:
        dirs.append(
            {
                "action": "HONOR_VAULT_PERFECT",
                "pattern": {"keys": p.get("keys"), "values": p.get("values")},
                "W": p.get("W"),
                "L": p.get("L"),
                "target_chat_becomes": "PRECISION",
                "why": f"vault perfect W={p.get('W')} L={p.get('L')}",
                "how": "Prefer when pattern matches — high WR assertiveness",
                "profit_period": "edge per signal maximized",
            }
        )

    # 6) Bundle purpose statement
    dirs.insert(
        0,
        {
            "action": "BUNDLE_PURPOSE",
            "target_chat_becomes": "ALL",
            "why": "Family AI Bac Bo money-printing — every chat BECOMES max profit",
            "how": (
                "UNIQUE_g1 APEX densest proven FIRE+clock+gale; "
                "g2 PRECISION peak-WR sniper; g3 VOLUME overflow; "
                "g4 ASSERTIVE recovery; g5 IMPACT RESULT proof; "
                "g6+ ELASTIC never miss. RESULT always under its FIRE now."
            ),
            "profit_period": "most volume possible × most honest WR possible",
        },
    )
    return dirs


_ATLAS_CACHE: Optional[Dict[str, Any]] = None


def load_atlas(force: bool = False) -> Dict[str, Any]:
    global _ATLAS_CACHE
    if _ATLAS_CACHE is not None and not force:
        return _ATLAS_CACHE
    data = _find_data()
    path = data / "result_essence_atlas.json"
    loaded = _load(path)
    if loaded and isinstance(loaded, dict) and loaded.get("family_index"):
        _ATLAS_CACHE = loaded
        return loaded
    atlas = build_atlas(data)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(atlas, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        # also mirror under bot/data if different
        alt = Path(__file__).resolve().parents[1] / "data" / "result_essence_atlas.json"
        if alt.parent != path.parent:
            alt.parent.mkdir(parents=True, exist_ok=True)
            alt.write_text(json.dumps(atlas, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except Exception:
        pass
    _ATLAS_CACHE = atlas
    return atlas


def essence_for_text(
    text: Optional[str] = None,
    *,
    family_id: Optional[str] = None,
    signal_kind: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Live consult: best matching essence card for this signal."""
    if not engine_enabled():
        return None
    atlas = load_atlas()
    idx = atlas.get("family_index") or {}
    if family_id and family_id in idx:
        return {"family_id": family_id, **idx[family_id], "match": "family_id"}

    blob = f"{text or ''}\n{signal_kind or ''}\n{family_id or ''}".upper()
    reg_idx = atlas.get("registry_index") or {}
    best_key = None
    best_score = -1.0
    for key, meta in reg_idx.items():
        if key and key.upper() in blob:
            score = float(meta.get("profit_sum") or 0)
            if score > best_score:
                best_score = score
                best_key = key
    if best_key:
        meta = reg_idx[best_key]
        return {
            "registry_family": best_key,
            "profit_score": meta.get("avg_profit"),
            "becomes_home": meta.get("best_becomes"),
            "tg_count": meta.get("tg_sum"),
            "match": "registry",
        }

    # Needle match against top fires
    for card in atlas.get("top_profit_fire") or []:
        lab = str(card.get("label") or "")[:40].upper()
        if lab and lab[:12] in blob:
            return {**card, "match": "label_needle"}
    return None


def becomes_boost_from_essence(essence: Optional[Dict[str, Any]]) -> Dict[str, float]:
    """Score deltas for organizer peers from essence match."""
    boosts = {
        "UNIQUE_g1": 0.0,
        "UNIQUE_g2": 0.0,
        "UNIQUE_g3": 0.0,
        "UNIQUE_g4": 0.0,
        "UNIQUE_g5": 0.0,
    }
    if not essence:
        return boosts
    becomes = str(essence.get("becomes_home") or "").upper()
    profit = float(essence.get("profit_score") or essence.get("avg_profit") or 0)
    amp = min(8.0, max(0.5, profit / 3.0))
    mapping = {
        "APEX": "UNIQUE_g1",
        "PRECISION": "UNIQUE_g2",
        "VOLUME": "UNIQUE_g3",
        "ASSERTIVE": "UNIQUE_g4",
        "IMPACT": "UNIQUE_g5",
    }
    peer = mapping.get(becomes)
    if peer:
        boosts[peer] += amp
    # Proven volume always feeds APEX existence
    tg = int(essence.get("tg_count") or 0)
    if tg >= 3000:
        boosts["UNIQUE_g1"] += 1.5
    if essence.get("never_fired"):
        # Latent: still APEX first to prove, then elastic
        boosts["UNIQUE_g1"] += 2.0
    return boosts


def family_ai_manifest() -> Dict[str, Any]:
    atlas = load_atlas()
    return {
        "model": "PROFIT_FAMILY_AI",
        "layers": {
            "1000pct": "ONE_AI_ORGANIZER — distribute by BECOMES",
            "2000pct": "RESULT_ESSENCE_ENGINE — know every signal+RESULT; invent from peaks",
        },
        "purpose": atlas.get("purpose"),
        "ambition": atlas.get("ambition"),
        "stats": atlas.get("stats"),
        "invent_top": (atlas.get("invent_directives") or [])[:12],
        "peak_floors_top": atlas.get("peak_floors_top"),
        "enabled": engine_enabled(),
        "reality": atlas.get("reality"),
    }
