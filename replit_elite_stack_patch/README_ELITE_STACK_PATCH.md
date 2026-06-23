Elite Stack Patch
=================

Copy the `bot/` folder from this patch into the root of your Replit project.
It adds four safe, read-only-by-default tools:

1. `bot/room_cleaner.py`
   - validates active/muted/stale/weak rooms
   - writes `bot/data/room_cleaner_report.json`
   - dry-run by default
   - `python room_cleaner.py --apply` applies conservative room-table changes

2. `bot/omni_score.py`
   - scores signals from room WR, color WR, hour WR, floor WR, blocked-winner
     history, room DNA, and freshness
   - writes `bot/data/omni_score_report.json`

3. `bot/early_result_audit.py`
   - measures whether fired signals resolved early enough to be true pre-result
     edge candidates
   - writes `bot/data/early_result_audit.json`

4. `bot/elite_stack_audit.py`
   - runs all three tools and writes `bot/data/elite_stack_audit.json`

5. `bot/result_lag_miner.py`
   - mines the "same result around 5 rounds later" pattern from resolved
     outcomes
   - writes `bot/data/result_lag_patterns.json`

6. `bot/martingale_audit.py`
   - audits G0/G1/G2/G3 recovery value
   - writes `bot/data/martingale_audit.json`

7. `bot/truth_verifier.py`
   - separates direct Twin225/casino truth from bot/Telegram DB-inferred truth
   - creates future direct-result tables
   - writes `bot/data/truth_verification_report.json`

8. `bot/volume_frontier.py`
   - audits the true volume-vs-WR frontier since day one
   - proves which daily signal volumes have actually happened at each WR band
   - writes `bot/data/volume_frontier_report.json`

9. `bot/g0_offset_oracle.py`
   - mines future-round continuation after G0 wins
   - finds cells like SEQUENCE/LIVE/BLUE offset 1-6
   - writes `bot/data/g0_offset_oracle_report.json`

10. `bot/tri_brain_score.py`
   - scores win/loss/tie brains separately
   - produces FIRE_COLOR_G0 / SHADOW_COLOR / SHADOW_TIE / BLOCK_LOSS_RISK
   - writes `bot/data/tri_brain_report.json`

11. `bot/edge_whitelist_engine.py`
   - combines elite room/hour/color cells, floor/kind/hour/color cells,
     G0 offset oracle, Tri-Brain verdicts, and loss-risk cells
   - writes `bot/data/edge_whitelist_engine.json`

12. `bot/floor_stack_registry.py`
   - classifies historical floors/camadas into PRECISION, BALANCED, VOLUME,
     SHADOW, and BLOCK lanes
   - writes `bot/data/floor_stack_registry_report.json`

13. `bot/skyscraper_floor_factory.py`
   - generates new virtual floors from peak days, room/hour/color cells,
     floor/kind/hour/color cells, G0 offsets, and loss-risk cells
   - writes `bot/data/skyscraper_floor_factory_report.json`

14. `bot/skyscraper_stack.py`
   - combines the best floors, generated floors, room cells, martingale,
     timing, and truth warnings into one stack blueprint
   - writes `bot/data/skyscraper_stack_report.json`

15. `bot/legacy_peak_355.py`
   - mines old Pawtucket moving time windows across the whole day that may
     have produced very early G0/offset results
   - writes `bot/data/legacy_peak_355_report.json`
   - matching live signals get a `LEGACY_355_PAWTUCKET` warning added to
     the signal text only when the current local time is inside that mined
     hot window

It also patches the dashboard/API:

- `artifacts/api-server/src/routes/bot.ts`
  - adds `/api/bot/result-lag-patterns`
  - adds `/api/bot/elite-stack-audit`
  - adds `/api/bot/room-cleaner-report`
  - adds `/api/bot/omni-score-report`
  - adds `/api/bot/martingale-audit`
  - adds `/api/bot/truth-verification`
- `artifacts/dashboard/src/lib/api.ts`
  - adds frontend methods for those endpoints
- `artifacts/dashboard/src/pages/DashboardPage.tsx`
  - fetches the new reports for the Engine tab
- `artifacts/dashboard/src/components/tabs/EngineTab.tsx`
  - shows truth verification, martingale, lag-5 pattern, and Elite Stack summary

Run in Replit Shell:

```bash
cd ~/workspace
python -u install_edge_tools.py
export EDGE_POLICY_MODE=shadow
```

The installer downloads the tools, patches `bot/signal_handler.py`, compiles
the patched files, and regenerates the fast reports. If your `signal_handler.py`
is an older version, it installs EdgePolicy in shadow-only mode so it logs
ALLOW/BLOCK decisions without changing live signal flow.

Manual report refresh:

```bash
cd ~/workspace
python -u bot/elite_stack_audit.py --db bot/bacbo.db
python -u bot/volume_frontier.py --db bot/bacbo.db
python -u bot/g0_offset_oracle.py --db bot/bacbo.db
python -u bot/legacy_peak_355.py --db bot/bacbo.db --slot-minutes 30
python -u bot/tri_brain_score.py --db bot/bacbo.db
python -u bot/edge_whitelist_engine.py --db bot/bacbo.db
python -u bot/floor_stack_registry.py --db bot/bacbo.db
python -u bot/skyscraper_floor_factory.py --db bot/bacbo.db
python -u bot/skyscraper_stack.py --db bot/bacbo.db
```

Optional room cleanup after reviewing the report:

```bash
cd ~/workspace
python -u bot/room_cleaner.py --db bot/bacbo.db --apply
```

Legacy moving-window warning controls:

```bash
# default: warnings are enabled when the signal matches its current mined
# Pawtucket moving window from bot/data/legacy_peak_355_report.json
export EDGE_LEGACY_355_WARN=1

# testing only: force the warning matcher on outside its mined window
export EDGE_LEGACY_355_ALWAYS_WARN=1
```
