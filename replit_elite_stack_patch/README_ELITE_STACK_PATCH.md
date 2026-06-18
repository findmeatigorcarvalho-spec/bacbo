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

It also patches the dashboard/API:

- `artifacts/api-server/src/routes/bot.ts`
  - adds `/api/bot/result-lag-patterns`
  - adds `/api/bot/elite-stack-audit`
  - adds `/api/bot/room-cleaner-report`
  - adds `/api/bot/omni-score-report`
- `artifacts/dashboard/src/lib/api.ts`
  - adds frontend methods for those endpoints
- `artifacts/dashboard/src/pages/DashboardPage.tsx`
  - fetches the new reports for the Engine tab
- `artifacts/dashboard/src/components/tabs/EngineTab.tsx`
  - shows the lag-5 pattern panel and Elite Stack summary

Run in Replit Shell:

```bash
cd bot
python elite_stack_audit.py
```

Optional room cleanup after reviewing the report:

```bash
cd bot
python room_cleaner.py --apply
```
