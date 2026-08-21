"""Load OPERATOR_LOCK so boot and later agents hit disk, not chat memory."""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent
LOCK_MD = HERE / "data" / "OPERATOR_LOCK.md"

AXES = ("SYSTEM", "SKIN", "CHAT")

FACTS = {
    "systems_are_not_skins": True,
    "solo_golden_sequence_are_three_fire_family_labels_only": True,
    "mr_iv4_birth_templates": 770,
    "museum_templates": 827,
    "museum_unknown_role": 550,
    "canonical_fire_families": 43,
    "canonical_result_families": 28,
    "coalition_distinct_scores_sum": True,
    "same_score_copies_are_one_vote": True,
    "bundle_is_all_systems_plus_all_skins_plus_all_shelves": True,
    "production_history_is_already_true": True,
    "already_working_min_sends": 10,
    "peak_day_min_signals": 50,
    "back_to_back_24h_already_working": True,
    "printed_seconds_are_outcome_timer": True,
    "do_not_hold_fire_for_packer_window": True,
}


def path() -> Path:
    return LOCK_MD


def load_text() -> str:
    if LOCK_MD.is_file():
        return LOCK_MD.read_text(encoding="utf-8")
    return ""


def boot() -> dict:
    text = load_text()
    ok = bool(text) and "Three axes" in text
    print(
        "[OPERATOR-LOCK]",
        "OK" if ok else "MISSING",
        f"bytes={len(text)}",
        "SYSTEM≠SKIN≠CHAT",
        "SOLO/GOLDEN/SEQUENCE=labels-only",
        "printed-secs=outcome",
        "already-working=>10",
        "UNKNOWN museum=550",
    )
    return {"ok": ok, "path": str(LOCK_MD), "facts": FACTS}


if __name__ == "__main__":
    boot()
