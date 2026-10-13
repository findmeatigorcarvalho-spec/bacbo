#!/usr/bin/env bash
# READ-ONLY. Answers one question against the live 4GB DB: does any system keep
# an edge once you only count signals that can be pinned to the round they named?
#
# Starts nothing. Sends nothing. Opens the DB with mode=ro and only writes a
# JSON report under bot/data.
#
#   curl -fsSL -o /tmp/EDGE.sh \
#     'https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/cursor/add-engine-gate-registry-d5ba/replit_elite_stack_patch/REPLIT_EDGE_TRUTH_CHECK.sh?v=20261013a'
#   bash /tmp/EDGE.sh
set -euo pipefail
ROOT="${ROOT:-/home/runner/workspace}"
cd "$ROOT"
PY="${PY:-python3}"
BRANCH="${BRANCH:-cursor/add-engine-gate-registry-d5ba}"
RAW="https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/${BRANCH}/replit_elite_stack_patch"
V="20261013a"
mkdir -p bot/data

echo "========== EDGE TRUTH CHECK ${V} =========="

for rel in bot/edge_truth_check.py bot/total_census.py; do
  if curl -fsSL --connect-timeout 20 --max-time 90 -o "$rel" "${RAW}/${rel}?v=${V}"; then
    echo "  OK   $rel"
  else
    echo "  FAIL $rel"
  fi
done

# Pick the largest bacbo.db on disk; the empty siblings have burned us before.
echo
echo "-- candidate DBs --"
DB=""
BEST=0
while IFS= read -r f; do
  sz=$(stat -c%s "$f" 2>/dev/null || echo 0)
  printf '  %12s  %s\n' "$sz" "$f"
  if [[ "$sz" -gt "$BEST" ]]; then BEST="$sz"; DB="$f"; fi
done < <(find . -name 'bacbo.db' -not -path './.git/*' 2>/dev/null)

if [[ -z "$DB" ]]; then
  echo "no bacbo.db found under $ROOT"
  exit 1
fi
echo "-- using: $DB ($BEST bytes) --"
echo

"$PY" bot/edge_truth_check.py --db "$DB" --report bot/data/edge_truth_check.json

echo
echo "-- row recency (is the engine producing anything?) --"
"$PY" - "$DB" <<'PYEOF'
import sqlite3, sys
conn = sqlite3.connect(f"file:{sys.argv[1]}?mode=ro", uri=True)
for label, sql in (
    ("rows total",      "SELECT COUNT(*) FROM consensus_signals"),
    ("max id",          "SELECT MAX(id) FROM consensus_signals"),
    ("newest fired_at", "SELECT MAX(fired_at) FROM consensus_signals"),
    ("last 30 min",     "SELECT COUNT(*) FROM consensus_signals WHERE fired_at >= datetime('now','-30 minutes')"),
    ("last 24 h",       "SELECT COUNT(*) FROM consensus_signals WHERE fired_at >= datetime('now','-1 day')"),
):
    try:
        print(f"  {label:<16}: {conn.execute(sql).fetchone()[0]}")
    except Exception as exc:
        print(f"  {label:<16}: ERR {exc}")
PYEOF

echo
echo "========== DONE — nothing was started or sent =========="
