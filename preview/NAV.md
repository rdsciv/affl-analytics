# Navigation and verification gates

CHI-29 / AFFL-009. Unavailable modules stay out of primary nav.

## Primary nav (2025 verified grain)

| page | grain | 2025 rows |
| --- | --- | --- |
| Dashboard | matchup+standings | 202 matchups |
| Scoreboard | matchup | 202 |
| Players | roster_week | 3382 |
| Draft | draft_pick | 192 |
| Trades | transaction | 1407 |
| Roto | roster_week+nfl_week | 3382 / 18539 |
| Teams | team-season | 12 |
| History | franchise-career | 19 franchises |
| Awards | roster_week | 3382 |
| Wrapped | matchup+standings | 202 matchups |

Not in primary nav: Genius, Projections, Auction Lab.

## Pre-2018

Weekly STARTERS are recovered and verified-partial (`slot_source` records how each slot was derived). Weekly bench and the transaction feed are unavailable, so `has_rosters` and `has_tx` both stay 0. Scoreboard chips those years. Roto career marks them missing, not zero.

## How to refresh

```
python3 evals/test_nav_gates.py
```
