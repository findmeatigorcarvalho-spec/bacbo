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


MAIN_SNIPPET = '''import os

def f():
    import sys
    return sys.argv

# ── Hour-advisory layer ─────────────────────────────────────────
import hour_advisory as _hour_adv
print(_hour_adv)
'''


class FixWireHourBlocksTest(unittest.TestCase):
    def setUp(self):
        self.fix = _load("fix_wire_hour_blocks")

    def test_hook_goes_before_hour_advisory_not_inside_function(self):
        out = self.fix.patch_main(MAIN_SNIPPET)
        self.assertIn("import lux_no_hour_blocks", out)
        self.assertLess(out.index("import lux_no_hour_blocks"),
                        out.index("Hour-advisory layer"))
        self.assertGreater(out.index("import lux_no_hour_blocks"),
                           out.index("def f():"))
        compile(out, "main.py", "exec")

    def test_refuses_without_anchor(self):
        with self.assertRaises(ValueError):
            self.fix.patch_main("import os\nprint(1)\n")

    def test_idempotent_and_install(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "main.py").write_text(MAIN_SNIPPET)
            self.assertIn("wired", self.fix.install(d))
            compile((d / "main.py").read_text(), "main.py", "exec")
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
