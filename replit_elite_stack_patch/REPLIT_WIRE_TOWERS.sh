#!/usr/bin/env bash
# Wire peak-gate towers v1:
#  1) peak-lock loaders (logical floor -> *_peak gate file)
#  2) lux_tower_merge at EdgePolicy site (all live floors can ALLOW; stamp winner)
#  3) hard-reset to ONE bacbo/supervisor/outbox
#
# Does NOT yet clone 32 full handlers — LIVE engine still proposes the fire;
# merge ensures every good floor is scored and the best tower is stamped.
set -euo pipefail
cd /home/runner/workspace
PY=python3
SHA="${LUXURY_PATCH_SHA:-cursor/add-engine-gate-registry-d5ba}"
BASE="https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/${SHA}/replit_elite_stack_patch"
PEER="${TELEGRAM_TARGET_PEER:-6774605259}"

echo "========== [1/6] download tower bits =========="
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
$PY -m py_compile bot/lux_tower_merge.py bot/gate_alias_resolve.py bot/edge_live_policy.py

echo "========== [2/6] peak-lock loaders (JUN19->_gates_JUN19_peak etc) =========="
bash REPLIT_PEAK_LOCK_APPLY.sh || {
  echo "WARN peak-lock apply returned $? — continuing with merge wire"
}

echo "========== [3/6] inject tower merge into EdgePolicy sites =========="
$PY <<'PY'
import ast, re, time
from pathlib import Path

ROOT = Path("/home/runner/workspace")
BLOCK = '''
# --- LUXURY_TOWER_MERGE (auto) ---
try:
    import os as _lux_tm_os
    _lux_tm_os.environ.setdefault("LUXURY_TOWER_MERGE", "1")
    from lux_tower_merge import merge_candidate as _lux_tower_merge, apply_winner_to_state as _lux_tower_stamp
    def _edge_policy_eval(*, kind, color, agreeing_rooms, source_floor="LIVE", hour_utc=None):
        _v = _lux_tower_merge(
            kind=kind,
            color=color,
            agreeing_rooms=agreeing_rooms,
            engine_floor=source_floor or "LIVE",
            hour_utc=hour_utc,
        )
        _wf = _v.get("winner_floor") or source_floor or "LIVE"
        try:
            _lux_tower_stamp(str(_wf))
        except Exception:
            pass
        return _v
    print("[LUXURY] tower-merge EdgePolicy wrapper ON")
except Exception as _lux_tm_exc:
    print("[LUXURY] tower-merge skipped:", _lux_tm_exc)
# --- end LUXURY_TOWER_MERGE ---
'''

def patch_file(path: Path) -> str:
    if not path.exists():
        return "missing"
    src = path.read_text(encoding="utf-8", errors="replace")
    src2 = re.sub(
        r"\n# --- LUXURY_TOWER_MERGE \(auto\) ---[\s\S]*?# --- end LUXURY_TOWER_MERGE ---\n?",
        "\n",
        src,
    )
    # Prefer inject right before first edge_live_policy import / EdgePolicy block
    markers = [
        r"from edge_live_policy import evaluate as _edge_policy_eval",
        r"from edge_live_policy import evaluate",
        r"# ── Edge Live Policy",
        r"\[EdgePolicy\]",
    ]
    placed = False
    for pat in markers:
        m = re.search(pat, src2)
        if m:
            # insert before the line containing the match
            line_start = src2.rfind("\n", 0, m.start()) + 1
            src2 = src2[:line_start] + BLOCK + "\n" + src2[line_start:]
            placed = True
            break
    if not placed:
        # late inject before __main__
        m = re.search(r"^if __name__", src2, re.M)
        if m:
            src2 = src2[: m.start()] + BLOCK + "\n" + src2[m.start() :]
            placed = True
        else:
            src2 = src2 + "\n" + BLOCK
            placed = True

    # If original _edge_policy_eval import remains AFTER our wrapper, rename it
    # so our wrapper is the name used by the EdgePolicy block.
    # Pattern: our def _edge_policy_eval then later "from edge_live_policy import evaluate as _edge_policy_eval"
    # → change later import alias to _edge_policy_eval_raw
    parts = src2.split("# --- end LUXURY_TOWER_MERGE ---", 1)
    if len(parts) == 2:
        head, tail = parts
        tail2 = tail.replace(
            "from edge_live_policy import evaluate as _edge_policy_eval",
            "from edge_live_policy import evaluate as _edge_policy_eval_raw  # tower-merge wraps",
            1,
        )
        # If block still calls _edge_policy_eval_raw by mistake, map calls that used raw:
        # Prefer: any leftover assignment _edge_v = _edge_policy_eval_raw( → keep raw unused
        # Ensure calls stay on _edge_policy_eval (our wrapper). If install used local import
        # inside try, the rename makes the try import raw; we need the try to USE wrapper.
        # Replace inside the EdgePolicy try body: _edge_policy_eval_raw( -> _edge_policy_eval(
        # only if wrapper exists — actually after rename, calls still say _edge_policy_eval(
        # which is our function. Good IF the import was `as _edge_policy_eval` renamed to raw
        # and calls are `_edge_policy_eval(`. Yes.
        src2 = head + "# --- end LUXURY_TOWER_MERGE ---" + tail2

    ast.parse(src2)
    bak = Path(str(path) + f".bak_pre_tower_{int(time.time())}")
    bak.write_text(src, encoding="utf-8")
    path.write_text(src2, encoding="utf-8")
    return f"patched placed={placed} bytes={len(src2)}"

targets = [
    ROOT / "bot" / "signal_handler.py",
    ROOT / "bacbo_royal_complete.py",
]
for t in targets:
    # only patch files that mention EdgePolicy / edge_live_policy
    if t.exists():
        txt = t.read_text(encoding="utf-8", errors="replace")
        if "edge_live_policy" in txt or "EdgePolicy" in txt or "signal_handler" in t.name:
            print(t.name, patch_file(t))
        else:
            print(t.name, "skip (no EdgePolicy)")
    else:
        print(t.name, "missing")
PY

echo "========== [4/6] env tower merge ON =========="
$PY <<'PY'
from pathlib import Path
p = Path("luxury_building.env")
keys = {}
order = []
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
print("LUXURY_TOWER_MERGE", keys.get("LUXURY_TOWER_MERGE"))
PY

echo "========== [5/6] smoke tower merge =========="
$PY <<'PY'
import os, sys
sys.path.insert(0, "bot")
os.environ["EDGE_POLICY_MODE"] = "luxury"
os.environ["EDGE_LUXURY_FLOOR_GATE"] = "1"
os.environ["LUXURY_TOWER_MERGE"] = "1"
from lux_tower_merge import merge_candidate, _load_floors
peaks, floors, blocked = _load_floors()
print("peaks", peaks)
print("floors_n", len(floors), "blocked", blocked)
v = merge_candidate(kind="SEQUENCE", color="blue", agreeing_rooms=["@RQDADOS1"], engine_floor="LIVE")
print("merge_action", v.get("action"), "winner", v.get("winner_floor"), "reason", str(v.get("reason"))[:120])
print("tower_allows", v.get("tower_allows", [])[:8])
PY

echo "========== [6/6] ONE_STACK hard reset =========="
bash REPLIT_ONE_STACK.sh

echo
echo "EXPECT:"
echo "  - peak-lock loaders for JUN19/JUN20/..."
echo "  - merge_action ALLOW, winner peak floor (not always LIVE)"
echo "  - bacbo=1 supervisor=1 outbox=1"
echo "  - next card FLOOR = tower winner; logs TOWER_MERGE"
echo
echo "DONE. Paste ALL output."
