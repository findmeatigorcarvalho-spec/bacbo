"""
hotfix_room_noise_filter.py - quarantine non-actionable room chatter.

This patches the live Replit bot/signal_handler.py so messages like:
  "🔥 42 vitórias seguidas!"
  "📊 Acertamos 96%"
  VIP ads, reports, streak-only messages, generic "analisando" notices
are saved to bot/data/room_noise_messages.jsonl instead of being relayed to
the main Telegram target.

It intentionally keeps actionable entry/result text available:
  entrada confirmada, apostar, banker/player, azul/vermelho, resultado,
  win/loss/tie/green/loss result messages.
"""
from __future__ import annotations

import argparse
import shutil
import time
from pathlib import Path


HERE = Path(__file__).resolve().parent
SIGNAL_HANDLER = HERE / "signal_handler.py"


HELPER = r'''

# ---- Cursor hotfix: room noise quarantine ----
def _cursor_noise_text(_text):
    import json as _json
    import re as _re
    from datetime import datetime as _dt
    from pathlib import Path as _Path
    _raw = str(_text or "")
    _low = _raw.lower()

    # Actionable betting/result phrases must stay in the normal bot pipeline.
    _actionable = (
        "entrada confirmada", "sinal confirmado", "apostar", "aposta",
        "banker", "player", "azul", "vermelho", "resultado",
        "green", "loss", "vitória", "vitoria", "tie", "empate",
        "gale", "win", "red", "blue",
    )
    if any(x in _low for x in _actionable):
        return False

    _noise_patterns = (
        r"\b\d+\s*vit[oó]rias?\s+seguidas?\b",
        r"\b\d+\s*greens?\s+seguidos?\b",
        r"\bacertamos\b",
        r"\bacertividade\b",
        r"\bplacar\b",
        r"\brelat[oó]rio\b",
        r"\bcadastre-se\b",
        r"\bvip\b",
        r"\bpowered by\b",
        r"\banalisando\b",
        r"\bposs[ií]vel entrada\b",
        r"https?://",
    )
    return any(_re.search(p, _low) for p in _noise_patterns)


def _cursor_save_room_noise(_room, _text):
    import json as _json
    from datetime import datetime as _dt
    from pathlib import Path as _Path
    try:
        _p = _Path(__file__).resolve().parent / "data" / "room_noise_messages.jsonl"
        _p.parent.mkdir(parents=True, exist_ok=True)
        with _p.open("a", encoding="utf-8") as _fh:
            _fh.write(_json.dumps({
                "ts": _dt.utcnow().isoformat() + "Z",
                "room": str(_room or ""),
                "text": str(_text or ""),
            }, ensure_ascii=False) + "\n")
    except Exception:
        pass


async def _cursor_noise_guard(_room, _text):
    if _cursor_noise_text(_text):
        _cursor_save_room_noise(_room, _text)
        try:
            log.info(f"[RoomNoise] quarantined room-only message from {_room}: {str(_text)[:80]!r}")
        except Exception:
            pass
        return True
    return False
# ---- end Cursor hotfix ----
'''


def patch(path: Path = SIGNAL_HANDLER, dry_run: bool = False) -> list[str]:
    if not path.exists():
        raise SystemExit(f"missing {path}")
    source = path.read_text(errors="ignore")
    changes: list[str] = []

    if "Cursor hotfix: room noise quarantine" not in source:
        # Put helpers after imports so log is available by runtime lookup.
        marker = "\nasync def "
        idx = source.find(marker)
        if idx == -1:
            source = HELPER + "\n" + source
        else:
            source = source[:idx] + HELPER + source[idx:]
        changes.append("inserted room noise helper")

    # Patch direct relay calls if present. This catches the common pattern:
    # _relay_message(... text/message ...)
    relay_needles = [
        "await _relay_message(",
        "await _relay_media(",
    ]
    for needle in relay_needles:
        if needle in source and f"_cursor_noise_guard" not in source[max(0, source.find(needle) - 500):source.find(needle)]:
            idx = source.find(needle)
            line_start = source.rfind("\n", 0, idx) + 1
            indent = source[line_start:idx]
            guard = (
                f"{indent}try:\n"
                f"{indent}    _cursor_ng_room = locals().get('handle') or locals().get('source_handle') or locals().get('room')\n"
                f"{indent}    _cursor_ng_text = locals().get('text') or locals().get('raw_text') or locals().get('msg_text') or locals().get('message_text')\n"
                f"{indent}    if await _cursor_noise_guard(_cursor_ng_room, _cursor_ng_text):\n"
                f"{indent}        return\n"
                f"{indent}except Exception:\n"
                f"{indent}    pass\n"
            )
            source = source[:line_start] + guard + source[line_start:]
            changes.append(f"guarded {needle.strip()}")

    if changes and not dry_run:
        backup = path.with_suffix(path.suffix + f".bak_noise_filter_{int(time.time())}")
        shutil.copy2(path, backup)
        path.write_text(source)
        changes.append(f"backup={backup}")
    return changes


def main() -> int:
    parser = argparse.ArgumentParser(description="Quarantine non-actionable room chatter")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    changes = patch(dry_run=args.dry_run)
    print({"dry_run": args.dry_run, "changes": changes, "restart_required": bool(changes and not args.dry_run)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
