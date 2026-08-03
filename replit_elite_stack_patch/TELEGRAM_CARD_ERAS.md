# Telegram card eras (from G1 Unique / Mr_iv4 chat — user scroll)

Source of truth = chat text, not DB `window_secs`.

## Era 0 — ONLINE only
**2026-03-17 ~08:37 UTC → 2026-03-19 ~17:44 UTC**

Only one **role**: `ONLINE` (bot restart / status banner).

Variants of the *same* type (not new roles):
- rooms monitored: 6 → 4
- thresholds: SOLO≥2.0 / GOLDEN≥3.0 → SOLO≥0.9 / GOLDEN≥2.5

No FIRE. No RESULT. No room relays yet in this window.

## Era 1 — two pipes appear (after 19 Mar ~17:44 ONLINE)
Starting ~17:46 same day, chat shows **two different roles**:

### A) ROOM RELAY / “news” (`📡 @RoomHandle — timestamp`)
Bot **forwards** tip-room chatter. Not an ENTER NOW fire.

Examples from chat:
- invite / promo spam
- `🚨 ANALISANDO 🚨`
- `🔁 Estamos no 1° gale` / `2° gale`
- `MÃO PESADA`
- `🔰 HORÁRIOS EMPATES`

Same role, many **news subtypes** (analisando, gale, promo, empates…).

### B) BOT FIRE — ENTER NOW (money-style, no result-ETA countdown on card)
Bot’s **own** signal card. Examples:

| Fire subtype | Header in chat |
|--------------|----------------|
| Coalition / confirmed | `🏆 SIGNAL CONFIRMED — ENTER NOW` |
| Solo | `💎 SOLO ELITE SIGNAL` |

Both say `⚡ ENTER NOW` and `_After result: /win · /loss · /tie_` — early era = **manual result**, not auto result card yet.

## Roles checklist (growing as we scroll)
| Role | Era start | Has result card? |
|------|-----------|------------------|
| ONLINE | Mar 17 | No |
| ROOM_RELAY (news) | Mar 19 ~17:46 | No (room’s own gale lines ≠ bot RESULT) |
| FIRE_ENTER_NOW | Mar 19 ~17:51 | Later — early cards ask /win /loss /tie |
| FIRE_* (other skins) | TBD scroll | TBD |
| RESULT_* | TBD scroll | — |
| UPDATE/OPS | TBD scroll | — |

## Not countdown-to-result
ENTER NOW cards in this era have **no** “Ns until result” factual countdown.
Do not classify 1s/11s/17s as the definition of countdown; real countdown-to-result = any Ns when that skin appears later.
