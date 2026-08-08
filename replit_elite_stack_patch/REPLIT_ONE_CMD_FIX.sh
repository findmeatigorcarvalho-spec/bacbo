#!/usr/bin/env bash
# ONE command — do not paste anything else into this.
#   curl -fsSL -o /tmp/ONE.sh \
#     'https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/cursor/add-engine-gate-registry-d5ba/replit_elite_stack_patch/REPLIT_ONE_CMD_FIX.sh?v=20260808f'
#   bash /tmp/ONE.sh
set -euo pipefail
ROOT="${ROOT:-/home/runner/workspace}"
cd "$ROOT"
BRANCH="${BRANCH:-cursor/add-engine-gate-registry-d5ba}"
RAW="https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/${BRANCH}"
V="20260808f"
PY="${PY:-python3}"

echo "========== ONE CMD FIX ${V} =========="
mkdir -p bot bot/config logs bot/data

echo "-- pull --"
for pair in \
  "bot/fix_bacbo_syntax.py|replit_elite_stack_patch/bot/fix_bacbo_syntax.py" \
  "bot/fix_bacbo_state.py|replit_elite_stack_patch/bot/fix_bacbo_state.py" \
  "bot/state.py|replit_elite_stack_patch/bot/state.py" \
  "bot/lux_estudo_kill.py|replit_elite_stack_patch/bot/lux_estudo_kill.py" \
  "bot/run_bacbo_live.py|replit_elite_stack_patch/bot/run_bacbo_live.py" \
  "bot/lux_re_harden.py|replit_elite_stack_patch/bot/lux_re_harden.py" \
  "bot/lux_send_config_bind.py|replit_elite_stack_patch/bot/lux_send_config_bind.py" \
  "bot/runtime_supervisor.py|replit_elite_stack_patch/bot/runtime_supervisor.py" \
  "bot/telegram_outbox.py|replit_elite_stack_patch/bot/telegram_outbox.py" \
  "bot/config/keep_allowlist.py|bot/config/keep_allowlist.py" \
  "bot/config/__init__.py|bot/config/__init__.py"
do
  dest="${pair%%|*}"
  rel="${pair##*|}"
  # Never clobber a larger existing state.py with a smaller template unless missing/proxy-less
  if [[ "$dest" == "bot/state.py" && -f "$dest" ]]; then
    if grep -q "LUXURY_CLIENT_PROXY" "$dest" 2>/dev/null; then
      echo "  KEEP $dest (proxy present)"
      continue
    fi
  fi
  if curl -fsSL --connect-timeout 20 --max-time 90 -o "$dest" "${RAW}/${rel}?v=${V}"; then
    echo "  OK $dest"
  else
    echo "  FAIL $dest"
  fi
done

# Disk-only fixer (never chat-heredoc — pastes break markers)
cat > /tmp/fix_bacbo_now.py <<'ENDPY'
from pathlib import Path
import ast, shutil, time, sys

def parse_ok(text: str):
    try:
        ast.parse(text)
        return True, None
    except SyntaxError as e:
        return False, e

SCB = """
# --- LUXURY_SEND_CONFIG_BIND (auto) ---
try:
    import lux_send_config_bind  # noqa: F401
    print("[LUXURY] send-config-bind loaded")
except Exception as _lux_scb_exc:
    print("[LUXURY] send-config-bind skipped:", _lux_scb_exc)
# --- end LUXURY_SEND_CONFIG_BIND ---
"""

REH = """
# --- lux_re_harden (safe EOF inject; do not move inside try) ---
try:
    import lux_re_harden  # noqa: F401
    print("[LUXURY] re-harden loaded")
except Exception as _lux_reh_exc:
    print("[LUXURY] re-harden skipped:", _lux_reh_exc)
# --- end lux_re_harden ---
"""

