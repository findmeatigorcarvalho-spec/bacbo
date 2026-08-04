#!/usr/bin/env bash
# UNIQUE_g1-only Telegram scan — does NOT re-scrape Mr_iv4.
# We already have the Mar17→Aug3 Mr_iv4 archaeology (537k). This only fills
# true Gunique volume + any new types that first appeared there.
#
#   curl -fsSL -o /tmp/TG_G1.sh \
#     'https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/cursor/add-engine-gate-registry-d5ba/replit_elite_stack_patch/REPLIT_TG_GUNIQUE_ONLY.sh?v=20260804d'
#   bash /tmp/TG_G1.sh
#   # if mid-run died:
#   bash /tmp/TG_G1.sh --resume
#
# Ctrl+C any full dual/mr_iv4 re-scrape — not needed.
set -euo pipefail
cd /home/runner/workspace 2>/dev/null || cd "$(pwd)"

REF="${BACBO_REF:-818b304}"
RAW="https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/${REF}/replit_elite_stack_patch"
VER="20260804d"

echo "GUNIQUE_ONLY_SCAN cwd=$(pwd) ref=${REF}"
echo "NOTE: skipping Mr_iv4 — already inventoried (537k Mar17→Aug3)."

export TELEGRAM_TARGET_PEER="${TELEGRAM_COUNTDOWN_PEER:-UNIQUE_g1}"
export TELEGRAM_COUNTDOWN_PEER="${TELEGRAM_COUNTDOWN_PEER:-UNIQUE_g1}"
# Peers list: ONLY Gunique (no 6774605259 / Mr_iv4)
export TELEGRAM_ARCH_PEERS="UNIQUE_g1"
export TELEGRAM_ARCHAEOLOGY_PEERS="UNIQUE_g1"
# Clear money peer so archaeology resolve list doesn't force Mr_iv4 first…
# Archaeology hardcodes fallbacks including 6774605259 — override via env hack:
export TELEGRAM_TARGET_PEER="UNIQUE_g1"
export SINCE_ISO="${SINCE_ISO:-2026-03-17T00:00:00+00:00}"
export OUT="${OUT:-tg_archaeology_gunique}"
mkdir -p "$OUT"

ARCH="/tmp/TG_ARCH_G1.sh"
UP="/tmp/TG_UP_G1.sh"
curl -fsSL -o "$ARCH" "${RAW}/REPLIT_TELEGRAM_TYPE_ARCHAEOLOGY.sh?v=${VER}"
curl -fsSL -o "$UP" "${RAW}/REPLIT_TG_ARCH_UPLOAD.sh?v=${VER}"
chmod +x "$ARCH" "$UP"

# Patch archaeology in-place: remove hardcoded Mr_iv4 fallbacks for this run only.
python3 - <<'PY'
from pathlib import Path
p = Path("/tmp/TG_ARCH_G1.sh")
t = p.read_text(encoding="utf-8")
# Replace hard-coded peer fallbacks so ONLY UNIQUE_g1 is scraped.
old = '''    for d in ("6774605259", "UNIQUE_g1", "@UNIQUE_g1", "Mr_iv4", "@Mr_iv4"):
        if d not in peers:
            peers.append(d)'''
new = '''    # GUNIQUE-ONLY mode: do not append Mr_iv4 fallbacks.
    if not peers:
        peers.append("UNIQUE_g1")
    for d in ("UNIQUE_g1", "@UNIQUE_g1"):
        if d not in peers:
            peers.append(d)'''
if old not in t:
    # try looser match
    import re
    t2, n = re.subn(
        r'for d in \("6774605259".*?"@Mr_iv4"\):\n(?:.*\n){0,3}',
        'for d in ("UNIQUE_g1", "@UNIQUE_g1"):\n        if d not in peers:\n            peers.append(d)\n    if not peers:\n        peers.append("UNIQUE_g1")\n',
        t,
        count=1,
    )
    if n:
        t = t2
        print("patched peer fallbacks via regex")
    else:
        print("WARN: could not patch peer fallbacks — may still hit Mr_iv4")
else:
    t = t.replace(old, new)
    print("patched peer fallbacks (exact)")
p.write_text(t, encoding="utf-8")
PY

ARGS=()
if [[ "${1:-}" == "--resume" ]]; then
  ARGS+=(--resume)
fi

echo "Running UNIQUE_g1-only → OUT=${OUT}"
bash "$ARCH" "${ARGS[@]+"${ARGS[@]}"}"

python3 - <<'PY'
import csv, json, os
from collections import Counter
from pathlib import Path
OUT = Path(os.environ.get("OUT", "tg_archaeology_gunique"))
csv_path = OUT / "all_messages.csv"
counts = Counter()
if csv_path.exists() and csv_path.stat().st_size > 100:
    with csv_path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            counts[row.get("chat") or row.get("peer") or "?"] += 1
    (OUT / "per_chat_counts.json").write_text(
        json.dumps({"by_chat": dict(counts), "mode": "gunique_only"}, indent=2),
        encoding="utf-8",
    )
    print("per_chat_counts:", dict(counts))
else:
    print("WARN: no all_messages yet — progress/types still useful")
    (OUT / "per_chat_counts.json").write_text(
        '{"mode":"gunique_only","error":"no_all_messages"}', encoding="utf-8"
    )
PY

bash "$UP" "$OUT" || true
echo "DONE gunique-only → ${OUT}"
echo "Paste FETCH_URL= back in chat. (No need to re-scrape Mr_iv4.)"
