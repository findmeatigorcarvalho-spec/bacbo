#!/usr/bin/env bash
# ONE command — do not paste anything else into this.
#   curl -fsSL -o /tmp/ONE.sh \
#     'https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/cursor/add-engine-gate-registry-d5ba/replit_elite_stack_patch/REPLIT_ONE_CMD_FIX.sh?v=20260824b'
#   bash /tmp/ONE.sh
set -euo pipefail
ROOT="${ROOT:-/home/runner/workspace}"
cd "$ROOT"
BRANCH="${BRANCH:-cursor/add-engine-gate-registry-d5ba}"
RAW="https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/${BRANCH}"
V="20260824b"
PY="${PY:-python3}"

echo "========== ONE CMD FIX ${V} =========="
mkdir -p bot bot/config logs bot/data

echo "-- pull --"
for pair in \
  "bot/fix_bacbo_syntax.py|replit_elite_stack_patch/bot/fix_bacbo_syntax.py" \
  "bot/fix_bacbo_state.py|replit_elite_stack_patch/bot/fix_bacbo_state.py" \
  "bot/state.py|replit_elite_stack_patch/bot/state.py" \
  "bot/lux_estudo_kill.py|replit_elite_stack_patch/bot/lux_estudo_kill.py" \
  "bot/lux_estudo_source_kill.py|replit_elite_stack_patch/bot/lux_estudo_source_kill.py" \
  "bot/run_bacbo_live.py|replit_elite_stack_patch/bot/run_bacbo_live.py" \
  "bot/hub_orchestrator.py|replit_elite_stack_patch/bot/hub_orchestrator.py" \
  "bot/hub_impact_learner.py|replit_elite_stack_patch/bot/hub_impact_learner.py" \
  "bot/lux_chat_watchdog.py|replit_elite_stack_patch/bot/lux_chat_watchdog.py" \
  "bot/lux_outbox_inline.py|replit_elite_stack_patch/bot/lux_outbox_inline.py" \
  "bot/lux_session_guard.py|replit_elite_stack_patch/bot/lux_session_guard.py" \
  "bot/lux_flask_guard.py|replit_elite_stack_patch/bot/lux_flask_guard.py" \
  "bot/lux_keepalive_off.py|replit_elite_stack_patch/bot/lux_keepalive_off.py" \
  "bot/fix_bacbo_keepalive.py|replit_elite_stack_patch/bot/fix_bacbo_keepalive.py" \
  "bot/lux_dialog_resolve.py|replit_elite_stack_patch/bot/lux_dialog_resolve.py" \
  "bot/hub_max_boot.py|replit_elite_stack_patch/bot/hub_max_boot.py" \
  "bot/hub_engine_route.py|replit_elite_stack_patch/bot/hub_engine_route.py" \
  "bot/lux_tower_merge.py|replit_elite_stack_patch/bot/lux_tower_merge.py" \
  "bot/v2_floor_proposers.py|replit_elite_stack_patch/bot/v2_floor_proposers.py" \
  "bot/edge_live_policy.py|replit_elite_stack_patch/bot/edge_live_policy.py" \
  "bot/lux_no_hour_blocks.py|replit_elite_stack_patch/bot/lux_no_hour_blocks.py" \
  "bot/lux_re_harden.py|replit_elite_stack_patch/bot/lux_re_harden.py" \
  "bot/lux_send_config_bind.py|replit_elite_stack_patch/bot/lux_send_config_bind.py" \
  "bot/runtime_supervisor.py|replit_elite_stack_patch/bot/runtime_supervisor.py" \
  "bot/telegram_outbox.py|replit_elite_stack_patch/bot/telegram_outbox.py" \
  "bot/fallback_result_sender.py|replit_elite_stack_patch/bot/fallback_result_sender.py" \
  "bot/card_timezone.py|replit_elite_stack_patch/bot/card_timezone.py" \
  "bot/lux_state_heal.py|replit_elite_stack_patch/bot/lux_state_heal.py" \
  "bot/hotfix_signal_handler.py|replit_elite_stack_patch/bot/hotfix_signal_handler.py" \
  "bot/lux_live_db.py|replit_elite_stack_patch/bot/lux_live_db.py" \
  "bot/g2_coalition.py|replit_elite_stack_patch/bot/g2_coalition.py" \
  "bot/lux_free_volume.py|replit_elite_stack_patch/bot/lux_free_volume.py" \
  "bot/reality_law.py|replit_elite_stack_patch/bot/reality_law.py" \
  "bot/window_packer.py|replit_elite_stack_patch/bot/window_packer.py" \
  "bot/round_sync_densifier.py|replit_elite_stack_patch/bot/round_sync_densifier.py" \
  "bot/operator_lock.py|replit_elite_stack_patch/bot/operator_lock.py" \
  "bot/data/OPERATOR_LOCK.md|replit_elite_stack_patch/bot/data/OPERATOR_LOCK.md" \
  "bot/data/peak_lock_config.json|replit_elite_stack_patch/bot/data/peak_lock_config.json" \
  "bot/hub_dispatch.py|replit_elite_stack_patch/bot/hub_dispatch.py" \
  "bot/sequence_family_wake.py|replit_elite_stack_patch/bot/sequence_family_wake.py" \
  "bot/dual_lane_router.py|replit_elite_stack_patch/bot/dual_lane_router.py" \
  "bot/chronology_evidence.py|replit_elite_stack_patch/bot/chronology_evidence.py" \
  "bot/chronology_integrity_audit.py|replit_elite_stack_patch/bot/chronology_integrity_audit.py" \
  "bot/observer_confirm.py|replit_elite_stack_patch/bot/observer_confirm.py" \
  "bot/truth_verifier.py|replit_elite_stack_patch/bot/truth_verifier.py" \
  "bot/build_evidence_manifest.py|replit_elite_stack_patch/bot/build_evidence_manifest.py" \
  "bot/fix_tz_utils.py|replit_elite_stack_patch/bot/fix_tz_utils.py" \
  "bot/lux_babysitter.sh|replit_elite_stack_patch/bot/lux_babysitter.sh" \
  "REPLIT_UP_NOW.sh|replit_elite_stack_patch/REPLIT_UP_NOW.sh" \
  "REPLIT_EVIDENCE_SNAPSHOT.sh|replit_elite_stack_patch/REPLIT_EVIDENCE_SNAPSHOT.sh" \
  "bot/config/keep_allowlist.py|bot/config/keep_allowlist.py" \
  "bot/config/__init__.py|bot/config/__init__.py" \
  "bot/config/emanation_laws.py|bot/config/emanation_laws.py" \
  "bot/config/signal_bundle_queue.py|bot/config/signal_bundle_queue.py" \
  "bot/config/fire_result_law.py|bot/config/fire_result_law.py"
