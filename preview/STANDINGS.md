# 2025 standings / Power / Luck

CHI-26 / AFFL-005. Recomputed from `fact_matchup` regular-season weeks.
This is the data. Not the website. Discrepancies are surfaced, not overwritten.

## ESPN records (W-L-T)

Weekly regular-season sides reproduce ESPN `dim_team` wins/losses/ties.

| rank | team | espn_w | wk_w | espn_l | wk_l | espn_t | wk_t | dw | dl | dt |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | San Diego Shadowcöcks | 11 | 11 | 3 | 3 | 0 | 0 | 0 | 0 | 0 |
| 2 | Goleta Gringos | 10 | 10 | 4 | 4 | 0 | 0 | 0 | 0 | 0 |
| 3 | Grand Teeton Feelers | 10 | 10 | 4 | 4 | 0 | 0 | 0 | 0 | 0 |
| 4 | Westeros Warlords | 9 | 9 | 5 | 5 | 0 | 0 | 0 | 0 | 0 |
| 5 | Patagonia Pipers | 8 | 8 | 6 | 6 | 0 | 0 | 0 | 0 | 0 |
| 6 | Honolulu Horndogs | 8 | 8 | 6 | 6 | 0 | 0 | 0 | 0 | 0 |
| 7 | Fairview Fat Cats | 6 | 6 | 8 | 8 | 0 | 0 | 0 | 0 | 0 |
| 8 | DC Mighty Cucks | 7 | 7 | 7 | 7 | 0 | 0 | 0 | 0 | 0 |
| 9 | Squaw Valley Skinners | 4 | 4 | 10 | 10 | 0 | 0 | 0 | 0 | 0 |
| 10 | Poulsbo Pollywogs | 5 | 5 | 9 | 9 | 0 | 0 | 0 | 0 | 0 |
| 11 | Pasco Pounders | 2 | 2 | 12 | 12 | 0 | 0 | 0 | 0 | 0 |
| 12 | Tijuana Sanchitos | 4 | 4 | 10 | 10 | 0 | 0 | 0 | 0 | 0 |

## Points Forced / Allowed

`fact_matchup.points` is the CHI-24 box grain (1 decimal). ESPN `dim_team.points_for` / `points_against` are league-record season totals (2 decimals). Weekly 1-dec sums do not equal ESPN. League schedule `totalPoints` (2-dec) does. dim_team was not overwritten.

| rank | team | espn_pf | wk_pf | dpf | espn_pa | wk_pa | dpa |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | San Diego Shadowcöcks | 1543.02 | 1542.90 | 0.1200 | 1296.96 | 1297.00 | -0.0400 |
| 2 | Goleta Gringos | 1370.88 | 1370.80 | 0.0800 | 1239.30 | 1239.30 | -0.0000 |
| 3 | Grand Teeton Feelers | 1407.48 | 1407.40 | 0.0800 | 1212.32 | 1212.20 | 0.1200 |
| 4 | Westeros Warlords | 1329.84 | 1330.00 | -0.1600 | 1220.98 | 1221.10 | -0.1200 |
| 5 | Patagonia Pipers | 1433.70 | 1433.70 | 0.0000 | 1421.36 | 1421.20 | 0.1600 |
| 6 | Honolulu Horndogs | 1333.36 | 1333.40 | -0.0400 | 1298.42 | 1298.50 | -0.0800 |
| 7 | Fairview Fat Cats | 1310.58 | 1310.60 | -0.0200 | 1329.56 | 1329.40 | 0.1600 |
| 8 | DC Mighty Cucks | 1282.20 | 1282.10 | 0.1000 | 1230.26 | 1230.20 | 0.0600 |
| 9 | Squaw Valley Skinners | 1200.78 | 1200.70 | 0.0800 | 1351.24 | 1351.00 | 0.2400 |
| 10 | Poulsbo Pollywogs | 1192.88 | 1192.80 | 0.0800 | 1324.12 | 1324.20 | -0.0800 |
| 11 | Pasco Pounders | 1090.02 | 1089.90 | 0.1200 | 1315.12 | 1315.00 | 0.1200 |
| 12 | Tijuana Sanchitos | 1227.72 | 1227.70 | 0.0200 | 1482.82 | 1482.90 | -0.0800 |

