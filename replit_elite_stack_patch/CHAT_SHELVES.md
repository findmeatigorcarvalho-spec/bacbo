# Chat shelves — skin/floor building → Telegram chats

**Not DB-kinds-only.** Shelves place every product skin (ENTER NOW, countdown peak fires, forensic G0/G1/G2, gale, expire ops). SOLO/GOLDEN/SEQUENCE/PLATINUM/FLASH are only part of the building.

Modules: `bot/config/chat_shelves.py` · `bot/config/chat_router.py`  
Replit shims: `bot/chat_shelves.py` · `bot/chat_router.py`

---

## Locked chat map

| Chat | Role |
|---|---|
| **Mr_iv4** (`6774605259`) | Money ENTER (SOLO/GOLDEN/SEQUENCE/PLATINUM), gale, ops primary |
| **UNIQUE_g1** | Countdown peak fires (`Sinal Retido→Liberado`, JANELA, `CD_FIRE_*`) + sniper |
| **UNIQUE_g2…gN** | Overflow — **as many as needed** (g2–g5 starters; auto-mints g6, g7, … up to 500). Never delay. |

Results (forensic G0/G1 WIN/LOSS, short `✅ WIN — KIND`, `G1 EXPIROU`, `G2 MISS`) **glue to the exact chat** that received the parent FIRE — including overflow.

---

## Never miss — never delay

Bet windows are seconds (JANELA / `🟢 Ns 🟢`). Soft cards/min caps only **move** a card to the next chat so chats stay readable — they must never make a fire wait.

1. Fire tries the **primary** shelf chat (Mr_iv4 or UNIQUE_g1).
2. Soft-cap hit → spill to **UNIQUE_g2**, then g3, g4, g5.
3. Those full too → **mint UNIQUE_g6, g7, …** and send **immediately** (`delayed_seconds=0`).

No queue-wait. No drop for capacity. Building more UNIQUE_gN chats *is* the strategy for never missing a window.

---

## Shelves

| Shelf | What goes here | Default peer |
|---|---|---|
| `SHELF_PENTHOUSE_MONEY` | SOLO ELITE ENTER / APOSTAR | Mr_iv4 |
| `SHELF_UPPER_MONEY` | GOLDEN / SEQUENCE / PLATINUM ENTER NOW | Mr_iv4 |
| `SHELF_COUNTDOWN` | **Sinal Retido→Liberado**, JANELA any-N, `CD_FIRE_*` | UNIQUE_g1 |
| `SHELF_SNIPER` | FLASH / ULTRA_TIE / EMERGING / EMPATE DIRETO | UNIQUE_g1 |
| `SHELF_GALE` | `♻️ RETENTATIVA` / `🔁 Entre novamente` / PREPARE G1 | Mr_iv4 |
| `SHELF_OPS_EXPIRE` | `G1 EXPIROU` / `G2 MISS` — prefer parent chat | parent / Mr_iv4 |
| *(results)* | Forensic `RESUMIDO FORENSE`, `🔔 GANHOU/PERDEU`, short `✅ WIN — KIND` | **parent fire chat** |
| `SHELF_OVERFLOW` | Elastic when any shelf is saturated | UNIQUE_g2…g5 |
| `SHELF_VAULT` | Built but not live yet — **keep, never delete** | no peer until revived |
| `SHELF_SINK` | Room relay / quarantine / gate dumps | suppress |

---

## Why countdown + forensic matter

These were among the best product cards and often **never reach Telegram** when a system is muted — they remain floors in the census, not discarded because DB only lists ~7 `signal_kind`s.

| Template | Family | Shelf |
|---|---|---|
| `⏳ Sinal Retido → Liberado` + `JANELA: Ns` | `FIRE_SINAL_RETIDO_LIBERADO` | COUNTDOWN → g1 |
| `🏆 GOLDEN SIGNAL — ENTER NOW` | `FIRE_GOLDEN_ENTER` | UPPER → Mr_iv4 |
| `🔍 RESUMIDO FORENSE` + G0/G1 WIN/LOSS | `RESULT_FORENSIC_INTERVALO` | parent |
| `🔔 ✅ GANHOU` / `❌ PERDEU` / `✅ G0 WIN` | `RESULT_BELL_GANHOU` | parent |
| `✅ WIN — SOLO_ELITE` / `SEQUENCE` | `RESULT_WIN_TIER` | parent |
| `⏰ G1 EXPIROU — VERIFICAR SUA MESA` | `OPS_G1_EXPIROU` | parent / OPS |
| `🛑 G2 MISS — PERDA TOTAL` | `OPS_G2_MISS` | parent / OPS |

---

## Completeness (honest)

We have a **large union** inventory (code + .bak + git + DB kinds + TG history + AST of live Replit formatters) → **113** named skin families. Your Jun-28 G1 Unique paste set classifies cleanly (Retido, GOLDEN ENTER, forensic G0/G1, short WIN tiers, G1 EXPIROU, G2 MISS).

We do **not** claim absolute 100% of every string fragment ever typed. ~¼ of mined scraps stay UNKNOWN (mostly truncated gate logs / separators). Muted systems that never hit Telegram still exist as floors in source/DB — “not firing” ≠ “not inventoried.”

---

## Env overrides (optional)

```bash
export TELEGRAM_SHELF_PENTHOUSE=6774605259   # Mr_iv4
export TELEGRAM_SHELF_UPPER=6774605259
export TELEGRAM_SHELF_COUNTDOWN=UNIQUE_g1
export TELEGRAM_SHELF_SNIPER=UNIQUE_g1
export TELEGRAM_SHELF_OVERFLOW_PEERS=UNIQUE_g2,UNIQUE_g3,UNIQUE_g4,UNIQUE_g5
# or TELEGRAM_SHELF_OVERFLOW_1=UNIQUE_g2 … _4=UNIQUE_g5
```

Unset overflow env → defaults to UNIQUE_g2…g5 automatically.

---

## Rules

1. RESULT / forensic / expire **glue under parent fire’s exact chat** (including overflow)
2. Never drop a fire because a chat is full — **overflow / mint UNIQUE_gN, never delay**
3. Skin gate may retire losers; vault keeps CREATED_ONLY
4. Building rank (census) informs priority; shelf map places product
