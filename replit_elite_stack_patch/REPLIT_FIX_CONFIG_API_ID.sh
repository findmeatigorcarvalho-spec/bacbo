#!/usr/bin/env bash
# Restore ALL bacbo/utils config imports + restart supervisor.
#   curl -fsSL -o /tmp/FIXCFG.sh \
#     'https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/cursor/add-engine-gate-registry-d5ba/replit_elite_stack_patch/REPLIT_FIX_CONFIG_API_ID.sh?v=20260807c'
#   bash /tmp/FIXCFG.sh
set -euo pipefail
ROOT="${ROOT:-/home/runner/workspace}"
cd "$ROOT"
BRANCH="${BRANCH:-cursor/add-engine-gate-registry-d5ba}"
RAW="https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/${BRANCH}"
V="20260807c"

echo "========== FIX config (full bacbo+utils import surface) =========="
mkdir -p bot/config
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
for mod in list(sys.modules):
    if mod == "config" or mod.startswith("config."):
        del sys.modules[mod]
import config

print("API_ID", getattr(config, "API_ID", None))
print("TARGET", getattr(config, "TARGET", None))
print("SESSION_FILE", getattr(config, "SESSION_FILE", None))
print("COLOR", getattr(config, "_COLOR_ICON_SHORT", None))

def names_from(path: Path):
    if not path.is_file():
        return []
    src = path.read_text(encoding="utf-8", errors="ignore")
    out = []
    for m in re.finditer(r"from\s+config\s+import\s*\((.*?)\)", src, re.S):
        for part in m.group(1).split(","):
            part = part.split("#", 1)[0].strip()
            if " as " in part:
                part = part.split(" as ", 1)[-1].strip()
            if part.isidentifier():
                out.append(part)
    return out

needed = []
for p in [Path("bacbo_royal_complete.py"), Path("bot/utils.py")]:
    needed.extend(names_from(p))
# dedupe
seen=set(); needed=[n for n in needed if not (n in seen or seen.add(n))]
print("needed", needed)
missing = [n for n in needed if n not in vars(config)]
if missing:
    print("MISSING_IN_DICT", missing)
    sys.exit(1)
ns = {}
exec("from config import " + ", ".join(needed), ns)
print("FROM_CONFIG_IMPORT_OK", len(needed))
# utils import smoke
try:
    import importlib
    if "utils" in sys.modules:
        del sys.modules["utils"]
    import utils  # type: ignore
    print("UTILS_IMPORT_OK")
except Exception as exc:
    print("UTILS_IMPORT_FAIL", repr(exc))
    # not always fatal if utils path differs
print("CONFIG_OK")
PY

pkill -f 'runtime_supervisor.py|bacbo_royal_complete.py|telegram_outbox.py' 2>/dev/null || true
rm -f bot/data/runtime_supervisor.lock bot/data/telegram_outbox.lock 2>/dev/null || true
sleep 1
nohup python3 -u bot/runtime_supervisor.py > /tmp/luxury_supervisor.log 2>&1 &
sleep 10
echo "---- procs ----"
pgrep -af 'runtime_supervisor|telegram_outbox|bacbo_royal' || true
echo "---- bot_live log ----"
tail -n 50 logs/bot_live.log 2>/dev/null || true
echo "========== DONE =========="
echo "Honesty: ROI is not guaranteed. System maximizes honest window capture."
