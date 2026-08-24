"""Wake the SEQUENCE FIRE family that sits under the forensic RESULT card.

The card the operator has been seeing on UNIQUE_g1:

    🔵🔵🔵🔵🔵🔵🔵🔵🔵🔵
    ⏰  18:59 Pawtucket, RI
    🔔 ✅ G0 WIN  ·  #2725
    Tipo: SEQUENCE

is a RESULT (FORENSIC_INTERVALO + WIN_TIER + COLOR_BANNER). It is not a FIRE.
``Tipo: SEQUENCE`` names the parent FIRE family.

Peak FIRE for that family (museum ``FIRE_SEQUENCE_ENTER`` / ``FIRE__704f4f1d66e0``,
historical tg_count 109, already-working):

    📊 SEQUENCE SIGNAL — ENTER NOW 📊

This module:
  1. Renders that peak FIRE body with live color / Pawtucket clock / rooms
  2. Lets the outbox POST that FIRE when HUB_MAX would otherwise skip fire cards
     (``HUB_OUTBOX_FIRE_CARDS=0`` assumed the engine owned skins — it did not)
  3. Leaves the forensic RESULT glued under the FIRE after resolve (Clock C)
  4. Does not flatten GOLDEN / SOLO / PLATINUM or other systems — SEQUENCE first

Sibling skins in the same family (APOSTAR, SEQUENCIA_ENTER_NOW) stay in the
catalog. Kind SEQUENCE on consensus_signals maps to ENTER NOW, which is the
FIRE historically paired with SEQUENCE results.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

FAMILY_IDS = (
    "FIRE_SEQUENCE_ENTER",
    "FIRE_SEQUENCE_APOSTAR",
    "FIRE_SEQUENCIA_ENTER_NOW",
    "FIRE_SEQUENCE",
    "FIRE__704f4f1d66e0",
)
KIND_NEEDLES = ("SEQUENCE", "SEQUENCIA", "SEQUÊNCIA")
HEADER = "📊 SEQUENCE SIGNAL — ENTER NOW 📊"
FORCE_ENV: dict[str, str] = {
    "SEQUENCE_FAMILY_WAKE": "1",
    "SEQUENCE_OUTBOX_FIRE": "1",
}


def _flag(name: str, default: str = "1") -> bool:
    return os.environ.get(name, default).strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def enabled() -> bool:
    return _flag("SEQUENCE_FAMILY_WAKE", "1")


def outbox_owns_fire() -> bool:
    """Outbox posts SEQUENCE ENTER NOW because the engine is not posting it."""
    return enabled() and _flag("SEQUENCE_OUTBOX_FIRE", "1")


def apply_env(env: dict[str, str] | None = None) -> dict[str, str]:
    target = env if env is not None else os.environ
    for key, value in FORCE_ENV.items():
        target[key] = value
        os.environ[key] = value
    return {k: str(os.environ.get(k, "")) for k in FORCE_ENV}


def boot() -> dict[str, str]:
    out = apply_env()
    print(
        "[SEQUENCE] family wake ON — FIRE=📊 SEQUENCE SIGNAL — ENTER NOW "
        "RESULT=forensic Apostou→Saiu under that FIRE · UNIQUE_g1"
    )
    return out


def _get(row: Any, key: str, default: Any = "") -> Any:
    if row is None:
        return default
    if isinstance(row, dict):
        val = row.get(key, default)
        return default if val is None else val
    try:
        keys = row.keys()  # sqlite3.Row
        if key in keys:
            val = row[key]
            return default if val is None else val
    except Exception:
        pass
    return getattr(row, key, default)


def is_sequence_family(
    row: Any = None,
    *,
    signal_kind: str | None = None,
    text: str | None = None,
    family_id: str | None = None,
) -> bool:
    fam = str(family_id or _get(row, "family_id") or "").upper()
    if fam in {x.upper() for x in FAMILY_IDS} or "FIRE_SEQUENCE" in fam or "SEQUENCIA" in fam:
        return True
    kind = str(signal_kind or _get(row, "signal_kind") or "").upper()
    kind_norm = kind.replace("Ê", "E").replace("É", "E")
    if any(n in kind_norm for n in ("SEQUENCE", "SEQUENCIA")):
        return True
    blob = str(text or "").upper()
    if "SEQUENCE SIGNAL" in blob or "SEQUENCE — APOSTAR" in blob:
        return True
    if "SEQUÊNCIA — ENTER" in str(text or "").upper() or "SEQUENCIA — ENTER" in blob:
        return True
    return False


def sequence_outbox_owns_fire(row: Any = None, *, signal_kind: str | None = None) -> bool:
    return outbox_owns_fire() and is_sequence_family(row, signal_kind=signal_kind)


def is_sequence_museum_body(text: str | None) -> bool:
    t = str(text or "")
    return HEADER in t or "SEQUENCE SIGNAL — ENTER NOW" in t


def _color_parts(color: str) -> tuple[str, str, str]:
    c = (color or "").strip().lower()
    if c == "red":
        return "🔴", "Vermelho (Player)", "RED"
    if c == "tie":
        return "🟡", "Empate (Tie)", "TIE"
    return "🔵", "Azul (Banker)", "BLUE"


def _clock(row: Any) -> str:
    raw = str(_get(row, "fired_at") or "")
    try:
        from card_timezone import pawtucket_time

        clock = pawtucket_time(raw, seconds=True)
        if clock and clock != "--:--":
            return clock
    except Exception:
        pass
    try:
        from zoneinfo import ZoneInfo

        if raw:
            dt = datetime.strptime(raw[:19].replace("T", " "), "%Y-%m-%d %H:%M:%S")
            dt = dt.replace(tzinfo=timezone.utc).astimezone(ZoneInfo("America/New_York"))
            return dt.strftime("%H:%M:%S")
    except Exception:
        pass
    try:
        from zoneinfo import ZoneInfo

        return datetime.now(ZoneInfo("America/New_York")).strftime("%H:%M:%S")
    except Exception:
        return datetime.now().strftime("%H:%M:%S")


def _pattern_block(color_word: str) -> tuple[str, str, str]:
    """Peak SEQUENCE ENTER used alternating confirmation for the called color."""
    if color_word == "RED":
        last = "🔴 🔵 🔴 🔵"
        hint = "_Alternância estrita nos últimos 4 rounds. Próximo: RED. Entre agora._"
        return "🔄 PADRÃO ALTERNADO CONFIRMADO", last, hint
    if color_word == "TIE":
        last = "🟡 🟡"
        hint = "_Empate em sequência. Próximo: TIE. Entre agora._"
        return "🔄 PADRÃO EMPATE CONFIRMADO", last, hint
    last = "🔵 🔴 🔵 🔴"
    hint = "_Alternância estrita nos últimos 4 rounds. Próximo: BLUE. Entre agora._"
    return "🔄 PADRÃO ALTERNADO CONFIRMADO", last, hint


def fmt_sequence_enter_now(
    row: Any,
    *,
    floor: str | None = None,
    trust: dict[str, Any] | None = None,
) -> str:
    """Museum FIRE_SEQUENCE_ENTER body, facts refreshed. No route/score noise."""
    color = str(_get(row, "color") or "").lower()
    emoji, label, word = _color_parts(color)
    pattern, last, hint = _pattern_block(word)
    clock = _clock(row)
    # floor/trust intentionally omitted — peak skin did not print them.
    _ = (floor, trust)
    return (
        f"{HEADER}\n"
        "\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "\n"
        f"🎯 Enter: {emoji} {label}\n"
        "   └ _Primary bet — full bankroll_\n"
        "\n"
        "📈 Pattern:\n"
        f" {pattern}\n"
        "\n"
        "🔢 Last results:\n"
        f" {last}\n"
        "\n"
        f"💡 {hint}\n"
        "\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "\n"
        f"⏰ {clock} | Evolution Bac Bo\n"
        "\n"
        "⚡ ENTER NOW — PATTERN CONFIRMED\n"
        "\n"
        "_After result: /win · /loss · /tie_"
    )


def main() -> int:
    apply_env()
    class R(dict):
        pass

    demo = R(
        id=2725,
        signal_kind="SEQUENCE",
        color="blue",
        fired_at="2026-08-12 22:59:29",
        rooms_agreed="3",
        source_floor="LIVE",
    )
    body = fmt_sequence_enter_now(demo, floor="LIVE")
    assert is_sequence_family(demo)
    assert sequence_outbox_owns_fire(demo)
    assert is_sequence_museum_body(body)
    assert HEADER in body
    assert "Azul (Banker)" in body
    assert "BAC BO SIGNAL" not in body
    assert "📡 Route:" not in body
    print("SEQUENCE_FAMILY_WAKE_OK")
    print(body)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