do
  dest="${pair%%|*}"
  rel="${pair##*|}"
  # Never clobber a larger existing state.py with a smaller template unless missing/proxy-less
  # NEVER overwrite a live bot/state.py. It can carry attributes the running
  # megafile depends on (e.g. _quarantine_tasks) that our minimal template
  # does not know about. An overwrite here previously caused a live crash
  # loop ("module 'state' has no attribute '_quarantine_tasks'"). Only write
  # when the file is missing entirely, or when explicitly forced.
  if [[ "$dest" == "bot/state.py" && -f "$dest" && "${LUX_STATE_FORCE_REFRESH:-0}" != "1" ]]; then
    echo "  KEEP $dest (exists — never clobber live state; LUX_STATE_FORCE_REFRESH=1 to override)"
    continue
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
$PY -m py_compile bot/run_bacbo_live.py bot/lux_estudo_kill.py bot/lux_estudo_source_kill.py bot/lux_chat_watchdog.py bot/card_timezone.py bot/chronology_evidence.py bot/chronology_integrity_audit.py bot/observer_confirm.py bot/build_evidence_manifest.py bot/telegram_outbox.py bot/fallback_result_sender.py bot/lux_flask_guard.py bot/lux_keepalive_off.py bot/fix_bacbo_keepalive.py
BOT_TZ=America/Sao_Paulo $PY bot/fix_tz_utils.py
$PY bot/build_evidence_manifest.py
$PY bot/chronology_evidence.py >/tmp/chronology_evidence_report.txt
echo "CHRONOLOGY_EVIDENCE_OK bot/data/chronology_evidence_report.json"
$PY bot/chronology_integrity_audit.py >/tmp/chronology_integrity_audit.txt
echo "CHRONOLOGY_INTEGRITY_OK bot/data/chronology_integrity_audit.json"
echo "-- disable KeepAlive in megafile (PORT steal → SIGKILL -9) --"
$PY -u bot/fix_bacbo_keepalive.py || true
echo "PY_COMPILE_OK"

