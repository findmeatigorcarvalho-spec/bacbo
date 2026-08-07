#!/usr/bin/env bash
# Typed config surface + runtime re/num harden + restart.
#   curl -fsSL -o /tmp/FIXCFG.sh \
# Prefer REPLIT_FIX_LIVE_NOW.sh?v=20260807h for full live repair.
#     'https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/cursor/add-engine-gate-registry-d5ba/replit_elite_stack_patch/REPLIT_FIX_CONFIG_API_ID.sh?v=20260807h'
#   bash /tmp/FIXCFG.sh
set -euo pipefail
ROOT="${ROOT:-/home/runner/workspace}"
cd "$ROOT"
BRANCH="${BRANCH:-cursor/add-engine-gate-registry-d5ba}"
RAW="https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/${BRANCH}"
V="20260807h"

echo "========== FIX config (typed knobs + regex/num harden) =========="
mkdir -p bot/config
rm -rf bot/config/__pycache__ bot/__pycache__ 2>/dev/null || true

curl -fsSL -o bot/config/__init__.py "${RAW}/bot/config/__init__.py?v=${V}"
for f in skin_families.py registry.py chat_shelves.py chat_router.py \
         bundle_organizer.py result_essence_engine.py fire_result_law.py \
         profit_chat_bundle.py; do
  curl -fsSL -o "bot/config/${f}" "${RAW}/bot/config/${f}?v=${V}" || true
done
curl -fsSL -o bot/lux_re_harden.py "${RAW}/replit_elite_stack_patch/bot/lux_re_harden.py?v=${V}"
curl -fsSL -o bot/lux_send_config_bind.py "${RAW}/replit_elite_stack_patch/bot/lux_send_config_bind.py?v=${V}"
curl -fsSL -o bot/hotfix_signal_handler.py "${RAW}/replit_elite_stack_patch/bot/hotfix_signal_handler.py?v=${V}" || true
rm -rf bot/config/__pycache__ bot/__pycache__ 2>/dev/null || true

# Apply _remaining hotfix if signal_handler present
if [[ -f bot/signal_handler.py && -f bot/hotfix_signal_handler.py ]]; then
  python3 bot/hotfix_signal_handler.py 2>/dev/null || true
fi

# Inject lux_re_harden into bacbo boot (idempotent)
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
        p.write_text(src + "\n" + block + "\n", encoding="utf-8")
        print("appended re-harden to", p)
        continue
    idx = src.find(anchor)
    nl = src.find("\n", idx)
    if nl < 0:
        nl = len(src)
    p.write_text(src[: nl + 1] + block + src[nl + 1 :], encoding="utf-8")
    print("injected re-harden into", p)
PY

python3 - <<'PY'
import re, sys, types
from pathlib import Path
sys.path.insert(0, "bot")
sys.path.insert(0, ".")
for mod in list(sys.modules):
    if mod == "config" or mod.startswith("config.") or mod in {"lux_re_harden", "utils", "signal_handler"}:
        del sys.modules[mod]
import config
import lux_re_harden

print("API_ID", getattr(config, "API_ID", None))
print("TARGET", getattr(config, "TARGET", None))
print("SESSION_FILE", getattr(config, "SESSION_FILE", None))
print("_ACCUM_HOLD_SECS", repr(config._ACCUM_HOLD_SECS), type(config._ACCUM_HOLD_SECS).__name__)
print("SOLO_LOSS_COOLDOWN", repr(config.SOLO_LOSS_COOLDOWN), type(config.SOLO_LOSS_COOLDOWN).__name__)

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

