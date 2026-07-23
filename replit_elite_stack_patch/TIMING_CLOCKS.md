# Three clocks (do not collapse them)

People say “janela / window / intervalo / timing” for **different machines**. Mixing them breaks routing and profit.

## CLOCK A — ENTRY WINDOW (bet placement urgency)

**On the FIRE.** Answers: *how long do I have to PUT the bet down?*

Examples: `JANELA: 1s para apostar`, `🟢 1s 🟢`, `11s`, `17s`, classic CD_FIRE countdown-to-enter skins.

- **Yes — `🟢 1s 🟢` ≈ “you have 1s to bet,” not “the hit arrives in 1s.”**
- This is **not** “when the casino result will land as a future fact.”
- This is **urgency to enter** (flash / retained→released / seconds left to click).
- Important, but **not** the catalog start axis — see `COUNTDOWN_START_AXIS.md` (WITH_TIMING vs NO_TIMING on every fire+result).

## CLOCK B — HIT / COLOR-COMING ETA (optional, rare, predictive)

**On the FIRE (if present).** Answers: *when is this color expected to hit / which round window?*

Different sense from Clock A: A = “enter by T”; B = “outcome expected around T / next G0.”  
If a template only has ENTER NOW with no A and no B → money/coalition style fire.

## CLOCK C — RESOLVE INTERVAL (forensic reporting)

**On the RESULT.** Answers: *how long did fire→resolved actually take?*

Example: `⏱ Intervalo: 31.3s` / `16.6s` on RESUMIDO FORENSE.

- **Never** a reason to call the card a countdown fire.
- **Never** the same thing as Clock A’s `JANELA: 1s`.
- Clock C can be 132s after a fire that had Clock A = 1s. Both can be true: you had 1s to enter; the round resolved 132s after fire timestamp.

## One-line test

| Text | Clock |
|------|-------|
| “I must click bet in Ns” | **A** |
| “Color expected / hit window” | **B** |
| “This signal took Ns to resolve” | **C** |

Lane split uses **Clock A (and CD_FIRE kinds)** on FIRE only — not Clock C on results.