echo "-- fix NameError state (line ~146) --"
$PY -u bot/fix_bacbo_state.py
$PY -m py_compile bacbo_royal_complete.py
$PY -m py_compile bot/state.py
echo "-- self-heal state.py (scan ALL live .py; Lock for *_lock; dict for _rooms) --"
$PY -u bot/lux_state_heal.py
$PY -m py_compile bot/state.py
echo "-- hotfix signal_handler _rooms.get --"
$PY -u bot/hotfix_signal_handler.py || true
echo "-- live DB probe (must have consensus_signals) --"
$PY -u bot/lux_live_db.py || true
echo "-- free-volume: unshrink FIRE/RESULT onto UNIQUE_g1 --"
$PY -u bot/lux_free_volume.py || true
echo "-- no-hour-blocks: wipe AutoCHB / AutoIntel hour mutes --"
$PY -u bot/lux_no_hour_blocks.py || true
echo "-- reality-law: printed seconds = outcome; already-working skins are live --"
$PY -u bot/reality_law.py || true
echo "-- sequence-family: forensic countdown FIRE (printed secs = outcome) --"
$PY -u bot/sequence_family_wake.py || true
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
  LUX_SEND_DEDUP_SECS=12 \
  LUX_FREE_VOLUME=1 \
  LUX_G2_COALITION_TO_G1=1 \
  HUB_GUNIQUE_TRUST_MIN=0 \
  HUB_CATCHUP_MAX_PER_TICK=24 \
  HUB_OUTBOX_RESULT_CARDS=1 \
  FIRE_RESULT_LAW=1 \
  RESULT_ATTACH_IMMEDIATE=1 \
  PRINTED_SECS_ARE_OUTCOME=1 \
  PACKER_HOLD_UNTIL_REAL=0 \
  HUB_MAX=1 \
  HUB_ORCHESTRATOR=1 \
  VOLUME_MODE=EXPLOSION \
  V2_PROPOSERS=1 \
  FREE_PROPOSE=1 \
  LUXURY_NO_HOUR_BLOCKS=1 \
  EDGE_LUXURY_FLOOR_GATE=0 \
  ROLLING_WR_MUTE_SECS=0 \
  AUTO_QUARANTINE_SECS=0 \
  HUB_IMPACT_LEARNER=1 \
  LUX_CHAT_WATCHDOG=1 \
  LUX_BLOCK_ESTUDO=1 \
  LUX_CHAT_WATCH_CALL=1 \
  LUX_CHAT_WATCH_CALL_BOOT=1 \
  LUX_CHAT_WATCH_CALL_ON_CONNECT=1 \
  LUX_CHAT_WATCH_CALL_EARLY_SECS=3 \
  LUX_CHAT_WATCH_CALL_AFTER_SETTLE=1 \
  LUX_BLOCK_FORWARDS=1 \
  LUX_ESTUDO_SOURCE_KILL=1 \
  EMANATION_LAWS=1 \
  COLOR_TRUTH_FACTUAL=1 \
  SIGNAL_BUNDLE_VERTICAL=1 \
  CHAT_HERMETIC=1 \
  RESULT_REPLY_TO_FIRE=1 \
  BOT_TZ=America/Sao_Paulo \
  LUX_SKIP_RESOLVE_USERNAME=1 \
  BACBO_READY_SECS=12 \
  FALLBACK_START_DELAY_SECS=15 \
  TELEGRAM_OUTBOX_INLINE=1 \
  TELEGRAM_OUTBOX_STARTUP_PING=0 \
  OUTBOX_INLINE_SETTLE_SECS=70 \
  LUX_SESSION_GUARD=1 \
  LUX_SESSION_RECONNECTS=12 \
  BACBO_SESSION_SETTLE_SECS=28 \
  BACBO_AUTHKEY_SETTLE_SECS=40 \
  LUX_DIALOG_WARM=cache \
  LUX_FLASK_GUARD=1 \
  LUX_KEEPALIVE_OFF=1 \
  FLASK_DEBUG=0
do
  k="${kv%%=*}"
  grep -q "^${k}=" "$ENVF" 2>/dev/null && sed -i "s|^${k}=.*|${kv}|" "$ENVF" || echo "$kv" >> "$ENVF"
done

# Force luxury_building.env — strip duplicate bare/export lines for session keys
LUXENV=luxury_building.env
touch "$LUXENV"
$PY - <<'PY'
from pathlib import Path
p = Path("luxury_building.env")
keys = {
    "TELEGRAM_OUTBOX_INLINE": "1",
    "TELEGRAM_OUTBOX_STARTUP_PING": "0",
    "OUTBOX_INLINE_SETTLE_SECS": "70",
    "LUX_SESSION_GUARD": "1",
    "LUX_SESSION_RECONNECTS": "12",
    "BACBO_SESSION_SETTLE_SECS": "28",
    "BACBO_AUTHKEY_SETTLE_SECS": "40",
    "LUX_DIALOG_WARM": "cache",
    "LUX_FLASK_GUARD": "1",
    "LUX_KEEPALIVE_OFF": "1",
    "LUX_CHAT_WATCHDOG": "1",
    "LUX_BLOCK_ESTUDO": "1",
    "LUX_CHAT_WATCH_CALL": "1",
    "LUX_CHAT_WATCH_CALL_BOOT": "1",
    "LUX_CHAT_WATCH_CALL_ON_CONNECT": "1",
    "LUX_CHAT_WATCH_CALL_EARLY_SECS": "3",
    "LUX_CHAT_WATCH_CALL_AFTER_SETTLE": "1",
    "LUX_BLOCK_FORWARDS": "1",
    "LUX_ESTUDO_SOURCE_KILL": "1",
    "EMANATION_LAWS": "1",
    "COLOR_TRUTH_FACTUAL": "1",
    "SIGNAL_BUNDLE_VERTICAL": "1",
    "CHAT_HERMETIC": "1",
    "RESULT_REPLY_TO_FIRE": "1",
    "FLASK_DEBUG": "0",
    "FLASK_ENV": "production",
    "WERKZEUG_RUN_MAIN": "true",
}
lines = p.read_text(encoding="utf-8", errors="ignore").splitlines() if p.exists() else []
seen=set(); out=[]
for line in lines:
    s=line.strip()
    if not s or s.startswith("#") or "=" not in s:
        out.append(line); continue
    body=s[7:].strip() if s.startswith("export ") else s
    k=body.split("=",1)[0].strip()
    if k in keys:
        if k in seen: continue
        out.append(f"export {k}={keys[k]}"); seen.add(k); continue
    out.append(line)
