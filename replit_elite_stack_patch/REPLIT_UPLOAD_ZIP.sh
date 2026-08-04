#!/usr/bin/env bash
# Re-upload an existing zip when catbox failed (LOCAL_ONLY).
#
#   bash REPLIT_UPLOAD_ZIP.sh /home/runner/workspace/bacbo_bot_sources_20260804T134549Z.zip
set -euo pipefail
ZIP="${1:-}"
if [[ -z "$ZIP" || ! -f "$ZIP" ]]; then
  # newest matching zip
  ZIP=$(ls -t /home/runner/workspace/bacbo_bot_sources_*.zip 2>/dev/null | head -1 || true)
fi
if [[ -z "${ZIP:-}" || ! -f "$ZIP" ]]; then
  echo "USAGE: bash REPLIT_UPLOAD_ZIP.sh /path/to.zip"
  echo "No bacbo_bot_sources_*.zip found"
  exit 1
fi
echo "UPLOADING $ZIP ($(du -h "$ZIP" | awk '{print $1}'))"

FETCH=""
try() {
  local name="$1"; shift
  local out
  out=$("$@" 2>/dev/null || true)
  if [[ -n "$out" && "$out" == http* ]]; then
    FETCH="$out"
    echo "OK via $name → $FETCH"
    return 0
  fi
  echo "FAIL $name → ${out:-empty}"
  return 1
}

try litterbox curl -fsS -F "reqtype=fileupload" -F "time=72h" -F "fileToUpload=@${ZIP}" \
  https://litterbox.catbox.moe/resources/internals/api.php \
  || try catbox curl -fsS -F "reqtype=fileupload" -F "fileToUpload=@${ZIP}" \
  https://catbox.moe/user/api.php \
  || try 0x0 curl -fsS -F "file=@${ZIP}" https://0x0.st \
  || try transfer curl -fsS --upload-file "$ZIP" "https://transfer.sh/$(basename "$ZIP")" \
  || try fileio curl -fsS -F "file=@${ZIP}" https://file.io \
  || true

echo "========== PASTE TO CURSOR =========="
echo "FETCH_URL=${FETCH:-UPLOAD_FAILED}"
echo "ZIP=$ZIP"
echo "====================================="
[[ -n "$FETCH" && "$FETCH" == http* ]]
