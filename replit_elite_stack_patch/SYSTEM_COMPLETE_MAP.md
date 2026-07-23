# Complete system map — every piece that must exist

## 1) Timing (see `TIMING_CLOCKS.md`)

| Clock | Where | Meaning | Lane effect |
|-------|--------|---------|-------------|
| **A** Entry window | FIRE | Ns to *place* bet (`JANELA 1s/11s/17s`) | → `@UNIQUE_g1` |
| **B** Hit ETA | FIRE (optional) | when color is *expected* to land | timed family if present |
| **C** Intervalo | RESULT | fire→resolve duration | **never** chooses lane |

ENTER NOW / coalition with **no A/B on fire** → Mr_iv4 money pipe.

---

## 2) Fire origins (two different “truths”)

### 2a COALITION decision (multi-room)

**Only fire as coalition card when ≥2 rooms agree same color** (or scored consensus).

Card job: “several independent rooms confirmed → enter this color now.”  
Peer: Mr_iv4 (unless Clock A also present → then timed lane).

### 2b SOLO FACT WARNING (strong floor alone)

When **one** elite / peak-locked floor fires alone (no multi-room stack):

- Do **not** dress it as “3 rooms confirmed.”
- Fire as **independent FACT WARNING**: floor name, peak tag, historical WR, color, G0-only.
- Own result glue under it.
- This is a different epistemic claim: “this floor’s pattern hit,” not “coalition.”

Rule of thumb:

```
rooms >= 2  →  COALITION_ENTER
rooms == 1 and floor in elite/peak  →  SOLO_FACT_WARNING
rooms == 1 and weak floor  →  hold / shadow (don’t spam money)
```

---

## 3) Result cards = truth board (not just win/loss sticker)

Every result must answer **all** of:

1. What we bet (predicted color)  
2. What **actually came out** (exact table color)  
3. Win/loss/tie at which gale (G0/G1/G2)  
4. Clock C Intervalo (reporting only)  
5. **Inverse truth line** when loss:  
   `BET BLUE → OUT RED · BLUE LOST G0 · TRUTH THIS ROUND = RED`  
   So a human (or next-layer brain) can be sure: that G0 was red — not “maybe.”

This is already computable: `loss on blue ⇒ actual = red` (and reverse). Make it **loud on the card**.

Optional next layer (not casino oracle): if a *new* signal is for the **same open G0 window** and predicted the losing color, suppress / flip advisory — only when timestamps prove same round. Default: never invent flips without round identity.

---

## 4) Dual Telegram pipes (separation, not mirror)

| Pipe | Peer | Fires | Results |
|------|------|-------|---------|
| Money | Mr_iv4 | Coalition ENTER NOW; solo fact without Clock A | their results |
| Timed | `@UNIQUE_g1` | Clock A / CD_FIRE skins | their results |

No money→Gunique copy.

---

## 5) Floors / towers / merge

- Each peak floor = frozen peak-day gates (propose machine).  
- Floors ≠ Telegram rooms.  
- Parallel propose → merge ≤1 **money** decision per conflict window.  
- Timed lane has its own merge / peaks.  
- Opposite colors same window → lock one per lane.

---

## 6) Sense → decide → voice → truth loop

```
rooms posts → parse templates (FIRE/RESULT, clocks A/B/C)
     → floor proposers (peak locks)
     → origin tag (COALITION | SOLO_FACT)
     → lane (MONEY | TIMED)
     → merge referee
     → outbox peer
     → result glue + actual color truth
     → ledger (WR / G0 / volume / misses)
     → feed back into floor weights
```

---

## 7) Autonomy metrics (factual only)

- Volume fires/day per lane  
- WR and G0 rate per origin (coalition vs solo)  
- Glue lag (Clock C distribution)  
- Zero-miss: proposed but never sent / sent but never resolved  
- Peak fidelity: live cadence vs peak-day cadence  

Ambition targets must survive stake × units × rounds/day math.

---

## 8) Ideas from “nowhere” that still fit the machine

1. **Inverse-color confirmation banner** on every loss (truth this round).  
2. **Origin badge** on every fire: `COALITION×3` vs `SOLO·JUN19`.  
3. **Same-round suppressor**: don’t stack second money fire if prior G0 still open.  
4. **Solo elite burst mode**: high-WR solo floors can volume without waiting for room #2.  
5. **Coalition quality score**: rooms × historical joint WR, not raw count.  
6. **Clock A only on Gunique**; if a coalition card also has Clock A, prefer Gunique timed skin OR strip A for money — never dual-post.  
7. **Result-first learning**: weight floors that predicted the *actual* color on losses of others.  
8. **Expire ops** stay results; never start a new FIRE from EXPIROU text.  
9. **Template DNA registry**: every fire/result skin since day one hashed → lane + origin + clocks.  
10. **Human bankroll script** on card: G0 $10 / G1 $20 / stop — same truth board, less chase.