for k,v in keys.items():
    if k not in seen:
        out.append(f"export {k}={v}")
p.write_text("\n".join(out).rstrip()+"\n", encoding="utf-8")
print("LUXENV_SESSION_KEYS_OK")
for k in keys:
    print(f"  {k}={keys[k]}")
PY

echo "-- self-test ESTUDO + HUB orchestrator --"
$PY -u - <<'PY'
import sys, os
sys.path.insert(0, "bot")
os.environ["FREE_PROPOSE"] = "1"
os.environ["VOLUME_MODE"] = "EXPLOSION"
os.environ["HUB_ORCHESTRATOR"] = "1"
import lux_chat_watchdog as cw
assert cw.apply()
s = "🔷 G2 ESTUDO | @robobacbodados\n🔵 BLUE G0 🟡 Empate 🔥 | 📊 NEUTRO 1.09"
assert cw.estudo_blocked(s), "estudo must block"
s_zw = "🔷 G2\u200b ESTUDO | @robobacbodados\n🔵 BLUE G0 | 📊 NEUTRO 1.09"
assert cw.estudo_blocked(s_zw), "zw estudo must block"
s_baixa = "🔷 G2 ESTUDO | @M8SINAIS\n🔴 RED G0 | 🟡 BAIXA 0.67"
assert cw.estudo_blocked(s_baixa), "BAIXA estudo must block"
s_flood = "🔷 G2 ESTUDO | @martinswinbacbo / @robobacbodados / @sinaisbacboangola"
assert cw.estudo_blocked(s_flood), "multi-handle estudo flood must block"
s_spaced = "🔷 G2 E S T U D O | @robobacbodados\n🔵 BLUE G0"
assert cw.estudo_blocked(s_spaced), "spaced ESTUDO must block"
assert not cw.estudo_blocked("💎 SOLO ELITE\nENTER NOW")
ok, why = cw.gate_outbound(msg=s, path="selftest", final=True)
assert ok is False and why == "ESTUDO", (ok, why)
# Immediate CALL arm helper must exist (closes pre-settle leak window)
assert callable(cw.arm_call_wrap_immediate)
print("IMMEDIATE_CALL_ARM_API_OK")
ok2, why2 = cw.gate_outbound(
    msg="💎 SOLO ELITE\nENTER NOW", path="selftest", final=True
)
assert ok2 is True, (ok2, why2)
# Nested Invoke* → SendMessageRequest must be visible to CALL wrap helpers
class _Send:
    def __init__(self):
        self.message = s_baixa
        self.peer = "UNIQUE_g1"
class _Invoke:
    def __init__(self, inner):
        self.query = inner
assert any(
    type(r).__name__ == "_Send" for r in cw._iter_tl_requests(_Invoke(_Send()))
)
assert cw._request_text(_Send()) == s_baixa
# Force CALL wrap install (post-settle path) when Telethon present
try:
    import telethon  # noqa: F401
    assert cw.install_call_wrap(force_env=True)
    print("CALL_WRAP_INSTALL_OK")
except ImportError:
    print("CALL_WRAP_INSTALL_SKIP")