def ensure_binds(path: Path, text: str) -> str:
    """Always ensure SCB + reharden exist as SEPARATE top-level try blocks."""
    changed = False
    # If reharden is nested inside SCB try, repair module first
    if "import lux_send_config_bind" in text and "import lux_re_harden" in text:
        # Detect illegal nest: reharden try before SCB except
        if "send-config-bind loaded" in text:
            i_scb = text.find("import lux_send_config_bind")
            i_reh = text.find("import lux_re_harden")
            i_exc = text.find("except Exception as _lux_scb_exc")
            if i_scb >= 0 and i_reh >= 0 and i_exc >= 0 and i_scb < i_reh < i_exc:
                print("NESTED_REHARDEN_DETECTED → repair module")
                sys.path.insert(0, "bot")
                from fix_bacbo_syntax import repair
                print(repair())
                text = path.read_text(encoding="utf-8", errors="ignore")
                changed = True

    if "import lux_send_config_bind" not in text:
        text = text.rstrip() + "\n" + SCB
        print("APPENDED_SCB")
        changed = True
    if "import lux_re_harden" not in text:
        text = text.rstrip() + "\n" + REH
        print("APPENDED_REHARDEN")
        changed = True
    if changed:
        ok, err = parse_ok(text)
        if not ok:
            print("ENSURE_BINDS_PARSE_FAIL", getattr(err, "lineno", None), getattr(err, "msg", None))
            sys.exit(9)
        shutil.copy2(path, path.with_suffix(path.suffix + f".bak_bind_{int(time.time())}"))
        path.write_text(text if text.endswith("\n") else text + "\n", encoding="utf-8")
    return text

