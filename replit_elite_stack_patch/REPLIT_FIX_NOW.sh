#!/usr/bin/env bash
# Restore working luxury bacbo: keep SESSION_AND_BIND / re-apply if clean bak.
set -euo pipefail
cd /home/runner/workspace

SHA="${LUXURY_PATCH_SHA:-cursor/add-engine-gate-registry-d5ba}"
BASE="https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/${SHA}/replit_elite_stack_patch"
PY=python3

echo "========== [1/4] stop =========="
pkill -9 -f 'bacbo_royal_complete.py' 2>/dev/null || true
pkill -9 -f 'runtime_supervisor.py' 2>/dev/null || true
pkill -9 -f 'fallback_signal_sender.py' 2>/dev/null || true
pkill -9 -f 'fallback_result_sender.py' 2>/dev/null || true
sleep 2

echo "========== [2/4] download =========="
mkdir -p bot/data logs
curl -fsSL -H "Cache-Control: no-cache" -o bot/lux_sqlite_harden.py "$BASE/bot/lux_sqlite_harden.py"
curl -fsSL -H "Cache-Control: no-cache" -o bot/runtime_supervisor.py "$BASE/bot/runtime_supervisor.py"
$PY -m py_compile bot/lux_sqlite_harden.py bot/runtime_supervisor.py

echo "========== [3/4] pick best source + patch =========="
$PY <<'PY'
import ast, re, sqlite3
from pathlib import Path

ROOT = Path("/home/runner/workspace")
p = ROOT / "bacbo_royal_complete.py"

def parses(t: str):
    try:
        ast.parse(t)
        return True, None
    except SyntaxError as e:
        return False, str(e)

