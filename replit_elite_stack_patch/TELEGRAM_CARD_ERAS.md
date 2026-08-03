# Telegram card eras (from G1 Unique / Mr_iv4 chat — user scroll)

Source of truth = chat text, not DB `window_secs`.

## Era 0 — ONLINE only
**2026-03-17 ~08:37 UTC → 2026-03-19 ~17:44 UTC**

Only one **role**: `ONLINE` (bot restart / status banner).

Variants of the *same* type (not new roles):
- rooms monitored: 6 → 4
- thresholds: SOLO≥2.0 / GOLDEN≥3.0 → SOLO≥0.9 / GOLDEN≥2.5

No FIRE. No RESULT. No room relays yet in this window.

## Era 1 — room news + ENTER NOW fires, **NO bot RESULT cards yet**
**From ~19 Mar 17:46 → before ~19:52**

### A) ROOM_RELAY / “news” (`📡 @RoomHandle — …`)
Forwarded tip-room lines. **Not** a bot FIRE. **Not** a bot RESULT.
Subtypes seen: promo/invite, ANALISANDO, gale 1°/2°, MÃO PESADA, HORÁRIOS EMPATES,
and later `✅ AUTO WIN @Room — …` / `🤑✅ GREEN` (still room relay, not bot result skin).

### B) FIRE subtypes (bot ENTER NOW) — **no auto RESULT under them yet**
Footer: `_After result: /win · /loss · /tie_` = **manual** — these fires **do not** get a
bot RESULT card type in this window. That is intentional for the catalog: FIRE without RESULT type.

| First seen (chat) | Header | Notes |
|-------------------|--------|-------|
| 19 Mar **17:51:34** | `🏆 SIGNAL CONFIRMED — ENTER NOW` | First bot FIRE (2-room) |
| 19 Mar **17:55:33** | `💎 SOLO ELITE SIGNAL` | **First SOLO** in chat (matches user) |
| 19 Mar **18:25:17** | `💎 SOLO ELITE SIGNAL` | Solo again (history ✅) |
| 19 Mar **19:52:03** | `🏆 GOLDEN SIGNAL — ENTER NOW` | **New FIRE type** (≠ SIGNAL CONFIRMED) |

## Era 2 — GOLDEN + first **bot RESULT** cards (~19 Mar 19:52)
Same minute as first GOLDEN FIRE:

| Type | Example | Role |
|------|---------|------|
| FIRE | `🏆 GOLDEN SIGNAL — ENTER NOW` | Bot fire |
| ROOM_RELAY | `✅ AUTO WIN @CoringaDados` + GREEN | Room news (not bot result skin) |
| RESULT | `✅ WIN — SOLO_ELITE` + `G0 — Acertou de primeira!` + daily stats | **First bot RESULT type** |

So: early SIGNAL CONFIRMED / SOLO fires can exist **without** a RESULT type;
RESULT types appear as a **later** invention in the chat.

## Era 3 — GALE retentativa FIRE + EMPATE RESULT (~19 Mar 20:48)
After GOLDEN/WIN exist. New skins (not the same as plain SOLO G0 fire):

| First seen (chat) | Header / skin | Role | Notes |
|-------------------|---------------|------|-------|
| 19 Mar **20:48:58** | `♻️ GALE 1 — RETENTATIVA (1 room at G1)` + body `💎 SOLO ELITE SIGNAL` | **FIRE** | Gale-retry fire. Still has `_After result: /win · /loss · /tie_`. ≠ plain SOLO G0 ENTER NOW. |
| 19 Mar **20:50** | `🟡 EMPATE — SOLO_ELITE` + `Resultado empatado — proteção ativada!` + daily stats | **RESULT** | **First bot TIE/EMPATE result type** (≠ WIN, ≠ LOSS, ≠ room AUTO WIN). |

Plain `💎 SOLO ELITE SIGNAL` (no GALE RETENTATIVA header) stays its own FIRE type.
`♻️ GALE N — RETENTATIVA` is a **separate FIRE type** even when the body still says SOLO ELITE.

## Locked type list so far (chat-native)
1. ONLINE  
2. ROOM_RELAY (many subtypes)  
3. FIRE / SIGNAL_CONFIRMED_ENTER_NOW  
4. FIRE / SOLO_ELITE_SIGNAL  
5. FIRE / GOLDEN_SIGNAL_ENTER_NOW  
6. RESULT / WIN_SOLO_ELITE (G0 + daily stats)  
7. FIRE / GALE_1_RETENTATIVA_SOLO_ELITE  
8. RESULT / EMPATE_SOLO_ELITE  

Keep scrolling → add every **new header/skin** as a new type when it first appears.

## Automated full catalog (no manual scroll)
Run on Replit → `bash TG_UP.sh` → paste `FETCH_URL=` (agent downloads).

### Partial pull already fetched (2026-08-03)
`https://litter.catbox.moe/zt31g0.zip` → `tg_archaeology_partial_30k/CATALOG_SUMMARY.md`

- **30,300** msgs · **mr_iv4 only** · range **2026-07-01 → 2026-08-03** (Ctrl+C at 30k)
- **Not yet:** Mar 17 day-one · `@UNIQUE_g1`
- Core Jul+ skins confirmed: SOLO/GOLDEN/PLATINUM/SEQUENCE fires, WIN/LOSS/EMPATE results, GALE retentativa, CD quantum/timer, room ANALISANDO + AUTO WIN, forensic, G0/G1/G2 follow-ups

Resume scrape until dates ≤ Mar 17 and UNIQUE_g1 finishes, then upload again.

## Not countdown-to-result
These ENTER NOW cards have **no** factual “Ns until result” countdown on the fire.
Do not treat 1s/11s/17s as the definition of countdown.
