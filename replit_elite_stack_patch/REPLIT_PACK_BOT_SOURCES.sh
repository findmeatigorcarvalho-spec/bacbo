#!/usr/bin/env bash
# Tiny pack — ONLY the live card formatters Cursor still needs.
# Inventory already merged from 16a5od.zip.
#
#   curl -fsSL -o PACK_SRC.sh \
#     "https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/cursor/add-engine-gate-registry-d5ba/replit_elite_stack_patch/REPLIT_PACK_BOT_SOURCES.sh?$(date +%s)"
#   bash PACK_SRC.sh
set -euo pipefail
cd /home/runner/workspace 2>/dev/null || cd "$(pwd)"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DIR="bot_sources_pack_${STAMP}"
mkdir -p "$DIR"

copy() {
  local f="$1"
  if [[ -f "$f" ]]; then
    mkdir -p "$DIR/$(dirname "$f")"
    cp -a "$f" "$DIR/$f"
    echo "OK $f ($(wc -c < "$f") bytes)"
    # backups next to it
    shopt -s nullglob
    for b in "$f".bak* "$f"~; do
      cp -a "$b" "$DIR/$(dirname "$f")/" 2>/dev/null || true
      echo "OK $b"
    done
    shopt -u nullglob
  else
    echo "MISSING $f"
  fi
}

copy bot/strings.py
copy bot/signal_handler.py
copy bot/telegram_outbox.py
copy bot/dual_lane_router.py
copy bot/fire_origin.py
copy bot/fallback_signal_sender.py
copy bot/fallback_result_sender.py
copy bot/countdown_alert.py
copy bot/lux_send_config_bind.py
copy bot/hub_engine_route.py

# gates list + a few peak gate files (full gates tree is large)
mkdir -p "$DIR/bot"
ls -1 bot/_gates_*.py 2>/dev/null | tee "$DIR/GATES_LIST.txt" | wc -l | tee "$DIR/GATES_COUNT.txt"
# copy gate sources (usually small enough)
cp -a bot/_gates_*.py "$DIR/bot/" 2>/dev/null || true

{
  echo "STAMP=$STAMP"
  echo "HAS_STRINGS=$([[ -f bot/strings.py ]] && echo YES || echo NO)"
  echo "HAS_SIGNAL_HANDLER=$([[ -f bot/signal_handler.py ]] && echo YES || echo NO)"
  echo "HAS_OUTBOX=$([[ -f bot/telegram_outbox.py ]] && echo YES || echo NO)"
  echo "STRINGS_BYTES=$(wc -c < bot/strings.py 2>/dev/null || echo 0)"
  echo "HANDLER_BYTES=$(wc -c < bot/signal_handler.py 2>/dev/null || echo 0)"
  echo "GATES_N=$(ls bot/_gates_*.py 2>/dev/null | wc -l)"
} | tee "$DIR/presence.txt"

ZIP="bacbo_bot_sources_${STAMP}.zip"
zip -qr "$ZIP" "$DIR"

FETCH=$(curl -fsS -F "reqtype=fileupload" -F "time=72h" -F "fileToUpload=@${ZIP}" \
  https://litterbox.catbox.moe/resources/internals/api.php 2>/dev/null || true)
if [[ -z "$FETCH" || "$FETCH" != http* ]]; then
  FETCH=$(curl -fsS -F "reqtype=fileupload" -F "fileToUpload=@${ZIP}" \
    https://catbox.moe/user/api.php 2>/dev/null || true)
fi
if [[ -z "$FETCH" || "$FETCH" != http* ]]; then
  FETCH=$(curl -fsS -F "file=@${ZIP}" https://0x0.st 2>/dev/null || true)
fi

echo "========== PASTE TO CURSOR =========="
echo "FETCH_URL=${FETCH:-LOCAL_ONLY:$(pwd)/$ZIP}"
echo "ZIP=$(pwd)/$ZIP"
cat "$DIR/presence.txt"
echo "====================================="
