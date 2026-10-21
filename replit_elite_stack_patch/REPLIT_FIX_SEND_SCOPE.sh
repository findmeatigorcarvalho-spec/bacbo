#!/usr/bin/env bash
# Fix: send() failed: name 'config' is not defined
# Cause is NOT "everything firing at once" — Telegram works (fallbacks).
# Cause: send() references `config` in a scope where it is not bound
# (local assignment / nested def), even if module has `import config`.
set -euo pipefail
cd /home/runner/workspace
PY=python3
SHA="${LUXURY_PATCH_SHA:-cursor/add-engine-gate-registry-d5ba}"
BASE="https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/${SHA}/replit_elite_stack_patch"
PEER="${TELEGRAM_TARGET_PEER:-6774605259}"

echo "========== [1/6] stop =========="
pkill -9 -f 'bacbo_royal_complete.py' 2>/dev/null || true
pkill -9 -f 'runtime_supervisor.py' 2>/dev/null || true
pkill -9 -f 'fallback_signal_sender.py' 2>/dev/null || true
pkill -9 -f 'fallback_result_sender.py' 2>/dev/null || true
sleep 2

echo "========== [2/6] download bind helper + fallbacks =========="
mkdir -p bot/data logs
curl -fsSL -H "Cache-Control: no-cache" -o bot/lux_send_config_bind.py "$BASE/bot/lux_send_config_bind.py"
curl -fsSL -H "Cache-Control: no-cache" -o bot/lux_no_hour_blocks.py "$BASE/bot/lux_no_hour_blocks.py"
curl -fsSL -H "Cache-Control: no-cache" -o bot/lux_sqlite_harden.py "$BASE/bot/lux_sqlite_harden.py"
curl -fsSL -H "Cache-Control: no-cache" -o bot/runtime_supervisor.py "$BASE/bot/runtime_supervisor.py"
curl -fsSL -H "Cache-Control: no-cache" -o bot/fallback_signal_sender.py "$BASE/bot/fallback_signal_sender.py"
curl -fsSL -H "Cache-Control: no-cache" -o bot/fallback_result_sender.py "$BASE/bot/fallback_result_sender.py"
$PY -m py_compile bot/lux_send_config_bind.py bot/lux_no_hour_blocks.py bot/runtime_supervisor.py

echo "========== [3/6] diagnose + patch send() scopes in bacbo =========="
$PY <<'PY'
import ast, re, shutil, time
from pathlib import Path

p = Path("bacbo_royal_complete.py")
src = p.read_text(encoding="utf-8", errors="replace")
bak = Path(f"bacbo_royal_complete.py.bak_pre_send_scope_{int(time.time())}")
shutil.copy2(p, bak)
print("backup", bak.name)

tree = ast.parse(src)
print("--- AST send() that reference config ---")


class SendVisitor(ast.NodeVisitor):
    def __init__(self):
        self.hits = []

    def visit_AsyncFunctionDef(self, node):
        self._check(node)
        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        self._check(node)
        self.generic_visit(node)

    def _check(self, node):
        if node.name != "send":
            return
        names = {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}
        assigns = {
            t.id
            for n in ast.walk(node)
            if isinstance(n, ast.Assign)
            for t in n.targets
            if isinstance(t, ast.Name)
        }
        # also AnnAssign / AugAssign
        for n in ast.walk(node):
            if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name):
                assigns.add(n.target.id)
            if isinstance(n, ast.AugAssign) and isinstance(n.target, ast.Name):
                assigns.add(n.target.id)
        uses_config = "config" in names
        assigns_config = "config" in assigns
        # free: Load of config
        loads = {
            n.id
            for n in ast.walk(node)
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)
        }
        self.hits.append(
            {
                "lineno": node.lineno,
                "uses_config": uses_config or ("config" in loads),
                "assigns_config": assigns_config,
                "has_import_config_in_body": any(
                    isinstance(n, ast.Import) and any(a.name == "config" for a in n.names)
                    for n in node.body
                ),
            }
        )


