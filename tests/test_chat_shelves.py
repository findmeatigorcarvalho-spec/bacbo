import unittest

from bot.config.chat_shelves import (
    SHELF_COUNTDOWN,
    SHELF_OPS_EXPIRE,
    SHELF_PENTHOUSE_MONEY,
    SHELF_UPPER_MONEY,
    resolve_shelf,
)
from bot.config.skin_families import classify_telegram_skin


class ChatShelvesTest(unittest.TestCase):
    def test_solo_penthouse(self):
        d = resolve_shelf("💎 SOLO ELITE SIGNAL 💎\n⚡ ENTER NOW")
        self.assertEqual(d.family_id, "FIRE_SOLO_ELITE_ENTER")
        self.assertEqual(d.shelf_id, SHELF_PENTHOUSE_MONEY)

    def test_golden_upper_money(self):
        d = resolve_shelf(
            "🏆 GOLDEN SIGNAL — ENTER NOW 🏆\n"
            "Rooms in consensus (3):\n⚡ ENTER NOW — 3 ROOM(S) CONFIRMED"
        )
        self.assertEqual(d.family_id, "FIRE_GOLDEN_ENTER")
        self.assertEqual(d.shelf_id, SHELF_UPPER_MONEY)

    def test_sinal_retido_countdown_not_just_db_kind(self):
        text = (
            "⏳ *Sinal Retido → Liberado* _(recuperação concluída)_\n"
            "📌 CONFIG: SOLO ELITE\n"
            "🔴 JANELA: 1s para apostar\n"
            "🟢 1s 🟢\n"
            "💎 SOLO ELITE — APOSTAR 🔴 VERMELHO"
        )
        skin = classify_telegram_skin(text)
        self.assertEqual(skin.family_id, "FIRE_SINAL_RETIDO_LIBERADO")
        self.assertEqual(skin.lane, "COUNTDOWN")
        d = resolve_shelf(text)
        self.assertEqual(d.shelf_id, SHELF_COUNTDOWN)
        self.assertEqual(d.kind, "SOLO_ELITE")

    def test_forensic_follows_parent_countdown(self):
        text = (
            "🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴\n"
            "🔔 ✅ GANHOU  ·  #49015\n"
            "🔍 SINAL #49015 — RESUMIDO FORENSE\n"
            "  Tipo: SOLO_ELITE · Cor: VERMELHO (Banker)\n"
            "  ⏱ Intervalo: 132.4s\n"
            "  Resultado: ✅ G0 WIN\n"
            "📋 ✅  GANHOU NO G0"
        )
        skin = classify_telegram_skin(text)
        self.assertEqual(skin.family_id, "RESULT_FORENSIC_INTERVALO")
        d = resolve_shelf(
            text, parent_shelf=SHELF_COUNTDOWN, parent_lane="COUNTDOWN"
        )
        self.assertTrue(d.follow_parent)
        self.assertEqual(d.shelf_id, SHELF_COUNTDOWN)

    def test_g1_expirou_and_g2_miss(self):
        g1 = classify_telegram_skin(
            "⏰ G1 EXPIROU — VERIFICAR SUA MESA\n"
            "PASSO A PASSO — O QUE FAZER AGORA"
        )
        self.assertEqual(g1.family_id, "OPS_G1_EXPIROU")
        g2 = classify_telegram_skin(
            "🛑 G2 MISS — PERDA TOTAL — PARE AGORA\n❌ G0 → ❌ G1 → ❌ G2"
        )
        self.assertEqual(g2.family_id, "OPS_G2_MISS")
        d = resolve_shelf(
            "⏰ G1 EXPIROU — VERIFICAR SUA MESA",
            parent_shelf=SHELF_UPPER_MONEY,
        )
        self.assertEqual(d.shelf_id, SHELF_UPPER_MONEY)
        self.assertTrue(d.follow_parent)

    def test_short_win_not_only_solo(self):
        for kind in ("SOLO_ELITE", "SEQUENCE", "GOLDEN"):
            d = resolve_shelf(
                f"✅ WIN — {kind}\n🏆 G0 — Acertou de primeira!",
                parent_shelf=SHELF_UPPER_MONEY,
            )
            self.assertEqual(d.family_id, "RESULT_WIN_TIER")
            self.assertEqual(d.kind, kind)
            self.assertEqual(d.shelf_id, SHELF_UPPER_MONEY)

    def test_catalog_lists_countdown_and_forensic(self):
        from bot.config.chat_shelves import shelf_catalog

        ids = {s["shelf_id"] for s in shelf_catalog()}
        self.assertIn(SHELF_COUNTDOWN, ids)
        self.assertIn(SHELF_OPS_EXPIRE, ids)
        self.assertIn(SHELF_PENTHOUSE_MONEY, ids)


if __name__ == "__main__":
    unittest.main()
