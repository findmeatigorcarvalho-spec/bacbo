import importlib.util
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parent.parent / "replit_elite_stack_patch" / "bot" / "fix_room_intel_blocking.py"

SNIPPET = '''
def refresh_all_room_dna() -> dict:
    conn = database.get_conn()
    try:
        rows = conn.execute("""
            SELECT handle, COUNT(*) AS n
            FROM channel_messages
        """).fetchall()
    finally:
        conn.close()
    return {}

async def periodic_room_intelligence_task():
    while True:
        summary = refresh_all_room_dna()
        await asyncio.sleep(1200)
'''


def _load():
    spec = importlib.util.spec_from_file_location("fix_room_intel_blocking", MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class FixRoomIntelTest(unittest.TestCase):
    def setUp(self):
        self.fix = _load()

    def test_sweep_is_offloaded_and_indexed(self):
        out = self.fix.patch_room_intelligence(SNIPPET)
        self.assertIn("summary = await asyncio.to_thread(refresh_all_room_dna)", out)
        self.assertIn("idx_cm_sent_handle", out)
        self.assertIn("idx_cm_handle_sent", out)
        import ast
        ast.parse(out)

    def test_patch_is_idempotent(self):
        once = self.fix.patch_room_intelligence(SNIPPET)
        self.assertEqual(once, self.fix.patch_room_intelligence(once))

    def test_install_and_backup(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "room_intelligence.py").write_text(SNIPPET)
            self.assertIn("patched", self.fix.install(d))
            self.assertTrue((d / "room_intelligence.py.bak_room_intel").exists())
            self.assertIn("already fixed", self.fix.install(d))

    def test_install_refuses_unexpected_shape(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "room_intelligence.py").write_text("x = 1\n")
            self.assertIn("NOT patched", self.fix.install(d))
            self.assertEqual((d / "room_intelligence.py").read_text(), "x = 1\n")


if __name__ == "__main__":
    unittest.main()