def fix(path: Path) -> str:
    raw = path.read_text(encoding="utf-8", errors="ignore").replace("\r\n", "\n").replace("\r", "\n")
    ok, err = parse_ok(raw)
    if ok:
        ensure_binds(path, raw)
        return "ALREADY_PARSE_OK"

    shutil.copy2(path, path.with_suffix(path.suffix + f".bak_one_{int(time.time())}"))
    lines = raw.splitlines(keepends=True)

    def S(i):
        return lines[i].strip()

    # Prefer repair module (line-based, CRLF tolerant)
    try:
        sys.path.insert(0, "bot")
        from fix_bacbo_syntax import repair
        print(repair())
        text = path.read_text(encoding="utf-8", errors="ignore")
        ensure_binds(path, text)
        return "REPAIR_MODULE"
    except SystemExit as e:
        print("REPAIR_MODULE_EXIT", e)
    except Exception as exc:
        print("REPAIR_MODULE_FAIL", repr(exc))

    # Strategy: LUXURY marker or import lux_send_config_bind
    start = next((i for i, ln in enumerate(lines) if "LUXURY_SEND_CONFIG_BIND (auto)" in ln), None)
    marker_mode = start is not None
    try_scb = None
    if start is not None:
        i = start + 1
        while i < len(lines) and not S(i):
            i += 1
        if i < len(lines) and S(i) == "try:":
            try_scb = i
    if try_scb is None:
        for i, ln in enumerate(lines):
            if "import lux_send_config_bind" in ln:
                j = i
                while j >= 0 and S(j) != "try:":
                    j -= 1
                if j >= 0:
                    try_scb = j
                    break
    if try_scb is None:
        print("NO_SCB_BLOCK — append binds after orphan close attempt")
        # close orphan at error line then append
        if err is None:
            sys.exit(2)
        ln = (err.lineno or 1) - 1
        try_i = None
        for j in range(ln, max(-1, ln - 80), -1):
            if S(j) == "try:":
                try_i = j
                break
        if try_i is not None:
            indent = lines[try_i][: len(lines[try_i]) - len(lines[try_i].lstrip())]
            j = try_i + 1
            while j < len(lines):
                if not S(j) or S(j).startswith("#"):
                    j += 1
                    continue
                ind = lines[j][: len(lines[j]) - len(lines[j].lstrip())]
                if len(ind) <= len(indent) and not S(j).startswith(("except", "finally", "else")):
                    break
                j += 1
            lines[j:j] = [
                f"{indent}except Exception as _lux_orphan_try:\n",
                f"{indent}    pass  # repaired orphan try\n",
            ]
            new = "".join(lines)
            ok3, err3 = parse_ok(new)
            if ok3:
                path.write_text(new, encoding="utf-8")
                ensure_binds(path, new)
                return "FIXED_ORPHAN_TRY"
            print("ORPHAN_CLOSE_FAIL", getattr(err3, "lineno", None), getattr(err3, "msg", None))
        if err and err.lineno:
            lo = max(0, err.lineno - 15)
            hi = min(len(lines), err.lineno + 15)
            for k in range(lo, hi):
                m = ">>>" if k + 1 == err.lineno else "   "
                print(f"{m} {k+1}|{lines[k].rstrip()}")
        sys.exit(2)

    i = try_scb + 1
    body = []
    reharden_try = None
    while i < len(lines):
        s = S(i)
        if s == "try:" and any("lux_re_harden" in S(j) for j in range(i + 1, min(i + 5, len(lines)))):
            reharden_try = i
            break
        if s.startswith("except Exception as _lux_scb_exc"):
            reharden_try = None
            break
        body.append(i)
        i += 1

    if reharden_try is not None:
        i = reharden_try + 1
        while i < len(lines) and not S(i).startswith("except Exception as _lux_scb_exc"):
            i += 1
        if i >= len(lines):
            print("NO_SCB_EXCEPT")
            sys.exit(4)
        scb_except = i
        i += 1
        end = None
        while i < len(lines):
            if "end LUXURY_SEND_CONFIG_BIND" in S(i):
                end = i
                break
            if S(i).startswith("# --- LUXURY_") and "SEND_CONFIG" not in S(i):
                end = i - 1
                break
            i += 1
        if end is None:
            end = scb_except + 1
            while end < len(lines) and (S(end).startswith("print") or not S(end) or S(end).startswith("#")):
                if S(end).startswith("# --- LUXURY_"):
                    break
                end += 1
            end = min(end, len(lines) - 1)

        while body and not S(body[-1]):
            body.pop()

        out = []
        if marker_mode and start is not None:
            out.extend(lines[: start + 1])
            out.extend(lines[start + 1 : try_scb])
        else:
            out.extend(lines[:try_scb])
        out.append(lines[try_scb])
        out.extend(lines[b] for b in body)
        if end >= scb_except:
            out.extend(lines[scb_except : end + 1])
        else:
            out.extend(lines[scb_except : scb_except + 2])
        out.append("\n")
        out.append(REH)
        nxt = end + 1 if end is not None else scb_except + 2
        out.extend(lines[nxt:])
        new = "".join(out)
        ok2, err2 = parse_ok(new)
        if not ok2:
            print("REBUILD_STILL_BAD", err2.lineno, err2.msg)
            sys.exit(5)
        path.write_text(new, encoding="utf-8")
        ensure_binds(path, new)
        return "FIXED_NESTED_REHARDEN"

    # Last resort orphan close
    if err is None:
        ensure_binds(path, raw)
        return "UNKNOWN"
    ln = (err.lineno or 1) - 1
    try_i = None
    for j in range(ln, max(-1, ln - 80), -1):
        if S(j) == "try:":
            try_i = j
            break
    if try_i is None:
        print("NO_ORPHAN_TRY")
        sys.exit(6)
    indent = lines[try_i][: len(lines[try_i]) - len(lines[try_i].lstrip())]
    j = try_i + 1
    while j < len(lines):
        if not S(j) or S(j).startswith("#"):
            j += 1
            continue
        ind = lines[j][: len(lines[j]) - len(lines[j].lstrip())]
        if len(ind) <= len(indent) and not S(j).startswith(("except", "finally", "else")):
            break
        j += 1
    lines[j:j] = [
        f"{indent}except Exception as _lux_orphan_try:\n",
        f"{indent}    pass  # repaired orphan try\n",
    ]
    new = "".join(lines)
    ok3, err3 = parse_ok(new)
    if not ok3:
        print("ORPHAN_CLOSE_FAIL", err3.lineno, err3.msg)
        sys.exit(7)
    path.write_text(new, encoding="utf-8")
    ensure_binds(path, new)
    return "FIXED_ORPHAN_TRY"

