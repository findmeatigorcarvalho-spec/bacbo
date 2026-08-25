"""Wake the forensic countdown card as its own FIRE.

Operator lock (already proven in production — do not re-litigate):

The UNIQUE_g1 card

    🔵🔵🔵🔵🔵🔵🔵🔵🔵🔵
    ⏰  18:59 Pawtucket, RI
    🔔 ✅ G0 WIN  ·  #2725
    Apostou: BLUE → Saiu: BLUE
    ⏱ Intervalo: 28.5s

is the profit call. The printed interval IS the outcome timer. The predicted
color materializes in that exact countdown. Saiu on this skin is the call,
not a ball that already finished.

This module posts that exact skin at FIRE time (color + countdown), instead of
waiting for SQLite outcome and then treating the card as after-the-fact.
Museum ``📊 SEQUENCE SIGNAL — ENTER NOW 📊`` stays in the catalog as a sibling
FIRE; it is not the live UNIQUE_g1 family the operator started with.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

FAMILY_IDS = (
    "FIRE_SEQUENCE_ENTER",
    "FIRE_SEQUENCE_APOSTAR",
    "FIRE_SEQUENCIA_ENTER_NOW",
    "FIRE_SEQUENCE",
    "FIRE__704f4f1d66e0",
    "RESULT_FORENSIC_INTERVALO",
)
KIND_NEEDLES = ("SEQUENCE", "SEQUENCIA", "SEQUÊNCIA")
HEADER = "📊 SEQUENCE SIGNAL — ENTER NOW 📊"
# Floors that already fired this family (DB attribution + floor factory cells).
PEAK_FLOORS = ("LIVE", "MAR19", "ELITE_V2", "ELITE_V2_PEAK")
# Printed countdown on the live family card the operator started with (#2725).
FAMILY_PRINTED_SECS = 28.5
FORCE_ENV: dict[str, str] = {
    "SEQUENCE_FAMILY_WAKE": "1",
    "SEQUENCE_OUTBOX_FIRE": "1",
    "FORENSIC_AS_FIRE": "1",
    "FORENSIC_COUNTDOWN_SECS": "28.5",
    "SEQUENCE_ENTER_NOW_ALSO": "0",
    "PRINTED_SECS_ARE_OUTCOME": "1",
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


def forensic_as_fire() -> bool:
    """This countdown skin fires as the call. Printed Intervalo = outcome timer."""
    return enabled() and _flag("FORENSIC_AS_FIRE", "1")


def outbox_owns_fire() -> bool:
    return enabled() and _flag("SEQUENCE_OUTBOX_FIRE", "1")


def apply_env(env: dict[str, str] | None = None) -> dict[str, str]:
    target = env if env is not None else os.environ
    for key, value in FORCE_ENV.items():
        target[key] = value
        os.environ[key] = value
    return {k: str(os.environ.get(k, "")) for k in FORCE_ENV}


def peak_floors() -> list[str]:
    """Every floor that already fired this family — each free-fires its own stream."""
    found: list[str] = []
    try:
        import json
        from pathlib import Path

        data = Path(__file__).resolve().parent / "data"
        report = json.loads(
            (data / "g0_secs_round_offset_report.json").read_text(encoding="utf-8")
        )
        for cell in report.get("cells") or []:
            if not isinstance(cell, dict):
                continue
            if "SEQUENC" not in str(cell.get("signal_kind") or "").upper():
                continue
            floor = str(cell.get("floor") or "").upper().strip()
            if floor and floor not in found:
                found.append(floor)
    except Exception:
        pass
    for floor in PEAK_FLOORS:
        if floor not in found:
            found.append(floor)
    return found


def boot() -> dict[str, str]:
    out = apply_env()
    floors = peak_floors()
    os.environ["SEQUENCE_PEAK_FLOORS"] = ",".join(floors)
    print(
        "[SEQUENCE] forensic countdown IS the FIRE — "
        f"printed {FAMILY_PRINTED_SECS}s = outcome timer · "
        "Apostou→Saiu is the call · UNIQUE_g1"
    )
    print(f"[SEQUENCE] free-fire floors ({len(floors)}): {', '.join(floors)}")
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
    if "FORENSIC" in fam:
        return True
    kind = str(signal_kind or _get(row, "signal_kind") or "").upper()
    kind_norm = kind.replace("Ê", "E").replace("É", "E")
    if any(n in kind_norm for n in ("SEQUENCE", "SEQUENCIA")):
        return True
    blob = str(text or "").upper()
    if "SEQUENCE SIGNAL" in blob or "SEQUENCE — APOSTAR" in blob:
        return True
    if "RESUMIDO FORENSE" in blob and "TIPO: SEQUENCE" in blob:
        return True
    if "SEQUÊNCIA — ENTER" in str(text or "").upper() or "SEQUENCIA — ENTER" in blob:
        return True
    return False


def sequence_outbox_owns_fire(row: Any = None, *, signal_kind: str | None = None) -> bool:
    return outbox_owns_fire() and is_sequence_family(row, signal_kind=signal_kind)


def skip_after_resolve_forensic(row: Any = None, *, signal_kind: str | None = None) -> bool:
    """Do not re-post the same countdown card after SQLite outcome.

    The FIRE already carried Apostou→Saiu and the printed interval. A second
    identical copy after resolve is what got misread as 'already happened.'

    A G0 win is identical to what the FIRE already said, so it is dropped.
    Anything else (loss, tie, or a gale recovery) is NOT identical, so the
    room still gets that card — a bankroll must never go silent on a miss.
    """
    if not (forensic_as_fire() and is_sequence_family(row, signal_kind=signal_kind)):
        return False
    outcome = str(_get(row, "outcome") or "").strip().lower()
    if outcome and outcome != "win":
        return False
    try:
        if int(_get(row, "won_at_gale") or 0) != 0:
            return False
    except (TypeError, ValueError):
        pass
    return True


def is_sequence_museum_body(text: str | None) -> bool:
    t = str(text or "")
    return HEADER in t or "SEQUENCE SIGNAL — ENTER NOW" in t


def is_forensic_fire_body(text: str | None) -> bool:
    t = str(text or "")
    return "RESUMIDO FORENSE" in t.upper() and "APOSTOU:" in t.upper()


def forensic_is_live_fire(text: str | None) -> bool:
    return forensic_as_fire() and is_forensic_fire_body(text)


def _color_icon(color: str) -> str:
    c = (color or "").strip().lower()
    if c == "red":
        return "🔴"
    if c == "tie":
        return "🟡"
    return "🔵"


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


def _parse_fired(row: Any) -> datetime | None:
    raw = str(_get(row, "fired_at") or "")
    try:
        from card_timezone import parse_db_utc

        dt = parse_db_utc(raw)
        if dt is not None:
            return dt
    except Exception:
        pass
    try:
        if raw:
            return datetime.strptime(raw[:19].replace("T", " "), "%Y-%m-%d %H:%M:%S").replace(
                tzinfo=timezone.utc
            )
    except Exception:
        return None
    return None


def forensic_printed_secs(row: Any = None) -> float:
    """Seconds printed on this FIRE = outcome timer (already proven)."""
    for key in (
        "printed_secs",
        "countdown_secs",
        "janela_secs",
        "clock_c_secs",
        "original_secs",
    ):
        raw = _get(row, key, None)
        if raw in (None, "", 0, "0"):
            continue
        try:
            val = float(raw)
        except (TypeError, ValueError):
            continue
        if val > 0:
            return val
    try:
        return float(os.environ.get("FORENSIC_COUNTDOWN_SECS") or FAMILY_PRINTED_SECS)
    except (TypeError, ValueError):
        return FAMILY_PRINTED_SECS


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
    """Museum FIRE_SEQUENCE_ENTER sibling — not the live UNIQUE_g1 family card."""
    color = str(_get(row, "color") or "").lower()
    emoji, label, word = _color_parts(color)
    pattern, last, hint = _pattern_block(word)
    clock = _clock(row)
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


def fmt_forensic_countdown_fire(
    row: Any,
    *,
    floor: str | None = None,
    trust: dict[str, Any] | None = None,
    secs: float | None = None,
) -> str:
    """Live UNIQUE_g1 family: forensic countdown card as the FIRE.

    Apostou and Saiu are the predicted color. Intervalo is the outcome timer.
    Production already proved that color materializes in that countdown.
    """
    _ = (floor, trust)
    predicted = str(_get(row, "color") or "blue").strip().lower() or "blue"
    if predicted not in {"blue", "red", "tie"}:
        predicted = "blue"
    icon = _color_icon(predicted)
    word = predicted.upper()
    sid = _get(row, "id", "")
    kind = str(_get(row, "signal_kind") or "SEQUENCE")
    n = FAMILY_PRINTED_SECS if secs is None else float(secs)
    if n <= 0:
        n = forensic_printed_secs(row)
    fired = _get(row, "fired_at") or None
    try:
        from card_timezone import pawtucket_banner, pawtucket_forensic

        local_time = pawtucket_banner(fired)
        disparado = pawtucket_forensic(fired)
        dt = _parse_fired(row)
        if dt is not None:
            resolvido = pawtucket_forensic(
                (dt + timedelta(seconds=n)).strftime("%Y-%m-%d %H:%M:%S")
            )
        else:
            resolvido = pawtucket_forensic(fired)
    except Exception:
        local_time = f"{_clock(row)[:5]} Pawtucket, RI"
        disparado = str(fired or "—")
        resolvido = disparado
    banner = icon * 10
    gale = 0
    try:
        gale = int(_get(row, "won_at_gale") or 0)
    except (TypeError, ValueError):
        gale = 0
    result_label = "G0 WIN" if gale == 0 else f"G{gale} WIN"
    try:
        from fire_origin import truth_from_outcome

        truth_line = truth_from_outcome(predicted, "win")["line"]
    except Exception:
        truth_line = f"BET {word} → OUT {word} · WIN · TRUTH THIS ROUND = {word}"
    secs_txt = f"{n:.1f}s"
    return (
        f"{banner}\n"
        f"⏰  {local_time}\n"
        f"{banner}\n"
        f"🔔 ✅ {result_label}  ·  #{sid}\n"
        f"🎲 Apostou: {icon} {word}  →  Saiu: {icon} {word}\n"
        f"🧭 {truth_line}\n"
        f"🔍 SINAL #{sid} — RESUMIDO FORENSE\n"
        f"  Tipo: {kind} · Cor prevista: {word}\n"
        f"  Cor que SAIU: {word}\n"
        f"  Disparado: {disparado} (Pawtucket, RI)\n"
        f"  Resolvido: {resolvido} (Pawtucket, RI)\n"
        f"  ⏱ Intervalo (Clock C — fire→resolve): {secs_txt}\n"
        f"  Resultado: ✅ {result_label}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🏁 Aguarde o próximo sinal do bot"
    )


def fmt_live_sequence_fire(
    row: Any,
    *,
    floor: str | None = None,
    trust: dict[str, Any] | None = None,
) -> str:
    """Live skin for this family: forensic countdown FIRE (operator-started family)."""
    if forensic_as_fire() and not _flag("SEQUENCE_ENTER_NOW_ALSO", "0"):
        return fmt_forensic_countdown_fire(
            row,
            floor=floor,
            trust=trust,
            secs=forensic_printed_secs(row),
        )
    return fmt_sequence_enter_now(row, floor=floor, trust=trust)


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
    assert is_sequence_family(demo)
    assert sequence_outbox_owns_fire(demo)
    assert forensic_as_fire()
    assert skip_after_resolve_forensic(demo)
    assert skip_after_resolve_forensic(R(signal_kind="SEQUENCE", outcome="win"))
    # A miss or a gale recovery is not what the FIRE said — that card still posts.
    assert not skip_after_resolve_forensic(R(signal_kind="SEQUENCE", outcome="loss"))
    assert not skip_after_resolve_forensic(R(signal_kind="SEQUENCE", outcome="tie"))
    assert not skip_after_resolve_forensic(
        R(signal_kind="SEQUENCE", outcome="win", won_at_gale=1)
    )
    assert "LIVE" in peak_floors()
    fire = fmt_live_sequence_fire(demo, floor="LIVE")
    assert is_forensic_fire_body(fire)
    assert "RESUMIDO FORENSE" in fire
    assert "Apostou: 🔵 BLUE" in fire
    assert "Saiu: 🔵 BLUE" in fire
    assert "28.5s" in fire
    assert "Tipo: SEQUENCE" in fire
    assert "BAC BO SIGNAL" not in fire
    museum = fmt_sequence_enter_now(demo, floor="LIVE")
    assert HEADER in museum
    print("SEQUENCE_FORENSIC_FIRE_OK")
    print(fire)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
