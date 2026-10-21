# TG archaeology partial — fetched from Replit via litterbox

**FETCH_URL:** `https://litter.catbox.moe/zt31g0.zip`  
**Scope:** `mr_iv4` only · **30,300 msgs** · **2026-07-01 13:10 → 2026-08-03 20:52 UTC**  
**Not included yet:** Mar 17 day-one history · `UNIQUE_g1` countdown peer (Ctrl+C at 30k)

`distinct_type_ids=4878` is inflated (RELAY_OTHER_*/UNKNOWN_*/`WIN — KIND #id` / JANELA every-Ns).  
Below = **real skins** after collapsing noise.

## Role mix (messages)
| role | n |
|------|--:|
| UNKNOWN | 8974 |
| ROOM_RELAY | 8660 |
| RESULT | 5117 |
| FIRE | 3164 |
| EMPTY | 2191 |
| OPS | 1543 |
| ONLINE | 651 |

## Core named skins (n≥5, noise filtered)

| n | role | type_id | note |
|--:|------|---------|------|
| 2804 | ROOM_RELAY | `RELAY_ANALISANDO` | room tip “analisando” |
| 1739 | FIRE | `FIRE_SOLO_ELITE_SIGNAL` | 💎 SOLO ELITE SIGNAL |
| 1497 | ROOM_RELAY | `RELAY_AUTO_WIN_GREEN` | ≠ bot RESULT |
| 649 | ONLINE | `ONLINE_BANNER` | UserBot ONLINE |
| 637 | RESULT | `RESULT_WIN_SOLO_ELITE` | ✅ WIN — SOLO_ELITE |
| 359 | FIRE | `CD_FIRE_QUANTUM_LOCK` | countdown/quantum |
| 331 | RESULT | `RESULT_BANNER_TIE_SEQUENCIA_EMPATES` | 🟡 SEQUÊNCIA DE EMPATES |
| 287 | FIRE | `FIRE_GOLDEN_SIGNAL_ENTER_NOW` | 🏆 GOLDEN SIGNAL — ENTER NOW |
| 284 | RESULT | `RESULT_WIN_SEQUENCE` | ✅ WIN — SEQUENCE |
| 275 | RESULT | `RESULT_BANNER_EMPATE_CRITICO` | 🔴 EMPATE CRÍTICO |
| 275 | FIRE | `CD_FIRE_TIMER_BRT_EDT_APOSTAR` | timed fire skin |
| 249 | RESULT | `RESULT_FORENSIC_INTERVALO` | RESUMIDO FORENSE |
| 207 | ROOM_RELAY | `RELAY_GALE_STATUS` | room gale lines |
| 195 | RESULT | `RESULT_LOSS_G0_FALHOU` | ❌ LOSS — G0 FALHOU |
| 144 | RESULT | `RESULT_GALE_G1_NAO_FOI` | 🟠 G1 NÃO FOI — G2 OPCIONAL |
| 142 | RESULT | `RESULT_WIN_GOLDEN` | ✅ WIN — GOLDEN |
| 114 | FIRE | `FIRE_PLATINUM` | PLATINUM SIGNAL |
| 111 | RESULT | `RESULT_GALE_G0_NAO_FOI` | ⚠️ G0 NÃO FOI — ENTRE NO G1 |
| 97 | FIRE | `FIRE_SEQUENCE` | SEQUENCE fire |
| 85 | RESULT | `RESULT_GALE_G2_PERDA_TOTAL` | 🛑 G2 NÃO FOI — PERDA TOTAL |
| 80 | ROOM_RELAY | `RELAY_HORARIOS_EMPATES` | |
| 70 | RESULT | `RESULT_LOSS_SOLO_ELITE` | ❌ LOSS — SOLO_ELITE |
| 57 | FIRE | `FIRE_GALE_1_RETENTATIVA_SOLO_ELITE` | ♻️ GALE 1 — RETENTATIVA |
| 54 | ROOM_RELAY | `RELAY_PROMO_INVITE` | |
| 42 | RESULT | `RESULT_EMPATE_SEQUENCE` | 🟡 EMPATE — SEQUENCE |
| 40 | RESULT | `RESULT_DO_NOT_BET_ROUND_PASSED` | ⛔ DO NOT BET |
| 38 | RESULT | `RESULT_BANNER_AVISO_EMPATE` | 🟡 AVISO DE EMPATE |
| 31 | RESULT | `RESULT_WIN_PLATINUM` | ✅ WIN — PLATINUM |
| 24 | RESULT | `RESULT_EMPATE_SOLO_ELITE` | 🟡 EMPATE — SOLO_ELITE |
| 23 | RESULT | `RESULT_LOSS_SEQUENCE` | ❌ LOSS — SEQUENCE |
| 23 | FIRE | `FIRE_GALE_1_RETENTATIVA_GOLDEN` | gale retry on GOLDEN |
| 16 | FIRE | `FIRE_JANELA_1S_SOLO_ELITE` | Clock A on fire (any Ns exists) |
| 12 | RESULT | `RESULT_LOSS_GOLDEN` | ❌ LOSS — GOLDEN |
| 8 | ROOM_RELAY | `RELAY_MAO_PESADA` | |

## Also present (manual Mar 19 locks — not in this Jul+ slice as “first”)
Day-one `SIGNAL CONFIRMED`, first SOLO/GOLDEN/WIN/EMPATE from **Mar 19** need the scrape to continue **past July back to Mar 17**. This dump’s “first=” dates are only oldest-in-slice.

## Next step
Resume scrape (don’t Ctrl+C until UNIQUE_g1 done + dates ≤ Mar 17), then:
```bash
bash TG_UP.sh
```
Paste new `FETCH_URL=`.
