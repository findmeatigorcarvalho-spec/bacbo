#!/usr/bin/env bash
# Extract Replit Agent memory + agent chat state.
#   curl -fsSL -H 'Cache-Control: no-cache' -o EXTRACT_AGENT.sh \
#     'https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/cursor/add-engine-gate-registry-d5ba/replit_elite_stack_patch/REPLIT_EXTRACT_AGENT_HISTORY.sh'
#   bash EXTRACT_AGENT.sh | tee extract_agent_report.txt
set -euo pipefail
cd /home/runner/workspace 2>/dev/null || cd "$(dirname "$0")/.."

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="bacbo_agent_history_${STAMP}"
mkdir -p "$OUT"

echo "========== EXTRACT AGENT HISTORY $STAMP =========="
echo "NOTE: .gemini missing — Google Antigravity/Gemini chats are NOT inside this Replit workspace."
echo "What IS here: Replit Agent memory + .local/state/replit/agent"

echo ""
echo "========== .agents/memory (all files) =========="
if [ -d .agents/memory ]; then
  cp -a .agents "$OUT/"
  ls -lah .agents/memory/
  echo "--- MEMORY.md ---"
  cat .agents/memory/MEMORY.md 2>/dev/null || true
  echo "--- all memory filenames ---"
  ls -1 .agents/memory/
else
  echo "(no .agents/memory)"
fi

echo ""
echo "========== .local/state/replit/agent (chat/agent state) =========="
if [ -d .local/state/replit/agent ]; then
  du -sh .local/state/replit/agent
  du -ah .local/state/replit/agent 2>/dev/null | sort -hr | head -40
  cp -a .local/state/replit/agent "$OUT/replit_agent_state"
  find .local/state/replit/agent -type f \( -name '*.json' -o -name '*.md' -o -name '*.txt' -o -name '*.log' \) 2>/dev/null \
    | head -30 | while read -r f; do
      echo "===== $f ($(ls -lah -- "$f" | awk '{print $5}')) ====="
      head -c 2000 -- "$f" 2>/dev/null; echo
    done
else
  echo "(no .local/state/replit/agent)"
fi

echo ""
echo "========== workflow-logs index =========="
if [ -d .local/state/workflow-logs ]; then
  find .local/state/workflow-logs -type f 2>/dev/null | while read -r f; do ls -lah -- "$f"; done | sort -k5 -hr | head -30
  mkdir -p "$OUT/workflow-logs"
  # Paths can start with '-' — always use -- and relative copy via python for safety
  python3 - "$OUT" <<'PY'
import shutil, sys
from pathlib import Path
out = Path(sys.argv[1]) / "workflow-logs"
src = Path(".local/state/workflow-logs")
if not src.is_dir():
    raise SystemExit(0)
n = 0
for f in src.rglob("*"):
    if not f.is_file():
        continue
    if f.stat().st_size > 50 * 1024 * 1024:
        print(f"SKIP_LARGE {f} {f.stat().st_size}")
        continue
    rel = f.relative_to(src)
    dest = out / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(f, dest)
    n += 1
print(f"copied_workflow_logs={n}")
PY
fi

echo ""
echo "========== pack zip =========="
zip -r -q -- "${OUT}.zip" "$OUT"
ls -lah -- "${OUT}.zip"
ln -sfn -- "${OUT}.zip" bacbo_agent_history.zip
echo "Upload: $(pwd)/${OUT}.zip"
echo "Also: $(pwd)/bacbo_agent_history.zip"
echo "DONE"
