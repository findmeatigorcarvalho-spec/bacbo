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
