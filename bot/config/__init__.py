"""bot.config package — fail-open so Profit Family AI modules can load on older Replit trees."""
from __future__ import annotations

__all__: list[str] = []

try:
    from bot.config.registry import EngineGateRegistry

    __all__.append("EngineGateRegistry")
except Exception:
    pass

try:
    from bot.config.skin_families import (
        SKIN_FAMILIES,
        SkinFamily,
        SkinMatch,
        all_skin_families,
        classify_telegram_skin,
        family_ids,
        gate_keys_for,
        product_skin_families,
        skin_blocked_by_registry,
    )

    __all__ += [
        "SKIN_FAMILIES",
        "SkinFamily",
        "SkinMatch",
        "all_skin_families",
        "classify_telegram_skin",
        "family_ids",
        "gate_keys_for",
        "product_skin_families",
        "skin_blocked_by_registry",
    ]
except Exception:
    pass

try:
    from bot.config.skin_gate import (
        SendGateDecision,
        evaluate_send_gate,
        should_block_telegram_send,
        skin_gate_enabled,
    )

    __all__ += [
        "SendGateDecision",
        "evaluate_send_gate",
        "should_block_telegram_send",
        "skin_gate_enabled",
    ]
except Exception:
    pass

try:
    from bot.config.chat_shelves import (
        ShelfDecision,
        resolve_shelf,
        shelf_catalog,
        shelf_for_family,
    )

    __all__ += [
        "ShelfDecision",
        "resolve_shelf",
        "shelf_catalog",
        "shelf_for_family",
    ]
except Exception:
    pass

try:
    from bot.config.chat_router import (
        ChatTarget,
        get_router,
        overflow_peers,
        route_card,
    )

    __all__ += [
        "ChatTarget",
        "get_router",
        "overflow_peers",
        "route_card",
    ]
except Exception:
    pass
