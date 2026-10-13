#!/usr/bin/env bash
# Telegram + engine pulse — why aren't cards landing?
set -euo pipefail
cd /home/runner/workspace
PY=python3

echo "========== PROCESSES =========="
$PY - <<'PY'
from pathlib import Path

def cmdline(pid):
    try:
        return Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\0", b" ").decode("utf-8", "replace").strip()
    except Exception:
        return ""

needles = ("bacbo_royal_complete.py", "runtime_supervisor.py", "telegram_outbox.py")
found = 0
for p in sorted(Path("/proc").iterdir(), key=lambda x: int(x.name) if x.name.isdigit() else 0):
    if not p.name.isdigit():
        continue
    cmd = cmdline(int(p.name))
    if "python" not in cmd.lower():
        continue
    if any(n in cmd for n in needles):
        print(f"{p.name}\t{cmd[:160]}")
        found += 1
print("proc_n", found)
PY

echo
echo "========== DB + OUTBOX CURSOR =========="
$PY - <<'PY'
import os, sqlite3, time
from pathlib import Path

def pick_db() -> Path:
    env = (os.environ.get("BACBO_DB") or os.environ.get("DB_PATH") or "").strip()
    cands: list[Path] = []
    if env:
        p = Path(env)
        if p.is_file():
            cands.append(p)
    for p in (Path("bot/bacbo.db"), Path("bacbo.db"), Path("bot/data/bacbo.db")):
        if p.is_file():
            cands.append(p)
    if not cands:
        raise SystemExit("NO bacbo.db FOUND")
    # Prefer bot/bacbo.db when mtimes are close; else freshest file.
    cands = list(dict.fromkeys(cands))  # dedupe preserve order
    cands.sort(
        key=lambda p: (
            p.stat().st_mtime,
            1 if str(p).endswith("bot/bacbo.db") or str(p) == "bot/bacbo.db" else 0,
        ),
        reverse=True,
    )
    return cands[0]

db = pick_db()
print("using_db", db, "mtime_age_s", int(time.time() - db.stat().st_mtime), "size_mb", round(db.stat().st_size / 1e6, 2))
for p in (Path("bot/bacbo.db"), Path("bacbo.db"), Path("bot/data/bacbo.db")):
    if p.is_file() and p.resolve() != db.resolve():
        print(" other_db", p, "mtime_age_s", int(time.time() - p.stat().st_mtime))

sig = Path("bot/data/fallback_sender_state.txt")
res = Path("bot/data/fallback_result_sender_state.txt")
last_sig = int(sig.read_text().strip()) if sig.exists() else 0
last_res = int(res.read_text().strip()) if res.exists() else 0
print("outbox_sig_state", last_sig)
print("outbox_res_state", last_res)

conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=60)
conn.row_factory = sqlite3.Row
conn.execute("PRAGMA busy_timeout=60000")
mx = conn.execute("SELECT MAX(id) m, MAX(fired_at) f, COUNT(*) n FROM consensus_signals").fetchone()
print("consensus_max_id", mx["m"], "max_fired", mx["f"], "n", mx["n"])
pending = conn.execute("SELECT COUNT(*) FROM consensus_signals WHERE id > ?", (last_sig,)).fetchone()[0]
print("pending_behind_cursor", pending)
for label, sql in (
    ("fires_last_30m", "SELECT COUNT(*) FROM consensus_signals WHERE fired_at >= datetime('now','-30 minutes')"),
    ("fires_last_2h", "SELECT COUNT(*) FROM consensus_signals WHERE fired_at >= datetime('now','-2 hours')"),
    ("fires_last_24h", "SELECT COUNT(*) FROM consensus_signals WHERE fired_at >= datetime('now','-24 hours')"),
    ("blocked_last_2h", "SELECT COUNT(*) FROM blocked_signals WHERE blocked_at >= datetime('now','-2 hours')"),
    ("blocked_wins_last_24h", "SELECT COUNT(*) FROM blocked_signals WHERE outcome='win' AND blocked_at >= datetime('now','-24 hours')"),
):
    try:
        print(label, conn.execute(sql).fetchone()[0])
    except Exception as e:
        print(label, "ERR", e)

# minutes since last fire
try:
    mins = conn.execute(
        "SELECT CAST((julianday('now')-julianday(MAX(fired_at)))*24*60 AS INT) FROM consensus_signals"
    ).fetchone()[0]
    print("minutes_since_last_fire", mins)
