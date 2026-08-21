#!/usr/bin/env python3
"""AFFL XFP / FPOE: non-PPR, bucket vs fractional, no Savant FP import."""
import unittest

from affl_xfp import (AFFL_SKILL_RULES, expected_box, rules_from_rows,
                      score_box, week_xfp)


class Scoring(unittest.TestCase):
    def setUp(self):
        self.rules = {sid: pts for sid, (_n, pts) in AFFL_SKILL_RULES.items()}

    def test_rec_is_zero(self):
        self.assertEqual(self.rules[53], 0.0)
        box = {'rec_yards': 0, 'receptions': 8, 'rec_tds': 0}
        self.assertEqual(score_box(box, self.rules, 'FRACTIONAL'), 0.0)

    def test_fractional_2019(self):
        box = {'rec_yards': 100, 'receptions': 6, 'rec_tds': 1}
        # 10.0 yards + 6.0 TD + 0 rec = 16. Never 16 + 6 PPR.
        self.assertAlmostEqual(score_box(box, self.rules, 'FRACTIONAL'), 16.0)

    def test_bucket_2018(self):
        box = {'rec_yards': 19, 'receptions': 4, 'rec_tds': 0}
        self.assertEqual(score_box(box, self.rules, 'BUCKET'), 1.0)
        box19 = {'rec_yards': 19, 'receptions': 4, 'rec_tds': 0}
        self.assertAlmostEqual(score_box(box19, self.rules, 'FRACTIONAL'), 1.9)

    def test_pass_and_int(self):
        box = {'pass_yards': 250, 'pass_tds': 2, 'interceptions': 1}
        self.assertAlmostEqual(score_box(box, self.rules, 'FRACTIONAL'), 16.0)

    def test_forced_non_ppr_even_if_donor_says_otherwise(self):
        rules = rules_from_rows([(53, 1.0), (42, 0.1), (43, 6.0)])
        self.assertEqual(rules[53], 0.0)
        box = {'rec_yards': 50, 'receptions': 5, 'rec_tds': 0}
        self.assertAlmostEqual(score_box(box, rules, 'FRACTIONAL'), 5.0)


class Expected(unittest.TestCase):
    def setUp(self):
        self.rules = {sid: pts for sid, (_n, pts) in AFFL_SKILL_RULES.items()}

    def test_xtd_and_air_yac(self):
        box = {'rec_yards': 80, 'receptions': 5, 'rec_tds': 1}
        pbp = {'rec_air_yards': 60, 'xyac': 4.0, 'xyac_n': 5,
               'rec_xtd': 0.5, 'pass_xtd': 0, 'rush_xtd': 0}
        exp = expected_box(box, pbp)
        self.assertAlmostEqual(exp['rec_yards'], 80.0)  # 60 + 4*5
        self.assertAlmostEqual(exp['rec_tds'], 0.5)
        self.assertEqual(exp['receptions'], 5)
        fp, xfp, fpoe = week_xfp(box, pbp, self.rules, 'FRACTIONAL')
        self.assertAlmostEqual(fp, 14.0)    # 8.0 + 6
        self.assertAlmostEqual(xfp, 11.0)   # 8.0 + 3.0
        self.assertAlmostEqual(fpoe, 3.0)

    def test_no_ppr_keys(self):
        box = {'rec_yards': 10, 'receptions': 2}
        pbp = {'rec_air_yards': 10, 'rec_xtd': 0}
        fp, xfp, fpoe = week_xfp(box, pbp, self.rules, 'FRACTIONAL')
        for v in (fp, xfp, fpoe):
            self.assertIsInstance(v, float)


if __name__ == '__main__':
    unittest.main()
