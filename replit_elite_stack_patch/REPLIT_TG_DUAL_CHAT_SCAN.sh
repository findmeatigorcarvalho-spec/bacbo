#!/usr/bin/env bash
# Dual-chat Telegram scan: Mr_iv4 + UNIQUE_g1 — fully self-bootstrapping.
# No local replit_elite_stack_patch/ files required.
#
#   curl -fsSL -o /tmp/TG_DUAL.sh \
#     'https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/cursor/add-engine-gate-registry-d5ba/replit_elite_stack_patch/REPLIT_TG_DUAL_CHAT_SCAN.sh?v=20260804b'
#   bash /tmp/TG_DUAL.sh
#   bash /tmp/TG_DUAL.sh --resume
#
# Paste the printed FETCH_URL= back in chat.
set -euo pipefail
cd /home/runner/workspace 2>/dev/null || cd "$(pwd)"

BRANCH="${BACBO_BRANCH:-cursor/add-engine-gate-registry-d5ba}"
RAW="https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/${BRANCH}/replit_elite_stack_patch"
VER="20260804b"

echo "DUAL_CHAT_SCAN cwd=$(pwd) branch=${BRANCH}"

export TELEGRAM_TARGET_PEER="${TELEGRAM_TARGET_PEER:-6774605259}"
export TELEGRAM_COUNTDOWN_PEER="${TELEGRAM_COUNTDOWN_PEER:-UNIQUE_g1}"
export TELEGRAM_ARCH_PEERS="${TELEGRAM_ARCH_PEERS:-6774605259,UNIQUE_g1,Mr_iv4,@UNIQUE_g1}"
export SINCE_ISO="${SINCE_ISO:-2026-03-17T00:00:00+00:00}"
export OUT="${OUT:-tg_archaeology_dual}"
mkdir -p "$OUT"

# ── fetch helpers from GitHub (Replit disk often lacks the patch folder) ──
fetch() {
  local name="$1" dest="$2"
  echo "fetch ${name} → ${dest}"
  curl -fsSL -o "$dest" "${RAW}/${name}?v=${VER}"
  chmod +x "$dest"
}

ARCH="/tmp/TG_ARCH_DUAL.sh"
UP="/tmp/TG_UP_DUAL.sh"
fetch "REPLIT_TELEGRAM_TYPE_ARCHAEOLOGY.sh" "$ARCH"
fetch "REPLIT_TG_ARCH_UPLOAD.sh" "$UP"

ARGS=()
if [[ "${1:-}" == "--resume" ]]; then
  ARGS+=(--resume)
fi

echo "Running archaeology peers=${TELEGRAM_ARCH_PEERS} out=${OUT}"
# Archaeology must honor OUT= (fixed on branch to use ${OUT:-tg_archaeology})
bash "$ARCH" "${ARGS[@]+"${ARGS[@]}"}"

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
            chat = row.get("chat") or row.get("peer") or "?"
            counts[chat] += 1
            roles[f"{chat}|{row.get('role') or '?'}"] += 1
    (OUT / "per_chat_counts.json").write_text(
        json.dumps({"by_chat": dict(counts), "by_chat_role": dict(roles)}, indent=2),
        encoding="utf-8",
    )
    print("per_chat_counts:", dict(counts))
else:
    print("WARN: all_messages.csv missing/small — types_first_seen only")
    (OUT / "per_chat_counts.json").write_text(
        json.dumps({"error": "no_all_messages", "hint": "check types_first_seen.csv + progress.json"}),
        encoding="utf-8",
    )
PY

# Cross-compare is optional on Replit (bot.config may be absent) — cloud does it after FETCH.
if python3 -c "import bot.config.tg_cross_compare" 2>/dev/null; then
  python3 - <<'PY'
from pathlib import Path
import os
from bot.config.tg_cross_compare import compare_types, write_report, _load_types
OUT = Path(os.environ["OUT"])
types = OUT / "types_first_seen.csv"
if types.exists():
    result = compare_types(_load_types(types))
    write_report(result, OUT / "cross_compare")
    print(
        f"CROSS product={result['product_looking_types']} "
        f"mapped={result['mapped_product_types']} "
        f"unmapped={result['unmapped_product_types']}"
    )
else:
    print("WARN: no types_first_seen.csv yet")
PY
else
  echo "SKIP cross-compare on Replit (bot.config not present) — cloud will compare after FETCH_URL"
fi

echo "Uploading catalog from ${OUT} ..."
bash "$UP" "$OUT" || true

echo "DONE dual scan → $OUT"
echo "Paste the FETCH_URL= line above back in chat."
