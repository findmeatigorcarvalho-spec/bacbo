# FIRE ↔ RESULT Law (locked)

Yes — exactly this:

1. **Every signal that has / will have a RESULT attached MUST FIRE.**
2. **Every FIRE that goes out MUST get a RESULT card template/skin** glued under it in the **same chat**, **immediately**.

No orphan RESULT. No silent FIRE. Inseparable pair.

## Env (forced)

```
FIRE_RESULT_LAW=1
RESULT_ATTACH_IMMEDIATE=1
HUB_OUTBOX_RESULT_CARDS=1
ROUND_SYNC_RESULT_ALIGN=0
```

## Wiring

| Layer | Behavior |
|---|---|
| `bot/config/fire_result_law.py` | Law helpers + overrides |
| `telegram_outbox.py` | Never skip RESULT card skins when law ON; force-fire result-paired soft-skips |
| `lux_send_config_bind.py` | Engine path: result-paired HOLD_PREP/DEDUP → FIRE_NOW |
| `round_sync_densifier.py` | RESULT always `RESULT_NOW` under parent FIRE |
| `hub_engine_route.py` | RESULT → last FIRE chat (same peer) |
| `profit_skyscraper.env` / `hub_max_boot` | Force the env keys above |

## Verify on Replit

```bash
curl -fsSL -o /tmp/SKY.sh \
  'https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/cursor/add-engine-gate-registry-d5ba/replit_elite_stack_patch/REPLIT_PROFIT_SKYSCRAPER.sh?v=20260807d'
bash /tmp/SKY.sh

# Confirm outbox + law
pgrep -af 'runtime_supervisor|telegram_outbox|bacbo_royal'
grep -E 'FIRE_RESULT_LAW|HUB_OUTBOX_RESULT|RESULT_ATTACH' bot/data/profit_skyscraper.env
tail -n 80 logs/telegram_outbox.log | grep -E 'RESULT|FIRE↔RESULT|sent signal|sent result'
```

Watch UNIQUE_g1: each ENTER/FIRE should be followed by the RESULT card template under it.