print("CHAT_WATCHDOG_OK", cw.snapshot())
from lux_send_config_bind import _estudo_blocked, _dedup_hit
assert _estudo_blocked(s), "bind estudo must block"
a = "🔷 X\n🔵 BLUE G0 | 📊 NEUTRO 1.07"
b = "🔷 X\n🔵 BLUE G0 | 📊 NEUTRO 0.81"
assert _dedup_hit(a) is False
assert _dedup_hit(b) is True
print("ESTUDO_SELFTEST_OK")
from config.keep_allowlist import should_block_as_trash
hit, why = should_block_as_trash(text=s)
assert hit, why
print("TRASH_SELFTEST_OK", why)
# Corrupted _SOLO_GLOBAL_BAD_UTC (float) must be repaired — was killing AccumHold FIRE
import types
import lux_no_hour_blocks as nhb
import lux_re_harden as rh
fake = types.ModuleType("signal_handler_selftest")
fake._SOLO_GLOBAL_BAD_UTC = 18.0  # live crash shape
sys.modules["signal_handler_selftest"] = fake
assert nhb.neutralize_module(fake) >= 1
assert isinstance(fake._SOLO_GLOBAL_BAD_UTC, (set, frozenset))
assert (18 in fake._SOLO_GLOBAL_BAD_UTC) is False
# re-harden must NOT turn setish names into floats
ns = {"_SOLO_GLOBAL_BAD_UTC": "", "_ACCUM_HOLD_SECS": ""}
fixed = rh.harden_namespace(ns, label="selftest")
assert isinstance(ns["_SOLO_GLOBAL_BAD_UTC"], frozenset), ns
assert isinstance(ns["_ACCUM_HOLD_SECS"], (int, float)), ns
print("SOLO_BAD_UTC_REPAIR_OK", fixed)
from lux_state_heal import default_expr
assert default_expr("_rooms") == "{}"
assert default_expr("_lock") == "asyncio.Lock()"
print("ROOMS_DICT_DEFAULT_OK")
# Empty TARGET must never reach Telethon (was: send() failed entity "")
import types as _types
import hub_engine_route as her
os.environ["HUB_MAX"] = "1"
os.environ["HUB_ENGINE_ROUTE"] = "1"
os.environ.setdefault("TELEGRAM_PRIMARY_PEER", "UNIQUE_g1")
os.environ.setdefault("TELEGRAM_GUNIQUE_PEER_ID", "5855678138")
assert her._as_target("") is None
assert her._valid_target("") is False
assert her._valid_target("@UNIQUE_g1") is True
apex = her.apex_target()
assert her._valid_target(apex), apex
cfg = _types.SimpleNamespace(TARGET="")
her.ensure_config_target(cfg)
assert her._valid_target(cfg.TARGET), cfg.TARGET
her.apply_target_to_config(cfg, "")
assert her._valid_target(cfg.TARGET), cfg.TARGET
dest, why = her.pick_target_for_text("🔥 SEQUENCE blue streak\nENTER NOW")
assert her._valid_target(dest), (dest, why)
from lux_send_config_bind import _coerce_empty_entity
coerced_args, coerced_kwargs = _coerce_empty_entity(("", "test"), {})
assert her._valid_target(coerced_args[0]), coerced_args
coerced_args2, coerced_kwargs2 = _coerce_empty_entity((), {"entity": "", "message": "test"})
assert her._valid_target(coerced_kwargs2["entity"]), coerced_kwargs2
print("EMPTY_TARGET_REPAIR_OK", dest, why, "telethon_coerce=OK")
# All live card timestamps must be Pawtucket, Rhode Island (DST-aware).
from card_timezone import pawtucket_forensic, pawtucket_time
assert pawtucket_time("2026-08-11 15:56:00") == "11:56"
assert pawtucket_forensic("2026-08-11 15:56:00").endswith("EDT")
assert pawtucket_forensic("2026-01-11 15:56:00").endswith("EST")
print("PAWTUCKET_TIME_OK", pawtucket_forensic("2026-08-11 15:56:00"))
# Card display is Pawtucket, but the ENGINE clock must stay exactly as the
# original system. local_hour() drives hour gates and countdown targets, so a
# zone change here shifts every timed card. Display must never retune logic.
import tz_utils
assert tz_utils.DISPLAY_TZ == "America/Sao_Paulo", (
    f"engine clock drifted to {tz_utils.DISPLAY_TZ}; countdown timing would shift"
)
print("ENGINE_TZ_OK", tz_utils.DISPLAY_TZ, "local_hour", tz_utils.local_hour())
# TL constructor + source kill APIs
assert callable(cw._patch_tl_constructors)
assert callable(cw.EstudoBlocked)
import lux_estudo_source_kill as esk
def _fake_estudo_emit(msg="🔷 G2 ESTUDO | @x"):
    return msg
