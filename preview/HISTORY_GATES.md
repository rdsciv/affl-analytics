# Historical completeness gates

CHI-36 / AFFL-016. Flags on `dim_season` must match actual counts. Missing stays missing.

2014-2017 are the one exception: `has_rosters` means full rosters *including bench* and
stays 0, while `roster_weeks` counts recovered starters. See `CONTRACTS.md`.

| season | teams | reg_weeks | auction | rosters | tx | matchups | roster_weeks | draft | transactions |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2014 | 10 | 13 | 0 | 0 | 0 | 150 | 1277 | 160 | 0 |
| 2015 | 10 | 13 | 0 | 0 | 0 | 150 | 1250 | 160 | 0 |
| 2016 | 10 | 13 | 1 | 0 | 0 | 150 | 1277 | 160 | 0 |
| 2017 | 12 | 13 | 1 | 0 | 0 | 190 | 1726 | 180 | 0 |
| 2018 | 12 | 13 | 1 | 1 | 1 | 190 | 2850 | 180 | 4326 |
| 2019 | 12 | 13 | 1 | 1 | 1 | 190 | 2849 | 180 | 1506 |
| 2020 | 12 | 13 | 1 | 1 | 1 | 190 | 2849 | 180 | 2071 |
| 2021 | 12 | 14 | 1 | 1 | 1 | 202 | 3156 | 180 | 1640 |
| 2022 | 12 | 14 | 1 | 1 | 1 | 202 | 3149 | 180 | 1665 |
| 2023 | 12 | 14 | 1 | 1 | 1 | 202 | 3150 | 180 | 1526 |
| 2024 | 12 | 14 | 1 | 1 | 1 | 202 | 3377 | 192 | 1674 |
| 2025 | 12 | 14 | 1 | 1 | 1 | 202 | 3382 | 192 | 1407 |

```
python3 evals/test_historical_gates.py
```
