# Current State

Audit timestamp: 2026-10-14 UTC

## Scope and handling

This is a read-only forensic assessment of the existing checkout. No bot, installer,
deployment script, supervisor, Telegram client, or database migration was run. No
secret-bearing file was opened. The only new material is this requested report set.

## Workspace identity

- Project path: `/workspace`
- Repository size on this machine: approximately 12 MB
- Git branch: `cursor/add-engine-gate-registry-d5ba`
- Upstream: `origin/cursor/add-engine-gate-registry-d5ba`
- Git state before report creation: clean; no uncommitted files
- Tracked files: 337
- Full application status: **not present in this checkout**

The checkout is primarily:

- `/workspace/replit_elite_stack_patch/` — patch modules, operational scripts,
  historical reports, and documentation
- `/workspace/bot/` — configuration/taxonomy modules and distilled data
- `/workspace/tests/` — tests for the patch/configuration layer
- `/workspace/replit_elite_stack_patch.zip` — a small 229,152-byte patch archive,
  not a full application or database backup

## Recent commits

| Commit | Date (UTC) | Subject |
|---|---|---|
| `045a57b` | 2026-10-13 17:24 | Break the edge check out by lag bucket and by month |
| `2a56aef` | 2026-10-13 17:09 | Add card-content atlas keyed on body content |
| `648eb0d` | 2026-10-13 16:52 | Add read-only edge truth check |
| `beac64b` | 2026-10-13 16:46 | Stop SEQUENCE FIRE from claiming an unknown result |
| `c499524` | 2026-10-13 16:40 | Add reconciled total census |
| `10beaad` | 2026-08-25 04:17 | Stop state sweep from wiping prediction engines |
| `9808959` | 2026-08-24 21:05 | Record free-fire floors and miss visibility |
| `9a5448b` | 2026-08-24 21:05 | Free-fire SEQUENCE family on historical floors |
| `69656b4` | 2026-08-24 20:35 | Treat forensic countdown card as a FIRE |
| `3f61c76` | 2026-08-24 19:45 | Post museum SEQUENCE card under forensic card |

The most recent work was forensic inventory and validation, not restoration of a
working runtime.

## Main application entry points

### Intended live entry points

1. `replit_elite_stack_patch/bot/run_bacbo_live.py`
   - Preloads state/session/Telegram/hub patches.
   - Then executes `bacbo_royal_complete.py`.
   - It exits immediately if that engine file is absent.

2. `replit_elite_stack_patch/bot/runtime_supervisor.py`
   - Intended Replit supervisor.
   - Monitors the main bot plus fallback signal/result senders.
   - Assumes `/home/runner/workspace`, environment files, a Telegram session,
     the live engine, and live database.

3. `bacbo_royal_complete.py`
   - Described throughout the project as the primary engine.
   - **Missing from this checkout.**

4. `bot/signal_handler.py`
   - Described as the core signal-generation/firing handler.
   - **Missing from this checkout.**

5. Historical full-app modules named in `ARCHIVE_MANIFEST.md`:
   `bot/main.py`, `bot/database.py`, `bot/config.py`, `bot/utils.py`,
   `bot/floor_tracker.py`, and many `_gates_*.py`.
   - **Missing from this checkout.**

### Dashboard/API entry surfaces

- `replit_elite_stack_patch/artifacts/api-server/src/routes/bot.ts`
- `replit_elite_stack_patch/artifacts/dashboard/src/pages/DashboardPage.tsx`
- `replit_elite_stack_patch/artifacts/dashboard/src/components/tabs/EngineTab.tsx`

These are patch artifacts, not a complete independently runnable web application.

## Exact responsibility map

### Signal generation and firing

Core files expected but absent:

- `bacbo_royal_complete.py`
- `bot/signal_handler.py`
- historical `_gates_*.py`
- `bot/database.py`

Present patch/control files:

- `replit_elite_stack_patch/bot/run_bacbo_live.py`
- `replit_elite_stack_patch/bot/hub_orchestrator.py`
- `replit_elite_stack_patch/bot/hub_engine_route.py`
- `replit_elite_stack_patch/bot/hub_dispatch.py`
- `replit_elite_stack_patch/bot/round_sync_densifier.py`
- `replit_elite_stack_patch/bot/window_packer.py`
- `replit_elite_stack_patch/bot/edge_live_policy.py`
- `replit_elite_stack_patch/bot/edge_whitelist_engine.py`
- `replit_elite_stack_patch/bot/unlock_signal_flow.py`
- `replit_elite_stack_patch/bot/hotfix_signal_handler.py`
- `replit_elite_stack_patch/bot/hotfix_signal_flow_dampers.py`
- `replit_elite_stack_patch/bot/sequence_family_wake.py`
- `replit_elite_stack_patch/bot/g2_coalition.py`
- `replit_elite_stack_patch/bot/state.py`

### Telegram sending and room routing

- `replit_elite_stack_patch/bot/telegram_outbox.py`
- `replit_elite_stack_patch/bot/lux_outbox_inline.py`
- `replit_elite_stack_patch/bot/fallback_signal_sender.py`
- `replit_elite_stack_patch/bot/fallback_result_sender.py`
- `replit_elite_stack_patch/bot/dual_lane_router.py`
- `replit_elite_stack_patch/bot/hub_dispatch.py`
- `replit_elite_stack_patch/bot/lux_session_guard.py`
- `replit_elite_stack_patch/bot/lux_dialog_resolve.py`
- `replit_elite_stack_patch/bot/config/signal_bundle_queue.py`
- `bot/config/chat_router.py`
- `bot/config/chat_shelves.py`
- `bot/config/profit_chat_bundle.py`

