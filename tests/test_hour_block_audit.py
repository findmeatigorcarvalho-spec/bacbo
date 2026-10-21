import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parent.parent / "replit_elite_stack_patch" / "bot" / "hour_block_audit.py"


def _load():
    spec = importlib.util.spec_from_file_location("hour_block_audit", MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class HourBlockAuditTest(unittest.TestCase):
    def setUp(self):
        self.audit = _load()

    def test_source_scan_finds_nonempty_blocks_only(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "gates.py").write_text(
                "_GOLDEN_BAD_UTC_HOURS = {3, 14}\n"
                "_EMPTY_BAD_HOURS = set()\n"
                "THRESHOLD = 3.0\n"
                "def f():\n    _LOCAL_BAD_HOURS = {1}\n"
            )
            hits = self.audit.scan_source(d)
            self.assertEqual(len(hits), 1)
            self.assertIn("_GOLDEN_BAD_UTC_HOURS", hits[0])

    def test_state_scan_counts_nested_lists(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "color_hour_blocks.json").write_text(json.dumps(
                {"dynamic_additions": {"GOLDEN": [1, 2], "SOLO_ELITE": []}}))
            hits = self.audit.scan_state_files(d)
            self.assertEqual(len(hits), 1)

    def test_wiring_detected(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "main.py").write_text("import lux_no_hour_blocks\n")
            self.assertTrue(self.audit.scan_wiring(d))


if __name__ == "__main__":
    unittest.main()
