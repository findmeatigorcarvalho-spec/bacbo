# Card template taxonomy — total separation (NOT mirror)

## What “mirrors 1” was (WRONG for your intent)

`TELEGRAM_MIRROR_MONEY_TO_GUNIQUE=1` **duplicated** every money card into `@UNIQUE_g1`.  
You did **not** ask for copies. You asked for **two exclusive pipes** by template family.

Default is now **`TELEGRAM_MIRROR_MONEY_TO_GUNIQUE=0`**.

---

## Split key (locked)

| Step | Rule |
|------|------|
| 1 | Classify **ROLE**: `FIRE` (color coming / enter) vs `RESULT` (outcome / ops) |
| 2 | Only **FIRE** chooses Telegram peer |
| 3 | **RESULT** always posts in the **same chat as its parent FIRE** |
| 4 | `⏱ Intervalo: XXs` on a result is **reporting**, never a countdown-fire detector |

---

## Lane A — MONEY → Mr_iv4 only

**FIRE** templates with **no bet-window / janela / Ns-to-hit on the signal itself**.

Examples from your chat:

- `🏆 GOLDEN SIGNAL — ENTER NOW`
- `Rooms in consensus (3)` / `CONFIRMED ENTRY`
- `⚡ ENTER NOW — 3 ROOM(S) CONFIRMED`
- Coalition / GOLDEN / PLATINUM / SEQUENCE / SOLO_ELITE **without** `JANELA: Ns`

**Their results** (forensic G0/G1 win/loss, short `✅ WIN — …`, even with Intervalo) stay on **Mr_iv4**.

---

## Lane B — TIMED / COUNTDOWN → @UNIQUE_g1 only

**FIRE** templates where **timing is on the SIGNAL** (when to bet / when color hits).

Examples:

- `JANELA: 1s para apostar`
- `🟢 1s 🟢`
- `⏳ Sinal Retido → Liberado` + window
- `CD_FIRE_TIMER_BRT_EDT_APOSTAR` and classic countdown signal-fire skins  
  (historically elite volume — not every system reaches Telegram)

**Their results** still fire under them in **@UNIQUE_g1** (own result cards).

---

## RESULT families (never choose lane alone)

| Family | Examples |
|--------|----------|
| Plain outcome | `🔵…` banner + `✅ GANHOU` / `❌ PERDEU`, `G0 WIN`, `blue win on G0` |
| Short skin | `✅ WIN — SOLO_ELITE`, `🏆 G1 — Recuperado` |
| Forensic | `RESUMIDO FORENSE` + `⏱ Intervalo` |
| Ops / expire | `G1 EXPIROU`, `G2 MISS — PERDA TOTAL` |

Ops results still glue under the parent fire’s chat.

---

## Implementation

- `bot/dual_lane_router.py` — role → lane; persist fire lane by signal id  
- `bot/telegram_outbox.py` — no default mirror; results use persisted parent lane  
- Env: `TELEGRAM_TARGET_PEER`, `TELEGRAM_COUNTDOWN_PEER=UNIQUE_g1`

---

## Honest foresight note

Seeing a result card with `Intervalo: 15s` (or a very early resolve) means the system **reported** how long fire→resolve took. It does **not** mean the casino already knew every intermediate round as future fact. Early glue + room capture latency ≠ omniscient round oracle.
