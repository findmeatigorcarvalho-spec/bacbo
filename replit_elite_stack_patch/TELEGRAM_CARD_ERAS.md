# Telegram Card Type Eras — Full Archaeology

Source: Telethon scrape of destination chat(s), **2026-03-17 → 2026-08-03**  
Catalog: `progress.json` total **537,166** messages · `coverage_complete_to_mar17: true`  
Oldest UTC: `2026-03-17 08:37:17` · Newest UTC: `2026-08-03 20:52:41`

Classifier role mix (approx): ROOM_RELAY ≫ UNKNOWN ≫ RESULT ≫ FIRE ≫ OPS ≫ ONLINE.  
Many `type_id` rows are over-fingerprinted (placar numbers, cycle summaries). Below is the **distilled bot card skin chronology** — distinct templates that matter for engine/gates/outbox.

Timestamps = **first seen in Telegram** (UTC). Counts = occurrences in the scrape window.

---

## Era 0 — Online / presence (from day one)

| First seen (UTC) | Skin | Example first line | n |
|---|---|---|---|
| 2026-03-17 08:37 | ONLINE banner | `🟢 BacBo Royal UserBot ONLINE 🟢` | 3533 |

---

## Era 1 — Classic ENTER NOW fires (Mar 19–20)

| First seen (UTC) | Skin | Example first line | n |
|---|---|---|---|
| 2026-03-19 21:51 | FIRE confirmed | `🏆 SIGNAL CONFIRMED — ENTER NOW 🏆` | 1 |
| 2026-03-19 21:55 | FIRE SOLO ELITE | `💎 SOLO ELITE SIGNAL 💎` | 11228 |
| 2026-03-19 22:57 | FIRE GOLDEN | `🏆 GOLDEN SIGNAL — ENTER NOW 🏆` | 1736 |
| 2026-03-20 00:45 | FIRE SEQUENCE | `📊 SEQUENCE SIGNAL — ENTER NOW 📊` | 2194 |
| 2026-03-20 21:29 | FIRE PLATINUM | `💠 PLATINUM SIGNAL — PAR DE OURO` | 185 |

**Distinct ENTER NOW / APOSTAR AGORA header variants found later in scrape: 9** (see Era 6).

---

## Era 1b — Results + gale follow-ups (Mar 19–20)

| First seen (UTC) | Skin | Example first line | n |
|---|---|---|---|
| 2026-03-19 22:58 | RESULT AUTO TIE banner | `⚪ AUTO TIE @…` | (many @ variants) |
| 2026-03-19 23:52 | RESULT WIN tier | `✅ WIN — SOLO_ELITE` | 10924+ |
| 2026-03-19 23:55 | RESULT LOSS tier | `❌ LOSS — GOLDEN` | (many) |
| 2026-03-19 23:55 | FIRE gale follow-up | `🔁 GALE 1 — Entre novamente` | 798 |
| 2026-03-20 00:21 | RESULT TIE / EMPATE | `🟡 EMPATE — SOLO_ELITE` | 447 |
| 2026-03-20 00:48 | FIRE gale retentativa | `♻️ GALE 1 — RETENTATIVA` | 798 |
| 2026-03-20 00:50 | RESULT EMPATE SEQUENCE | `🟡 EMPATE — SEQUENCE` | 166 |
| 2026-03-20 10:17 | RESULT GREEN legacy | `✅✅✅ GREEN — VITÓRIA NO G0!` | 6 |
| 2026-03-20 10:18 | RESULT GREEN G1 | `♻️♻️♻️ GREEN — RECUPERADO NO G1!` | 2 |

Confirmed distinct (user-required): **`♻️ GALE 1 — RETENTATIVA`** and **`🟡 EMPATE — SOLO_ELITE`**.

---

## Era 2 — Ops / pre-alerts / specials (Mar 20–31)

| First seen (UTC) | Skin | Example first line |
|---|---|---|
| 2026-03-20 00:34 | OPS cooldown | `⚠️ LOSS COOLDOWN ACTIVATED` |
| 2026-03-20 20:25 | PREALERT forming | `⚡ SINAL SE FORMANDO ⚡` |
| 2026-03-20 22:43 | OPS duplo elite | `🔮 DUPLO ELITE ANALISANDO` |
| 2026-03-21 15:45 | TIMED JANELA (any N) | `⛔ JANELA FECHADA — NÃO ENTRE…` |
| 2026-03-22 00:06 | FIRE ULTRA TIE | `🟡 ULTRA TIE — EMPATE CONFIRMADO` |
| 2026-03-31 14:23 | OPS triple lock | `🔐🔐🔐 TRIPLE LOCK CHEGANDO` |