path = Path("bacbo_royal_complete.py")
if not path.is_file():
    path = Path("bot/bacbo_royal_complete.py")
if not path.is_file():
    raise SystemExit("MISSING bacbo_royal_complete.py")
print("FILE", path)
print(fix(path))
text = path.read_text(encoding="utf-8", errors="ignore")
ok, err = parse_ok(text)
print("FINAL_PARSE", ok, getattr(err, "lineno", None), getattr(err, "msg", None))
print("HAS_SCB", "import lux_send_config_bind" in text)
print("HAS_REH", "import lux_re_harden" in text)
if not ok:
    sys.exit(8)
print("DONE_FIX")
ENDPY

echo "-- diagnose/fix bacbo syntax + pre-main ESTUDO gate --"
$PY -u /tmp/fix_bacbo_now.py
# Lightweight pre-main inject only (full regex strip hangs on 2.5MB file)
$PY -u - <<'PY'
from pathlib import Path
import sys
sys.path.insert(0, "bot")
from fix_bacbo_syntax import _ensure_scb_before_main, _parse, _show
p = Path("bacbo_royal_complete.py")
if not p.is_file():
    p = Path("bot/bacbo_royal_complete.py")
src = p.read_text(encoding="utf-8", errors="ignore")
rep = {"actions": []}
out = _ensure_scb_before_main(src, rep)
print("PREMAIN", rep)
if out != src:
    err = _parse(out)
    if err is not None:
        _show(err, out)
        raise SystemExit(2)
    p.write_text(out if out.endswith("\n") else out + "\n", encoding="utf-8")
    print("PREMAIN_WROTE", p)
else:
    print("PREMAIN_ALREADY_OK")
PY
$PY -m py_compile bacbo_royal_complete.py 2>/dev/null || $PY -m py_compile bot/bacbo_royal_complete.py
$PY -m py_compile bot/run_bacbo_live.py bot/lux_estudo_kill.py
echo "PY_COMPILE_OK"

echo "-- fix NameError state (line ~146) --"
$PY -u bot/fix_bacbo_state.py
$PY -m py_compile bacbo_royal_complete.py
$PY -m py_compile bot/state.py
# Prove bare name is bound before first state.client assign
$PY -u - <<'PY'
from pathlib import Path
import re, ast
p = Path("bacbo_royal_complete.py")
src = p.read_text(encoding="utf-8", errors="replace")
ast.parse(src)
lines = src.splitlines()
idx = next(i for i, ln in enumerate(lines) if re.search(r"^state\.client\s*=\s*TelegramClient\(", ln) or re.search(r"^_lux_state_mod\.client\s*=\s*TelegramClient\(", ln))
pre = "\n".join(lines[:idx])
assert "state = _lux_state_mod" in pre or "import state as _lux_state_mod" in pre, (
    f"state still unbound before client assign at line {idx+1}"
)
print("STATE_BIND_OK line", idx + 1)
print("HAS_SESSION_BIND", "LUXURY_SESSION_AND_BIND" in src)
# show 12 lines around bind
for j in range(max(0, idx - 12), min(len(lines), idx + 3)):
    print(f"{j+1}: {lines[j][:140]}")
PY

