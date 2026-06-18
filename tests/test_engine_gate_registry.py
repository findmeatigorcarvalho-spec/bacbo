import json
import os
import tempfile
import unittest
from types import MappingProxyType

from bot.engine_gate_registry import EngineGateRegistry


class EngineGateRegistryTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.file_path = os.path.join(self.temp_dir.name, "disabled_gates.json")

    def tearDown(self):
        self.temp_dir.cleanup()

    def read_config(self):
        with open(self.file_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def write_config(self, config):
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(config, f)

    def test_disable_and_enable_gate_persist_atomically(self):
        registry = EngineGateRegistry(self.file_path)

        registry.disable_gate(" beta ")
        registry.bulk_disable(["alpha", "gamma", "alpha"])

        self.assertEqual(
            registry.disabled_gates_snapshot(),
            frozenset({"alpha", "beta", "gamma"}),
        )
        saved = self.read_config()
        self.assertEqual(saved["schema_version"], EngineGateRegistry.CURRENT_SCHEMA_VERSION)
        self.assertEqual(saved["runtime_disabled"], ["alpha", "beta", "gamma"])
        self.assertIn("updated_at", saved)
        self.assertEqual(saved["retired_gates"], [])
        self.assertEqual(saved["retest_candidates"], [])
        self.assertEqual(saved["audit_log"], [])

        registry.enable_gate("beta")
        registry.bulk_enable(["gamma", "missing"])

        self.assertEqual(registry.disabled_gates_snapshot(), frozenset({"alpha"}))
        self.assertEqual(self.read_config()["runtime_disabled"], ["alpha"])

    def test_loads_existing_schema_v2_runtime_disabled(self):
        self.write_config(
            {
                "schema_version": 2,
                "runtime_disabled": ["alpha", " beta ", "", 3, "alpha"],
                "audit_log": [{"event": "seed"}],
            }
        )

        registry = EngineGateRegistry(self.file_path)

        self.assertTrue(registry.is_disabled("alpha"))
        self.assertTrue(registry.is_disabled("beta"))
        self.assertFalse(registry.is_disabled("gamma"))
        self.assertEqual(registry.disabled_gates_snapshot(), frozenset({"alpha", "beta"}))

    def test_migrates_legacy_disabled_lists_on_save(self):
        self.write_config(
            {
                "schema_version": 1,
                "disabled": [{"gate": "alpha"}, {"gate": " beta "}, {"bad": "ignored"}],
                "manual_disabled": [{"gate": "gamma"}, {"gate": ""}, "ignored"],
                "retired_gates": ["old_gate"],
            }
        )
        registry = EngineGateRegistry(self.file_path)

        self.assertEqual(
            registry.disabled_gates_snapshot(),
            frozenset({"alpha", "beta", "gamma"}),
        )

        registry.enable_gate("beta")
        saved = self.read_config()

        self.assertEqual(saved["schema_version"], EngineGateRegistry.CURRENT_SCHEMA_VERSION)
        self.assertEqual(saved["runtime_disabled"], ["alpha", "gamma"])
        self.assertEqual(saved["retired_gates"], ["old_gate"])
        self.assertNotIn("disabled", saved)
        self.assertNotIn("manual_disabled", saved)

    def test_config_snapshot_is_read_only_and_detached(self):
        registry = EngineGateRegistry(self.file_path)
        registry.disable_gate("alpha")

        snapshot = registry.config_snapshot()

        self.assertIsInstance(snapshot, MappingProxyType)
        with self.assertRaises(TypeError):
            snapshot["schema_version"] = 3

        snapshot["runtime_disabled"].append("mutated")

        self.assertEqual(registry.config_snapshot()["runtime_disabled"], ["alpha"])
        self.assertEqual(registry.disabled_gates_snapshot(), frozenset({"alpha"}))

    def test_rejects_invalid_gate_names(self):
        registry = EngineGateRegistry(self.file_path)

        with self.assertRaises(ValueError):
            registry.disable_gate(" ")
        with self.assertRaises(TypeError):
            registry.enable_gate(None)
        with self.assertRaises(ValueError):
            registry.bulk_disable(["alpha", ""])

        self.assertEqual(registry.disabled_gates_snapshot(), frozenset())
        self.assertFalse(os.path.exists(self.file_path))


if __name__ == "__main__":
    unittest.main()
