#!/usr/bin/env bash
# Fix bot_live ImportError (tz_utils.local_hour) + fallback Telegram session file.
set -euo pipefail
cd /home/runner/workspace

echo "========== [1/5] patch tz_utils (local_hour / today_iso) =========="
python3 - <<'PY'
from __future__ import annotations
from pathlib import Path

HELPER = '''
# --- LUXURY_TZ_HELPERS (auto) ---
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

def local_now():
    return datetime.now(tz=_zone())

def local_hour(dt=None):
    """Local hour (0-23) in BOT_TZ (default America/Sao_Paulo / BRT)."""
    if dt is None:
        return local_now().hour
    if getattr(dt, "tzinfo", None) is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(_zone()).hour

def today_iso(dt=None):
    """Local calendar date YYYY-MM-DD in BOT_TZ."""
    if dt is None:
        return local_now().date().isoformat()
    if getattr(dt, "tzinfo", None) is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(_zone()).date().isoformat()
'''

# Prefer bot/tz_utils.py on PYTHONPATH (supervisor puts bot first)
bot_tz = Path("bot/tz_utils.py")
root_tz = Path("tz_utils.py")

def ensure(path: Path) -> None:
    if path.exists():
        txt = path.read_text(encoding="utf-8", errors="replace")
        if "def local_hour" in txt and "def today_iso" in txt:
            print(f"OK {path} already has local_hour/today_iso")
            return
        if "LUXURY_TZ_HELPERS" in txt:
            print(f"OK {path} already patched")
            return
        bak = path.with_suffix(path.suffix + ".bak_pre_tz_fix")
        if not bak.exists():
            bak.write_text(txt, encoding="utf-8")
        path.write_text(txt.rstrip() + "\n\n" + HELPER + "\n", encoding="utf-8")
        print(f"patched {path}")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(HELPER.lstrip() + "\n", encoding="utf-8")
        print(f"created {path}")

ensure(bot_tz)
ensure(root_tz)

# smoke
import sys
sys.path.insert(0, "bot")
sys.path.insert(0, ".")
# force bot first
import importlib
if "tz_utils" in sys.modules:
    del sys.modules["tz_utils"]
import tz_utils
assert hasattr(tz_utils, "local_hour") and hasattr(tz_utils, "today_iso")
print("tz_utils.local_hour()", tz_utils.local_hour(), "today_iso()", tz_utils.today_iso())
PY

echo "========== [2/5] materialize .telegram_session_string =========="
python3 - <<'PY'
from __future__ import annotations
import os, re
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
        k, v = line.split("=", 1)
        d[k.strip()] = v.strip().strip('"').strip("'")
    return d

envf = {}
for p in [ROOT / ".env", ROOT / "bot" / ".env", ROOT / "secrets.env"]:
    envf.update(load_dotenv(p))

candidates = []
for key in (
    "TELEGRAM_SESSION_STRING",
    "TELEGRAM_STRING_SESSION",
    "STRING_SESSION",
    "TG_SESSION_STRING",
    "SESSION_STRING",
):
    v = os.environ.get(key) or envf.get(key)
    if v and len(v.strip()) > 50:
        candidates.append((key, v.strip()))

# other files that might hold the session
for p in [
    ROOT / "telegram_session_string.txt",
    ROOT / "session_string.txt",
    ROOT / "bot" / ".telegram_session_string",
    ROOT / "data" / ".telegram_session_string",
]:
    if p.exists():
        t = p.read_text(errors="ignore").strip()
        if len(t) > 50:
            candidates.append((str(p), t))

# Replit sometimes keeps StringSession in *.session sqlite — skip binary
if out.exists() and len(out.read_text(errors="ignore").strip()) > 50:
    print("OK session file exists len=", len(out.read_text().strip()))
else:
    if not candidates:
        print("MISSING_SESSION: set Replit Secret TELEGRAM_SESSION_STRING (or write .telegram_session_string)")
        print("Checked env keys + .env — none found with len>50")
    else:
        src, val = candidates[0]
        out.write_text(val + "\n", encoding="utf-8")
        os.chmod(out, 0o600)
        print(f"WROTE {out} from {src} len={len(val)}")

