#!/usr/bin/env bash
# Download + extract the full Bac Bo Replit app from a YDRAY share link.
#
# Usage:
#   bash download_ydray_full_app.sh 'https://ydray.com/get/t/TRANSFER_ID'
#
# Or set env:
#   YDRAY_URL='https://ydray.com/get/t/u17818127167255IdjZb8f932d8c217QL' \
#   OUT_DIR=/workspace/full_app \
#   bash download_ydray_full_app.sh
set -euo pipefail

YDRAY_URL="${1:-${YDRAY_URL:-}}"
# Replit: /workspace is read-only — use cwd. Cloud agent: /workspace/full_app.
if [ -w /workspace ] 2>/dev/null; then
  OUT_DIR="${OUT_DIR:-/workspace/full_app}"
else
  OUT_DIR="${OUT_DIR:-$(pwd)/ydray_download}"
fi
COOKIES="${OUT_DIR}/.ydray.cookies"
ZIP="${OUT_DIR}/full_replit_app.zip"

if [ -z "$YDRAY_URL" ]; then
  echo "FATAL: pass YDRAY share URL as arg1 or set YDRAY_URL"
  exit 1
fi

TRANSFER_ID="$(printf '%s' "$YDRAY_URL" | sed -n 's|.*/get/t/\([^/?#]*\).*|\1|p')"
if [ -z "$TRANSFER_ID" ]; then
  echo "FATAL: could not parse transfer id from: $YDRAY_URL"
  exit 1
fi

mkdir -p "$OUT_DIR"
echo "========== [1/5] YDRAY transfer metadata =========="
META="$(curl -fsSL \
  -c "$COOKIES" -b "$COOKIES" \
  -H "Referer: $YDRAY_URL" \
  -H 'User-Agent: Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36' \
  "https://api.ydray.com/get/transfer/${TRANSFER_ID}")"
printf '%s\n' "$META" | python3 -m json.tool > "${OUT_DIR}/transfer.json"

python3 - <<'PY' "$OUT_DIR/transfer.json"
import json, sys
meta = json.load(open(sys.argv[1]))
err = meta.get("error") or ""
if err:
    raise SystemExit(f"YDRAY error: {err!r} — link expired or invalid. Re-export from Replit and upload a fresh share.")
files = meta.get("files") or []
if not files:
    raise SystemExit("No files in transfer metadata")
f = files[0]
print("fileName", f.get("fileName"))
print("size_bytes", f.get("size"))
print("idFile", f.get("idFile"))
print("hash", f.get("hash"))
print("until", f.get("until"))
open(sys.argv[1].replace("transfer.json", "file_meta.json"), "w").write(json.dumps(f, indent=2))
PY

ID_FILE="$(python3 -c "import json; print(json.load(open('${OUT_DIR}/transfer.json'))['files'][0]['idFile'])")"
FILE_HASH="$(python3 -c "import json; print(json.load(open('${OUT_DIR}/transfer.json'))['files'][0]['hash'])")"
FILE_NAME="$(python3 -c "import json; print(json.load(open('${OUT_DIR}/transfer.json'))['files'][0]['fileName'])")"

echo "========== [2/5] warm session (visit share page) =========="
curl -fsSL -c "$COOKIES" -b "$COOKIES" \
  -H 'User-Agent: Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36' \
  "$YDRAY_URL" -o "${OUT_DIR}/share.html" >/dev/null

API_URL="https://api.ydray.com/get/tf/${TRANSFER_ID}/${ID_FILE}/${FILE_HASH}"
echo "API_URL=$API_URL"

echo "========== [3/5] download (~multi-GB; resume supported) =========="
curl -fL --retry 4 --retry-delay 4 -C - \
  -c "$COOKIES" -b "$COOKIES" \
  -H "Referer: ${YDRAY_URL}" \
  -H 'User-Agent: Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36' \
  "$API_URL" -o "$ZIP"

ls -lah "$ZIP"
file "$ZIP" | head -1

echo "========== [4/5] extract =========="
EXTRACT="${OUT_DIR}/extracted"
rm -rf "$EXTRACT"
mkdir -p "$EXTRACT"
unzip -q "$ZIP" -d "$EXTRACT"
echo "EXTRACT=$EXTRACT"
find "$EXTRACT" -maxdepth 3 -type f \( -name 'bacbo_royal_complete.py' -o -name 'bacbo.db' \) -ls

echo "========== [5/5] symlink into workspace =========="
ROOT="$(find "$EXTRACT" -maxdepth 4 -name 'bacbo_royal_complete.py' -print -quit | xargs -r dirname)"
if [ -n "$ROOT" ]; then
  ln -sfn "$ROOT" /workspace/Bac-Bo-Watcher-live
  echo "LINKED /workspace/Bac-Bo-Watcher-live -> $ROOT"
else
  echo "WARN: bacbo_royal_complete.py not found under $EXTRACT"
fi

echo "DONE download_ydray_full_app.sh"
