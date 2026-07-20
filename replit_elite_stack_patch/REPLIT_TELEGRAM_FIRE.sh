#!/usr/bin/env bash
# Diagnose silent Telegram + re-enable fallbacks + test-ping TARGET + restart.
# Bot is up / rooms recv / GameCoach sends — but no FIRED cards to chat.
set -euo pipefail
cd /home/runner/workspace
PY=python3
SHA="${LUXURY_PATCH_SHA:-cursor/add-engine-gate-registry-d5ba}"
BASE="https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/${SHA}/replit_elite_stack_patch"

echo "========== [1/6] why no fires? (read-only) =========="
$PY <<'PY'
from pathlib import Path
import re, json, os, sqlite3
from datetime import datetime, timezone

log = Path("logs/bot_live.log").read_text(errors="ignore") if Path("logs/bot_live.log").exists() else ""
tail = "\n".join(log.splitlines()[-400:])
print("utc_now", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"), "hour", datetime.now(timezone.utc).hour)
print("EDGE_POLICY_MODE", os.environ.get("EDGE_POLICY_MODE") or "(unset in this shell)")
print("FALLBACKS_ENABLED", os.environ.get("FALLBACKS_ENABLED") or "(unset)")
print("TELEGRAM_TARGET_PEER", os.environ.get("TELEGRAM_TARGET_PEER") or "(unset)")

for pat, label in [
    (r"FIRED|SEQUENCE/FIRED|signal sent", "fire_hits"),
    (r"EdgePolicy.*ALLOW|EDGE_LUXURY.*ALLOW", "allow_hits"),
    (r"EdgePolicy.*BLOCK|FLOOR_BLOCKED|DENY_FLOOR", "block_hits"),
    (r"QUIET — no signal fired", "quiet_hits"),
    (r"Blocked-hour|blocked hour|bad hrs|HourEval", "hour_hits"),
    (r"send\(|Send failed|FloodWait|TARGET|FallbackSender|FallbackResult", "send_hits"),
    (r"GameCoach.*sent", "coach_sent"),
]:
    print(label, len(re.findall(pat, tail, re.I)))

print("--- last fire/allow/block/quiet/coach ---")
for ln in re.findall(r".*(?:FIRED|EdgePolicy|QUIET|Blocked-hour|GameCoach|FallbackSender|send failed|ALLOW|FLOOR_BLOCK).*", tail, re.I)[-25:]:
    print(ln[:200])

# AutoIntel / color blocks
for rel in ["bot/data/color_hour_blocks.json", "bot/data/audit_report.json", "bot/data/fragility_state.json"]:
    p = Path(rel)
    if p.exists():
        try:
            d = json.loads(p.read_text())
            print(rel, "keys", list(d)[:12] if isinstance(d, dict) else type(d))
            if isinstance(d, dict):
                for k in ("blocked_hours", "solo_bad_hours", "platinum_bad_hours", "bad_hours", "SOLO_ELITE", "PLATINUM"):
                    if k in d:
                        print(" ", k, d[k])
        except Exception as e:
            print(rel, e)

# recent consensus
db = Path("bot/bacbo.db") if Path("bot/bacbo.db").exists() else Path("bacbo.db")
if db.exists():
    con = sqlite3.connect(str(db), timeout=30)
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute(
            """SELECT id, fired_at, signal_kind, color, source_floor, total_score, outcome
               FROM consensus_signals ORDER BY id DESC LIMIT 12"""
        ).fetchall()
        print("db", db, "last_consensus")
        for r in rows:
            print(dict(r))
    except Exception as e:
        print("db_fail", e)
    try:
        n = con.execute(
            "SELECT COUNT(*) FROM consensus_signals WHERE fired_at >= datetime('now','-6 hours')"
        ).fetchone()[0]
        print("consensus_last_6h", n)
    except Exception as e:
        print("count_fail", e)
    con.close()
PY

echo "========== [2/6] refresh fallbacks + supervisor (FALLBACKS ON) =========="
curl -fsSL -H "Cache-Control: no-cache" -o bot/lux_sqlite_harden.py "$BASE/bot/lux_sqlite_harden.py"
curl -fsSL -H "Cache-Control: no-cache" -o bot/runtime_supervisor.py "$BASE/bot/runtime_supervisor.py"
curl -fsSL -H "Cache-Control: no-cache" -o bot/fallback_signal_sender.py "$BASE/bot/fallback_signal_sender.py"
curl -fsSL -H "Cache-Control: no-cache" -o bot/fallback_result_sender.py "$BASE/bot/fallback_result_sender.py"
$PY -m py_compile bot/lux_sqlite_harden.py bot/runtime_supervisor.py bot/fallback_signal_sender.py bot/fallback_result_sender.py

# Default fallbacks ON again (DB WAL harden is in place)
cat > luxury_building.env <<'EOF'
export EDGE_POLICY_MODE=luxury
export EDGE_LUXURY_FLOOR_GATE=1
export FALLBACK_SEND_BLOCKED=0
export FALLBACKS_ENABLED=1
export FALLBACK_START_DELAY_SECS=20
export TELEGRAM_TARGET_PEER=6774605259
export BOT_TZ=America/Sao_Paulo
EOF

# Ensure supervisor treats FALLBACKS_ENABLED=1 as on
# (empty/0/false = off)

echo "========== [3/6] Telegram test ping to TARGET =========="
set -a
source ./luxury_building.env
set +a
export TELEGRAM_SESSION_STRING="$(tr -d '\n' < .telegram_session_string 2>/dev/null || true)"
export TELEGRAM_TARGET_PEER=6774605259
export PYTHONPATH="/home/runner/workspace/bot:/home/runner/workspace:${PYTHONPATH:-}"

$PY <<'PY'
import asyncio, os, sys
from pathlib import Path
sys.path.insert(0, str(Path("bot").resolve()))
sys.path.insert(0, str(Path(".").resolve()))
from telethon import TelegramClient
from telethon.sessions import StringSession

def _load_api():
    api_id = os.environ.get("TELEGRAM_API_ID") or os.environ.get("API_ID") or ""
    api_hash = os.environ.get("TELEGRAM_API_HASH") or os.environ.get("API_HASH") or ""
    target = None
    try:
        import config as cfg
        api_id = api_id or getattr(cfg, "API_ID", None) or getattr(cfg, "TELEGRAM_API_ID", None) or ""
        api_hash = api_hash or getattr(cfg, "API_HASH", None) or getattr(cfg, "TELEGRAM_API_HASH", None) or ""
        target = getattr(cfg, "TARGET", None)
    except Exception as e:
        print("config_import", e)
    # .env fallback
    envp = Path(".env")
    if envp.exists() and (not api_id or not api_hash):
        for line in envp.read_text(errors="ignore").splitlines():
            if "=" not in line or line.strip().startswith("#"):
                continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if k in ("TELEGRAM_API_ID", "API_ID") and not api_id:
                api_id = v
            if k in ("TELEGRAM_API_HASH", "API_HASH") and not api_hash:
                api_hash = v
    return int(api_id), str(api_hash), target

async def main():
    api_id, api_hash, target = _load_api()
    sess = (os.environ.get("TELEGRAM_SESSION_STRING") or "").strip()
    if len(sess) < 50:
        sess = Path(".telegram_session_string").read_text().strip()
    peer = os.environ.get("TELEGRAM_TARGET_PEER") or "6774605259"
    print("api_id", api_id, "session_len", len(sess), "peer", peer, "config.TARGET", target)
    if not api_id or not api_hash:
        print("TEST_PING FAIL: missing API_ID/API_HASH")
        return
    client = TelegramClient(StringSession(sess), api_id, api_hash)
    await client.connect()
    if not await client.is_user_authorized():
        print("TEST_PING FAIL: session not authorized")
        await client.disconnect()
        return
    ent = await client.get_entity(int(peer))
    msg = await client.send_message(
        ent,
        "LUXURY TEST PING\nIf you see this, Telegram delivery to TARGET works.\nSignal cards still need engine FIRED rows.",
    )
    print("TEST_PING OK id=", msg.id, "to", getattr(ent, "username", None) or peer)
    await client.disconnect()

asyncio.run(main())
PY

echo "========== [4/6] restart with fallbacks =========="
pkill -9 -f 'bacbo_royal_complete.py' 2>/dev/null || true
pkill -9 -f 'runtime_supervisor.py' 2>/dev/null || true
pkill -9 -f 'fallback_signal_sender.py' 2>/dev/null || true
pkill -9 -f 'fallback_result_sender.py' 2>/dev/null || true
sleep 2

export TELEGRAM_SESSION_STRING="$(tr -d '\n' < .telegram_session_string)"
export TELEGRAM_TARGET_PEER=6774605259
export FALLBACKS_ENABLED=1
export FALLBACK_START_DELAY_SECS=20
export EDGE_POLICY_MODE=luxury
export EDGE_LUXURY_FLOOR_GATE=1
export FALLBACK_SEND_BLOCKED=0
export BOT_TZ=America/Sao_Paulo
export PYTHONPATH="/home/runner/workspace/bot:/home/runner/workspace:${PYTHONPATH:-}"

echo "===== TELEGRAM_FIRE marker $(date -u +%Y-%m-%dT%H:%M:%SZ) =====" >> logs/bot_live.log

nohup env EDGE_POLICY_MODE=luxury EDGE_LUXURY_FLOOR_GATE=1 FALLBACKS_ENABLED=1 \
  FALLBACK_START_DELAY_SECS=20 FALLBACK_SEND_BLOCKED=0 \
  BOT_TZ=America/Sao_Paulo \
  TELEGRAM_SESSION_STRING="$TELEGRAM_SESSION_STRING" \
  TELEGRAM_TARGET_PEER=6774605259 \
  PYTHONPATH="$PYTHONPATH" \
  python3 -u bot/runtime_supervisor.py > /tmp/luxury_supervisor.log 2>&1 &
echo "supervisor pid=$!"

echo "========== [5/6] settle 70s =========="
sleep 25
echo "----- 25s procs -----"
pgrep -af 'runtime_supervisor|bacbo_royal|fallback_' || true
sleep 45
echo "----- 70s procs -----"
pgrep -af 'runtime_supervisor|bacbo_royal|fallback_' || true

echo "========== [6/6] verdict =========="
$PY <<'PY'
from pathlib import Path
import re, subprocess, sqlite3
log = Path("logs/bot_live.log").read_text(errors="ignore")
idx = log.rfind("===== TELEGRAM_FIRE marker")
chunk = log[idx:] if idx >= 0 else log[-10000:]
print("run_forever", "run_forever" in chunk or "starting run_forever()" in chunk)
print("NameError_state", "NameError: name 'state'" in chunk)
print("FIRED", len(re.findall(r"FIRED|SEQUENCE/FIRED", chunk)))
print("ALLOW", len(re.findall(r"ALLOW", chunk)))
print("QUIET", len(re.findall(r"QUIET — no signal fired", chunk)))
print("Blocked-hour", len(re.findall(r"Blocked-hour|blocked hour", chunk, re.I)))
print("GameCoach_sent", len(re.findall(r"GameCoach.*sent", chunk)))
print("--- procs ---")
print(subprocess.getoutput("pgrep -af 'runtime_supervisor|bacbo_royal|fallback_' || echo NONE"))
print("--- fallback tails ---")
for rel in ["logs/fallback_sender.log", "logs/fallback_result_sender.log"]:
    p = Path(rel)
    print("##", rel)
    print("\n".join(p.read_text(errors="ignore").splitlines()[-12:]) if p.exists() else "missing")
print("--- last bot 20 ---")
print("\n".join(Path("logs/bot_live.log").read_text(errors="ignore").splitlines()[-20:]))
db = Path("bot/bacbo.db")
con = sqlite3.connect(str(db), timeout=30)
n = con.execute("SELECT COUNT(*) FROM consensus_signals WHERE fired_at >= datetime('now','-2 hours')").fetchone()[0]
print("consensus_last_2h", n)
con.close()
procs = subprocess.getoutput("pgrep -af 'bacbo_royal|fallback_signal' || true")
ok = "bacbo_royal" in procs and "fallback_signal" in procs and "NameError: name 'state'" not in chunk
print("VERDICT:", "OK — bacbo+fallbacks up; check Telegram for TEST PING" if ok else "BAD — paste ALL output")
print("NOTE: If TEST PING arrived but still no signal cards, engine is not FIRED (gates/hour/gale) — not a Telegram outage.")
PY

echo
echo "DONE. Paste ALL output."
echo "1) Did TEST PING land in Telegram chat?"
echo "2) Paste this output."
