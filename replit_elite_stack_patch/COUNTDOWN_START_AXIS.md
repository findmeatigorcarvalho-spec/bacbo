# Start axis — WITH_TIMING vs NO_TIMING (what you meant)

## 1) `🟢 1s 🟢` / `JANELA: 1s` — what it is

**Yes: that means you have ~1 second to place the bet** (entry urgency).  
It does **not** mean “the casino result arrives in 1 second.”

That family is **Clock A** (entry window). Useful, historically flashy, but it is **not** the whole countdown value story — and it is **not** the place you said you want to **start**.

---

## 2) Where you want to START (locked)

Catalog **every card ever fired** (fire **and** result; good/bad; n=1 counts; PT or EN):

| Axis | Meaning | Examples |
|------|---------|----------|
| **WITH_TIMING** | Body carries a duration / countdown / Intervalo / Ns span | `⏱ Intervalo: 31.3s`, `200s`, `400s+`, `30s`, `40s`, `⏱ 11s`, `RÁPIDO — 6s RESTANTES`, `rodada(s) · 132s`, CD timer skins |
| **NO_TIMING** | Fire/result template with **no** such duration marker | Plain ENTER NOW / color banner / short `✅ WIN — SOLO_ELITE` with no Intervalo |

This is broader than Clock A. Clock A cards are a **subset** that often also show Ns, but the valuable binge systems include **all** timed durations on fires **and** results.

Scanner: `bot/timing_presence_catalog.py` → `bot/data/timing_presence_catalog.json`

### Snapshot (Vany chat, full export)

| Metric | Count |
|--------|------:|
| Messages scanned | 535,697 |
| **WITH_TIMING** | 36,221 |
| **NO_TIMING** | 499,476 |
| Clock A entry markers | 20,350 |
| Template fingerprints WITH_TIMING | 4,225 |
| Template fingerprints NO_TIMING | 14,856 |
| FIRE + WITH_TIMING | 4,301 |
| RESULT + WITH_TIMING | 19,495 |
| FIRE + NO_TIMING | 43,200 |

Duration buckets seen (extracted Ns): includes **200–400s** (2,361) and **400s+** (2,746) — not only 1s/11s/17s.

### Peak timed-fire days (binge candidates)

Highest **FIRE + timing** days include **19–27 May 2026** (e.g. 19 May ≈ 2,419 timed-fireish msgs).  
**Fri 22 May → Sat 23 May** sits inside that countdown-dense week — matches the shape of your “Friday night → Saturday” countdown-only binge (500+ hits class). Catalog day totals use `DD.MM.YYYY` timestamps from Vany.

---

## 3) Why countdown cards matter

When a system **only** fires WITH_TIMING / countdown skins and does it **back-to-back**, history shows **volume weapons** (May countdown week, CD_FIRE family forensics, ~500+ G0/hit class sessions).  

That value is **not** the same as:
- Clock A alone (`1s to click`), or  
- Money ENTER NOW with no duration, or  
- A result that merely prints Intervalo after the fact (still WITH_TIMING on the **result** axis, but role=RESULT).

Start catalog first → then lane/volume wire the WITH_TIMING **fire** family hard (Gunique), keep NO_TIMING fires on money/solo/coalition pipes.

---

## 4) “G0” is not always the next round

Two different measurements:

### A) `secs_to_result` → implied table rounds (~30s/round)

From current export DB (smaller live sample): most labeled kinds still **mode = round 1**, but tails go to **80s / 240s / 279s** ⇒ implied **3–9 rounds** on outliers (SOLO_ELITE/GOLDEN especially).  
Those are systems that can be “G0 profitable” while **mechanically late**.

### B) Color offset after a G0 WIN (stream oracle)

`g0_offset_oracle.py`: after a G0 win, does the **same color** show again at +1…+6 resolved outcomes?

On available DB: **SEQUENCE·LIVE·blue** stays very high even at **offset 3 (~86%)** while offset 1 is ~90%.  
That can mean **streak persistence** and/or **label lag** — both matter: a system “saying G0” may still be riding a color that keeps printing several rounds later.  
**Per-system true lag** = combine (A) median Intervalo/rounds **and** (B) best offset cell. Not all “G0” skins are next-card casino rounds.

Report paths:
- `bot/data/g0_secs_round_offset_report.json`
- `bot/data/g0_offset_oracle_report.json`

---

## 5) What we do next (order)

1. Keep expanding WITH_TIMING vs NO_TIMING fingerprints (already running on full Vany).  
2. Split WITH_TIMING → FIRE vs RESULT (done in catalog).  
3. Tag Clock A as sub-flag only.  
4. For each FIRE WITH_TIMING family: peak day, WR, median Intervalo, implied rounds, best color-offset.  
5. Revive countdown-only binge mode (May 22–23 class) as its own free proposer stream — not merged to death by SAFE_MERGE.
