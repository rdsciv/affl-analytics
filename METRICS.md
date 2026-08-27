# AFFL metric catalog

Target surface, benchmarked against FantasyGenius (their demo league at
`fantasygenius.io/nfl/demo`, plus their published data dictionary).

Status key: **have** = already computed · **partial** = computed but needs rework ·
**new** = not built yet · **n/a** = depends on data we don't have.

## Their defined metrics (from the FG data dictionary, verbatim definitions)

| Metric | Definition | Status |
| --- | --- | --- |
| **Power Rankings** | Every team played against every other team each week; ranked by win% of those hypothetical games | **have** — `v_power` ranks on raw allplay_w / (allplay_w+allplay_l), not the rounded display |
| **Management Score** | actual points ÷ optimal lineup points, as a % | **have** (our "Lineup IQ" efficiency) |
| **Luck** | *lucky win* = won while scoring in the bottom half that week; *unlucky loss* = lost while scoring in the top half; net = lucky − unlucky | **have** — Luck Index is `v_luck` (discrete). League Legacy weighted luck is `v_luck_weighted` (wins − expected wins). Do not mix. |
| **Ideal Start %** | how often a player was in your optimal lineup | **new** |
| **Optimal Lineup Score** | the highest-scoring lineup that was available ("max points") | **have** |
| **FG Start %** | % of teams across all FG leagues who started the player | **n/a** — cross-league data we don't have |
| **Correct Decision Rate (CDR)** | how often a start/bench call was right (started a good week, benched a bad one) | **new** |

## Rankings / home

| Metric | Notes | Status |
| --- | --- | --- |
| Standings: record, PO flag, WIN%, PF, PA | | **have** |
| PWR% (power win %) | all-play win%; rank from raw num/denom | **have** (`v_power`) |
| Luck column | Luck Index (`v_luck`) is not League Legacy weighted luck (`v_luck_weighted`) | **have** |
| Superlatives: Min Win, Max Loss, Slugfest, Pillow Fight, Blowout, Nail Biter | `v_notable_matchup` both scores, regular season | **have** |
| Featured Rivalry | H2H wins, total pts, PPG, longest streak, per pair | **partial** — we have the H2H ledger, not pts/PPG/streak |
| Team Score Trend | weekly line per team + avg / high / low | **have** (weekly scoring chart) |
| Team Trends | rolling PTS and RANK delta over last 1–12 weeks | **new** |
| Top Performances | best player-weeks, flagged when the player was on the **bench** | **partial** — we don't flag bench |
| Season High & Low | best/worst team weeks with opponent and their score | **partial** |
| Score Distribution | min / avg / max + 10-pt histogram | **have** (`v_score_week`, `v_score_distribution`) |
| Skill Radar | team totals + league rank for pass yds/TD/comp%, rush yds/TD/YPC, rec yds/TD/rec/YPR | **new** — needs nflverse box stats aggregated by AFFL roster |
| Streaks | active + season-best W/L runs | **new** |
| Trophies | 13 "good" + 12 "bad" awards | **new** |
| Tiers | Contenders / Mid-tier / Get on the stick / Dumpster fire | **new** |
| Management Blunders | worst actual-vs-optimal weeks, points left on bench | **partial** — we have season totals, not the worst individual weeks |

## History

| Metric | Status |
| --- | --- |
| Champions by year, by owner, and title games (1st / 2nd / 3rd) | **partial** — we have champion + runner-up, not 3rd |
| Finishes-by-year heatmap (champ / top half / bottom half / sacko / DNP) | **new** |
| All-time records: titles, 2nds, 3rds, sackos, playoff appearances, playoff %, years, overall record, win%, regular-season record, win% | **partial** — we have titles/win%/PF, missing the rest |
| All-time luck: lucky weeks, unlucky weeks, net, luckiest/unluckiest seasons | **new** |
| All-time streaks: longest winning and losing runs with year, weeks, length, LIVE flag | **new** |
| Team-season record book + scatter | **new** |

## Wrapped (their season-in-review is 33 slides)

Groups, with slide counts: Season Leaders (3), Team Awards (8), Matchup Awards (9),
Individual Awards (4), Player Highlights (5), Management (1), Podium (1). **new** —
this is a presentation layer over metrics above, so it comes last.

## Draft

| Metric | Status |
| --- | --- |
| Full board, auction or snake | **have** |
| Spend allocation by position | **have** |
| Steals / busts | **partial → being reworked**: raw points-per-dollar is positionally biased. A $1 QB looks like an infinite steal because QB scoring floor is high; a stud RB looks mediocre. Replacing with **points above replacement per dollar** (see below) |
| Draft hit rate | **have** |
| Keeper flags | **have** |

### Why points/$ is wrong, and the fix

Raw `points ÷ dollars` ignores that positions have different **replacement levels**.
A QB you get for free still scores ~250 points, so every cheap QB grades as a steal.
An RB2 scoring 250 is genuinely scarce, because the next RB off the wire scores far less.
That's exactly why an auction market pays more for a stud RB than a stud QB.

The fix is value over replacement, per dollar:

```
replacement(pos, season) = points of the Nth-best player at that position,
                           where N = (teams x starters required at pos)
PAR                      = player points - replacement(pos, season)
value                    = PAR / max(dollars, 1)
```

Replacement level is computed **per season** from that season's own starter
requirements, so a 10-team year and a 12-team year get different baselines.

## NFL contracts / cap (new capability)

Goal: sum the real NFL salary-cap cost of each AFFL roster.

