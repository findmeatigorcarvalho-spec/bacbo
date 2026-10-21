import importlib.util
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parent.parent / "replit_elite_stack_patch" / "bot" / "fix_none_counters.py"


def _load():
    spec = importlib.util.spec_from_file_location("fix_none_counters", MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class FixNoneCountersTest(unittest.TestCase):
    def setUp(self):
        self.fix = _load()

    def test_state_none_defaults_become_zero(self):
        src = "_session_wins = None\n_session_losses = None\n_session_ties = None\n_other = None\n"
        out = self.fix.patch_state(src)
        self.assertIn("_session_wins = 0", out)
        self.assertIn("_session_losses = 0", out)
        self.assertIn("_session_ties = 0", out)
        self.assertIn("_other = None", out)

    def test_main_brain_restore_coerces_explicit_nulls(self):
        src = ('state._session_wins    = _brain.get("session_wins", 0)\n'
               'state._session_g0_wins = _brain.get("session_g0", 0)\n')
        out = self.fix.patch_main(src)
        self.assertIn('(_brain.get("session_wins") or 0)', out)
        self.assertIn('(_brain.get("session_g0") or 0)', out)
        ns = {"_brain": {"session_wins": None, "session_g0": 3}}
        import re as _re
        for line in out.strip().splitlines():
            expr = line.split("=", 1)[1].strip()
            self.assertIsInstance(eval(expr, {}, ns), int)

    def test_install_is_idempotent_and_backs_up(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "state.py").write_text("_session_wins = None\n")
            (d / "main.py").write_text('x = _brain.get("session_wins", 0)\n')
            first = self.fix.install(d)
            self.assertTrue(any("patched" in r for r in first))
            self.assertTrue((d / "state.py.bak_none_counters").exists())
            second = self.fix.install(d)
            self.assertTrue(all("already fixed" in r for r in second))


if __name__ == "__main__":
    unittest.main()