**Timed / countdown rule:** JANELA and `~Ns window` skins are **variable-N** (1s…40s+), not only 1/11/17. Classifier also emitted many `FIRE_JANELA_*S_*` fingerprints; treat as one family with N clock.

---

## Era 3 — Hot/cold + timed result clocks (Apr 29–May)

| First seen (UTC) | Skin | Example first line |
|---|---|---|
| 2026-04-29 22:48 | OPS sequência quente | `🔥🔥🔥 SEQUÊNCIA QUENTE` |
| 2026-04-29 22:49 | OPS sequência fria | `🧊🧊🧊 SEQUÊNCIA FRIA — PAUSAR` |
| 2026-04-29 22:49 | OPS sequência empates | `🟡🟡🟡 SEQUÊNCIA DE EMPATES` |
| 2026-04-30 00:02 | RESULT timed window | `🕐 HH:MM:SS EDT · … · ~Ns window` |
| 2026-04-30 18:25 | PREALERT 3-bolt | `⚡⚡⚡ SINAL FORMANDO` |
| 2026-05-01 14:13 | FIRE EMPATE DIRETO G0 | `🎯🟡 EMPATE DIRETO — G0` |
| 2026-05-01 14:17 | OPS AUDIT 360 | `📊 AUDIT 360° (DB only)` |
| 2026-05-01 14:18 | FIRE G0 DIRETO | `⚡ G0 DIRETO — Entre com confiança` |
| 2026-05-01 14:18 | FIRE PREPARE G1 | `♟ PREPARE O G1 — Provável…` |
| 2026-05-05 01:48 | STREAK banner | `🎰 SEQUÊNCIA Nx 🔴 VERMELHO` / azul variants |
| 2026-05-07 03:00 | CAMADAS DO DIA | `🏆 CAMADAS DO DIA — DD/MM/YYYY` |

---

## Era 4 — FLASH + compact GREEN (May)

| First seen (UTC) | Skin | Example first line | n |
|---|---|---|---|
| 2026-05-09 16:13 | RESULT FLASH WIN | `✅ WIN — FLASH` | 6 |
| 2026-05-11 17:23 | RESULT GREEN compact G0 | `✅ GREEN · G0 · HH:MM BRT` | 11 |
| 2026-05-11 17:24 | RESULT GREEN compact G1 | `♻️ GREEN · G1 · HH:MM BRT` | 2 |

DB also has FIRE kind **FLASH** / **EMERGING**. Telegram first-line for **EMERGING** was **not** found as a distinct ENTER header in this catalog pass. FLASH as FIRE header appears later (Era 6).

---

## Era 5 — Compact hash signals (Jul 5)

| First seen (UTC) | Skin | Example first line |
|---|---|---|
| 2026-07-05 16:50 | COMPACT SIGNAL # | `🔵 SIGNAL #51250 -- SOLO_ELITE red \| rooms: @…` |
| 2026-07-05 16:56 | COMPACT LOSS # | `❌ LOSS #51250 G0` |
| 2026-07-05 17:16 | COMPACT WIN # | `✅ WIN #51252 G0` |
| 2026-07-05 17:48 | COMPACT TIE # | `➖ TIE #51257 G0` |

Later variants include `[MAR19]`, `[MAY10]`, `[ELITE_V2]`, `[LIVE]`, `[ULTIMATE]`, `[JUN12A/B]` tags on the SIGNAL line.

---

## Era 6 — APOSTAR AGORA / luxury outbox (Jul 11–28)

| First seen (UTC) | Skin | Example first line | n |
|---|---|---|---|
| 2026-07-11 23:40 | FIRE SOLO APOSTAR | `⚡ SOLO ELITE — APOSTAR AGORA` | 82 |
| 2026-07-11 23:49 | FIRE SEQUENCE APOSTAR | `⚡ SEQUENCE — APOSTAR AGORA` | 739 |
| 2026-07-15 13:35 | FIRE GOLDEN APOSTAR | `⚡ GOLDEN — APOSTAR AGORA` | 31 |
| 2026-07-17 02:24 | FIRE PLATINUM APOSTAR | `⚡ PLATINUM — APOSTAR AGORA` | 60 |
| 2026-07-17 06:00 | FIRE FLASH APOSTAR | `⚡ FLASH — APOSTAR AGORA` | 2 |
| 2026-07-21 01:41+ | ONLINE luxury outbox | `LUXURY OUTBOX ONLINE` (+ MONEY / TIMED / GUNIQUE lanes) | |
| 2026-07-28 23:10 | FIRE SEQUÊNCIA ENTER NOW | `🔥 SEQUência — ENTER NOW 🔥` | 4 |

