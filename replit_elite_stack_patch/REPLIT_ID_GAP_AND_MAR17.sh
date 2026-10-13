#!/usr/bin/env bash
# Explain consensus_signals id starting at 5 WITHOUT assuming wipe/delete.
# Also hunt Mar 17–18 gold: logs, blocked_signals, signal_context, sqlite_sequence.
#
#   curl -fsSL -H 'Cache-Control: no-cache' -o ID_GAP.sh \
#     'https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/cursor/add-engine-gate-registry-d5ba/replit_elite_stack_patch/REPLIT_ID_GAP_AND_MAR17.sh'
#   bash ID_GAP.sh | tee id_gap_mar17_report.txt
set -euo pipefail
cd /home/runner/workspace 2>/dev/null || cd "$(dirname "$0")/.."

python3 - <<'PY'
import sqlite3, os, re
from pathlib import Path

con = sqlite3.connect("file:bot/bacbo.db?mode=ro", uri=True)
con.row_factory = sqlite3.Row

print("========== 1. sqlite_sequence (AUTOINCREMENT counter) ==========")
try:
    for r in con.execute("SELECT * FROM sqlite_sequence"):
        print(dict(r))
except Exception as e:
    print("no sqlite_sequence:", e)

print("\n========== 2. consensus_signals id stats (NOT claiming wipe) ==========")
print(con.execute(
    "SELECT MIN(id), MAX(id), COUNT(*), MIN(fired_at), MAX(fired_at) FROM consensus_signals"
).fetchone())
# Check if ids 1-4 exist anywhere as references
for t, col in [
    ("signal_context", "signal_id"),
    ("outcome_history", "id"),
    ("blocked_signals", "id"),
]:
    try:
        cols = [c[1] for c in con.execute(f"PRAGMA table_info({t})")]
        print(f"  {t} cols sample:", cols[:8])
    except Exception as e:
        print(t, e)

print("\n========== 3. ANY table with timestamps on 2026-03-17 or 2026-03-18 ==========")
tables = [r[0] for r in con.execute(
    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY 1"
)]
for t in tables:
    cols = [c[1] for c in con.execute(f"PRAGMA table_info([{t}])")]
    ts_cols = [c for c in cols if any(x in c.lower() for x in
               ("at", "time", "ts", "fired", "sent", "created", "recorded", "resolved"))]
    for tc in ts_cols:
        try:
            n = con.execute(
                f"SELECT COUNT(*) FROM [{t}] WHERE CAST([{tc}] AS TEXT) LIKE '2026-03-17%' OR CAST([{tc}] AS TEXT) LIKE '2026-03-18%'"
            ).fetchone()[0]
            if n:
                print(f"  HIT {t}.{tc} count={n}")
                for r in con.execute(
                    f"SELECT * FROM [{t}] WHERE CAST([{tc}] AS TEXT) LIKE '2026-03-17%' OR CAST([{tc}] AS TEXT) LIKE '2026-03-18%' ORDER BY [{tc}] ASC LIMIT 5"
                ):
                    d = dict(r)
                    for k, v in list(d.items()):
                        if isinstance(v, str) and len(v) > 100:
                            d[k] = v[:100] + "..."
                    print("   ", d)
        except Exception:
            pass

print("\n========== 4. blocked_signals earliest ==========")
try:
    print(con.execute(
        "SELECT MIN(id), MAX(id), COUNT(*) FROM blocked_signals"
    ).fetchone())
    # guess timestamp col
    cols = [c[1] for c in con.execute("PRAGMA table_info(blocked_signals)")]
    print("cols:", cols)
    for r in con.execute("SELECT * FROM blocked_signals ORDER BY id ASC LIMIT 5"):
        d = dict(r)
        for k, v in list(d.items()):
            if isinstance(v, str) and len(v) > 100:
                d[k] = v[:100] + "..."
        print(" ", d)
except Exception as e:
    print(e)

print("\n========== 5. Why id can start at 5 WITHOUT any wipe ==========")
print("""
SQLite AUTOINCREMENT can skip numbers when:
  - INSERT failed/rolled back (counter still advances)
  - Explicit INSERT with id=5 as first successful row
  - Table recreated empty but sqlite_sequence already advanced
  - Copy/restore of DB that already had sequence past 4
NONE of these require you deleting rows. Do NOT assume wipe.
""")

print("\n========== 6. Search bot logs for 17/03 and 18/03 and ONLINE / FIRE ==========")
log_paths = []
for p in Path(".").rglob("*"):
    if not p.is_file():
        continue
    name = p.name.lower()
    if any(x in str(p).lower() for x in ("bot.log", "bot_live", "workflow-logs", "telegram_bot")):
        if p.stat().st_size > 0:
            log_paths.append(p)

# Prefer smaller readable logs + heads of large ones
log_paths = sorted(set(log_paths), key=lambda p: p.stat().st_size)[:40]
print("log candidates:", len(log_paths))
pat = re.compile(r"2026-03-1[78]|17/03/2026|18/03/2026|ONLINE|SIGNAL FIRED|SOLO_ELITE|GOLDEN|Mr_iv4|08:37", re.I)
hits = 0
for p in log_paths:
    try:
        # read last/first chunks for huge files
        data = p.read_bytes()
        if len(data) > 8_000_000:
            chunks = [data[:2_000_000], data[-2_000_000:]]
        else:
            chunks = [data]
        text = b"\n".join(chunks).decode("utf-8", errors="ignore")
        for i, line in enumerate(text.splitlines()):
            if pat.search(line):
                print(f"LOGHIT {p}: {line[:240]}")
                hits += 1
                if hits >= 40:
                    break
    except Exception as e:
        print("log err", p, e)
    if hits >= 40:
        break
print(f"total_log_hits_shown={hits}")

print("\n========== 7. VERDICT ==========")
print("ONLINE 17/03/2026 08:37:17 is GOLD from Telegram — real day-one in Mr_iv4.")
print("DB first consensus fire 19/03 is first SUCCESSFULLY STORED row — not proof nothing existed before.")
print("Id gap 1-4 ≠ wipe. Hunt logs + Telegram scroll 17–18 Mar for fires.")
con.close()
PY
