#!/usr/bin/env bash
# Telegram pulse — why aren't cards landing?
# Shows: processes, DB freshness, pending behind outbox cursor, recent fires, log tails.
set -euo pipefail
cd /home/runner/workspace
PY=python3

echo "========== PROCESSES =========="
$PY - <<'PY'
from pathlib import Path

def cmdline(pid):
    try:
        return Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\0", b" ").decode("utf-8","replace").strip()
    except Exception:
        return ""

needles = ("bacbo_royal_complete.py", "runtime_supervisor.py", "telegram_outbox.py")
for p in sorted(Path("/proc").iterdir(), key=lambda x: int(x.name) if x.name.isdigit() else 0):
    if not p.name.isdigit():
        continue
    cmd = cmdline(int(p.name))
    if "python" not in cmd.lower():
        continue
    if any(n in cmd for n in needles):
        print(f"{p.name}\t{cmd[:160]}")
PY

echo
echo "========== DB + OUTBOX CURSOR =========="
$PY - <<'PY'
import os, sqlite3, time
from pathlib import Path

cands = []
for p in [
    Path(os.environ.get("BACBO_DB") or ""),
    Path("bot/bacbo.db"),
    Path("bacbo.db"),
    Path("bot/data/bacbo.db"),
]:
    if str(p) and p.exists():
        cands.append(p)
if not cands:
    print("NO bacbo.db FOUND")
    raise SystemExit(1)
cands.sort(key=lambda p: p.stat().st_mtime, reverse=True)
db = cands[0]
print("using_db", db, "mtime_age_s", int(time.time() - db.stat().st_mtime), "size", db.stat().st_size)
for p in cands[1:]:
    print(" other_db", p, "mtime_age_s", int(time.time() - p.stat().st_mtime))

sig = Path("bot/data/fallback_sender_state.txt")
res = Path("bot/data/fallback_result_sender_state.txt")
last_sig = int(sig.read_text().strip()) if sig.exists() else 0
last_res = int(res.read_text().strip()) if res.exists() else 0
print("outbox_sig_state", last_sig)
print("outbox_res_state", last_res)

conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=30)
conn.row_factory = sqlite3.Row
mx = conn.execute("SELECT MAX(id) m, MAX(fired_at) f, COUNT(*) n FROM consensus_signals").fetchone()
print("consensus_max_id", mx["m"], "max_fired", mx["f"], "n", mx["n"])
pending = conn.execute("SELECT COUNT(*) FROM consensus_signals WHERE id > ?", (last_sig,)).fetchone()[0]
print("pending_behind_cursor", pending)
recent = conn.execute(
    "SELECT COUNT(*) FROM consensus_signals WHERE fired_at >= datetime('now','-30 minutes')"
).fetchone()[0]
print("fires_last_30m", recent)
recent2 = conn.execute(
    "SELECT COUNT(*) FROM consensus_signals WHERE fired_at >= datetime('now','-2 hours')"
).fetchone()[0]
print("fires_last_2h", recent2)
blocked = conn.execute(
    "SELECT COUNT(*) FROM blocked_signals WHERE blocked_at >= datetime('now','-2 hours')"
).fetchone()[0]
print("blocked_last_2h", blocked)
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
conn.close()

# Verdict
if pending > 0 and recent == 0:
    print("VERDICT: OUTBOX_BEHIND — engine may be quiet now but cursor lags; restart outbox / widen lookback")
elif recent == 0 and pending == 0:
    print("VERDICT: ENGINE_SILENT — no new consensus fires (edge block / rooms / bacbo stuck)")
elif pending > 0 and recent > 0:
    print("VERDICT: OUTBOX_NOT_DRAINING — fires exist but not sending (check outbox log / session)")
else:
    print("VERDICT: CATCHING_UP_OR_OK — watch outbox log for sent signal")
PY

echo
echo "========== OUTBOX LOG (tail) =========="
tail -n 40 logs/telegram_outbox.log 2>/dev/null || tail -n 40 /tmp/luxury_supervisor.log 2>/dev/null || true

echo
echo "========== BACBO LOG (FIRED/ERROR tail) =========="
if [ -f logs/bot_live.log ]; then
  grep -E 'FIRED|ERROR|EdgePolicy|TOWER_MERGE|BLOCK|subscribe|Traceback' logs/bot_live.log | tail -n 40 || tail -n 30 logs/bot_live.log
else
  ls -la logs/ 2>/dev/null || true
fi

echo
echo "========== QUICK FIXES =========="
echo "1) If ENGINE_SILENT: check rooms subscribed + EdgePolicy not ALL_BLOCKED"
echo "2) If OUTBOX_BEHIND/NOT_DRAINING: re-run ONE.sh (refreshes hardened outbox)"
echo "3) Optional rewind cursor 20 ids (only if stuck):"
echo "   python3 - <<'PY'"
echo "from pathlib import Path"
echo "p=Path('bot/data/fallback_sender_state.txt'); n=max(0,int(p.read_text())-20); p.write_text(str(n)); print('sig->',n)"
echo "PY"
echo "DONE."
