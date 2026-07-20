#!/usr/bin/env bash
# Quick: fix send() config NameError + Oracle db path + show live health.
set -euo pipefail
cd /home/runner/workspace

echo "========== [1/3] fix config NameError in send path =========="
python3 - <<'PY'
from pathlib import Path
import re, ast

# bacbo send() failed: name 'config' is not defined — ensure `import config` near top
p = Path("bacbo_royal_complete.py")
src = p.read_text(encoding="utf-8", errors="replace")
if not re.search(r"^import config\b", src, re.M):
    # insert after first import block line
    lines = src.splitlines(True)
    idx = 0
    for i, ln in enumerate(lines[:80]):
        if ln.startswith("import ") or ln.startswith("from "):
            idx = i + 1
    lines.insert(idx, "import config  # LUXURY: ensure config in module scope for send()\n")
    src = "".join(lines)
    p.write_text(src, encoding="utf-8")
    print("inserted import config")
else:
    print("import config already present")

# Also scan bot/*.py that might call send with bare config
for fp in Path("bot").glob("*.py"):
    t = fp.read_text(encoding="utf-8", errors="replace")
    if "name 'config'" in t:
        continue
    # if file uses config. but never imports it
    if re.search(r"\bconfig\.", t) and not re.search(r"^(import config|from config import)", t, re.M):
        if fp.name in ("config.py",):
            continue
        # only fix if it's a runtime module likely in send path
        if fp.name in ("signal_handler.py", "background.py", "utils.py", "commands.py"):
            if "import config" not in t.split("\n")[:40]:
                lines = t.splitlines(True)
                lines.insert(0, "import config  # LUXURY auto\n")
                fp.write_text("".join(lines), encoding="utf-8")
                print("added import config to", fp.name)

ast.parse(p.read_text(encoding="utf-8"))
print("bacbo syntax OK")
PY

echo "========== [2/3] Oracle DB path (symlink) =========="
python3 - <<'PY'
from pathlib import Path
# Find what Oracle wants — often a path under bot/
for cand in [
    Path("bot/oracle.db"), Path("bot/data/oracle.db"), Path("oracle.db"),
    Path("bot/bacbo.db"), Path("bacbo.db"),
]:
    print(cand, "exists" if cand.exists() else "missing", cand.stat().st_size if cand.exists() else 0)

# Grep oracle open path from code
import re
hits = []
for fp in list(Path(".").glob("*.py")) + list(Path("bot").glob("*.py")):
    try:
        t = fp.read_text(encoding="utf-8", errors="replace")
    except Exception:
        continue
    if "Oracle" in t or "oracle" in t:
        for m in re.finditer(r["']([^"']*oracle[^"']*\.db)["']", t, re.I):
            hits.append((fp.name, m.group(1)))
        for m in re.finditer(r"sqlite3\.connect\(([^)]+)\)", t):
            if "oracle" in m.group(1).lower() or "Oracle" in t[max(0,m.start()-80):m.start()]:
                hits.append((fp.name, m.group(1)[:80]))
print("oracle_hits", hits[:20])

# Ensure parent dirs for common oracle paths + touch empty if missing (Oracle can init)
for rel in ["bot/data/oracle.db", "bot/oracle.db"]:
    path = Path(rel)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        # symlink to bacbo.db if that's what they share, else empty file
        if Path("bot/bacbo.db").exists():
            try:
                path.symlink_to("bacbo.db" if path.parent == Path("bot") else "../bacbo.db")
                print("symlinked", path)
            except Exception:
                path.write_bytes(b"")
                print("touched", path)
        else:
            path.write_bytes(b"")
            print("touched", path)
PY

echo "========== [3/3] health snapshot (no restart unless bot dead) =========="
set -a; source ./luxury_building.env 2>/dev/null || true; set +a
export EDGE_POLICY_MODE=luxury
export TELEGRAM_TARGET_PEER="${TELEGRAM_TARGET_PEER:-6774605259}"

# restart only if bacbo missing
if ! pgrep -f 'bacbo_royal_complete.py' >/dev/null; then
  echo "bacbo dead — restarting supervisor"
  pkill -f runtime_supervisor.py 2>/dev/null || true
  sleep 1
  export TELEGRAM_SESSION_STRING="$(tr -d '\n' < .telegram_session_string)"
  nohup env EDGE_POLICY_MODE=luxury EDGE_LUXURY_FLOOR_GATE=1 FALLBACK_SEND_BLOCKED=0 \
    BOT_TZ=America/Sao_Paulo TELEGRAM_SESSION_STRING="$TELEGRAM_SESSION_STRING" \
    TELEGRAM_TARGET_PEER="$TELEGRAM_TARGET_PEER" \
    python3 -u bot/runtime_supervisor.py > /tmp/luxury_supervisor.log 2>&1 &
  echo "started $!"
  sleep 8
else
  echo "bacbo already running — no restart"
fi

echo "===== PROCS ====="
pgrep -af 'runtime_supervisor|bacbo_royal|fallback_signal|fallback_result' || true

echo "===== MODE / PEER / SESSION ====="
echo "EDGE_POLICY_MODE=${EDGE_POLICY_MODE:-}"
echo "TELEGRAM_TARGET_PEER=${TELEGRAM_TARGET_PEER:-}"
echo "session_len=$(wc -c < .telegram_session_string | tr -d ' ')"

echo "===== recent bot (no NameError?) ====="
tail -n 40 logs/bot_live.log | grep -E 'ERROR|CrashGuard|NameError|run_forever|EdgePolicy|ALLOW|BOOT|GameCoach|Fallback|signal' || tail -n 20 logs/bot_live.log

echo "===== fallback ====="
tail -n 15 logs/fallback_sender.log
tail -n 10 logs/fallback_result_sender.log

echo "===== last consensus signals ====="
python3 - <<'PY'
import sqlite3
from pathlib import Path
db = Path('bot/bacbo.db') if Path('bot/bacbo.db').exists() else Path('bacbo.db')
con = sqlite3.connect(str(db))
con.row_factory = sqlite3.Row
try:
    rows = con.execute("""
      SELECT id, fired_at, signal_kind, color, source_floor, total_score
      FROM consensus_signals
      ORDER BY id DESC LIMIT 12
    """).fetchall()
    print('db', db)
    for r in rows:
        print(dict(r))
except Exception as e:
    print('db_query_fail', e)
PY

echo
echo "DONE. Paste to Cursor."
echo "If bot stays up: watch Telegram for mixed floors (JUN19/MAY10/LIVE), not only fallback template."
