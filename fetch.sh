#!/bin/zsh
# Refresh every season of AFFL data and rebuild the site bundles.
# Credentials live in .env (gitignored) — copy .env.example and fill it in.
#
# Usage:  ./fetch.sh            full refresh (all years)
#         ./fetch.sh box        just lineups
#         ./fetch.sh tx         just transactions
#         ./fetch.sh nflverse   weekly stats + rosters (no ESPN cookie)
#         ./fetch.sh pbp        nflverse play-by-play 2013–2025 (no ESPN cookie)
#         ./fetch.sh ngs        nextgen_stats 2016+ (no ESPN cookie)
#         ./fetch.sh process    skip fetching, just rebuild site JSON
set -e
cd "$(dirname "$0")"

if [[ ! -f .env ]]; then
  echo "error: .env not found. Copy .env.example to .env and fill in your ESPN cookies." >&2
  exit 1
fi

STEP=${1:-all}

if [[ "$STEP" != "process" ]]; then
  python3 fetch.py "$STEP"
fi

python3 process.py          # league / franchise / all-time -> site/data.json
python3 process_seasons.py  # per-season bundles -> site/years/*.json

echo "done — site/data.json + site/years/*.json rebuilt"
