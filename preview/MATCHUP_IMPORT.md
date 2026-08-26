# 2025 matchup import

Generated 2026-08-16 14:34 CT from `affl.db`. This is the data. Not the website.

The 2025 scoreboard already lived in `fact_matchup` from the ESPN box
cache (`data/box_2025.json`). CHI-24 adds a versioned adapter, a source
checksum, an import-run row, and pairing gates. Re-importing does not
change the scores.

## What landed

- **202 sides** (101 games), **12 teams**, weeks 1–17
- Regular season (weeks 1–14): every week has 12 teams / 6 games. No holes.
- Week 15 has 10 teams / 5 games because the #1 and #2 seeds have a first-round bye. That is what should have happened, not a missing pairing.
- Weeks 16–17: 12 teams / 6 games.

| week | sides | teams | games | playoff_sides |
| --- | --- | --- | --- | --- |
| 1 | 12 | 12 | 6 | 0 |
| 2 | 12 | 12 | 6 | 0 |
| 3 | 12 | 12 | 6 | 0 |
| 4 | 12 | 12 | 6 | 0 |
| 5 | 12 | 12 | 6 | 0 |
| 6 | 12 | 12 | 6 | 0 |
| 7 | 12 | 12 | 6 | 0 |
| 8 | 12 | 12 | 6 | 0 |
| 9 | 12 | 12 | 6 | 0 |
| 10 | 12 | 12 | 6 | 0 |
| 11 | 12 | 12 | 6 | 0 |
| 12 | 12 | 12 | 6 | 0 |
| 13 | 12 | 12 | 6 | 0 |
| 14 | 12 | 12 | 6 | 0 |
| 15 | 10 | 10 | 5 | 10 |
| 16 | 12 | 12 | 6 | 12 |
| 17 | 12 | 12 | 6 | 12 |

## Provenance (latest runs)

| run_id | adapter | adapter_version | season | status | row_count | finished_at | path | sha256 | bytes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 3 | espn_box | v1 | 2025 | ok | 202 | 2026-08-16T19:34:09+00:00 | data/box_2025.json | 8cb77c0bdbb4fa004d1d501244b03fe5b4170af08cac56733840ac533b2984a0 | 99907 |
| 3 | espn_box | v1 | 2025 | ok | 202 | 2026-08-16T19:34:09+00:00 | data/league_2025.json | c4510757cf5e4d216056869614d06a871cffb7dd3fc7850324f12fe19c203411 | 969299 |
| 2 | espn_box | v1 | 2025 | ok | 202 | 2026-08-16T19:34:09+00:00 | data/box_2025.json | 8cb77c0bdbb4fa004d1d501244b03fe5b4170af08cac56733840ac533b2984a0 | 99907 |
| 2 | espn_box | v1 | 2025 | ok | 202 | 2026-08-16T19:34:09+00:00 | data/league_2025.json | c4510757cf5e4d216056869614d06a871cffb7dd3fc7850324f12fe19c203411 | 969299 |
| 1 | espn_box | v1 | 2025 | ok | 202 | 2026-08-16T19:33:58+00:00 | data/box_2025.json | 8cb77c0bdbb4fa004d1d501244b03fe5b4170af08cac56733840ac533b2984a0 | 99907 |
| 1 | espn_box | v1 | 2025 | ok | 202 | 2026-08-16T19:33:58+00:00 | data/league_2025.json | c4510757cf5e4d216056869614d06a871cffb7dd3fc7850324f12fe19c203411 | 969299 |

Checksum is SHA-256 of the on-disk cache. Secrets stay in `.env` and are not in this file.
