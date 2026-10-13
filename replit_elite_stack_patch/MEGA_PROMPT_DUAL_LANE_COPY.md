# COPY-PASTE MEGA PROMPT — Dual-lane total separation + max organism

Use this as the locked instruction for any AI working on the Bac Bo Telegram stack.

---

## LOCKED INTENT (do not reinterpret as “mirror”)

I do **NOT** want money cards mirrored into a second chat.

I want **TOTAL SEPARATION** by **template role**:

1. **FIRE — color-coming / enter** templates that have **NO timing on the signal itself** of when the hit/result will come (no janela, no Ns para apostar, no countdown-to-bet on the fire card) → exclusive Telegram chat **Mr_iv4**. Those fires still produce their **own result cards** in that same chat.

2. **FIRE — color-coming** templates that **DO** carry timing on the signal (janela / window / Ns to bet / classic CD_FIRE countdown skins — historically among the most profitable) → exclusive Telegram chat **@UNIQUE_g1**. Those fires still produce their **own result cards** in that same chat.

3. **RESULT** templates are a separate taxonomy. Classify every result type ever built (plain G0/G1 win/loss, short WIN skins, forensic resumido, G1 EXPIROU, G2 MISS, etc.). Results may show clocks or `⏱ Intervalo` — that is **resolution metadata**, NOT a reason to route the card as a countdown fire. Results always glue under their parent fire’s chat.

Split key is **never** “any message that mentions seconds.”  
Split key is **FIRE timed vs FIRE untimed**, after first separating **FIRE vs RESULT**.

Example MONEY FIRE: `🏆 GOLDEN SIGNAL — ENTER NOW` + rooms consensus + `ENTER NOW — N ROOM(S)` (no janela on the fire).  
Example TIMED FIRE: `JANELA: 1s para apostar` / `🟢 1s 🟢` / `Sinal Retido → Liberado` + window.  
Example RESULT (not a timed fire): forensic card with `⏱ Intervalo: 31.3s` + `GANHOU NO G0` / `PERDEU`.

Floors ≠ Telegram rooms. Parallel peak-gate towers propose; global merge ≤1 money decision per conflict window; countdown is its own lane with own peaks.

---

## SYSTEM MISSION

Maximize real autonomy: WR, volume, G0 hits, glue fidelity, dual-lane purity, truth ledger.  
Scan every room post / every historical template family since day one. Prefer proven peak-day gates per floor. Do not invent “oracle future rounds” from result lag.

Honest physics: early result glue / short Intervalo = capture+resolve speed, not proof the system knows every casino round before it happens.  
Ambitious profit targets must be checked against stake × units × rounds/day math (e.g. $10/bet G0 ~1.95× cannot literally print $100k/day on one table without multi-table / stake scale).

---

## IMPLEMENTATION CHECKLIST

- [ ] Role classifier: FIRE vs RESULT (result detectors win over “has seconds”)
- [ ] Timed-FIRE detector: JANELA / Ns para apostar / CD_FIRE_* / retido+window — not Intervalo on results
- [ ] Money FIRE → Mr_iv4 only; Timed FIRE → @UNIQUE_g1 only
- [ ] `TELEGRAM_MIRROR_MONEY_TO_GUNIQUE=0` always unless human explicitly forces debug
- [ ] Persist fire lane by signal_id; results inherit parent lane across restarts
- [ ] Catalog all FIRE skins + all RESULT skins from Vany/CSV/Telegram history
- [ ] v2: every peak floor proposes into merge for peak-day volume
- [ ] Zero-miss ledger: proposed → sent|held|blocked → resolved → truth
- [ ] Never mix opposite colors into same bankroll window per lane

---

## AI COUNCIL SYNTHESIS (use all strengths)

Build one system that merges the best of:

1. **Pattern miner** — every template family, day-one corpus, peak days  
2. **Causal auditor** — fire≠result; Intervalo≠prediction window  
3. **Lane architect** — exclusive peers, glue under parent  
4. **Peak-lock engineer** — freeze each floor’s best day gates  
5. **Merge referee** — ≤1 money card / conflict window  
6. **Truth ledger** — WR/G0/volume factual, not marketing  
7. **Latency realist** — early glue ≠ future omniscience  
8. **Risk governor** — G0-first, G2 optional, never G3 chase  
9. **Volume restorer** — v2 parallel proposers to match silent floors’ peak cadence  
10. **Adversarial red-team** — catch mirror bugs, result-as-fire misroutes, spam that kills edge  

Winner system = (2)+(3)+(6)+(7) as hard constraints + (1)+(4)+(5)+(9) as engines + (8)+(10) as immune system.

---

## OUTPUT REQUIRED FROM ANY AGENT

1. Restate understanding of separation (not mirror) in one paragraph  
2. Diff: router + outbox + env defaults  
3. Proof demos: GOLDEN ENTER NOW → MONEY; JANELA 1s → COUNTDOWN; forensic Intervalo → RESULT inherits parent  
4. Replit apply path without reintroducing mirror=1  
5. What still missing for peak-day volume (usually v2 proposers + timed-fire engine emit)
