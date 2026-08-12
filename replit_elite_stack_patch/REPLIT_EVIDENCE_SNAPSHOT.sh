#!/usr/bin/env bash
# Build a local, content-addressed Bac Bo evidence archive on Replit.
# No upload. No Telegram session/.env/secrets are included.
set -euo pipefail

ROOT="${ROOT:-/home/runner/workspace}"
cd "$ROOT"
PY="${PY:-python3}"
STAMP="$(TZ=America/New_York date +%Y%m%d_%H%M%S)"
OUT_DIR="$ROOT/exports/bacbo_evidence_${STAMP}_Pawtucket"
ARCHIVE="${OUT_DIR}.tar.gz"

mkdir -p "$OUT_DIR"/{db,derived,telegram,agent_history,reports,metadata}

echo "EVIDENCE SNAPSHOT — Pawtucket $(TZ=America/New_York date '+%Y-%m-%d %I:%M:%S %p %Z')"

# Consistent SQLite snapshot while the bot is live.
if [[ -f bot/bacbo.db ]]; then
  "$PY" - <<PY
import sqlite3
src = sqlite3.connect("file:bot/bacbo.db?mode=ro", uri=True, timeout=60)
dst = sqlite3.connect("${OUT_DIR}/db/bacbo.db")
src.backup(dst)
dst.execute("PRAGMA integrity_check")
dst.close()
src.close()
print("DB_SNAPSHOT_OK")
PY
else
  echo "DB_MISSING bot/bacbo.db" | tee "$OUT_DIR/reports/DB_MISSING.txt"
fi

# Generate current manifests/audits against the live evidence.
for script in build_evidence_manifest.py chronology_evidence.py chronology_integrity_audit.py \
              truth_verifier.py early_result_audit.py early_source_audit.py; do
  if [[ -f "bot/$script" ]]; then
    "$PY" "bot/$script" >"$OUT_DIR/reports/${script%.py}.stdout.txt" 2>&1 || true
  fi
done

# Derived catalogs and append-only ledgers. Never copy credentials.
for pattern in \
  'bot/data/*museum*.json' \
  'bot/data/*catalog*.json' \
  'bot/data/*audit*.json' \
  'bot/data/*truth*.json' \
  'bot/data/*ledger*.json' \
  'bot/data/*ledger*.jsonl' \
  'bot/data/*atlas*.json' \
  'bot/data/*census*.json' \
  'bot/data/signal_bundle_fire_msgs.json' \
  'bot/data/historical_evidence_manifest.json' \
  'bot/data/chronology_evidence_report.json' \
  'bot/data/chronology_integrity_audit.json'; do
  for file in $pattern; do
    [[ -f "$file" ]] || continue
    cp -p "$file" "$OUT_DIR/derived/"
  done
done

# Raw/partial Telegram archaeology exports, if present.
for dir in bot/data/tg_arch_final_snapshot tg_archaeology replit_elite_stack_patch/tg_archaeology_partial_*; do
  [[ -d "$dir" ]] || continue
  name="$(echo "$dir" | tr '/' '_')"
  mkdir -p "$OUT_DIR/telegram/$name"
  while IFS= read -r -d '' file; do
    rel="${file#"$dir"/}"
    mkdir -p "$OUT_DIR/telegram/$name/$(dirname "$rel")"
    cp -p "$file" "$OUT_DIR/telegram/$name/$rel"
  done < <(find "$dir" -type f \( -name '*.csv' -o -name '*.json' -o -name '*.txt' -o -name '*.md' \) -print0)
done

# Replit agent memory/history if available. Exclude binary state and credentials.
for dir in .agents/memory .agents; do
  [[ -d "$dir" ]] || continue
  name="$(echo "$dir" | tr '/' '_')"
  mkdir -p "$OUT_DIR/agent_history/$name"
  while IFS= read -r -d '' file; do
    rel="${file#"$dir"/}"
    mkdir -p "$OUT_DIR/agent_history/$name/$(dirname "$rel")"
    cp -p "$file" "$OUT_DIR/agent_history/$name/$rel"
  done < <(find "$dir" -type f \( -name '*.md' -o -name '*.txt' -o -name '*.json' \) -print0)
done

cat >"$OUT_DIR/metadata/ACCESS_BOUNDARIES.txt" <<'EOF'
Included only when present on this Replit workspace:
- bot/bacbo.db consistent SQLite backup
- derived museum/audit/truth/ledger artifacts
- Telegram archaeology CSV/JSON/TXT/MD
- Replit .agents text/JSON memory

Never included:
- .env
- .telegram_session_string
- Telegram/API credentials
- arbitrary personal chats outside supplied archaeology exports
- Cursor conversation history not exported into this workspace
EOF

(
  cd "$OUT_DIR"
  find . -type f ! -name SHA256SUMS -print0 \
    | sort -z \
    | xargs -0 sha256sum >SHA256SUMS
)

tar -czf "$ARCHIVE" -C "$(dirname "$OUT_DIR")" "$(basename "$OUT_DIR")"
sha256sum "$ARCHIVE" >"${ARCHIVE}.sha256"

echo "EVIDENCE_SNAPSHOT_OK"
echo "archive=$ARCHIVE"
echo "checksum=${ARCHIVE}.sha256"
echo "Download both files from Replit before changing/recovering primary stores."
