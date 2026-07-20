# Final Luxury Building Plan — Everything

## Floors ≠ Rooms (locked in)
- **Floor / camada** = engine config version (`LIVE`, `ELITE_V2`, `MAR19`…) — how the bot decides.
- **Room** = Telegram source (`@rqdados`, `@IsaDados`…) — who feeds coalitions.
- Latest Replit export: **26 floors** in DB · **79 rooms** in `rooms` table.
- Live luxury lanes: **26 floors** (every WR≥60% n≥10). Blocked: JUN12A/JUN12B. Mode: `EDGE_POLICY_MODE=luxury`.

---

## Every luxury / stack version we already tried

| # | Version | What it was | Result / truth |
|---|---|---|---|
| 1 | **BASE_18 (“18 floors”)** | LIVE + MAR19–21 + APR* + early MAY | Foundation. ULTIMATE = cherry-pick of these gates |
| 2 | **EXPANDED_60 (“60 floors”)** | Base + AITEST + MAX + PEAK + MAY10–27 + JUN + ELITE_V2 | Remembered best G0-before-round era; stopped ~3:55 Pawtucket window |
| 3 | **LIVE alone** | Main production floor | Biggest: n≈18.8k, WR≈81%, peak day 2151 |
| 4 | **ELITE_V2** | Elite core | n≈8.5k, WR≈80%, late-May 600–770/day @ 80–83% |
| 5 | **ULTIMATE** | All-18 gate blend | Solid balanced, smaller n≈407, WR≈80% |
| 6 | **MAR19 volume giant** | Huge volume shadow | n≈12k, WR≈72% — volume yes, not precision king |
| 7 | **MAY20–27 PEAK_VOLUME** | Peak calendar floors | Hot days 80–84% but many thin / JUN12 blocked |
| 8 | **Super Ultra Skyscraper (12 live)** | P2 + B5 + V5 live; rest shadow | Current structural building |
| 9 | **Luxury Building (≥60% early-result rule)** | Keep 12 + add WR≥60 shadows (esp MAR19, APR22…) → target **26** | Matches “result card before round ⇒ volume is money” |
| 10 | **Policy modes** | shadow / precision / volume / G0-only max | Volume mode = flood; precision = sniper |
| 11 | **Floor Factory virtuals** | 184 generated peak/room/hour cells | Learn-only until promoted |
| 12 | **LEGACY_355** | Moving Pawtucket window oracle | Warning lane, not free-fire |

**Hard peak from dump day:** 2026-05-19 = **3427 fires @ 78.28% WR / 77.96% G0**.  
**Frontier:** 3500/day only holds around 75–78% WR — not 98%. Early-safe ≤20s ≈ **16%** of results (bot-inferred, not Twin225 direct).

---

## Best way to run THIS last version

### Goal
Max volume + max WR + max G0 hits, with each floor firing **exactly like its peak day**, in parallel, without killing each other — using early result cards as the volume weapon.

### Architecture: Peak-Locked Parallel Towers

```
┌──────────── Floor Tower: ELITE_V2 (peak 2026-05-19/24) ────────────┐
│ frozen gates · frozen kinds · CORE rooms (peak day only)            │
│ EXPAND rooms = confirm-only (same color vote, cannot flip alone)    │
│ own cooldown / own hour map / own score                             │
└───────────────────────────┬─────────────────────────────────────────┘
┌──────────── Floor Tower: LIVE ──────────────────────────────────────┐
│ same isolation rules                                                │
└───────────────────────────┬─────────────────────────────────────────┘
┌──────────── Floor Tower: MAR19 / APR22 / … (each peak-locked) ─────┐
└───────────────────────────┬─────────────────────────────────────────┘
                            ▼
                 GLOBAL MERGE (only place floors meet)
                 1) same-round opposite-color LOCK
                 2) one outbox / rate limit
                 3) pick highest peak-confidence card
                 4) result card glued to THAT floor’s fire
```

### What to put in the live building now

**KEEP (already in):**  
LIVE · ELITE_V2 · ULTIMATE · AITEST_LIVE · AITEST_ULTIMATE · AITEST_APR20_MAX · APR20 · APR26 · MAY01 · MAY10 · MAR21  
(+ MAR20 only as volume lane under ≥60% rule)

**ADD next (shadow → live, WR≥60%):**  
MAR19 · APR22 · APR29 · APR27 · ELITE_V2_PEAK · MAY19 · APR20_MAX · AITEST_MAR21 · MAY11 · APR30 · APR28 · AITEST_APR20 · MAY04 · APR19  
→ **~26 floor live stack**

**NEVER add:** JUN12A · JUN12B · &lt;60% thin AITEST trash

### Rooms — not “all 79 as equals”
- **Core per floor** = rooms that actually fired on that floor’s peak day (locked).
- **Expand** = other strong KEEP rooms as **confirm votes only** (same color).
- Do **not** let weak/stale rooms flip a peak floor.
- Global opposite-color lock stays ON.

### Must-freeze per floor (not only rooms)
1. `_gates_*` snapshot from peak day  
2. Allowed kinds (SEQUENCE / SOLO / GOLDEN / PLATINUM / FLASH)  
3. Hour / minute windows from peak day  
4. Thresholds / score cuts  
5. Core room set  
6. Early-result glue (result card under its own fire, no delay)

### Parallel without hurt
- Floor-local dedup (same floor won’t double-spam)
- Global color lock (no red+blue same window)
- No shared post-loss cooldown across floors
- No shared “blocked hour” that one floor’s bleed can impose on another
- G0-only cards for money; gales advisory-only unless martingale audit says ALLOW

### Why this beats every prior version
| Old approach | Failure | This fix |
|---|---|---|
| One shared brain | Floors damp each other | Isolated towers |
| All rooms everywhere | Dilutes peak | Core + confirm expand |
| Chase 98% WR | Caps volume ~17–283/day | Accept ≥60% with early result edge |
| Free-fire blocked supply | WR collapses ~60% | Only peak-locked floors |
| Evolving live gates | Peak drifts away | Frozen peak snapshot |

---

## Pull May–July from Replit (do this now)

```bash
cd /home/runner/workspace
curl -fsSL -o replit_pull_may_jul.sh \
  https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/cursor/add-engine-gate-registry-d5ba/replit_elite_stack_patch/replit_pull_may_jul.sh
bash replit_pull_may_jul.sh
ls -lah may_jul_export.zip luxury_export_light.zip
```

Upload **both** zips via YDRAY and paste the links.  
Then I will:
1. Lock each floor’s true peak day (May/Jun/Jul)  
2. Extract core rooms per peak  
3. Wire the parallel tower stack into EdgePolicy live mode  
4. Leave JUN12 + &lt;60% out  

---

## Expected band (honest)
- With early result cards + ≥60% floors + parallel peak locks: **high volume days in the 2k–3.5k band @ ~75–82% WR** when markets match May peaks.
- 98% WR at 3500/day is **not** in the historical frontier.
- Direct Twin225 capture still required to prove “100% before round” claims.
