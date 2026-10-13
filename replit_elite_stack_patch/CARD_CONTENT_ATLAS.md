# CARD CONTENT ATLAS — every card type, read by what it says

Generated 2026-10-13T17:07:06.277287+00:00. Reproduce with `python3 bot/card_content_atlas.py`.

`signal_kind` only knows 7 buckets. Two cards sharing one kind can encode entirely different setups, so everything here is classified on body content.

## 1. How many distinct cards there really are

| Measure | Count |
| --- | --- |
| Card types catalogued | 827 |
| Distinct designs after normalising numbers/rooms/times | 597 |
| Designs with a single variant | 520 |
| Card types that actually fired | 781 |
| Card types built but never fired | 46 |
| Card types that instruct a bet | 71 |
| Card types with their original result preserved | 4 |

Telegram holds 39,271 distinct type fingerprints, of which 10,423 look like product cards. Only 1,651 map to a registry family (15.84% of types) — but those cover 89.25% of product messages. Type ids were fingerprinted from rendered text including the statistics, so one template renders a new 'type' for every number it prints. Unmapped types are mostly that long tail, which is why message coverage is far higher than type coverage.

Message volume by chat (first appearance):

| Chat | Messages |
| --- | --- |
| mr_iv4 | 537,139 |
| UNIQUE_g1 | 27 |

## 2. Designs carrying the most variants

Each row is one template; variants are the same card with different numbers in it.

| Variants | TG msgs | Bet? | Roles | First line of design |
| --- | --- | --- | --- | --- |
| 60 | 7,259 | no | OPS/RESULT/UNKNOWN | `🔧 [DBG] <ROOM> → blue conf=entry trust=<N> streak=<N> score=<N> agree=<N>` |
| 33 | 424 | yes | RESULT/UNKNOWN | `<ROOM>+<ROOM> n=<N> WR=<N>%` |
| 21 | 309 | no | UNKNOWN | `🔵 SIGNAL #<N> -- SOLO_ELITE red \| rooms:@…` |
| 8 | 293,992 | no | ROOM_RELAY | `📡 <ROOM> — <N>/<N>/<N> <TIME>` |
| 8 | 1,711 | no | RESULT/UNKNOWN | `🎰 SEQUÊNCIA Nx 🔴 VERMELHO` |
| 8 | 65 | no | RESULT/UNKNOWN | `💎 SOLO ELITE → sala elite sozinha / single elite room` |
| 7 | 39,510 | no | RESULT/UNKNOWN | `🔴🔴🔴🔴🔴 VERMELHO 🔴🔴🔴🔴🔴` |
| 5 | 6,990 | no | RESULT | `🟡⚡🟡 PRESSÃO DE EMPATE — ALERTA AUTOMÁTICO 🟡⚡🟡` |
| 4 | 10,119 | no | RESULT | `✅ WIN — SOLO_ELITE` |
| 4 | 3,045 | yes | FIRE/RESULT/UNKNOWN | `⛔ DO NOT BET — ROUND PASSED ⛔` |
| 4 | 2,363 | no | RESULT | `❌ LOSS — G<N> FALHOU` |
| 4 | 621 | no | RESULT | `🟡 EMPATE — SOLO_ELITE` |
| 4 | 446 | no | RESULT/UNKNOWN | `📊 AUDIT <N>° (DB only)` |
| 4 | 285 | yes | RESULT/UNKNOWN | `⚡ **ENTRE AGORA — VIRADA DETECTADA**` |
| 3 | 2,281 | yes | UNKNOWN | `📊 Market Status — ⚡ Gale <N> detected` |

## 3. What the cards claim about themselves

81 card types print both a win rate and a sample size. Grouped by how much data backs the claim:

| Sample size | Cards | Mean claimed WR | Best claim |
| --- | --- | --- | --- |
| n<=15 | 27 | 83.1% | 100.0% |
| n=16-30 | 22 | 71.3% | 100.0% |
| n=31-60 | 11 | 73.0% | 95.0% |
| n=61-150 | 4 | 70.7% | 87.8% |
| n>150 | 17 | 63.1% | 78.9% |

Mean claimed win rate falls 20.0 points from the smallest samples to the largest. A real edge does not weaken as you measure it more; a selected one does, because the selection is what produced the number.

### Every 100% claim, and the evidence under it

12 card types claim a perfect rate. The largest sample behind any of them is **n=20**.

