"""Replit/hub send gate — block disabled/retired Telegram skin families.

Prefers ``bot.config.skin_gate`` (GitHub package). Falls back to path bootstrap
from this file's parents. Fail-open if the package is missing.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional


def _bootstrap_config_package() -> None:
    here = Path(__file__).resolve().parent
    candidates = [
        here.parent,  # …/bot → repo root when nested as repo/bot/
        here.parent.parent,  # …/replit_elite_stack_patch/bot → repo
        Path("/workspace"),
        Path("/home/runner/workspace"),
    ]
    for root in candidates:
        pkg = root / "bot" / "config" / "skin_gate.py"
        if pkg.is_file():
            root_s = str(root)
            if root_s not in sys.path:
                sys.path.insert(0, root_s)
            return


def _impl():
    try:
        from bot.config import skin_gate as sg  # type: ignore

        return sg
    except ImportError:
        pass
    _bootstrap_config_package()
    try:
        from bot.config import skin_gate as sg  # type: ignore

        return sg
    except ImportError:
        return None


def skin_gate_enabled() -> bool:
    sg = _impl()
    if sg is None:
        return False
    return bool(sg.skin_gate_enabled())


def evaluate_send_gate(
    text: Optional[str] = None,
    *,
    signal_kind: Optional[str] = None,
    meta: Optional[Dict[str, Any]] = None,
    registry: Any = None,
    registry_path: Optional[str] = None,
):
    sg = _impl()
    if sg is None:
        # Fail-open stub
        class _Allow:
            blocked = False
            family_id = "UNKNOWN"
            kind = None
            gate_keys = ()
            matched_keys = ()
            role = "UNKNOWN"
            lane = None
            reason = "skin_gate_unavailable"

            def as_dict(self):
                return {
                    "blocked": False,
                    "family_id": self.family_id,
                    "reason": self.reason,
                }

        return _Allow()
    return sg.evaluate_send_gate(
        text,
        signal_kind=signal_kind,
        meta=meta,
        registry=registry,
        registry_path=registry_path,
    )


def should_block_telegram_send(
    text: Optional[str] = None,
    *,
    signal_kind: Optional[str] = None,
    meta: Optional[Dict[str, Any]] = None,
    registry: Any = None,
    registry_path: Optional[str] = None,
) -> bool:
    return bool(
        evaluate_send_gate(
            text,
            signal_kind=signal_kind,
            meta=meta,
            registry=registry,
            registry_path=registry_path,
        ).blocked
    )


def log_block(decision: Any, *, where: str = "send") -> None:
    if not getattr(decision, "blocked", False):
        return
    if os.environ.get("TELEGRAM_SKIN_GATE_LOG", "1").strip().lower() in {
        "0",
        "false",
        "no",
        "off",
    }:
        return
    print(
        f"[SKIN-GATE] BLOCK {where} family={getattr(decision, 'family_id', '?')} "
        f"kind={getattr(decision, 'kind', None)} "
        f"matched={getattr(decision, 'matched_keys', ())} "
        f"reason={getattr(decision, 'reason', '')}"
    )
