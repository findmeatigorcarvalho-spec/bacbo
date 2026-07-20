#!/usr/bin/env bash
# Fix bot_live tz_utils API + Telegram session for fallback senders.
set -euo pipefail
cd /home/runner/workspace

echo "========== [1/5] rebuild root tz_utils (script-dir wins over PYTHONPATH) =========="
python3 - <<'PY'
from __future__ import annotations
import ast
import re
from pathlib import Path

ROOT = Path("/home/runner/workspace")
bot_tz = ROOT / "bot" / "tz_utils.py"
root_tz = ROOT / "tz_utils.py"

# Collect names imported from tz_utils across the project
needed: set[str] = set()
for p in list(ROOT.glob("*.py")) + list((ROOT / "bot").glob("*.py")):
    try:
        t = p.read_text(encoding="utf-8", errors="replace")
    except Exception:
        continue
    for m in re.finditer(r"from\s+tz_utils\s+import\s+([^\n]+)", t):
        chunk = m.group(1)
        # strip trailing comments
        chunk = chunk.split("#")[0]
        for part in chunk.split(","):
            part = part.strip()
            if not part or part.startswith("("):
                continue
            name = part.split(" as ")[0].strip()
            if name and name.isidentifier():
                needed.add(name)
print("needed_from_tz_utils", sorted(needed))

FULL = '''"""Timezone helpers for Bac Bo (root module — bacbo_royal_complete loads this first)."""
from __future__ import annotations

import os
from datetime import datetime, timezone

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None  # type: ignore

_BOT_TZ = os.environ.get("BOT_TZ") or os.environ.get("TZ_NAME") or "America/Sao_Paulo"


def _zone():
    if ZoneInfo is None:
        return timezone.utc
    try:
        return ZoneInfo(_BOT_TZ)
    except Exception:
        return timezone.utc


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def now_local() -> datetime:
    return datetime.now(tz=_zone())


# aliases used across modules
local_now = now_local


def local_hour(dt=None) -> int:
    if dt is None:
        return now_local().hour
    if getattr(dt, "tzinfo", None) is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(_zone()).hour


def today_iso(dt=None) -> str:
    if dt is None:
        return now_local().date().isoformat()
    if getattr(dt, "tzinfo", None) is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(_zone()).date().isoformat()


def ts(dt=None) -> str:
    """Compact local timestamp used in logs/cards."""
    d = now_local() if dt is None else dt
    if getattr(d, "tzinfo", None) is None:
        d = d.replace(tzinfo=timezone.utc).astimezone(_zone())
    else:
        d = d.astimezone(_zone())
    return d.strftime("%Y-%m-%d %H:%M:%S")


def dts(dt=None) -> str:
    """ISO-ish local datetime string."""
    d = now_local() if dt is None else dt
    if getattr(d, "tzinfo", None) is None:
        d = d.replace(tzinfo=timezone.utc).astimezone(_zone())
    else:
        d = d.astimezone(_zone())
    return d.isoformat(sep=" ", timespec="seconds")


def to_local(dt):
    if dt is None:
        return now_local()
    if getattr(dt, "tzinfo", None) is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(_zone())


def to_utc(dt):
    if dt is None:
        return now_utc()
    if getattr(dt, "tzinfo", None) is None:
        dt = dt.replace(tzinfo=_zone())
    return dt.astimezone(timezone.utc)
'''

# If bot/tz_utils exists and already defines most needed names, prefer copying it
use_bot = False
if bot_tz.exists():
    bt = bot_tz.read_text(encoding="utf-8", errors="replace")
    try:
        tree = ast.parse(bt)
        defined = {n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Assign))}
        # also capture simple assigns
        for n in tree.body:
            if isinstance(n, ast.Assign):
                for tgt in n.targets:
                    if isinstance(tgt, ast.Name):
                        defined.add(tgt.id)
            if isinstance(n, ast.FunctionDef):
                defined.add(n.name)
        missing_in_bot = [n for n in needed if n not in defined and n not in bt]
        print("bot_tz_defined_sample", sorted(list(defined))[:30], "missing_in_bot", missing_in_bot)
        if "now_local" in bt or "def now_local" in bt:
            # merge: start from bot file, append any missing helpers from FULL via exec check later
            use_bot = True
    except Exception as e:
        print("bot_tz parse skip", e)