bad = []
for n in needed:
    v = getattr(config, n)
    if n.endswith("_RE") or n.endswith("_REGEX") or n.endswith("_PATTERN"):
        if not hasattr(v, "search"):
            bad.append((n, "not_re", type(v).__name__))
        elif n == "_WIN_STREAK_RE":
            m = v.search("💵 Estamos com 7 Greens seguidos!")
            print("_WIN_STREAK_RE sample", bool(m), (m.groupdict() if m else None))
    elif any(n.endswith(s) for s in (
        "_SECS","_SECONDS","_TIMEOUT","_INTERVAL","_THRESHOLD","_DURATION",
        "_WINDOW","_TTL","_DELAY","_PCT","_PROB","_RETRIES","_CYCLES","_EVERY",
        "_MSGS","_HOUR","_HOURS","_BUMP","_LOSSES","_REQUIRE","_LEN","_COOLDOWN",
        "_DRIFT","_MATCH","_RESULTS","_MIN","_MAX","_LIMIT",
    )) or n in {"SOLO_LOSS_COOLDOWN","RECONNECT_DELAY"}:
        if not isinstance(v, (int, float)) or isinstance(v, bool):
            bad.append((n, "not_num", type(v).__name__, repr(v)[:40]))
        else:
            try:
                _ = -float(v)
            except Exception as exc:
                bad.append((n, "unary_fail", repr(exc)))
if bad:
    print("BAD_TYPED_IMPORTS", bad)
    sys.exit(1)
print("TYPED_IMPORT_OK")

# Poison test: empty str bindings in signal_handler → harden repairs
fake = types.ModuleType("signal_handler")
fake._WIN_STREAK_RE = ""
fake._ACCUM_HOLD_SECS = ""
fake.SOLO_LOSS_COOLDOWN = ""
sys.modules["signal_handler"] = fake
nfix, _ = lux_re_harden.apply(silent=False)
assert hasattr(fake._WIN_STREAK_RE, "search")
assert isinstance(fake._ACCUM_HOLD_SECS, (int, float))
assert isinstance(fake.SOLO_LOSS_COOLDOWN, (int, float))
_ = -float(fake._ACCUM_HOLD_SECS)
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
sleep 2
nohup python3 -u bot/runtime_supervisor.py > /tmp/luxury_supervisor.log 2>&1 &
sleep 20
echo "---- procs ----"
PROCS="$(pgrep -af 'runtime_supervisor|telegram_outbox|bacbo_royal' || true)"
echo "$PROCS"
if ! echo "$PROCS" | grep -q bacbo_royal; then
  echo "WARN bacbo not up — supervisor log:"
  tail -n 40 /tmp/luxury_supervisor.log 2>/dev/null || true
  # one more kick
  nohup python3 -u bot/runtime_supervisor.py > /tmp/luxury_supervisor.log 2>&1 &
  sleep 15
  pgrep -af 'runtime_supervisor|telegram_outbox|bacbo_royal' || true
fi
echo "---- boot / harden markers ----"
grep -E 're-harden|all imports OK|Telegram connected|TYPED|CONFIG_OK' logs/bot_live.log 2>/dev/null | tail -n 30 || true
echo "---- CrashGuard AFTER last boot ----"
python3 - <<'PY'
from pathlib import Path
p = Path("logs/bot_live.log")
if not p.is_file():
    print("NO_LOG"); raise SystemExit(0)
lines = p.read_text(encoding="utf-8", errors="ignore").splitlines()
last = -1
for i, ln in enumerate(lines):
    if "all imports OK" in ln or "re-harden loaded" in ln or "re-harden proof" in ln:
        last = i
post = lines[last+1:] if last >= 0 else []
keys = ("has no attribute 'search'", "unary -", "concatenate str")
hits = [ln for ln in post if "CrashGuard" in ln and any(k in ln for k in keys)]
print(f"post_boot_lines={len(post)} typed_crashguard={len(hits)}")
for ln in hits[-8:]:
    print(ln)
if not hits:
    print("POST_BOOT_NO_TYPED_CRASH — good (confirm with new room msgs)")
PY
echo "========== DONE =========="
echo "Use ?v=20260807g — do not paste DONE lines as shell commands."
echo "Honesty: ROI is not guaranteed. System maximizes honest window capture."
