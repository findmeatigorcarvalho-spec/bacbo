# BLUEPRINT — Hub dispatcher · ≤30s real countdown · elastic chats · zero loss

## THREE LOCKS (user — do not weaken)

### 1) Every config is a separate full machine
Each system / config / setup ever created:
- **decides separate**
- **analyzes separate**
- **fires separate**
- **no blocks / no gates** that shrink it vs its own best day

Its live stream must match **that config’s most-volume day** — whether that day was **1** signal or **100,000**.  
Not “merged average.” Not “allowed only if coalition.” Not silenced by another config’s loss.  
Hub **routes** after they fire; hub does **not** veto peak-day volume.

### 2) Original card templates — clean, don’t reinvent
Keep each template’s **original version/skin**.  
Only:
- strip **unnecessary** noise
- refresh **factual** fields (time, WR, score, color, result truth, original secs / live ≤30s)

Do not replace day-one DNA with a generic outbox card.

### 3) Chat priority — Gunique first, 24/7
Fill in order (never starve #1):

| Priority | Chat | Role |
|---------:|------|------|
| **1** | **@UNIQUE_g1 (Gunique)** | Most important — run **24 hours**, every second capacity; first fill |
| **2** | Main money / bot chat (Mr_iv4 / PLAY) | Second fill |
| **3+** | SOLO → GOLDEN → SEQUENCE → MIX → OPS → elastic | Rest of volume, in order |

Hub still sees all configs. **Dispatch order** = Gunique first until its ~2–3/min (or binge) band is healthy, then cascade down.  
Timed ≤30s release + packing still apply **inside** this priority.

---

## ALL signals since day 1 (not countdown-only)

Hub intakes **every signal from every system config / setup ever created** — SOLO, GOLDEN, SEQUENCE, PLATINUM, FLASH, timed, untimed, gale follow-ups, etc.  
Countdown ≤30s hold/release is **one rule inside** that pipe, not the whole design.

### Volume if everything fires

| Band | Signals/day | Global rate |
|------|------------:|------------:|
| Naive sum of personal best days | ~51,000 | ~36/min |
| Realistic same-day free-fire | ~8,000–20,000 | ~6–14/min |
| Aggressive packed day | ~25,000 | ~17/min |

### How many chats (human + AI sweet spot)

Target **~2–3 signals/min per chat** (readable, glueable, followable).

| Total volume | Chats @ 2/min | Chats @ 2.5/min | Chats @ 3/min |
|--------------|--------------:|----------------:|--------------:|
| 8k/day | ~3 | ~2–3 | ~2 |
| 12–18k/day | ~6–7 | ~5–6 | ~4–5 |
| 20–25k/day | ~7–9 | ~6–7 | ~5–6 |
| 51k naive ceiling | ~18 | ~14 | ~12 |

**Best default: 7 chats** (expand to ~10–12 only on binge days).

| # | Chat | What goes there | ~rate at 18k/day |
|---|------|-----------------|------------------|
| 1 | **PLAY** | Hub’s best single bet (bankroll) | ~1/min |
| 2 | **SOLO** | All SOLO_ELITE / solo configs | ~2.5–3/min |
| 3 | **GOLDEN** | GOLDEN + coalition ENTER NOW | ~2–2.5/min |
| 4 | **SEQUENCE** | SEQUENCE / streak configs | ~2.5–3/min |
| 5 | **TIMED** | Any timed card released at ≤30s live (original secs shown) | ~2–2.5/min |
| 6 | **MIX** | Flash / early skins / overflow | ~1/min |
| 7 | **OPS** | EXPIROU / long forensic / gale ops | ~0.5/min |

Hub brain still sees **all**; these chats are **distribution**, so nothing is lost — overflow spawns MIX-2 etc. when a chat exceeds ~3/min.

---

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
