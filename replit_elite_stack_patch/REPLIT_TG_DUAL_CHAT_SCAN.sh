#!/usr/bin/env bash
# Dual-chat Telegram scan: Mr_iv4 + UNIQUE_g1 (Gunique), then cross-compare
# every distinct landed type against bot.config.skin_families.
#
#   bash replit_elite_stack_patch/REPLIT_TG_DUAL_CHAT_SCAN.sh
#   bash replit_elite_stack_patch/REPLIT_TG_DUAL_CHAT_SCAN.sh --resume
#
# Forces both peers. Writes per_chat_counts.json so Gunique volume is visible
# (types_first_seen alone attributes duplicates to first-appearance chat).
set -euo pipefail
cd /home/runner/workspace 2>/dev/null || cd "$(dirname "$0")/.."

echo "DUAL_CHAT_SCAN cwd=$(pwd)"
export TELEGRAM_TARGET_PEER="${TELEGRAM_TARGET_PEER:-6774605259}"
export TELEGRAM_COUNTDOWN_PEER="${TELEGRAM_COUNTDOWN_PEER:-UNIQUE_g1}"
export TELEGRAM_ARCH_PEERS="${TELEGRAM_ARCH_PEERS:-6774605259,UNIQUE_g1,Mr_iv4,@UNIQUE_g1}"
export SINCE_ISO="${SINCE_ISO:-2026-03-17T00:00:00+00:00}"
export OUT="${OUT:-tg_archaeology_dual}"

# Prefer existing archaeology runner (full scrape + types_first_seen).
ARCH="replit_elite_stack_patch/REPLIT_TELEGRAM_TYPE_ARCHAEOLOGY.sh"
if [[ ! -f "$ARCH" ]]; then
  ARCH="REPLIT_TELEGRAM_TYPE_ARCHAEOLOGY.sh"
fi
if [[ ! -f "$ARCH" ]]; then
  echo "FATAL: archaeology script not found"
  exit 1
fi

# Patch OUT dir for this dual run
export OUT
mkdir -p "$OUT"

ARGS=()
if [[ "${1:-}" == "--resume" ]]; then
  ARGS+=(--resume)
fi

echo "Running archaeology peers=${TELEGRAM_ARCH_PEERS} out=${OUT}"
# Archaeology reads TELEGRAM_TARGET_PEER + hardcodes UNIQUE_g1; also honor TELEGRAM_ARCH_PEERS if patched.
bash "$ARCH" "${ARGS[@]:-}"

# Per-chat volume from all_messages.csv (if present)
python3 - <<'PY'
import csv, json, os
from collections import Counter
from pathlib import Path
OUT = Path(os.environ.get("OUT", "tg_archaeology_dual"))
csv_path = OUT / "all_messages.csv"
counts = Counter()
roles = Counter()
if csv_path.exists() and csv_path.stat().st_size > 100:
    with csv_path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            counts[row.get("chat") or row.get("peer") or "?"] += 1
            roles[(row.get("chat") or "?", row.get("role") or "?")] += 1
    (OUT / "per_chat_counts.json").write_text(
        json.dumps({"by_chat": dict(counts), "by_chat_role": {f"{a}|{b}": n for (a,b), n in roles.items()}}, indent=2),
        encoding="utf-8",
    )
    print("per_chat_counts:", dict(counts))
else:
    print("WARN: all_messages.csv missing/small — types_first_seen only")
    (OUT / "per_chat_counts.json").write_text('{"error":"no_all_messages"}', encoding="utf-8")
PY

# Cross-compare with skin registry (cloud module or local copy)
python3 - <<'PY'
import os, sys
from pathlib import Path
root = Path.cwd()
for p in (root, root / "replit_elite_stack_patch", Path("/workspace")):
    if (p / "bot" / "config" / "tg_cross_compare.py").is_file():
        sys.path.insert(0, str(p))
        break
from bot.config.tg_cross_compare import compare_types, write_report, _load_types
OUT = Path(os.environ.get("OUT", "tg_archaeology_dual"))
types = OUT / "types_first_seen.csv"
if not types.exists():
    raise SystemExit(f"missing {types}")
result = compare_types(_load_types(types))
write_report(result, OUT / "cross_compare")
print(
    f"CROSS product={result['product_looking_types']} "
    f"mapped={result['mapped_product_types']} "
    f"unmapped={result['unmapped_product_types']} "
    f"never_in_tg={result['registry_never_seen_count']}"
)
print("REPORT:", OUT / "cross_compare" / "TG_CROSS_COMPARE.md")
PY

# Upload helper if present
if [[ -f replit_elite_stack_patch/REPLIT_TG_ARCH_UPLOAD.sh ]]; then
  bash replit_elite_stack_patch/REPLIT_TG_ARCH_UPLOAD.sh "$OUT" || true
elif [[ -f REPLIT_TG_ARCH_UPLOAD.sh ]]; then
  bash REPLIT_TG_ARCH_UPLOAD.sh "$OUT" || true
fi

echo "DONE dual scan → $OUT (paste FETCH_URL= from upload)"
