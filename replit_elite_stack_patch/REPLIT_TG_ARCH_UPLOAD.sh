#!/usr/bin/env bash
# Upload archaeology catalog to a public URL the cloud agent can fetch.
# Run anytime (mid-scrape or after) — does NOT need Telegram.
#
#   curl -fsSL -o TG_UP.sh \
#     'https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/fe2e879/replit_elite_stack_patch/REPLIT_TG_ARCH_UPLOAD.sh'
#   bash TG_UP.sh
#
# Then paste the FETCH_URL line here (one line). Agent pulls it.
set -euo pipefail
cd /home/runner/workspace 2>/dev/null || cd "$(pwd)"

OUT="${1:-tg_archaeology}"
if [[ ! -d "$OUT" ]]; then
  echo "FATAL: no $OUT/ — scrape hasn't written yet"
  exit 1
fi

# Prefer small catalog; include csv if present (may be large)
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
BUNDLE="tg_arch_catalog_${STAMP}"
mkdir -p "$BUNDLE"
for f in report.txt types_first_seen.csv eras_auto.md types_summary.json progress.json PASTE_ME.txt COVERAGE.txt; do
  [[ -f "$OUT/$f" ]] && cp -f "$OUT/$f" "$BUNDLE/" || true
done
# unknown_messages can be huge noise — cap at 15MB
if [[ -f "$OUT/unknown_messages.csv" ]]; then
  USZ=$(wc -c < "$OUT/unknown_messages.csv")
  if [[ "$USZ" -lt 15000000 ]]; then
    cp -f "$OUT/unknown_messages.csv" "$BUNDLE/"
  else
    echo "skip unknown_messages.csv (size=$USZ) — too large for upload hosts"
    echo "$USZ" > "$BUNDLE/unknown_messages.csv.SIZE_ONLY.txt"
    # keep only first-seen unknowns via types file
  fi
fi
# all_messages.csv can be huge — only include if under 40MB
if [[ -f "$OUT/all_messages.csv" ]]; then
  SZ=$(wc -c < "$OUT/all_messages.csv")
  echo "$SZ" > "$BUNDLE/all_messages.csv.SIZE_ONLY.txt"
  if [[ "$SZ" -lt 40000000 ]]; then
    cp -f "$OUT/all_messages.csv" "$BUNDLE/"
  else
    echo "skip all_messages.csv (size=$SZ > 40MB) — stays on Replit disk for --resume"
  fi
fi

if [[ -z "$(ls -A "$BUNDLE" 2>/dev/null)" ]]; then
  echo "FATAL: $OUT/ has no catalog files yet. Wait for first 'flushed' line."
  ls -la "$OUT" || true
  exit 2
fi

# Coverage gate (Mar 17 → today)
if [[ -f "$OUT/progress.json" ]]; then
  echo "=== coverage check ==="
  python3 - "$OUT/progress.json" <<'PY'
import json, sys
d = json.loads(open(sys.argv[1], encoding="utf-8").read())
print(json.dumps({k: d.get(k) for k in (
    "total", "oldest_date_utc", "newest_date_utc", "target_since", "coverage_complete_to_mar17"
)}, indent=2))
if not d.get("coverage_complete_to_mar17"):
    print("WARNING: NOT full Mar17→today yet.")
    print("Run: bash TG_ARCH.sh --resume  (do not Ctrl+C until oldest≤2026-03-17 and UNIQUE_g1 done)")
PY
fi

# Compact paste file for chat (progress + report only — not 849KB types dump)
{
  echo "TG_ARCH_CATALOG $STAMP"
  echo "files: $(ls "$BUNDLE" | tr '\n' ' ')"
  [[ -f "$BUNDLE/progress.json" ]] && echo "--- progress ---" && cat "$BUNDLE/progress.json"
  [[ -f "$BUNDLE/report.txt" ]] && echo "--- report ---" && head -n 200 "$BUNDLE/report.txt"
} > "$OUT/PASTE_ME.txt"
cp -f "$OUT/PASTE_ME.txt" "$BUNDLE/"

ZIP="${BUNDLE}.zip"
zip -r -q "$ZIP" "$BUNDLE"
ls -lah "$ZIP" "$BUNDLE"
echo ""
echo "=== uploading (so cloud agent can fetch without you pasting megabytes) ==="

URL=""
# try several hosts
try_up() {
  local name="$1"; shift
  local out
  echo "try $name ..."
  if out="$("$@" 2>/dev/null)" && [[ -n "$out" ]] && echo "$out" | grep -qE 'https?://'; then
    URL="$(echo "$out" | tr -d '\r' | grep -Eo 'https?://[^ ]+' | tail -n1)"
    echo "OK $name → $URL"
    return 0
  fi
  echo "fail $name"
  return 1
}

try_up "0x0.st" curl -fsS -F "file=@${ZIP}" https://0x0.st \
  || try_up "catbox" curl -fsS -F "reqtype=fileupload" -F "fileToUpload=@${ZIP}" https://catbox.moe/user/api.php \
  || try_up "litterbox" curl -fsS -F "reqtype=fileupload" -F "time=72h" -F "fileToUpload=@${ZIP}" https://litterbox.catbox.moe/resources/internals/api.php \
  || try_up "transfer.sh" curl -fsS --upload-file "$ZIP" "https://transfer.sh/$(basename "$ZIP")" \
  || true

if [[ -n "$URL" ]]; then
  echo "$URL" | tee "$OUT/FETCH_URL.txt"
  echo ""
  echo "=========================================="
  echo "FETCH_URL=$URL"
  echo "=========================================="
  echo "Paste ONLY that FETCH_URL line back in chat. Agent will download it."
else
  echo "AUTO-UPLOAD FAILED (egress/blocked)."
  echo "Fallback — paste this small file (not the full csv):"
  echo "  cat $OUT/PASTE_ME.txt"
  echo "Or download $ZIP from Replit files panel and drop the link here."
fi