| n | TG msgs | Card |
| --- | --- | --- |
| 6 | 6 | `🔴 accum_solo_tier                     n=   6 W=  6/L=  0/T= 0  sWR=100.0%  net=-` |
| 10 | 1 | `🔴 hard_fva_ceiling                    n=  10 W= 10/L=  0/T= 0  sWR=100.0%  net=-` |
| 10 | 23 | `bacbob2xbet           +rigosinais              n= 10 WR=100.0%` |
| 10 | 6 | `bacbobrl              +robobacbodados          n= 10 WR=100.0%` |
| 11 | 18 | `reicassinofs          +rqdados1                n= 11 WR=100.0%` |
| 11 | 16 | `baccarat_b            +speedbaccarat_a_01      n= 11 WR=100.0%` |
| 11 | 23 | `bacboaovivovip        +sinaisbacboangola       n= 11 WR=100.0%` |
| 11 | 28 | `bacboaovivovip        +sinaisbacboangola       n= 11 WR=100.0%` |
| 12 | 4 | `coringadados          +sinal_bac_bo            n= 12 WR=100.0%` |
| 13 | 4 | `isadados              +umgalesalabacbo123      n= 13 WR=100.0%` |
| 15 | 62 | `reicassinofs          +rqdados1                n= 15 WR=100.0%` |
| 20 | 2 | `rqdados               +speedbaccarat_a         n= 20 WR=100.0%` |

Claims resting on at least n=100: **19**.

These clear even money against their own stated sample, before accounting for having been picked as the best of many candidates:

- 59.1% on n=274 — `GOLDEN     /red/H14  overall_WR=59.1%  n=274`
- 79.7% on n=133 — `@footballstudiodice01              n= 133 W=100 L= 27 T= 6 WR= 79.7% | b=86.4%(n`
- 76.1% on n=197 — `@footballstudiodice01              n= 197 W=140 L= 47 T=10 WR= 76.1% | b=73.9%(n`
- 54.1% on n=625 — `🔴 solo_proven_room_main               n= 625 W=297/L=287/T=41  sWR= 54.1%  net=-`
- 78.9% on n=1085 — `@martinswinbacbo                   n=1085 W=800 L=229 T=56 WR= 78.9% | - | last=`
- 78.8% on n=391 — `SOLO_ELITE /red/H05  T≥2.70  WR=78.8%  n=391/total391`
- 78.4% on n=250 — `SOLO_ELITE /blue/H18  T≥3.81  WR=78.4%  n=250/total344`
- 61.2% on n=3113 — `🔴 GOLDEN       score=11-13   n=3113  blocked-but-WR= 61.2%`
- 61.6% on n=263 — `🔴 GOLDEN       score=7-8     n= 263  blocked-but-WR= 61.6%`
- 64.6% on n=837 — `SOLO_ELITE /red/H00  overall_WR=64.6%  n=837`
- 62.2% on n=347 — `SOLO_ELITE /blue/H13  overall_WR=62.2%  n=347`
- 72.5% on n=302 — `🟡 SOLO_ELITE   score=7-8     n= 302  blocked-but-WR= 72.5%`
- 77.5% on n=965 — `@robobacbodados                    n= 965 W=724 L=217 T=24 WR= 77.5% | - | last=`
- 87.8% on n=115 — `📊 **87.8% WR** combinado · TRUE G2 · n=115`

### Pricing the search that produced those cells

Most high claims are keyed to a pair of source rooms agreeing. The corpus contains **59 source rooms**, which is **1,711 candidate pairs**. Scoring every pair against the bot's own labels, which run about 77.5% overall, you would expect roughly **103.6 pairs** to show a spotless record on n=11 with no skill whatsoever.

The corpus contains **12**. Expected count is candidate_pairs * baseline**n — how many pairs reach a spotless record on n observations with no skill at all. Pairs with fewer than n shared signals cannot produce a cell, so the true expected count is lower than this ceiling; the comparison is still the right order of magnitude for pricing the search.

So the perfect cells are not merely weak evidence, they are fewer than the search hands out for free. The card records the winner without recording the contest.

## 4. How to use the CSV

`bot/data/card_content_atlas.csv` has one row per card type with its content features, so every card can be reviewed by hand. Useful filters:

- `instructs_bet=True` — cards that tell you to place money
- `tg_count=0` — built in code, never fired once
- `claim_verdict=CLAIM_ON_THIN_SAMPLE` — prints a rate with too little behind it
- `room_pair` non-empty — setup is a pair of source rooms agreeing
- `had_original_result=True` — the original outcome card survives next to it