except Exception as e:
    print("minutes_since_last_fire ERR", e)

print("--- last 8 consensus ---")
for r in conn.execute(
    "SELECT id, fired_at, signal_kind, color, outcome, source_floor, "
    "COALESCE(final_score, confidence_pct, total_score) score "
    "FROM consensus_signals ORDER BY id DESC LIMIT 8"
):
    print(dict(r))
print("--- last 5 blocked ---")
try:
    for r in conn.execute(
        "SELECT id, blocked_at, signal_kind, color, gate_reason, source_floor, outcome "
        "FROM blocked_signals ORDER BY id DESC LIMIT 5"
    ):
        print(dict(r))
except Exception as e:
    print("blocked_query", e)

# room activity if present
for table, col in (("channel_messages", "received_at"), ("signals", "created_at"), ("room_live_metrics", "updated_at")):
    try:
        cols = [x[1] for x in conn.execute(f"pragma table_info({table})")]
        if not cols:
            continue
        tcol = col if col in cols else cols[-1]
        row = conn.execute(f"SELECT COUNT(*), MAX({tcol}) FROM {table}").fetchone()
        print(f"table_{table}", "n", row[0], "max", row[1])
    except Exception:
        pass

conn.close()

mins = mins if isinstance(mins, int) else 99999
if pending > 0 and mins is not None and mins > 30:
    print("VERDICT: OUTBOX_BEHIND — cursor lags; ONE.sh refresh outbox")
elif pending > 0 and mins is not None and mins <= 30:
    print("VERDICT: OUTBOX_NOT_DRAINING — fires exist, outbox not sending")
elif mins is not None and mins > 45:
    print("VERDICT: ENGINE_SILENT — bacbo alive but no new consensus FIRED (rooms/gates/hours/edge)")
else:
    print("VERDICT: OK_OR_RECENT — watch for next sent signal")
PY

echo
echo "========== OUTBOX LOG =========="
grep -E 'HEARTBEAT|sent signal|db_max|FATAL|SEND .* FAIL|ONLINE|COUNTDOWN' logs/telegram_outbox.log 2>/dev/null | tail -n 25 || true

echo
echo "========== BACBO LOG (fire/block/error) =========="
if [ -f logs/bot_live.log ]; then
  echo "bot_live bytes $(wc -c < logs/bot_live.log) age_s $(( $(date +%s) - $(stat -c %Y logs/bot_live.log) ))"
  grep -E 'FIRED|QUIET|EdgePolicy|TOWER_MERGE|BLOCK|ALLOW|subscribe|Subscribed|Traceback|ERROR|FloodWait|disconnected|AuthKey' logs/bot_live.log | tail -n 50 || tail -n 40 logs/bot_live.log
else
  echo "missing logs/bot_live.log — listing logs/"
  ls -lah logs/ 2>/dev/null || true
fi

echo
echo "========== ENV UNLOCKS (read-only check) =========="
$PY - <<'PY'
import os
from pathlib import Path
# source-like peek
env = {}
for path in (Path("luxury_building.env"), Path(".env")):
    if not path.exists():
        continue
    for line in path.read_text(errors="ignore").splitlines():
        line=line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line=line[7:]
        k,v=line.split("=",1)
        env[k.strip()]=v.strip().strip('"').strip("'")
keys = [
    "EDGE_POLICY_MODE","EDGE_LUXURY_FLOOR_GATE","LUXURY_TOWER_MERGE",
    "LUXURY_NO_HOUR_BLOCKS","FALLBACK_SEND_BLOCKED","TELEGRAM_SINGLE_OUTBOX",
    "TELEGRAM_COUNTDOWN_PEER","FALLBACKS_ENABLED",
]
for k in keys:
    print(f"{k}={os.environ.get(k) or env.get(k) or '(unset)'}")
PY

echo
echo "========== NEXT =========="
echo "If VERDICT ENGINE_SILENT → run ENGINE_WAKE.sh (unlocks hour blocks + restarts + watches FIRED)"
echo "curl -fsSL -H 'Cache-Control: no-cache' -o WAKE.sh https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/cursor/add-engine-gate-registry-d5ba/replit_elite_stack_patch/REPLIT_ENGINE_WAKE.sh && bash WAKE.sh"
echo "DONE."
