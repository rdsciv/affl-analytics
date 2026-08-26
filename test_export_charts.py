#!/usr/bin/env python3
"""CHI-114 bind payloads: separate grains, NON-PPR, 2016–17 stay."""
import sqlite3
import unittest

from export_site import (player_season_xfp_payload, player_week_nfl_payload,
                         CHART_FIRST_YEAR, CHART_LAST_YEAR)


def _db():
    con = sqlite3.connect(':memory:')
    con.executescript("""
        CREATE TABLE dim_player (
          player_id INTEGER PRIMARY KEY, name TEXT, position TEXT, gsis_id TEXT);
        CREATE TABLE fact_player_xfp (
          season INTEGER, player_id INTEGER, fp REAL, xfp REAL, fpoe REAL,
          PRIMARY KEY (season, player_id));
        CREATE TABLE fact_pbp_agg (
          season INTEGER, week INTEGER, gsis_id TEXT,
          targets REAL, receptions REAL, rush_td REAL, pass_td REAL, rec_td REAL,
          pass_air_yards REAL, rec_air_yards REAL,
          PRIMARY KEY (season, week, gsis_id));
        CREATE TABLE fact_nfl_week (
          season INTEGER, week INTEGER, gsis_id TEXT,
          pass_yards REAL, rush_yards REAL,
          PRIMARY KEY (season, week, gsis_id));
    """)
    con.execute("INSERT INTO dim_player VALUES (3918298,'Josh Allen','QB','00-0034857')")
    # 2016–17 must export; 2013 is weekly-only (no nfl_week / xfp)
    con.execute("INSERT INTO fact_player_xfp VALUES (2016,3918298,10.0,8.0,2.0)")
    con.execute("INSERT INTO fact_player_xfp VALUES (2017,3918298,20.0,18.0,2.0)")
    con.execute("INSERT INTO fact_player_xfp VALUES (2025,3918298,364.6,324.4,40.2)")
    con.execute("""INSERT INTO fact_pbp_agg
        VALUES (2013,1,'00-0034857',0,0,1,2,0,99,88)""")
    con.execute("""INSERT INTO fact_pbp_agg
        VALUES (2016,4,'00-0034857',0,0,0,1,0,40,0)""")
    con.execute("""INSERT INTO fact_pbp_agg
        VALUES (2017,2,'00-0034857',3,2,0,0,1,12,9)""")
    con.execute("INSERT INTO fact_nfl_week VALUES (2016,4,'00-0034857',220.0,15.0)")
    con.execute("INSERT INTO fact_nfl_week VALUES (2017,2,'00-0034857',0.0,8.0)")
    con.execute("""INSERT INTO fact_pbp_agg
        VALUES (2025,1,'00-0034857',0,0,1,2,0,10,0)""")
    con.execute("INSERT INTO fact_nfl_week VALUES (2025,1,'00-0034857',304.0,39.0)")
    return con


class ChartPayloads(unittest.TestCase):
    def setUp(self):
        self.con = _db()

    def test_years_cover_savant_window(self):
        self.assertEqual(CHART_FIRST_YEAR, 2013)
        self.assertEqual(CHART_LAST_YEAR, 2025)

    def test_season_grain_does_not_mix_weeks(self):
        p = player_season_xfp_payload(self.con, 2025)
        self.assertEqual(p['grain'], 'season+player_id')
        self.assertEqual(p['scoring'], 'NON_PPR')
        self.assertTrue(p['recIsVolume'])
        row = p['rows'][0]
        self.assertEqual(set(row), {'season', 'player_id', 'fp', 'xfp', 'fpoe'})
        self.assertNotIn('week', row)
        self.assertNotIn('pass_yards', row)
        self.assertNotIn('targets', row)

    def test_week_grain_does_not_mix_xfp(self):
        p = player_week_nfl_payload(self.con, 2016)
        self.assertEqual(p['grain'], 'season+week+gsis_id')
        self.assertEqual(p['scoring'], 'NON_PPR')
        row = p['rows'][0]
        self.assertEqual(set(row), {
            'season', 'week', 'gsis_id', 'player_id',
            'targets', 'receptions', 'rush_td', 'pass_td', 'rec_td',
            'pass_yards', 'rush_yards',
        })
        self.assertNotIn('xfp', row)
        self.assertNotIn('fpoe', row)
        self.assertNotIn('fp', row)
        # air yards are not yards
        self.assertNotEqual(row['pass_yards'], 40)
        self.assertEqual(row['pass_yards'], 220.0)

    def test_does_not_drop_2016_or_2017(self):
        s16 = player_season_xfp_payload(self.con, 2016)
        s17 = player_season_xfp_payload(self.con, 2017)
        w16 = player_week_nfl_payload(self.con, 2016)
        w17 = player_week_nfl_payload(self.con, 2017)
        self.assertTrue(s16['rows'])
        self.assertTrue(s17['rows'])
        self.assertTrue(w16['rows'])
        self.assertTrue(w17['rows'])

    def test_2013_weekly_exists_without_xfp(self):
        self.assertIsNone(player_season_xfp_payload(self.con, 2013))
        w = player_week_nfl_payload(self.con, 2013)
        self.assertEqual(w['rows'][0]['pass_td'], 2)
        self.assertIsNone(w['rows'][0]['pass_yards'])

    def test_no_ppr_fields(self):
        for year in (2013, 2016, 2017, 2025):
            for payload in (player_season_xfp_payload(self.con, year),
                            player_week_nfl_payload(self.con, year)):
                if not payload:
                    continue
                blob = str(payload).lower()
                self.assertNotIn('half-ppr', blob)
                self.assertNotIn('half_ppr', blob)
                self.assertEqual(payload['scoring'], 'NON_PPR')
                for row in payload['rows']:
                    for k in row:
                        self.assertNotIn('ppr', k.lower())

    def test_receptions_are_volume_not_points(self):
        w = player_week_nfl_payload(self.con, 2017)
        rec = next(r for r in w['rows'] if r['receptions'])
        self.assertEqual(rec['receptions'], 2)
        self.assertNotIn('rec_pts', rec)


if __name__ == '__main__':
    unittest.main()
