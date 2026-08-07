#!/usr/bin/env bash
# One-shot: typed config + ESTUDO kill + bacbo stay-up + restart.
#   curl -fsSL -o /tmp/LIVE.sh \
#     'https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/cursor/add-engine-gate-registry-d5ba/replit_elite_stack_patch/REPLIT_FIX_LIVE_NOW.sh?v=20260807j'
#   bash /tmp/LIVE.sh
set -euo pipefail
ROOT="${ROOT:-/home/runner/workspace}"
cd "$ROOT"
BRANCH="${BRANCH:-cursor/add-engine-gate-registry-d5ba}"
RAW="https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/${BRANCH}"
V="20260807j"
PY="${PY:-python3}"

echo "========== FIX LIVE NOW (typed config + ESTUDO block + bacbo stay-up) =========="
mkdir -p bot/config bot/data logs
rm -rf bot/config/__pycache__ bot/__pycache__ 2>/dev/null || true

pull() {
  local dest="$1" url="$2"
  if curl -fsSL -o "$dest" "$url"; then
    echo "  OK  $dest"
  else
    echo "  FAIL $dest"
    return 1
  fi
}

echo "-- pull --"
pull bot/config/__init__.py "${RAW}/bot/config/__init__.py?v=${V}"
pull bot/config/keep_allowlist.py "${RAW}/bot/config/keep_allowlist.py?v=${V}"
pull bot/config/fire_result_law.py "${RAW}/bot/config/fire_result_law.py?v=${V}" || true
for f in lux_re_harden.py lux_send_config_bind.py runtime_supervisor.py telegram_outbox.py \
         hotfix_signal_handler.py hub_max_boot.py fix_bacbo_syntax.py; do
  pull "bot/${f}" "${RAW}/replit_elite_stack_patch/bot/${f}?v=${V}" || true
done
pull replit_elite_stack_patch/REPLIT_FIX_BACBO_SYNTAX.sh \
  "${RAW}/replit_elite_stack_patch/REPLIT_FIX_BACBO_SYNTAX.sh?v=${V}" || true
# Force env knobs
ENVF=bot/data/profit_skyscraper.env
touch "$ENVF"
for kv in \
  "FIRE_RESULT_LAW=1" \
  "RESULT_ATTACH_IMMEDIATE=1" \
  "HUB_OUTBOX_RESULT_CARDS=1" \
  "TELEGRAM_TRASH_BLOCK=1" \
  "TELEGRAM_SKIN_GATE=1" \
  "LUX_SEND_DEDUP_SECS=45" \
  "BACBO_READY_SECS=45" \
  "FALLBACK_START_DELAY_SECS=25" \
  "TELEGRAM_SINGLE_OUTBOX=1" \
  "TELEGRAM_PRIMARY_PEER=UNIQUE_g1" \
  "TELEGRAM_EXCLUDE_PEERS=Mr_iv4,6774605259"
do
  k="${kv%%=*}"
  if grep -q "^${k}=" "$ENVF" 2>/dev/null; then
    sed -i "s|^${k}=.*|${kv}|" "$ENVF"
  else
    echo "$kv" >> "$ENVF"
  fi
done
# luxury_building.env force keys used by supervisor
if [[ -f luxury_building.env ]]; then
  for kv in "BACBO_READY_SECS=45" "FALLBACK_START_DELAY_SECS=25" "TELEGRAM_SINGLE_OUTBOX=1"; do
    k="${kv%%=*}"
    if grep -qE "^(export )?${k}=" luxury_building.env 2>/dev/null; then
      sed -i -E "s|^(export )?${k}=.*|export ${kv}|" luxury_building.env
    else
      echo "export ${kv}" >> luxury_building.env
    fi
  done
fi

# CRITICAL: repair SyntaxError from prior mid-try injects (line ~725)
echo "-- fix bacbo syntax --"
$PY -u bot/fix_bacbo_syntax.py

if [[ -f bot/signal_handler.py && -f bot/hotfix_signal_handler.py ]]; then
  $PY bot/hotfix_signal_handler.py 2>/dev/null || true
fi

