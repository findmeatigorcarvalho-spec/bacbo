#!/usr/bin/env bash
# Probe YDRAY transfers — metadata, recovery flags, direct-download attempts.
# Run on cloud agent OR Replit (needs curl + python3).
#
#   bash ydray_probe_all.sh
set -euo pipefail

OUT="${OUT_DIR:-/workspace/recovery_probe}"
mkdir -p "$OUT"

probe() {
  local name="$1" tid="$2" idfile="${3:-}" hash="${4:-}"
  echo ""
  echo "========== $name =========="
  echo "transfer=$tid"
  META="$(curl -fsSL \
    -H 'User-Agent: Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36' \
    -H "Referer: https://ydray.com/get/t/${tid}" \
    "https://api.ydray.com/get/transfer/${tid}" 2>&1)" || META='{"error":"curl_failed"}'
  printf '%s\n' "$META" | python3 -m json.tool > "${OUT}/${name}_transfer.json" 2>/dev/null || printf '%s\n' "$META" > "${OUT}/${name}_transfer.json"
  cat "${OUT}/${name}_transfer.json"

  if [ -n "$idfile" ] && [ -n "$hash" ]; then
    URL="https://api.ydray.com/get/tf/${tid}/${idfile}/${hash}"
    echo "direct_url=$URL"
    CODE="$(curl -sSL -o "${OUT}/${name}_head.bin" -w '%{http_code}' \
      -H 'User-Agent: Mozilla/5.0' \
      -H "Referer: https://ydray.com/get/t/${tid}" \
      -r 0-4095 "$URL" || true)"
    echo "http_range_0_4095=$CODE size=$(wc -c < "${OUT}/${name}_head.bin" 2>/dev/null || echo 0)"
    file "${OUT}/${name}_head.bin" 2>/dev/null || true
    head -c 4 "${OUT}/${name}_head.bin" 2>/dev/null | od -An -tx1 || true
    # PK\x03\x04 = zip
    if head -c 2 "${OUT}/${name}_head.bin" 2>/dev/null | grep -q 'PK'; then
      echo "LOOKS LIKE ZIP — transfer may still be downloadable with session cookies"
    fi
  fi
}

probe "full_app_7gb" \
  "u17818127167255IdjZb8f932d8c217QL" \
  "21051862" \
  "7e83b1446f704866377e1be327b6cc0b"

probe "messages_34mb" \
  "u1784507017063UBqg11e64279acc9Hc"

echo ""
echo "Results in $OUT"
echo "If full_app shows expired + non-zip head: need restored YDRAY link or PC copy."
echo "If messages shows recoverable:true — pay €2.99 recovery before 2026-08-06 for Telegram export."