def score(path: Path, t: str) -> int:
    """Higher = better luxury-ready source."""
    s = 0
    if "LUXURY_SESSION_AND_BIND" in t:
        s += 100
    if "state = _lux_state_mod" in t:
        s += 50
    if "LUXURY_GET_ENTITY_MONKEYPATCH" in t:
        s += 40
    if "LUXURY_SQLITE_HARDEN" in t:
        s += 10
    if path.name == "bacbo_royal_complete.py":
        s += 5
    # clean pre-state bak is worst if we have alternatives
    if "bak_pre_state_fix" in path.name:
        s -= 30
    s += min(path.stat().st_size // 100000, 30)
    return s

cands = []
for c in [p] + sorted(ROOT.glob("bacbo_royal_complete.py.bak*"), key=lambda x: x.stat().st_mtime, reverse=True):
    if not c.exists():
        continue
    t = c.read_text(encoding="utf-8", errors="replace")
    good, err = parses(t)
    sc = score(c, t) if good else -10**9
    print(f"candidate {c.name} parse={'OK' if good else 'BAD'} score={sc} {'' if good else err}")
    if good:
        cands.append((sc, c, t))

if not cands:
    raise SystemExit("FATAL: no parseable bacbo source")

cands.sort(key=lambda x: x[0], reverse=True)
sc, src_path, text = cands[0]
print("USING", src_path.name, "score", sc, "size", len(text))

# backup current
if p.exists():
    bak = ROOT / "bacbo_royal_complete.py.bak_before_fixnow3"
    if not bak.exists():
        bak.write_text(p.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")

# Strip markers we re-apply (not SESSION_AND_BIND / GET_ENTITY if already present — refresh harden/force/crashguard only)
for marker in ("LUXURY_SQLITE_HARDEN", "LUXURY_CRASHGUARD_DBLOCK", "LUXURY_STATE_NAME_FORCE"):
    text = re.sub(
        rf"\n# --- {marker} \(auto\) ---.*?--- end {marker} ---\n",
        "\n",
        text,
        flags=re.S,
    )

# --- get_entity monkeypatch if missing ---
if "LUXURY_GET_ENTITY_MONKEYPATCH" not in text:
    monkey = r'''
# --- LUXURY_GET_ENTITY_MONKEYPATCH (auto) ---
try:
    import json as _lux_json
    from pathlib import Path as _LuxPath
    from telethon import TelegramClient as _LuxTGClient
    from telethon.tl.types import InputPeerUser, InputPeerChannel, InputPeerChat
    from telethon.errors import FloodWaitError as _LuxFloodWait

    def _lux_cache_rec(username):
        try:
            p = _LuxPath("/home/runner/workspace/bot/data/room_entity_cache.json")
            data = _lux_json.loads(p.read_text(encoding="utf-8"))
            m = data.get("by_username") or {}
            key = str(username or "").strip().lower()
            for k in (key, key.lstrip("@"), "@" + key.lstrip("@")):
                if k in m:
                    return m[k]
        except Exception:
            return None
        return None

    def _lux_input_peer(rec):
        if not isinstance(rec, dict):
            return None
        et = rec.get("type")
        ah = rec.get("access_hash")
        raw = rec.get("raw_id")
        peer_id = rec.get("peer_id")
        if et == "channel" and raw is not None and ah is not None:
            return InputPeerChannel(int(raw), int(ah))
        if et == "user" and raw is not None and ah is not None:
            return InputPeerUser(int(raw), int(ah))
        if et == "chat" and raw is not None:
            return InputPeerChat(int(raw))
        if peer_id is not None:
            return int(peer_id)
        return None

    _lux_orig_get_entity = _LuxTGClient.get_entity

    async def _lux_get_entity(self, entity):
        if not getattr(self, "_lux_dialogs_warmed", False):
            try:
                async for _ in self.iter_dialogs():
                    pass
            except Exception as e:
                print("[LUXURY] dialog warm failed:", e)
            self._lux_dialogs_warmed = True

        if isinstance(entity, str) and not str(entity).lstrip("-").isdigit():
            rec = _lux_cache_rec(entity)
            if rec is not None:
                inp = _lux_input_peer(rec)
                if inp is not None:
                    try:
                        return await _lux_orig_get_entity(self, inp)
                    except Exception as e1:
                        try:
                            return await _lux_orig_get_entity(self, int(rec["peer_id"]))
                        except Exception as e2:
                            print(f"[LUXURY] cache resolve failed for {entity}: {e1!r} / {e2!r}")
                            raise
            raise ValueError(f"LUXURY_SKIP_RESOLVE_USERNAME:{entity}")

        try:
            return await _lux_orig_get_entity(self, entity)
        except _LuxFloodWait:
            raise

    _LuxTGClient.get_entity = _lux_get_entity  # type: ignore
    print("[LUXURY] get_entity: dialog cache + InputPeer (no ResolveUsername for @rooms)")
except Exception as _lux_mp_exc:
    print("[LUXURY] get_entity monkeypatch skipped:", _lux_mp_exc)
# --- end LUXURY_GET_ENTITY_MONKEYPATCH ---
'''
    lines = text.splitlines(True)
    idx = 0
    for i, ln in enumerate(lines[:120]):
        if "telethon" in ln and (ln.startswith("import ") or ln.startswith("from ")):
            idx = i + 1
    if idx == 0:
        idx = 30
    lines.insert(idx, monkey + "\n")
    text = "".join(lines)
    print("injected GET_ENTITY monkeypatch")

# --- SESSION_AND_BIND if missing (THIS fixes state.client NameError) ---
if "LUXURY_SESSION_AND_BIND" not in text:
    bind = r'''
# --- LUXURY_SESSION_AND_BIND (auto) ---
try:
    import os as _lux_os
    from pathlib import Path as _LuxPath
    _sf = _LuxPath("/home/runner/workspace/.telegram_session_string")
    if _sf.exists():
        _sv = _sf.read_text(errors="ignore").strip()
        if len(_sv) > 50:
            _lux_os.environ["TELEGRAM_SESSION_STRING"] = _sv
            try:
                from telethon.sessions import StringSession as _LuxSS
                _session = _LuxSS(_sv)
            except Exception:
                pass
except Exception as _lux_sess_exc:
    print("[LUXURY] session force skipped:", _lux_sess_exc)

import state as _lux_state_mod
_lux_prev_client = getattr(_lux_state_mod, "client", None)
_lux_state_mod.client = TelegramClient(_session, API_ID, API_HASH, sequential_updates=False)
try:
    if hasattr(_lux_prev_client, "bind"):
        _lux_prev_client.bind(_lux_state_mod.client)
except Exception as _lux_bind_exc:
    print("[LUXURY] proxy bind failed:", _lux_bind_exc)
state = _lux_state_mod
# --- end LUXURY_SESSION_AND_BIND ---
'''
    m = re.search(r"^state\.client\s*=\s*TelegramClient\([^\n]*\)\s*$", text, re.M)
    if not m:
        raise SystemExit("missing state.client = TelegramClient(...) line to replace")
    text = text[: m.start()] + bind + "\n" + text[m.end() :]
    print("injected SESSION_AND_BIND (replaces state.client=)")
else:
    # ensure state= present inside bind
    chunk = text.split("LUXURY_SESSION_AND_BIND", 1)[1][:900]
    if "state = _lux_state_mod" not in chunk:
        text = text.replace(
            'print("[LUXURY] proxy bind failed:", _lux_bind_exc)\n# --- end LUXURY_SESSION_AND_BIND ---',
            'print("[LUXURY] proxy bind failed:", _lux_bind_exc)\nstate = _lux_state_mod\n# --- end LUXURY_SESSION_AND_BIND ---',
        )
        print("added state= into existing SESSION_AND_BIND")

# --- sqlite harden ---
harden = (
    "\n# --- LUXURY_SQLITE_HARDEN (auto) ---\n"
    "try:\n"
    "    import lux_sqlite_harden  # noqa: F401\n"
    '    print("[LUXURY] sqlite harden applied (WAL/busy_timeout/retry)")\n'
    "except Exception as _lux_sql_exc:\n"
    '    print("[LUXURY] sqlite harden skipped:", _lux_sql_exc)\n'
    "# --- end LUXURY_SQLITE_HARDEN ---\n"
)
lines = text.splitlines(True)
idx = 0
for i, ln in enumerate(lines):
    if "[BOOT] all imports OK" in ln or "[BOOT] stdlib imports OK" in ln:
        idx = i + 1
        break
if idx == 0:
    idx = min(40, len(lines))
lines.insert(idx, harden)
text = "".join(lines)

# --- state force before state.engine ---
force = (
    "# --- LUXURY_STATE_NAME_FORCE (auto) ---\n"
    "import state as _lux_state_mod\n"
    "state = _lux_state_mod\n"
    "# --- end LUXURY_STATE_NAME_FORCE ---\n"
)
if re.search(r"^state\.engine\s*=", text, re.M):
    text = re.sub(r"^(state\.engine\s*=)", force + r"\1", text, count=1, flags=re.M)
    print("state force before state.engine")

# --- CrashGuard soft DB lock ---
if "LUXURY_CRASHGUARD_DBLOCK" not in text:
    m = re.search(
        r"^([ \t]*)log\.error\(\s*\n[ \t]*f\"\[CrashGuard\] Bot crashed \(attempt #\{_consecutive_failures\}\): \{exc\}\.",
        text,
        flags=re.M,
    )
    if m:
        ind = m.group(1)
        block = (
            ind + "# --- LUXURY_CRASHGUARD_DBLOCK (auto) ---\n"
            + ind + 'if "database is locked" in str(exc).lower() or "database is busy" in str(exc).lower():\n'
            + ind + '    log.warning("[CrashGuard] soft DB lock (no reconnect): %s", exc)\n'
            + ind + "    await asyncio.sleep(2)\n"
            + ind + "    continue\n"
            + ind + "# --- end LUXURY_CRASHGUARD_DBLOCK ---\n"
        )
        text = text[: m.start()] + block + text[m.start() :]
        print("injected CRASHGUARD_DBLOCK")

good, err = parses(text)
if not good:
    raise SystemExit(f"patched invalid: {err}")

# Verify state is defined before first state.client / state.engine use at module level
# Quick check: SESSION_AND_BIND or state = _lux must appear before state.client=
pos_bind = text.find("state = _lux_state_mod")
pos_client = text.find("state.client")
# After bind replace, state.client assign is inside bind as _lux_state_mod.client
if "LUXURY_SESSION_AND_BIND" not in text:
    raise SystemExit("SESSION_AND_BIND missing after patch")
if pos_bind < 0:
    raise SystemExit("state = _lux_state_mod missing")

p.write_text(text, encoding="utf-8")
print("WROTE", p.stat().st_size)
print("has_session_bind", "LUXURY_SESSION_AND_BIND" in text)
print("has_get_entity", "LUXURY_GET_ENTITY_MONKEYPATCH" in text)
print("has_harden", "LUXURY_SQLITE_HARDEN" in text)
print("has_state_force", "LUXURY_STATE_NAME_FORCE" in text)

# show lines around bind end
lines = text.splitlines()
for i, ln in enumerate(lines):
    if "LUXURY_SESSION_AND_BIND" in ln or (ln.strip() == "state = _lux_state_mod" and i < 200):
        a, b = max(0, i - 2), min(len(lines), i + 8)
        print(f"----- {a+1}-{b} -----")
        for j in range(a, b):
            print(f"{j+1}: {lines[j][:140]}")
        if "state = _lux_state_mod" in ln:
            break

db = ROOT / "bot" / "bacbo.db"
if db.exists():
    con = sqlite3.connect(str(db), timeout=60)
    print("journal_mode", con.execute("PRAGMA journal_mode=WAL").fetchone()[0])
    con.close()
PY

echo "========== compile =========="
$PY -m py_compile bacbo_royal_complete.py
echo "compile OK"

echo "========== [4/4] restart =========="
set -a
source ./luxury_building.env 2>/dev/null || true
set +a
export TELEGRAM_SESSION_STRING="$(tr -d '\n' < .telegram_session_string 2>/dev/null || true)"
export TELEGRAM_TARGET_PEER="${TELEGRAM_TARGET_PEER:-6774605259}"
export FALLBACKS_ENABLED=0
export EDGE_POLICY_MODE=luxury
export EDGE_LUXURY_FLOOR_GATE=1
export BOT_TZ=America/Sao_Paulo
export PYTHONPATH="/home/runner/workspace/bot:/home/runner/workspace:${PYTHONPATH:-}"

echo "===== FIX_NOW3 marker $(date -u +%Y-%m-%dT%H:%M:%SZ) =====" >> logs/bot_live.log

nohup env EDGE_POLICY_MODE=luxury EDGE_LUXURY_FLOOR_GATE=1 FALLBACKS_ENABLED=0 \
  BOT_TZ=America/Sao_Paulo \
  TELEGRAM_SESSION_STRING="$TELEGRAM_SESSION_STRING" \
  TELEGRAM_TARGET_PEER="$TELEGRAM_TARGET_PEER" \
  PYTHONPATH="$PYTHONPATH" \
  python3 -u bot/runtime_supervisor.py > /tmp/luxury_supervisor.log 2>&1 &
echo "supervisor pid=$!"

sleep 20
echo "----- 20s -----"
pgrep -af 'runtime_supervisor|bacbo_royal' || true
sleep 35

$PY <<'PY'
from pathlib import Path
import re, subprocess
log = Path("logs/bot_live.log").read_text(errors="ignore")
idx = log.rfind("===== FIX_NOW3 marker")
chunk = log[idx:] if idx >= 0 else log[-8000:]
print("run_forever", "run_forever" in chunk or "starting run_forever()" in chunk)
print("harden", "sqlite harden applied" in chunk)
print("get_entity_patch", "get_entity: dialog cache" in chunk)
print("NameError_state", "NameError: name 'state'" in chunk)
print("CrashGuard", len(re.findall(r"\[CrashGuard\] Bot crashed", chunk)))
print("--- procs ---")
print(subprocess.getoutput("pgrep -af 'runtime_supervisor|bacbo_royal' || echo NONE"))
print("--- last 25 ---")
print("\n".join(Path("logs/bot_live.log").read_text(errors="ignore").splitlines()[-25:]))
procs = subprocess.getoutput("pgrep -af bacbo_royal || true")
ok = (
    ("run_forever" in chunk or "starting run_forever()" in chunk)
    and "bacbo_royal" in procs
    and "NameError: name 'state'" not in chunk
)
print("VERDICT:", "OK" if ok else "BAD — paste ALL output")
PY

echo
echo "DONE. Paste ALL output."
