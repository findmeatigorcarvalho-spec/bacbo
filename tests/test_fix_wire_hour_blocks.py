import importlib.util
import tempfile
import unittest
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent / "replit_elite_stack_patch" / "bot"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, BASE / (name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class FixWireHourBlocksTest(unittest.TestCase):
    def setUp(self):
        self.fix = _load("fix_wire_hour_blocks")

    def test_hook_inserted_after_last_import(self):
        src = "import os\nimport sys\n\nX = 1\n"
        out = self.fix.patch_main(src)
        self.assertIn("import lux_no_hour_blocks", out)
        self.assertLess(out.index("import lux_no_hour_blocks"), out.index("X = 1"))
        import ast
        ast.parse(out)

    def test_idempotent(self):
        src = "import os\n"
        once = self.fix.patch_main(src)
        self.assertEqual(once, self.fix.patch_main(once))

    def test_install_and_backup(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "main.py").write_text("import os\nprint('hi')\n")
            self.assertIn("wired", self.fix.install(d))
            self.assertTrue((d / "main.py.bak_hourwire").exists())
            self.assertIn("already wired", self.fix.install(d))


class AuditMarkerTest(unittest.TestCase):
    def test_lux_marker_keys_are_not_flagged(self):
        audit = _load("hour_block_audit")
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            import json
            (d / "intelligence_state.json").write_text(json.dumps(
                {"lux_no_hour_blocks": True, "lux_no_hour_blocks_at": "x",
                 "dynamic_solo_bad_hrs": [3, 4]}))
            hits = audit.scan_state_files(d)
            self.assertEqual(len(hits), 1)
            self.assertIn("dynamic_solo_bad_hrs", hits[0])


if __name__ == "__main__":
    unittest.main()
