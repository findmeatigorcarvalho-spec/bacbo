# Replit Agent Memory Index (captured from Replit `.agents/memory/MEMORY.md` 2026-08-03)

This is the **project knowledge** the Replit Agent saved. Not Google Antigravity (`.gemini` missing on Replit).

## Critical system facts

| Topic | Rule |
|-------|------|
| Idle suspension | Dev workspace sleeps → all workflows freeze together; fix = **24/7 deployment**, not code |
| Win-rate regime | May ~84% WR was game regime; June ~72% systemic; filtering ceiling ~75% |
| Gate auto-tuner | Silently re-disables quality gates that block <~60%WR; force-enable at reader |
| SeqAI | Additive-only boost (cap 1.5); never reduce volume |
| Floors | ~39 floors fire; all watch ONE game → correlated dupes; can't multiply volume by more doors |
| Connection healing | "alive but deaf"; trust `_last_recv_wall`; soft reconnect needs `_soft_reconnect_active` |
| Async restart | Use `_restart_self`/`os._exit`, **never** `sys.exit` in asyncio |
| Volume bottleneck | Driven by generation+uptime, not gates; ~700-850/day weak regime |
| Muted rooms | High-WR muted often Football Studio/Speed Bac — verify GAME not WR |
| Bet window | `_BET_WINDOW_SECS=90` for G0-only |
| SEQUENCE floors | Cross-floor dedup = mutual exclusion (caps volume); additive floor needs floor-local dedup |
| GOLDEN gauntlet | Lowering analyzer GOLDEN threshold alone is NO-OP; must lower AccumHold/Sniper/Markov floors |
| sklearn | Needed to unpickle SEQUENCE `.pkl`; missing = silent hard-block of ALL SEQUENCE signals |
| Event-loop saturation | 35-floor fan-out can starve loop; only EXTERNAL restart recovers |
| Knowledge gate | Old 100%-forever seal was absorbing-state; replaced WR-floor in `_gates_MAR21.py` |
| Replay flood | Pts desync re-dumps months-old history → FloodWait; StopPropagation on >1h-old msgs |
| External watchdog | Out-of-loop process is only recovery for wedged loop |

## Memory files on Replit (`.agents/memory/`)

- MEMORY.md (index)
- bacbo-workspace-suspension.md
- bacbo-winrate-regime.md
- bacbo-gate-system.md
- bacbo-env-quirks.md
- bacbo-sequence-ai.md
- bacbo-parallel-gate-engines.md
- bacbo-connection-healing.md
- bacbo-asyncio-restart.md
- bacbo-db-write-contention.md
- bacbo-volume-bottleneck.md
- bacbo-muted-rooms-crossgame.md
- bacbo-bet-window-g0.md
- bacbo-autochb-spiral.md
- bacbo-deployment-image-size.md
- bacbo-deploy-build-ordering.md
- bacbo-deployment-24x7.md
- bacbo-sequence-predictor.md
- bacbo-sequence-floors.md
- bacbo-relay-quiet-window.md
- bacbo-data-history.md
- bacbo-input-flow-detector.md
- bacbo-sweet-spot.md
- bacbo-hour-advisory.md
- bacbo-quarantine-dup-notify.md
- bacbo-golden-fire-gauntlet.md
- bacbo-signal-wall-semantics.md
- bacbo-time-to-result.md
- bacbo-telethon-secerr.md
- bacbo-event-loop-saturation.md
- bacbo-knowledge-gate.md
- bacbo-implicit-sklearn-dep.md
- bacbo-replay-flood-cascade.md
- bacbo-external-watchdog.md
- (+ accuracy-guardian, hour-gates, result-card-g1-color, sequence-suspension, signal-threshold-tuning, repl-platform-quirks)

## Also on Replit (binary agent sessions)

`.local/state/replit/agent/.agent_state_*.bin` (~31 MB total) — Replit Agent session state blobs (not plain text chat).

## Extract pack (fixed)

```bash
curl -fsSL -H 'Cache-Control: no-cache' -o EXTRACT_AGENT.sh \
  'https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/cursor/add-engine-gate-registry-d5ba/replit_elite_stack_patch/REPLIT_EXTRACT_AGENT_HISTORY.sh'
bash EXTRACT_AGENT.sh | tee extract_agent_report.txt
ls -lah bacbo_agent_history*.zip
```
