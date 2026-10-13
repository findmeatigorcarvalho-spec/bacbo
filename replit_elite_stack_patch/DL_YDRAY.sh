#!/usr/bin/env bash
# Download YDRAY full app — one-paste for Replit OR Cursor cloud.
#
#   curl -fsSL -H 'Cache-Control: no-cache' -o DL_YDRAY.sh \
#     'https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/cursor/add-engine-gate-registry-d5ba/replit_elite_stack_patch/download_ydray_full_app.sh'
#   YDRAY_URL='https://ydray.com/get/t/YOUR_ID' bash DL_YDRAY.sh
#
# Known expired (for reference only):
#   u17818127167255IdjZb8f932d8c217QL  — 7.4GB full app
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec bash "${SCRIPT_DIR}/download_ydray_full_app.sh" "$@"
