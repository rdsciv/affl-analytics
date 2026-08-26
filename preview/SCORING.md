# 2025 scoring and notable matchups

CHI-25 / AFFL-006. From `fact_matchup` regular-season weeks (box grain).
This is the data. Not the website.

## Weekly distribution (heatmap / trend grain)

| week | n | min | avg | max |
| --- | --- | --- | --- | --- |
| 1 | 12 | 66.60 | 82.48 | 113.90 |
| 2 | 12 | 73.10 | 91.36 | 117.50 |
| 3 | 12 | 71.40 | 88.51 | 111.80 |
| 4 | 12 | 76.90 | 100.15 | 141.90 |
| 5 | 12 | 63.60 | 95.37 | 148.70 |
| 6 | 12 | 64.50 | 92.36 | 117.00 |
| 7 | 12 | 59.00 | 99.35 | 154.40 |
| 8 | 12 | 61.70 | 96.38 | 122.40 |
| 9 | 12 | 78.70 | 99.01 | 125.10 |
| 10 | 12 | 56.50 | 98.32 | 137.60 |
| 11 | 12 | 59.50 | 88.26 | 127.90 |
| 12 | 12 | 78.50 | 96.37 | 123.20 |
| 13 | 12 | 54.40 | 88.81 | 130.60 |
| 14 | 12 | 58.60 | 93.46 | 147.00 |

## Score histogram (10-pt buckets)

| bucket | n |
| --- | --- |
| 50 | 5 |
| 60 | 13 |
| 70 | 27 |
| 80 | 34 |
| 90 | 23 |
| 100 | 32 |
| 110 | 20 |
| 120 | 6 |
| 130 | 4 |
| 140 | 3 |
| 150 | 1 |

## Notable matchups (both scores)

Min win = lowest winning score. Max loss = highest losing score. Slugfest = highest combined. Pillow fight = lowest combined. Blowout = largest margin. Nail biter = smallest margin > 0.

| kind | week | winner | w_pts | loser | l_pts | combined | margin |
| --- | --- | --- | --- | --- | --- | --- | --- |
| min_win | 1 | Grand Teeton Feelers | 68.90 | Honolulu Horndogs | 68.70 | 137.60 | 0.20 |
| max_loss | 8 | San Diego Shadowcöcks | 122.40 | Fairview Fat Cats | 115.50 | 237.90 | 6.90 |
| slugfest | 14 | Goleta Gringos | 147.00 | Patagonia Pipers | 114.70 | 261.70 | 32.30 |
| pillow_fight | 13 | Westeros Warlords | 71.10 | Pasco Pounders | 54.40 | 125.50 | 16.70 |
| blowout | 10 | Westeros Warlords | 137.60 | Poulsbo Pollywogs | 56.50 | 194.10 | 81.10 |
| nail_biter | 1 | Grand Teeton Feelers | 68.90 | Honolulu Horndogs | 68.70 | 137.60 | 0.20 |

## How to refresh

```
python3 evals/test_scoring_notables_2025.py
```
