# Luxury Building — Floor Decisions

Rule (user): result cards fire under their signal **before** the live Bac Bo round, so volume at **WR ≥ 60%** is worth stacking (early win/loss known).  
Sources: DB floor registry (73 floors) + Telegram good-card filter.

## Counts

| Metric | n |
|---|---:|
| Floors registered in system | **73** |
| Already in live building (PRECISION+BALANCED+VOLUME) | **12** |
| Missing to ADD (shadow, WR≥60%, n≥10) | **14** |
| Shadow keep/out (thin or &lt;60%) | **45** |
| Blocked (do not add) | **2** (JUN12A, JUN12B) |
| Rooms total | **66** (40 unmuted / 26 muted) |
| Live stack size after adds | **26** |

## Replit pull (fixed — no sqlite3 binary needed)

```bash
cd /home/runner/workspace
curl -fsSL -o replit_pull_luxury_export.sh \
  https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/cursor/add-engine-gate-registry-d5ba/replit_elite_stack_patch/replit_pull_luxury_export.sh
bash replit_pull_luxury_export.sh
ls -lah luxury_export_light.zip
```

Upload `luxury_export_light.zip` via YDRAY and paste the link.

## Telegram filter (good vs skip)

**Keep (good cards):** structured fires, WIN/LOSS kind cards, oracle/forensic timing cards  
**Skip (do not stack):** AUTO WIN/LOSS relays, VIP ads, cycle summaries, `SINAL FORMANDO`, streak chatter, audits, cooldown spam

## Already in the building — KEEP

| Floor | Lane | n | WR | G0 | max/day | Verdict |
|---|---|---:|---:|---:|---:|---|
| LIVE | BALANCED | 18786 | 81.13 | 77.57 | 2151 | LUXURY_BALANCED |
| ELITE_V2 | BALANCED | 8522 | 80.42 | 79.99 | 982 | LUXURY_BALANCED |
| AITEST_ULTIMATE | PRECISION | 49 | 93.75 | 93.75 | 37 | LUXURY_PRECISION |
| AITEST_APR20_MAX | PRECISION | 93 | 92.13 | 92.13 | 28 | LUXURY_PRECISION |
| ULTIMATE | BALANCED | 407 | 80.16 | 79.63 | 83 | LUXURY_BALANCED |
| AITEST_LIVE | VOLUME | 498 | 79.66 | 78.41 | 148 | LUXURY_VOLUME |
| MAY01 | BALANCED | 101 | 82.98 | 80.85 | 17 | LUXURY_BALANCED |
| APR20 | BALANCED | 115 | 81.48 | 81.48 | 18 | LUXURY_BALANCED |
| MAY10 | VOLUME | 312 | 76.27 | 73.90 | 76 | LUXURY_VOLUME |
| APR26 | VOLUME | 101 | 79.57 | 77.42 | 17 | PROMOTE_CANDIDATE |

## In building — DEMOTE / watch

| Floor | Lane | n | WR | G0 | Action |
|---|---|---:|---:|---:|---|
| MAR20 | VOLUME | 2637 | 70.64 | 67.45 | DEMOTE (fails luxury WR/G0) |
| MAR21 | VOLUME | 390 | 76.15 | 73.71 | WATCH / tighten only |

## ADD still (not in luxury stack yet)

| Floor / setup | Source | n | WR | G0 | Action |
|---|---|---:|---:|---:|---|
| APR22 | shadow floor | 58 | 79.63 | 75.93 | ADD (PROMOTE_CANDIDATE) |
| SEQUENCE\|BLUE | telegram kind×color | 1048 | 90.55 | high G0 card share | ADD as virtual luxury lane |
| SOLO_ELITE\|BLUE | telegram kind×color | 2742 | 91.90 | high G0 card share | ADD as virtual luxury lane |
| GOLDEN\|BLUE | telegram kind×color | 1002 | 91.82 | high G0 card share | ADD as virtual luxury lane |
| PLATINUM\|BLUE | telegram kind×color | 283 | 89.40 | high G0 card share | ADD as virtual luxury lane |
| SEQUENCE\|RED | telegram kind×color | 749 | 88.79 | high G0 card share | ADD carefully (lower than blue) |
| SOLO_ELITE\|RED / GOLDEN\|RED | telegram | large n | ~90 on WIN— cards | — | use only with DB confirm; DB all-color WR is weaker |

## Do NOT add

- JUN12A / JUN12B (blocked, ~61–62% WR)
- MAR19 as luxury (huge volume n=12057 but WR 72.28 / G0 69.94 → shadow only)
- Weak AITEST_*_MAX / APR28 / APR30 / MAY02 / MAY04 and other <70% WR shadows
- AUTO-relay volume, streak alerts, forming pre-fires

## Day scan takeaway

- Best real DB fired peak: **2026-05-19 = 3427 @ 78.28% WR** (ELITE_V2 / LIVE heavy)
- ELITE_V2 repeated 80%+ days in late May (700+/day) — already in building
- Telegram after dump (Jun19–Jul18) needs fresh `bacbo.db` export to create new floors safely
