# AFFL metric catalog

Target surface, benchmarked against FantasyGenius (their demo league at
`fantasygenius.io/nfl/demo`, plus their published data dictionary).

Status key: **have** = already computed · **partial** = computed but needs rework ·
**new** = not built yet · **n/a** = depends on data we don't have.

## Their defined metrics (from the FG data dictionary, verbatim definitions)

| Metric | Definition | Status |
| --- | --- | --- |
| **Power Rankings** | Every team played against every other team each week; ranked by win% of those hypothetical games | **partial** — we compute all-play W/L but don't surface it as PWR% or rank |
| **Management Score** | actual points ÷ optimal lineup points, as a % | **have** (our "Lineup IQ" efficiency) |
| **Luck** | *lucky win* = won while scoring in the bottom half that week; *unlucky loss* = lost while scoring in the top half; net = lucky − unlucky | **partial** — ours is all-play expected wins, a different (finer) definition. Add theirs as a discrete count |
| **Ideal Start %** | how often a player was in your optimal lineup | **new** |
| **Optimal Lineup Score** | the highest-scoring lineup that was available ("max points") | **have** |
| **FG Start %** | % of teams across all FG leagues who started the player | **n/a** — cross-league data we don't have |
| **Correct Decision Rate (CDR)** | how often a start/bench call was right (started a good week, benched a bad one) | **new** |

## Rankings / home

| Metric | Notes | Status |
| --- | --- | --- |
| Standings: record, PO flag, WIN%, PF, PA | | **have** |
| PWR% (power win %) | all-play win% | **partial** |
| Luck column | see above | **partial** |
| Superlatives: Min Win, Max Loss, Slugfest, Pillow Fight, Blowout, Nail Biter | we have best/worst week, closest, biggest blowout — need the full six, each as *both* teams' scores | **partial** |
| Featured Rivalry | H2H wins, total pts, PPG, longest streak, per pair | **partial** — we have the H2H ledger, not pts/PPG/streak |
| Team Score Trend | weekly line per team + avg / high / low | **have** (weekly scoring chart) |
| Team Trends | rolling PTS and RANK delta over last 1–12 weeks | **new** |
| Top Performances | best player-weeks, flagged when the player was on the **bench** | **partial** — we don't flag bench |
| Season High & Low | best/worst team weeks with opponent and their score | **partial** |
| Score Distribution | min / median / max histogram across all games | **new** |
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
