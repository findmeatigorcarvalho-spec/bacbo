import csv
import tempfile
import unittest
from pathlib import Path

from bot.config.skin_census import (
    _normalize_archaeology_type_id,
    build_census,
    write_csv,
)


class SkinCensusTest(unittest.TestCase):
    def test_collapse_janela_and_banners(self):
        self.assertEqual(
            _normalize_archaeology_type_id("FIRE_JANELA_11S_SOLO_ELITE")[0],
            "FIRE_JANELA_TIMED",
        )
        self.assertEqual(
            _normalize_archaeology_type_id("RESULT_BANNER_TIE_FOO")[0],
            "RESULT_BANNER_FAMILY",
        )
        self.assertEqual(
            _normalize_archaeology_type_id("OPS_AUTO_QUARANTINE_X")[0],
            "OPS_ROOM_QUARANTINE",
        )

    def test_build_census_from_tiny_tg_csv(self):
        with tempfile.TemporaryDirectory() as td:
            tg = Path(td) / "types_first_seen.csv"
            with tg.open("w", encoding="utf-8", newline="") as fh:
                w = csv.DictWriter(
                    fh,
                    fieldnames=[
                        "type_id",
                        "role",
                        "lane",
                        "clocks",
                        "first_date_utc",
                        "first_chat",
                        "first_msg_id",
                        "count",
                        "first_line",
                        "note",
                    ],
                )
                w.writeheader()
                w.writerow(
                    {
                        "type_id": "FIRE_SOLO_ELITE_SIGNAL",
                        "role": "FIRE",
                        "lane": "",
                        "clocks": "",
                        "first_date_utc": "2026-03-19 21:55:00",
                        "first_chat": "x",
                        "first_msg_id": "1",
                        "count": "12",
                        "first_line": "💎 SOLO ELITE SIGNAL 💎",
                        "note": "",
                    }
                )
                w.writerow(
                    {
                        "type_id": "FIRE_JANELA_17S_GOLDEN",
                        "role": "FIRE",
                        "lane": "COUNTDOWN",
                        "clocks": "17",
                        "first_date_utc": "2026-03-21 15:45:00",
                        "first_chat": "x",
                        "first_msg_id": "2",
                        "count": "3",
                        "first_line": "JANELA: 17s para apostar",
                        "note": "",
                    }
                )
            census = build_census(
                tg_csv=tg,
                db_path=Path(td) / "missing.db",
                code_roots=[Path("/workspace/bot/config")],
            )
            ids = {r["floor_id"]: r for r in census["floors"]}
            self.assertIn("FIRE_SOLO_ELITE_ENTER", ids)
            self.assertTrue(ids["FIRE_SOLO_ELITE_ENTER"]["seen_telegram"])
            self.assertIn("FIRE_JANELA_TIMED", ids)
            self.assertGreaterEqual(ids["FIRE_JANELA_TIMED"]["tg_count"], 3)
            out = Path(td) / "out.csv"
            write_csv(census, out)
            self.assertTrue(out.exists())


if __name__ == "__main__":
    unittest.main()
