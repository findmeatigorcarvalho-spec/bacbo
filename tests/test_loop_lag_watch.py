import importlib.util
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parent.parent / "replit_elite_stack_patch" / "bot" / "loop_lag_watch.py"


def _load():
    spec = importlib.util.spec_from_file_location("loop_lag_watch", MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class LoopLagWatchTest(unittest.TestCase):
    def setUp(self):
        self.w = _load()

    def test_should_dump_thresholds(self):
        w = self.w
        self.assertFalse(w.should_dump(5, 1e9))
        self.assertFalse(w.should_dump(20, 10))
        self.assertTrue(w.should_dump(20, 1e9))
        self.assertTrue(w.should_dump(15, 60))

    def test_main_thread_stack_contains_current_frame(self):
        stack = self.w._main_thread_stack()
        self.assertIn("test_main_thread_stack", stack)

    def test_update_poller_starts_lag_watch(self):
        src = (MODULE_PATH.parent / "update_poller.py").read_text()
        self.assertIn("loop_lag_watch.start(loop)", src)


if __name__ == "__main__":
    unittest.main()
