# TOTAL CENSUS — everything ever built, and what its numbers are worth

Generated 2026-10-13T16:34:00.185795+00:00. Reproduce with `python3 bot/total_census.py`.

## The question this answers

Which fire systems, out of everything ever built in 6 months, have a profitable win rate that survives independent verification?

**None are verified. Infrastructure to verify exists (casino_round_results, signal_truth_matches) and holds zero rows, so every win rate below is the bot grading its own labels.**

## 1. Scale of what exists

| Layer | Count |
| --- | --- |
| Telegram messages scanned (Mr_iv4, UNIQUE_g1, UNIQUE_museum_chrono) | 537,166 |
| Distinct card type fingerprints | 39,271 |
| Museum templates catalogued | 827 |
| Floors / camadas / systems | 154 |
| Registry families | 120 |
| Systems that ever reached the database | 13 |
| Distinct systems with graded outcomes | 7 |

Coverage runs 2026-03-17 08:37:17 → 2026-08-03 20:52:41, complete back to day one.

The funnel is the headline. Of 154 floors, 120 were written in code, 103 ever appeared in Telegram, 13 reached the database, and 7 produced graded outcomes. 44 were built and never fired once.

Telegram traffic by role:

| Role | Messages |
| --- | --- |
| ROOM_RELAY | 293,992 |
| UNKNOWN | 93,704 |
| RESULT | 75,281 |
| EMPTY | 25,993 |
| OPS | 22,583 |
| FIRE | 22,079 |
| ONLINE | 3,533 |
| MEDIA | 1 |

Only 22,079 of 537,166 messages were fire cards. The largest share is ROOM_RELAY — copies of other rooms' traffic.

## 2. Every system that ever fired

| System | Band | TG cards | Fired | Graded | Wins | Claimed WR | Verified WR |
| --- | --- | --- | --- | --- | --- | --- | --- |
| SOLO_ELITE | PENTHOUSE | 11,228 | 1,058 | 1,058 | 832 | 78.64% | — |
| SEQUENCE | UPPER | 109 | 560 | 560 | 414 | 73.93% | — |
| GOLDEN | UPPER | 2,964 | 338 | 338 | 265 | 78.4% | — |
| PLATINUM | UPPER | 1,377 | 229 | 229 | 174 | 75.98% | — |
| FLASH | MID | 2 | 48 | 48 | 45 | 93.75% | — |
| EMERGING | BASEMENT | 0 | 3 | 3 | 3 | 100.0% | — |
| ULTRA_TIE | BASEMENT | 6 | 1 | 1 | 1 | 100.0% | — |
| **TOTAL** | | | | 2,237 | 1,734 | **77.51%** | **none** |

That is the complete list. Everything else in the census never produced a single graded outcome.

## 3. Why the claimed win rates cannot be used

`truth_verification_report.json` verdict: **BOT_DB_INFERRED_ONLY**

| Truth level | Rows |
| --- | --- |
| Direct casino results captured | 0 |
| Signals matched to a casino round | 0 |
| Outcomes inferred from the bot's own DB | 3,650 |

### The card cannot show a miss on a win

actual_color(predicted, outcome) returns `predicted` whenever outcome=='win', so a WIN card's 'Saiu'/'TRUTH THIS ROUND' field cannot disagree with the call.

Defined identically in:

- `bot/telegram_outbox.py:actual_color`
- `bot/fallback_result_sender.py:actual_color`
- `bot/peak_fidelity_ranker.py:actual_color`
- `bot/config/emanation_laws.py:factual_color_from_outcome`

So `Apostou: 🔵 BLUE → Saiu: 🔵 BLUE` is not an observation of the dice. On any card labelled WIN the two fields are the same value printed twice. A win card showing a matching outcome is arithmetic, not evidence, and it has been that way for every win card ever rendered.

### The grading window was unbounded

A Bac Bo round takes about 30 seconds. Observed resolve lag averages 16.1s with a minimum of 0.0s and a maximum of 6560.8s. Only 15.6% of signals (526) resolved inside a window that pins them to the round they named; 2,417 are flagged late-risk.

Among cells with at least 50 samples, the lowest-lag one is SEQUENCE on floor LIVE (n=324) at a median of 0.6s — the result landed in the DB effectively the same instant as the call, which is the shape you get when the outcome was already known.

A ~30s table round with a 0.0s minimum and a 6560s maximum resolve lag means the grader matched some fires to rounds far outside the round they named.

### The headline rate is also a martingale rate

G0 win rate 71.15% rises to 72.86% final only by counting gale recoveries, on 936 losses and 201 ties. Recovery wins cost escalating stakes, so final WR overstates return even if the labels were sound.

## 4. What would make a verified answer possible

- Capture Twin225 round_id/player_total/banker_total/actual_color directly.
- Store every direct result in casino_round_results.
- Match consensus_signals.id to casino_round_results.round_id before counting verified WR.
- Require signal_time < betting_closed_at for early-result oracle claims.

Until `casino_round_results` holds independently observed rounds and `signal_truth_matches` joins calls to them with the call timestamped before betting closed, no system in this repo has a measured win rate. Opening a sala de sinais per system would publish the claimed column above as if it were the verified column.

## 5. Standing note on the underlying bet

Bac Bo is dice. Player/Banker pays about even money against a house edge near 2.7%, and rolls are independent, so no arrangement of floors, gates, coalitions or skins shifts the next roll. A genuine 77% rate on an even-money independent event is not a strong edge, it is a signal that the measurement is wrong.
