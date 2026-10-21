import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path("/workspace/replit_elite_stack_patch/bot/total_census.py")


def _load_module():
    spec = importlib.util.spec_from_file_location("total_census", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@unittest.skipUnless(MODULE_PATH.exists(), "census module not present")
class TotalCensusTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = _load_module()
        cls.rep = cls.mod.build_report()

    def test_inventory_reconciles_every_source(self):
        inv = self.rep["inventory"]
        self.assertEqual(inv["floors"]["total"], 154)
        self.assertEqual(inv["museum_templates"]["total"], 827)
        self.assertEqual(inv["registry_families"]["total"], 120)
        self.assertEqual(inv["telegram_scan"]["messages_scanned"], 537166)

    def test_funnel_narrows_from_built_to_graded(self):
        """Most floors were never seen, let alone graded; the report must show that."""
        inv = self.rep["inventory"]
        floors = inv["floors"]
        fired = self.rep["systems_that_fired"]
        self.assertGreater(floors["total"], floors["seen_in_telegram"])
        self.assertGreater(floors["seen_in_telegram"], floors["reached_database"])
        self.assertGreaterEqual(floors["reached_database"], len(fired))
        self.assertEqual(len(fired), 7)

    def test_no_system_reports_a_verified_win_rate(self):
        totals = self.rep["systems_that_fired_totals"]
        self.assertIsNone(totals["verified_wr_pct"])
        self.assertIsNotNone(totals["claimed_wr_pct"])
        for row in self.rep["systems_that_fired"]:
            self.assertNotIn("verified_wr_pct", row)

    def test_verification_records_zero_ground_truth(self):
        ver = self.rep["verification"]
        self.assertEqual(ver["verdict"], "BOT_DB_INFERRED_ONLY")
        self.assertEqual(ver["direct_casino_rows"], 0)
        self.assertEqual(ver["signal_truth_matches"], 0)
        self.assertGreater(ver["labels_inferred_from_bot_db"], 0)

    def test_timing_cell_ignores_low_sample_cells(self):
        """A 3-sample cell can show any median, so it must not be cited as evidence."""
        cell = self.rep["verification"]["resolve_lag"]["fastest_cell"]
        self.assertGreaterEqual(cell["n"], self.mod.MIN_CELL_N)

    def test_markdown_states_the_verdict_and_the_tautology(self):
        md = self.mod.render_markdown(self.rep)
        self.assertIn("BOT_DB_INFERRED_ONLY", md)
        self.assertIn("| **none** |", md)
        self.assertIn("cannot disagree with the call", md)
        for kind in ("SOLO_ELITE", "SEQUENCE", "GOLDEN", "PLATINUM", "FLASH"):
            self.assertIn(kind, md)


if __name__ == "__main__":
    unittest.main()
