# Dual-chat Telegram scan (Mr_iv4 + UNIQUE_g1)

## Why

Capacity must never **delay** a time-sensitive fire. Soft caps only spill to the next UNIQUE_gN chat.

Inventory completeness needs a **live Telethon pass** of both destination chats, then cross-compare every landed type against `bot.config.skin_families`.

## Already on disk (cloud)

Full archaeology catalog (2026-08-03):
- **537,166** messages · Mar 17 → Aug 3 · `coverage_complete_to_mar17: true`
- Peers resolved: `mr_iv4` + `UNIQUE_g1`
- **Caveat:** `types_first_seen` attributes duplicates to the chat of **first appearance**. Msg-count by first_chat ≈ `mr_iv4: 537139` / `UNIQUE_g1: 27`. That does **not** prove Gunique never received product cards — many Jun-28 G1 Unique pastes share type_ids that first fired on Mr_iv4.
- Cross-compare report: `bot/data/tg_cross_compare/TG_CROSS_COMPARE.md`

## Re-run on Replit (needed for true per-chat volume)

Script lives on the PR branch — not on Replit disk. Curl it:

Self-bootstrapping (curls archaeology + upload from GitHub — no local patch folder needed):

```bash
curl -fsSL -o /tmp/TG_DUAL.sh \
  'https://raw.githubusercontent.com/findmeatigorcarvalho-spec/bacbo/cursor/add-engine-gate-registry-d5ba/replit_elite_stack_patch/REPLIT_TG_DUAL_CHAT_SCAN.sh?v=20260804b'
bash /tmp/TG_DUAL.sh
```

Resume if it dies mid-scrape:

```bash
bash /tmp/TG_DUAL.sh --resume
```

Paste the printed `FETCH_URL=` back here. That zip must include:
- `all_messages.csv` (or `per_chat_counts.json`)
- `types_first_seen.csv`
- `cross_compare/TG_CROSS_COMPARE.md`

## Router rule (locked)

Never delay. Soft-cap → UNIQUE_g2…g5 → mint UNIQUE_g6+ → send **now**.
