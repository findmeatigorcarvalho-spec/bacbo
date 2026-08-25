import os
import unittest

from bot.config.chat_router import ChatRouter, elastic_overflow_peer, overflow_peers


class ChatRouterTest(unittest.TestCase):
    def test_default_overflow_is_unique_g2_to_g5(self):
        for key in list(os.environ):
            if key.startswith("TELEGRAM_SHELF_OVERFLOW"):
                os.environ.pop(key, None)
        peers = overflow_peers()
        self.assertEqual(peers, ["UNIQUE_g2", "UNIQUE_g3", "UNIQUE_g4", "UNIQUE_g5"])

    def test_elastic_mints_g6_never_delays(self):
        """Time-sensitive fires must never wait — mint UNIQUE_g6+ instead."""
        for key in list(os.environ):
            if key.startswith("TELEGRAM_SHELF_OVERFLOW") or key.startswith("TELEGRAM_CAP_"):
                os.environ.pop(key, None)
        os.environ["TELEGRAM_CAP_UPPER_MONEY"] = "1"
        os.environ["TELEGRAM_CAP_OVERFLOW"] = "1"
        r = ChatRouter()
        now = 1_000_000.0
        text = "🏆 GOLDEN SIGNAL — ENTER NOW 🏆\n⚡ ENTER NOW — 3 ROOM(S) CONFIRMED"
        # Fill primary + UNIQUE_g2..g5 (1 card/min each) = 5 immediate sends.
        for i in range(5):
            t = r.route(text, signal_id=f"s{i}", now=now, commit=True)
            self.assertEqual(t.delayed_seconds, 0.0)
            self.assertFalse(t.suppressed)
        # Next must mint UNIQUE_g6 immediately — NOT delay.
        minted = r.route(text, signal_id="s_mint", now=now, commit=True)
        self.assertEqual(minted.delayed_seconds, 0.0)
        self.assertFalse(minted.suppressed)
        self.assertEqual(minted.peer, "UNIQUE_g6")
        self.assertIn("elastic_mint", minted.reason)
        os.environ.pop("TELEGRAM_CAP_UPPER_MONEY", None)
        os.environ.pop("TELEGRAM_CAP_OVERFLOW", None)

    def test_elastic_overflow_peer_helper(self):
        self.assertEqual(elastic_overflow_peer(["UNIQUE_g2", "UNIQUE_g5"]), "UNIQUE_g6")

    def test_result_glues_to_overflow_chat(self):
        for key in list(os.environ):
            if key.startswith("TELEGRAM_SHELF_OVERFLOW") or key.startswith("TELEGRAM_CAP_"):
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
