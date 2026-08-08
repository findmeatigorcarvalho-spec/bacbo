# HUB orchestration — free propose → AI pick → card+RESULT

## The model (what you described)

Every **signal gate / config / setup / camada / floor / system** decides on its own, **any time, 24/7**.  
They all fire **into the HUB**, not straight to the user as raw spam.

Example:
- Round N: **20** proposers say RED is next → hub scores strength → picks the **best** primary card+RESULT for APEX chat, places same-color extras on spill chats if useful.
- Round N+1: **10** say BLUE → same process again.

Opposite colors in the **same** window cannot both become bet cards (opp-color lock).  
Same color from many machines is **expected** — hub chooses which card fits that round + which chat + how to present it.

**Floors are not the whole inventory.** Peak floors are one class of proposer. Skins, gates, factory camadas, and other systems also belong in the hub as they get wired.

There are **no hour windows** on the propose path. Propose is always on.  
The hub **orchestrates** output for smooth, productive, profitable use — not “loosen blocks,” **remove mute on propose**.

## Architecture

```
rooms / sensors
    → EVERY proposer (floor / gate / camada / system) FREE_PROPOSE 24/7
    → HUB queue (v2 proposals)
    → hub_orchestrator: score → win color → primary card + spill
    → bundle_organizer: which UNIQUE_gN chat
    → Telegram FIRE skin
    → RESULT skin glued under that FIRE (FIRE↔RESULT law)
```

| Mode | Behavior |
|---|---|
| **FREE_PROPOSE=1** | Hour / WR / volume / loss-risk mutes do **not** kill propose |
| **VOLUME_MODE=EXPLOSION** | Same-color multi kept; opposite-color same window locked |
| **HUB_ORCHESTRATOR=1** | Picks primary + spill peers from free proposals |
| **SAFE_MERGE** (old) | ≤1 card — compresses peak days into one pipe — **not** the goal |

## Impact learner / watchdog (always most resourceful)

`hub_impact_learner.py` watches **every**:
- singular gate / floor / camada fire → RESULT
- coalition of signal fires (many same-color proposers) → RESULT
- opposite-color same-window LOCKS (and whether the lock was right)

It attributes win/loss/tie to `floor:*`, `room:@*`, `origin:*`, `mode:SINGULAR|COALITION`, `kind:*`, `lock:OPP_COLOR`, then boosts hub scores so the next pick is more resourceful — volume, WR, primary, spill, opp-lock, choices.

Ledger: `bot/data/hub_impact_ledger.jsonl`  
Scores: `bot/data/hub_impact_scores.json` (`resourcefulness_snapshot()`)

## Chat watchdog (what lands / what never leaves)

`lux_chat_watchdog.py` watches **every** Telegram outbound path:
`send_message`, `send_file(caption)`, and `TelegramClient.__call__` (SendMessageRequest).

- G2 ESTUDO / study spam → HARD DROP (unicode-normalized)
- near-duplicate floods → DROP
- ledger: `bot/data/chat_watchdog_ledger.jsonl` + `chat_watchdog_stats.json`

## Opp-color LOCK causality

Hub decisions store `color_map` + `opp_locked_colors`.  
After RESULT, learner records whether the lock was right/wrong — so it keeps emanating the best from all proposers (which said what, what locked, what happened).

## Room resolve (FloodWait)

`lux_dialog_resolve.py` — `@rooms` via dialog cache / InputPeer only.  
**Never** hammer `ResolveUsername` while flooded (that starvation kills all proposers).

## Honesty

Hub maximizes capture of real windows with the best card the machines offer.  
Dollar ROI / “win every round” is ambition, not a physics guarantee — Bac Bo has variance.  
Volume restoration (many free proposers + hub pick + live rooms) is step one.

## Code

- `bot/hub_orchestrator.py` — pick primary + spill (+ learner enrich)
- `bot/hub_impact_learner.py` — fire/result watchdog → scores
- `bot/lux_dialog_resolve.py` — no ResolveUsername FloodWait
- `bot/v2_floor_proposers.py` — enqueue / referee
- `bot/lux_tower_merge.py` — wires free proposers + hub pick
- `bot/edge_live_policy.py` — `FREE_PROPOSE` skips mute BLOCKs
- `bot/hub_max_boot.py` / `runtime_supervisor.py` — force EXPLOSION + free propose env
