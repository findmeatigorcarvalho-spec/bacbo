# Profit Skyscraper OS

Autonomous distribution + kid-simple play layer over the full Telegram skin/gate inventory.

## What it is

1. **Understands the whole product** — 827 museum templates → KEEP 777 / TRASH 50, plus 120 registry skins and live floors (JUN10, ELITE_V2, …).
2. **Blocks trash** — UI crumbs, shell pastes, agent meta never go live (`TELEGRAM_TRASH_BLOCK=1`).
3. **Money penthouse = Mr_iv4** — ENTER / gale / most results (`HUB_MONEY_FIRST=1`).
4. **Countdown = UNIQUE_g1** — JANELA / Sinal Retido / sniper clocks.
5. **Never delay** — soft-cap only spills to UNIQUE_g2…gN (mint as needed).
6. **User playbook** — six rules, minimum stake, every chat usable even at 5 signals/day.

## Apply on Replit

```bash
curl -fsSL -o /tmp/SKY.sh \
  'https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/cursor/add-engine-gate-registry-d5ba/replit_elite_stack_patch/REPLIT_PROFIT_SKYSCRAPER.sh?v=20260806a'
bash /tmp/SKY.sh
```

Then pin the texts from `bot/data/chat_playbook_cards.json` in each chat.

## Key files

| File | Role |
|---|---|
| `bot/config/profit_skyscraper.py` | Chat map + play rules + money-first |
| `bot/config/keep_allowlist.py` | KEEP/TRASH live gate |
| `bot/config/skin_gate.py` | Registry retire + trash block |
| `bot/config/chat_router.py` | Soft-cap spill, never delay |
| `bot/hub_engine_route.py` | Engine send → Mr_iv4 / g1 / spill |
| `bot/telegram_outbox.py` | Outbox spill resolve |
| `bot/data/CHAT_PROFIT_PLAYBOOK.md` | Human playbook |
| `bot/data/profit_skyscraper_brain.json` | Full system map |

## User rules (every chat)

1. ENTER + color → bet **minimum** on that color  
2. Timer / JANELA → bet before 0  
3. GALE → same color, minimum again  
4. WIN → stop that round  
5. DO NOT BET / EXPIRED → skip  
6. Never invent bets  

### Round sync densifier
- Target **1 signal/round/chat** (min 1 per 2)
- Prep invest up to **400s** → release at **TTB≈10s**
- RESULT aligned to **interval start**
- See `ROUND_SYNC_DENSIFIER.md`

Honesty: the OS maximizes capture of real windows at min stake. Dollar totals depend on platform volume/WR — not a guarantee.
