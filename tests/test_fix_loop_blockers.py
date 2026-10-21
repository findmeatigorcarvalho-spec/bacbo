import importlib.util
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parent.parent / "replit_elite_stack_patch" / "bot" / "fix_loop_blockers.py"


def _load():
    spec = importlib.util.spec_from_file_location("fix_loop_blockers", MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


SAMPLE = '''import asyncio
import sqlite3


def mine_perfect_cells():
    return {}


async def periodic_mining_task():
    while True:
        summary = mine_perfect_cells()
        print(summary)
        await asyncio.sleep(600)
'''

BG_SAMPLE = '''async def periodic_signal_health_monitor():
    _db = get_db()
    _today = _db.execute("""
        SELECT COUNT(*) FROM signals WHERE date(fired_at) = date('now')
    """).fetchone()
    return _today
'''


class FixLoopBlockersTest(unittest.TestCase):
    def setUp(self):
        self.f = _load()

    def test_patches_async_call_site(self):
        new = self.f.patch_perfect_g0(SAMPLE)
        self.assertIn("summary = await asyncio.to_thread(mine_perfect_cells)", new)
        compile(new, "perfect_g0_finder.py", "exec")

    def test_idempotent(self):
        once = self.f.patch_perfect_g0(SAMPLE)
        self.assertEqual(self.f.patch_perfect_g0(once), once)

    def test_refuses_sync_caller(self):
        src = SAMPLE.replace("async def periodic_mining_task", "def periodic_mining_task")
        with self.assertRaises(ValueError):
            self.f.patch_perfect_g0(src)

    def test_refuses_without_asyncio_import(self):
        src = SAMPLE.replace("import asyncio\n", "")
        with self.assertRaises(ValueError):
            self.f.patch_perfect_g0(src)

    def test_refuses_when_call_missing(self):
        with self.assertRaises(ValueError):
            self.f.patch_perfect_g0("import asyncio\n\n\nasync def other():\n    pass\n")

    def test_health_monitor_snippet_locates_execute(self):
        snippet = self.f.health_monitor_snippet(BG_SAMPLE)
        self.assertIn("periodic_signal_health_monitor", snippet)
        self.assertIn("_db.execute", snippet)
        self.assertIsNone(self.f.health_monitor_snippet("x = 1\n"))


if __name__ == "__main__":
    unittest.main()
