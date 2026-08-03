#!/usr/bin/env bash
# Full census: signal KINDS / FAMILIES / RESULTS / reached-or-not since Mar 17.
# Run on Replit:
#   curl -fsSL -H 'Cache-Control: no-cache' -o CENSUS.sh \
#     'https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/cursor/add-engine-gate-registry-d5ba/replit_elite_stack_patch/REPLIT_SIGNAL_TYPE_CENSUS.sh'
#   bash CENSUS.sh | tee signal_type_census.txt
set -euo pipefail
cd /home/runner/workspace 2>/dev/null || cd "$(dirname "$0")/.."

python3 - <<'PY'
import json, sqlite3
from collections import Counter, defaultdict
from pathlib import Path

con = sqlite3.connect("file:bot/bacbo.db?mode=ro", uri=True)
con.row_factory = sqlite3.Row
SINCE = "2026-03-17"

print("=" * 72)
print("SIGNAL / RESULT / FAMILY CENSUS since", SINCE)
print("=" * 72)
print("""
TAXONOMY (what you asked for):
  ROLE:     ONLINE | FIRE | RESULT | UPDATE/OPS
  FAMILY:   money-fire | timed-fire | result | online | ops
  KIND:     SOLO_ELITE | GOLDEN | PLATINUM | SEQUENCE | EMERGINDO | ALERTA | ULTRA_TIE | ...
  REACHED:  outcome filled (win/loss/tie/expire) vs still open / blocked never sent
""")

# ── 1. FIRE kinds in consensus_signals ─────────────────────────────────────
print("\n========== 1. FIRE kinds (consensus_signals) ==========")
rows = con.execute(
    f"""
    SELECT signal_kind,
           COUNT(*) n,
           SUM(CASE WHEN outcome IS NULL OR outcome='' THEN 1 ELSE 0 END) open_no_result,
           SUM(CASE WHEN lower(COALESCE(outcome,''))='win' THEN 1 ELSE 0 END) wins,
           SUM(CASE WHEN lower(COALESCE(outcome,''))='loss' THEN 1 ELSE 0 END) losses,
           SUM(CASE WHEN lower(COALESCE(outcome,'')) LIKE '%tie%' THEN 1 ELSE 0 END) ties,
           SUM(CASE WHEN lower(COALESCE(outcome,'')) NOT IN ('','win','loss') AND outcome IS NOT NULL THEN 1 ELSE 0 END) other_outcomes,
           MIN(fired_at) first_at,
           MAX(fired_at) last_at
    FROM consensus_signals
    WHERE fired_at >= ?
    GROUP BY signal_kind
    ORDER BY n DESC
    """,
    (SINCE,),
).fetchall()
print(f"{'KIND':22} {'N':>6} {'OPEN':>6} {'WIN':>6} {'LOSS':>6} {'OTHER':>6}  FIRST → LAST")
kinds = []
for r in rows:
    kinds.append(r["signal_kind"] or "(null)")
    print(
        f"{(r['signal_kind'] or '(null)'):22} {r['n']:6} {r['open_no_result']:6} "
        f"{r['wins']:6} {r['losses']:6} {r['other_outcomes']:6}  {r['first_at']} → {r['last_at']}"
    )
print(f"\nDISTINCT FIRE KINDS: {len(kinds)}")
print("LIST:", ", ".join(kinds))

total = con.execute(
    f"SELECT COUNT(*) FROM consensus_signals WHERE fired_at>=?", (SINCE,)
).fetchone()[0]
with_result = con.execute(
    f"""SELECT COUNT(*) FROM consensus_signals
        WHERE fired_at>=? AND outcome IS NOT NULL AND TRIM(outcome)!=''""",
    (SINCE,),
).fetchone()[0]
print(f"TOTAL FIRES: {total}  WITH RESULT CARD OUTCOME: {with_result}  OPEN/NO OUTCOME: {total-with_result}")

# ── 2. Outcome / result vocabulary ─────────────────────────────────────────
print("\n========== 2. RESULT outcome values (what 'reached') ==========")
for r in con.execute(
    f"""
    SELECT COALESCE(NULLIF(TRIM(outcome),''),'(none)') outcome, COUNT(*) n
    FROM consensus_signals WHERE fired_at>=?
    GROUP BY 1 ORDER BY n DESC
    """,
    (SINCE,),
):
    print(f"  {r['outcome']:20} {r['n']}")

print("\ngale / recovery style:")
for r in con.execute(
    f"""
    SELECT COALESCE(CAST(won_at_gale AS TEXT),'(null)') gale, COUNT(*) n
    FROM consensus_signals WHERE fired_at>=? AND outcome IS NOT NULL AND TRIM(outcome)!=''
    GROUP BY 1 ORDER BY n DESC
    """,
    (SINCE,),
):
    print(f"  won_at_gale={r['gale']:8} {r['n']}")

