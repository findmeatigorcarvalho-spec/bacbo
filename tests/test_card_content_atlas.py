import csv
import importlib.util
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path("/workspace/replit_elite_stack_patch/bot/card_content_atlas.py")


def _load_module():
    spec = importlib.util.spec_from_file_location("card_content_atlas", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@unittest.skipUnless(MODULE_PATH.exists(), "atlas module not present")
class CardContentAtlasTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = _load_module()

    def test_skeleton_collapses_numeric_and_room_variants(self):
        a = "reicassinofs          +rqdados1                n= 11 WR=100.0%"
        b = "bacbobrl              +robobacbodados          n= 47 WR= 61.2%"
        self.assertEqual(self.mod.skeleton(a), self.mod.skeleton(b))

    def test_skeleton_keeps_genuinely_different_designs_apart(self):
        a = "💎 SOLO ELITE SIGNAL 💎"
        b = "🏆 GOLDEN SIGNAL — ENTER NOW 🏆"
        self.assertNotEqual(self.mod.skeleton(a), self.mod.skeleton(b))

    def test_claim_pairs_colocated_rate_and_sample(self):
        """A multi-stat card must not have its best rate paired with its smallest n."""
        body = "@footballstudiodice01   n= 133 W=100 L= 27 T= 6 WR= 79.7% | b=86.4%(n=22)"
        wr, n = self.mod.primary_claim(body)
        self.assertEqual(n, 133)
        self.assertEqual(wr, 79.7)

    def test_claim_reads_suffixed_rate_form(self):
        body = "🔴 accum_solo_tier    n=   6 W=  6/L=  0/T= 0  sWR=100.0%  net=-"
        self.assertEqual(self.mod.primary_claim(body), (100.0, 6))

    def test_claim_absent_when_card_states_no_rate(self):
        self.assertEqual(self.mod.primary_claim("💎 SOLO ELITE SIGNAL 💎"), (None, None))

    def test_rate_without_sample_is_flagged_separately(self):
        wr, n = self.mod.primary_claim("🏆 CERTIFIED ELITE — 100% G0 HISTÓRICO 🏆")
        self.assertEqual(wr, 100.0)
        self.assertIsNone(n)
        self.assertEqual(self.mod.claim_verdict(wr, n), "CLAIM_WITHOUT_SAMPLE_SIZE")

    def test_thin_sample_never_counts_as_evidence(self):
        for n in (6, 11, 20, 99):
            self.assertEqual(
                self.mod.claim_verdict(100.0, n), "CLAIM_ON_THIN_SAMPLE", f"n={n}"
            )

    def test_large_sample_near_breakeven_is_noise(self):
        self.assertEqual(self.mod.claim_verdict(51.0, 500), "CLAIM_WITHIN_NOISE")

    def test_large_sample_clear_of_breakeven_survives(self):
        self.assertEqual(
            self.mod.claim_verdict(78.9, 1085), "CLAIM_SURVIVES_ITS_OWN_SAMPLE"
        )

    def test_map_rate_fractions_render_as_percent(self):
        self.assertEqual(self.mod._as_pct(0.1584), 15.84)
        self.assertEqual(self.mod._as_pct(89.25), 89.25)
        self.assertIsNone(self.mod._as_pct(None))

    def test_bet_instruction_detected_from_body(self):
        self.assertTrue(self.mod.features("⚡ **ENTER NOW**")["instructs_bet"])
        self.assertTrue(self.mod.features("🎯 Aposte no EMPATE")["instructs_bet"])
        self.assertFalse(self.mod.features("🟢 UserBot ONLINE 🟢")["instructs_bet"])

    def test_room_pair_setups_are_identified(self):
        f = self.mod.features("reicassinofs          +rqdados1                n= 11 WR=100.0%")
        self.assertEqual(f["room_pair"], "reicassinofs+rqdados1")

    def test_report_covers_every_card_and_no_perfect_claim_has_real_evidence(self):
        rep = self.mod.build_report()
        self.assertEqual(rep["totals"]["card_types"], 827)
        self.assertEqual(len(rep["cards"]), 827)
        self.assertLess(rep["totals"]["distinct_designs"], rep["totals"]["card_types"])
        self.assertLessEqual(
            rep["claims"]["perfect_claims_max_n"], self.mod.MIN_CREDIBLE_N
        )

    def test_claimed_rate_declines_as_sample_grows(self):
        """The overfitting signature: the smallest samples carry the biggest claims."""
        rep = self.mod.build_report()
        buckets = rep["claims"]["by_sample_size"]
        self.assertGreater(buckets[0]["mean_wr_pct"], buckets[-1]["mean_wr_pct"])
        self.assertGreater(rep["claims"]["mean_wr_drop_smallest_to_largest_bucket"], 0)

    def test_perfect_cells_are_priced_against_the_search(self):
        """A 100% room pair is meaningless if scanning all pairs hands out more."""
        sm = self.mod.build_report()["selection_math"]
        self.assertGreater(sm["source_rooms_in_corpus"], 1)
        self.assertEqual(
            sm["candidate_pairs"],
            sm["source_rooms_in_corpus"] * (sm["source_rooms_in_corpus"] - 1) // 2,
        )
        self.assertGreater(
            sm["perfect_cells_expected_by_chance"], sm["perfect_cells_observed"]
        )
        self.assertEqual(sm["verdict"], "FEWER_PERFECT_CELLS_THAN_CHANCE_PRODUCES")

    def test_room_vocabulary_excludes_plain_words(self):
        vocab = self.mod.room_vocabulary()
        for word in ("historical", "combinado", "vermelho", "sequencia", "entrada"):
            self.assertNotIn(word, vocab)

    def test_csv_has_a_row_per_card(self):
        rep = self.mod.build_report()
        with tempfile.TemporaryDirectory() as td:
            path = str(Path(td) / "atlas.csv")
            self.mod.write_csv(rep["cards"], path)
            with open(path, encoding="utf-8") as fh:
                rows = list(csv.DictReader(fh))
        self.assertEqual(len(rows), 827)
        self.assertIn("claim_verdict", rows[0])
        self.assertIn("instructs_bet", rows[0])


if __name__ == "__main__":
    unittest.main()