# also ensure .env has pointer if session file present
if out.exists() and len(out.read_text(errors="ignore").strip()) > 50:
    sess = out.read_text().strip()
    env_path = ROOT / ".env"
    lines = env_path.read_text(errors="ignore").splitlines() if env_path.exists() else []
    keys = {"TELEGRAM_SESSION_STRING"}
    kept = [ln for ln in lines if not any(ln.startswith(k + "=") for k in keys)]
    # do NOT dump huge session into .env if already in file — just note file
    # but fallbacks read file; supervisor copies file->env. OK.
    env_path.write_text("\n".join(kept) + ("\n" if kept else "") , encoding="utf-8")
    # restore EDGE lines
    for k, v in [
        ("EDGE_POLICY_MODE", "luxury"),
        ("EDGE_LUXURY_FLOOR_GATE", "1"),
        ("FALLBACK_SEND_BLOCKED", "0"),
    ]:
        with env_path.open("a", encoding="utf-8") as f:
            f.write(f"{k}={v}\n")
    print("refreshed .env edge keys")
PY

echo "========== [3/5] patch fallback senders to accept env session =========="
python3 - <<'PY'
from pathlib import Path
import re

PATCH = '''
def _load_telegram_session() -> str:
    import os
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    for key in ("TELEGRAM_SESSION_STRING", "TELEGRAM_STRING_SESSION", "STRING_SESSION", "TG_SESSION_STRING"):
        v = (os.environ.get(key) or "").strip()
        if len(v) > 50:
            return v
    for p in (root / ".telegram_session_string", Path(__file__).resolve().parent / ".telegram_session_string"):
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
        print("MISSING", rel)
        continue
    t = p.read_text(encoding="utf-8", errors="replace")
    if "_load_telegram_session" in t:
        print("already patched", rel)
        continue
    # insert helper before async def main
    if "async def main" not in t:
        print("skip no main", rel)
        continue
    t2 = t.replace("async def main", PATCH + "\nasync def main", 1)
    t2 = t2.replace(
        'session = (ROOT / ".telegram_session_string").read_text().strip()',
        "session = _load_telegram_session()",
    )
    if t2 == t:
        print("WARN: pattern not found in", rel)
        continue
    bak = p.with_suffix(".py.bak_pre_session_fix")
    if not bak.exists():
        bak.write_text(t, encoding="utf-8")
    p.write_text(t2, encoding="utf-8")
    print("patched", rel)
PY

echo "========== [4/5] luxury env + restart supervisor =========="
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

# supervisor copies .telegram_session_string -> TELEGRAM_SESSION_STRING for children
nohup env EDGE_POLICY_MODE=luxury EDGE_LUXURY_FLOOR_GATE=1 FALLBACK_SEND_BLOCKED=0 \
  BOT_TZ=America/Sao_Paulo \
  python3 -u bot/runtime_supervisor.py > /tmp/luxury_supervisor.log 2>&1 &
echo "supervisor pid=$!"
sleep 5

echo "========== [5/5] verify boot =========="
echo "MODE=$EDGE_POLICY_MODE"
pgrep -af 'runtime_supervisor|bacbo_royal|fallback_signal|fallback_result' || true
echo "----- bot_live.log (tail) -----"
tail -n 40 logs/bot_live.log 2>/dev/null || true
echo "----- fallback_sender.log (tail) -----"
tail -n 30 logs/fallback_sender.log 2>/dev/null || true
echo "----- fallback_result_sender.log (tail) -----"
tail -n 20 logs/fallback_result_sender.log 2>/dev/null || true

python3 - <<'PY'
from pathlib import Path
import sys
sys.path.insert(0,'bot'); sys.path.insert(0,'.')
import tz_utils
print('tz_ok', tz_utils.local_hour(), tz_utils.today_iso())
sess = Path('.telegram_session_string')
print('session_file', sess.exists(), 'len', len(sess.read_text().strip()) if sess.exists() else 0)
# quick import database like bot_live does
try:
    import database
    print('database_import_ok')
except Exception as e:
    print('database_import_FAIL', type(e).__name__, e)
PY

echo
echo "DONE. Paste this whole output to Cursor."
echo "If MISSING_SESSION: add Replit Secret TELEGRAM_SESSION_STRING then re-run this script."
