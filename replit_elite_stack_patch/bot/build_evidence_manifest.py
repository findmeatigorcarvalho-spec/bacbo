"""Inventory every locally accessible historical evidence source.

The manifest is deterministic and content-addressed.  It explicitly lists
unavailable sources rather than letting future agents assume they were scanned.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DATA = HERE / "data"
OUT = DATA / "historical_evidence_manifest.json"

PATTERNS = (
    "*museum*.json",
    "*audit*.json",
    "*truth*.json",
    "*ledger*.jsonl",
    "*catalog*.json",
    "*atlas*.json",
    "*census*.json",
    "*pairs*.json",
    "*.db",
)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _json_shape(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except Exception as exc:
        return {"parse_error": repr(exc)}
    if isinstance(data, list):
        return {"type": "list", "items": len(data)}
    if isinstance(data, dict):
        shape: dict[str, Any] = {"type": "object", "keys": sorted(data)[:80]}
        for key in (
            "items", "pairs", "keep", "trash", "families", "museum_candidates",
            "total_complete_pairs", "pre_stack_complete_pairs",
        ):
            value = data.get(key)
            if isinstance(value, (list, dict)):
                shape[f"{key}_count"] = len(value)
            elif value is not None:
                shape[key] = value
        if isinstance(data.get("stats"), dict):
            shape["stats"] = data["stats"]
        return shape
    return {"type": type(data).__name__}


def _jsonl_shape(path: Path) -> dict[str, Any]:
    lines = 0
    types: dict[str, int] = {}
    with path.open(encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            if not line.strip():
                continue
            lines += 1
            try:
                row = json.loads(line)
                kind = str(row.get("event_type") or row.get("type") or "?")
                types[kind] = types.get(kind, 0) + 1
            except Exception:
                types["PARSE_ERROR"] = types.get("PARSE_ERROR", 0) + 1
    return {"type": "jsonl", "rows": lines, "event_types": types}


def _db_shape(path: Path) -> dict[str, Any]:
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=20)
        tables = [
            r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
        ]
        counts = {}
        for table in tables:
            if not table.replace("_", "").isalnum():
                continue
            try:
                counts[table] = int(
                    conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
                )
            except Exception:
                pass
        conn.close()
        return {"type": "sqlite", "tables": tables, "row_counts": counts}
    except Exception as exc:
        return {"type": "sqlite", "parse_error": repr(exc)}


def build() -> dict[str, Any]:
    paths: set[Path] = set()
    for base in (DATA, ROOT / "bot" / "data", ROOT):
        if not base.exists():
            continue
        for pattern in PATTERNS:
            paths.update(p for p in base.glob(pattern) if p.is_file())

    sources = []
    for path in sorted(paths):
        rel = str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)
        if path.suffix == ".db":
            shape = _db_shape(path)
        elif path.suffix == ".jsonl":
            shape = _jsonl_shape(path)
        else:
            shape = _json_shape(path)
        sources.append(
            {
                "path": rel,
                "bytes": path.stat().st_size,
                "sha256": _sha256(path),
                "shape": shape,
            }
        )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "root": str(ROOT),
        "source_count": len(sources),
        "sources": sources,
        "access_boundaries": {
            "cursor_conversation_history": (
                "NOT_PRESENT_AS_A_COMPLETE_EXPORT_IN_WORKSPACE; requires an "
                "authorized product export or provided transcript."
            ),
            "replit_conversation_history": (
                "NOT_PRESENT_AS_A_COMPLETE_EXPORT_IN_WORKSPACE; requires an "
                "authorized Replit export or provided transcript."
            ),
            "telegram_account_history": (
                "PARTIAL_ARCHAEOLOGY_AND_CATALOG_PRESENT; a complete account scan "
                "must run on the authorized Telegram account and persist message IDs."
            ),
            "direct_casino_round_feed": (
                "SCHEMA_PRESENT; population measured in chronology report."
            ),
            "internet": (
                "Only relevant public/authorized sources can be ingested; the whole "
                "internet is neither a finite nor automatically authorized dataset."
            ),
        },
        "rule": (
            "A source is considered scanned only when it appears here with a content "
            "hash and shape/count metadata."
        ),
    }


def main() -> int:
    DATA.mkdir(parents=True, exist_ok=True)
    manifest = build()
    OUT.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        "EVIDENCE_MANIFEST_OK",
        f"sources={manifest['source_count']}",
        f"out={OUT}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
