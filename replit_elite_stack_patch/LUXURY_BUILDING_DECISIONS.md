# Luxury Building — Floor Decisions (LOCKED + SEEDED)

Rule: result cards fire under their signal **before** the live Bac Bo round, so volume at **lifetime/historical WR ≥ 60%** (n≥10) is worth stacking.

**Critical:** Live Replit `bacbo.db` is often truncated. Installer merges `historical_luxury_seed.json` so thin recent samples cannot wipe the building.

## Counts (seeded)

| Metric | n |
|---|---:|
| Live building floors | **32** (26 historical camadas + JUN08/10/19/20/26/27 peaks) |
| Peak-day locks | JUN19 · JUN20 · JUN08 · JUN10 · JUN26 · JUN27 · MAY19 · MAY10 |
| Hard blocked | JUN12A · JUN12B |

## Why JUN19 / JUN20 matter

Telegram good-card days (not previously named floors):

| Day | good_fires | WR | G0 wins |
|--|--:|--:|--:|
| **2026-06-19** | 2908 | **78.96%** | 1592 |
| **2026-06-20** | 3003 | **81.07%** | 1756 |

Also seeded: JUN08 / JUN10 / JUN26 / JUN27 (monster G0 volume days).

## Live building floors

`AITEST_ULTIMATE` · `AITEST_APR20_MAX` · `MAY01` · `APR20` · `LIVE` · `APR27` · `ELITE_V2` · `ULTIMATE` · `AITEST_LIVE` · `APR22` · `APR26` · `APR20_MAX` · `MAY19` · `MAY10` · `MAR21` · `APR29` · `ELITE_V2_PEAK` · `MAR19` · `MAY11` · `MAR20` · `AITEST_MAR21` · `APR30` · `APR28` · `AITEST_APR20` · `MAY04` · `APR19` · **`JUN19`** · **`JUN20`** · **`JUN08`** · **`JUN10`** · **`JUN26`** · **`JUN27`**

## Virtual setups (boosters)
`SOLO_ELITE|BLUE` · `SEQUENCE|BLUE` · `GOLDEN|BLUE` · `PLATINUM|BLUE` · `SEQUENCE`

## Install
See `REPLIT_COMMANDS.md` — re-run `install_luxury_building.py` (must download seed).  
Expect **~32 live floors**, not 1.
