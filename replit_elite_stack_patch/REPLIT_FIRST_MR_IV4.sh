#!/usr/bin/env bash
# Find first Mr_iv4 / bot activity vs first consensus signal.
# Run on Replit:
#   curl -fsSL -H 'Cache-Control: no-cache' -o FIRST_SIGNAL.sh \
#     'https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/cursor/add-engine-gate-registry-d5ba/replit_elite_stack_patch/REPLIT_FIRST_MR_IV4.sh'
#   bash FIRST_SIGNAL.sh
set -euo pipefail
cd /home/runner/workspace 2>/dev/null || cd "$(dirname "$0")/.."

python3 - <<'PY'
import sqlite3, re
from pathlib import Path

con = sqlite3.connect("file:bot/bacbo.db?mode=ro", uri=True)
con.row_factory = sqlite3.Row

print("========== A. consensus_signals timeline ==========")
print("min/max/count:", con.execute(
    "SELECT MIN(fired_at), MAX(fired_at), COUNT(*), MIN(id), MAX(id) FROM consensus_signals"
).fetchone())
print("first 5 by fired_at:")
for r in con.execute(
    "SELECT id, fired_at, signal_kind, color, source_floor, outcome FROM consensus_signals ORDER BY fired_at, id LIMIT 5"
):
    print(" ", dict(r))
print("id gaps (missing early ids?):")
ids = [r[0] for r in con.execute("SELECT id FROM consensus_signals ORDER BY id LIMIT 20")]
print(" first_20_ids=", ids)

print("\n========== B. channel_messages — ONLINE / bot banners ==========")
# Online banner text from user paste
patterns = [
    "%ONLINE%",
    "%BacBo Royal%",
    "%UserBot%",
    "%SOLO ELITE%",
    "%GOLDEN%",
    "%Mr_iv4%",
    "%6774605259%",
]
for pat in patterns:
    row = con.execute(
        """
        SELECT id, handle, msg_id, sent_at, substr(raw_text,1,200) AS head
        FROM channel_messages
        WHERE raw_text LIKE ?
        ORDER BY sent_at ASC, id ASC
        LIMIT 1
        """,
        (pat,),
    ).fetchone()
    if row:
        print(f"FIRST LIKE {pat!r}:", dict(row))

print("\n========== C. earliest channel_messages overall ==========")
print("min sent_at:", con.execute("SELECT MIN(sent_at), MAX(sent_at), COUNT(*) FROM channel_messages").fetchone())
for r in con.execute(
    "SELECT id, handle, msg_id, sent_at, substr(raw_text,1,160) head FROM channel_messages ORDER BY sent_at ASC, id ASC LIMIT 8"
):
    print(" ", dict(r))

print("\n========== D. bot-outbound-looking cards (signal language) ==========")
# Heuristic: messages that look like fired signal cards, not room tips
sig_pats = [
    "%SIGNAL%",
    "%ENTRADA%",
    "%ENTRAR%",
    "%FIRE%",
    "%G0%",
    "%Gale%",
    "%GALE%",
    "%PLATINUM%",
    "%SEQUENCE%",
    "%consenso%",
    "%CONSENSO%",
    "%Disparado%",
]
seen = set()
hits = []
for pat in sig_pats:
    for r in con.execute(
        """
        SELECT id, handle, sent_at, substr(raw_text,1,220) head
        FROM channel_messages
        WHERE raw_text LIKE ?
        ORDER BY sent_at ASC, id ASC
        LIMIT 3
        """,
        (pat,),
    ):
        key = (r["id"],)
        if key in seen:
            continue
        seen.add(key)
        hits.append(dict(r))
hits.sort(key=lambda x: (x["sent_at"] or "", x["id"]))
print("earliest signal-like channel_messages:")
for h in hits[:15]:
    print(" ", h)

print("\n========== E. activity_feed / engine_events / signals tables ==========")
for t in ["activity_feed", "engine_events", "signals", "outcome_history", "bot_startup"]:
    try:
        cols = [c[1] for c in con.execute(f"PRAGMA table_info({t})")]
        print(f"\n--- {t} cols={cols[:12]}... ---")
        # find a timestamp-ish column
        ts = None
        for c in cols:
            if any(x in c.lower() for x in ("at", "time", "ts", "created", "fired", "sent")):
                ts = c
                break
        if ts:
            print(" min/max:", con.execute(f"SELECT MIN([{ts}]), MAX([{ts}]), COUNT(*) FROM [{t}]").fetchone())
            for r in con.execute(f"SELECT * FROM [{t}] ORDER BY [{ts}] ASC LIMIT 3"):
                d = dict(r)
                # trim long fields
                for k, v in list(d.items()):
                    if isinstance(v, str) and len(v) > 120:
                        d[k] = v[:120] + "..."
                print(" ", d)
        else:
            print(" count:", con.execute(f"SELECT COUNT(*) FROM [{t}]").fetchone()[0])
    except Exception as e:
        print(t, "ERR", e)

print("\n========== F. VERDICT ==========")
online = con.execute(
    """
    SELECT sent_at, handle, substr(raw_text,1,120)
    FROM channel_messages
    WHERE raw_text LIKE '%ONLINE%' OR raw_text LIKE '%BacBo Royal%'
    ORDER BY sent_at ASC LIMIT 1
    """
).fetchone()
first_sig = con.execute(
    "SELECT id, fired_at, signal_kind, color, source_floor FROM consensus_signals ORDER BY fired_at, id LIMIT 1"
).fetchone()
print("FIRST_ONLINE_BANNER:", tuple(online) if online else None)
print("FIRST_CONSENSUS_SIGNAL:", dict(first_sig) if first_sig else None)
print("""
INTERPRETATION:
- ONLINE banner = bot started posting to Telegram (can be before any consensus_signals row).
- consensus_signals starts at id=5 → rows 1-4 likely deleted/migrated; first STORED fire ≠ first ever chat message.
- Mr_iv4 has no peer column; money chat was default target — ONLINE on 17/03 proves chat was live that day.
""")
con.close()
PY
