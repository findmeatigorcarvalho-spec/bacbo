#!/usr/bin/env bash
# ONE paste on Replit: restore Telegram session + HUB MAX boot + verify.
# Usage:
#   curl -fsSL -H "Cache-Control: no-cache" -o DOIT.sh \
#     "https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/cursor/add-engine-gate-registry-d5ba/replit_elite_stack_patch/REPLIT_DO_IT.sh" \
#     && bash DOIT.sh
set -euo pipefail
cd /home/runner/workspace 2>/dev/null || cd "$(dirname "$0")/.."
PY="${PYTHON:-python3}"
SHA="${LUXURY_PATCH_SHA:-cursor/add-engine-gate-registry-d5ba}"
BASE="https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/${SHA}/replit_elite_stack_patch"

echo "========== DO IT [0/3] materialize Telegram session =========="
set -a
# shellcheck disable=SC1091
[ -f .env ] && source ./.env || true
set +a

SESS=""
_try() {
  local name="$1" val="$2"
  val="$(printf '%s' "$val" | tr -d '\n\r')"
  if [ "${#val}" -gt 50 ]; then
    SESS="$val"
    echo "session OK from $name (len=${#SESS})"
    return 0
  fi
  return 1
}
_try TELEGRAM_SESSION_STRING "${TELEGRAM_SESSION_STRING:-}" || \
_try TELEGRAM_STRING_SESSION "${TELEGRAM_STRING_SESSION:-}" || \
_try STRING_SESSION "${STRING_SESSION:-}" || \
_try TG_SESSION_STRING "${TG_SESSION_STRING:-}" || true

if [ -z "$SESS" ]; then
  for f in .telegram_session_string bot/.telegram_session_string; do
    if [ -f "$f" ]; then
      _try "file:$f" "$(cat "$f")" && break || true
    fi
  done
fi

if [ -z "$SESS" ] && [ -f .env ]; then
  SESS="$($PY - <<'PY'
from pathlib import Path
keys = ("TELEGRAM_SESSION_STRING","TELEGRAM_STRING_SESSION","STRING_SESSION","TG_SESSION_STRING")
p = Path(".env")
if not p.exists():
    raise SystemExit
for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
    s = line.strip()
    if not s or s.startswith("#") or "=" not in s:
        continue
    if s.startswith("export "):
        s = s[len("export "):]
    k, _, v = s.partition("=")
    k, v = k.strip(), v.strip().strip('"').strip("'")
    if k in keys and len(v) > 50:
        print(v.replace("\n","").replace("\r",""), end="")
        break
PY
)"
  if [ "${#SESS}" -gt 50 ]; then
    echo "session OK from .env (len=${#SESS})"
  else
    SESS=""
  fi
fi

if [ -z "$SESS" ] || [ "${#SESS}" -le 50 ]; then
  echo "FATAL: no Telegram session on this Replit."
  echo "Fix once in Replit → Tools → Secrets:"
  echo "  Key:   TELEGRAM_SESSION_STRING"
  echo "  Value: <your Telethon string session>"
  echo "Then re-run this script."
  exit 1
fi

printf '%s\n' "$SESS" > .telegram_session_string
chmod 600 .telegram_session_string 2>/dev/null || true
export TELEGRAM_SESSION_STRING="$SESS"
echo "wrote .telegram_session_string"

echo "========== DO IT [0b/3] fix tz_utils (local_hour) =========="
curl -fsSL -H "Cache-Control: no-cache" -o bot/fix_tz_utils.py "$BASE/bot/fix_tz_utils.py"
$PY bot/fix_tz_utils.py

echo "========== DO IT [1/3] pull latest HUBMAX =========="
curl -fsSL -H "Cache-Control: no-cache" -o HUBMAX.sh "$BASE/REPLIT_HUB_MAX.sh"
chmod +x HUBMAX.sh

echo "========== DO IT [2/3] run HUB MAX =========="
export TELEGRAM_SESSION_STRING="$SESS"
export TELEGRAM_GUNIQUE_PEER_ID="${TELEGRAM_GUNIQUE_PEER_ID:-5855678138}"
export GUNIQUE_PEER_ID="${GUNIQUE_PEER_ID:-5855678138}"
bash HUBMAX.sh

echo "========== DO IT [3/3] verify =========="
sleep 2
echo "--- processes ---"
$PY - <<'PY'
from pathlib import Path

def cmdline(pid):
    try:
        return Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\0", b" ").decode("utf-8","replace")
    except Exception:
        return ""

needles = {
    "bacbo": "bacbo_royal_complete.py",
    "sup": "runtime_supervisor.py",
    "outbox": "telegram_outbox.py",
}
counts = {}
for label, needle in needles.items():
    rows = []
    for p in Path("/proc").iterdir():
        if not p.name.isdigit():
            continue
        cmd = cmdline(int(p.name))
        if needle in cmd and "python" in cmd.lower() and "REPLIT_" not in cmd:
            rows.append((p.name, cmd[:120]))
    counts[label] = len(rows)
    print(f"{label}: {len(rows)}")
    for pid, cmd in rows:
        print(f"  pid={pid} {cmd}")
if counts.get("bacbo", 0) == 0:
    print("\n--- bacbo:0 → last bot_live crash ---")
    bl = Path("logs/bot_live.log")
    if bl.exists():
        lines = bl.read_text(encoding="utf-8", errors="replace").splitlines()
        for ln in lines[-60:]:
            print(ln)
    else:
        print("(no logs/bot_live.log yet)")
PY
echo "--- session file ---"
ls -la .telegram_session_string 2>/dev/null || echo "MISSING session file"
echo "--- recent logs ---"
rg -n 'HUB-ROUTE|snap fire cursor|Gunique resolve OK|session:|VERDICT|FATAL|WARN: no Telegram|Traceback|Error' \
  logs/telegram_outbox.log logs/bot_live.log /tmp/luxury_supervisor.log 2>/dev/null | tail -50 || true
echo
echo "DONE DO IT. Expect bacbo:1 + outbox:1 + Gunique id 5855678138 + HUB-ROUTE lines after next fire."
if [ -f logs/bot_live.log ]; then
  if ! pgrep -f 'bacbo_royal_complete.py' >/dev/null 2>&1; then
    echo "NEXT: paste the Traceback from logs/bot_live.log (commands below)."
  fi
fi