`telegram_outbox.py` explicitly warns that a second MTProto client on the same
session can trigger an authentication-key conflict and kill the live bot. The
intended mode is inline reuse of the engine's existing Telegram client.

### Result cards

- `replit_elite_stack_patch/bot/telegram_outbox.py`
- `replit_elite_stack_patch/bot/fallback_result_sender.py`
- `replit_elite_stack_patch/bot/fire_origin.py`
- `replit_elite_stack_patch/bot/sequence_family_wake.py`
- `replit_elite_stack_patch/bot/config/fire_result_law.py`
- `bot/config/fire_result_law.py`
- `bot/config/result_essence_engine.py`
- `replit_elite_stack_patch/bot/build_result_essence_atlas.py`

### Templates, skins, families, and card taxonomy

- `bot/config/skin_families.py`
- `bot/config/skin_census.py`
- `bot/config/skin_gate.py`
- `bot/config/registry.py`
- `bot/config/keep_allowlist.py`
- `bot/config/bundle_organizer.py`
- `replit_elite_stack_patch/bot/card_content_atlas.py`
- `replit_elite_stack_patch/bot/build_museum_everything.py`
- `replit_elite_stack_patch/bot/build_museum_chrono_existence.py`
- `replit_elite_stack_patch/TELEGRAM_CARD_ERAS.md`
- `replit_elite_stack_patch/CARD_TEMPLATE_TAXONOMY.md`
- `replit_elite_stack_patch/LITERALLY_EVERYTHING_SKINS.md`
- `replit_elite_stack_patch/bot/data/museum_full_catalog.json`
- `replit_elite_stack_patch/bot/data/signal_ledger.json`

### Consensus, timing, and validation

- `replit_elite_stack_patch/bot/early_result_audit.py`
- `replit_elite_stack_patch/bot/result_lag_miner.py`
- `replit_elite_stack_patch/bot/g0_offset_oracle.py`
- `replit_elite_stack_patch/bot/observer_confirm.py`
- `replit_elite_stack_patch/bot/truth_verifier.py`
- `replit_elite_stack_patch/bot/edge_truth_check.py`
- `replit_elite_stack_patch/bot/timing_presence_catalog.py`
- `replit_elite_stack_patch/bot/chronology_integrity_audit.py`
- `replit_elite_stack_patch/bot/data/timing_presence_catalog.json`
- `replit_elite_stack_patch/bot/data/museum_chrono_all_pairs.json`

### Deployment and recovery

Primary current scripts:

- `replit_elite_stack_patch/REPLIT_UP_NOW.sh`
- `replit_elite_stack_patch/REPLIT_ONE_CMD_FIX.sh`
- `replit_elite_stack_patch/REPLIT_ENGINE_WAKE.sh`
- `replit_elite_stack_patch/REPLIT_TELEGRAM_UP.sh`
- `replit_elite_stack_patch/REPLIT_FIX_LIVE_NOW.sh`
- `replit_elite_stack_patch/REPLIT_RECOVER_ALL.sh`
- `replit_elite_stack_patch/REPLIT_EXPORT_FULL_APP.sh`
- `replit_elite_stack_patch/REPLIT_EXPORT_ALL_DB.sh`
- `replit_elite_stack_patch/REPLIT_EXPORT_DB_FAST.sh`
- `replit_elite_stack_patch/download_ydray_full_app.sh`

There are dozens of older `REPLIT_FIX_*`, `REPLIT_FIRE_*`, and installer scripts.
That density is itself a maintenance risk: there is no single immutable,
versioned deployment path represented in this checkout.

## What appears broken or unfinished

1. **This checkout cannot run the bot.**
   The main engine and signal handler are absent, as are most original runtime
   modules and the live database.

2. **The Replit engine appears stale.**
   The operator-supplied read-only output reported 55,096 consensus rows and a
   newest `fired_at` of `2026-08-19 01:08:19`, with zero rows in the preceding
   24 hours. This was observed on Replit, not independently reproduced here.

3. **The latest suspected runtime defect was state destruction.**
   Commit `10beaad` changed `lux_state_heal.py` to stop coercing live engine
   objects into dictionaries. Whether that exact revision is active on Replit
   is not established by this local checkout.

4. **Telegram delivery has competing mechanisms.**
   Native sends, inline outbox, and fallback senders coexist. Project comments
   document prior authentication-key conflicts when more than one Telegram
   client used the same session.

5. **Database selection has historically been unsafe.**
   Code contains special handling to avoid selecting empty sibling databases.
   The operator-supplied Replit inventory showed one live multi-gigabyte DB,
   one legacy multi-gigabyte DB, one tiny root DB, and one zero-byte DB.

6. **Truth verification is unfinished.**
   `bot/data/truth_verification_report.json` records:
   - direct casino rows: 0
   - signal-to-casino matches: 0
   - verdict: `BOT_DB_INFERRED_ONLY`

   Therefore no accuracy, profitability, or “99%/100%” claim is independently
   established.

7. **Card/system classification is unfinished.**
   `signal_ledger.json` lists 71 canonical money families for review and many
   pending decisions. The card-content atlas catalogues 827 card types, but only
   four retain an original paired result in that distilled catalog.

8. **Recent card semantics changed but are not known to be deployed.**
   Commit `beac64b` changed the SEQUENCE FIRE card so unresolved fields remain
   pending and result cards are no longer suppressed. The live Replit revision
   is not established.

## Current conclusion

The repository is a valuable patch, taxonomy, and forensic-report layer, but it
is not the source-complete application. Restoration cannot be safely designed
from this checkout alone. The missing source-of-truth inputs are the live Replit
source tree and its databases, captured read-only and with metadata preserved.
