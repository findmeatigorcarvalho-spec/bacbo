#!/usr/bin/env python3
"""Triage UNIQUE_museum_chrono catalog → KEEP vs TRASH.

Source: museum_full_catalog.json (same templates posted to the Telegram chat).

Rules (user-locked):
  KEEP  = bet edge OR ops/system value OR any result indication OR timing OR
          inverse-usable OR volume-useful info OR room health — any angle.
  TRASH = no edge AND no value from any angle (UI crumbs, accidental shell
          pastes, agent meta chatter with no ops meaning).
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

HERE = Path(__file__).resolve().parent
CATALOG = HERE / "data" / "museum_full_catalog.json"
OUT_JSON = HERE / "data" / "museum_triage_keep_trash.json"
OUT_MD = HERE / "data" / "MUSEUM_TRIAGE_KEEP_TRASH.md"

# Definite trash: no edge and no ops value
_TRASH_EXACT = {
    "more",
}
_TRASH_PATTERNS = [
    r"^more$",
    r"curl\s+-s\s+-X\s+POST",
    r"~/workspace\$\s*curl",
    r"https://[0-9a-f-]{20,}.*\.janeway\.replit",
    r"made the bot do now,\s*on its own",
    r"If the dry run shows commented-out",
    r"This won't fix everything blind",
    r"Next script:\s*backups/",
    r"To finish this without more guessing",
    r"TEMPLATE PREVIEW\s*—\s*PART",
    r"TEMPLATE ARCHAEOLOGY PREVIEW",
    r"END OF PART\s+\d+",
    r"Running total:\s*\d+\s*distinct templates",
    r"IMPORTANT CORRECTION on the AITEST floors",
    r"don'?t paste",
    r"^```",
    r"git\s+reset\s+--hard",
    r"^cd\s+/home/runner",
    r"TEST:\s*confirming delivery",
    r"output test\s*—\s*if you see this",
    r"LUXURY TEST PING",
    r"MUSEUM PACK\s*—",
    r"MUSEUM\s*#\d",
    r"Chrono batch\s*#",
    r"CHRONO\s*#\d+\s*—",
    r"ACTIVATION SCRIPT READY",
    r"HOW TO RUN IT\s*\(on the bot",
    r"RESULTS FROM SCRIPT\s+\d+",
    r"Revised diagnosis:",
    r"BUT:\s*I found something useful",
    r"Same routine to create it",
    r"^Hers the message$",
    r"^Yo$",
    r"^nhza$",
    r"^Fix$",
    r"^I lost again$",
    r"^Best next time to play\?",
    r"^Tell me all setups that we had",
    r"^Every single time make a post",
    r"^Are you sure every single accurate",
    r"^that time inest\?",
    r"^make sure shedules",
    r"^find everything thatsnot okk",
]


def _text(it: dict) -> str:
    return f"{it.get('label') or ''}\n{it.get('body') or ''}\n{it.get('example_first_line') or ''}"


def classify(it: dict) -> Tuple[str, str]:
    """Return (KEEP|TRASH, reason)."""
    role = (it.get("role") or "").upper()
    raw = _text(it)
    low = raw.lower().strip()
    label = (it.get("label") or "").strip()

    # Explicit trash
    if label.casefold() in _TRASH_EXACT or low in _TRASH_EXACT:
        return "TRASH", "ui_crumb_no_value"
    for pat in _TRASH_PATTERNS:
        if re.search(pat, raw, re.I | re.M):
            return "TRASH", f"meta_or_accidental:{pat[:40]}"

    # Role defaults — product classes are KEEP unless trash matched above
    if role == "FIRE":
        return "KEEP", "fire_enter_edge"
    if role == "RESULT":
        return "KEEP", "result_indication"
    if role == "ONLINE":
        return "KEEP", "boot_menu_system"
    if role == "ROOM_RELAY":
        return "KEEP", "room_info_edge_ai_filter"
    if role == "OPS":
        return "KEEP", "ops_system_value"

    # UNKNOWN — keep if any value angle (bias KEEP; only clear junk is TRASH)
    keep_hints = [
        (r"\bWIN\b|\bLOSS\b|\bEMPATE\b|\bTIE\b|GREEN|AUTO\s+(WIN|LOSS|TIE)|PERDEU|GANHOU|RECUPER", "result_indication"),
        (r"JANELA|DO NOT BET|N[AÃ]O\s+(ENTRE|APOSTE)|APOSTAR|APOSTE|ENTRE AGORA|ENTER NOW|ENTRAR AGORA", "timing_or_entry_edge"),
        (r"GALE|RETENTATIVA|Entre novamente|AGUARDANDO G|entrando G|G0|G1|G2|G3|G7", "gale_ops_edge"),
        (r"quarantine|muted|grounded|cooldown|Cool-Down|watchdog|WARDEN|Circuit Breaker|CONEX[AÃ]O CONGELADA", "ops_health_value"),
        (r"GATE\s*\[|net negative|blocked_wins|hard_block|timing_gate|streak_gate|coalition_dedup", "gate_audit_value"),
        (r"FLOOR|ANDAR|PEAK|PROFITABLE|Leaderboard|CYCLE\s+(OPEN|CLOSE)|Skyscraper|SETUP SESSION", "floor_ops_value"),
        (r"SOLO|GOLDEN|PLATINUM|SEQUENCE|FLASH|ULTRA|EMERGIN|ALERTA|GOD-TIER|ELITE|TRIPLE LOCK|DUPLO", "tier_signal"),
        (r"VERMELHO|AZUL|\bRED\b|\bBLUE\b|Player|Banker|🔴|🔵|🟡", "color_indication"),
        (r"~\d+\s*s\b|\d+\s*s\b|\d+\s*sec|PARA ENTRAR|window|BRT|EDT|UTC|ÚLTIMA CHAMADA", "timing_indication"),
        (r"PARE|ATINGIDO|EXPIROU|MISS|SATURATION|COOLDOWN|RODADA J[AÁ] PASSOU", "gale_ops_edge"),
        (r"SEQU[EÊ]NCIA\s+(QUENTE|FRIA)|SECA DE SINAIS|SALA EM QUEDA|MERCADO INST[AÁ]VEL|HORA DESFAVOR", "market_regime_edge"),
        (r"HOR[AÁ]RIOS|GRADE|TABELA|schedule|RELAT[OÓ]RIO|STATUS DO SISTEMA|AUDIT|Forensics|Truth Report|Hourly Pulse", "schedule_audit_value"),
        (r"WR=\d|sWR=|OPTIMAL cells|BOTTOM-10|TOP-10|EV (Positivo|Negativo)|Calibra", "stats_edge"),
        (r"n=\s*\d+\s+WR=|n=\s*\d+\s+W=", "pair_room_stats_edge"),
        (r"📡|RELAY|@\w+|SAME TABLE|same_table", "room_info"),
        (r"Bot Ativo|ONLINE|AutoIntelligence|AutoAuditor|DELIVERY AUDIT|WebWatchdog|ACCURACY GUARDIAN|PERFORMANCE GUARDIAN|COBERTURA", "system_health"),
        (r"SINAL|SIGNAL|PREDICTION|CONSENSO|RADAR|FORMANDO|ANALISANDO|DIVERG", "signal_forming"),
        (r"VIP ROOM|Sinais retomados|Recovery Insight|CORRE[CÇ][AÃ]O|CORRECTION|DIRETO", "ops_recovery_value"),
        (r"risk flag|LIVE RISK|FULL AUDIT|SHADOW AUDIT|GATE DRIFT|MONITORAMENTO", "risk_audit_value"),
        (r"Hora (razo|ativa|baixo)|baixo volume|jogue com cautela", "hour_regime_edge"),
        (r"Engine em ALTA|ALTA performance|performance!", "engine_health_ops"),
        (r"Session check|bot alive|Sil[eê]ncio prolongado", "ops_silence_alive"),
        (r"SALAS DO DIA|worst hours|Next 24h Forecast|per-hour expected WR|Forecast\s*\(per-hour", "hour_forecast_edge"),
    ]
    for pat, reason in keep_hints:
        if re.search(pat, raw, re.I):
            return "KEEP", reason

    # Never-fired registry skins still KEEP for evaluation (code existence)
    if it.get("never_fired"):
        return "KEEP", "code_taught_never_fired_eval"

    # High historical volume alone = keep for volume/early-result building
    if int(it.get("tg_count") or 0) >= 20:
        return "KEEP", "volume_presence"

    # Default UNKNOWN with no recognizable value → trash
    if len(label) < 3:
        return "TRASH", "empty_or_tiny_no_value"
    return "TRASH", "no_edge_no_value_detected"


def main() -> int:
    pack = json.loads(CATALOG.read_text(encoding="utf-8"))
    items = pack.get("items") or []
    keep: List[dict] = []
    trash: List[dict] = []
    for it in items:
        verdict, reason = classify(it)
        row = {
            "chrono_order": it.get("chrono_order"),
            "family_id": it.get("family_id"),
            "registry_family": it.get("registry_family") or "",
            "role": it.get("role"),
            "label": it.get("label"),
            "tg_count": it.get("tg_count") or 0,
            "existence_at": it.get("existence_at"),
            "never_fired": bool(it.get("never_fired")),
            "verdict": verdict,
            "reason": reason,
            "example_first_line": (it.get("example_first_line") or "")[:200],
        }
        (keep if verdict == "KEEP" else trash).append(row)

    keep.sort(key=lambda x: (-(x["tg_count"] or 0), x["chrono_order"] or 0))
    trash.sort(key=lambda x: (x["chrono_order"] or 0))

    out: Dict[str, Any] = {
        "source": "museum_full_catalog.json (= UNIQUE_museum_chrono posted set)",
        "rules": {
            "KEEP": "edge OR ops/system value OR result/timing indication OR room info — any angle",
            "TRASH": "no edge AND no value (UI crumbs, shell pastes, agent meta)",
        },
        "stats": {
            "total": len(items),
            "keep": len(keep),
            "trash": len(trash),
            "keep_pct": round(100.0 * len(keep) / max(1, len(items)), 1),
            "keep_by_role": {},
            "trash_by_reason": {},
        },
        "keep": keep,
        "trash": trash,
    }
    for row in keep:
        r = row["role"] or "?"
        out["stats"]["keep_by_role"][r] = out["stats"]["keep_by_role"].get(r, 0) + 1
    for row in trash:
        r = row["reason"]
        out["stats"]["trash_by_reason"][r] = out["stats"]["trash_by_reason"].get(r, 0) + 1

    keep_by_reason: Dict[str, int] = {}
    for row in keep:
        keep_by_reason[row["reason"]] = keep_by_reason.get(row["reason"], 0) + 1
    out["stats"]["keep_by_reason"] = keep_by_reason

    lines = [
        "# Museum triage — KEEP vs TRASH",
        "",
        "Scanned: full `museum_full_catalog.json` (= everything posted to UNIQUE_museum_chrono).",
        "",
        "## Verdict",
        "",
        f"- Total templates: **{out['stats']['total']}**",
        f"- **KEEP: {out['stats']['keep']}** ({out['stats']['keep_pct']}%) — wire-eligible",
        f"- **TRASH: {out['stats']['trash']}** — UI crumbs / shell pastes / agent meta / museum-poster chatter",
        "",
        "Rules: KEEP = bet edge OR ops/system value OR result/timing/room indication — any angle. "
        "TRASH = no edge AND no value.",
        "",
        "## KEEP by role",
        "",
    ]
    for k, v in sorted(out["stats"]["keep_by_role"].items(), key=lambda kv: -kv[1]):
        lines.append(f"- `{k}`: {v}")
    lines += ["", "## KEEP by reason (top)", ""]
    for k, v in sorted(keep_by_reason.items(), key=lambda kv: -kv[1])[:25]:
        lines.append(f"- `{k}`: {v}")
    lines += ["", "## TRASH buckets", ""]
    trash_buckets = {
        "ui_crumb_tiny": 0,
        "user_chat_noise": 0,
        "shell_accidental": 0,
        "agent_meta_diagnosis": 0,
        "template_archaeology_meta": 0,
        "museum_poster_meta": 0,
        "delivery_test_ping": 0,
        "other": 0,
    }
    for row in trash:
        lab = (row["label"] or "")
        r = row["reason"]
        if "ui_crumb" in r or "empty_or_tiny" in r:
            trash_buckets["ui_crumb_tiny"] += 1
        elif any(x in lab for x in ("MUSEUM", "CHRONO #", "Chrono batch")):
            trash_buckets["museum_poster_meta"] += 1
        elif "TEMPLATE" in lab or "END OF PART" in lab:
            trash_buckets["template_archaeology_meta"] += 1
        elif any(x in lab.lower() for x in ("curl", "git reset", "cd /home", "workspace$")):
            trash_buckets["shell_accidental"] += 1
        elif any(x in lab for x in ("TEST:", "output test", "LUXURY TEST", "TEST PING")):
            trash_buckets["delivery_test_ping"] += 1
        elif any(
            x in lab
            for x in (
                "I lost",
                "Best next",
                "Tell me",
                "Every single",
                "Are you sure",
                "that time",
                "shedules",
                "thatsnot",
                "Yo",
                "Hers the",
                "Fix",
                "nhza",
                "ok",
            )
        ) or lab in ("I", "1", "ok", "Fix", "Yo"):
            trash_buckets["user_chat_noise"] += 1
        elif any(
            x in lab
            for x in (
                "made the bot",
                "dry run",
                "won't fix",
                "Next script",
                "ACTIVATION",
                "HOW TO RUN",
                "RESULTS FROM",
                "IMPORTANT CORRECTION",
                "Revised diagnosis",
                "BUT:",
                "Same routine",
                "guessing",
            )
        ):
            trash_buckets["agent_meta_diagnosis"] += 1
        else:
            trash_buckets["other"] += 1
    for k, v in trash_buckets.items():
        if v:
            lines.append(f"- `{k}`: {v}")
    out["stats"]["trash_buckets"] = trash_buckets

    lines += ["", "## Top KEEP by TG volume", ""]
    for row in keep[:50]:
        lines.append(
            f"- #{row['chrono_order']} · `{row['role']}` · tg={row['tg_count']} · "
            f"{(row['label'] or '')[:80]} · _{row['reason']}_"
        )
    lines += ["", "## Full TRASH list (do not wire)", ""]
    for row in trash:
        lines.append(
            f"- #{row['chrono_order']} · tg={row['tg_count']} · "
            f"{(row['label'] or '')[:100]}"
        )
    lines += [
        "",
        "## Machine-readable",
        "",
        "- JSON: `bot/data/museum_triage_keep_trash.json`",
        "- Regenerator: `python3 bot/triage_museum_keep_trash.py`",
        "",
    ]
    OUT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(out["stats"], indent=2))
    print("Wrote", OUT_JSON)
    print("Wrote", OUT_MD)
    print("TRASH samples:")
    for row in trash[:25]:
        print(f"  #{row['chrono_order']} {(row['label'] or '')[:70]} [{row['reason']}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
