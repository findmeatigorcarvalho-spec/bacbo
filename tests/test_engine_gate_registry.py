import json
import os
import tempfile
import unittest
from types import MappingProxyType

from bot.config.registry import EngineGateRegistry


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

    def test_routine_enable_disable_is_not_audited(self):
        registry = EngineGateRegistry(self.file_path)

        registry.disable_gate("alpha")
        registry.bulk_disable(["beta", "gamma"])
        registry.enable_gate("alpha")

        self.assertEqual(registry.audit_log_snapshot(), tuple())
        self.assertEqual(self.read_config()["audit_log"], [])

    def test_retire_disables_persists_and_audits(self):
        registry = EngineGateRegistry(self.file_path)

        registry.retire_gate(" streak_reversal ")
        registry.bulk_retire(["m8sinais_lead_anchor", "streak_reversal"])

        self.assertEqual(
            registry.retired_gates_snapshot(),
            frozenset({"streak_reversal", "m8sinais_lead_anchor"}),
        )
        # Retiring also removes the gate from active rotation (disabled).
        self.assertTrue(registry.is_disabled("streak_reversal"))
        self.assertTrue(registry.is_disabled("m8sinais_lead_anchor"))
        self.assertTrue(registry.is_retired("streak_reversal"))

        saved = self.read_config()
        self.assertEqual(
            saved["retired_gates"], ["m8sinais_lead_anchor", "streak_reversal"]
        )
        self.assertEqual(
            saved["runtime_disabled"], ["m8sinais_lead_anchor", "streak_reversal"]
        )

        actions = [entry["action"] for entry in saved["audit_log"]]
        self.assertEqual(actions, ["retire", "retire"])
        self.assertEqual(saved["audit_log"][0]["gates"], ["streak_reversal"])
        self.assertEqual(saved["audit_log"][1]["gates"], ["m8sinais_lead_anchor"])
        self.assertIn("timestamp", saved["audit_log"][0])

    def test_retire_is_idempotent(self):
        registry = EngineGateRegistry(self.file_path)

        registry.retire_gate("alpha")
        registry.retire_gate("alpha")

        self.assertEqual(len(registry.audit_log_snapshot()), 1)
        self.assertEqual(registry.retired_gates_snapshot(), frozenset({"alpha"}))

    def test_unretire_keeps_disabled_state(self):
        registry = EngineGateRegistry(self.file_path)
        registry.retire_gate("alpha")

        registry.unretire_gate("alpha")

        self.assertFalse(registry.is_retired("alpha"))
        # Un-retiring does not silently re-enable the gate.
        self.assertTrue(registry.is_disabled("alpha"))

        actions = [entry["action"] for entry in self.read_config()["audit_log"]]
        self.assertEqual(actions, ["retire", "unretire"])

    def test_retest_and_retire_are_mutually_exclusive(self):
        registry = EngineGateRegistry(self.file_path)

        registry.retire_gate("alpha")
        registry.mark_retest_candidate("alpha")

        self.assertTrue(registry.is_retest_candidate("alpha"))
        self.assertFalse(registry.is_retired("alpha"))

        registry.retire_gate("alpha")

        self.assertTrue(registry.is_retired("alpha"))
        self.assertFalse(registry.is_retest_candidate("alpha"))

    def test_clear_retest_candidate(self):
        registry = EngineGateRegistry(self.file_path)
        registry.bulk_mark_retest(["alpha", "beta"])

        registry.clear_retest_candidate("alpha")

        self.assertEqual(registry.retest_candidates_snapshot(), frozenset({"beta"}))
        self.assertEqual(self.read_config()["retest_candidates"], ["beta"])

    def test_audit_log_snapshot_is_read_only_and_detached(self):
        registry = EngineGateRegistry(self.file_path)
        registry.retire_gate("alpha")

        snapshot = registry.audit_log_snapshot()
        self.assertEqual(len(snapshot), 1)
        with self.assertRaises(TypeError):
            snapshot[0]["action"] = "tampered"

        self.assertEqual(registry.audit_log_snapshot()[0]["action"], "retire")

    def test_audit_log_is_capped(self):
        registry = EngineGateRegistry(self.file_path, max_audit_entries=3)

        for i in range(5):
            registry.retire_gate(f"gate_{i}")

        snapshot = registry.audit_log_snapshot()
        self.assertEqual(len(snapshot), 3)
        gates = [entry["gates"][0] for entry in snapshot]
        self.assertEqual(gates, ["gate_2", "gate_3", "gate_4"])
        self.assertEqual(len(self.read_config()["audit_log"]), 3)

    def test_lifecycle_state_reloads_from_disk(self):
        registry = EngineGateRegistry(self.file_path)
        registry.bulk_retire(["alpha", "beta"])
        registry.mark_retest_candidate("gamma")

        reloaded = EngineGateRegistry(self.file_path)

        self.assertEqual(
            reloaded.retired_gates_snapshot(), frozenset({"alpha", "beta"})
        )
        self.assertEqual(
            reloaded.retest_candidates_snapshot(), frozenset({"gamma"})
        )
        # One audit entry for the bulk retire, one for the retest mark.
        self.assertEqual(len(reloaded.audit_log_snapshot()), 2)

    def test_lifecycle_rejects_invalid_gate_names(self):
        registry = EngineGateRegistry(self.file_path)

        with self.assertRaises(ValueError):
            registry.retire_gate("  ")
        with self.assertRaises(TypeError):
            registry.mark_retest_candidate(None)

        self.assertEqual(registry.retired_gates_snapshot(), frozenset())
        self.assertFalse(os.path.exists(self.file_path))


if __name__ == "__main__":
    unittest.main()
