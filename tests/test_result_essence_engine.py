import os
import unittest

from bot.config.result_essence_engine import (
    build_atlas,
    essence_for_text,
    family_ai_manifest,
    load_atlas,
)
from bot.config.bundle_organizer import organize


class ResultEssenceEngineTest(unittest.TestCase):
    def setUp(self):
        os.environ["RESULT_ESSENCE_ENGINE"] = "1"
        os.environ["PROFIT_FAMILY_AI"] = "1"
        os.environ["BUNDLE_ORGANIZER"] = "1"

    def test_atlas_scores_keep(self):
        atlas = load_atlas()
        self.assertGreaterEqual(atlas["stats"]["keep_scored"], 700)
        self.assertGreaterEqual(atlas["stats"]["result_keep"], 100)
        self.assertTrue(atlas.get("invent_directives"))
        self.assertEqual(atlas["invent_directives"][0]["action"], "BUNDLE_PURPOSE")

    def test_solo_elite_essence(self):
        e = essence_for_text(
            "💎 SOLO ELITE SIGNAL 💎\n⚡ ENTER NOW", signal_kind="SOLO_ELITE"
        )
        self.assertIsNotNone(e)
        self.assertEqual(e.get("becomes_home"), "APEX")
        self.assertGreater(float(e.get("profit_score") or 0), 5.0)

    def test_organizer_uses_essence(self):
        d = organize("💎 SOLO ELITE SIGNAL 💎\n⚡ ENTER NOW", signal_kind="SOLO_ELITE")
        self.assertEqual(d.peer, "UNIQUE_g1")
        self.assertIn("essence", d.why)

    def test_manifest_layers(self):
        m = family_ai_manifest()
        self.assertEqual(m["model"], "PROFIT_FAMILY_AI")
        self.assertIn("2000pct", m["layers"])
        self.assertTrue(m["enabled"])

    def test_result_still_immediate(self):
        d = organize(
            "✅ WIN — SOLO_ELITE",
            role="RESULT",
            parent_peer="UNIQUE_g2",
            is_result=True,
        )
        self.assertEqual(d.peer, "UNIQUE_g2")
        self.assertEqual(d.delayed_seconds, 0.0)


if __name__ == "__main__":
    unittest.main()
