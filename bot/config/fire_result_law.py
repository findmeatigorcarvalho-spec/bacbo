"""FIRE ↔ RESULT law (locked) — part of EMANATION LAWS.

Hard product law — no exceptions when FIRE_RESULT_LAW=1 (default ON):

  1) Every signal that has / will have a RESULT attached MUST FIRE.
     (No soft-skip of result-paired ENTER/FIRE. Latent KEEP FIRE with
      comprovation DNA must go live.)

  2) Every FIRE that goes out MUST get a RESULT card template/skin
     glued under it in the same chat when the round resolves.
     The seconds printed on the FIRE card ARE the time until that
     outcome materializes (15s on the card = 15s to RESULT). Do not
     HOLD the FIRE until a 12s/30s packing remainder.

Env:
  FIRE_RESULT_LAW=1              (default on)
  PRINTED_SECS_ARE_OUTCOME=1     (printed N is the outcome timer)
  RESULT_ATTACH_IMMEDIATE=1      (once the round resolves, glue RESULT now)
  HUB_OUTBOX_RESULT_CARDS=1      (outbox guarantees RESULT template skin)
  EMANATION_LAWS=1               (factual color + hermetic + vertical bundle)
"""
from __future__ import annotations

import os
import re
from typing import Any, Optional


def law_enabled() -> bool:
    return os.environ.get("FIRE_RESULT_LAW", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def result_skin_required() -> bool:
    """Every fired signal must receive a RESULT card template/skin."""
    if not law_enabled():
        return os.environ.get("RESULT_ATTACH_IMMEDIATE", "1").strip().lower() not in {
            "0",
            "false",
            "no",
            "off",
        }
    return True


def outbox_must_emit_result_cards() -> bool:
    """When law is on, outbox never skips RESULT skins (engine may also send)."""
    if law_enabled():
        return True
    raw = os.environ.get("HUB_OUTBOX_RESULT_CARDS")
    if raw is None:
        return True
    return raw.strip().lower() not in {"0", "false", "no", "off"}


_RESULT_PAIR_HINT = re.compile(
    r"(GREEN|RED\s*❌|WIN|LOSS|TIE|RESULT|PLACAR|GALE|G\d|"
    r"SAIU|APOSTOU|COMPROV|✅|❌|🟡|"
    r"ENTRADA\s*FINALIZADA|RESULTADO)",
    re.I,
)
_FIRE_HINT = re.compile(
    r"(ENTRADA|SINAL|APOSTE|ENTRAR|FIRE|ENTER|JANELA|RETIDO|"
    r"COUNTDOWN|🟢|🔵|🔴)",
    re.I,
)


def text_has_result_dna(text: str | None) -> bool:
    """True when text / skin is result-paired or is itself a RESULT card."""
    u = str(text or "")
    if not u.strip():
        return False
    return bool(_RESULT_PAIR_HINT.search(u))


def text_is_fire(text: str | None) -> bool:
    u = str(text or "")
    if not u.strip():
        return False
    if text_has_result_dna(u) and not _FIRE_HINT.search(u):
        return False
    return bool(_FIRE_HINT.search(u))


def must_fire_result_paired(
    text: str | None = None,
    *,
    signal_kind: str | None = None,
    has_result_row: bool = False,
    outcome: Any = None,
) -> bool:
    """Law §1 — if RESULT is/will be attached, this signal must FIRE."""
    if not law_enabled():
        return False
    if has_result_row or outcome not in (None, "", 0):
        return True
    kind = str(signal_kind or "").upper()
    if kind in {"RESULT", "WIN", "LOSS", "TIE", "GALE", "GREEN", "RED"}:
        return True
    if text_has_result_dna(text) and text_is_fire(text):
        return True
    return False


def decide_fire_override(
    action: str,
    text: str | None = None,
    *,
    signal_kind: str | None = None,
    has_result_row: bool = False,
    outcome: Any = None,
) -> Optional[str]:
    """If law requires fire, convert soft skips into FIRE_NOW.

    Never overrides TOO_LATE (burning a closed window is still wrong).
    """
    if not must_fire_result_paired(
        text,
        signal_kind=signal_kind,
        has_result_row=has_result_row,
        outcome=outcome,
    ):
        return None
    if action in {"HOLD_PREP", "DEDUP", "SKIP_NON_FIRE", "HOLD_RESULT"}:
        return "FIRE_NOW"
    return None


def law_banner() -> str:
    extra = ""
    try:
        try:
            from bot.config.emanation_laws import enabled as _em, law_banner as _eb
        except ImportError:
            from config.emanation_laws import enabled as _em, law_banner as _eb

        if _em():
            extra = " | " + _eb()
    except Exception:
        pass
    return (
        "[FIRE↔RESULT LAW] ON — "
        "result-paired signals MUST FIRE; "
        "every FIRE MUST get RESULT card skin under it (same chat, when printed seconds / round resolve)"
        + extra
    )
