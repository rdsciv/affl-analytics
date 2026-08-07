#!/bin/zsh
# Refresh all AFFL data, then rebuild site/data.json + site/scoreboard.json.
# Credentials live in .env (gitignored) — copy .env.example and fill it in.
set -e
cd "$(dirname "$0")"

if [[ ! -f .env ]]; then
  echo "error: .env not found. Copy .env.example to .env and fill in your ESPN cookies." >&2
  exit 1
fi
set -a; source .env; set +a

: ${ESPN_LEAGUE_ID:?missing in .env}
: ${ESPN_SWID:?missing in .env}
: ${ESPN_S2:?missing in .env}
SEASON=${ESPN_SEASON:-2025}

COOKIE="SWID=${ESPN_SWID}; espn_s2=${ESPN_S2}"
BASE='https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl'
LG=$ESPN_LEAGUE_ID
mkdir -p data

echo "current season $SEASON..."
curl -s -H "Cookie: $COOKIE" "$BASE/seasons/$SEASON/segments/0/leagues/$LG?view=mTeam&view=mSettings&view=mStandings" -o "data/league_$SEASON.json"

echo "history..."
for yr in $(seq 2014 $((SEASON-1))); do
  curl -s -H "Cookie: $COOKIE" "$BASE/leagueHistory/$LG?seasonId=$yr&view=mTeam&view=mSettings&view=mStandings&view=mMatchup" -o "data/league_$yr.json"
done

echo "boxscores..."
for wk in $(seq 1 17); do
  curl -s -H "Cookie: $COOKIE" "$BASE/seasons/$SEASON/segments/0/leagues/$LG?view=mMatchup&view=mMatchupScore&scoringPeriodId=$wk" -o "data/box_w$wk.json"
done
curl -s -H "Cookie: $COOKIE" "$BASE/seasons/$SEASON/segments/0/leagues/$LG?view=mDraftDetail" -o "data/draft_$SEASON.json"

echo "nflverse..."
curl -sL "https://github.com/nflverse/nflverse-data/releases/download/stats_player/stats_player_week_$SEASON.csv" -o "data/stats_player_week_$SEASON.csv"
curl -sL "https://github.com/nflverse/nflverse-data/releases/download/rosters/roster_$SEASON.csv" -o "data/roster_$SEASON.csv"

python3 process.py
python3 process_players.py
echo "done — site/data.json + site/scoreboard.json rebuilt"
