# AFFL Analytics

Three joined static sites for a 12-team ESPN fantasy football league (est. 2014), built from the
ESPN Fantasy API and joined to real NFL data via [nflverse](https://github.com/nflverse/nflverse-data).

**Live:** https://rdsciv.github.io/affl-analytics/

| Page | What's on it |
| --- | --- |
| **Dashboard** (`index.html`) | Season KPIs, weekly scoring waves, standings, schedule-luck index, Next Gen Lab (lineup IQ, draft ROI, position DNA, starter EPA), Player Profiler grid, Fantasy Genius report cards, all-time records back to 2014 |
| **Scoreboard** (`scoreboard.html`) | Every matchup of all 17 weeks with complete lineups — slot, player, NFL team, points, collapsible bench. Every player name links into the profiler |
| **PlayerProfiler** (`players.html`) | Per-player hero card, weekly production chart, AFFL journey, and a full game log joining fantasy scoring to real NFL box scores (yards, TDs, targets, EPA) |

## Notable metrics

- **Lineup IQ** — points started vs. the mathematically optimal lineup each week (exact optimum for 1QB/2RB/2WR/1TE/1FLEX/1DST/1K), surfacing points left on the bench.
- **Luck Index** — actual wins minus all-play expected wins, separating scoring from schedule.
- **Draft ROI** — auction points-per-dollar, producing steals and busts.
- **Starter EPA / WOPR / target share** — real NFL advanced stats attributed to whoever started the player, joined `espn_id → gsis_id` at a 99–100% match rate.
- **What-If Machine** — final standings if every manager had started a perfect lineup every week.
- **Manager Report Card** — A+–F grades on the three true skills (draft, lineups, waivers), with luck graded separately.

## Rebuilding the data

Credentials are read from a gitignored `.env` — never committed.

```bash
cp .env.example .env    # then fill in ESPN_SWID and ESPN_S2 from your browser cookies
./fetch.sh
```

`fetch.sh` pulls the current season, all league history, all 17 weekly boxscores, the draft, and the
nflverse weekly stats + rosters, then runs both processors:

- `process.py` → league/franchise/all-time analytics, plus ESPN member GUID anonymization
- `process_players.py` → player analytics, game logs, and `scoreboard.json`

Output is `site/data.json` and `site/scoreboard.json`. The site is fully static — no build step,
no external requests at runtime (Chart.js and all team logos are vendored locally).

## Local preview

```bash
python3 -m http.server 8788 --directory site
```