echo "-- smoke --"
$PY - <<'PY'
import sys, types
sys.path.insert(0, "bot"); sys.path.insert(0, ".")
for m in list(sys.modules):
    if m in {"config", "lux_re_harden", "lux_send_config_bind"} or m.startswith("config."):
        del sys.modules[m]
import config
import lux_re_harden
from bot.config.keep_allowlist import should_block_as_trash
assert isinstance(config._ACCUM_HOLD_SECS, (int, float))
assert hasattr(config._WIN_STREAK_RE, "search")
hit, why = should_block_as_trash(text="🔷 G2 ESTUDO | @robobacbodados\n🔵 BLUE G0")
assert hit, why
print("ESTUDO_BLOCK_OK", why)
print("TYPED_OK", config._ACCUM_HOLD_SECS, type(config.SOLO_LOSS_COOLDOWN).__name__)
# poison repair
fake = types.ModuleType("signal_handler")
fake._WIN_STREAK_RE = ""
fake._ACCUM_HOLD_SECS = ""
sys.modules["signal_handler"] = fake
lux_re_harden.apply(silent=True)
assert hasattr(fake._WIN_STREAK_RE, "search")
assert isinstance(fake._ACCUM_HOLD_SECS, (int, float))
print("HARDEN_OK")
# lux send filters
import lux_send_config_bind as lux
assert lux._estudo_blocked("🔷 G2 ESTUDO | @x")
assert not lux._estudo_blocked("💎 SOLO ELITE SIGNAL 💎\nENTER NOW")
print("SEND_FILTER_OK")
print("SMOKE_OK")
PY

# Mark log cut so we only judge NEW boot
MARK="===== LIVE_FIX_MARK $(date -u '+%Y-%m-%dT%H:%M:%SZ') ====="
echo "$MARK" >> logs/bot_live.log

pkill -f 'runtime_supervisor.py|bacbo_royal_complete.py|telegram_outbox.py' 2>/dev/null || true
rm -f bot/data/runtime_supervisor.lock bot/data/telegram_outbox.lock 2>/dev/null || true
sleep 2

# Direct bacbo probe (10s) to surface boot errors before supervisor loop
echo "-- bacbo probe (12s) --"
set +e
timeout 12 $PY -u bacbo_royal_complete.py > /tmp/bacbo_probe.log 2>&1
PROBE_EC=$?
set -e
echo "probe_exit=$PROBE_EC (124=timeout=still running=GOOD)"
tail -n 40 /tmp/bacbo_probe.log || true
# Kill probe if still running
pkill -f 'bacbo_royal_complete.py' 2>/dev/null || true
sleep 1

nohup $PY -u bot/runtime_supervisor.py > /tmp/luxury_supervisor.log 2>&1 &
sleep 35

echo "---- procs ----"
pgrep -af 'runtime_supervisor|telegram_outbox|bacbo_royal' || true

echo "---- NEW bot_live (after mark) ----"
$PY - <<PY
from pathlib import Path
p = Path("logs/bot_live.log")
text = p.read_text(encoding="utf-8", errors="ignore") if p.is_file() else ""
mark = "$MARK"
idx = text.rfind(mark)
chunk = text[idx + len(mark):] if idx >= 0 else text[-8000:]
lines = [ln for ln in chunk.splitlines() if ln.strip()]
print(f"new_lines={len(lines)}")
for ln in lines[-60:]:
    print(ln)
keys = ("has no attribute 'search'", "unary -", "concatenate str")
hits = [ln for ln in lines if "CrashGuard" in ln and any(k in ln for k in keys)]
print(f"NEW_typed_crashguard={len(hits)}")
for ln in hits[-5:]:
    print(ln)
if not hits:
    print("NEW_BOOT_NO_TYPED_CRASH — good")
PY

echo "---- supervisor ----"
tail -n 40 /tmp/luxury_supervisor.log || true

BACBO=$(pgrep -f 'bacbo_royal_complete.py' || true)
if [[ -z "${BACBO}" ]]; then
  echo "FAIL: bacbo still not up — see NEW bot_live + bacbo_probe.log"
  exit 1
fi
echo "BACBO_UP pid=${BACBO}"
echo "========== DONE =========="
echo "ESTUDO spam blocked; FIRE↔RESULT law on; wait for real ENTER+RESULT on UNIQUE_g1."
echo "Do not paste DONE lines as commands."
