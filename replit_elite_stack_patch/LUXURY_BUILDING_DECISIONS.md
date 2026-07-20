# Luxury Building — Floor Decisions (LOCKED)

Rule: result cards fire under their signal **before** the live Bac Bo round, so volume at **lifetime WR ≥ 60%** (n≥10) is worth stacking.

Generated stack: `bot/data/luxury_building_stack.json`  
Runtime mode: `EDGE_POLICY_MODE=luxury`

## Counts

| Metric | n |
|---|---:|
| Floors registered | **73** |
| **Live building (PRECISION+BALANCED+VOLUME)** | **26** |
| Shadow (thin / unproven) | **45** |
| Blocked | **2** (`JUN12A`, `JUN12B`) |

## Live building — all 26 good floors

### PRECISION (2)
`AITEST_APR20_MAX` · `AITEST_ULTIMATE`

### BALANCED (5)
`LIVE` · `ELITE_V2` · `ULTIMATE` · `APR20` · `MAY01`

### VOLUME (19) — newly promoted under WR≥60 rule
`MAR19` · `MAR20` · `AITEST_LIVE` · `MAR21` · `MAY10` · `APR26` · `AITEST_MAR21` · `APR22` · `APR29` · `APR30` · `APR27` · `ELITE_V2_PEAK` · `APR28` · `MAY19` · `APR20_MAX` · `MAY11` · `AITEST_APR20` · `MAY04` · `APR19`

## Blocked — never fire
`JUN12A` · `JUN12B`

## Card policy
**Keep:** `CD_FIRE_TIMER_BRT_EDT_APOSTAR`, `CD_RES_GREEN_G_BRT`, `CD_RES_RODADAS_TEMPO`, `CD_RES_BELL_GANHOU`, `RES_WIN_KIND`, `FIRE_GOLDEN`, `RES_GREEN_G0`  
**Kill:** AUTO relay, `DO_NOT_BET_PASSED`, LOSS spam, streak chatter  
**Bias:** SOLO_ELITE / SEQUENCE / GOLDEN / PLATINUM · **BLUE**

## Install on Replit
See `REPLIT_COMMANDS.md` — run `install_luxury_building.py` then `source luxury_building.env`.
