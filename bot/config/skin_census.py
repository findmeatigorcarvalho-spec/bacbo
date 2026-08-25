"""Complete skin/floor census — everything ever created since day 1.

Union of three sources (a type counts if present in ANY):
  1. CODE / templates / registered families (created, even if never fired)
  2. TELEGRAM archaeology (appeared in chat)
  3. DB signal_kind / card types (stored outbound), when bacbo.db available

Each distinct skin family is a candidate **building floor**, ranked later by
volume / WR / G0 / profit when metrics exist.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sqlite3
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from bot.config.skin_families import (
    SKIN_FAMILIES,
    classify_telegram_skin,
    family_ids,
)


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]  # /workspace
DEFAULT_TG_TYPES = Path(
    "/tmp/tg_arch_final/tg_arch_catalog_20260803T234517Z/types_first_seen.csv"
)
DEFAULT_OUT_JSON = REPO / "bot" / "data" / "skin_floor_census.json"
DEFAULT_OUT_CSV = REPO / "bot" / "data" / "skin_floor_census.csv"
DEFAULT_OUT_MD = REPO / "replit_elite_stack_patch" / "SKIN_FLOOR_CENSUS.md"

# Patterns that look like created card / kind / template identifiers in code.
_CODE_ID_RE = re.compile(
    r"\b("
    r"FIRE_[A-Z0-9_]{3,}|"
    r"RESULT_[A-Z0-9_]{3,}|"
    r"CD_FIRE_[A-Z0-9_]{3,}|"
    r"CD_RES_[A-Z0-9_]{3,}|"
    r"RES_[A-Z0-9_]{3,}|"
    r"ONLINE_[A-Z0-9_]{3,}|"
    r"OPS_[A-Z0-9_]{3,}|"
    r"NORMAL_SIGNAL_FIRE|NORMAL_RESULT|"
    r"COUNTDOWN_SIGNAL_FIRE|COUNTDOWN_RESULT|"
    r"SOLO_ELITE|GOLDEN|SEQUENCE|PLATINUM|FLASH|ULTRA_TIE|EMERGING|EMERGINDO|"
    r"ORACLE|COALITION|CONSENSUS"
    r")\b"
)

_FIRST_LINE_HINTS = [
    (r"GOLDEN SIGNAL\s*—\s*ENTER NOW", "FIRE_GOLDEN_ENTER", "FIRE"),
    (r"SOLO ELITE SIGNAL", "FIRE_SOLO_ELITE_ENTER", "FIRE"),
    (r"SEQUENCE SIGNAL\s*—\s*ENTER NOW", "FIRE_SEQUENCE_ENTER", "FIRE"),
    (r"SIGNAL CONFIRMED\s*—\s*ENTER NOW", "FIRE_CONFIRMED_ENTER", "FIRE"),
    (r"PLATINUM SIGNAL", "FIRE_PLATINUM_ENTER", "FIRE"),
    (r"GALE\s*\d+\s*—\s*RETENTATIVA", "FIRE_GALE_RETENTATIVA", "FIRE"),
    (r"GALE\s*\d+\s*—\s*Entre novamente", "FIRE_GALE_ENTRE_NOVAMENTE", "FIRE"),
    (r"APOSTAR AGORA", "FIRE_APOSTAR_AGORA_FAMILY", "FIRE"),
    (r"JANELA\s*[:=]", "FIRE_JANELA_TIMED", "FIRE"),
    (r"ULTRA\s*TIE", "FIRE_ULTRA_TIE", "FIRE"),
    (r"EMPATE DIRETO", "FIRE_EMPATE_DIRETO_G0", "FIRE"),
    (r"G0 DIRETO", "FIRE_G0_DIRETO", "FIRE"),
    (r"PREPARE O G1", "FIRE_PREPARE_G1", "FIRE"),
    (r"UserBot ONLINE", "ONLINE_BANNER", "ONLINE"),
    (r"LUXURY OUTBOX ONLINE", "ONLINE_LUXURY_OUTBOX", "ONLINE"),
    (r"🟡\s*EMPATE\s*—", "RESULT_EMPATE", "RESULT"),
    (r"✅\s*WIN\s*—", "RESULT_WIN_TIER", "RESULT"),
    (r"❌\s*LOSS\s*—", "RESULT_LOSS_TIER", "RESULT"),
    (r"RESUMIDO FORENSE", "RESULT_FORENSIC_INTERVALO", "RESULT"),
    (r"ORACLE CARD", "RESULT_ORACLE_CARD", "RESULT"),
    (r"CAMADAS DO DIA", "OPS_CAMADAS_DO_DIA", "OPS"),
    (r"SEQU[EÊ]NCIA QUENTE", "OPS_SEQ_QUENTE", "OPS"),
    (r"SEQU[EÊ]NCIA FRIA", "OPS_SEQ_FRIA", "OPS"),
    (r"TRIPLE LOCK", "OPS_TRIPLE_LOCK", "OPS"),
    (r"Sinal Retido", "FIRE_SINAL_RETIDO_LIBERADO", "FIRE"),
    (r"CD_FIRE_TIMER_BRT_EDT_APOSTAR", "CD_FIRE_TIMER_BRT_EDT_APOSTAR", "FIRE"),
    (r"CD_FIRE_QUANTUM_LOCK", "CD_FIRE_QUANTUM_LOCK", "FIRE"),
    (r"CD_FIRE_RUSH_NS_LEFT", "CD_FIRE_RUSH_NS_LEFT", "FIRE"),
    (r"CD_RES_GREEN_G_BRT", "CD_RES_GREEN_G_BRT", "RESULT"),
    (r"CD_RES_BELL_GANHOU", "CD_RES_BELL_GANHOU", "RESULT"),
    (r"CD_RES_RODADAS_TEMPO", "CD_RES_RODADAS_TEMPO", "RESULT"),
]

_KIND_DB_ALIASES = {
    "SOLO_ELITE": "SIGNAL_KIND_SOLO_ELITE",
    "GOLDEN": "SIGNAL_KIND_GOLDEN",
    "SEQUENCE": "SIGNAL_KIND_SEQUENCE",
    "PLATINUM": "SIGNAL_KIND_PLATINUM",
    "FLASH": "SIGNAL_KIND_FLASH",
    "EMERGING": "SIGNAL_KIND_EMERGING",
    "ULTRA_TIE": "SIGNAL_KIND_ULTRA_TIE",
}


@dataclass
class FloorRow:
    floor_id: str
    role: str = "UNKNOWN"
    label: str = ""
    sources: Set[str] = field(default_factory=set)
    created_in_code: bool = False
    registered_family: bool = False
    seen_telegram: bool = False
    in_db: bool = False
    tg_count: int = 0
    tg_first_seen: str = ""
    tg_example: str = ""
    db_fired: int = 0
    db_with_outcome: int = 0
    db_wins: int = 0
    db_g0: int = 0
    db_first_fired: str = ""
    notes: str = ""
    # Rank inputs (filled when metrics exist)
    score: float = 0.0
    rank_band: str = "UNRANKED"  # PENTHOUSE|UPPER|MID|BASEMENT|NOISE|CREATED_ONLY

    def touch_source(self, src: str) -> None:
        self.sources.add(src)


def _ensure(rows: Dict[str, FloorRow], floor_id: str, **kwargs: Any) -> FloorRow:
    fid = (floor_id or "").strip()
    if not fid:
        fid = "UNKNOWN"
    row = rows.get(fid)
    if row is None:
        row = FloorRow(floor_id=fid, label=kwargs.get("label") or fid)
        rows[fid] = row
    for k, v in kwargs.items():
        if k == "label" and v and (not row.label or row.label == fid):
            row.label = str(v)
        elif k == "role" and v and row.role in ("", "UNKNOWN"):
            row.role = str(v)
        elif k == "notes" and v:
            if row.notes:
                if str(v) not in row.notes:
                    row.notes = f"{row.notes}; {v}"
            else:
                row.notes = str(v)
        elif k == "tg_count":
            row.tg_count += int(v or 0)
        elif k == "db_fired":
            row.db_fired += int(v or 0)
        elif k == "db_with_outcome":
            row.db_with_outcome += int(v or 0)
        elif k == "db_wins":
            row.db_wins += int(v or 0)
        elif k == "db_g0":
            row.db_g0 += int(v or 0)
        elif k == "tg_first_seen" and v and (
            not row.tg_first_seen or str(v) < row.tg_first_seen
        ):
            row.tg_first_seen = str(v)
        elif k == "db_first_fired" and v and (
            not row.db_first_fired or str(v) < row.db_first_fired
        ):
            row.db_first_fired = str(v)
        elif k == "tg_example" and v and not row.tg_example:
            row.tg_example = str(v)[:160]
        elif k in (
            "created_in_code",
            "registered_family",
            "seen_telegram",
            "in_db",
        ) and v:
            setattr(row, k, True)
    return row


def mine_registered_families(rows: Dict[str, FloorRow]) -> None:
    for fam in SKIN_FAMILIES:
        r = _ensure(
            rows,
            fam.family_id,
            role=fam.role,
            label=fam.label,
            registered_family=True,
            created_in_code=True,
            notes=fam.notes or f"era {fam.era}",
            tg_example=fam.example_first_line,
        )
        r.touch_source("REGISTERED")


def mine_code_paths(rows: Dict[str, FloorRow], roots: Iterable[Path]) -> None:
    skip_dirs = {
        ".git",
        "__pycache__",
        "node_modules",
        "tg_archaeology_partial_30k",
        "tg_archaeology_partial_ba19ss",
        "recovery_probe",
    }
    skip_names = {
        "skin_floor_census.json",
        "skin_floor_census.csv",
        "SKIN_FLOOR_CENSUS.md",
        "types_first_seen.csv",
        "all_messages.csv",
        "unknown_messages.csv",
    }
    exts = {".py", ".md", ".json", ".sh"}
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if any(part in skip_dirs for part in path.parts):
                continue
            if path.name in skip_names:
                continue
            if path.suffix.lower() not in exts:
                continue
            # Skip huge dumps
            try:
                if path.stat().st_size > 2_000_000:
                    continue
                text = path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            for m in _CODE_ID_RE.finditer(text):
                tok = m.group(1)
                # Skip incomplete fragments from regex on f-strings / prefixes
                if tok.endswith("_") or len(tok) < 5:
                    continue
                if tok in {
                    "FIRE_IF_TRI_BRAIN_OK",
                    "FIRE_IF_TRI_BRAIN_OK_AND_NO_LOSS_RISK",
                    "FIRE_IN_VOLUME_MODE_IF_NO_LOSS_RISK",
                }:
                    continue  # control-flow names, not card skins
                # Map bare kinds to SIGNAL_KIND_* floors (created in engine)
                if tok in _KIND_DB_ALIASES:
                    fid = _KIND_DB_ALIASES[tok]
                    role = "FIRE"
                else:
                    fid = tok
                    role = (
                        "FIRE"
                        if "FIRE" in tok or tok in {"GOLDEN", "SEQUENCE"}
                        else "RESULT"
                        if "RESULT" in tok or tok.startswith("RES_") or tok.startswith("CD_RES")
                        else "ONLINE"
                        if tok.startswith("ONLINE")
                        else "OPS"
                        if tok.startswith("OPS")
                        else "UNKNOWN"
                    )
                r = _ensure(
                    rows,
                    fid,
                    role=role,
                    created_in_code=True,
                    label=fid,
                    notes=f"code:{path.name}",
                )
                r.touch_source("CODE")
            for pat, fid, role in _FIRST_LINE_HINTS:
                if re.search(pat, text, re.I):
                    r = _ensure(
                        rows,
                        fid,
                        role=role,
                        created_in_code=True,
                        label=fid,
                        notes=f"template_hint:{path.name}",
                    )
                    r.touch_source("CODE")


def _normalize_archaeology_type_id(type_id: str) -> Tuple[str, str]:
    """Collapse over-fingerprinted archaeology ids → stable floor id + note."""
    tid = (type_id or "").strip()
    if not tid:
        return tid, ""
    # Variable-N JANELA → one timed family (Ns is not a separate floor)
    if re.match(r"^FIRE_JANELA_\d+S_", tid, re.I) or re.match(r"^FIRE_JANELA_", tid, re.I):
        return "FIRE_JANELA_TIMED", "collapsed_janela_ns"
    # Color/room banner dumps
    if tid.startswith("RESULT_BANNER_"):
        return "RESULT_BANNER_FAMILY", "collapsed_banner"
    # Gate-net-negative / hour-block dumps mis-tagged as RESULT_GALE_*
    if tid.startswith("RESULT_GALE_"):
        if re.search(
            r"(GATE|BLOCK|SAVED_|NET_NEG|HOUR_BLOCK|DUPE_GUARD|BACBOBRL|ROBOFREE|WR_)",
            tid,
            re.I,
        ):
            return "OPS_GATE_HEALTH_DUMP", "collapsed_gate_dump"
        return "RESULT_GALE_OUTCOME", "collapsed_gale_outcome"
    # Kind-scoped win/loss/empate stay distinct when kind is clean
    m = re.match(r"^RESULT_(WIN|LOSS|EMPATE)_([A-Z0-9_]{2,40})$", tid)
    if m:
        outcome, kind = m.group(1), m.group(2)
        if kind in {
            "SOLO_ELITE",
            "GOLDEN",
            "SEQUENCE",
            "PLATINUM",
            "FLASH",
            "ULTRA_TIE",
            "EMERGING",
            "G0_FALHOU",
            "G1_FALHOU",
            "G2_FALHOU",
            "G3_FALHOU",
        } or (kind.isupper() and len(kind) <= 24 and not re.search(r"\d{5,}", kind)):
            return tid, "kind_scoped_result"
        family = {
            "WIN": "RESULT_WIN_TIER",
            "LOSS": "RESULT_LOSS_TIER",
            "EMPATE": "RESULT_EMPATE",
        }[outcome]
        return family, "collapsed_result_fingerprint"
    # Gale retentativa / entre novamente kind variants → family floors
    m = re.match(r"^FIRE_GALE_(\d+)_RETENTATIVA_", tid, re.I)
    if m:
        return "FIRE_GALE_RETENTATIVA", "collapsed_gale_retentativa"
    m = re.match(r"^FIRE_GALE_(\d+)_ENTRE_", tid, re.I)
    if m:
        return "FIRE_GALE_ENTRE_NOVAMENTE", "collapsed_gale_entre"
    # Room quarantine / delivery audit spam → ops families
    if tid.startswith("OPS_AUTO_QUARANTINE_") or tid.startswith("OPS_QUARANTINE_ENDED_"):
        return "OPS_ROOM_QUARANTINE", "collapsed_quarantine"
    if tid.startswith("OPS_DELIVERY_AUDIT_"):
        return "OPS_DELIVERY_AUDIT", "collapsed_delivery_audit"
    if tid in {"OPS_MANUAL_RESULT_HINT"} or tid.startswith("OPS_MANUAL_RESULT"):
        # Archaeology catch-all for prediction/footer lines — ops, not a money skin
        return "OPS_MANUAL_RESULT_HINT", "ops_manual_hint"
    return tid, ""


def ingest_telegram_types_csv(rows: Dict[str, FloorRow], csv_path: Path) -> Dict[str, Any]:
    meta: Dict[str, Any] = {
        "path": str(csv_path),
        "raw_type_rows": 0,
        "mapped_rows": 0,
        "unmapped_raw_ids": 0,
        "collapsed_rows": 0,
    }
    if not csv_path.exists():
        meta["error"] = "missing"
        return meta

    with csv_path.open("r", encoding="utf-8", errors="ignore", newline="") as fh:
        reader = csv.DictReader(fh)
        for rec in reader:
            meta["raw_type_rows"] += 1
            type_id = (rec.get("type_id") or "").strip()
            role = (rec.get("role") or "").strip().upper()
            first_line = (rec.get("first_line") or "").strip()
            count = int(float(rec.get("count") or 0) or 0)
            first_date = (rec.get("first_date_utc") or "").strip()

            # Prefer semantic family via classifier on first_line
            match = classify_telegram_skin(first_line or type_id)
            fid = match.family_id
            mapped = fid not in {"UNKNOWN", "EMPTY"}
            role_u = (match.role if match.role != "UNKNOWN" else role or "UNKNOWN").upper()
            collapse_note = ""

            if not mapped and type_id:
                norm, collapse_note = _normalize_archaeology_type_id(type_id)
                if norm != type_id:
                    fid = norm
                    mapped = True
                    meta["collapsed_rows"] += 1
                    if fid.startswith("OPS_"):
                        role_u = "OPS"
                    elif fid.startswith("RESULT_"):
                        role_u = "RESULT"
                    elif fid.startswith("FIRE_"):
                        role_u = "FIRE"

            if mapped:
                meta["mapped_rows"] += 1
                r = _ensure(
                    rows,
                    fid,
                    role=role_u,
                    label=match.label if match.family_id == fid else fid,
                    seen_telegram=True,
                    tg_count=count,
                    tg_first_seen=first_date,
                    tg_example=first_line or match.first_line,
                    notes=collapse_note,
                )
                r.touch_source("TELEGRAM")
                # Keep clean named archaeology ids as sub-floors (not fingerprints)
                if (
                    type_id
                    and type_id != fid
                    and re.match(
                        r"^(FIRE_|RESULT_|CD_|ONLINE_|OPS_|RES_)", type_id
                    )
                    and not re.search(r"\d{5,}", type_id)
                    and not type_id.startswith("RESULT_BANNER_")
                    and not type_id.startswith("RESULT_GALE_")
                    and not re.match(r"^FIRE_JANELA_\d+S_", type_id)
                ):
                    # Kind-scoped results / classic named fires only
                    if (
                        re.match(r"^RESULT_(WIN|LOSS|EMPATE)_[A-Z0-9_]{2,40}$", type_id)
                        or re.match(
                            r"^FIRE_(SOLO_ELITE|GOLDEN|SEQUENCE|PLATINUM|FLASH|ULTRA|SIGNAL|GALE_1_|EMPATE|G0_|PREPARE)",
                            type_id,
                        )
                        or type_id.startswith("CD_")
                    ):
                        raw = _ensure(
                            rows,
                            type_id,
                            role=role or match.role,
                            label=type_id,
                            seen_telegram=True,
                            tg_count=count,
                            tg_first_seen=first_date,
                            tg_example=first_line,
                            notes=f"raw_named→{fid}",
                        )
                        raw.touch_source("TELEGRAM_NAMED")
            else:
                meta["unmapped_raw_ids"] += 1
                keep = False
                if type_id:
                    if re.match(r"^(FIRE_|CD_|ONLINE_)", type_id):
                        keep = True
                    elif re.match(r"^RESULT_(WIN|LOSS|EMPATE)_", type_id):
                        keep = True
                    elif role_u in {"FIRE", "ONLINE"} and count >= 1:
                        keep = True
                    elif role_u == "OPS" and count >= 5 and not type_id.startswith(
                        "UNKNOWN_"
                    ):
                        keep = True
                if keep:
                    r = _ensure(
                        rows,
                        type_id,
                        role=role_u,
                        label=type_id,
                        seen_telegram=True,
                        tg_count=count,
                        tg_first_seen=first_date,
                        tg_example=first_line,
                        notes="unmapped_telegram",
                    )
                    r.touch_source("TELEGRAM_UNMAPPED")
    return meta


def ingest_db(rows: Dict[str, FloorRow], db_path: Path) -> Dict[str, Any]:
    meta: Dict[str, Any] = {"path": str(db_path), "kinds": 0}
    if not db_path.exists():
        meta["error"] = "missing"
        return meta
    try:
        con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
    except Exception as exc:
        meta["error"] = repr(exc)
        return meta

    try:
        tables = {
            r[0]
            for r in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        meta["tables"] = sorted(tables)

        # Prefer consensus_signals; fall back to signals
        table = None
        for cand in ("consensus_signals", "signals"):
            if cand in tables:
                table = cand
                break
        if not table:
            meta["error"] = "no signals table"
            return meta

        cols = {
            r[1]
            for r in con.execute(f"PRAGMA table_info({table})").fetchall()
        }
        kind_col = "signal_kind" if "signal_kind" in cols else None
        if not kind_col:
            meta["error"] = "no signal_kind column"
            return meta

        outcome_expr = "outcome" if "outcome" in cols else "NULL"
        gale_expr = "won_at_gale" if "won_at_gale" in cols else "NULL"
        fired_expr = "fired_at" if "fired_at" in cols else "NULL"

        sql = f"""
            SELECT {kind_col} AS kind,
                   COUNT(*) AS n,
                   SUM(CASE WHEN {outcome_expr} IS NOT NULL AND TRIM(COALESCE({outcome_expr},''))!='' THEN 1 ELSE 0 END) AS with_outcome,
                   SUM(CASE WHEN UPPER(COALESCE({outcome_expr},'')) IN ('WIN','W','GREEN','G0','G1','G2','G3') THEN 1 ELSE 0 END) AS wins,
                   SUM(CASE WHEN CAST({gale_expr} AS TEXT) IN ('0','G0') OR UPPER(COALESCE({outcome_expr},'')) LIKE '%G0%' THEN 1 ELSE 0 END) AS g0,
                   MIN({fired_expr}) AS first_fired
            FROM {table}
            GROUP BY {kind_col}
            ORDER BY n DESC
        """
        family_for_kind = {
            "SOLO_ELITE": "FIRE_SOLO_ELITE_ENTER",
            "GOLDEN": "FIRE_GOLDEN_ENTER",
            "SEQUENCE": "FIRE_SEQUENCE_ENTER",
            "PLATINUM": "FIRE_PLATINUM_ENTER",
            "FLASH": "FIRE_FLASH_APOSTAR",
            "ULTRA_TIE": "FIRE_ULTRA_TIE",
            "EMERGING": "SIGNAL_KIND_EMERGING",
        }
        for rec in con.execute(sql):
            kind = (rec["kind"] or "(null)").strip().upper() or "(NULL)"
            n = int(rec["n"] or 0)
            with_outcome = int(rec["with_outcome"] or 0)
            wins = int(rec["wins"] or 0)
            g0 = int(rec["g0"] or 0)
            first_fired = str(rec["first_fired"] or "")
            kind_floor = _KIND_DB_ALIASES.get(kind, f"SIGNAL_KIND_{kind}")
            r = _ensure(
                rows,
                kind_floor,
                role="FIRE",
                label=kind_floor,
                in_db=True,
                db_fired=n,
                db_with_outcome=with_outcome,
                db_wins=wins,
                db_g0=g0,
                db_first_fired=first_fired,
                notes=f"db_kind={kind}",
            )
            r.touch_source("DB")
            fam = family_for_kind.get(kind)
            if fam and fam != kind_floor:
                fr = _ensure(
                    rows,
                    fam,
                    role="FIRE",
                    label=fam,
                    in_db=True,
                    notes=f"db_kind={kind}",
                )
                fr.touch_source("DB")
                fr.db_fired = max(fr.db_fired, n)
                fr.db_with_outcome = max(fr.db_with_outcome, with_outcome)
                fr.db_wins = max(fr.db_wins, wins)
                fr.db_g0 = max(fr.db_g0, g0)
                if first_fired and (
                    not fr.db_first_fired or first_fired < fr.db_first_fired
                ):
                    fr.db_first_fired = first_fired
            meta["kinds"] += 1
    finally:
        con.close()
    return meta


def score_and_band(row: FloorRow) -> None:
    """Provisional building rank. DB metrics preferred; else Telegram volume."""
    wr = 0.0
    if row.db_with_outcome > 0:
        wr = row.db_wins / row.db_with_outcome
    # Profit-ish score: G0 + 0.65*extra wins - losses proxy
    losses = max(0, row.db_with_outcome - row.db_wins)
    profitish = row.db_g0 + 0.65 * max(0, row.db_wins - row.db_g0) - losses
    vol = max(row.db_fired, row.tg_count)
    row.score = round(profitish * 10 + wr * 100 + min(vol, 5000) * 0.01, 3)

    sources = row.sources
    is_noise = (
        row.floor_id.startswith("RELAY_")
        or row.floor_id.startswith("UNKNOWN_")
        or row.floor_id.startswith("CYCLE_")
        or row.floor_id
        in {
            "ROOM_RELAY",
            "EMPTY",
            "UNKNOWN",
            "OPS_GATE_HEALTH_DUMP",
            "RESULT_BANNER_FAMILY",
            "OPS_ROOM_QUARANTINE",
            "OPS_DELIVERY_AUDIT",
            "OPS_MANUAL_RESULT_HINT",
        }
        or row.role in {"ROOM_RELAY", "EMPTY", "MEDIA"}
    )
    if is_noise:
        row.rank_band = "NOISE"
        return
    if row.created_in_code and not row.seen_telegram and not row.in_db:
        row.rank_band = "CREATED_ONLY"
        return
    if row.db_fired >= 500 and wr >= 0.75:
        row.rank_band = "PENTHOUSE"
    elif row.db_fired >= 100 or row.tg_count >= 500:
        row.rank_band = "UPPER"
    elif row.db_fired >= 10 or row.tg_count >= 50:
        row.rank_band = "MID"
    elif row.seen_telegram or row.in_db:
        row.rank_band = "BASEMENT"
    else:
        row.rank_band = "CREATED_ONLY"


def build_census(
    *,
    tg_csv: Optional[Path] = None,
    db_path: Optional[Path] = None,
    code_roots: Optional[List[Path]] = None,
) -> Dict[str, Any]:
    rows: Dict[str, FloorRow] = {}
    mine_registered_families(rows)
    roots = code_roots or [
        REPO / "bot",
        REPO / "replit_elite_stack_patch",
        REPO / "tests",
    ]
    mine_code_paths(rows, roots)

    tg_meta = {}
    tg_path = tg_csv or Path(
        os.environ.get("TG_TYPES_CSV", str(DEFAULT_TG_TYPES))
    )
    # Fallbacks
    if not tg_path.exists():
        for alt in (
            REPO / "replit_elite_stack_patch" / "tg_archaeology_partial_30k" / "types_first_seen.csv",
            REPO / "replit_elite_stack_patch" / "tg_archaeology_partial_ba19ss" / "types_first_seen.csv",
        ):
            if alt.exists():
                tg_path = alt
                break
    tg_meta = ingest_telegram_types_csv(rows, tg_path)

    db_meta = {}
    db = db_path or Path(os.environ.get("BACBO_DB", "bot/bacbo.db"))
    alts = [
        db,
        Path("bacbo.db"),
        REPO / "bot" / "bacbo.db",
        Path("/home/runner/workspace/bot/bacbo.db"),
    ]
    db_used = next((p for p in alts if p.exists()), None)
    if db_used:
        db_meta = ingest_db(rows, db_used)
    else:
        db_meta = {"error": "missing", "tried": [str(p) for p in alts]}

    for row in rows.values():
        score_and_band(row)

    ordered = sorted(
        rows.values(),
        key=lambda r: (
            {"PENTHOUSE": 0, "UPPER": 1, "MID": 2, "BASEMENT": 3, "CREATED_ONLY": 4, "NOISE": 5, "UNRANKED": 6}.get(
                r.rank_band, 9
            ),
            -r.score,
            -r.db_fired,
            -r.tg_count,
            r.floor_id,
        ),
    )

    bands: Dict[str, int] = defaultdict(int)
    roles: Dict[str, int] = defaultdict(int)
    for r in ordered:
        bands[r.rank_band] += 1
        roles[r.role] += 1

    product_floors = [
        r
        for r in ordered
        if r.rank_band not in {"NOISE"} and r.role in {"FIRE", "RESULT", "ONLINE", "OPS"}
    ]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "goal": (
            "Every signal skin/family/template ever created is a candidate building "
            "floor — ranked by volume/WR/G0/profit when known; never dropped from census."
        ),
        "sources": {
            "telegram": tg_meta,
            "db": db_meta,
            "registered_families": len(family_ids()),
            "code_roots": [str(p) for p in roots],
        },
        "totals": {
            "all_floors": len(ordered),
            "product_floors": len(product_floors),
            "created_in_code": sum(1 for r in ordered if r.created_in_code),
            "seen_telegram": sum(1 for r in ordered if r.seen_telegram),
            "in_db": sum(1 for r in ordered if r.in_db),
            "created_only_never_seen": sum(1 for r in ordered if r.rank_band == "CREATED_ONLY"),
            "by_band": dict(bands),
            "by_role": dict(roles),
        },
        "floors": [
            {
                **{k: (sorted(v) if k == "sources" else v) for k, v in asdict(r).items()},
            }
            for r in ordered
        ],
    }


def write_csv(census: Dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "rank_band",
        "score",
        "floor_id",
        "role",
        "label",
        "sources",
        "created_in_code",
        "registered_family",
        "seen_telegram",
        "in_db",
        "tg_count",
        "tg_first_seen",
        "db_fired",
        "db_with_outcome",
        "db_wins",
        "db_g0",
        "db_first_fired",
        "tg_example",
        "notes",
    ]
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for row in census["floors"]:
            out = dict(row)
            out["sources"] = "|".join(row.get("sources") or [])
            w.writerow(out)


def write_markdown(census: Dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    t = census["totals"]
    src = census["sources"]
    lines = [
        "# Skin Floor Census — Building Inventory",
        "",
        f"Generated: `{census['generated_at']}`",
        "",
        census["goal"],
        "",
        "## Totals",
        "",
        f"| Metric | n |",
        f"|---|---:|",
        f"| All floor candidates | **{t['all_floors']}** |",
        f"| Product floors (FIRE/RESULT/ONLINE/OPS, excl noise band) | **{t['product_floors']}** |",
        f"| Created in code / registered | {t['created_in_code']} |",
        f"| Seen in Telegram | {t['seen_telegram']} |",
        f"| Present in DB | {t['in_db']} |",
        f"| Created only (never seen TG/DB) | {t['created_only_never_seen']} |",
        "",
        "### By building band",
        "",
        "| Band | n | Meaning |",
        "|---|---:|---|",
        f"| PENTHOUSE | {t['by_band'].get('PENTHOUSE', 0)} | High DB volume + WR≥75% |",
        f"| UPPER | {t['by_band'].get('UPPER', 0)} | Strong volume (DB or TG) |",
        f"| MID | {t['by_band'].get('MID', 0)} | Moderate presence |",
        f"| BASEMENT | {t['by_band'].get('BASEMENT', 0)} | Seen but thin |",
        f"| CREATED_ONLY | {t['by_band'].get('CREATED_ONLY', 0)} | Built in code, never observed |",
        f"| NOISE | {t['by_band'].get('NOISE', 0)} | Room relay / empty / unknown dump |",
        "",
        "## Source coverage",
        "",
        f"- Telegram types CSV: `{src.get('telegram', {}).get('path')}` "
        f"(raw rows={src.get('telegram', {}).get('raw_type_rows', '?')})",
        f"- DB: `{src.get('db', {}).get('path', src.get('db'))}` "
        f"{'(missing — run on Replit / paste FETCH_URL)' if src.get('db', {}).get('error') else ''}",
        f"- Registered semantic families: {src.get('registered_families')}",
        "",
        "## Top product floors (non-noise)",
        "",
        "| Band | Floor id | Role | TG n | DB fired | Sources | Example |",
        "|---|---|---|---:|---:|---|---|",
    ]
    n = 0
    for row in census["floors"]:
        if row["rank_band"] == "NOISE":
            continue
        if row["role"] not in {"FIRE", "RESULT", "ONLINE", "OPS"} and not row[
            "registered_family"
        ]:
            # still show SIGNAL_KIND_* and CD_* product-ish
            if not (
                row["floor_id"].startswith("SIGNAL_KIND_")
                or row["floor_id"].startswith("CD_")
                or row["floor_id"].startswith("FIRE_")
                or row["floor_id"].startswith("RESULT_")
            ):
                continue
        ex = (row.get("tg_example") or "").replace("|", "\\|")[:60]
        lines.append(
            f"| {row['rank_band']} | `{row['floor_id']}` | {row['role']} | "
            f"{row['tg_count']} | {row['db_fired']} | "
            f"{','.join(row.get('sources') or [])} | {ex} |"
        )
        n += 1
        if n >= 80:
            break

    lines += [
        "",
        "## FIRE floors only (enter / follow-up skins)",
        "",
        "| Band | Floor id | TG n | DB fired | Sources |",
        "|---|---|---:|---:|---|",
    ]
    for row in census["floors"]:
        if row["role"] != "FIRE" or row["rank_band"] == "NOISE":
            continue
        lines.append(
            f"| {row['rank_band']} | `{row['floor_id']}` | {row['tg_count']} | "
            f"{row['db_fired']} | {','.join(row.get('sources') or [])} |"
        )

    lines += [
        "",
        "## How to read this",
        "",
        "- **Floor** = signal skin / family / template system (not only JUN19 engine configs).",
        "- **CREATED_ONLY** = existed in code/docs but never appeared in this TG/DB pass — still kept.",
        "- **DB missing** in cloud until Replit `bacbo.db` / DAY_ONE zip is uploaded.",
        "- Noise band collapses room placar / quarantine / gate-health dumps (still counted, not product floors).",
        "- Next: enrich DB metrics on Replit → re-rank PENTHOUSE→BASEMENT → assign chat shelves.",
        "",
        "## Reproduce",
        "",
        "```bash",
        "python3 -m bot.config.skin_census \\",
        "  --tg-csv /path/to/types_first_seen.csv \\",
        "  --db bot/bacbo.db \\",
        "  --out-json bot/data/skin_floor_census.json \\",
        "  --out-csv bot/data/skin_floor_census.csv \\",
        "  --out-md replit_elite_stack_patch/SKIN_FLOOR_CENSUS.md",
        "```",
        "",
        "Replit helper: `replit_elite_stack_patch/REPLIT_SKIN_FLOOR_CENSUS.sh`",
        "",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Skin/floor complete census")
    ap.add_argument("--tg-csv", type=Path, default=None)
    ap.add_argument("--db", type=Path, default=None)
    ap.add_argument("--out-json", type=Path, default=DEFAULT_OUT_JSON)
    ap.add_argument("--out-csv", type=Path, default=DEFAULT_OUT_CSV)
    ap.add_argument("--out-md", type=Path, default=DEFAULT_OUT_MD)
    args = ap.parse_args(argv)

    census = build_census(tg_csv=args.tg_csv, db_path=args.db)
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(census, indent=2, ensure_ascii=False) + "\n")
    write_csv(census, args.out_csv)
    write_markdown(census, args.out_md)

    t = census["totals"]
    print("SKIN_FLOOR_CENSUS")
    print(f"  all_floors={t['all_floors']} product={t['product_floors']}")
    print(f"  created_code={t['created_in_code']} tg={t['seen_telegram']} db={t['in_db']}")
    print(f"  bands={t['by_band']}")
    print(f"  json={args.out_json}")
    print(f"  csv={args.out_csv}")
    print(f"  md={args.out_md}")
    if census["sources"]["db"].get("error"):
        print("  NOTE: DB missing — upload bacbo.db / run REPLIT_SKIN_FLOOR_CENSUS.sh")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
