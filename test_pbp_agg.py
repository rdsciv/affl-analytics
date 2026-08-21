#!/usr/bin/env python3
"""Synthetic PBP → player-week facts. No network, no PPR."""
import csv
import io
import os
import tempfile
import unittest

from pbp_agg import aggregate_pbp, fit_xtd_rates, ptd, yardline_bucket
from export_site import _rank

HEADER = [
    'season', 'week', 'season_type', 'play_type', 'two_point_attempt',
    'passer_player_id', 'rusher_player_id', 'receiver_player_id',
    'complete_pass', 'pass_attempt', 'rush_attempt', 'sack',
    'air_yards', 'epa', 'success', 'cpoe',
    'yardline_100', 'touchdown', 'pass_touchdown', 'rush_touchdown',
    'xyac_mean_yardage',
]


def write_pbp(rows):
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=HEADER)
    w.writeheader()
    for r in rows:
        full = {k: '' for k in HEADER}
        full.update(r)
        w.writerow(full)
    path = tempfile.NamedTemporaryFile('w', suffix='.csv', delete=False)
    path.write(buf.getvalue())
    path.close()
    return path.name


def play(**kw):
    base = {
        'season': '2024', 'week': '1', 'season_type': 'REG',
        'play_type': 'pass', 'two_point_attempt': '0',
        'pass_attempt': '1', 'complete_pass': '0', 'sack': '0',
        'air_yards': '8', 'epa': '0.2', 'success': '1', 'cpoe': '2.5',
        'yardline_100': '2', 'touchdown': '0', 'pass_touchdown': '0',
        'rush_touchdown': '0', 'xyac_mean_yardage': '4',
        'passer_player_id': 'QB1', 'receiver_player_id': 'WR1',
    }
    base.update(kw)
    return base


class YardlineAndRates(unittest.TestCase):
    def test_buckets(self):
        self.assertEqual(yardline_bucket(1), '1-2')
        self.assertEqual(yardline_bucket(2), '1-2')
        self.assertEqual(yardline_bucket(10), '6-10')
        self.assertEqual(yardline_bucket(51), '51+')
        self.assertIsNone(yardline_bucket(None))

    def test_laplace(self):
        # 1 TD in 2 plays → (1+0.5)/(2+1) = 0.5
        self.assertAlmostEqual(ptd({('k',): [2, 1]}, ('k',)), 0.5)


class Aggregate(unittest.TestCase):
    def tearDown(self):
        if getattr(self, 'path', None) and os.path.exists(self.path):
            os.unlink(self.path)

    def test_pass_and_rush_xtd(self):
        rows = [
            play(complete_pass='1', touchdown='1', pass_touchdown='1', epa='1.5'),
            play(complete_pass='0', cpoe='-4', success='0', epa='-0.4'),
            play(play_type='run', rusher_player_id='RB1', passer_player_id='',
                 receiver_player_id='', rush_attempt='1', pass_attempt='0',
                 complete_pass='0', air_yards='', cpoe='',
                 touchdown='0', rush_touchdown='0', epa='0.1', success='1',
                 yardline_100='2'),
            # ignored: postseason, two-point, punt
            play(season_type='POST', complete_pass='1', pass_touchdown='1'),
            play(two_point_attempt='1', complete_pass='1', pass_touchdown='1'),
            play(play_type='punt', passer_player_id='', receiver_player_id=''),
        ]
        self.path = write_pbp(rows)
        rates = fit_xtd_rates(self.path)
        self.assertAlmostEqual(rates[(2024, 'pass', '1-2')], 0.5)
        # one rush play, no TD → (0+0.5)/(1+1) = 0.25
        self.assertAlmostEqual(rates[(2024, 'run', '1-2')], 0.25)

        agg = { (r['gsis_id'], r['week']): r for r in aggregate_pbp(self.path, rates) }
        qb = agg[('QB1', 1)]
        wr = agg[('WR1', 1)]
        rb = agg[('RB1', 1)]
        self.assertEqual(qb['dropbacks'], 2)
        self.assertEqual(qb['pass_td'], 1)
        self.assertAlmostEqual(qb['pass_xtd'], 1.0)  # 0.5 + 0.5
        self.assertEqual(wr['targets'], 2)
        self.assertEqual(wr['receptions'], 1)
        self.assertEqual(wr['rec_td'], 1)
        self.assertAlmostEqual(wr['rec_xtd'], 1.0)
        self.assertEqual(rb['rush_att'], 1)
        self.assertEqual(rb['rush_td'], 0)
        self.assertAlmostEqual(rb['rush_xtd'], 0.25)
        # volume only — no fantasy / PPR field
        for row in agg.values():
            self.assertNotIn('ppr', row)
            self.assertNotIn('ppr_points', row)
            self.assertNotIn('fantasy_points_ppr', row)

    def test_cpoe_average(self):
        rows = [
            play(cpoe='10', complete_pass='1'),
            play(cpoe='-2', complete_pass='0', success='0'),
        ]
        self.path = write_pbp(rows)
        qb = next(r for r in aggregate_pbp(self.path) if r['gsis_id'] == 'QB1')
        self.assertAlmostEqual(qb['cpoe'], 4.0)
        self.assertEqual(qb['cpoe_n'], 2)


class Ranks(unittest.TestCase):
    def test_competition_rank(self):
        self.assertEqual(_rank([10, 30, 20]), [3, 1, 2])
        self.assertEqual(_rank([10, 10, 5]), [1, 1, 3])
        self.assertEqual(_rank([1, None, 3]), [2, None, 1])


if __name__ == '__main__':
    unittest.main()
