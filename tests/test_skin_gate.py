import asyncio
import os
import tempfile
import unittest
from unittest import mock

from bot.config.registry import EngineGateRegistry
from bot.config.skin_gate import (
    evaluate_send_gate,
    reset_registry_cache,
    should_block_telegram_send,
    skin_gate_enabled,
)


class SkinGateTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.path = os.path.join(self.temp_dir.name, "disabled_gates.json")
        reset_registry_cache()
        self._env_backup = os.environ.get("TELEGRAM_SKIN_GATE")
        os.environ["TELEGRAM_SKIN_GATE"] = "1"

    def tearDown(self):
        reset_registry_cache()
        if self._env_backup is None:
            os.environ.pop("TELEGRAM_SKIN_GATE", None)
        else:
            os.environ["TELEGRAM_SKIN_GATE"] = self._env_backup

    def test_allows_when_registry_empty(self):
        registry = EngineGateRegistry(self.path)
        decision = evaluate_send_gate(
            "💎 SOLO ELITE SIGNAL 💎\nENTER NOW",
            registry=registry,
        )
        self.assertFalse(decision.blocked)
        self.assertEqual(decision.family_id, "FIRE_SOLO_ELITE_ENTER")
        self.assertEqual(decision.reason, "allow")

    def test_blocks_retired_family(self):
        registry = EngineGateRegistry(self.path)
        registry.retire_gate("FIRE_GALE_RETENTATIVA")
        text = "♻️ GALE 1 — RETENTATIVA\n💎 SOLO ELITE SIGNAL"
        decision = evaluate_send_gate(text, registry=registry)
        self.assertTrue(decision.blocked)
        self.assertIn("FIRE_GALE_RETENTATIVA", decision.matched_keys)
        self.assertTrue(should_block_telegram_send(text, registry=registry))

    def test_blocks_kind_scoped_empate(self):
        registry = EngineGateRegistry(self.path)
        registry.retire_gate("RESULT_EMPATE:SOLO_ELITE")
        self.assertTrue(
            should_block_telegram_send(
                "🟡 EMPATE — SOLO_ELITE",
                registry=registry,
            )
        )
        self.assertFalse(
            should_block_telegram_send(
                "🟡 EMPATE — SEQUENCE",
                registry=registry,
            )
        )

    def test_env_off_never_blocks(self):
        registry = EngineGateRegistry(self.path)
        registry.retire_gate("FIRE_SOLO_ELITE_ENTER")
        os.environ["TELEGRAM_SKIN_GATE"] = "0"
        self.assertFalse(skin_gate_enabled())
        decision = evaluate_send_gate(
            "💎 SOLO ELITE SIGNAL 💎",
            registry=registry,
        )
        self.assertFalse(decision.blocked)
        self.assertEqual(decision.reason, "skin_gate_off")

    def test_lux_send_wrapper_drops_blocked(self):
        # Import after path is workspace root so bot.config resolves.
        import sys
        from pathlib import Path

        patch_bot = Path("/workspace/replit_elite_stack_patch/bot")
        if str(patch_bot) not in sys.path:
            sys.path.insert(0, str(patch_bot))

        registry = EngineGateRegistry(self.path)
        registry.retire_gate("FIRE_GOLDEN_ENTER")
        reset_registry_cache()

        with mock.patch(
            "bot.config.skin_gate.get_registry", return_value=registry
        ):
            import lux_send_config_bind as lux

            calls = []

            async def fake_send(msg, **kwargs):
                calls.append(msg)
                return 1

            wrapped = lux._wrap_send(fake_send)
            # Avoid hub route import noise / config requirement for this unit.
            with mock.patch.object(lux, "_ensure_config", return_value=object()):
                with mock.patch(
                    "hub_engine_route.hub_route_enabled", return_value=False
                ):
                    blocked = asyncio.run(
                        wrapped("🏆 GOLDEN SIGNAL — ENTER NOW 🏆")
                    )
                    allowed = asyncio.run(
                        wrapped("💎 SOLO ELITE SIGNAL 💎\nENTER NOW")
                    )

        self.assertIsNone(blocked)
        self.assertEqual(allowed, 1)
        self.assertEqual(calls, ["💎 SOLO ELITE SIGNAL 💎\nENTER NOW"])


if __name__ == "__main__":
    unittest.main()
