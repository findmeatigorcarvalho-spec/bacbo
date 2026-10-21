import importlib.util
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parent.parent / "replit_elite_stack_patch" / "bot" / "fix_hardfva_notify.py"


def _load():
    spec = importlib.util.spec_from_file_location("fix_hardfva_notify", MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class FixHardFvaTest(unittest.TestCase):
    def setUp(self):
        self.fix = _load()

    def test_block_wall_none_is_coerced(self):
        src = "            _block_wall = state._hard_fva_blocked_wall\n"
        out = self.fix.patch_background(src)
        self.assertIn("_block_wall = state._hard_fva_blocked_wall or 0.0", out)

    def test_self_healer_error_gets_traceback(self):
        src = '            log.error(f"[SelfHealer] Loop error (continuing): {exc}")\n'
        out = self.fix.patch_self_healer(src)
        self.assertIn("exc_info=True", out)

    def test_install_idempotent_and_backs_up(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "background.py").write_text("_block_wall = state._hard_fva_blocked_wall\n")
            (d / "self_healer.py").write_text('log.error(f"[SelfHealer] Loop error (continuing): {exc}")\n')
            first = self.fix.install(d)
            self.assertTrue(any("patched" in r for r in first))
            self.assertTrue((d / "background.py.bak_hardfva").exists())
            second = self.fix.install(d)
            self.assertTrue(all("already fixed" in r for r in second))


if __name__ == "__main__":
    unittest.main()