v = SendVisitor()
v.visit(tree)
for h in v.hits:
    print(h)
if not v.hits:
    print("(no def send found — will still inject runtime bind)")

# 1) Inject `import config` as first body line of each send that uses config
#    Use line-based insert with AST linenos (1-based)
lines = src.splitlines(True)
# Work from bottom so line numbers stay valid
inserts = []
for h in v.hits:
    if not h["uses_config"]:
        continue
    if h["has_import_config_in_body"]:
        continue
    # find def line and first body statement line
    # Re-parse to get end_lineno of def header / body[0].lineno
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "send" and node.lineno == h["lineno"]:
            if not node.body:
                break
            body0 = node.body[0]
            # skip docstring
            if (
                isinstance(body0, ast.Expr)
                and isinstance(getattr(body0, "value", None), ast.Constant)
                and isinstance(body0.value.value, str)
            ):
                if len(node.body) > 1:
                    body0 = node.body[1]
                else:
                    break
            indent = "    "
            # detect indent from body0 line
            raw = lines[body0.lineno - 1]
            indent = raw[: len(raw) - len(raw.lstrip())] or "    "
            inserts.append((body0.lineno - 1, f"{indent}import config  # LUXURY: send-scope bind\n"))
            break

for idx, text in sorted(inserts, key=lambda x: -x[0]):
    lines.insert(idx, text)
    print("inserted import config into send() before line", idx + 1)

src2 = "".join(lines)

# 2) Ensure module-level import config
if not re.search(r"^(import config|from config import)\b", src2, re.M):
    ls = src2.splitlines(True)
    idx = 0
    for i, ln in enumerate(ls[:80]):
        s = ln.strip()
        if not s or s.startswith("#") or s.startswith("from __future__") or s.startswith("import ") or s.startswith("from "):
            idx = i + 1
        else:
            break
    ls.insert(idx, "import config  # LUXURY: module-level for send()\n")
    src2 = "".join(ls)
    print("added module-level import config")

# 3) Inject lux_send_config_bind LATE (after send() is defined) — before __main__/run_forever
if "LUXURY_SEND_CONFIG_BIND" not in src2:
    block = '''
# --- LUXURY_SEND_CONFIG_BIND (auto) ---
try:
    import lux_send_config_bind  # noqa: F401
    print("[LUXURY] send-config-bind loaded")
except Exception as _lux_scb_exc:
    print("[LUXURY] send-config-bind skipped:", _lux_scb_exc)
# --- end LUXURY_SEND_CONFIG_BIND ---
'''
    m3 = re.search(r"^if __name__", src2, re.M)
    m4 = re.search(r"\brun_forever\s*\(", src2)
    if m3:
        src2 = src2[: m3.start()] + block + "\n" + src2[m3.start() :]
        print("injected SEND_CONFIG_BIND before __main__")
    elif m4:
        src2 = src2[: m4.start()] + block + "\n" + src2[m4.start() :]
        print("injected SEND_CONFIG_BIND before run_forever")
    else:
        src2 = src2 + "\n" + block
        print("injected SEND_CONFIG_BIND at eof")
# Keep peak-pure injector if missing
if "LUXURY_NO_HOUR_BLOCKS" not in src2:
    nhb = '''
# --- LUXURY_NO_HOUR_BLOCKS (auto) ---
try:
    import lux_no_hour_blocks  # noqa: F401
    print("[LUXURY] peak-pure: hour blocks OFF (peak floors kept)")
except Exception as _lux_nhb_exc:
    print("[LUXURY] no_hour_blocks skipped:", _lux_nhb_exc)
# --- end LUXURY_NO_HOUR_BLOCKS ---
'''
    m = re.search(r"# --- LUXURY_SEND_CONFIG_BIND", src2)
    if m:
        src2 = src2[: m.start()] + nhb + "\n" + src2[m.start() :]
    else:
        src2 = src2 + "\n" + nhb
    print("re-injected NO_HOUR_BLOCKS")

