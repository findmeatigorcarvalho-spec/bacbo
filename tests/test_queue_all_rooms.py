import importlib.util
import sqlite3
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parent.parent / "replit_elite_stack_patch" / "bot" / "queue_all_rooms.py"


def _load():
    spec = importlib.util.spec_from_file_location("queue_all_rooms", MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _make_db(path, col="handle"):
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE rooms (%s TEXT, status TEXT)" % col)
    conn.executemany("INSERT INTO rooms VALUES (?, 'active')",
                     [("@RoomA",), ("roomb",), ("@ROOMA",), ("",), (None,)])
    conn.commit()
    conn.close()


class QueueAllRoomsTest(unittest.TestCase):
    def setUp(self):
        self.q = _load()

    def test_handles_normalised_and_deduped(self):
        with tempfile.TemporaryDirectory() as d:
            db = Path(d) / "bacbo.db"
            _make_db(db)
            self.assertEqual(self.q.db_handles(db), ["rooma", "roomb"])

    def test_alternate_handle_column(self):
        with tempfile.TemporaryDirectory() as d:
            db = Path(d) / "bacbo.db"
            _make_db(db, col="username")
            self.assertEqual(self.q.db_handles(db), ["rooma", "roomb"])

    def test_queue_merges_without_duplicates(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            db = d / "bacbo.db"
            _make_db(db)
            targets = d / "data" / "slow_join_targets.txt"
            targets.parent.mkdir()
            targets.write_text("rooma\n")
            r = self.q.queue(db, targets)
            self.assertEqual(r, {"db_rooms": 2, "already_queued": 1, "added": 1})
            self.assertEqual(self.q.queue(db, targets)["added"], 0)
            self.assertEqual(sorted(targets.read_text().split()), ["rooma", "roomb"])


if __name__ == "__main__":
    unittest.main()
