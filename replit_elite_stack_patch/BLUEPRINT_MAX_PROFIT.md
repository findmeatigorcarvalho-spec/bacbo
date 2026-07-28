# BLUEPRINT — Max signals · all floors · human-friendly · smart merge

## Your idea (locked)

A **35s countdown** fire does **not** mean “freeze the whole system for 35s.”

It means: that **lane/chat** has an open card for ~35s.  
In the **gaps** (e.g. +3s … +30s), **other families** can still fire — other chats, or even the same hub if bankroll-safe — so you **fit** volume into time instead of wasting it.

That is resourceful: **time-multiplex + multi-chat + conflict-only merge.**

```
T=0     COUNTDOWN chat: ⏱ 35s fire (red)
T=3s    SOLO chat:      SOLO ELITE blue  → OK (different chat / non-conflict rule)
T=12s   SEQUENCE chat:  sequence red     → OK if same color or other room
T=20s   HUB:            skip opposite-color money double
T=35s   COUNTDOWN:      result glued under the 35s fire
```

---

## One-sentence system

**Every floor ever built proposes freely at its peak gates → pack non-conflicting fires into time + chat slots → merge only true bankroll collisions → result always glued under its parent with no delay.**

---

## Layer cake

```
┌─────────────────────────────────────────────────────────┐
│ 1. SENSE     rooms / casino ticks                       │
├─────────────────────────────────────────────────────────┤
│ 2. PROPOSE   every peak floor/config (v2 EXPLOSION)     │
│              SOLO · GOLDEN · SEQUENCE · PLATINUM · CD   │
├─────────────────────────────────────────────────────────┤
│ 3. PACK      WindowPacker — fit families into time gaps │
├─────────────────────────────────────────────────────────┤
│ 4. ROUTE     family → Telegram group (5–6 chats)        │
├─────────────────────────────────────────────────────────┤
│ 5. GLUE      result → same chat as parent fire (0 delay)│
├─────────────────────────────────────────────────────────┤
│ 6. LEARN     WR / G0 / $/room / missed-by-merge ledger  │
└─────────────────────────────────────────────────────────┘
```

---

## Telegram layout (human-friendly max capture)

| Chat | Families | Open-window rule |
|------|----------|------------------|
| **HUB** | 1 best “bet now” when needed | Strict: ≤1 opposite-color money decision / window |
| **COUNTDOWN** | Clock-A / CD timer fires | Own 35s (etc.) window; **does not mute other chats** |
| **SOLO** | SOLO_ELITE peak floors | Free-fire; pack into gaps |
| **GOLDEN** | Coalition ENTER NOW | Free-fire; pack into gaps |
| **SEQUENCE** | Sequence / high cadence | Free-fire; absorbs 1k–3k/day |
| **OPS** (opt) | EXPIROU / forensic long | Never blocks money rooms |

Humans: follow **HUB** to play safe; open **1–2 specialists** for max volume.  
Never 32 chats. Never squash all into 2 if that kills packing.

---

## WindowPacker — the “fit everything” brain

### State per chat
- `open_fires[]`: `{id, family, color, t0, window_secs, chat}`
- Countdown example: `window_secs=35`

### Admit a new candidate at time `t`
1. **Route** to its family chat (not always HUB).  
2. **Same chat + opposite color + overlapping window?** → merge lock (keep higher score).  
3. **Same chat + same color + overlapping?** → allow short burst **or** coalesce (config).  
4. **Different chat?** → **ALLOW** (your 3s–30s gap idea). Countdown open ≠ global silence.  
5. **HUB only:** if any money color already open and candidate is opposite → block/hold for hub; specialists may still fire.  
6. **Glue:** result for fire X only in X’s chat, under X, ASAP.

### Conflict matrix (default)

| A already open | B wants in | Same chat? | Action |
|----------------|------------|------------|--------|
| CD red 35s | SOLO blue | No | **FIRE** (pack gap) |
| CD red 35s | CD blue | Yes | **LOCK** one |
| HUB blue | HUB red | Yes | **LOCK** one |
| SOLO red | GOLDEN red | No | **FIRE** both (two chats) |
| SOLO red | SEQUENCE red | No | **FIRE** both |

Profit comes from **packing**, not from **deleting** B every time A is open.

---

## Merge philosophy (most profitable)

| Old (lossy) | Blueprint (max) |
|-------------|-----------------|
| One global ≤1 card / window | ≤1 only where **bankroll** collides |
| Countdown freezes everything | Countdown occupies **its chat’s** window |
| 36 floors → 1 mouth | 36 floors → 5 mouths + packer |
| Mirror copies | Exclusive route, no mirrors |

---

## Volume / WR / $ (what “most” means)

- **Volume:** sum of free floor streams packed into 5 chats (realistic same-day **~8k–20k** fires; binge days higher in COUNTDOWN+SEQUENCE).  
- **WR:** keep peak floors’ own WR; don’t dilute by forcing bad merges.  
- **$:** HUB protects bankroll; specialists print volume; raise stake only after glue+packer stable.  

---

## Build order

1. `VOLUME_MODE=EXPLOSION` + v2 proposers (all floors)  
2. 5 Telegram peers + `route_by_family`  
3. **WindowPacker** (this blueprint)  
4. Result glue by `parent_fire_id` → same peer  
5. Per-chat dashboard: fires/day, WR, G0, gaps packed, merges locked  

---

## Success test

On a live countdown card (~35s):  
you still see **other family fires in other chats** in the +3s…+30s band, each with their own result under them — **without** opposite-color doubles in HUB.

If the system goes quiet for 35s every countdown, the packer is wrong.
