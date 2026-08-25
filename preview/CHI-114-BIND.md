# CHI-114 bind files (Ork, no local tree)

Ork's `~/Projects/ccDesktopAFFL` is offline. Bind player/team Savant-style
charts from this branch (`verify/full-audit`). Do not scrape Savant `/fantasy`.
Do not import its FP / XFP / PPR / half-PPR columns.

## Files

Year bundles on this branch, one object per grain (never mixed):

| Year | Bundle | Season grain | Week grain |
| --- | --- | --- | --- |
| 2013–2025 | `site/years/{year}.json` | `playerSeasonXfp` | `playerWeekNfl` |

2016 and 2017 are included. 2013 is NFL-only (`nflOnly: true`); AFFL starts 2014.

## Objects

`playerSeasonXfp` — `grain: "season+player_id"` — source `fact_player_xfp`

- Keys: `season`, `player_id`
- Fields: `fp`, `xfp`, `fpoe` (AFFL, non-PPR)
- No week, no yards, no TDs

`playerWeekNfl` — `grain: "season+week+gsis_id"` — rows are `fact_pbp_agg` keys

- Keys: `season`, `week`, `gsis_id` (`player_id` is a `dim_player` join, may be null)
- From `fact_pbp_agg`: `targets`, `receptions`, `rush_td`, `pass_td`, `rec_td`
- Left-joined from `fact_nfl_week`: `pass_yards`, `rush_yards` (2013 has plays, no weekly box — yards are null)
- No `xfp` / `fpoe` / `fp`. Do not treat `pass_air_yards` / `rec_air_yards` as yards.

Both objects: `scoring: "NON_PPR"`, `recIsVolume: true`. Receptions are volume.

Savant `/fantasy` std is a comparison UI, not the AFFL scoring source.
