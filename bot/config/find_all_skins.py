#!/usr/bin/env python3
"""Find LITERALLY every signal skin / template / kind ever created.

Sources (union — an item counts if present in ANY):
  A. Live code + backups (*.py, *.bak*, *.py.bak, strings, formatters)
  B. Git history blobs (deleted templates still recoverable as text)
  C. SQLite: signal_kind + any card_type/template/skin columns + sample texts
  D. Telegram archaeology types_first_seen.csv
  E. Existing registered skin_families + census

Output: bot/data/literally_everything_skins.json (+ .csv + .md)
Never drop a candidate — even n=1 / never-fired / CREATED_ONLY.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sqlite3
import subprocess
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple


REPO = Path(__file__).resolve().parents[1].parent  # …/bot/config → repo
DEFAULT_OUT = REPO / "bot" / "data" / "literally_everything_skins.json"

# Card-ish first lines / headers embedded in source
_HEADER_LINE = re.compile(
    r"""(?x)
    (?P<q>['"`])
    (?P<body>
      (?:
        [🏆💎💠📊⚡🔥🟢🔴🔵🟡⚪♻️🔁⏳⛔🛑⏰🔔✅❌➖🔐🔮🃏🎯🏛📋🕐]|
        (?:GOLDEN|SOLO\s*ELITE|SEQUENCE|PLATINUM|FLASH|ULTRA\s*TIE|EMERG)
        |
        (?:ENTER\s+NOW|APOSTAR\s+AGORA|JANELA|Sinal\s+Retido|
           RESUMIDO\s+FORENSE|G1\s+EXPIROU|G2\s+MISS|
           UserBot\s+ONLINE|LUXURY\s+OUTBOX|
           WIN\s*—|LOSS\s*—|EMPATE\s*—|GANHOU|PERDEU|
           SIGNAL\s*\#|CAMADAS\s+DO\s+DIA|QUANTUM\s+LOCK)
      )
      .{0,160}
    )
    (?P=q)
    """
)

_ID_TOKEN = re.compile(
    r"\b("
    r"FIRE_[A-Z0-9_]{3,}|"
    r"RESULT_[A-Z0-9_]{3,}|"
    r"CD_FIRE_[A-Z0-9_]{3,}|"
    r"CD_RES_[A-Z0-9_]{3,}|"
    r"RES_[A-Z0-9_]{3,}|"
    r"ONLINE_[A-Z0-9_]{3,}|"
    r"OPS_[A-Z0-9_]{3,}|"
    r"NORMAL_SIGNAL_FIRE|NORMAL_RESULT|COUNTDOWN_SIGNAL_FIRE|COUNTDOWN_RESULT|"
    r"SOLO_ELITE|GOLDEN|SEQUENCE|PLATINUM|FLASH|ULTRA_TIE|EMERGING|EMERGINDO"
    r")\b"
)

_SKIP_DIR = {
    ".git",
    "__pycache__",
    "node_modules",
    "tg_archaeology_partial_30k",
    "tg_archaeology_partial_ba19ss",
    "recovery_probe",
    ".local",
    "venv",
    ".venv",
}

_SKIP_NAME_FRAG = (
    "skin_floor_census",
    "literally_everything",
    "types_first_seen.csv",
    "all_messages.csv",
    "unknown_messages.csv",
    "museum_chrono",
    "skyscraper_floor",
    "elite_stack_audit",
    "omni_score_report",
    "tg_archaeology",
)

# Header mining only from code-ish sources (JSON dumps create fake "templates")
_HEADER_EXTS = {".py", ".py.bak", ".bak", ".txt", ".jinja", ".j2", ".md"}


@dataclass
class Hit:
    key: str
    kind: str  # HEADER | TOKEN | DB_KIND | DB_TEXT | TG_TYPE | REGISTERED
    sources: Set[str] = field(default_factory=set)
    examples: List[str] = field(default_factory=list)
    files: Set[str] = field(default_factory=set)
    count_hint: int = 0
    notes: str = ""

    def add_example(self, ex: str, limit: int = 3) -> None:
        ex = (ex or "").replace("\n", " | ")[:180]
        if ex and ex not in self.examples and len(self.examples) < limit:
            self.examples.append(ex)


def _norm_key(raw: str) -> str:
    s = re.sub(r"\s+", " ", (raw or "").strip())
    s = s.strip("`\"'")
    if len(s) > 120:
        s = s[:120]
    return s


def _token_key(tok: str) -> str:
    t = tok.strip()
    if t in {
        "SOLO_ELITE",
        "GOLDEN",
        "SEQUENCE",
        "PLATINUM",
        "FLASH",
        "ULTRA_TIE",
        "EMERGING",
        "EMERGINDO",
    }:
        return f"SIGNAL_KIND_{t if t != 'EMERGINDO' else 'EMERGING'}"
    return t


def _ensure(hits: Dict[str, Hit], key: str, kind: str) -> Hit:
    k = _norm_key(key) or "EMPTY"
    h = hits.get(k)
    if h is None:
        h = Hit(key=k, kind=kind)
        hits[k] = h
    return h


def mine_filesystem(hits: Dict[str, Hit], roots: Iterable[Path]) -> Dict[str, Any]:
    meta = {"files_scanned": 0, "bytes": 0, "headers": 0, "tokens": 0}
    exts = {".py", ".py.bak", ".bak", ".txt", ".md", ".json", ".jinja", ".j2"}
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if any(p in _SKIP_DIR for p in path.parts):
                continue
            if any(frag in path.name for frag in _SKIP_NAME_FRAG):
                continue
            suf = path.suffix.lower()
            name = path.name.lower()
            ok = suf in exts or name.endswith(".py.bak") or ".bak" in name or name.endswith(".py~")
            if not ok:
                continue
            try:
                sz = path.stat().st_size
                if sz > 5_000_000:
                    continue
                text = path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            meta["files_scanned"] += 1
            meta["bytes"] += sz
            rel = str(path)
            allow_headers = suf in _HEADER_EXTS or ".bak" in name or name.endswith(".py~")

            if allow_headers:
                for m in _HEADER_LINE.finditer(text):
                    body = _norm_key(m.group("body"))
                    if len(body) < 6 or "\n" in body:
                        continue
                    # Drop format-string / dict noise
                    if "{" in body or "'," in body or '","' in body:
                        continue
                    h = _ensure(hits, f"HEADER::{body}", "HEADER")
                    h.sources.add("CODE")
                    h.files.add(rel)
                    h.add_example(body)
                    h.count_hint += 1
                    meta["headers"] += 1

            for m in _ID_TOKEN.finditer(text):
                tok = m.group(1)
                if tok.endswith("_") or len(tok) < 5:
                    continue
                if tok.startswith("FIRE_IF_") or tok.startswith("FIRE_IN_"):
                    continue
                key = _token_key(tok)
                h = _ensure(hits, key, "TOKEN")
                h.sources.add("CODE")
                h.files.add(Path(rel).name)
                h.count_hint += 1
                meta["tokens"] += 1
    return meta


def mine_git_history(hits: Dict[str, Hit], repo: Path) -> Dict[str, Any]:
    meta = {"ok": False, "blobs": 0, "hits": 0}
    git_dir = repo / ".git"
    if not git_dir.exists():
        # also try cwd parents /home/runner/workspace
        for alt in (Path("/home/runner/workspace"), Path.cwd()):
            if (alt / ".git").exists():
                repo = alt
                git_dir = alt / ".git"
                break
    if not git_dir.exists():
        meta["error"] = "no_git"
        return meta
    try:
        # Sample largest / recently touched python blobs mentioning SIGNAL/ENTER/JANELA
        proc = subprocess.run(
            ["git", "-C", str(repo), "rev-list", "--objects", "--all"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if proc.returncode != 0:
            meta["error"] = proc.stderr[:200]
            return meta
        candidates = []
        for line in proc.stdout.splitlines():
            parts = line.split(maxsplit=1)
            if len(parts) != 2:
                continue
            oid, path = parts[0], parts[1]
            if not re.search(r"\.(py|bak|txt|md)$", path, re.I):
                continue
            if re.search(
                r"(signal|string|telegram|outbox|template|card|gate|bacbo)",
                path,
                re.I,
            ):
                candidates.append((oid, path))
        candidates = candidates[:400]
        meta["blobs"] = len(candidates)
        for oid, path in candidates:
            show = subprocess.run(
                ["git", "-C", str(repo), "cat-file", "-p", oid],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if show.returncode != 0 or not show.stdout:
                continue
            text = show.stdout
            if len(text) > 2_000_000:
                continue
            for m in _HEADER_LINE.finditer(text):
                body = _norm_key(m.group("body"))
                h = _ensure(hits, f"HEADER::{body}", "HEADER")
                h.sources.add("GIT_HISTORY")
                h.files.add(f"git:{path}")
                h.add_example(body)
                meta["hits"] += 1
            for m in _ID_TOKEN.finditer(text):
                tok = m.group(1)
                if tok.endswith("_") or len(tok) < 5:
                    continue
                key = _token_key(tok)
                h = _ensure(hits, key, "TOKEN")
                h.sources.add("GIT_HISTORY")
                h.files.add(f"git:{Path(path).name}")
                meta["hits"] += 1
        meta["ok"] = True
    except Exception as exc:
        meta["error"] = repr(exc)
    return meta


def mine_db(hits: Dict[str, Hit], db_path: Path) -> Dict[str, Any]:
    meta: Dict[str, Any] = {"path": str(db_path), "kinds": 0, "text_rows": 0}
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
            )
        }
        meta["tables"] = sorted(tables)

        for table in ("consensus_signals", "signals", "blocked_signals", "oracle_signals"):
            if table not in tables:
                continue
            cols = {r[1] for r in con.execute(f"PRAGMA table_info({table})")}
            if "signal_kind" in cols:
                for rec in con.execute(
                    f"SELECT signal_kind AS k, COUNT(*) n FROM {table} GROUP BY signal_kind"
                ):
                    k = (rec["k"] or "(null)").strip().upper() or "(NULL)"
                    key = _token_key(k) if re.match(r"^[A-Z0-9_]+$", k) else f"DB_KIND_{k}"
                    h = _ensure(hits, key, "DB_KIND")
                    h.sources.add("DB")
                    h.count_hint += int(rec["n"] or 0)
                    h.notes = f"table={table}"
                    meta["kinds"] += 1

            # Distinct free-text card fields if present
            for col in (
                "card_text",
                "message_text",
                "signal_text",
                "template",
                "card_type",
                "skin",
                "outbox_text",
            ):
                if col not in cols:
                    continue
                try:
                    rows = con.execute(
                        f"SELECT {col} AS t, COUNT(*) n FROM {table} "
                        f"WHERE {col} IS NOT NULL AND TRIM({col})!='' "
                        f"GROUP BY {col} ORDER BY n DESC LIMIT 2000"
                    ).fetchall()
                except Exception:
                    continue
                for rec in rows:
                    t = str(rec["t"] or "")
                    first = next((ln.strip() for ln in t.splitlines() if ln.strip()), "")
                    if not first:
                        continue
                    # Classify-ish key from first line
                    key = f"DB_TEXT::{_norm_key(first)[:100]}"
                    h = _ensure(hits, key, "DB_TEXT")
                    h.sources.add("DB")
                    h.count_hint += int(rec["n"] or 0)
                    h.add_example(first)
                    h.files.add(f"db:{table}.{col}")
                    meta["text_rows"] += 1

        # channel_messages — sample distinct first lines if huge table exists
        if "channel_messages" in tables:
            cols = {r[1] for r in con.execute("PRAGMA table_info(channel_messages)")}
            text_col = next(
                (c for c in ("text", "message", "body", "content") if c in cols),
                None,
            )
            if text_col:
                try:
                    # Only grab rows that look like bot cards (limit cost)
                    rows = con.execute(
                        f"""
                        SELECT substr({text_col},1,200) AS t, COUNT(*) n
                        FROM channel_messages
                        WHERE {text_col} LIKE '%ENTER NOW%'
                           OR {text_col} LIKE '%APOSTAR%'
                           OR {text_col} LIKE '%JANELA%'
                           OR {text_col} LIKE '%FORENSE%'
                           OR {text_col} LIKE '%EXPIROU%'
                           OR {text_col} LIKE '%G2 MISS%'
                           OR {text_col} LIKE '%SOLO ELITE%'
                           OR {text_col} LIKE '%GOLDEN SIGNAL%'
                           OR {text_col} LIKE '%Sinal Retido%'
                           OR {text_col} LIKE '%WIN —%'
                           OR {text_col} LIKE '%EMPATE —%'
                        GROUP BY substr({text_col},1,200)
                        ORDER BY n DESC
                        LIMIT 5000
                        """
                    ).fetchall()
                    for rec in rows:
                        t = str(rec["t"] or "")
                        first = next(
                            (ln.strip() for ln in t.splitlines() if ln.strip()), ""
                        )
                        if not first:
                            continue
                        key = f"DB_MSG::{_norm_key(first)[:100]}"
                        h = _ensure(hits, key, "DB_TEXT")
                        h.sources.add("DB_CHANNEL")
                        h.count_hint += int(rec["n"] or 0)
                        h.add_example(first)
                        meta["text_rows"] += 1
                except Exception as exc:
                    meta["channel_messages_error"] = repr(exc)
    finally:
        con.close()
    return meta


def mine_telegram_csv(hits: Dict[str, Hit], csv_path: Path) -> Dict[str, Any]:
    meta = {"path": str(csv_path), "rows": 0}
    if not csv_path.exists():
        meta["error"] = "missing"
        return meta
    with csv_path.open("r", encoding="utf-8", errors="ignore", newline="") as fh:
        for rec in csv.DictReader(fh):
            meta["rows"] += 1
            tid = (rec.get("type_id") or "").strip()
            fl = (rec.get("first_line") or "").strip()
            role = (rec.get("role") or "").strip()
            n = int(float(rec.get("count") or 0) or 0)
            if tid:
                h = _ensure(hits, tid, "TG_TYPE")
                h.sources.add("TELEGRAM")
                h.count_hint += n
                h.add_example(fl)
                if role:
                    h.notes = f"role={role}"
            if fl:
                h2 = _ensure(hits, f"TG_LINE::{_norm_key(fl)[:100]}", "TG_TYPE")
                h2.sources.add("TELEGRAM")
                h2.count_hint += n
                h2.add_example(fl)
    return meta


def mine_registered(hits: Dict[str, Hit]) -> Dict[str, Any]:
    meta = {"n": 0}
    try:
        from bot.config.skin_families import SKIN_FAMILIES

        for fam in SKIN_FAMILIES:
            h = _ensure(hits, fam.family_id, "REGISTERED")
            h.sources.add("REGISTERED")
            h.add_example(fam.example_first_line)
            h.notes = f"role={fam.role};era={fam.era}"
            meta["n"] += 1
    except Exception as exc:
        meta["error"] = repr(exc)
    return meta


def build_inventory(
    *,
    roots: Optional[List[Path]] = None,
    db_path: Optional[Path] = None,
    tg_csv: Optional[Path] = None,
    repo: Optional[Path] = None,
) -> Dict[str, Any]:
    hits: Dict[str, Hit] = {}
    roots = roots or [
        Path("/home/runner/workspace"),
        Path("/home/runner/workspace/bot"),
        REPO / "bot",
        REPO / "replit_elite_stack_patch",
        Path.cwd(),
        Path.cwd() / "bot",
    ]
    # de-dupe existing roots
    seen_roots = []
    for r in roots:
        rp = r.resolve() if r.exists() else r
        if r.exists() and rp not in seen_roots:
            seen_roots.append(rp)

    meta = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "goal": "Literally every skin/template/kind ever created — union of all sources",
        "filesystem": mine_filesystem(hits, seen_roots),
        "git_history": mine_git_history(hits, repo or Path("/home/runner/workspace")),
        "registered": mine_registered(hits),
    }

    db = db_path
    if db is None:
        for cand in (
            Path("bot/bacbo.db"),
            Path("/home/runner/workspace/bot/bacbo.db"),
            Path("bacbo.db"),
            REPO / "bot" / "bacbo.db",
        ):
            if cand.exists():
                db = cand
                break
    meta["db"] = mine_db(hits, db) if db else {"error": "missing"}

    tg = tg_csv
    if tg is None:
        candidates: List[Path] = []
        for base in (
            Path("/tmp"),
            Path("/home/runner/workspace"),
            REPO,
            Path.cwd(),
        ):
            if not base.exists():
                continue
            try:
                candidates.extend(base.rglob("types_first_seen.csv"))
            except Exception:
                pass
        # Prefer the CSV with the most rows (fullest archaeology)
        best: Optional[Path] = None
        best_n = -1
        for cand in candidates:
            try:
                n = sum(1 for _ in cand.open("r", encoding="utf-8", errors="ignore"))
            except Exception:
                continue
            if n > best_n:
                best, best_n = cand, n
        tg = best
    meta["telegram"] = mine_telegram_csv(hits, tg) if tg else {"error": "missing"}

    # Summaries
    by_kind = defaultdict(int)
    by_source = defaultdict(int)
    for h in hits.values():
        by_kind[h.kind] += 1
        for s in h.sources:
            by_source[s] += 1

    ordered = sorted(
        hits.values(),
        key=lambda h: (-h.count_hint, h.kind, h.key),
    )

    return {
        **meta,
        "totals": {
            "unique_keys": len(ordered),
            "by_kind": dict(by_kind),
            "by_source": dict(by_source),
            "header_templates": by_kind.get("HEADER", 0),
            "tokens": by_kind.get("TOKEN", 0),
            "db_kinds": by_kind.get("DB_KIND", 0),
            "db_texts": by_kind.get("DB_TEXT", 0),
            "tg_types": by_kind.get("TG_TYPE", 0),
            "registered": by_kind.get("REGISTERED", 0),
        },
        "items": [
            {
                "key": h.key,
                "kind": h.kind,
                "sources": sorted(h.sources),
                "count_hint": h.count_hint,
                "examples": h.examples,
                "files": sorted(h.files)[:12],
                "notes": h.notes,
            }
            for h in ordered
        ],
    }


def _collapse_tg_floor_key(key: str) -> Optional[str]:
    """Map noisy TG type_ids → stable floor keys; None = drop from floors distill."""
    if key.startswith("TG_LINE::") or key.startswith("RELAY_"):
        return None
    if key in {"EMPTY"}:
        return None
    # Per-room quarantine / audit spam → family stubs
    if key.startswith("OPS_AUTO_QUARANTINE_"):
        return "OPS_AUTO_QUARANTINE"
    if key.startswith("OPS_QUARANTINE_ENDED_"):
        return "OPS_QUARANTINE_ENDED"
    if key.startswith("OPS_DELIVERY_AUDIT_"):
        return "OPS_DELIVERY_AUDIT"
    # UNKNOWN_* from archaeology = unclassified first-lines; keep high-signal names only
    if key.startswith("UNKNOWN_"):
        keep = (
            "UNKNOWN_SINAL_FORMANDO",
            "UNKNOWN_LOSS_COOLDOWN_ACTIVATED",
            "UNKNOWN_ELITE_ANALISANDO",
            "UNKNOWN_SEQU_NCIA_QUENTE",
            "UNKNOWN_SEQU_NCIA_FRIA",
            "UNKNOWN_GRADE_DE_JOGO",
            "UNKNOWN_COOLDOWN_CANCELLED",
            "UNKNOWN_DUPLO_ELITE",
            "UNKNOWN_TRIPLE_LOCK",
            "UNKNOWN_PREALERT",
            "UNKNOWN_JANELA",
            "UNKNOWN_SINAL_RETIDO",
            "UNKNOWN_QUANTUM",
            "UNKNOWN_FLASH",
            "UNKNOWN_PLATINUM",
            "UNKNOWN_ULTRA",
            "UNKNOWN_EMERG",
        )
        if any(key.startswith(p) for p in keep):
            return key
        return None
    if key.startswith(
        (
            "FIRE_",
            "RESULT_",
            "CD_FIRE_",
            "CD_RES_",
            "ONLINE_",
            "OPS_",
            "RES_",
            "SIGNAL_KIND_",
        )
    ) or key in {
        "NORMAL_SIGNAL_FIRE",
        "NORMAL_RESULT",
        "COUNTDOWN_SIGNAL_FIRE",
        "COUNTDOWN_RESULT",
    }:
        return key
    return None


def distill_floors(inv: Dict[str, Any]) -> Dict[str, Any]:
    """Building-relevant subset: ids + real card headers + TG FIRE/RESULT/CD/OPS families.

    Drops TG_LINE:: duplicates, room-relay spam, and unclassified UNKNOWN noise.
    Collapses per-room quarantine into family stubs. Keeps CREATED_ONLY code tokens.
    """
    merged: Dict[str, Dict[str, Any]] = {}

    def _merge(it: Dict[str, Any], key: str, kind: str) -> None:
        cur = merged.get(key)
        if cur is None:
            merged[key] = {
                "key": key,
                "kind": kind,
                "sources": list(it.get("sources") or []),
                "count_hint": int(it.get("count_hint") or 0),
                "examples": list(it.get("examples") or [])[:3],
                "files": list(it.get("files") or [])[:12],
                "notes": it.get("notes") or "",
            }
            return
        cur["count_hint"] += int(it.get("count_hint") or 0)
        for s in it.get("sources") or []:
            if s not in cur["sources"]:
                cur["sources"].append(s)
        for ex in it.get("examples") or []:
            if ex not in cur["examples"] and len(cur["examples"]) < 3:
                cur["examples"].append(ex)

    for it in inv["items"]:
        k = it["key"]
        kind = it["kind"]
        if kind in {"TOKEN", "REGISTERED", "DB_KIND", "HEADER", "DB_TEXT"}:
            _merge(it, k, kind)
            continue
        if kind != "TG_TYPE":
            continue
        nk = _collapse_tg_floor_key(k)
        if not nk:
            continue
        _merge(it, nk, "TG_TYPE")

    floors = sorted(
        merged.values(),
        key=lambda h: (-h["count_hint"], h["kind"], h["key"]),
    )
    by_kind: Dict[str, int] = defaultdict(int)
    by_source: Dict[str, int] = defaultdict(int)
    for it in floors:
        by_kind[it["kind"]] += 1
        for s in it["sources"]:
            by_source[s] += 1
    return {
        "generated_at": inv["generated_at"],
        "goal": "Distilled floors for the luxury building (union minus relay/TG_LINE/UNKNOWN noise)",
        "parent_totals": inv["totals"],
        "totals": {
            "unique_keys": len(floors),
            "by_kind": dict(by_kind),
            "by_source": dict(by_source),
        },
        "gaps": {
            "db": inv.get("db", {}).get("error"),
            "telegram": inv.get("telegram", {}).get("error"),
            "filesystem_files": inv.get("filesystem", {}).get("files_scanned"),
            "git_ok": inv.get("git_history", {}).get("ok"),
        },
        "items": floors,
    }


def write_csv(inv: Dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(
            fh,
            fieldnames=[
                "kind",
                "key",
                "count_hint",
                "sources",
                "example",
                "files",
                "notes",
            ],
        )
        w.writeheader()
        for it in inv["items"]:
            w.writerow(
                {
                    "kind": it["kind"],
                    "key": it["key"],
                    "count_hint": it["count_hint"],
                    "sources": "|".join(it["sources"]),
                    "example": (it["examples"][0] if it["examples"] else ""),
                    "files": "|".join(it["files"][:5]),
                    "notes": it["notes"],
                }
            )


def write_md(inv: Dict[str, Any], path: Path) -> None:
    t = inv["totals"]
    by_kind = t.get("by_kind") or {}
    lines = [
        "# Literally Everything — Skin / Template Inventory",
        "",
        f"Generated: `{inv['generated_at']}`",
        "",
        inv.get("goal") or "",
        "",
        "## Totals",
        "",
        f"| Metric | n |",
        f"|---|---:|",
        f"| Unique keys | **{t['unique_keys']}** |",
        f"| HEADER templates (quoted card lines in code/git) | {t.get('header_templates', by_kind.get('HEADER', 0))} |",
        f"| TOKEN ids (FIRE_/RESULT_/CD_/kinds) | {t.get('tokens', by_kind.get('TOKEN', 0))} |",
        f"| DB kinds | {t.get('db_kinds', by_kind.get('DB_KIND', 0))} |",
        f"| DB text first-lines | {t.get('db_texts', by_kind.get('DB_TEXT', 0))} |",
        f"| Telegram type_ids / lines | {t.get('tg_types', by_kind.get('TG_TYPE', 0))} |",
        f"| Registered families | {t.get('registered', by_kind.get('REGISTERED', 0))} |",
        "",
        f"Sources: `{t.get('by_source')}`",
        "",
        "## Gaps / honesty",
        "",
        "- If `db.error` or `telegram.error` → that source was missing on this host.",
        "- Cloud agents without full Replit `bot/` **cannot** see every formatter — run on Replit.",
        "- CREATED_ONLY / never-Telegram templates still appear via CODE + GIT_HISTORY.",
        "",
        "## Top HEADER templates",
        "",
        "| count | key | files |",
        "|---:|---|---|",
    ]
    n = 0
    for it in inv["items"]:
        if it["kind"] != "HEADER":
            continue
        lines.append(
            f"| {it['count_hint']} | `{it['key'][:90]}` | "
            f"{', '.join(it['files'][:3])} |"
        )
        n += 1
        if n >= 80:
            break
    lines += [
        "",
        "## All TOKEN / REGISTERED / DB_KIND ids",
        "",
        "| kind | key | count | sources |",
        "|---|---|---:|---|",
    ]
    for it in inv["items"]:
        if it["kind"] not in {"TOKEN", "REGISTERED", "DB_KIND"}:
            continue
        lines.append(
            f"| {it['kind']} | `{it['key']}` | {it['count_hint']} | "
            f"{','.join(it['sources'])} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, default=None)
    ap.add_argument("--tg-csv", type=Path, default=None)
    ap.add_argument("--repo", type=Path, default=None)
    ap.add_argument("--out-json", type=Path, default=DEFAULT_OUT)
    ap.add_argument(
        "--out-csv",
        type=Path,
        default=REPO / "bot" / "data" / "literally_everything_skins.csv",
    )
    ap.add_argument(
        "--out-md",
        type=Path,
        default=REPO / "replit_elite_stack_patch" / "LITERALLY_EVERYTHING_SKINS.md",
    )
    ap.add_argument(
        "--out-floors",
        type=Path,
        default=REPO / "bot" / "data" / "literally_everything_floors.json",
    )
    ap.add_argument(
        "--skip-full-json",
        action="store_true",
        help="Skip writing the multi-MB full union JSON (still writes floors/csv/md)",
    )
    args = ap.parse_args(argv)

    inv = build_inventory(db_path=args.db, tg_csv=args.tg_csv, repo=args.repo)
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    if not args.skip_full_json:
        args.out_json.write_text(json.dumps(inv, indent=2, ensure_ascii=False) + "\n")
    floors = distill_floors(inv)
    args.out_floors.parent.mkdir(parents=True, exist_ok=True)
    args.out_floors.write_text(json.dumps(floors, indent=2, ensure_ascii=False) + "\n")
    write_csv(floors, args.out_csv.with_name("literally_everything_floors.csv"))
    # Full CSV only if we kept full json path intent
    write_csv(inv, args.out_csv)
    write_md(inv, args.out_md)
    # Compact floors MD
    floors_md = args.out_md.with_name("LITERALLY_EVERYTHING_FLOORS.md")
    write_md({**floors, "goal": floors["goal"], "db": inv.get("db"), "telegram": inv.get("telegram")}, floors_md)
    t = inv["totals"]
    tf = floors["totals"]
    print("LITERALLY_EVERYTHING_SKINS")
    print(f"  unique_keys={t['unique_keys']}  floors_distilled={tf['unique_keys']}")
    print(f"  headers={t['header_templates']} tokens={t['tokens']} db_kinds={t['db_kinds']} tg={t['tg_types']}")
    print(f"  json={args.out_json} (skip={args.skip_full_json})")
    print(f"  floors={args.out_floors}")
    print(f"  csv={args.out_csv}")
    print(f"  md={args.out_md}")
    if inv.get("db", {}).get("error"):
        print("  NOTE: DB missing on this host — run REPLIT_FIND_ALL_SKINS.sh")
    if inv.get("telegram", {}).get("error"):
        print("  NOTE: Telegram types CSV missing on this host")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
