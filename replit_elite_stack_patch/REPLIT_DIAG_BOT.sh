#!/usr/bin/env bash
# Diagnose why bot_live / fallback children are not visible under supervisor.
set -euo pipefail
cd /home/runner/workspace
source luxury_building.env 2>/dev/null || true
export EDGE_POLICY_MODE=luxury EDGE_LUXURY_FLOOR_GATE=1 FALLBACK_SEND_BLOCKED=0

echo "===== MODE / env ====="
echo "EDGE_POLICY_MODE=$EDGE_POLICY_MODE"
echo "EDGE_LUXURY_FLOOR_GATE=$EDGE_LUXURY_FLOOR_GATE"

echo "===== all python procs ====="
ps aux | grep -E 'python|bot_|fallback|bacbo|signal' | grep -v grep || echo "(none)"

echo "===== supervisor file ====="
ls -la bot/runtime_supervisor.py 2>/dev/null || echo "MISSING supervisor"
# show what commands it launches
python3 - <<'PY'
from pathlib import Path
p=Path('bot/runtime_supervisor.py')
if not p.exists():
    raise SystemExit(0)
t=p.read_text(encoding='utf-8', errors='replace')
print('supervisor_bytes', len(t))
for key in ['bot_live','fallback','Popen','subprocess','argv','cmd','logs/']:
    if key in t:
        print('has', key)
# print launch-related lines
for i,line in enumerate(t.splitlines(),1):
    low=line.lower()
    if any(x in low for x in ['popen','subprocess','bot_live','fallback','restart','cmd','argv','execl','os.system']):
        print(f'{i}: {line[:200]}')
PY

echo "===== logs dir listing ====="
ls -lah logs/ 2>/dev/null | head -n 40 || echo "no logs/"

echo "===== newest log tails ====="
for f in $(ls -t logs/* 2>/dev/null | head -n 12); do
  echo "-------- $f --------"
  tail -n 40 "$f" || true
done

echo "===== /tmp luxury supervisor ====="
tail -n 60 /tmp/luxury_supervisor.log 2>/dev/null || true

echo "===== key bot entrypoints ====="
ls -la bot/bacbo_royal_complete.py bot/bot_live.py bot/signal_handler.py \
  bot/fallback_signal_sender.py bot/fallback_result_sender.py \
  main.py start_luxury.sh 2>/dev/null || true

echo "===== try import edge policy ====="
python3 - <<'PY'
import os, sys
from pathlib import Path
sys.path[:0]=[str(Path('.').resolve()), str(Path('bot').resolve())]
os.environ.setdefault('EDGE_POLICY_MODE','luxury')
try:
    import edge_live_policy as e
    print('edge_live_policy OK', getattr(e,'EDGE_POLICY_MODE',None), 'mode_env', os.environ.get('EDGE_POLICY_MODE'))
    if hasattr(e,'_luxury_sets'):
        live, blocked = e._luxury_sets()
        print('live_n', len(live), 'blocked', sorted(blocked)[:10])
except Exception as ex:
    print('edge_live_policy FAIL', type(ex).__name__, ex)
PY

echo
echo "DONE. Paste ALL of this output to Cursor."
