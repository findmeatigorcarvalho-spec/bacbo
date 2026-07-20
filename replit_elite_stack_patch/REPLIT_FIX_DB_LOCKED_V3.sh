#!/usr/bin/env bash
# Retired — redirects to FIX_NOW
set -euo pipefail
cd /home/runner/workspace
SHA="${LUXURY_PATCH_SHA:-cursor/add-engine-gate-registry-d5ba}"
BASE="https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/${SHA}/replit_elite_stack_patch"
echo "NOTE: old script retired → running FIX_NOW"
curl -fsSL -H "Cache-Control: no-cache" -o REPLIT_FIX_NOW.sh "$BASE/REPLIT_FIX_NOW.sh"
bash REPLIT_FIX_NOW.sh