class _M: pass
_m = _M()
_m.emit_estudo_card = _fake_estudo_emit
assert esk.neutralize_module(_m, label="t") >= 1
assert getattr(_m.emit_estudo_card, "_lux_estudo_source_killed", False)
print("ESTUDO_SOURCE_KILL_OK")
from hub_orchestrator import orchestrate
dec = orchestrate([
    {"floor": "JUN19", "color": "red", "score": 90, "window_id": "t1"},
    {"floor": "MAY10", "color": "red", "score": 70, "window_id": "t1"},
    {"floor": "LIVE", "color": "blue", "score": 95, "window_id": "t1"},
])
assert dec["color"] == "red", dec  # 90+70 beats single 95
assert dec["primary"]["floor"] == "JUN19", dec
assert len(dec["spill"]) == 1 and dec["spill"][0]["floor"] == "MAY10"
assert len(dec["dropped_opp"]) == 1
assert "blue" in (dec.get("opp_locked_colors") or []), dec
assert dec.get("color_map", {}).get("red"), dec
print("HUB_ORCH_OK", dec["why"], "lock", dec.get("opp_locked_colors"))
# EMANATION: factual color overrides committee when known
from config.emanation_laws import (
    chat_hermetic,
    color_truth_factual,
    factual_color_from_outcome,
    law_banner as em_banner,
    signal_bundle_vertical,
)
assert color_truth_factual() and signal_bundle_vertical() and chat_hermetic()
assert factual_color_from_outcome("blue", "loss") == "red"
assert factual_color_from_outcome("red", "win") == "red"
fact_dec = orchestrate(
    [
        {"floor": "JUN19", "color": "red", "score": 90, "window_id": "t2"},
        {"floor": "LIVE", "color": "blue", "score": 95, "window_id": "t2"},
    ],
    factual_color="blue",
)
assert fact_dec["color"] == "blue", fact_dec
assert fact_dec.get("color_truth") == "FACTUAL", fact_dec
print("EMANATION_OK", em_banner(), fact_dec["why"])
from hub_impact_learner import (
    observe_result,
    observe_fire,
    floor_boost,
    resourcefulness_snapshot,
    understand_lock_matrix,
)
observe_fire(
    signal_id="s1",
    floors=["SOLO_GATE"],
    rooms=["a1sinais"],
    color="blue",
    kind="SOLO",
    mode="SINGULAR",
)
observe_fire(
    signal_id="c1",
    floors=["JUN19", "MAY10"],
    rooms=["robobacbodados", "m8sinais"],
    color="red",
    kind="GOLDEN",
    mode="COALITION",
)
observe_result(
    signal_id="c1",
    outcome="win",
    predicted="red",
    floors=["JUN19", "MAY10"],
    rooms=["robobacbodados", "m8sinais"],
    kind="GOLDEN",
    origin="COALITION",
    mode="COALITION",
    primary_floor="JUN19",
    opp_locked_floors=["LIVE"],
    actual_color="red",
)
snap = resourcefulness_snapshot()
matrix = understand_lock_matrix()
assert floor_boost("JUN19") >= 50.0
assert snap.get("opportunities"), snap
print("IMPACT_LEARN_OK", "JUN19", floor_boost("JUN19"), "mode", dec.get("mode"))
print("RESOURCEFUL", snap.get("emanate"), "opp", snap.get("opportunities"))
print("LOCK_MATRIX", matrix.get("opportunities"), "n_dec", len(matrix.get("recent_decisions") or []))
import lux_dialog_resolve as dr
assert dr.apply()
print("DIALOG_RESOLVE_OK")
import hub_max_boot
print("HUB_BOOT", hub_max_boot.apply())
PY

echo "-- restart --"
# Mark log so we ignore stale SyntaxError/NameError lines
echo "===== ONE_CMD ${V} restart $(date -u +%Y-%m-%dT%H:%M:%SZ) =====" >> logs/bot_live.log
# Kill competing stacks that SIGKILL bacbo mid-subscribe (code=-9)
# NOTE: never kill lux_babysitter.sh — it keeps supervisor alive after Shell close
pkill -TERM -f 'REPLIT_ONE_STACK|REPLIT_FIX_|REPLIT_FIRE|REPLIT_PEAK|REPLIT_LUXURY|start_luxury' 2>/dev/null || true
# Graceful stop first (SIGTERM) so Telethon can release AuthKey
pkill -TERM -f 'runtime_supervisor.py|bacbo_royal_complete.py|telegram_outbox.py|run_bacbo_live.py|museum_unique_poster.py|museum_first5_poster.py|museum_chrono_poster.py|fallback_signal_sender.py|fallback_result_sender.py' 2>/dev/null || true
sleep 6
pkill -KILL -f 'runtime_supervisor.py|bacbo_royal_complete.py|telegram_outbox.py|run_bacbo_live.py|museum_unique_poster.py|museum_first5_poster.py|museum_chrono_poster.py|fallback_signal_sender.py|fallback_result_sender.py' 2>/dev/null || true
rm -f bot/data/runtime_supervisor.lock bot/data/telegram_outbox.lock 2>/dev/null || true
# CRITICAL: Telegram holds AuthKey after kill — do NOT reconnect in 2s
echo "-- AuthKey settle 35s after kill (prevents mid-subscribe kick loop) --"
sleep 35
# Free memory + show cgroup limit (host free≠cgroup max)
$PY - <<'PY' || true
import gc, pathlib
gc.collect()
print("GC_OK")
for p in (
    pathlib.Path("/sys/fs/cgroup/memory.max"),
    pathlib.Path("/sys/fs/cgroup/memory/memory.limit_in_bytes"),
    pathlib.Path("/sys/fs/cgroup/memory.high"),
):
    if p.is_file():
        print(f"CGROUP {p}={p.read_text().strip()}")
