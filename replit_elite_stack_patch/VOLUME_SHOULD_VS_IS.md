# SHOULD vs IS — why 36 peak floors are not “exploding”

## Your worry (correct)

You have **30–36+ factual good peak floors/camadas**.  
Historically, when **each** system was the **only** one running, that single floor freely fired on the order of **~100 → ~4000 signals/day** on its best day(s) — not “together,” not waiting for multi-floor coalition.

So the **basic expectation** is:

> If every peak floor is wired as its own full machine again,  
> each one should fire **every signal it would have fired on its peak day**,  
> and the day total should look like **the sum of those free streams**  
> (minus only true same-window bankroll collisions) —  
> i.e. **thousands → 5k+ signals/day**, not a quiet trickle.

What you are seeing instead feels like **slowdown / funnel / mute** while the UI says “32 floors locked.”  
That mismatch is real. It is not you misunderstanding profit.

---

## What IS (today — v1)

```
rooms → ONE LIVE engine proposes a candidate
      → EdgePolicy SCOREs many floors (ALLOW/deny stamp)
      → tower MERGE picks ≤1 winner floor label
      → outbox sends ≤1 money card per conflict window
```

| Piece | Reality |
|-------|---------|
| Peak locks / gates | Installed — good |
| Floors in merge | Mostly **vote/stamp** the LIVE candidate |
| Independent peak-day fire streams | **Not running** |
| Volume shape | ≈ **1 pipe**, not **36 pipes** |
| Symptom in vitals | `VOLUME_GAP_VS_PEAK` on many best floors; some `silent_floors`; blocked-would-win misses |

So: **36 brains rating one mouth ≠ 36 mouths speaking.**  
That is why “everything installed” does not explode volume.

Proof already in organism vitals (example snapshot): dozens of floors ranked, **most volume-gapped or silent**, while LIVE still dominates strength — classic single-proposer artifact.

---

## What SHOULD be (v2 — explosion architecture)

```
rooms → EACH peak floor PROPOSES with its own frozen peak gates
      → (own hours, rooms, kinds, thresholds, cooldown — loss on JUN19 ≠ mute MAY10)
      → lane split (money / Clock-A timed)
      → conflict referee ONLY when same bankroll window collides
           · same color → may keep multiple SOLO_FACT cards OR collapse to one money decision (mode switch)
           · opposite color → must lock one
      → outbox delivers the free stream(s)
      → each fire gets its own result + truth color
```

**Rule you care about:**  
A floor that historically knew/predicted “color coming” on peak day must be able to say it **again**, alone, without needing 2–3 other rooms or another floor’s permission — unless *that floor’s own peak gates* required those rooms.

Coalition (≥2 rooms) is **one origin**.  
Solo peak floor free-fire is **another**.  
They must not be collapsed into “only LIVE proposes.”

---

## Two operating modes (must be explicit)

| Mode | Behavior | When |
|------|----------|------|
| **SAFE_MERGE** (current default mindset) | ≤1 money card / conflict window | Protect bankroll from red+blue doubles / spam |
| **EXPLOSION / PEAK_SUM** (what you’re asking for) | Every peak floor free-fires its peak stream; referee only on true opposite-color same window | Restore day-one volume × N floors |

You cannot get “36× peak day” while leaving SAFE_MERGE as the only path.  
v1 is SAFE_MERGE dressed with floor stickers.  
Your instinct (“boost / explode”) needs **EXPLOSION mode + real proposers**.

---

## Dollar honesty (so hope doesn’t fight physics)

At **$10/guess** and ~1.95× G0 payout, net ≈ **~$9.50 per G0 win**.

| Target profit/day | Approx G0 wins needed @ $10 |
|-------------------|-----------------------------|
| $50,000 | ~5,300 G0 wins |
| $100,000 | ~10,500 G0 wins |

One Bac Bo table ≈ one result every ~30s → **~2,880 rounds/day** hard ceiling.  
So **$50k–$100k/day at $10/bet on one table is not physically reachable** even at absurd WR.  
That target needs **higher stake**, **many tables**, or both — *after* volume is restored.

Volume restoration (5k+ signal cards / dual lanes / multi-floor free-fire) is still the right first war.  
Dollar print is stake × units × G0 — separate lever.

---

## What “slowing down instead of boosting” means in one sentence

**We bolted peak floors onto a single proposal funnel, so the system compresses history’s best days into one stream instead of replaying all of them in parallel.**

---

## Build that matches your basic

1. **Shadow miss ledger** — per floor: “would have ALLOWed on peak gates but LIVE never proposed / merge dropped”  
2. **v2 proposers** — one process/queue per peak floor (or multiplexed workers), each writing `proposals`  
3. **VOLUME_MODE=EXPLOSION** — default referee = opposite-color lock only; same-color multi-ALLOW can all emit as SOLO_FACT (or coalesce only if same exact round id)  
4. **Peak fidelity KPI** — each floor’s live fires/day ≥ its peak_day fires/day (attributed)  
5. **Dual lane** — Clock-A timed floors free-fire to `@UNIQUE_g1`; money/coalition to Mr_iv4  
6. **No fake consensus** — solo peak fire ≠ “3 rooms confirmed”

Until (2)+(3) ship, “36 floors live” will keep feeling like a lie next to day-one volume.
