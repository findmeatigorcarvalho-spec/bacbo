#!/usr/bin/env bash
# V3 is retired (re-run caused IndentationError). This wrapper downloads+runs V4.
set -euo pipefail
cd /home/runner/workspace
SHA="${LUXURY_PATCH_SHA:-cursor/add-engine-gate-registry-d5ba}"
BASE="https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/${SHA}/replit_elite_stack_patch"
echo "NOTE: V3 retired → running V4 instead"
curl -fsSL -H "Cache-Control: no-cache" -o REPLIT_FIX_DB_LOCKED_V4.sh "$BASE/REPLIT_FIX_DB_LOCKED_V4.sh"
bash REPLIT_FIX_DB_LOCKED_V4.sh