PY
free -m 2>/dev/null | head -n 2 || true
# Strip PORT from this shell so children cannot steal Replit web fd
unset PORT REPLIT_SOCKET REPLIT_SOCKETS REPLIT_PORT 2>/dev/null || true
export LUX_KEEPALIVE_OFF=1 LUX_FLASK_GUARD=1 FLASK_DEBUG=0
# setsid: survive Replit Shell tab close (bare nohup still dies with session)
setsid $PY -u bot/runtime_supervisor.py >>/tmp/luxury_supervisor.log 2>&1 </dev/null &
# Babysitter restarts supervisor if the whole process tree vanishes
chmod +x bot/lux_babysitter.sh 2>/dev/null || true
if ! pgrep -f '[l]ux_babysitter.sh' >/dev/null 2>&1; then
  setsid bash bot/lux_babysitter.sh >>logs/babysitter.log 2>&1 </dev/null &
  echo "babysitter armed pid=$!"
else
  echo "babysitter already running"
fi
# Supervisor cold-starts then spawns bacbo (KeepAlive OFF)
echo "-- wait supervisor cold-start + bacbo connect (~90s) --"
sleep 90
echo "-- wait bacbo STAY UP (expect NO KeepAlive bind; SIGKILL was PORT steal) --"
pkill -TERM -f 'telegram_outbox.py' 2>/dev/null || true
pkill -TERM -f 'museum_unique_poster.py|museum_first5_poster.py|museum_chrono_poster.py' 2>/dev/null || true
BACBO_STABLE=0
INLINE_OK=0
INLINE_STARTED=0
ALIVE_STREAK=0
for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24; do
  if pgrep -f 'run_bacbo_live.py' >/dev/null 2>&1; then
    ALIVE_STREAK=$((ALIVE_STREAK + 1))
    BACBO_STABLE=1
    if awk "/ONE_CMD ${V} restart/{flag=1;next} flag" logs/bot_live.log 2>/dev/null \
      | grep -qE 'OUTBOX-INLINE\] starting on bacbo client|\[Outbox\] HEARTBEAT|CHAT-WATCH __call__ gate armed'; then
      INLINE_STARTED=1
      INLINE_OK=1
      if [[ "$ALIVE_STREAK" -ge 6 ]]; then
        echo "BACBO_STABLE+OUTBOX_STARTED streak=${ALIVE_STREAK} t=~$((90 + i * 5))s"
        break
      fi
      echo "OUTBOX_STARTED waiting streak>=6 (now ${ALIVE_STREAK}) t=~$((90 + i * 5))s"
    elif awk "/ONE_CMD ${V} restart/{flag=1;next} flag" logs/bot_live.log 2>/dev/null \
      | grep -qE 'OUTBOX-INLINE\] (scheduled|boot task|settle heartbeat|CHAT-WATCH)|rss_heartbeat|dialogs warm SKIP'; then
      INLINE_OK=1
      echo "BACBO_STABLE+BOOTING streak=${ALIVE_STREAK} t=~$((90 + i * 5))s"
    else
      echo "BACBO_STABLE streak=${ALIVE_STREAK} t=~$((90 + i * 5))s"
    fi
  else
    ALIVE_STREAK=0
    BACBO_STABLE=0
    # If supervisor is mid AuthKey settle, this is expected — do not panic
    if grep -q 'AuthKey settle\|SIGKILL cool-down\|cold-start AuthKey' /tmp/luxury_supervisor.log 2>/dev/null \
      && ! grep -qE 'starting/restarting bot_live$' /tmp/luxury_supervisor.log 2>/dev/null; then
      echo "bacbo down — supervisor settling t=~$((90 + i * 5))s"
    else
      echo "bacbo not up yet / flapping t=~$((90 + i * 5))s"
    fi
    # Surface -9 quickly
    if grep -q 'code=-9' /tmp/luxury_supervisor.log 2>/dev/null; then
      echo "WARN: saw exit code=-9 (SIGKILL) — if KeepAlive still binds PORT, patch failed"
    fi
  fi
  sleep 5
done

echo "---- procs ----"
pgrep -af 'runtime_supervisor|telegram_outbox|bacbo_royal|run_bacbo_live|museum_' || true
if pgrep -f 'telegram_outbox.py' >/dev/null 2>&1; then
  echo "WARN: standalone telegram_outbox still running — killing (AuthKey risk)"
  pkill -TERM -f 'telegram_outbox.py' 2>/dev/null || true
fi
echo "---- bot_live (post-restart only) ----"
awk "/ONE_CMD ${V} restart/{flag=1;next} flag" logs/bot_live.log 2>/dev/null | tail -n 80 || tail -n 40 logs/bot_live.log
echo "---- fresh errors / gate ----"
awk "/ONE_CMD ${V} restart/{flag=1;next} flag" logs/bot_live.log 2>/dev/null \
  | grep -E 'NameError|SyntaxError|Traceback|rss_heartbeat|dialogs warm|OUTBOX-INLINE|FLASK-GUARD|KEEPALIVE|AuthKey|SESSION-GUARD|code=-9|SIGKILL|got SIGTERM|EXITING|DROP ESTUDO|KeepAlive' \
  | tail -n 80 || true
echo "---- supervisor ----"
tail -n 60 /tmp/luxury_supervisor.log 2>/dev/null || true
echo "---- memory ----"
free -m 2>/dev/null || true

