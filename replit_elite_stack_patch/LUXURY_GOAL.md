# Luxury Goal — Big Picture (aligned track)

## One-sentence goal
Every **historically good floor/setup since March** (WR≥60%, real peak days) can **propose** fires using its **own frozen peak gates**, in parallel; a **global merge** sends **at most one money card per conflict window** to Telegram, with the **result card glued under that signal** — and **countdown** is a **separate lane** with its own peaks/setups.

## Does this avoid losing profitable signals?
**Best available design — yes, with one honest tradeoff:**

| Situation | What happens | Value kept? |
|---|---|---|
| One tower ALLOWs, others quiet | That tower’s card sends | Yes |
| Several towers ALLOW **same color** | Merge picks best (sniper > watch > peak > LIVE); **one** card | Yes — signal kept, no spam |
| Two towers ALLOW **opposite colors** same window | Opposite-color **lock** → one wins | Yes for bankroll; you cannot bet both |
| Tower would have fired but LIVE engine never proposed | v1 may miss it | **v2** isolated peak handlers fix this |

v1 (shipping now): LIVE engine proposes + **all floors scored in EdgePolicy merge** + peak-lock loaders bound.  
v2: each peak handler can propose independently into the merge queue.

So: merge is how you **keep** multi-floor edge without destroying the account with red+blue doubles.

## What we are NOT doing
- Not 32 independent bots spamming chat every round.
- Not “only send after we know it won” (impossible pre-round; casino result comes after).
- Not renaming LIVE fires to JUN19 and calling that multi-floor.

## Three layers

```
ROOMS (Telegram sources)  →  feed votes into floors
FLOOR / CAMADA (brain)    →  frozen peak gates + rooms + hours + kinds
OUTBOX (chat)             →  one merged card + matching result
```

Floors ≠ rooms. `@rqdados` is a room. `JUN19` / `MAR19` / `ELITE_V2` are floors.

## Parallel towers (yes — wire the real good peaks)

Each good floor is a **tower**:
- Gate file locked to peak day (e.g. `_gates_JUN19_peak.py`)
- Own core rooms, kinds (SEQUENCE/GOLDEN/SOLO/…), hours, thresholds
- Own cooldown / dedup (a loss on MAR19 must not silence JUN19)

They evaluate **without knowing each other** until merge.

### Global merge (the only place they meet)
1. Same-round / same-window **opposite color → lock** (no red+blue spam)
2. Rank candidates (peak confidence / lane priority)
3. **One outbox** sends the winner’s signal card
4. Result card attaches to **that** fire only

So: parallel **proposals**, single **chat decision**.

## “Winning signal” — precise meaning
We fire when a tower’s gates say **FIRE** (predicted edge), on setups that **historically win** (peak WR / G0).  
We do **not** wait for the casino win to send the signal.  
Result cards then report win/loss/tie under that signal (early result card = volume weapon when the pipeline is accurate).

## Countdown vs normal (must stay separate)
From chat forensics:
- **Normal** signal+result = main money lane (NORMAL_RESULT ~75% WR family)
- **Countdown** fire = high volume / different timing edge
- **Countdown result** ≈ **91% WR** family — different accuracy profile

Therefore countdown deserves **its own peak towers + merge rules**, not the same thresholds as FLASH/SEQUENCE normal cards.

## Profit organism (locked)
See **`PROFIT_ORGANISM.md`** + **`PROFIT_MAX_MODEL.md`**.

Living max-EV system: every floor ≥ peak day · dual lane · zero-miss · vault patterns · $/day projection.

## Profit-max dual chat (locked)
See **`PROFIT_MAX_MODEL.md`** — full rationale.

| Chat | Sends | Glue |
|--|--|--|
| **Mr_iv4** | Money / floor proposers (Solo·Golden·Platinum·Sequence per floor) | Result card under signal (current Mr_iv4 UX) |
| **Gunique** | Countdown **signal-fire** templates | Countdown **result** under that same CD fire |

One outbox, two peers. Floors propose (v2); merge only ranks. CD result skin ≠ 91% magic — 91% is the countdown lane.

## Build order (right track)
1. ~~Telegram path + single outbox~~ (done)
2. ~~Stable one bacbo / one supervisor~~ (ONE_STACK)
3. **Shadow miss report** — blocked would-win per floor (proves the hole)
4. **v2 parallel floor proposers** → money-lane merge (peak-day cadence)
5. **Dual-peer outbox** — Mr_iv4 money + Gunique countdown
6. **Countdown lane** own peaks + CD_FIRE→CD_RESULT glue on Gunique
7. Native luxury cards (optional once glue + proposers solid)

## Blocked forever
`JUN12A` · `JUN12B` · thin &lt;60% junk
