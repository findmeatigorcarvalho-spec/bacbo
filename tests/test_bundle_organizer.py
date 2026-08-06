import os
import unittest

from bot.config.bundle_organizer import (
    organize,
    organizer_manifest,
    result_attach_immediate,
)
from bot.config.chat_router import ChatRouter


class BundleOrganizerTest(unittest.TestCase):
    def setUp(self):
        os.environ["BUNDLE_ORGANIZER"] = "1"
        os.environ["RESULT_ATTACH_IMMEDIATE"] = "1"
        os.environ["PROFIT_CHAT_BUNDLE"] = "1"
        os.environ["TELEGRAM_PRIMARY_PEER"] = "UNIQUE_g1"
        os.environ["TELEGRAM_EXCLUDE_PEERS"] = "Mr_iv4,6774605259"

    def test_manifest_one_ai(self):
        m = organizer_manifest()
        self.assertEqual(m["model"], "ONE_AI_ORGANIZER")
        self.assertTrue(m["result_attach_immediate"])
        self.assertTrue(result_attach_immediate())

    def test_enter_goes_apex(self):
        d = organize("🏆 GOLDEN SIGNAL — ENTER NOW\n⚡ ENTER NOW")
        self.assertEqual(d.peer, "UNIQUE_g1")
        self.assertEqual(d.becomes, "APEX")
        self.assertEqual(d.delayed_seconds, 0.0)
        self.assertNotIn(d.peer, {"Mr_iv4", "6774605259"})

    def test_flash_goes_precision(self):
        d = organize("⚡ FLASH SIGNAL\nAPOSTE AGORA", signal_kind="FLASH")
        self.assertEqual(d.peer, "UNIQUE_g2")
        self.assertEqual(d.becomes, "PRECISION")

    def test_timed_precision_mixes_to_apex(self):
        d = organize(
            "⚡ FLASH SIGNAL\nJANELA: 11s para apostar\n🟢 11s 🟢",
            signal_kind="FLASH",
        )
        self.assertEqual(d.peer, "UNIQUE_g1")
        self.assertTrue(any("PRECISION" in m or "mix" in m for m in d.mix))

    def test_result_glues_parent_immediate(self):
        d = organize(
            "✅ WIN — GOLDEN\nRESUMIDO FORENSE",
            role="RESULT",
            parent_peer="UNIQUE_g3",
            is_result=True,
        )
        self.assertEqual(d.peer, "UNIQUE_g3")
        self.assertTrue(d.glue_parent)
        self.assertEqual(d.delayed_seconds, 0.0)
        self.assertIn("immediate", d.why)

    def test_router_remembers_parent_for_result(self):
        for key in list(os.environ):
            if key.startswith("TELEGRAM_CAP_") or key.startswith("TELEGRAM_SHELF_OVERFLOW"):
                os.environ.pop(key, None)
        r = ChatRouter()
        now = 3_000_000.0
        fire = r.route(
            "🏆 GOLDEN SIGNAL — ENTER NOW\n⚡ ENTER NOW",
            signal_id="org1",
            now=now,
            commit=True,
        )
        self.assertEqual(fire.peer, "UNIQUE_g1")
        self.assertEqual(fire.delayed_seconds, 0.0)
        res = r.route(
            "🔔 ✅ GANHOU\n🔍 RESUMIDO FORENSE\n  Resultado: ✅ G0 WIN",
            signal_id="org1",
            now=now + 0.1,
            commit=True,
        )
        self.assertTrue(res.follow_parent)
        self.assertEqual(res.peer, fire.peer)
        self.assertEqual(res.delayed_seconds, 0.0)
        self.assertIn("immediate", res.reason)


if __name__ == "__main__":
    unittest.main()
