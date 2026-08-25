# Round sync (wire) — servant of the Human Return Path

**This filename is a handle, not the creation.**  
See `WHAT_WE_ARE_CREATING.md` and `python3 bot/human_return_path.py`.

## What this wire does for a human

Every chat gets **~1 signal per BacBo round** (minimum **1 per 2 rounds**).  
Every fire lands when the human still has time to bet.  
Spare prep time (30s…400s+) is **invested**, not wasted as late spam.

## Clocks (do not mix)

| Clock | Meaning | This module |
|---|---|---|
| **A** | Ns to place bet (JANELA) | Used to size prep hold → release at TTB |
| **B** | Hit ETA (rare) | Optional prep hint |
| **C** | Fire→resolve duration on RESULT | Not a fire trigger |
| **Interval** | ~10s between rounds | Grid for FIRE + RESULT align |

## Phases

```
INTERVAL_OPEN → BET_WINDOW → LOCKED → (next) INTERVAL_OPEN
     │              │            │
     │              │            └─ too late → hold for NEXT interval
     │              └─ TTB 12s…3s → FIRE NOW
     └─ post RESULT (prior color) + arm FIRE for this round
```

## What we invented / wired

| Piece | Role |
|---|---|
| `round_sync_densifier.py` | Phase clock + hold queue + density tracker |
| `lux_send_config_bind` | Engine HOLD_PREP / HOLD_RESULT (no late burns) |
| `telegram_outbox` | 1s release loop when queue waiting; outbox fire/result gated |
| `window_packer` | Real countdown max → TTB 12s under ROUND_SYNC |
| Gap fill | Extra signal for a full chat → UNIQUE_gN that is behind density |

## Env

```bash
ROUND_SYNC=1
ROUND_INTERVAL_SECS=10
TTB_IDEAL_SECS=10
TTB_RELEASE_MAX_SECS=12
TTB_RELEASE_MIN_SECS=3
PREP_INVEST_MAX_SECS=400
ROUND_SYNC_RESULT_ALIGN=1
```

## User experience (simple)

1. At interval start you may see **RESULT** (last color) then **ENTER** for the new round.  
2. You have ~10s — bet **minimum** on the color.  
3. Long JANELA (87s, 400s) never dumps early — system holds and releases when TTB is real.  
4. If a chat is quiet for 2 rounds, the densifier fills it from overflow.

## Status

```bash
python3 bot/round_sync_densifier.py
python3 bot/round_sync_densifier.py --demo
```

Honesty: grid is inferred + nudged from resolves until direct `casino_round_results` ticks exist (`truth_verifier` schema). Density target is operational — WR still decides wins.