# Force ESTUDO kill env
ENVF=bot/data/profit_skyscraper.env
touch "$ENVF"
for kv in \
  TELEGRAM_TRASH_BLOCK=1 \
  LUX_BLOCK_ESTUDO=1 \
  LUX_SEND_DEDUP_SECS=90 \
  HUB_OUTBOX_RESULT_CARDS=1 \
  FIRE_RESULT_LAW=1 \
  BACBO_READY_SECS=45
do
  k="${kv%%=*}"
  grep -q "^${k}=" "$ENVF" 2>/dev/null && sed -i "s|^${k}=.*|${kv}|" "$ENVF" || echo "$kv" >> "$ENVF"
done

echo "-- self-test ESTUDO drop --"
$PY -u - <<'PY'
import sys
sys.path.insert(0, "bot")
from lux_send_config_bind import _estudo_blocked, _dedup_hit
s = "🔷 G2 ESTUDO | @robobacbodados\n🔵 BLUE G0 🟡 Empate 🔥 | 📊 NEUTRO 1.07"
assert _estudo_blocked(s), "estudo must block"
assert not _estudo_blocked("💎 SOLO ELITE\nENTER NOW")
# near-dup score flicker
a = "🔷 X\n🔵 BLUE G0 | 📊 NEUTRO 1.07"
b = "🔷 X\n🔵 BLUE G0 | 📊 NEUTRO 0.81"
assert _dedup_hit(a) is False
assert _dedup_hit(b) is True
print("ESTUDO_SELFTEST_OK")
from config.keep_allowlist import should_block_as_trash
hit, why = should_block_as_trash(text=s)
assert hit, why
print("TRASH_SELFTEST_OK", why)
PY

echo "-- restart --"
# Mark log so we ignore stale SyntaxError/NameError lines
echo "===== ONE_CMD ${V} restart $(date -u +%Y-%m-%dT%H:%M:%SZ) =====" >> logs/bot_live.log
pkill -f 'runtime_supervisor.py|bacbo_royal_complete.py|telegram_outbox.py|run_bacbo_live.py' 2>/dev/null || true
rm -f bot/data/runtime_supervisor.lock bot/data/telegram_outbox.lock 2>/dev/null || true
sleep 2
nohup $PY -u bot/runtime_supervisor.py > /tmp/luxury_supervisor.log 2>&1 &
sleep 40

echo "---- procs ----"
pgrep -af 'runtime_supervisor|telegram_outbox|bacbo_royal|run_bacbo_live' || true
echo "---- bot_live (post-restart only) ----"
awk "/ONE_CMD ${V} restart/{flag=1;next} flag" logs/bot_live.log 2>/dev/null | tail -n 50 || tail -n 40 logs/bot_live.log
echo "---- fresh errors / gate ----"
awk "/ONE_CMD ${V} restart/{flag=1;next} flag" logs/bot_live.log 2>/dev/null \
  | grep -E 'NameError|SyntaxError|Traceback|send-config-bind|ESTUDO-KILL|run_bacbo_live|run_forever|BootGrace|drop ESTUDO' \
  | tail -n 40 || true
echo "---- supervisor ----"
tail -n 50 /tmp/luxury_supervisor.log 2>/dev/null || true

BACBO_ALIVE=0
pgrep -f 'run_bacbo_live.py|bacbo_royal_complete.py' >/dev/null && BACBO_ALIVE=1
if [[ "$BACBO_ALIVE" -eq 1 ]]; then
  if awk "/ONE_CMD ${V} restart/{flag=1;next} flag" logs/bot_live.log 2>/dev/null | grep -q "NameError: name 'state'"; then
    echo "BACBO_UP_BUT_STATE_NAMEERROR"
    exit 1
  fi
  echo "BACBO_UP"
else
  echo "BACBO_DOWN — see tails above"
  exit 1
fi
echo "========== DONE =========="
echo "Launcher preloads ESTUDO kill BEFORE main. pgrep: runtime_supervisor|run_bacbo_live|telegram_outbox"
