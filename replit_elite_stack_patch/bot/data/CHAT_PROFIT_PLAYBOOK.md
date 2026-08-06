# Profit Skyscraper — how to use every chat (simple)

Built from the full museum (827 templates) → **KEEP 777 / TRASH 50**, plus 120 registry skins and live floors/gates.

## The building

| Chat | Job | What you do |
|---|---|---|
| **Mr_iv4** | Money penthouse (most profit) | ENTER + color → min bet; gale → same color min; WIN/LOSS ends round |
| **UNIQUE_g1** | Countdown / sniper | Bet before the timer hits 0 |
| **UNIQUE_g2…gN** | Overflow when busy | Same rules — never wait for a free slot |

## Universal rules (even a 12-year-old)

### 1. When: ENTER NOW / APOSTE AGORA / ENTRE AGORA + color (🔴/🔵)
- **Do:** Bet the MINIMUM on that color NOW.
- **Stop:** Wait for WIN / LOSS / gale card for this signal.

### 2. When: JANELA / 🟢 Ns 🟢 / Sinal Retido→Liberado
- **Do:** Same: minimum bet on the color before the seconds hit 0.
- **Stop:** If it says RODADA JÁ PASSOU / DO NOT BET — skip.

### 3. When: GALE / RETENTATIVA / Entre novamente / AGUARDANDO G1
- **Do:** Same color, MINIMUM bet again (G1). Then G2 only if the card says so.
- **Stop:** Never invent G3+ unless the chat posts it.

### 4. When: ✅ WIN / GREEN / GANHOU
- **Do:** Round over. Bank the win. Wait for next ENTER.
- **Stop:** Do not re-bet the same round.

### 5. When: ❌ LOSS / PERDEU + no gale card
- **Do:** Round over. Next signal only.
- **Stop:** Do not chase with your own gales.

### 6. When: DO NOT BET / NÃO APOSTE / RODADA PASSOU / EXPIROU / G2 MISS
- **Do:** Skip. Zero bet.
- **Stop:** This protects the bankroll.

### 7. When: OPS only (quarantine, schedule, grounded, hot/cold)
- **Do:** Read. Do not bet from ops alone.
- **Stop:** Bet only from ENTER / JANELA / GALE cards.

## Stake policy

- Mode: `MINIMUM_ALWAYS`
- Always the platform minimum unit. Volume of correct windows > size of bet.
- Gale: G0 = 1u, G1 = 1u (same min), G2 = 1u only if card says enter G2.
- Never: Never raise stake to 'recover'. Never bet without a card.
- Worst chat (5 signals/day): Even if a chat only posts 5 ENTER days: play all 5 with min stake + official gales. Skip DO-NOT-BET. That chat is still fully used.

## What the system does (autonomous)

1. Blocks TRASH (shell pastes, agent meta, UI crumbs).
2. Sends KEEP fires: money → Mr_iv4, countdown → UNIQUE_g1.
3. Soft-cap → spill to UNIQUE_gN **immediately** (never delay a bet window).
4. Results glue to the exact chat of the parent fire.
5. Peak floors (JUN10, ELITE_V2, …) stay as gates; their skins ride the shelves.

## Inventory snapshot

- Museum templates: 827
- KEEP: 777 · TRASH: 50
- Registry skins: 120 → {'ONLINE': 2, 'FIRE': 43, 'OPS': 44, 'RESULT': 28, 'ROOM_RELAY': 1, 'UNKNOWN': 2}
- Live floors: JUN10, AITEST_ULTIMATE, AITEST_APR20_MAX, MAY01, APR20, LIVE, JUN20, APR27, ELITE_V2, ULTIMATE, AITEST_LIVE, APR22, APR26, JUN19, APR20_MAX, JUN26, MAY19, MAY10, MAR21, JUN27, APR29, ELITE_V2_PEAK, MAR19, MAY11, MAR20, AITEST_MAR21, JUN08, APR30, APR28, AITEST_APR20, MAY04, APR19

## Pin these cards in each chat

### Mr_iv4
```
🏛 Mr_iv4 — MONEY PENTHOUSE
This is the main profit chat.

Focus: Most ENTER NOW / gale / WIN-LOSS land here.

HOW TO MAKE MONEY HERE (simple):
1) See ENTER + color → bet MINIMUM on that color.
2) See timer / JANELA → bet BEFORE 0.
3) See GALE / again → same color, MINIMUM again.
4) See WIN → stop that round.
5) See DO NOT BET / EXPIRED → skip.
6) Never invent your own bets.

One card = one job. Follow the card. Minimum stake. Every signal.
```

### UNIQUE_g1
```
⏱ UNIQUE_g1 — COUNTDOWN / SNIPER
Fast clocks. Bet in the seconds shown.

Focus: JANELA / Sinal Retido / FLASH live here.

HOW TO MAKE MONEY HERE (simple):
1) See ENTER + color → bet MINIMUM on that color.
2) See timer / JANELA → bet BEFORE 0.
3) See GALE / again → same color, MINIMUM again.
4) See WIN → stop that round.
5) See DO NOT BET / EXPIRED → skip.
6) Never invent your own bets.

One card = one job. Follow the card. Minimum stake. Every signal.
```

### UNIQUE_gN
```
📤 UNIQUE_gN — OVERFLOW
Same game as the main chats — just less crowded.

Focus: If you see ENTER here, treat it like Mr_iv4 / g1.

HOW TO MAKE MONEY HERE (simple):
1) See ENTER + color → bet MINIMUM on that color.
2) See timer / JANELA → bet BEFORE 0.
3) See GALE / again → same color, MINIMUM again.
4) See WIN → stop that round.
5) See DO NOT BET / EXPIRED → skip.
6) Never invent your own bets.

One card = one job. Follow the card. Minimum stake. Every signal.
```

## Machine files

- `keep_allowlist.json` — live trash block list
- `profit_skyscraper_brain.json` — full system map
- `chat_playbook_cards.json` — pin texts
- Regenerator: `python3 bot/build_profit_skyscraper_brain.py`

