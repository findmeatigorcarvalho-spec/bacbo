#!/usr/bin/env bash
# Wire peak-gate towers v1 (SAFE — no bacbo AST surgery):
#  1) restore bacbo if prior inject broke IndentationError
#  2) peak-lock loaders (JUN19 -> _gates_JUN19_peak)
#  3) tower merge via edge_live_policy.evaluate hook (no mega-file patch)
#  4) hard-reset ONE bacbo/supervisor/outbox
set -euo pipefail
cd /home/runner/workspace
PY=python3
SHA="${LUXURY_PATCH_SHA:-cursor/add-engine-gate-registry-d5ba}"
BASE="https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/${SHA}/replit_elite_stack_patch"
PEER="${TELEGRAM_TARGET_PEER:-6774605259}"

echo "========== [1/7] download bits =========="
mkdir -p bot/data logs
for rel in \
  bot/lux_tower_merge.py \
  bot/gate_alias_resolve.py \
  bot/edge_live_policy.py \
  bot/runtime_supervisor.py \
  bot/telegram_outbox.py \
  bot/lux_floor_rotate.py \
  peak_lock_config.json \
  REPLIT_PEAK_LOCK_APPLY.sh \
  REPLIT_ONE_STACK.sh
do
  curl -fsSL -H "Cache-Control: no-cache" -o "$rel" "$BASE/$rel"
done
cp -f peak_lock_config.json bot/data/peak_lock_config.json 2>/dev/null || true
$PY -m py_compile bot/lux_tower_merge.py bot/edge_live_policy.py bot/gate_alias_resolve.py

echo "========== [2/7] restore bacbo if tower-inject broke it =========="
$PY <<'PY'
import ast
from pathlib import Path

bacbo = Path("bacbo_royal_complete.py")
sh = Path("bot/signal_handler.py")

def try_parse(p: Path) -> bool:
    if not p.exists():
        return True
    try:
        ast.parse(p.read_text(encoding="utf-8", errors="replace"))
        return True
    except SyntaxError as e:
        print(p, "BROKEN:", e)
        return False

def restore(p: Path) -> None:
    baks = sorted(p.parent.glob(p.name + ".bak_pre_tower_*"), reverse=True)
    if not baks:
        # also try generic bak
        baks = sorted(p.parent.glob(p.name + ".bak*"), reverse=True)
    for bak in baks:
        try:
            txt = bak.read_text(encoding="utf-8", errors="replace")
            ast.parse(txt)
            p.write_text(txt, encoding="utf-8")
            print("RESTORED", p, "from", bak.name)
            return
        except Exception as e:
            print("skip bak", bak.name, e)
    print("WARN: no good bak for", p)

for path in (bacbo, sh):
    if path.exists() and not try_parse(path):
        restore(path)
        if not try_parse(path):
            raise SystemExit(f"FATAL: {path} still broken after restore")
    elif path.exists():
        print(path, "syntax OK")

# Strip any failed LUXURY_TOWER_MERGE inject blocks (leave file clean)
import re
for path in (bacbo, sh):
    if not path.exists():
        continue
    src = path.read_text(encoding="utf-8", errors="replace")
    src2 = re.sub(
        r"\n# --- LUXURY_TOWER_MERGE \(auto\) ---[\s\S]*?# --- end LUXURY_TOWER_MERGE ---\n?",
        "\n",
        src,
    )
    if src2 != src:
        ast.parse(src2)
        path.write_text(src2, encoding="utf-8")
        print(path, "stripped failed tower-merge inject")
PY

echo "========== [3/7] peak-lock loaders =========="
# Do NOT let peak-lock start a second supervisor — ONE_STACK owns the stack.
export SKIP_SUPERVISOR_RESTART=1
bash REPLIT_PEAK_LOCK_APPLY.sh || echo "WARN peak-lock apply status=$?"
unset SKIP_SUPERVISOR_RESTART

echo "========== [4/7] tower merge via edge_live_policy hook (safe) =========="
# edge_live_policy.evaluate already wraps merge when LUXURY_TOWER_MERGE=1
# Ensure no leftover broken inject; confirm hook works in smoke below.

echo "========== [5/7] env =========="
$PY <<'PY'
from pathlib import Path
p = Path("luxury_building.env")
keys, order = {}, []
if p.exists():
    for ln in p.read_text().splitlines():
        s = ln.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        if s.startswith("export "):
            s = s[7:].strip()
        k, v = s.split("=", 1)
        k = k.strip()
        if k not in keys:
            order.append(k)
        keys[k] = v.strip()
for k, v in {
    "EDGE_POLICY_MODE": "luxury",
    "EDGE_LUXURY_FLOOR_GATE": "1",
    "LUXURY_TOWER_MERGE": "1",
    "TELEGRAM_SINGLE_OUTBOX": "1",
    "FALLBACKS_ENABLED": "1",
    "LUXURY_FLOOR_ROTATE": "1",
    "LUXURY_FLOOR_ROTATE_MODE": "tag",
    "LUXURY_FLOOR_ROTATE_DEFER_APPLY": "0",
    "FALLBACK_START_DELAY_SECS": "20",
}.items():
    if k not in order:
        order.append(k)
    keys[k] = v
p.write_text("\n".join(f"export {k}={keys[k]}" for k in order if k in keys) + "\n")
print("LUXURY_TOWER_MERGE", keys["LUXURY_TOWER_MERGE"])
PY

echo "========== [6/7] smoke =========="
$PY <<'PY'
import os, sys, ast
from pathlib import Path
sys.path.insert(0, "bot")
os.environ["EDGE_POLICY_MODE"] = "luxury"
os.environ["EDGE_LUXURY_FLOOR_GATE"] = "1"
os.environ["LUXURY_TOWER_MERGE"] = "1"
# bacbo must parse
ast.parse(Path("bacbo_royal_complete.py").read_text(encoding="utf-8", errors="replace"))
print("bacbo_parse OK")
from edge_live_policy import evaluate, evaluate_one
from lux_tower_merge import merge_candidate, _load_floors
peaks, floors, blocked = _load_floors()
print("peaks", peaks[:5], "floors_n", len(floors))
one = evaluate_one(kind="SEQUENCE", color="blue", agreeing_rooms=["@RQDADOS1"], source_floor="LIVE")
print("one_LIVE", one.get("action"), one.get("reason"))
v = evaluate(kind="SEQUENCE", color="blue", agreeing_rooms=["@RQDADOS1"], source_floor="LIVE")
print("merge_via_evaluate", v.get("action"), "winner", v.get("winner_floor"), "reason", str(v.get("reason"))[:100])
print("allows", (v.get("tower_allows") or [])[:8])
assert v.get("action") in ("ALLOW", "SHADOW_ALLOW"), v
assert v.get("winner_floor"), v
print("smoke_ok")
PY

echo "========== [7/7] ONE_STACK hard reset =========="
bash REPLIT_ONE_STACK.sh

echo
echo "EXPECT: bacbo_parse OK, winner peak (JUN19…), bacbo_pids n=1, outbox n=1"
echo "DONE. Paste ALL output."
