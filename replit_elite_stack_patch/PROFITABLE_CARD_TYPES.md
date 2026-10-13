# Profitable Card Types — Day One → Jul 18 2026

Source: Vany Video Telegram export (`vany_video_telegram_chat_history.csv`, ~510k msgs).  
Typed families/types: `/opt/cursor/artifacts/telegram_card_type_profit.json`.

Profit score ≈ G0 wins + 0.65×G1 wins − losses (fires without paired results score near 0).

---

## Family scoreboard

| Family | n | WR | G0 wins | Profit | Peak G0 day | Peak vol day |
|--|--:|--:|--:|--:|--|--|
| **NORMAL_RESULT** | 20,702 | **75.3%** | 9,438 | **9,366** | Jun 28 (3874*) | Jun 28 (6033*) |
| **COUNTDOWN_SIGNAL_FIRE** | 32,813 | 51.6%† | 9,398 | **5,733** | **May 10 (505)** | **May 19 (2837)** |
| **COUNTDOWN_RESULT** | 6,320 | **91.3%** | 4,303 | **5,149** | Apr 24 (334) | May 15 (491) |
| NORMAL_SIGNAL_FIRE | 37,289 | n/a | 950 | 769 | May 10 (181) | Jun 8 (1529) |
| AUTO_RELAY_RESULT | 20,676 | — | 0 | **0** | — | May 26 (953) |

\* Jun 28 oracle flood — high G0 *mentions*, treat as spam risk, not stack target.  
† Fire cards often embed later result text; use paired COUNTDOWN_RESULT WR (~91%) as the real edge.

### Countdown signal vs countdown result

| | COUNTDOWN SIGNAL FIRE | COUNTDOWN RESULT |
|--|--:|--:|
| Role | Entry / timer / “apostar agora” | Post-round green/loss/placar |
| Volume king | Yes (32.8k) | Smaller (6.3k) |
| Win-rate | Noise in fire text | **~91%** (best family) |
| Best single type | `CD_FIRE_TIMER_BRT_EDT_APOSTAR` | `CD_RES_GREEN_G_BRT` |
| Best G0 day | May 10 → **500–505 G0** | Apr 24 → **334 G0** |
| Best volume day | May 19 → **2819 fires** | May 15 → 491 |

**About “~780 G0 from countdown fire templates”:**  
Closest real numbers in this chat:

| What you likely remember | Actual day | Actual count |
|--|--|--|
| ~780 auto “win” spam (not profit) | **2026-05-19** | **798** `RES_AUTO_WIN` |
| True CD fire G0 peak | **2026-05-10** | **500** (`CD_FIRE_TIMER…`) / family **505** |
| Biggest CD fire volume day | **2026-05-19** | **2819** timer fires |
| CD ecosystem G0 ~750 | **2026-05-30** | ~729–750 CD result G0 |
| Chat-wide G0 mentions ~780 | Jun 19 (776) / Apr 23 (784) | mixed types |

So the monster countdown *fire volume* day is May 19; the monster countdown *G0 attribution* day for fires is May 10 (~500), not 780. Pair fire→result glue is what turns May-19 volume into May-10-style G0.

---

## Every profitable type (n≥30, profit > 0)

Ranked by profit score:

