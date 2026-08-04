import os
import unittest

from bot.config.chat_router import ChatRouter, overflow_peers


class ChatRouterTest(unittest.TestCase):
    def test_default_overflow_is_unique_g2_to_g5(self):
        # Clear overflow env so defaults apply.
        for key in list(os.environ):
            if key.startswith("TELEGRAM_SHELF_OVERFLOW"):
                os.environ.pop(key, None)
        peers = overflow_peers()
        self.assertEqual(peers, ["UNIQUE_g2", "UNIQUE_g3", "UNIQUE_g4", "UNIQUE_g5"])

    def test_delay_not_drop_when_all_saturated(self):
        for key in list(os.environ):
            if key.startswith("TELEGRAM_SHELF_OVERFLOW"):
                os.environ.pop(key, None)
        # Tiny capacity so saturation is easy.
        os.environ["TELEGRAM_CAP_UPPER_MONEY"] = "1"
        os.environ["TELEGRAM_CAP_OVERFLOW"] = "1"
        r = ChatRouter()
        now = 1_000_000.0
        text = "🏆 GOLDEN SIGNAL — ENTER NOW 🏆\n⚡ ENTER NOW — 3 ROOM(S) CONFIRMED"
        # Fill primary + 4 overflow slots (g2..g5) at 1 card/min each.
        for i in range(5):
            t = r.route(text, signal_id=f"s{i}", now=now, commit=True)
            self.assertEqual(t.delayed_seconds, 0.0)
            self.assertFalse(t.suppressed)
        # Next card must DELAY on primary — never drop.
        delayed = r.route(text, signal_id="s_delay", now=now, commit=True)
        self.assertGreater(delayed.delayed_seconds, 0.0)
        self.assertFalse(delayed.suppressed)
        self.assertIn("delayed_all_saturated", delayed.reason)
        # Cleanup env overrides.
        os.environ.pop("TELEGRAM_CAP_UPPER_MONEY", None)
        os.environ.pop("TELEGRAM_CAP_OVERFLOW", None)

    def test_result_glues_to_overflow_chat(self):
        for key in list(os.environ):
            if key.startswith("TELEGRAM_SHELF_OVERFLOW"):
                os.environ.pop(key, None)
        os.environ["TELEGRAM_CAP_UPPER_MONEY"] = "1"
        r = ChatRouter()
        now = 2_000_000.0
        fire = "🏆 GOLDEN SIGNAL — ENTER NOW 🏆\n⚡ ENTER NOW — 3 ROOM(S) CONFIRMED"
        r.route(fire, signal_id="parent1", now=now, commit=True)  # fills primary
        spilled = r.route(fire, signal_id="parent2", now=now, commit=True)
        self.assertEqual(spilled.peer, "UNIQUE_g2")
        result = (
            "🔔 ✅ GANHOU  ·  #99\n"
            "🔍 SINAL #99 — RESUMIDO FORENSE\n"
            "  Resultado: ✅ G0 WIN"
        )
        glued = r.route(result, signal_id="parent2", now=now + 1, commit=True)
        self.assertTrue(glued.follow_parent)
        self.assertEqual(glued.peer, "UNIQUE_g2")
        os.environ.pop("TELEGRAM_CAP_UPPER_MONEY", None)


if __name__ == "__main__":
    unittest.main()