## Power (raw all-play)

Rank is `RANK()` on unrounded `allplay_w / (allplay_w + allplay_l)`, then more all-play wins. `power_pct` is display-only (4 decimals). Two 1-dec box ties (week 3: Pipers/Pounders 90.6; week 9: Shadowcocks/Mighty Cucks 104.2) are counted as all-play losses in `v_power` because `beat_this_week` is a strict `<`. League 2-dec scores break those ties; site `data.json` all-play therefore differs for Shadowcocks (112-42 vs 111-43) and Pounders (39-115 vs 38-116).

| rank | team | allplay_w | allplay_l | power_ratio | power_pct |
| --- | --- | --- | --- | --- | --- |
| 1 | San Diego Shadowcöcks | 111 | 43 | 0.7208 | 0.7208 |
| 2 | Patagonia Pipers | 109 | 45 | 0.7078 | 0.7078 |
| 3 | Grand Teeton Feelers | 93 | 61 | 0.6039 | 0.6039 |
| 4 | Goleta Gringos | 84 | 70 | 0.5455 | 0.5455 |
| 5 | Honolulu Horndogs | 81 | 73 | 0.5260 | 0.5260 |
| 6 | Westeros Warlords | 80 | 74 | 0.5195 | 0.5195 |
| 7 | Fairview Fat Cats | 79 | 75 | 0.5130 | 0.5130 |
| 8 | DC Mighty Cucks | 67 | 87 | 0.4351 | 0.4351 |
| 9 | Tijuana Sanchitos | 66 | 88 | 0.4286 | 0.4286 |
| 10 | Squaw Valley Skinners | 57 | 97 | 0.3701 | 0.3701 |
| 10 | Poulsbo Pollywogs | 57 | 97 | 0.3701 | 0.3701 |
| 12 | Pasco Pounders | 38 | 116 | 0.2468 | 0.2468 |

## Luck Index (v_luck) — FantasyGenius discrete

Lucky win = won while scoring in the bottom half that week. Unlucky loss = lost while scoring in the top half. Net = lucky − unlucky.

| team | lucky_wins | unlucky_losses | net_luck |
| --- | --- | --- | --- |
| Goleta Gringos | 2 | 0 | 2 |
| Grand Teeton Feelers | 3 | 1 | 2 |
| Westeros Warlords | 2 | 0 | 2 |
| DC Mighty Cucks | 2 | 1 | 1 |
| Honolulu Horndogs | 2 | 1 | 1 |
| Squaw Valley Skinners | 2 | 1 | 1 |
| Pasco Pounders | 1 | 1 | 0 |
| Poulsbo Pollywogs | 1 | 1 | 0 |
| San Diego Shadowcöcks | 1 | 1 | 0 |
| Fairview Fat Cats | 1 | 3 | -2 |
| Patagonia Pipers | 1 | 4 | -3 |
| Tijuana Sanchitos | 0 | 4 | -4 |

## League Legacy weighted luck (v_luck_weighted)

expected wins = all-play win% × regular-season games. weighted luck = actual wins − expected wins. Not Luck Index.

| team | reg_wins | exp_wins | weighted_luck |
| --- | --- | --- | --- |
| Goleta Gringos | 10 | 7.64 | 2.36 |
| Westeros Warlords | 9 | 7.27 | 1.73 |
| Grand Teeton Feelers | 10 | 8.45 | 1.55 |
| DC Mighty Cucks | 7 | 6.09 | 0.9100 |
| San Diego Shadowcöcks | 11 | 10.09 | 0.9100 |
| Honolulu Horndogs | 8 | 7.36 | 0.6400 |
| Poulsbo Pollywogs | 5 | 5.18 | -0.1800 |
| Fairview Fat Cats | 6 | 7.18 | -1.18 |
| Squaw Valley Skinners | 4 | 5.18 | -1.18 |
| Pasco Pounders | 2 | 3.45 | -1.45 |
| Patagonia Pipers | 8 | 9.91 | -1.91 |
| Tijuana Sanchitos | 4 | 6.00 | -2.00 |

## How to refresh

```
python3 evals/test_standings_power_luck_2025.py
```