| Rank | Type | Family | n | WR | G0w | Profit | Peak G0 day | Peak G0 |
|--:|--|--|--:|--:|--:|--:|--|--:|
| 1 | **RES_WIN_KIND** | NORMAL_RESULT | 10,922 | 100%* | 4,759 | **8,279** | Jun 8 | 315 |
| 2 | **CD_FIRE_TIMER_BRT_EDT_APOSTAR** | COUNTDOWN_SIGNAL_FIRE | 25,826 | 56%† | 9,064 | **6,184** | **May 10** | **500** |
| 3 | **RES_ORACLE_CARD** | NORMAL_RESULT | 5,560 | — | 3,723 | 3,723 | Jun 28* | 3722* |
| 4 | **CD_RES_GREEN_G_BRT** | COUNTDOWN_RESULT | 3,253 | **100%** | 1,579 | **2,653** | May 15 | 255 |
| 5 | **CD_RES_RODADAS_TEMPO** | COUNTDOWN_RESULT | 1,519 | — | 1,285 | **1,274** | **Apr 24** | **334** |
| 6 | **CD_RES_BELL_GANHOU** | COUNTDOWN_RESULT | 859 | **100%** | 859 | **1,025** | Jul 10 | 164 |
| 7 | **FIRE_GOLDEN** | NORMAL_SIGNAL_FIRE | 6,584 | — | 925 | 925 | May 10 | 180 |
| 8 | **RES_GREEN_G0** | NORMAL_RESULT | 357 | 100% | 357 | 411 | Apr 27 | 107 |
| 9 | **CD_RES_FORENSIC_INTERVALO** | COUNTDOWN_RESULT | 306 | — | 197 | 197 | Jun 28* | 196 |
| 10 | **CD_FIRE_QUANTUM_LOCK** | COUNTDOWN_SIGNAL_FIRE | 1,517 | — | 35 | 34 | May 2 | 16 |
| 11 | **CD_FIRE_RUSH_NS_LEFT** | COUNTDOWN_SIGNAL_FIRE | 325 | — | 19 | 19 | Apr 29 | 16 |
| 12 | **RES_GREEN_G1** | NORMAL_RESULT | 159 | 100% | 0 | 58 | — | 0 |

\* Result cards are wins by definition in that template.  
† Fire WR is contaminated; trust paired result family.

### Kinds that print when glued to wins

From `RES_WIN_KIND` / `CD_RES_BELL_GANHOU` top_kinds:

1. **SOLO_ELITE** (volume + G0 king)
2. **SEQUENCE** (highest WR setups, often BLUE)
3. **GOLDEN** (volume)
4. **PLATINUM** (smaller n, keep as sniper)

Best color/setup (prior Telegram setup scan): **SEQUENCE|BLUE, SOLO_ELITE|BLUE, GOLDEN|BLUE, PLATINUM|BLUE** (~89–91% WR).

---

## Dead / negative types — do not stack

| Type | Why |
|--|--|
| **RES_AUTO_WIN / LOSS / TIE** | 20k+ msgs, **0 profit** — pure relay spam |
| **RES_LOSS_KIND** | −3,105 profit |
| **CD_FIRE_DO_NOT_BET_PASSED** | −499 — late / passed signals |
| **FIRE_SOLO_ELITE** alone | −111 without paired result cards |
| **FIRE_SINAL_RETIDO** | −27 |
| **FIRE_SEQUENCIA_STREAK** | chatter, not entries |
| **CD_FIRE_MULTI_ALARM** | ~0 / slightly negative |
| **CD_RES_BELL_PERDEU** | losses (G0 field polluted) |
| **RES_G2_MISS_STOP** | stop noise |

---

## What else we should do

1. **Glue every countdown fire to its own countdown result**  
   Same signal id / floor / color. This is the path from May-19 fire volume → May-10 G0 density.

2. **Keep only profitable templates live**  
   - Fires: `CD_FIRE_TIMER_BRT_EDT_APOSTAR` (+ light RUSH/QUANTUM)  
   - Results: `CD_RES_GREEN_G_BRT`, `CD_RES_RODADAS_TEMPO`, `CD_RES_BELL_GANHOU`, `RES_WIN_KIND`  
   - Kill: AUTO relay, DO_NOT_BET_PASSED, LOSS spam, streak chatter

3. **Peak-lock parallel towers**  
   Freeze each floor to its peak-day gates/kinds/hours/core rooms; extra rooms = confirm-only votes.

4. **Promote WR≥60% shadow floors (~14)** onto the luxury stack; keep factory cells as boosters, not the building.

5. **Bias BLUE + SOLO_ELITE / SEQUENCE / GOLDEN** for volume+WR; RED only as volume-side confirm, not primary luxury.

6. **Upload `may_jul_export.zip` + `luxury_export_light.zip` via YDRAY** so we can lock live DB peaks/core rooms to these card economics.

7. **Ignore Jun 28 oracle flood** as a target — G0 mention spam, not a repeatable edge day.

8. **Still need Twin225 casino truth** for real WR; until then treat these as Telegram-card economics (`BOT_DB_INFERRED_ONLY`).