ast.parse(src2)
p.write_text(src2, encoding="utf-8")
print("bacbo syntax OK bytes", len(src2))
print("send_scope_imports", src2.count("import config  # LUXURY: send-scope bind"))
print("has_send_config_bind", "LUXURY_SEND_CONFIG_BIND" in src2)
PY

echo "========== [4/6] env =========="
cat > luxury_building.env <<EOF
export EDGE_POLICY_MODE=luxury
export EDGE_LUXURY_FLOOR_GATE=1
export FALLBACKS_ENABLED=1
export FALLBACK_SEND_BLOCKED=0
export LUXURY_NO_HOUR_BLOCKS=1
export BOT_TZ=America/Sao_Paulo
export TELEGRAM_TARGET_PEER=${PEER}
EOF
set -a
# shellcheck disable=SC1091
source ./luxury_building.env
set +a
export TELEGRAM_SESSION_STRING="$(tr -d '\n' < .telegram_session_string)"
export TELEGRAM_TARGET_PEER="$PEER"
export FALLBACKS_ENABLED=1

echo "========== [5/6] restart =========="
nohup env EDGE_POLICY_MODE=luxury EDGE_LUXURY_FLOOR_GATE=1 FALLBACKS_ENABLED=1 \
  FALLBACK_SEND_BLOCKED=0 LUXURY_NO_HOUR_BLOCKS=1 BOT_TZ=America/Sao_Paulo \
  TELEGRAM_SESSION_STRING="$TELEGRAM_SESSION_STRING" \
  TELEGRAM_TARGET_PEER="$PEER" \
  $PY -u bot/runtime_supervisor.py > /tmp/luxury_supervisor.log 2>&1 &
echo "supervisor pid=$!"

echo "========== [6/6] settle 60s + verdict =========="
sleep 30
echo "----- 30s -----"
pgrep -af 'runtime_supervisor|bacbo_royal|fallback_' || echo NONE
sleep 30
echo "----- 60s -----"
pgrep -af 'runtime_supervisor|bacbo_royal|fallback_' || echo NONE

$PY <<'PY'
from pathlib import Path
import re
src = Path("bacbo_royal_complete.py").read_text(encoding="utf-8", errors="replace")
print("module_import_config", bool(re.search(r"^import config\b", src, re.M)))
print("send_scope_binds", src.count("LUXURY: send-scope bind"))
print("runtime_bind_block", "LUXURY_SEND_CONFIG_BIND" in src)
print("boot_bind_log_expected", "send-config-bind" )

log = Path("logs/bot_live.log")
lines = log.read_text(errors="replace").splitlines() if log.exists() else []
cut = 0
for i, ln in enumerate(lines):
    if "[BootFilter]" in ln or "send-config-bind" in ln or "starting run_forever" in ln:
        cut = i
post = lines[cut:]
cfg_err = [ln for ln in post if "name 'config' is not defined" in ln]
send_fail = [ln for ln in post if "send() failed" in ln]
print("post_boot_config_NameError", len(cfg_err))
print("post_boot_send_failed", len(send_fail))
for ln in (cfg_err + send_fail)[-10:]:
    print(ln)
bind = [ln for ln in post if "send-config-bind" in ln or "SEND_CONFIG" in ln]
print("bind_boot_lines", len(bind))
for ln in bind[-5:]:
    print(ln)
print("--- last 20 ---")
for ln in lines[-20:]:
    print(ln)
PY

echo "--- fallback ---"
tail -n 6 logs/fallback_sender.log 2>/dev/null || true
tail -n 4 logs/fallback_result_sender.log 2>/dev/null || true

echo
echo "VERDICT: want post_boot_config_NameError 0"
echo "NOTE: Not a fire-dump issue. Fallbacks already prove Telegram delivery."
echo "Native send fails on Python scope for config (often boot grade/schedule card)."
echo
echo "DONE. Paste ALL output."
