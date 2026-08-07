#!/usr/bin/env bash
# Emergency: restore bacbo config exports (API_ID, SESSION_FILE, …) + restart.
#   curl -fsSL -o /tmp/FIXCFG.sh \
#     'https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/cursor/add-engine-gate-registry-d5ba/replit_elite_stack_patch/REPLIT_FIX_CONFIG_API_ID.sh?v=20260807b'
#   bash /tmp/FIXCFG.sh
set -euo pipefail
ROOT="${ROOT:-/home/runner/workspace}"
cd "$ROOT"
BRANCH="${BRANCH:-cursor/add-engine-gate-registry-d5ba}"
RAW="https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/${BRANCH}"
V="20260807b"

echo "========== FIX config API_ID + SESSION_FILE =========="
mkdir -p bot/config
# bust pycache so old __init__ cannot stick
rm -rf bot/config/__pycache__ 2>/dev/null || true
curl -fsSL -o bot/config/__init__.py "${RAW}/bot/config/__init__.py?v=${V}"
for f in skin_families.py registry.py chat_shelves.py chat_router.py \
         bundle_organizer.py result_essence_engine.py profit_chat_bundle.py; do
  curl -fsSL -o "bot/config/${f}" "${RAW}/bot/config/${f}?v=${V}" || true
done
rm -rf bot/config/__pycache__ 2>/dev/null || true

python3 - <<'PY'
import re, sys
from pathlib import Path
sys.path.insert(0, "bot")
sys.path.insert(0, ".")
# Force fresh import
for mod in list(sys.modules):
    if mod == "config" or mod.startswith("config."):
        del sys.modules[mod]
import config
print("API_ID", getattr(config, "API_ID", None))
print("API_HASH_set", bool(getattr(config, "API_HASH", None)))
print("TARGET", getattr(config, "TARGET", None))
print("SESSION_FILE", getattr(config, "SESSION_FILE", None))

bacbo = Path("bacbo_royal_complete.py")
needed = []
if bacbo.is_file():
    src = bacbo.read_text(encoding="utf-8", errors="ignore")
    m = re.search(r"from\s+config\s+import\s*\((.*?)\)", src, re.S)
    if m:
        for part in m.group(1).split(","):
            part = part.split("#", 1)[0].strip()
            if " as " in part:
                part = part.split(" as ", 1)[-1].strip()
            if part.isidentifier():
                needed.append(part)
print("bacbo_imports", needed)
missing = [n for n in needed if not hasattr(config, n)]
# Also force-attr via __getattr__ path
still = []
for n in missing:
    try:
        getattr(config, n)
    except Exception:
        still.append(n)
if still:
    print("MISSING", still)
    sys.exit(1)
# Smoke: from config import the bacbo list
if needed:
    ns = {}
    code = "from config import " + ", ".join(needed)
    exec(code, ns)
    print("FROM_CONFIG_IMPORT_OK", len(needed))
print("CONFIG_OK")
PY

pkill -f 'runtime_supervisor.py|bacbo_royal_complete.py|telegram_outbox.py' 2>/dev/null || true
rm -f bot/data/runtime_supervisor.lock bot/data/telegram_outbox.lock 2>/dev/null || true
sleep 1
nohup python3 -u bot/runtime_supervisor.py > /tmp/luxury_supervisor.log 2>&1 &
sleep 8
echo "---- procs ----"
pgrep -af 'runtime_supervisor|telegram_outbox|bacbo_royal' || true
echo "---- bot_live log ----"
tail -n 40 logs/bot_live.log 2>/dev/null || true
echo "========== DONE =========="
