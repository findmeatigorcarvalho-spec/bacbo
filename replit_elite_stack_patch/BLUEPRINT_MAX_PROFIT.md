# BLUEPRINT — Hub dispatcher · ≤30s real countdown · elastic chats · zero loss

## Understanding (locked)

1. **Any window length is valid** (15s, 35s, 90s, 200s…) — 35 was only an example.  
2. If a card’s timing window is **> 30s**, it is **not** a “real countdown fire” yet.  
   - **Hold** it in the hub queue.  
   - **Release** when remaining time is **≤ 30s** (best actionable window).  
   - Card still **prints the original seconds** (e.g. “original 87s · live 28s”).  
3. Inside a chat, pack whatever **fits best under that ≤30s** (and gaps).  
4. **Not floors yet** — intake is **every signal type / system config / setup ever created**.  
5. **One HUB brain** sees **every** signal. Hub **assigns** each to whichever chat is ready *right now* for timing + profit + WR + volume — **create as many chats as needed**.  
6. Goal: **lose nothing**; route everything to the best slot.

```
ALL CONFIGS / SETUPS (every signal type ever)
              │
              ▼
     ┌────────────────────┐
     │   HUB (brain)      │  ← every signal enters here first
     │  queue · hold>30s  │
     │  score · dispatch  │
     └─────────┬──────────┘
               │ picks best chat at that moment
     ┌─────────┼─────────┬─────────┬──────────┐
     ▼         ▼         ▼         ▼          ▼
  Chat A    Chat B    Chat C    Chat D   … Chat N
  (elastic — spawn when capacity / family needs it)
     │
     └─ result glued under parent in THAT chat
```

---

## Real countdown rule (≤30s)

| Detected window | Hub action | What user sees on card |
|-----------------|------------|-------------------------|
| **≤ 30s** | Eligible to dispatch now as **real countdown fire** | Original secs (= live secs) |
| **> 30s** | **HOLD** until remaining ≤ 30s (or better slot) | **Original** secs kept + optional live remaining |
| No timing | Dispatch by family/profit/WR/volume fit | Normal ENTER NOW / solo / etc. |

When released from hold at e.g. remaining 27s after original 87s:

```
⏱ Original window: 87s
⚡ Live countdown: 27s   ← real fire moment
```

---

## Hub dispatcher (zero loss)

Every signal from every config hits the hub:

1. **Classify** — family / kind / has_window / original_secs / color / score / WR priors  
2. **If original_secs > 30** → `HOLD_UNTIL_REAL` (queue), do not burn a chat yet  
3. **When ready** (≤30s or untimed) → **score all chats**:
   - free slot vs opposite-color conflict  
   - family affinity (prefer matching specialist if free)  
   - current open-window fit (what packs under ≤30s best)  
   - WR / volume / profit weight for that config  
4. **Dispatch** to best chat; if none fit → **spawn new chat** (elastic) or short queue (never drop)  
5. **Glue** result to same chat as parent  

Hub is **intake + brain**, not necessarily the only human money view.  
Optional **PLAY** chat = hub’s single “bet this” recommendation for bankroll.

---

## Elastic chats

Start with specialists; **grow as needed**:

| Chat role | Examples |
|-----------|----------|
| PLAY / money recommend | Hub’s best single bet |
| Real countdown (≤30s releases) | Held>30s then released |
| Solo configs | SOLO_ELITE setups |
| Golden / coalition | Multi-room ENTER NOW |
| Sequence / volume | High cadence |
| Extra N | Spawn when packer says all chats saturated |

**As many as needed** so nothing is deleted for lack of a slot.

---

## Packing under ≤30s (your gap idea, generalized)

While Chat C has a **real** countdown open (e.g. 28s left):

- Other configs can still go to Chat A/B/D… (**zero global mute**)  
- Same chat: only lock on **opposite color** (or score replace)  
- Hub keeps feeding whatever **fits** timing + profit + WR + volume  

---

## Order of build (your “not floors yet”)

1. Catalog every **signal type / config / setup** ever (chrono museum path)  
2. Hub intake + HOLD>30s + release≤30s + original secs on card  
3. Elastic chat dispatch (zero loss)  
4. Window packer conflicts  
5. **Then** floors as parallel proposers into the same hub  

---

## Success test

- 87s window arrives → **not** posted as frantic enter at 87s → held → posts near ≤30s with **original 87s** visible  
- During that hold/open, **other** configs still appear in other chats  
- No signal dropped because “only 2 chats” or “merge ate it”