| Field | Source | Notes |
| --- | --- | --- |
| Per-season cap hit, base salary, bonuses, dead cap | **Spotrac** team cap tables | `robots.txt` allows `/` with `Crawl-delay: 5`; the `/cap/_/year/{YYYY}` path is not disallowed. Cache locally, crawl politely |
| Contract value, APY, guaranteed, APY as % of cap | **Over The Cap** via nflverse `contracts` release | Free and redistributable, but the bulk release **stops at 2022**, so it only backfills older seasons |

Join path: `espn_id → gsis_id` (nflverse rosters, already used) `→ otc_id`
(`otc_players.csv`) `→ contracts`. Spotrac is matched on name + NFL team + season.

## GM effectiveness (not starter points)

Starter points measure the lineup that week. They fail as a GM grade because
a drafted player can appreciate and be traded for a better player. After the
trade, starter points credit the new roster and erase the construction path.

**Custody PAR** is the replacement.

```
stint            = one player on one team, from acquisition week to exit week
weekly PAR       = player_points - replacement(pos, season)
Custody PAR      = SUM of weekly PAR for every week the player was rostered
                   (started or benched)
```

Split every team's Custody PAR by acquisition type: Drafted / Traded in / Waiver / FA.
Lineup IQ (actual ÷ optimal) stays. That is start/sit, not asset management.

Before 2018 it exists only where the bench does. ESPN's weekly payloads hold starters
only, but the same archive carries one late-season full-roster snapshot per team; where
that snapshot can be dated against a recovered lineup, the bench for that week is known
and Lineup IQ is computable. 18 team-weeks qualify (2014: 3, 2015: 4, 2016: 0, 2017: 11),
published as `lineupIQPre2018` — one record per team-week, never pooled with the 2018+
season aggregate. Actual starter points are ESPN's own and exact; the optimal depends on
bench points computed by the engine `validate_scoring.py` gates. See `CONTRACTS.md`.

**Trade Alpha** is the second number, not added into Custody PAR (that would
double-count).

```
Trade Alpha      = incoming consensus ROS − outgoing consensus ROS
                   at the timestamp of the trade
Trade Realized   = incoming remaining-season actual PAR
                   − outgoing remaining-season actual PAR
```

Trade Alpha grades the decision. Trade Realized grades the aftermath (injuries
and breakouts after the deal contaminate it).

Related existing idea: opportunity cost = points scored by players you dropped,
after you dropped them.

## Projection residual and xTD residual

Need a weekly expected line for every player, then:

```
proj residual    = actual AFFL points − projected AFFL points
team week        = SUM of starter residuals that week
roster week      = SUM of rostered residuals that week
xTD residual     = actual TDs − expected TDs
xTD portfolio    = team SUM(xTD residual)
```

Projected points are **not** the vendor's FPTS column. Ingest the stat line
(pass/rush/rec yards and TDs, ints, fumbles) and run it through that season's
AFFL scoring rules (bucketed yards through 2018, fractional after; the 50-yard
FG quirk).

### Expected points source

Warehouse has zero weekly projections today. nflverse has none.

1. **Going forward, and any week we can still pull:** FantasyPros weekly
   consensus **standard** (non-PPR) stat-line projections. AFFL is non-PPR.
   Archive every week ourselves so we are not dependent on their history later.
2. **Backfill:** FantasyPros historical weekly consensus is a paid API product,
   not a public archive. Do not scrape a fake "consensus." If a licensed dump
   or a verified public weekly file exists for a season, use it and label the
   source. If it does not, that season's proj residual stays unavailable.
3. **ESPN `projectedPoints`** on `mMatchup` is a fallback for weeks where the
   raw payload still has it. Label it ESPN, never "consensus."

### Expected TDs

Primary series is opportunity xTD from nflverse pbp, already specified:

```
xTD = SUM over targets/carries of P(TD | yardline_100, down, ydstogo, play_type)
      fit per season
```

That covers every AFFL season. Consensus *projected* TDs (FantasyPros) are a
second series, only where the projection file exists. Do not mix the two.


## Roto standings (AFFL_Pillars methodology)

Live page: `site/roto.html`. Computes in the browser from `site/pillars/boxscores/*.json`
plus `site/pillars/league.json`. No standings totals are stored.

Copied from `rdsciv/AFFL_Pillars`:
- 10 categories: Pass Yds, Pass TD, Comp%, Rush Yds, Rush TD, YPC, Rec Yds, Rec TD, Rec, YPR
- Starter NFL stats only (`p.st`), summed per team-game
- Rank 1 = best; roto pts = nTeams − rank + 1
- Phases: `reg` (tier NONE), `post` (any non-NONE), `combined` (both). Consolation ladders excluded from all three so `reg + post == combined`
- Career = mean of each scored season's totalRank / totalPts per ownerId
- A year without a boxscore is not a sit-out. Pillars only scores years with player-level boxscores (2018+, ESPN cutoff). Pre-2018 is unavailable, not zero.

Do not serve warehouse `v_roto_standings` on this page. That path can diverge (phase names, lineup source). This page is the Pillars boxscore re-score.


## Player logs

`site/players.html` game log is the AFFL roster week (started or benched) joined to nflverse EPA and opportunity xTD. Bench rows stay gray. Year chips + All walk every season the player was actually rostered (2018+). Spotrac cap hits are annual accounting rows (a mid-year trade can show more than one team). Signing terms are Over The Cap via nflverse, labeled separately. Rebuild with `enrich_players.py`.
