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

BG_SAMPLE = '''import asyncio


async def periodic_signal_health_monitor():
    import sqlite3 as _sq3
    _WINDOW_MIN = 60
    _MIN_N = 3
    _WR_LEAK = 75.0
    await asyncio.sleep(120)
    while True:
        try:
            _db = _sq3.connect("bacbo.db", timeout=5)
            _db.execute("PRAGMA busy_timeout=3000")
            _recent = _db.execute("""
                SELECT gate_reason FROM blocked_signals
                WHERE blocked_at >= datetime('now',?)
            """, (f"-{_WINDOW_MIN} minutes",)).fetchall()
            _today = _db.execute("""
                SELECT COUNT(*) FROM consensus_signals
            """).fetchone()
            _blocked_today = _db.execute("""
                SELECT COUNT(*) FROM blocked_signals
            """).fetchone()[0]
            _db.close()
            _n_fired = _today[0] or 0
            print(_recent, _n_fired, _blocked_today)
        except Exception:
            pass
        await asyncio.sleep(300)
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

    def test_patches_two_async_call_sites(self):
        src = SAMPLE + '''

async def periodic_mining_task_b():
    summary = mine_perfect_cells()
    print(summary)
'''
        new = self.f.patch_perfect_g0(src)
        self.assertEqual(new.count("await asyncio.to_thread(mine_perfect_cells)"), 2)
        self.assertNotIn("summary = mine_perfect_cells()", new)
        compile(new, "perfect_g0_finder.py", "exec")

    def test_sync_site_left_untouched(self):
        src = SAMPLE + '''

def one_off():
    return mine_perfect_cells()
'''
        new = self.f.patch_perfect_g0(src)
        self.assertEqual(new.count("await asyncio.to_thread(mine_perfect_cells)"), 1)
        self.assertIn("return mine_perfect_cells()", new)

    def test_background_db_block_offloaded(self):
        new = self.f.patch_background(BG_SAMPLE)
        compile(new, "background.py", "exec")
        self.assertIn("def _signal_health_queries(_WINDOW_MIN, _MIN_N, _WR_LEAK):", new)
        self.assertIn("await asyncio.to_thread(_signal_health_queries, _WINDOW_MIN, _MIN_N, _WR_LEAK)", new)
        self.assertIn("    return _recent, _today, _blocked_today", new)
        monitor = new.split("async def periodic_signal_health_monitor", 1)[1]
        self.assertNotIn('_sq3.connect("bacbo.db"', monitor)
        self.assertIn("_db.execute", new.split("async def periodic_signal_health_monitor", 1)[0])

    def test_background_idempotent(self):
        once = self.f.patch_background(BG_SAMPLE)
        self.assertEqual(self.f.patch_background(once), once)

    def test_background_refuses_without_anchors(self):
        with self.assertRaises(ValueError):
            self.f.patch_background("import asyncio\n\n\nasync def periodic_signal_health_monitor():\n    pass\n")

    def test_background_helper_actually_runs_queries(self):
        import sqlite3, tempfile, os
        src = self.f.patch_background(BG_SAMPLE)
        with tempfile.TemporaryDirectory() as d:
            old = os.getcwd()
            os.chdir(d)
            try:
                conn = sqlite3.connect("bacbo.db")
                conn.execute("CREATE TABLE blocked_signals (gate_reason TEXT, blocked_at TEXT)")
                conn.execute("CREATE TABLE consensus_signals (id INTEGER)")
                conn.commit(); conn.close()
                ns = {}
                exec(compile(src, "background.py", "exec"), ns)
                recent, today, blocked = ns["_signal_health_queries"](60, 3, 75.0)
                self.assertEqual(recent, [])
                self.assertEqual(today[0], 0)
                self.assertEqual(blocked, 0)
            finally:
                os.chdir(old)

    def test_health_monitor_snippet_locates_execute(self):
        snippet = self.f.health_monitor_snippet(BG_SAMPLE)
        self.assertIn("periodic_signal_health_monitor", snippet)
        self.assertIn("_db.execute", snippet)
        self.assertIsNone(self.f.health_monitor_snippet("x = 1\n"))


if __name__ == "__main__":
    unittest.main()
