#!/usr/bin/env bash
# Restore ALL bacbo/utils config imports (compiled *_RE) + runtime re-harden + restart.
#   curl -fsSL -o /tmp/FIXCFG.sh \
#     'https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/cursor/add-engine-gate-registry-d5ba/replit_elite_stack_patch/REPLIT_FIX_CONFIG_API_ID.sh?v=20260807f'
#   bash /tmp/FIXCFG.sh
set -euo pipefail
ROOT="${ROOT:-/home/runner/workspace}"
cd "$ROOT"
BRANCH="${BRANCH:-cursor/add-engine-gate-registry-d5ba}"
RAW="https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/${BRANCH}"
V="20260807f"

echo "========== FIX config + runtime *_RE harden =========="
mkdir -p bot/config
rm -rf bot/config/__pycache__ bot/__pycache__ 2>/dev/null || true

curl -fsSL -o bot/config/__init__.py "${RAW}/bot/config/__init__.py?v=${V}"
for f in skin_families.py registry.py chat_shelves.py chat_router.py \
         bundle_organizer.py result_essence_engine.py fire_result_law.py \
         profit_chat_bundle.py; do
  curl -fsSL -o "bot/config/${f}" "${RAW}/bot/config/${f}?v=${V}" || true
done
# Runtime harden — repairs signal_handler bindings after import
curl -fsSL -o bot/lux_re_harden.py "${RAW}/replit_elite_stack_patch/bot/lux_re_harden.py?v=${V}"
curl -fsSL -o bot/lux_send_config_bind.py "${RAW}/replit_elite_stack_patch/bot/lux_send_config_bind.py?v=${V}"
rm -rf bot/config/__pycache__ bot/__pycache__ 2>/dev/null || true

# Inject lux_re_harden into bacbo boot (idempotent) — runs after imports bind names
python3 - <<'PY'
from pathlib import Path
marker = "lux_re_harden"
block = """
try:
    import lux_re_harden  # noqa: F401
    print("[LUXURY] re-harden loaded")
except Exception as _lux_reh_exc:
    print("[LUXURY] re-harden skipped:", _lux_reh_exc)
"""
for p in [Path("bacbo_royal_complete.py"), Path("bot/bacbo_royal_complete.py")]:
    if not p.is_file():
        continue
    src = p.read_text(encoding="utf-8", errors="ignore")
    if marker in src:
        print("re-harden already injected in", p)
        continue
    # Prefer after send-config-bind block; else before run_forever / __main__
    anchor = None
    for a in (
        'print("[LUXURY] send-config-bind loaded")',
        "import lux_send_config_bind",
        'if __name__ == "__main__"',
        "run_forever()",
    ):
        if a in src:
            anchor = a
            break
    if anchor is None:
        src = src + "\n" + block + "\n"
        p.write_text(src, encoding="utf-8")
        print("appended re-harden to", p)
        continue
    idx = src.find(anchor)
    # insert after the line containing anchor
    nl = src.find("\n", idx)
    if nl < 0:
        nl = len(src)
    src = src[: nl + 1] + block + src[nl + 1 :]
    p.write_text(src, encoding="utf-8")
    print("injected re-harden into", p)
PY

python3 - <<'PY'
import re, sys
from pathlib import Path
sys.path.insert(0, "bot")
sys.path.insert(0, ".")
for mod in list(sys.modules):
    if mod == "config" or mod.startswith("config.") or mod in {"lux_re_harden", "utils"}:
        del sys.modules[mod]
import config
import lux_re_harden

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
for p in [Path("bacbo_royal_complete.py"), Path("bot/utils.py"), Path("bot/signal_handler.py")]:
    needed.extend(names_from(p))
seen=set(); needed=[n for n in needed if not (n in seen or seen.add(n))]
print("needed", len(needed), "names")
missing = [n for n in needed if n not in vars(config)]
if missing:
    print("MISSING_IN_DICT", missing)
    sys.exit(1)
ns = {}
exec("from config import " + ", ".join(needed), ns)
print("FROM_CONFIG_IMPORT_OK", len(needed))

bad_re = []
for n in needed:
    if n.endswith("_RE") or n.endswith("_REGEX") or n.endswith("_PATTERN"):
        v = getattr(config, n)
        if not hasattr(v, "search"):
            bad_re.append((n, type(v).__name__))
        elif n == "_WIN_STREAK_RE":
            m = v.search("💵 Estamos com 7 Greens seguidos!")
            print("_WIN_STREAK_RE sample", bool(m), (m.groupdict() if m else None))
if bad_re:
    print("BAD_RE_NOT_COMPILED", bad_re)
    sys.exit(1)
print("REGEX_IMPORT_OK", sum(1 for n in needed if n.endswith("_RE")))

# Simulate poisoned binding then harden
import types
fake = types.ModuleType("signal_handler")
fake._WIN_STREAK_RE = ""  # poison
sys.modules["signal_handler"] = fake
nfix, _ = lux_re_harden.apply(silent=False)
assert hasattr(fake._WIN_STREAK_RE, "search"), type(fake._WIN_STREAK_RE)
assert fake._WIN_STREAK_RE.search("7 Greens seguidos")
print("RE_HARDEN_POISON_TEST_OK", nfix)

try:
    if "utils" in sys.modules:
        del sys.modules["utils"]
    import utils  # type: ignore
    print("UTILS_IMPORT_OK")
except Exception as exc:
    print("UTILS_IMPORT_FAIL", repr(exc))
print("CONFIG_OK")
PY

pkill -f 'runtime_supervisor.py|bacbo_royal_complete.py|telegram_outbox.py' 2>/dev/null || true
rm -f bot/data/runtime_supervisor.lock bot/data/telegram_outbox.lock 2>/dev/null || true
sleep 1
BOOT_MARK="$(date -u '+%Y-%m-%d %H:%M:%S' 2>/dev/null || date '+%Y-%m-%d %H:%M:%S')"
nohup python3 -u bot/runtime_supervisor.py > /tmp/luxury_supervisor.log 2>&1 &
sleep 18
echo "---- procs ----"
pgrep -af 'runtime_supervisor|telegram_outbox|bacbo_royal' || true
echo "---- boot markers ----"
grep -E 're-harden|send-config-bind|all imports OK|Telegram connected|REGEX|CrashGuard' logs/bot_live.log 2>/dev/null | tail -n 40 || true
echo "---- CrashGuard AFTER this fix (should be empty / only old) ----"
# Show only lines after last 'all imports OK'
python3 - <<'PY'
from pathlib import Path
p = Path("logs/bot_live.log")
if not p.is_file():
    print("NO_LOG")
    raise SystemExit(0)
lines = p.read_text(encoding="utf-8", errors="ignore").splitlines()
last = -1
for i, ln in enumerate(lines):
    if "all imports OK" in ln or "re-harden loaded" in ln or "re-harden proof" in ln:
        last = i
post = lines[last+1:] if last >= 0 else lines[-30:]
hits = [ln for ln in post if "CrashGuard" in ln and "has no attribute 'search'" in ln]
print(f"post_boot_lines={len(post)} str_search_crashguard={len(hits)}")
for ln in hits[-5:]:
    print(ln)
if not hits:
    print("POST_BOOT_NO_STR_SEARCH_CRASH — good (wait for new room msgs to confirm)")
PY
echo "========== DONE =========="
echo "Honesty: ROI is not guaranteed. System maximizes honest window capture."