Also in late July: `⚡ ELITE ANALISANDO`, `🟠 DIVERGÊNCIA DE SALAS`, BacBo Royal hour pins, museum/chrono historical packs.

---

## DB vs Telegram (bridge)

Locked SQLite census (outbound `signals` / `results`) still holds:

- FIRE kinds: `SOLO_ELITE`, `SEQUENCE`, `GOLDEN`, `PLATINUM`, `FLASH`, `EMERGING`, `ULTRA_TIE`
- RESULT: win / loss / tie × gale G0–G3

Telegram shows **many more skins** than those 7 kinds (gale retentativa, EMPATE banners, JANELA clocks, GREEN legacy, APOSTAR AGORA, compact `#`, luxury ONLINE, room relays, audits). Engine gates should key off **Telegram skin families**, not only `signal_kind`.

---

## Stable gate keys (engine registry)

Canonical module: `bot/config/skin_families.py`  
Classifier: `classify_telegram_skin(text)` → `SkinMatch.gate_keys`  
Registry check: `EngineGateRegistry.is_telegram_skin_blocked(text)`

| Family id | Role | Notes |
|---|---|---|
| `ONLINE_BANNER` | ONLINE | Era 0 |
| `FIRE_CONFIRMED_ENTER` | FIRE | Era 1 |
| `FIRE_SOLO_ELITE_ENTER` | FIRE | Era 1 |
| `FIRE_GOLDEN_ENTER` | FIRE | Era 1 |
| `FIRE_SEQUENCE_ENTER` | FIRE | Era 1 |
| `FIRE_PLATINUM_ENTER` | FIRE | Era 1 |
| `RESULT_WIN_TIER` / `RESULT_LOSS_TIER` | RESULT | kind-scoped (`:SOLO_ELITE` …) |
| `FIRE_GALE_ENTRE_NOVAMENTE` | FIRE | ≠ retentativa |
| `RESULT_EMPATE` | RESULT | keep `RESULT_EMPATE:SOLO_ELITE` distinct |
| `FIRE_GALE_RETENTATIVA` | FIRE | ≠ entre novamente |
| `FIRE_JANELA_TIMED` | FIRE | **variable-N** COUNTDOWN family |
| `FIRE_ULTRA_TIE` | FIRE | Era 2 |
| `RESULT_TIMED_WINDOW` | RESULT | variable-N resolve clock |
| `FIRE_EMPATE_DIRETO_G0` / `FIRE_G0_DIRETO` / `FIRE_PREPARE_G1` | FIRE | Era 3 |
| `FIRE_COMPACT_HASH` + `RESULT_COMPACT_*_HASH` | FIRE/RESULT | Era 5 `#` |
| `FIRE_*_APOSTAR` | FIRE | Era 6 APOSTAR AGORA (≠ ENTER NOW) |
| `ONLINE_LUXURY_OUTBOX` | ONLINE | Era 6 |
| `FIRE_SEQUENCIA_ENTER_NOW` | FIRE | Era 6 |

Disable/retire either the family (`FIRE_GALE_RETENTATIVA`) or a kind-scoped key (`RESULT_EMPATE:SOLO_ELITE`).

---

## Noise classes (high volume — not primary skins)

- `ROOM_RELAY` placar / acertividade / @room scoreboards  
- `CYCLE OPEN/CLOSE/SUMMARY @room`  
- `HEALTH MONITOR`, `DEAD ROOMS`, `DEEP SYSTEM AUDIT`, gate net-negative dumps  
- `EMPTY` / media / human chat relays  

These dominate message count; they are operational/relay, not the ENTER→RESULT product cards.

---

## How this catalog was produced

1. Replit: `bash replit_elite_stack_patch/REPLIT_TELEGRAM_TYPE_ARCHAEOLOGY.sh` (resume until Mar 17)  
2. Replit: `bash replit_elite_stack_patch/REPLIT_TG_ARCH_UPLOAD.sh` → `FETCH_URL=`  
3. Cloud agent downloads catalog zip (report + `types_first_seen.csv` + eras auto); full `all_messages.csv` stays on Replit disk (too large for hosts).

Resume / recover helpers: `REPLIT_TG_ARCH_RECOVER.sh`, archaeology `--resume` / `--diag`.