# Final recheck — do NOT kill supervisor if it is mid-settle/restart (that caused thrash)
echo "-- final alive recheck (90s) — must survive subscribe + outbox settle --"
sleep 90
pkill -TERM -f 'telegram_outbox.py' 2>/dev/null || true
pkill -TERM -f 'museum_unique_poster.py|museum_first5_poster.py|museum_chrono_poster.py' 2>/dev/null || true
if ! pgrep -f 'run_bacbo_live.py' >/dev/null 2>&1; then
  if pgrep -f 'runtime_supervisor.py' >/dev/null 2>&1; then
    echo "BACBO_DOWN_BUT_SUPERVISOR_ALIVE — letting supervisor recover (no hard kick)"
    # Wait one more recovery window (cool-down + settle + boot)
    sleep 120
  else
    echo "BACBO_DIED_AFTER_BOOT — supervisor dead; one clean restart"
    rm -f bot/data/runtime_supervisor.lock 2>/dev/null || true
    sleep 20
    setsid $PY -u bot/runtime_supervisor.py >>/tmp/luxury_supervisor.log 2>&1 </dev/null &
    sleep 120
  fi
fi
echo "---- procs (final) ----"
pgrep -af 'lux_babysitter|runtime_supervisor|telegram_outbox|run_bacbo_live' || true
echo "---- exit markers ----"
awk "/ONE_CMD ${V} restart/{flag=1;next} flag" logs/bot_live.log 2>/dev/null \
  | grep -E 'SESSION-GUARD|FLASK-GUARD|KEEPALIVE|atexit|EXITING|rss_heartbeat|AuthKey|FATAL|boot task|settle heartbeat|starting on bacbo|got SIGTERM|dialogs warm|KeepAlive' \
  | tail -n 50 || true

BACBO_ALIVE=0
pgrep -f 'run_bacbo_live.py|bacbo_royal_complete.py' >/dev/null && BACBO_ALIVE=1
SUP_ALIVE=0
pgrep -f 'runtime_supervisor.py' >/dev/null && SUP_ALIVE=1
if [[ "$BACBO_ALIVE" -eq 1 ]]; then
  if awk "/ONE_CMD ${V} restart/{flag=1;next} flag" logs/bot_live.log 2>/dev/null | grep -q "NameError: name 'state'"; then
    echo "BACBO_UP_BUT_STATE_NAMEERROR"
    exit 1
  fi
  echo "BACBO_UP"
else
  echo "BACBO_DOWN — see tails above (if code=-9: Replit OOM / external SIGKILL)"
  exit 1
fi
if [[ "$SUP_ALIVE" -ne 1 ]]; then
  echo "SUPERVISOR_DOWN"
  exit 1
fi
# Robust outbox detect — marker awk can miss when log rotates / multi-restart.
# Live proofs: starting on bacbo | HEARTBEAT | CALL gate armed | money=UNIQUE_g1
POST_LOG=$(awk "/ONE_CMD ${V} restart/{flag=1;next} flag" logs/bot_live.log 2>/dev/null || true)
if echo "$POST_LOG" | grep -qE 'OUTBOX-INLINE\] starting on bacbo client|\[Outbox\] HEARTBEAT|CHAT-WATCH __call__ gate armed|money=UNIQUE_g1'; then
  INLINE_STARTED=1
elif grep -qE 'OUTBOX-INLINE\] starting on bacbo client|\[Outbox\] HEARTBEAT' logs/bot_live.log 2>/dev/null; then
  # Fall back to whole log if marker slice empty but outbox clearly ran this boot
  INLINE_STARTED=1
fi
if [[ "$INLINE_STARTED" -eq 1 ]]; then
  echo "OUTBOX_INLINE_OK"
elif echo "$POST_LOG" | grep -qE 'OUTBOX-INLINE\] (scheduled|boot task|settle heartbeat|CHAT-WATCH)'; then
  echo "OUTBOX_INLINE_SETTLING — bacbo up but outbox not started yet; recheck in 60s"
elif [[ "$BACBO_ALIVE" -eq 1 ]]; then
  echo "OUTBOX_INLINE_PENDING — check logs for [OUTBOX-INLINE]"
else
  echo "OUTBOX_INLINE_NO_BACBO"
fi
echo "========== DONE =========="
echo "Expect: BACBO_UP + OUTBOX_INLINE_OK; pgrep: babysitter|supervisor|run_bacbo_live"
echo "Recheck: pgrep -af 'lux_babysitter|runtime_supervisor|run_bacbo_live'"
echo "If empty later (Shell closed / Replit sleep): bash REPLIT_UP_NOW.sh"
echo "Enable Replit Always On if the whole VM sleeps when idle."
echo "Logs: grep -E 'KEEPALIVE|OUTBOX-INLINE|starting on bacbo|money=' logs/bot_live.log | tail -n 40"
