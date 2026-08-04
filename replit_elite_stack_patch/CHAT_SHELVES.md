# Chat shelves — skin/floor building → Telegram chats

**Not DB-kinds-only.** Shelves place every product skin (ENTER NOW, countdown peak fires, forensic G0/G1/G2, gale, expire ops). SOLO/GOLDEN/SEQUENCE/PLATINUM/FLASH are only part of the building.

Module: `bot/config/chat_shelves.py` · Replit: `bot/chat_shelves.py`  
Resolver: `resolve_shelf(text)` → shelf + peer + lane  
Wired into: `hub_engine_route`, `dual_lane_router.classify_card`, `telegram_outbox`

---

## Shelves

| Shelf | Band | What goes here | Default peer |
|---|---|---|---|
| `SHELF_PENTHOUSE_MONEY` | PENTHOUSE | SOLO ELITE ENTER / APOSTAR | `TELEGRAM_TARGET_PEER` (Mr_iv4) |
| `SHELF_UPPER_MONEY` | UPPER | GOLDEN / SEQUENCE / PLATINUM ENTER NOW, compact `#` | money chat |
| `SHELF_COUNTDOWN` | UPPER_COUNTDOWN | **Sinal Retido→Liberado**, JANELA any-N, `CD_FIRE_*` | `@UNIQUE_g1` |
| `SHELF_SNIPER` | MID | FLASH / ULTRA_TIE / EMERGING / EMPATE DIRETO | Gunique (or sniper env) |
| `SHELF_GALE` | MID | `♻️ RETENTATIVA` / `🔁 Entre novamente` / PREPARE G1 | money (or gale env) |
| `SHELF_OPS_EXPIRE` | OPS | `G1 EXPIROU` / `G2 MISS` — **follow parent shelf** | parent |
| *(results)* | — | Forensic `RESUMIDO FORENSE`, `🔔 GANHOU/PERDEU`, short `✅ WIN — KIND` | **always parent fire chat** |
| `SHELF_OVERFLOW` | elastic | When any shelf > ~2–3/min | `TELEGRAM_SHELF_OVERFLOW` |
| `SHELF_VAULT` | CREATED_ONLY | Built but not live yet — **keep, never delete** | no peer until revived |
| `SHELF_SINK` | NOISE | Room relay / quarantine / gate dumps | suppress / sink |

---

## Why countdown + forensic matter

User-locked examples (Jun 28 Gunique history) prove systems beyond DB `signal_kind`:

| Template | Family | Shelf |
|---|---|---|
| `⏳ Sinal Retido → Liberado` + `JANELA: 1s` + `🟢 1s 🟢` | `FIRE_SINAL_RETIDO_LIBERADO` | COUNTDOWN |
| `🏆 GOLDEN SIGNAL — ENTER NOW` | `FIRE_GOLDEN_ENTER` | UPPER_MONEY |
| `🔍 RESUMIDO FORENSE` + `⏱ Intervalo` + G0 WIN/LOSS | `RESULT_FORENSIC_INTERVALO` | parent |
| `🔔 ✅ GANHOU` / `❌ PERDEU` | `RESULT_BELL_GANHOU` | parent |
| `✅ WIN — SOLO_ELITE` / `SEQUENCE` | `RESULT_WIN_TIER` | parent |
| `⏰ G1 EXPIROU — VERIFICAR SUA MESA` | `OPS_G1_EXPIROU` | parent / OPS |
| `🛑 G2 MISS — PERDA TOTAL` | `OPS_G2_MISS` | parent / OPS |

Many countdown / forensic skins **were among the best** and often **never reach Telegram** when a system is muted — they remain floors in the census (CREATED_ONLY / TG history), not discarded because DB only lists 7 kinds.

---

## Env (optional elastic peers)

```bash
export TELEGRAM_SHELF_PENTHOUSE=6774605259
export TELEGRAM_SHELF_UPPER=6774605259
export TELEGRAM_SHELF_COUNTDOWN=UNIQUE_g1
export TELEGRAM_SHELF_SNIPER=UNIQUE_g1
export TELEGRAM_SHELF_GALE=6774605259
export TELEGRAM_SHELF_OVERFLOW=   # add when rate demands
```

Unset → fall back to existing `TELEGRAM_TARGET_PEER` / `TELEGRAM_COUNTDOWN_PEER`.

---

## Rules

1. RESULT / forensic / expire **glue under parent fire’s shelf**  
2. Never drop a fire to protect a chat — **overflow**  
3. Skin gate may retire losers; vault keeps CREATED_ONLY  
4. Building rank (census) informs priority; shelf map places product
