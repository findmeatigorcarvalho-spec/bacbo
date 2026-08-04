"""Send-path gate: block Telegram cards whose skin family is disabled/retired.

Used by engine ``send()`` wrap (lux_send_config_bind) and telegram_outbox.
Fail-open on import/IO errors so a missing registry never stalls the bot.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, Optional, Sequence, Tuple

from bot.config.registry import EngineGateRegistry
from bot.config.skin_families import SkinMatch, classify_telegram_skin


@dataclass(frozen=True)
class SendGateDecision:
    blocked: bool
    family_id: str
    kind: Optional[str]
    gate_keys: Tuple[str, ...]
    matched_keys: Tuple[str, ...]
    role: str
    lane: Optional[str]
    reason: str

    def as_dict(self) -> Dict[str, Any]:
        return {
            "blocked": self.blocked,
            "family_id": self.family_id,
            "kind": self.kind,
            "gate_keys": list(self.gate_keys),
            "matched_keys": list(self.matched_keys),
            "role": self.role,
            "lane": self.lane,
            "reason": self.reason,
        }


_REGISTRY: Optional[EngineGateRegistry] = None


def skin_gate_enabled() -> bool:
    return os.environ.get("TELEGRAM_SKIN_GATE", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def get_registry(file_path: Optional[str] = None) -> EngineGateRegistry:
    global _REGISTRY
    path = file_path or os.environ.get(
        "ENGINE_GATE_REGISTRY_PATH", "bot/data/disabled_gates.json"
    )
    if _REGISTRY is None or (
        file_path and getattr(_REGISTRY, "file_path", None) != file_path
    ):
        _REGISTRY = EngineGateRegistry(path)
    else:
        # Reload so retire/disable from disk is visible without process restart.
        try:
            _REGISTRY.load()
        except Exception:
            pass
    return _REGISTRY


def reset_registry_cache() -> None:
    """Test helper — drop the process-wide registry singleton."""
    global _REGISTRY
    _REGISTRY = None


def _matched_blocked_keys(
    registry: EngineGateRegistry, gate_keys: Sequence[str]
) -> Tuple[str, ...]:
    hit = []
    for key in gate_keys:
        if not isinstance(key, str) or not key.strip():
            continue
        try:
            if registry.is_blocked(key):
                hit.append(key)
        except (TypeError, ValueError):
            continue
    return tuple(hit)


def evaluate_send_gate(
    text: Optional[str] = None,
    *,
    signal_kind: Optional[str] = None,
    meta: Optional[Dict[str, Any]] = None,
    registry: Optional[EngineGateRegistry] = None,
    registry_path: Optional[str] = None,
) -> SendGateDecision:
    """Classify card text and decide whether send should be blocked."""
    match: SkinMatch = classify_telegram_skin(
        text, signal_kind=signal_kind, meta=meta
    )
    if not skin_gate_enabled():
        return SendGateDecision(
            blocked=False,
            family_id=match.family_id,
            kind=match.kind,
            gate_keys=match.gate_keys,
            matched_keys=(),
            role=match.role,
            lane=match.lane,
            reason="skin_gate_off",
        )

    try:
        reg = registry or get_registry(registry_path)
        matched = _matched_blocked_keys(reg, match.gate_keys)
    except Exception as exc:
        return SendGateDecision(
            blocked=False,
            family_id=match.family_id,
            kind=match.kind,
            gate_keys=match.gate_keys,
            matched_keys=(),
            role=match.role,
            lane=match.lane,
            reason=f"fail_open:{exc!r}",
        )

    if matched:
        return SendGateDecision(
            blocked=True,
            family_id=match.family_id,
            kind=match.kind,
            gate_keys=match.gate_keys,
            matched_keys=matched,
            role=match.role,
            lane=match.lane,
            reason=f"blocked:{','.join(matched)}",
        )
    return SendGateDecision(
        blocked=False,
        family_id=match.family_id,
        kind=match.kind,
        gate_keys=match.gate_keys,
        matched_keys=(),
        role=match.role,
        lane=match.lane,
        reason="allow",
    )


def should_block_telegram_send(
    text: Optional[str] = None,
    *,
    signal_kind: Optional[str] = None,
    meta: Optional[Dict[str, Any]] = None,
    registry: Optional[EngineGateRegistry] = None,
    registry_path: Optional[str] = None,
) -> bool:
    return evaluate_send_gate(
        text,
        signal_kind=signal_kind,
        meta=meta,
        registry=registry,
        registry_path=registry_path,
    ).blocked