bak = root_tz.with_suffix(".py.bak_pre_full_rebuild")
if root_tz.exists() and not bak.exists():
    bak.write_text(root_tz.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")

if use_bot:
    bt = bot_tz.read_text(encoding="utf-8", errors="replace")
    # Ensure critical aliases exist
    extras = []
    if "def now_local" not in bt and "now_local =" not in bt:
        if "def local_now" in bt:
            extras.append("\nnow_local = local_now\n")
        else:
            extras.append("\nfrom datetime import datetime, timezone\ntry:\n    from zoneinfo import ZoneInfo\nexcept Exception:\n    ZoneInfo=None\ndef now_local():\n    z=ZoneInfo('America/Sao_Paulo') if ZoneInfo else timezone.utc\n    return datetime.now(tz=z)\nlocal_now=now_local\n")
    for name, stub in [
        ("local_hour", "def local_hour(dt=None):\n    d=now_local() if dt is None else dt\n    return d.hour if hasattr(d,'hour') else now_local().hour\n"),
        ("today_iso", "def today_iso(dt=None):\n    d=now_local() if dt is None else dt\n    return d.date().isoformat()\n"),
        ("ts", "def ts(dt=None):\n    d=now_local() if dt is None else dt\n    return d.strftime('%Y-%m-%d %H:%M:%S')\n"),
        ("dts", "def dts(dt=None):\n    d=now_local() if dt is None else dt\n    return d.isoformat(sep=' ', timespec='seconds')\n"),
        ("local_now", "local_now = now_local\n"),
    ]:
        if name in needed and f"def {name}" not in bt and f"{name} =" not in bt:
            extras.append("\n" + stub)
    out = bt.rstrip() + "\n" + "".join(extras) + "\n"
    # Strip any mid-file __future__
    lines = out.splitlines(True)
    futures = [ln for ln in lines if ln.strip().startswith("from __future__")]
    body = [ln for ln in lines if not ln.strip().startswith("from __future__")]
    # drop leading blank/comment-only before placing future once
    out = "".join(futures[:1] or ["from __future__ import annotations\n"]) + "".join(body)
    # if future not first non-empty/doc/comment — rewrite cleanly with FULL instead
    try:
        compile(out, str(root_tz), "exec")
        root_tz.write_text(out, encoding="utf-8")
        print("wrote root tz_utils from bot/tz_utils + aliases")
    except SyntaxError as e:
        print("bot copy syntax fail, using FULL rebuild:", e)
        root_tz.write_text(FULL, encoding="utf-8")
else:
    root_tz.write_text(FULL, encoding="utf-8")
    print("wrote full root tz_utils.py")

# Also ensure bot/tz_utils has the same critical names (for bot.* imports)
if not bot_tz.exists() or "def now_local" not in bot_tz.read_text(encoding="utf-8", errors="replace"):
    # mirror root
    bot_tz.write_text(root_tz.read_text(encoding="utf-8"), encoding="utf-8")
    print("mirrored root -> bot/tz_utils.py")

# smoke import as bacbo does (cwd/script dir first)
import importlib
import sys
sys.path.insert(0, str(ROOT))
if "tz_utils" in sys.modules:
    del sys.modules["tz_utils"]
import tz_utils
print("loaded", tz_utils.__file__)
for n in sorted(needed) or ["now_local", "local_hour", "today_iso", "ts", "dts"]:
    ok = hasattr(tz_utils, n)
    print(f"  {n}: {'OK' if ok else 'MISSING'}")
    if not ok:
        raise SystemExit(f"tz_utils missing {n}")
print("tz_smoke_ok", "hour", tz_utils.local_hour(), "today", tz_utils.today_iso())
PY

echo "========== [2/5] materialize Telegram session =========="
python3 - <<'PY'
from __future__ import annotations
import os
import sqlite3
from pathlib import Path

ROOT = Path("/home/runner/workspace")
out = ROOT / ".telegram_session_string"

def load_dotenv(path: Path) -> dict:
    d = {}
    if not path.exists():
        return d
    for line in path.read_text(errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export "):].strip()
        k, v = line.split("=", 1)
        d[k.strip()] = v.strip().strip('"').strip("'")
    return d

envf = {}
for p in [ROOT/".env", ROOT/"bot"/".env", ROOT/"secrets.env", ROOT/"luxury_building.env"]:
    envf.update(load_dotenv(p))

candidates = []
for key in (
    "TELEGRAM_SESSION_STRING", "TELEGRAM_STRING_SESSION", "STRING_SESSION",
    "TG_SESSION_STRING", "SESSION_STRING", "TELEGRAM_SESSION",
):
    v = (os.environ.get(key) or envf.get(key) or "").strip()
    if len(v) > 50:
        candidates.append((key, v))

for p in [
    ROOT/"telegram_session_string.txt", ROOT/"session_string.txt",
    ROOT/"bot"/".telegram_session_string", ROOT/"data"/".telegram_session_string",
    ROOT/"string_session.txt",
]:
    if p.exists():
        t = p.read_text(errors="ignore").strip()
        if len(t) > 50:
            candidates.append((str(p), t))

# convert Telethon sqlite session -> StringSession if possible
api_id = os.environ.get("TELEGRAM_API_ID") or envf.get("TELEGRAM_API_ID")
api_hash = os.environ.get("TELEGRAM_API_HASH") or envf.get("TELEGRAM_API_HASH")
session_files = list(ROOT.glob("*.session")) + list((ROOT/"bot").glob("*.session"))
print("api_id_set", bool(api_id), "api_hash_set", bool(api_hash), "session_files", [str(p.name) for p in session_files])

if not candidates and api_id and api_hash and session_files:
    try:
        from telethon.sync import TelegramClient
        from telethon.sessions import StringSession
        for sf in session_files:
            stem = str(sf.with_suffix(""))
            try:
                client = TelegramClient(stem, int(api_id), api_hash)
                client.connect()
                if client.is_user_authorized():
                    s = StringSession.save(client.session)
                    candidates.append((f"convert:{sf.name}", s))
                    print("converted", sf.name, "len", len(s))
                client.disconnect()
            except Exception as e:
                print("convert_fail", sf.name, type(e).__name__, e)
    except Exception as e:
        print("telethon_convert_unavailable", type(e).__name__, e)

if out.exists() and len(out.read_text(errors="ignore").strip()) > 50:
    print("OK session file exists len=", len(out.read_text().strip()))
elif candidates:
    src, val = candidates[0]
    out.write_text(val.strip() + "\n", encoding="utf-8")
    os.chmod(out, 0o600)
    print(f"WROTE {out} from {src} len={len(val.strip())}")
else:
    print("MISSING_SESSION: set Replit Secret TELEGRAM_SESSION_STRING then re-run")
    print("Or place StringSession text into /home/runner/workspace/.telegram_session_string")
    # show hint keys present in env
    keys = [k for k in os.environ if "TELE" in k.upper() or "SESSION" in k.upper()]
    print("env_hint_keys", sorted(keys)[:40])

# refresh edge keys in .env (do not put session into .env)
env_path = ROOT / ".env"
lines = env_path.read_text(errors="ignore").splitlines() if env_path.exists() else []
keep = [ln for ln in lines if not ln.startswith("EDGE_POLICY_MODE=")
        and not ln.startswith("EDGE_LUXURY_FLOOR_GATE=")
        and not ln.startswith("FALLBACK_SEND_BLOCKED=")
        and not ln.startswith("BOT_TZ=")]
keep += [
    "EDGE_POLICY_MODE=luxury",
    "EDGE_LUXURY_FLOOR_GATE=1",
    "FALLBACK_SEND_BLOCKED=0",
    "BOT_TZ=America/Sao_Paulo",
]
env_path.write_text("\n".join(keep) + "\n", encoding="utf-8")
print("refreshed .env edge keys")
PY

echo "========== [3/5] patch fallback session loader =========="
python3 - <<'PY'
from pathlib import Path

PATCH_FN = '''
def _load_telegram_session() -> str:
    import os
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    here = Path(__file__).resolve().parent
    for key in ("TELEGRAM_SESSION_STRING", "TELEGRAM_STRING_SESSION", "STRING_SESSION", "TG_SESSION_STRING", "TELEGRAM_SESSION"):
        v = (os.environ.get(key) or "").strip()
        if len(v) > 50:
            return v
    for p in (root / ".telegram_session_string", here / ".telegram_session_string"):
        if p.exists():
            v = p.read_text(errors="ignore").strip()
            if len(v) > 50:
                return v
    raise FileNotFoundError(
        "Telegram session missing. Set Replit Secret TELEGRAM_SESSION_STRING "
        "or create /home/runner/workspace/.telegram_session_string"
    )
'''

for rel in ["bot/fallback_signal_sender.py", "bot/fallback_result_sender.py"]:
    p = Path(rel)
    if not p.exists():
        print("MISSING", rel); continue
    t = p.read_text(encoding="utf-8", errors="replace")
    if "def _load_telegram_session" not in t:
        t = t.replace("async def main", PATCH_FN + "\nasync def main", 1)
    t2 = t.replace(
        'session = (ROOT / ".telegram_session_string").read_text().strip()',
        "session = _load_telegram_session()",
    )
    if t2 != t:
        p.write_text(t2, encoding="utf-8")
        print("patched", rel)
    else:
        # still ensure call site uses helper
        if "_load_telegram_session()" in t2:
            p.write_text(t2, encoding="utf-8")
            print("ok", rel)
        else:
            print("WARN", rel)
PY

echo "========== [4/5] luxury env + restart =========="
cat > luxury_building.env <<'EOF'
export EDGE_POLICY_MODE=luxury
export EDGE_LUXURY_FLOOR_GATE=1
export FALLBACK_SEND_BLOCKED=0
export BOT_TZ=America/Sao_Paulo
EOF
set -a; source ./luxury_building.env; set +a

pkill -f 'runtime_supervisor.py' 2>/dev/null || true
pkill -f 'bacbo_royal_complete.py' 2>/dev/null || true
pkill -f 'fallback_signal_sender.py' 2>/dev/null || true
pkill -f 'fallback_result_sender.py' 2>/dev/null || true
sleep 1

nohup env EDGE_POLICY_MODE=luxury EDGE_LUXURY_FLOOR_GATE=1 FALLBACK_SEND_BLOCKED=0 \
  BOT_TZ=America/Sao_Paulo \
  python3 -u bot/runtime_supervisor.py > /tmp/luxury_supervisor.log 2>&1 &
echo "supervisor pid=$!"
sleep 6

echo "========== [5/5] verify =========="
echo "MODE=$EDGE_POLICY_MODE"
pgrep -af 'runtime_supervisor|bacbo_royal|fallback_signal|fallback_result' || true
echo "----- bot_live.log -----"
tail -n 50 logs/bot_live.log 2>/dev/null || true
echo "----- fallback_sender.log -----"
tail -n 25 logs/fallback_sender.log 2>/dev/null || true
echo "----- fallback_result_sender.log -----"
tail -n 15 logs/fallback_result_sender.log 2>/dev/null || true

python3 - <<'PY'
from pathlib import Path
import importlib, sys
sys.path.insert(0, '/home/runner/workspace')
if 'tz_utils' in sys.modules: del sys.modules['tz_utils']
import tz_utils
print('tz_file', tz_utils.__file__)
for n in ['ts','dts','now_local','local_hour','today_iso']:
    print(n, hasattr(tz_utils,n))
try:
    import database
    print('database_import_ok')
except Exception as e:
    print('database_import_FAIL', e)
try:
    import learning
    print('learning_import_ok')
except Exception as e:
    print('learning_import_FAIL', type(e).__name__, e)
sess=Path('.telegram_session_string')
print('session_file', sess.exists(), 'len', len(sess.read_text().strip()) if sess.exists() else 0)
PY

echo
echo "DONE. Paste ALL output to Cursor."
echo "If MISSING_SESSION still: Replit → Tools → Secrets → TELEGRAM_SESSION_STRING = <StringSession> then re-run."
