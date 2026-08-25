import os
import tempfile
import unittest

from bot.config.registry import EngineGateRegistry
from bot.config.skin_families import (
    SELFTEST_CASES,
    SKIN_FAMILIES,
    classify_telegram_skin,
    family_ids,
    gate_keys_for,
    product_skin_families,
)


class TelegramSkinFamiliesTest(unittest.TestCase):
    def test_catalog_ids_are_unique(self):
        ids = [f.family_id for f in SKIN_FAMILIES]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertIn("FIRE_GALE_RETENTATIVA", ids)
        self.assertIn("RESULT_EMPATE", ids)
        self.assertIn("FIRE_JANELA_TIMED", ids)

    def test_product_skins_exclude_room_relay_noise(self):
        ids = {f.family_id for f in product_skin_families()}
        self.assertNotIn("ROOM_RELAY", ids)
        self.assertIn("FIRE_SOLO_ELITE_ENTER", ids)

    def test_selftest_vectors(self):
        for text, expected_family, expected_kind in SELFTEST_CASES:
            with self.subTest(family=expected_family, text=text[:48]):
                match = classify_telegram_skin(text)
                self.assertEqual(match.family_id, expected_family)
                if expected_kind is not None:
                    self.assertEqual(match.kind, expected_kind)
                self.assertEqual(match.gate_keys[0], expected_family)

    def test_gale_retentativa_distinct_from_entre_novamente(self):
        a = classify_telegram_skin("♻️ GALE 1 — RETENTATIVA\n💎 SOLO ELITE SIGNAL")
        b = classify_telegram_skin("🔁 GALE 1 — Entre novamente")
        self.assertEqual(a.family_id, "FIRE_GALE_RETENTATIVA")
        self.assertEqual(b.family_id, "FIRE_GALE_ENTRE_NOVAMENTE")
        self.assertNotEqual(a.family_id, b.family_id)

    def test_empate_solo_elite_kind_scoped_gate_key(self):
        match = classify_telegram_skin(
            "🟡 EMPATE — SOLO_ELITE\nResultado empatado — proteção ativada!"
        )
        self.assertEqual(match.family_id, "RESULT_EMPATE")
        self.assertEqual(match.kind, "SOLO_ELITE")
        self.assertEqual(
            match.gate_keys,
            ("RESULT_EMPATE", "RESULT_EMPATE:SOLO_ELITE"),
        )

    def test_janela_variable_n_collapses_to_one_family(self):
        a = classify_telegram_skin("JANELA: 1s para apostar\n💎 SOLO ELITE")
        b = classify_telegram_skin("JANELA: 17s para apostar\n🏆 GOLDEN")
        c = classify_telegram_skin("🟢 40s 🟢\nSEQUENCE SIGNAL")
        self.assertEqual(a.family_id, "FIRE_JANELA_TIMED")
        self.assertEqual(b.family_id, "FIRE_JANELA_TIMED")
        self.assertEqual(c.family_id, "FIRE_JANELA_TIMED")
        self.assertEqual(a.clock_n, 1)
        self.assertEqual(b.clock_n, 17)
        self.assertEqual(c.clock_n, 40)
        self.assertEqual(a.lane, "COUNTDOWN")

    def test_apostar_agora_distinct_from_enter_now(self):
        enter = classify_telegram_skin("💎 SOLO ELITE SIGNAL 💎\nENTER NOW")
        apostar = classify_telegram_skin("⚡ SOLO ELITE — APOSTAR AGORA")
        self.assertEqual(enter.family_id, "FIRE_SOLO_ELITE_ENTER")
        self.assertEqual(apostar.family_id, "FIRE_SOLO_APOSTAR")

    def test_gate_keys_for_helper(self):
        self.assertEqual(gate_keys_for("RESULT_EMPATE"), ("RESULT_EMPATE",))
        self.assertEqual(
            gate_keys_for("RESULT_EMPATE", "solo elite"),
            ("RESULT_EMPATE", "RESULT_EMPATE:SOLO_ELITE"),
        )

    def test_registry_blocks_kind_scoped_skin(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        path = os.path.join(temp_dir.name, "disabled_gates.json")
        registry = EngineGateRegistry(path)

        text = "🟡 EMPATE — SOLO_ELITE\nproteção"
        self.assertFalse(registry.is_telegram_skin_blocked(text))

        registry.retire_gate("RESULT_EMPATE:SOLO_ELITE")
        self.assertTrue(registry.is_telegram_skin_blocked(text))

        # Sibling kind still allowed unless family-wide retired.
        other = "🟡 EMPATE — SEQUENCE"
        self.assertFalse(registry.is_telegram_skin_blocked(other))

        registry.retire_gate("RESULT_EMPATE")
        self.assertTrue(registry.is_telegram_skin_blocked(other))

    def test_registry_blocks_gale_retentativa_family(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        path = os.path.join(temp_dir.name, "disabled_gates.json")
        registry = EngineGateRegistry(path)

        registry.disable_gate("FIRE_GALE_RETENTATIVA")
        self.assertTrue(
            registry.is_telegram_skin_blocked(
                "♻️ GALE 1 — RETENTATIVA\n💎 SOLO ELITE SIGNAL"
            )
        )
        self.assertFalse(
            registry.is_telegram_skin_blocked("🔁 GALE 1 — Entre novamente")
        )

    def test_family_ids_helper_matches_catalog(self):
        self.assertEqual(family_ids(), tuple(f.family_id for f in SKIN_FAMILIES))

    def test_signal_kind_bridge_fallback(self):
        match = classify_telegram_skin("", signal_kind="EMERGING")
        self.assertEqual(match.family_id, "SIGNAL_KIND_EMERGING")
        self.assertIn("EMERGING", match.gate_keys)


if __name__ == "__main__":
    unittest.main()