# ── 3. Families via signal_tier / classification / source_floor ─────────────
print("\n========== 3. FAMILIES (tier / classification / floor) ==========")
for col in ("signal_tier", "classification", "source_floor"):
    print(f"\n--- by {col} ---")
    try:
        for r in con.execute(
            f"""
            SELECT COALESCE(CAST({col} AS TEXT),'(null)') v, COUNT(*) n
            FROM consensus_signals WHERE fired_at>=?
            GROUP BY 1 ORDER BY n DESC LIMIT 40
            """,
            (SINCE,),
        ):
            print(f"  {r['v'][:40]:40} {r['n']}")
    except Exception as e:
        print(" ", e)

# ── 4. Kind × floor (how many fire "skins" by floor) ───────────────────────
print("\n========== 4. KIND × FLOOR (top cells) ==========")
for r in con.execute(
    f"""
    SELECT signal_kind, COALESCE(source_floor,'LIVE') floor, COUNT(*) n
    FROM consensus_signals WHERE fired_at>=?
    GROUP BY 1,2 ORDER BY n DESC LIMIT 40
    """,
    (SINCE,),
):
    print(f"  {r['signal_kind'] or '?':18} × {r['floor']:12} = {r['n']}")

# ── 5. Blocked = proposed but NOT reached Telegram as fire ─────────────────
print("\n========== 5. BLOCKED (proposed, often NEVER reached chat as FIRE) ==========")
try:
    for r in con.execute(
        f"""
        SELECT signal_kind, COUNT(*) n,
               SUM(CASE WHEN outcome IS NOT NULL AND TRIM(outcome)!='' THEN 1 ELSE 0 END) later_known
        FROM blocked_signals
        WHERE blocked_at>=?
        GROUP BY signal_kind ORDER BY n DESC
        """,
        (SINCE,),
    ):
        print(f"  {r['signal_kind'] or '?':18} blocked={r['n']:5} later_outcome_known={r['later_known']}")
    print("top gate_reason:")
    for r in con.execute(
        f"""
        SELECT gate_reason, COUNT(*) n FROM blocked_signals
        WHERE blocked_at>=? GROUP BY 1 ORDER BY n DESC LIMIT 15
        """,
        (SINCE,),
    ):
        print(f"  {r['gate_reason'][:50]:50} {r['n']}")
except Exception as e:
    print(e)

# ── 6. Timeline: first of each kind ────────────────────────────────────────
print("\n========== 6. FIRST appearance of each FIRE kind ==========")
for r in con.execute(
    f"""
    SELECT signal_kind, MIN(fired_at) first_at, MIN(id) first_id
    FROM consensus_signals WHERE fired_at>=?
    GROUP BY signal_kind ORDER BY first_at
    """,
    (SINCE,),
):
    print(f"  {r['first_at']}  id={r['first_id']:<6}  {r['signal_kind']}")

# ── 7. JSON export for Cursor ──────────────────────────────────────────────
out = {
    "since": SINCE,
    "note": "ONLINE banners are NOT in consensus_signals. Telegram chat has ONLINE/FIRE/RESULT/UPDATE types; DB tracks FIRE+outcome mainly.",
    "fire_kinds": [dict(r) for r in rows],
    "telegram_roles_expected": {
        "ONLINE": "startup banner — NO result card (what you pasted 17 Mar)",
        "FIRE": "SOLO_ELITE/GOLDEN/PLATINUM/SEQUENCE/... enter cards",
        "RESULT": "WIN/LOSS/TIE/G0/G1/forensic under parent fire",
        "UPDATE_OPS": "expire, miss, quarantine, delivery audit",
    },
}
Path("signal_type_census.json").write_text(json.dumps(out, indent=2, default=str))
print("\nWrote signal_type_census.json")

print("""
========== HOW THIS MAPS TO YOUR PASTE ==========
Your 17 Mar 4:37–4:56 messages are ALL role=ONLINE (same template ×4 restarts).
That is 1 TYPE. ONLINE has no RESULT card — correct, not a missing result.
Telegram UI 4:37 AM ≈ footer 08:37:17 UTC (timezone display).
Chat label 'G1 Unique' in export = that peer's name in the dump.

TO CENSUS EVERY CARD TYPE ACTUALLY IN TELEGRAM (including ONLINE/UPDATE):
  export chat history since Mar 17 → paste link, OR run Telethon scrape.
DB census above = FIRE kinds + whether outcome was recorded (reached resolve).
""")
con.close()
PY
