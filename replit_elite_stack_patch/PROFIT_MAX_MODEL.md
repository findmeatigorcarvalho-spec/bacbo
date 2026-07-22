# Profit-Max Model (locked)

Goal: **most WR · most G0 · most usable profit** from every proven floor + both card lanes, without bankroll suicide or spam that kills the edge.

Source of truth: `PROFITABLE_CARD_TYPES.md` (Vany chat forensics → Jul 18).

---

## The answer to “use everything”

**Yes — but as two lanes, not one mixed pipe.**

| Lane | Chat | What fires | Result glue | Why |
|--|--|--|--|--|
| **MONEY** | `@Mr_iv4` (peer `6774605259`) | Every good **floor/camada** can propose (Solo/Golden/Platinum/Sequence style, but per **floor**) → merge picks best when several agree | **Result card immediately under that signal** (Mr_iv4 style — including countdown-*looking* green/result templates you already use) | NORMAL_RESULT family ≈ **75% WR**, top profit (~9.3k). Peak-day pace returns when floors propose, not only LIVE. |
| **COUNTDOWN** | **@UNIQUE_g1** (Gunique) | Every profitable **countdown signal-fire** template (`CD_FIRE_TIMER_BRT_EDT_APOSTAR` primary; light RUSH/QUANTUM) | **Countdown result under that same CD fire** (`CD_RES_GREEN_G_BRT`, `CD_RES_RODADAS_TEMPO`, `CD_RES_BELL_GANHOU`) | CD_RESULT ≈ **91% WR**; CD_FIRE is the volume engine (May 19) that becomes G0 when glued (May 10 ≈ 500 G0). |

One Telethon outbox process, **two target peers**, routed by card family. Never two session clients.

---

## Your idea — keep / sharpen

**Keep**
- Regular/floor money cards on Mr_iv4 with result glued under (exactly the UX you like).
- Countdown **signal-fire** templates on Gunique (so Mr_iv4 stays a money chat, not a timer flood).
- When one floor wants it → fire that floor. When many → fire the **most proven** card among them (rank by peak WR / G0 / sniper>watch>volume).

**Sharpen (this is the profit difference)**
1. **Gunique must also get CD results under its CD fires.**  
   If Gunique only gets CD *fires* and all results stay on Mr_iv4, you keep May-19 volume and lose the May-10 glue path. Orphan fires ≈ noise.
2. **91% is the countdown lane, not a sticker.**  
   Putting a countdown-result *skin* under a money fire does **not** magically import 91% WR. It is still correct UX on Mr_iv4; the WR comes from **which tower proposed + gates + glue**, not the emoji template alone.
3. **Floors propose (v2), merge only ranks.**  
   v1 (LIVE proposes, floors only stamp) is why peak-day “2/min” feels dead — silent towers never open the door.
4. **Opposite-color same window → lock one** (per lane). Same-color multi-ALLOW → one best card (or short ranked burst if volume mode on). Never red+blue doubles into the same bankroll window.

---

## Floor model = old room model

Rooms used to originate Solo / Golden / Platinum.  
Now **each good floor/camada** (March→Jun peak, WR≥60%, JUN12* blocked) is a proposer with **frozen peak gates**.

```
each floor tower  →  proposes FIRE (own gates/kinds/hours/rooms)
        ↓
lane merge        →  rank / opposite-color lock / ≤1 money decision per window
        ↓
outbox            →  Mr_iv4 (money) or Gunique (countdown)
        ↓
result glue       →  same signal id, card directly under fire
```

Blocked forever: `JUN12A`, `JUN12B`, thin &lt;60% junk, AUTO relay spam, `CD_FIRE_DO_NOT_BET_PASSED`.

---

## What we refuse (looks busy, loses money)

- 32 bots spamming both chats every round  
- CD fire flood inside Mr_iv4 (buries money reads)  
- CD fires on Gunique with **no** CD result glue  
- Claiming “every floor fires every round” without merge (opposite-color death)  
- Jun 28 oracle G0-mention flood as a target  

---

## Floor peak fidelity + strength rank (truth from result cards)

Script: `bot/peak_fidelity_ranker.py` → `bot/data/peak_fidelity_ranker_report.json`

- Cross-compare every live floor vs its **peak-day baseline** (n / WR / gate lock)
- Rank by strength: peak WR · volume · G0 · live profit · **assertiveness**
- Result-card truth: `loss on red` ⇒ actual **blue** ⇒ blue opinions right (and vice versa)
- Multi-floor same color = more trust (coalition confirmation)
- `VOLUME_GAP_VS_PEAK` / `NO_LIVE_ATTRIBUTION` = floor not presenting peak-day opinions in v1 stream → needs v2 proposers

```bash
python3 bot/peak_fidelity_ranker.py --db bot/bacbo.db
```

## Build order (profit path)

1. ~~Single stack + outbox online~~  
2. ~~Peak fidelity + floor strength ranker~~ (`peak_fidelity_ranker.py`)  
3. **Shadow miss report** on full historical DB — per floor would-ALLOW ∩ win  
4. **v2 parallel floor proposers** into money-lane merge (restores peak-day cadence)  
5. **Dual-peer outbox** — `TELEGRAM_TARGET_PEER` = Mr_iv4, `TELEGRAM_COUNTDOWN_PEER` = Gunique  
6. **Countdown lane** — own peak towers + CD_FIRE→CD_RESULT glue on Gunique  
7. Money lane keeps result-under-signal on Mr_iv4 (current UX)  
8. Native templates only after glue + proposers are solid  

---

## Success metrics (not vibes)

| Metric | Target signal |
|--|--|
| Mr_iv4 | Floor tags rotate across peaks; result under every money fire; pace approaches peak days without opposite-color doubles |
| Gunique | CD_FIRE volume with matching CD_RESULT under; orphan CD fires → 0 |
| Shadow audit | Blocked-win count per floor trending down after v2 |
| Kill list | AUTO relay / DO_NOT_BET_PASSED / JUN12* stay dead |
