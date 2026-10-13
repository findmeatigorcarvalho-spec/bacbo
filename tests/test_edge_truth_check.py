import importlib.util
import sqlite3
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path("/workspace/replit_elite_stack_patch/bot/edge_truth_check.py")


def _load_module():
    spec = importlib.util.spec_from_file_location("edge_truth_check", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _make_db(path: str, rows) -> None:
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE consensus_signals("
        "id INTEGER PRIMARY KEY, signal_kind TEXT, color TEXT, outcome TEXT,"
        " secs_to_result REAL, fired_at TEXT)"
    )
    conn.executemany(
        "INSERT INTO consensus_signals(signal_kind,color,outcome,secs_to_result,fired_at)"
        " VALUES(?,?,?,?,'2026-10-13 00:00:00')",
        rows,
    )
    conn.commit()
    conn.close()


@unittest.skipUnless(MODULE_PATH.exists(), "edge check module not present")
class EdgeTruthCheckTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = _load_module()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = str(Path(self.tmp.name) / "bacbo.db")

    def _kind(self, rep, name):
        return next(k for k in rep["by_kind"] if k["signal_kind"] == name)

    def test_stray_wins_do_not_create_an_edge(self):
        """A high overall WR built from late grading must not pass the filter."""
        rows = [("S", "blue", "win", 900.0)] * 400
        rows += [("S", "blue", "win", 20.0)] * 100
        rows += [("S", "blue", "loss", 20.0)] * 100
        _make_db(self.db, rows)
        rep = self.mod.build_report(self.db)
        k = self._kind(rep, "S")
        self.assertGreater(k["overall_wr_pct"], 80)
        self.assertEqual(k["forward_wr_pct"], 50.0)
        self.assertEqual(k["verdict"], "NO_EDGE_AT_95PCT")
        self.assertEqual(rep["conclusion"]["systems_with_surviving_edge"], [])

    def test_real_forward_edge_is_reported(self):
        rows = [("R", "blue", "win", 20.0)] * 400 + [("R", "blue", "loss", 20.0)] * 200
        _make_db(self.db, rows)
        rep = self.mod.build_report(self.db)
        k = self._kind(rep, "R")
        self.assertEqual(k["verdict"], "EDGE_SURVIVES_FORWARD_FILTER")
        self.assertIn("R", rep["conclusion"]["systems_with_surviving_edge"])

    def test_small_forward_sample_is_not_a_verdict(self):
        rows = [("T", "blue", "win", 20.0)] * 8
        _make_db(self.db, rows)
        rep = self.mod.build_report(self.db)
        self.assertEqual(
            self._kind(rep, "T")["verdict"], "INSUFFICIENT_FORWARD_SAMPLE"
        )

    def test_ties_excluded_from_win_rate_denominator(self):
        rows = [("U", "blue", "win", 20.0)] * 50
        rows += [("U", "blue", "loss", 20.0)] * 50
        rows += [("U", "blue", "tie", 20.0)] * 100
        _make_db(self.db, rows)
        rep = self.mod.build_report(self.db)
        fwd = self._kind(rep, "U")["buckets"]["FORWARD"]
        self.assertEqual(fwd["n"], 200)
        self.assertEqual(fwd["decided"], 100)
        self.assertEqual(fwd["wr_pct"], 50.0)

    def test_lag_buckets_split_on_round_length(self):
        rows = [
            ("V", "blue", "win", 1.0),
            ("V", "blue", "win", 20.0),
            ("V", "blue", "win", 500.0),
        ]
        _make_db(self.db, rows)
        lag = self.mod.build_report(self.db)["lag_shape"]
        self.assertEqual((lag["instant"], lag["forward"], lag["stray"]), (1, 1, 1))

    def test_missing_ground_truth_tables_report_as_absent(self):
        _make_db(self.db, [("W", "blue", "win", 20.0)])
        gt = self.mod.build_report(self.db)["ground_truth"]
        self.assertIsNone(gt["casino_round_results"])
        self.assertFalse(gt["has_ground_truth"])

    def test_wrong_db_is_reported_not_crashed(self):
        conn = sqlite3.connect(self.db)
        conn.execute("CREATE TABLE unrelated(a)")
        conn.commit()
        conn.close()
        rep = self.mod.build_report(self.db)
        self.assertIn("consensus_signals missing", rep["error"])
        self.assertIn("[EDGE-TRUTH] ERROR", self.mod.render(rep))

    def test_db_is_never_written(self):
        rows = [("X", "blue", "win", 20.0)] * 40
        _make_db(self.db, rows)
        before = Path(self.db).read_bytes()
        self.mod.build_report(self.db)
        self.assertEqual(Path(self.db).read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
