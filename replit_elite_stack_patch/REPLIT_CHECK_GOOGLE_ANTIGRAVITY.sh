#!/usr/bin/env bash
# Check Google / Gemini / Antigravity / Replit Agent artifacts on workspace.
# Run on Replit:
#   curl -fsSL -H 'Cache-Control: no-cache' -o CHECK_GOOGLE.sh \
#     'https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/cursor/add-engine-gate-registry-d5ba/replit_elite_stack_patch/REPLIT_CHECK_GOOGLE_ANTIGRAVITY.sh'
#   bash CHECK_GOOGLE.sh | tee google_antigravity_report.txt
set -euo pipefail
cd /home/runner/workspace 2>/dev/null || cd "$(dirname "$0")/.."

echo "========== GOOGLE / GEMINI / ANTIGRAVITY / AGENT CHECK $(date -u) =========="
echo "pwd=$(pwd) host=$(hostname 2>/dev/null || true)"

echo ""
echo "========== 1. TOP-LEVEL HIDDEN DIRS (AI / Google) =========="
for d in .gemini .agents .local .config .cache .replit; do
  if [ -d "$d" ]; then
    echo "--- $d ---"
    du -sh "$d" 2>/dev/null
    du -ah "$d" 2>/dev/null | sort -hr | head -25
  else
    echo "--- $d --- (missing)"
  fi
done

echo ""
echo "========== 2. SEARCH: antigravity | gemini | google | ghostwriter =========="
find . -xdev -type f \( \
  -iname '*antigravity*' -o -iname '*gemini*' -o -iname '*google*' \
  -o -iname '*ghostwriter*' -o -iname '*replit-agent*' \) \
  ! -path './node_modules/*' 2>/dev/null | while read -r f; do
  ls -lah "$f"
done | sort -k5 -hr | head -60

echo ""
echo "========== 3. SEARCH: inside path names =========="
find . -xdev \( \
  -path '*/.gemini/*' -o -path '*/.agents/*' \
  -o -path '*/workflow-logs/*' -o -path '*/.local/skills/*' \
  -o -path '*/scribe/*' \) -type f 2>/dev/null | while read -r f; do
  ls -lah "$f"
done | sort -k5 -hr | head -80

echo ""
echo "========== 4. .gemini/ FULL TREE (Google AI on Replit) =========="
if [ -d .gemini ]; then
  find .gemini -type f 2>/dev/null | head -200
  echo "--- text/json previews ---"
  find .gemini -type f \( -name '*.json' -o -name '*.txt' -o -name '*.md' -o -name '*.log' \) 2>/dev/null \
    | head -20 | while read -r f; do
      echo "===== $f ====="
      head -30 "$f" 2>/dev/null || true
    done
else
  echo "(no .gemini/ folder)"
fi

echo ""
echo "========== 5. .agents/ FULL TREE =========="
if [ -d .agents ]; then
  find .agents -type f 2>/dev/null | while read -r f; do ls -lah "$f"; done
  find .agents -type f 2>/dev/null | head -15 | while read -r f; do
    echo "===== $f ====="
    head -40 "$f" 2>/dev/null || true
  done
else
  echo "(no .agents/ folder)"
fi

echo ""
echo "========== 6. workflow-logs (shell/agent sessions) =========="
if [ -d .local/state/workflow-logs ]; then
  du -sh .local/state/workflow-logs
  find .local/state/workflow-logs -type f -size +100k 2>/dev/null | while read -r f; do ls -lah "$f"; done | sort -k5 -hr | head -20
else
  echo "(no workflow-logs)"
fi

echo ""
echo "========== 7. replit config =========="
for f in .replit replit.md .config/replit*; do
  [ -e "$f" ] && echo "--- $f ---" && head -50 "$f" 2>/dev/null
done

echo ""
echo "========== 8. PACK FOR UPLOAD (google+agent slice) =========="
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
PACK="bacbo_google_agent_${STAMP}"
mkdir -p "$PACK"
for d in .gemini .agents; do
  [ -d "$d" ] && cp -a "$d" "$PACK/" && echo "copied $d"
done
[ -d .local/state/workflow-logs ] && cp -a .local/state/workflow-logs "$PACK/workflow-logs" && echo "copied workflow-logs"
[ -d .local/skills ] && cp -a .local/skills "$PACK/skills" && echo "copied skills"
[ -d .local/state/scribe ] && cp -a .local/state/scribe "$PACK/scribe" && echo "copied scribe"
zip -r -q "${PACK}.zip" "$PACK" 2>/dev/null && ls -lah "${PACK}.zip" || echo "zip skipped"
echo "Upload ${PACK}.zip to Drive/YDRAY if non-empty"

echo ""
echo "========== DONE =========="
echo "Paste google_antigravity_report.txt in Cursor."
