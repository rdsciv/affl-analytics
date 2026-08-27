-- ============================================================================
-- AFFL warehouse.  One SQLite file (affl.db) is the single source of truth;
-- the site's JSON bundles become build artifacts exported from these tables.
--
-- Conventions
--   * season          = fantasy year (2014..2026)
--   * team_id         = ESPN team id, only unique WITHIN a season
--   * member_id       = ESPN slot alias (m01..m22); not the person
--   * owner_id        = the person (dim_owner). career math joins through this
--   * player_id       = ESPN player id (negative for D/ST: -16000 - proTeamId)
--   * points are fantasy points; "started" excludes BN/IR slots
--   * phase           = regular | championship | consolation | playoff_unspecified
-- ============================================================================

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------- dimensions
CREATE TABLE IF NOT EXISTS dim_season (
  season          INTEGER PRIMARY KEY,
  reg_weeks       INTEGER NOT NULL,       -- last regular-season matchup period
  playoff_teams   INTEGER,
  team_count      INTEGER NOT NULL,
  auction_draft   INTEGER NOT NULL DEFAULT 0,
  has_rosters     INTEGER NOT NULL DEFAULT 0,   -- ESPN keeps lineups from 2018
  has_tx          INTEGER NOT NULL DEFAULT 0,
  uses_faab       INTEGER NOT NULL DEFAULT 0,
  slot_qb INTEGER, slot_rb INTEGER, slot_wr INTEGER,
  slot_te INTEGER, slot_flex INTEGER, slot_dst INTEGER, slot_k INTEGER,
  -- How ESPN converted yardage to points that season. Determined empirically by
  -- validate_scoring.py: 2018 and earlier floor yardage to whole points
  -- (floor(yds/25) passing, floor(yds/10) rush+rec); 2019 onward awards
  -- fractional points per yard. Getting this wrong costs ~0.5 pts per player-week.
  yardage_mode    TEXT NOT NULL DEFAULT 'FRACTIONAL'
);

-- Person grain. ESPN member_id splits (Kafka m07/m01) and leaves orphans
-- (Sliger m03, Dunn m20). Career math joins dim_team.member_id -> dim_member
-- -> dim_owner. member_id is kept; it is not destroyed.
CREATE TABLE IF NOT EXISTS dim_owner (
  owner_id        TEXT PRIMARY KEY,
  display_name    TEXT NOT NULL,
  is_active       INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS dim_member (
  member_id       TEXT PRIMARY KEY,       -- m01..m22 (never a real ESPN SWID)
  display_name    TEXT NOT NULL,
  is_active       INTEGER NOT NULL DEFAULT 0,
  owner_id        TEXT                    -- person; see dim_owner
);

-- a franchise-season: the same owner's team in one particular year
CREATE TABLE IF NOT EXISTS dim_team (
  season          INTEGER NOT NULL REFERENCES dim_season(season),
  team_id         INTEGER NOT NULL,
  member_id       TEXT REFERENCES dim_member(member_id),
  name            TEXT NOT NULL,
  abbrev          TEXT,
  logo            TEXT,
  wins            INTEGER, losses INTEGER, ties INTEGER,
  points_for      REAL,   points_against REAL,
  playoff_seed    INTEGER,
  final_rank      INTEGER,
  PRIMARY KEY (season, team_id)
);

CREATE TABLE IF NOT EXISTS dim_player (
  player_id       INTEGER PRIMARY KEY,    -- ESPN id
  name            TEXT NOT NULL,
  position        TEXT,
  gsis_id         TEXT,                   -- nflverse join key
  otc_id          TEXT,                   -- Over The Cap join key
  headshot_url    TEXT
);
CREATE INDEX IF NOT EXISTS ix_player_gsis ON dim_player(gsis_id);
CREATE INDEX IF NOT EXISTS ix_player_name ON dim_player(name);

-- a player's NFL club can change mid-career, so it is season-scoped
CREATE TABLE IF NOT EXISTS player_season (
  season          INTEGER NOT NULL,
  player_id       INTEGER NOT NULL REFERENCES dim_player(player_id),
  nfl_team        TEXT,
  PRIMARY KEY (season, player_id)
);

-- ---------------------------------------------------------------- core facts
-- one row per player per week per fantasy roster: the grain everything else
-- aggregates from
CREATE TABLE IF NOT EXISTS fact_roster_week (
  season          INTEGER NOT NULL,
  week            INTEGER NOT NULL,
  team_id         INTEGER NOT NULL,
  player_id       INTEGER NOT NULL,
  slot            TEXT NOT NULL,          -- QB/RB/WR/TE/FLEX/D-ST/K/BN/IR
  points          REAL NOT NULL DEFAULT 0,
  started         INTEGER NOT NULL,
  PRIMARY KEY (season, week, team_id, player_id),
  FOREIGN KEY (season, team_id) REFERENCES dim_team(season, team_id)
);
CREATE INDEX IF NOT EXISTS ix_rw_player  ON fact_roster_week(season, player_id);
CREATE INDEX IF NOT EXISTS ix_rw_team    ON fact_roster_week(season, team_id, week);
CREATE INDEX IF NOT EXISTS ix_rw_started ON fact_roster_week(season, started);

-- 2014-2017 only. ESPN's leagueHistory response carries, alongside the weekly
-- starters in rosterForMatchupPeriod, a `teams[].roster` block holding one FULL
-- roster per team - bench included, with real lineupSlotId values. It is a single
-- late-season snapshot repeated byte-identically in every weekly file, not a
-- weekly series, so it cannot go in fact_roster_week without pretending to be a
-- week it is not. dated_week is filled only when the snapshot's non-bench set
-- matches a recovered lineup for that team; NULL means it could not be placed and
-- nothing downstream may treat it as a week. See CONTRACTS.md.
CREATE TABLE IF NOT EXISTS fact_roster_snapshot_pre2018 (
  season          INTEGER NOT NULL,
  team_id         INTEGER NOT NULL,
  player_id       INTEGER NOT NULL,
  slot            TEXT NOT NULL,          -- QB/RB/WR/TE/K/D-ST/FLEX/BE
  started         INTEGER NOT NULL,       -- 0 for BE, 1 otherwise
  dated_week      INTEGER,                -- NULL when the snapshot is not datable
  PRIMARY KEY (season, team_id, player_id),
  FOREIGN KEY (season, team_id) REFERENCES dim_team(season, team_id)
);
CREATE INDEX IF NOT EXISTS ix_snap_dated
  ON fact_roster_snapshot_pre2018(season, dated_week);

CREATE TABLE IF NOT EXISTS fact_matchup (
  season          INTEGER NOT NULL,
  week            INTEGER NOT NULL,
  team_id         INTEGER NOT NULL,       -- stored twice per game, once per side
  opponent_id     INTEGER NOT NULL,
  points          REAL NOT NULL,
  opponent_points REAL NOT NULL,
  is_home         INTEGER NOT NULL,
  tier            TEXT NOT NULL DEFAULT 'NONE',   -- WINNERS_BRACKET etc.
  is_playoff      INTEGER NOT NULL DEFAULT 0,
  result          TEXT GENERATED ALWAYS AS (
                    CASE WHEN points > opponent_points THEN 'W'
                         WHEN points < opponent_points THEN 'L' ELSE 'T' END) STORED,
  margin          REAL GENERATED ALWAYS AS (points - opponent_points) STORED,
  PRIMARY KEY (season, week, team_id)
);
CREATE INDEX IF NOT EXISTS ix_mu_team ON fact_matchup(season, team_id);

CREATE TABLE IF NOT EXISTS fact_draft_pick (
  season          INTEGER NOT NULL,
  overall         INTEGER NOT NULL,
  round           INTEGER,
  pick_in_round   INTEGER,
  team_id         INTEGER NOT NULL,
  player_id       INTEGER,
  bid             INTEGER NOT NULL DEFAULT 0,   -- auction dollars, 0 if snake
  is_keeper       INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (season, overall)
);
CREATE INDEX IF NOT EXISTS ix_draft_player ON fact_draft_pick(season, player_id);

-- waiver claims and free-agent moves. `team_id` here is the team that GAINED or
-- LOST the player (taken from the transaction item, never the executing team --
-- the commissioner executes on others' behalf).
CREATE TABLE IF NOT EXISTS fact_transaction (
  tx_id           INTEGER PRIMARY KEY AUTOINCREMENT,
  season          INTEGER NOT NULL,
  week            INTEGER,
  ts              INTEGER,                -- epoch millis
  tx_type         TEXT NOT NULL,          -- WAIVER | FREEAGENT
  team_id         INTEGER NOT NULL,
  player_id       INTEGER NOT NULL,
  direction       TEXT NOT NULL,          -- ADD | DROP
  bid             INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ix_tx ON fact_transaction(season, team_id, direction);

-- trades: TRADE_ACCEPT items when present; else reconstructed from roster deltas
CREATE TABLE IF NOT EXISTS fact_trade (
  trade_id        INTEGER PRIMARY KEY AUTOINCREMENT,
  season          INTEGER NOT NULL,
  week            INTEGER NOT NULL,
  ts              INTEGER
);
CREATE TABLE IF NOT EXISTS fact_trade_item (
  trade_id        INTEGER NOT NULL REFERENCES fact_trade(trade_id) ON DELETE CASCADE,
  player_id       INTEGER NOT NULL,
  from_team_id    INTEGER NOT NULL,
  to_team_id      INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_ti ON fact_trade_item(trade_id);

-- ---------------------------------------------------------------- nfl / money
CREATE TABLE IF NOT EXISTS fact_nfl_week (
  season          INTEGER NOT NULL,
  week            INTEGER NOT NULL,
  gsis_id         TEXT NOT NULL,
  opponent        TEXT,
  pass_yards REAL, pass_tds REAL, completions REAL, attempts REAL,
  rush_yards REAL, rush_tds REAL, carries REAL,
  rec_yards  REAL, rec_tds  REAL, receptions REAL, targets REAL,
  air_yards  REAL, target_share REAL, wopr REAL,
  epa        REAL,
  -- scoring inputs: without these, recomputed points miss INT/fumble/2pt terms
  interceptions REAL, fumbles_lost REAL, two_pt REAL,
  sacks_suffered REAL, air_yards_share REAL, racr REAL, pacr REAL,
  PRIMARY KEY (season, week, gsis_id)
);

-- one row per NFL contract signing (Over The Cap via nflverse)
CREATE TABLE IF NOT EXISTS fact_contract (
  contract_id     INTEGER PRIMARY KEY AUTOINCREMENT,
  otc_id          TEXT,
  gsis_id         TEXT,
  player_name     TEXT NOT NULL,
  position        TEXT,
  nfl_team        TEXT,
  year_signed     INTEGER,
  years           INTEGER,
  value           REAL,
  apy             REAL,
  guaranteed      REAL,
  apy_cap_pct     REAL,
  is_active       INTEGER
);
CREATE INDEX IF NOT EXISTS ix_contract_gsis ON fact_contract(gsis_id);

-- per-season cap accounting (Spotrac team cap tables)
CREATE TABLE IF NOT EXISTS fact_cap_hit (
  season          INTEGER NOT NULL,
  nfl_team        TEXT NOT NULL,
  player_name     TEXT NOT NULL,
  player_id       INTEGER,                -- resolved to ESPN id where possible
  position        TEXT,
  cap_hit         REAL,
  base_salary     REAL,
  signing_bonus   REAL,
  dead_cap        REAL,
  cap_pct         REAL,
  PRIMARY KEY (season, nfl_team, player_name)
);
CREATE INDEX IF NOT EXISTS ix_cap_player ON fact_cap_hit(player_id);

-- ============================================================================
-- Views: the metric layer.  Everything the site renders should come from here.
-- ============================================================================

-- weekly team result joined to lineup efficiency
DROP VIEW IF EXISTS v_team_week;
CREATE VIEW v_team_week AS
SELECT m.season, m.week, m.team_id, t.member_id, t.name AS team_name,
       m.opponent_id, m.points, m.opponent_points, m.result, m.margin,
       m.is_playoff,
       (SELECT SUM(r.points) FROM fact_roster_week r
         WHERE r.season = m.season AND r.week = m.week
           AND r.team_id = m.team_id AND r.started = 1)              AS started_points,
       (SELECT SUM(r.points) FROM fact_roster_week r
         WHERE r.season = m.season AND r.week = m.week
           AND r.team_id = m.team_id AND r.started = 0)              AS bench_points,
       (SELECT COUNT(*) FROM fact_matchup o
         WHERE o.season = m.season AND o.week = m.week
           AND o.points < m.points)                                  AS beat_this_week,
       (SELECT COUNT(*) - 1 FROM fact_matchup o
         WHERE o.season = m.season AND o.week = m.week)               AS field_size
FROM fact_matchup m
JOIN dim_team t ON t.season = m.season AND t.team_id = m.team_id;

-- all-play / power ranking: how you'd do against the whole league every week.
-- Ranks use the raw numerator/denominator (power_ratio), not the rounded display.
-- CHI-26 / AFFL-005.
DROP VIEW IF EXISTS v_power;
CREATE VIEW v_power AS
SELECT season, team_id, allplay_w, allplay_l, power_ratio, power_pct,
       RANK() OVER (PARTITION BY season
                    ORDER BY power_ratio DESC, allplay_w DESC, allplay_l ASC) AS power_rank
FROM (
  SELECT season, team_id,
         SUM(beat_this_week)                                    AS allplay_w,
         SUM(field_size - beat_this_week)                       AS allplay_l,
         1.0 * SUM(beat_this_week) /
               NULLIF(SUM(field_size), 0)                       AS power_ratio,
         ROUND(1.0 * SUM(beat_this_week) /
               NULLIF(SUM(field_size), 0), 4)                   AS power_pct
  FROM v_team_week
  WHERE is_playoff = 0
  GROUP BY season, team_id
);

-- Luck Index (FantasyGenius discrete). Distinct from League Legacy weighted luck
-- in v_luck_weighted (actual wins minus all-play expected wins).
DROP VIEW IF EXISTS v_luck;
CREATE VIEW v_luck AS
SELECT season, team_id,
       SUM(CASE WHEN result = 'W' AND beat_this_week * 2 <  field_size THEN 1 ELSE 0 END) AS lucky_wins,
       SUM(CASE WHEN result = 'L' AND beat_this_week * 2 >= field_size THEN 1 ELSE 0 END) AS unlucky_losses,
       SUM(CASE WHEN result = 'W' AND beat_this_week * 2 <  field_size THEN 1 ELSE 0 END)
       - SUM(CASE WHEN result = 'L' AND beat_this_week * 2 >= field_size THEN 1 ELSE 0 END) AS net_luck
FROM v_team_week
WHERE is_playoff = 0
GROUP BY season, team_id;

-- CHI-25 / AFFL-006. Normalized scoring + notable matchups from fact_matchup.
-- Regular season only. One game = is_home=1 so we do not double-count sides.
DROP VIEW IF EXISTS v_score_week;
CREATE VIEW v_score_week AS
SELECT season, week,
       COUNT(*) AS n,
       MIN(points) AS min_pts,
       AVG(points) AS avg_pts,
       MAX(points) AS max_pts
FROM fact_matchup
WHERE is_playoff = 0
GROUP BY season, week;

DROP VIEW IF EXISTS v_score_normalized;
CREATE VIEW v_score_normalized AS
SELECT m.season, m.week, m.team_id, m.opponent_id, m.points, m.result,
       w.avg_pts AS week_avg, w.min_pts AS week_min, w.max_pts AS week_max,
       m.points - w.avg_pts AS vs_avg,
       1.0 * m.points / NULLIF(w.avg_pts, 0) AS pct_of_week
FROM fact_matchup m
JOIN v_score_week w ON w.season = m.season AND w.week = m.week
WHERE m.is_playoff = 0;

DROP VIEW IF EXISTS v_score_distribution;
CREATE VIEW v_score_distribution AS
SELECT season,
       CAST(points / 10 AS INTEGER) * 10 AS bucket,
       COUNT(*) AS n
FROM fact_matchup
WHERE is_playoff = 0
GROUP BY season, CAST(points / 10 AS INTEGER) * 10;

DROP VIEW IF EXISTS v_game;
CREATE VIEW v_game AS
SELECT season, week, team_id AS home_id, opponent_id AS away_id,
       points AS home_pts, opponent_points AS away_pts,
       CASE WHEN points >= opponent_points THEN team_id ELSE opponent_id END AS winner_id,
       CASE WHEN points >= opponent_points THEN opponent_id ELSE team_id END AS loser_id,
       CASE WHEN points >= opponent_points THEN points ELSE opponent_points END AS winner_pts,
       CASE WHEN points >= opponent_points THEN opponent_points ELSE points END AS loser_pts,
       points + opponent_points AS combined,
       ABS(points - opponent_points) AS margin,
       is_playoff
FROM fact_matchup
WHERE is_home = 1;

DROP VIEW IF EXISTS v_notable_matchup;
CREATE VIEW v_notable_matchup AS
WITH g AS (
  SELECT * FROM v_game WHERE is_playoff = 0
)
SELECT season, 'min_win' AS kind, week, winner_id, loser_id,
       winner_pts, loser_pts, combined, margin
FROM g WHERE (season, winner_pts) IN (SELECT season, MIN(winner_pts) FROM g GROUP BY season)
UNION ALL
SELECT season, 'max_loss', week, winner_id, loser_id,
       winner_pts, loser_pts, combined, margin
FROM g WHERE (season, loser_pts) IN (SELECT season, MAX(loser_pts) FROM g GROUP BY season)
UNION ALL
SELECT season, 'slugfest', week, winner_id, loser_id,
       winner_pts, loser_pts, combined, margin
FROM g WHERE (season, combined) IN (SELECT season, MAX(combined) FROM g GROUP BY season)
UNION ALL
SELECT season, 'pillow_fight', week, winner_id, loser_id,
       winner_pts, loser_pts, combined, margin
FROM g WHERE (season, combined) IN (SELECT season, MIN(combined) FROM g GROUP BY season)
UNION ALL
SELECT season, 'blowout', week, winner_id, loser_id,
       winner_pts, loser_pts, combined, margin
FROM g WHERE (season, margin) IN (SELECT season, MAX(margin) FROM g GROUP BY season)
UNION ALL
SELECT season, 'nail_biter', week, winner_id, loser_id,
       winner_pts, loser_pts, combined, margin
FROM g WHERE margin > 0
  AND (season, margin) IN (SELECT season, MIN(margin) FROM g WHERE margin > 0 GROUP BY season);

-- a player's fantasy season from the AFFL's point of view
DROP VIEW IF EXISTS v_player_season;
CREATE VIEW v_player_season AS
SELECT r.season, r.player_id, p.name, p.position, ps.nfl_team,
       SUM(r.points)                                        AS total_points,
       SUM(CASE WHEN r.started = 1 THEN r.points ELSE 0 END) AS started_points,
       SUM(r.started)                                        AS starts,
       COUNT(*)                                              AS weeks_rostered,
       ROUND(SUM(CASE WHEN r.started = 1 THEN r.points ELSE 0 END)
             / NULLIF(SUM(r.started), 0), 2)                 AS ppg_started
FROM fact_roster_week r
JOIN dim_player p ON p.player_id = r.player_id
LEFT JOIN player_season ps ON ps.season = r.season AND ps.player_id = r.player_id
GROUP BY r.season, r.player_id;

-- replacement level: the Nth-best scorer at a position, where N is how many
-- the league must collectively start. This is what makes cross-position value
-- comparable -- a free QB is not a steal, because QB replacement is high.
DROP VIEW IF EXISTS v_starter_demand;
CREATE VIEW v_starter_demand AS
SELECT season, 'QB' AS position, team_count * COALESCE(slot_qb,1) AS demand FROM dim_season
UNION ALL SELECT season, 'RB', team_count * (COALESCE(slot_rb,2) + 1) FROM dim_season
UNION ALL SELECT season, 'WR', team_count * (COALESCE(slot_wr,2) + 1) FROM dim_season
UNION ALL SELECT season, 'TE', team_count * COALESCE(slot_te,1) FROM dim_season
UNION ALL SELECT season, 'K',  team_count * COALESCE(slot_k,1)  FROM dim_season
UNION ALL SELECT season, 'DST',team_count * COALESCE(slot_dst,1) FROM dim_season;


-- ===========================================================================
-- Computed fantasy points, for seasons where ESPN kept no weekly lineups.
--
-- ESPN retains lineups only from 2018, so v_player_season (which reads
-- fact_roster_week) is empty for 2014-2017 and every downstream metric --
-- replacement level, draft PAR -- came out NULL for those years. nflverse has
-- weekly NFL stats back to 1999 and validate_scoring.py proves this engine
-- reproduces ESPN's own points at 96-99.8% exact, so season totals CAN be
-- computed for the early seasons without knowing anybody's lineup.
--
-- MATERIALIZED, not a view: doing this as correlated subqueries over 208k
-- player-weeks made the site export take minutes. build_db.py fills it.
-- Bucketing is applied per week (as ESPN scored it) and then summed.
-- ===========================================================================
CREATE TABLE IF NOT EXISTS fact_player_season_points (
  season          INTEGER NOT NULL,
  player_id       INTEGER NOT NULL,
  total_points    REAL NOT NULL,
  is_computed     INTEGER NOT NULL,   -- 1 = derived from NFL stats, not ESPN
  PRIMARY KEY (season, player_id)
);

-- Actual where ESPN gave it to us, computed where it didn't. `is_computed`
-- keeps the distinction visible so the UI can label reconstructed numbers.
DROP VIEW IF EXISTS v_player_season_any;
CREATE VIEW v_player_season_any AS
SELECT sp.season, sp.player_id, p.name, p.position, sp.total_points, sp.is_computed
FROM fact_player_season_points sp
JOIN dim_player p ON p.player_id = sp.player_id;

DROP VIEW IF EXISTS v_pos_rank;
CREATE VIEW v_pos_rank AS
SELECT season, position, player_id, name, total_points,
       ROW_NUMBER() OVER (PARTITION BY season, position
                          ORDER BY total_points DESC) AS pos_rank
FROM v_player_season_any
WHERE position IS NOT NULL;

-- SQLite forbids a correlated reference in OFFSET, so rank first then join on
-- rank = demand to pick out the replacement-level scorer.
DROP VIEW IF EXISTS v_replacement_level;
CREATE VIEW v_replacement_level AS
SELECT d.season, d.position, d.demand,
       (SELECT pr.total_points FROM v_pos_rank pr
         WHERE pr.season = d.season AND pr.position = d.position
           AND pr.pos_rank = d.demand)                    AS replacement_points
FROM v_starter_demand d;

-- Empirical replacement level: the best player at that position who went
-- UNDRAFTED that season -- i.e. what you could have had for nothing. This is
-- better than a rank-based baseline for streamed positions (K, D/ST), where far
-- more than one-per-team are actually usable.
DROP VIEW IF EXISTS v_replacement_fa;
CREATE VIEW v_replacement_fa AS
SELECT ps.season, ps.position, MAX(ps.total_points) AS fa_points
FROM v_player_season_any ps
WHERE ps.position IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM fact_draft_pick dp
                   WHERE dp.season = ps.season AND dp.player_id = ps.player_id)
GROUP BY ps.season, ps.position;

-- The baseline actually used: the harder of the two (a free agent who outscores
-- the rank-based baseline IS the true replacement).
DROP VIEW IF EXISTS v_baseline;
CREATE VIEW v_baseline AS
SELECT r.season, r.position, r.demand,
       r.replacement_points AS rank_based,
       f.fa_points          AS best_undrafted,
       MAX(COALESCE(r.replacement_points, 0), COALESCE(f.fa_points, 0)) AS baseline_points
FROM v_replacement_level r
LEFT JOIN v_replacement_fa f ON f.season = r.season AND f.position = r.position;

-- draft value, positionally fair: points above replacement per dollar
DROP VIEW IF EXISTS v_draft_value;
CREATE VIEW v_draft_value AS
SELECT dp.season, dp.overall, dp.round, dp.pick_in_round, dp.team_id,
       dp.player_id, p.name, p.position, dp.bid, dp.is_keeper,
       ps.total_points,
       rl.baseline_points AS replacement_points,
       ROUND(ps.total_points - COALESCE(rl.baseline_points, 0), 1)         AS par,
       ROUND((ps.total_points - COALESCE(rl.baseline_points, 0))
             / MAX(dp.bid, 1), 2)                                          AS par_per_dollar,
       ROUND(ps.total_points / MAX(dp.bid, 1), 2)                          AS points_per_dollar
FROM fact_draft_pick dp
JOIN dim_player p        ON p.player_id = dp.player_id
LEFT JOIN v_player_season_any ps ON ps.season = dp.season AND ps.player_id = dp.player_id
LEFT JOIN v_baseline rl ON rl.season = dp.season AND rl.position = p.position;

-- A player traded mid-season appears on BOTH NFL teams' cap tables (the old club
-- carries dead money), which double-counted him in roster payroll. Name-only
-- matching can also merge two different players who share a name -- there is a
-- QB Lamar Jackson and a CB Lamar Jackson. Resolve to exactly one row per
-- season+player, preferring the club the player actually played for that season.
DROP VIEW IF EXISTS v_player_cap;
CREATE VIEW v_player_cap AS
SELECT season, player_id, nfl_team, player_name, position,
       cap_hit, base_salary, signing_bonus, dead_cap, cap_pct
FROM (
  SELECT c.*,
         ROW_NUMBER() OVER (
           PARTITION BY c.season, c.player_id
           ORDER BY CASE WHEN c.nfl_team = ps.nfl_team THEN 0 ELSE 1 END,
                    c.cap_hit DESC) AS rn
    FROM fact_cap_hit c
    LEFT JOIN player_season ps
      ON ps.season = c.season AND ps.player_id = c.player_id
   WHERE c.player_id IS NOT NULL
)
WHERE rn = 1;

-- the headline new capability: NFL cap dollars carried by each AFFL roster
DROP VIEW IF EXISTS v_team_nfl_cap;
CREATE VIEW v_team_nfl_cap AS
SELECT r.season, r.team_id, t.name AS team_name,
       COUNT(DISTINCT r.player_id)                     AS players_matched,
       ROUND(SUM(c.cap_hit))                           AS total_cap_hit,
       ROUND(AVG(c.cap_hit))                           AS avg_cap_hit,
       ROUND(MAX(c.cap_hit))                           AS priciest_cap_hit
FROM (SELECT DISTINCT season, team_id, player_id FROM fact_roster_week) r
JOIN dim_team  t ON t.season = r.season AND t.team_id = r.team_id
JOIN v_player_cap c ON c.season = r.season AND c.player_id = r.player_id
GROUP BY r.season, r.team_id;

-- Season-long cap sums count everyone who ever passed through a roster, which
-- rewards churn. This is the cap carried by the roster as it stood in the final
-- week -- "what my team is actually worth".
DROP VIEW IF EXISTS v_team_nfl_cap_final;
CREATE VIEW v_team_nfl_cap_final AS
WITH last_wk AS (
  SELECT season, MAX(week) AS week FROM fact_roster_week GROUP BY season
)
SELECT r.season, r.team_id, t.name AS team_name,
       COUNT(DISTINCT r.player_id)                AS players_matched,
       ROUND(SUM(c.cap_hit))                      AS total_cap_hit,
       ROUND(AVG(c.cap_hit))                      AS avg_cap_hit,
       ROUND(MAX(c.cap_hit))                      AS priciest_cap_hit,
       ROUND(SUM(CASE WHEN r.started = 1 THEN c.cap_hit END)) AS starters_cap_hit
FROM fact_roster_week r
JOIN last_wk l      ON l.season = r.season AND l.week = r.week
JOIN dim_team t     ON t.season = r.season AND t.team_id = r.team_id
JOIN v_player_cap c ON c.season = r.season AND c.player_id = r.player_id
GROUP BY r.season, r.team_id;

-- League scoring rules, per season. Scoring is NOT constant across AFFL history
-- (19 rules 2014-2019, 20 from 2020, 25 in 2025), so any recomputation of
-- fantasy points from raw NFL stats must join on season.
CREATE TABLE IF NOT EXISTS dim_scoring (
  season          INTEGER NOT NULL,
  stat_id         INTEGER NOT NULL,
  stat_name       TEXT,
  points          REAL NOT NULL,
  PRIMARY KEY (season, stat_id)
);

-- ===========================================================================
-- The AFFL auction market, treated as a market.
--
-- Inspired by how NFL IQ models the draft: don't trust one opinion, model the
-- consensus. Twelve years of auction prices are revealed preference -- what this
-- specific league of twelve managers actually pays for production. Comparing
-- price paid against PAR delivered exposes where the market is systematically
-- wrong, which is an edge no public tool can have because it is your league's
-- own price history.
--
-- Read WITHIN a price tier, across positions. Comparing across tiers is
-- misleading: cheap picks are bench flyers that sit far below replacement by
-- construction, so their PAR/$ is dominated by that, not by market error.
-- ===========================================================================
DROP VIEW IF EXISTS v_market_tier;
CREATE VIEW v_market_tier AS
SELECT CASE WHEN bid >= 50 THEN '$50+'
            WHEN bid >= 25 THEN '$25-49'
            WHEN bid >= 10 THEN '$10-24'
            ELSE '$1-9' END                       AS price_tier,
       CASE WHEN bid >= 50 THEN 4 WHEN bid >= 25 THEN 3
            WHEN bid >= 10 THEN 2 ELSE 1 END      AS tier_rank,
       position,
       COUNT(*)                                   AS picks,
       ROUND(AVG(bid), 1)                         AS avg_bid,
       ROUND(AVG(par), 1)                         AS avg_par,
       ROUND(AVG(par) / NULLIF(AVG(bid), 0), 2)   AS par_per_dollar
FROM v_draft_value
WHERE bid > 0 AND par IS NOT NULL
  AND position IN ('QB', 'RB', 'WR', 'TE')
GROUP BY price_tier, tier_rank, position;

-- Per-manager skill vs the league's OWN market.
--
-- An earlier version summed raw PAR/$ per manager and made everyone look awful
-- (-1.6 to -2.5), because a roster is mostly $1 bench flyers that sit far below
-- replacement by construction. That measured roster shape, not skill.
--
-- This compares each pick against what the league typically got for that same
-- position at that same price tier. Positive edge = you beat your own league's
-- market. That is the only version of this number that means anything.
DROP VIEW IF EXISTS v_pick_edge;
CREATE VIEW v_pick_edge AS
SELECT dv.season, dv.team_id, dv.player_id, dv.name, dv.position, dv.bid, dv.par,
       CASE WHEN dv.bid >= 50 THEN '$50+' WHEN dv.bid >= 25 THEN '$25-49'
            WHEN dv.bid >= 10 THEN '$10-24' ELSE '$1-9' END AS price_tier,
       mt.avg_par                                            AS market_par,
       ROUND(dv.par - mt.avg_par, 1)                         AS edge
FROM v_draft_value dv
JOIN v_market_tier mt
  ON mt.position = dv.position
 AND mt.price_tier = CASE WHEN dv.bid >= 50 THEN '$50+' WHEN dv.bid >= 25 THEN '$25-49'
                          WHEN dv.bid >= 10 THEN '$10-24' ELSE '$1-9' END
WHERE dv.bid > 0 AND dv.par IS NOT NULL
  AND dv.position IN ('QB', 'RB', 'WR', 'TE');

DROP VIEW IF EXISTS v_manager_market;
CREATE VIEW v_manager_market AS
SELECT COALESCE(o.owner_id, t.member_id)         AS owner_id,
       COALESCE(o.display_name, m.display_name)  AS display_name,
       COUNT(*)                                  AS picks,
       ROUND(SUM(e.bid))                         AS spent,
       ROUND(SUM(e.edge), 1)                     AS total_edge,
       ROUND(AVG(e.edge), 1)                     AS edge_per_pick,
       ROUND(SUM(e.edge) / NULLIF(SUM(e.bid), 0), 3) AS edge_per_dollar
FROM v_pick_edge e
JOIN dim_team   t ON t.season = e.season AND t.team_id = e.team_id
JOIN dim_member m ON m.member_id = t.member_id
LEFT JOIN dim_owner o ON o.owner_id = m.owner_id
GROUP BY COALESCE(o.owner_id, t.member_id);


-- ===========================================================================
-- Identity / phase / GM / xTD / projections  (CONTRACTS.md)
-- ===========================================================================

DROP VIEW IF EXISTS v_team;
CREATE VIEW v_team AS
SELECT t.season, t.team_id, t.member_id, m.owner_id,
       t.name, t.abbrev, t.logo, t.wins, t.losses, t.ties,
       t.points_for, t.points_against, t.playoff_seed, t.final_rank,
       o.display_name AS owner_name
FROM dim_team t
LEFT JOIN dim_member m ON m.member_id = t.member_id
LEFT JOIN dim_owner  o ON o.owner_id = m.owner_id;

-- regular = is_playoff 0. championship = winners bracket. consolation =
-- either consolation ladder. Pre-2018 ESPN stored no tier, so those playoff
-- sides are playoff_unspecified and stay out of official W/L.
DROP VIEW IF EXISTS v_matchup;
CREATE VIEW v_matchup AS
SELECT m.*,
       CASE
         WHEN m.is_playoff = 0 THEN 'regular'
         WHEN m.tier = 'WINNERS_BRACKET' THEN 'championship'
         WHEN m.tier IN ('LOSERS_CONSOLATION_LADDER', 'WINNERS_CONSOLATION_LADDER')
           THEN 'consolation'
         ELSE 'playoff_unspecified'
       END AS phase
FROM fact_matchup m;

DROP VIEW IF EXISTS v_official_record;
CREATE VIEW v_official_record AS
SELECT m.season, m.team_id, t.member_id, t.owner_id, t.owner_name, t.name AS team_name,
       SUM(CASE WHEN m.result = 'W' THEN 1 ELSE 0 END) AS wins,
       SUM(CASE WHEN m.result = 'L' THEN 1 ELSE 0 END) AS losses,
       SUM(CASE WHEN m.result = 'T' THEN 1 ELSE 0 END) AS ties,
       ROUND(SUM(m.points), 1) AS points_for,
       ROUND(SUM(m.opponent_points), 1) AS points_against
FROM v_matchup m
JOIN v_team t ON t.season = m.season AND t.team_id = m.team_id
WHERE m.phase IN ('regular', 'championship')
GROUP BY m.season, m.team_id;

-- Regular-season standings from weekly sides. ESPN dim_team W-L-T is the
-- published record; PF/PA here is the 1-decimal box grain (CHI-24). Compare,
-- do not overwrite. CHI-26 / AFFL-005.
DROP VIEW IF EXISTS v_standings_regular;
CREATE VIEW v_standings_regular AS
SELECT m.season, m.team_id, t.member_id, t.owner_id, t.owner_name, t.name AS team_name,
       SUM(CASE WHEN m.result = 'W' THEN 1 ELSE 0 END) AS wins,
       SUM(CASE WHEN m.result = 'L' THEN 1 ELSE 0 END) AS losses,
       SUM(CASE WHEN m.result = 'T' THEN 1 ELSE 0 END) AS ties,
       SUM(m.points) AS points_for,
       SUM(m.opponent_points) AS points_against,
       COUNT(*) AS games
FROM v_matchup m
JOIN v_team t ON t.season = m.season AND t.team_id = m.team_id
WHERE m.phase = 'regular'
GROUP BY m.season, m.team_id;

-- League Legacy weighted luck: actual regular-season wins minus all-play
-- expected wins. Not Luck Index (v_luck). CHI-26 / AFFL-005.
DROP VIEW IF EXISTS v_luck_weighted;
CREATE VIEW v_luck_weighted AS
SELECT s.season, s.team_id,
       s.wins AS reg_wins,
       s.games AS reg_games,
       p.allplay_w, p.allplay_l,
       ROUND(p.power_ratio * s.games, 2) AS exp_wins,
       ROUND(s.wins - p.power_ratio * s.games, 2) AS weighted_luck
FROM v_standings_regular s
JOIN v_power p ON p.season = s.season AND p.team_id = s.team_id;

-- Weekly custody PAR, 2018-2025 only (needs fact_roster_week).
-- par = weekly points - replacement(pos, season) / weeks_in_season.
-- replacement is the Nth-best season total at the position (v_replacement_level).
CREATE TABLE IF NOT EXISTS fact_player_week_par (
  season          INTEGER NOT NULL,
  week            INTEGER NOT NULL,
  player_id       INTEGER NOT NULL,
  team_id         INTEGER NOT NULL,
  points          REAL NOT NULL,
  par             REAL,
  started         INTEGER NOT NULL,
  acquisition     TEXT NOT NULL,          -- Drafted | Traded in | Waiver | FA
  position        TEXT,
  PRIMARY KEY (season, week, team_id, player_id)
);
CREATE INDEX IF NOT EXISTS ix_pwpar_team ON fact_player_week_par(season, team_id);
CREATE INDEX IF NOT EXISTS ix_pwpar_acq  ON fact_player_week_par(season, acquisition);

DROP VIEW IF EXISTS v_custody_par;
CREATE VIEW v_custody_par AS
SELECT r.season, r.team_id, t.owner_id, t.owner_name, t.name AS team_name,
       ROUND(SUM(r.par), 1) AS par_total,
       ROUND(SUM(CASE WHEN r.acquisition = 'Drafted'    THEN r.par ELSE 0 END), 1) AS par_drafted,
       ROUND(SUM(CASE WHEN r.acquisition = 'Traded in'  THEN r.par ELSE 0 END), 1) AS par_traded_in,
       ROUND(SUM(CASE WHEN r.acquisition = 'Waiver'     THEN r.par ELSE 0 END), 1) AS par_waiver,
       ROUND(SUM(CASE WHEN r.acquisition = 'FA'         THEN r.par ELSE 0 END), 1) AS par_fa
FROM fact_player_week_par r
JOIN v_team t ON t.season = r.season AND t.team_id = r.team_id
GROUP BY r.season, r.team_id;

-- 2014-2017: no weekly lineups. Season draft PAR from draft + season totals.
-- Labeled reconstructed. Not weekly custody PAR.
CREATE TABLE IF NOT EXISTS fact_player_season_par_reconstructed (
  season          INTEGER NOT NULL,
  team_id         INTEGER NOT NULL,
  player_id       INTEGER NOT NULL,
  position        TEXT,
  points          REAL,
  par             REAL,
  acquisition     TEXT NOT NULL DEFAULT 'Drafted',
  PRIMARY KEY (season, team_id, player_id)
);

DROP VIEW IF EXISTS v_custody_par_reconstructed;
CREATE VIEW v_custody_par_reconstructed AS
SELECT r.season, r.team_id, t.owner_id, t.owner_name, t.name AS team_name,
       ROUND(SUM(r.par), 1) AS par_total,
       ROUND(SUM(CASE WHEN r.acquisition = 'Drafted' THEN r.par ELSE 0 END), 1) AS par_drafted,
       'reconstructed' AS grain
FROM fact_player_season_par_reconstructed r
JOIN v_team t ON t.season = r.season AND t.team_id = r.team_id
GROUP BY r.season, r.team_id;

-- Opportunity xTD from nflverse pbp. Empty until compute_xtd.py lands rows.
CREATE TABLE IF NOT EXISTS fact_xtd_player_week (
  season          INTEGER NOT NULL,
  week            INTEGER NOT NULL,
  gsis_id         TEXT NOT NULL,
  player_id       INTEGER,                -- ESPN id when resolved
  team_id         INTEGER,                -- AFFL roster owner that week, else NULL
  rush_td         REAL NOT NULL DEFAULT 0,
  rec_td          REAL NOT NULL DEFAULT 0,
  actual_td       REAL NOT NULL DEFAULT 0,
  rush_xtd        REAL NOT NULL DEFAULT 0,
  rec_xtd         REAL NOT NULL DEFAULT 0,
  xtd             REAL NOT NULL DEFAULT 0,
  residual        REAL NOT NULL DEFAULT 0,
  PRIMARY KEY (season, week, gsis_id)
);
CREATE INDEX IF NOT EXISTS ix_xtd_team ON fact_xtd_player_week(season, team_id);

DROP VIEW IF EXISTS v_xtd_player_season;
CREATE VIEW v_xtd_player_season AS
SELECT season, player_id, gsis_id,
       ROUND(SUM(actual_td), 2) AS actual_td,
       ROUND(SUM(xtd), 2)       AS xtd,
       ROUND(SUM(residual), 2)  AS residual
FROM fact_xtd_player_week
GROUP BY season, gsis_id;

DROP VIEW IF EXISTS v_xtd_portfolio;
CREATE VIEW v_xtd_portfolio AS
SELECT x.season, x.team_id, t.owner_id, t.owner_name, t.name AS team_name,
       ROUND(SUM(x.actual_td), 2) AS actual_td,
       ROUND(SUM(x.xtd), 2)       AS xtd,
       ROUND(SUM(x.residual), 2)  AS residual
FROM fact_xtd_player_week x
JOIN v_team t ON t.season = x.season AND t.team_id = x.team_id
WHERE x.team_id IS NOT NULL
GROUP BY x.season, x.team_id;

-- Weekly projections. source='espn' from raw mMatchup stats (statSourceId=1).
-- source='fantasypros' reserved; no historical dump is on disk.
CREATE TABLE IF NOT EXISTS fact_projection_week (
  source          TEXT NOT NULL,
  season          INTEGER NOT NULL,
  week            INTEGER NOT NULL,
  player_id       INTEGER NOT NULL,
  pass_yds REAL, pass_td REAL, interceptions REAL,
  rush_yds REAL, rush_td REAL,
  rec_yds  REAL, rec_td  REAL, receptions REAL,
  fumbles_lost REAL,
  affl_points     REAL,
  PRIMARY KEY (source, season, week, player_id)
);


-- ===========================================================================
-- Rotisserie standings. Started-player NFL stats, 2018+ only.
-- Rank 1 = best. Roto pts = nTeams - rank + 1. Consolation excluded.
-- ===========================================================================
CREATE TABLE IF NOT EXISTS fact_roto_team_season (
  season INTEGER NOT NULL,
  phase TEXT NOT NULL,                 -- regular | championship | combined
  team_id INTEGER NOT NULL,
  games INTEGER NOT NULL,
  py REAL NOT NULL DEFAULT 0,
  ptd REAL NOT NULL DEFAULT 0,
  cmp REAL NOT NULL DEFAULT 0,
  att REAL NOT NULL DEFAULT 0,
  ry REAL NOT NULL DEFAULT 0,
  rtd REAL NOT NULL DEFAULT 0,
  car REAL NOT NULL DEFAULT 0,
  rec REAL NOT NULL DEFAULT 0,
  recy REAL NOT NULL DEFAULT 0,
  retd REAL NOT NULL DEFAULT 0,
  comp_pct REAL NOT NULL DEFAULT 0,
  ypc REAL NOT NULL DEFAULT 0,
  ypr REAL NOT NULL DEFAULT 0,
  py_rank INTEGER, py_pts INTEGER,
  ptd_rank INTEGER, ptd_pts INTEGER,
  comp_pct_rank INTEGER, comp_pct_pts INTEGER,
  ry_rank INTEGER, ry_pts INTEGER,
  rtd_rank INTEGER, rtd_pts INTEGER,
  ypc_rank INTEGER, ypc_pts INTEGER,
  recy_rank INTEGER, recy_pts INTEGER,
  retd_rank INTEGER, retd_pts INTEGER,
  rec_rank INTEGER, rec_pts INTEGER,
  ypr_rank INTEGER, ypr_pts INTEGER,
  total_pts INTEGER NOT NULL,
  total_rank INTEGER NOT NULL,
  PRIMARY KEY (season, phase, team_id)
);

CREATE TABLE IF NOT EXISTS fact_roto_team_week (
  season INTEGER NOT NULL,
  phase TEXT NOT NULL,                 -- regular | championship | combined
  week INTEGER NOT NULL,
  team_id INTEGER NOT NULL,
  py REAL NOT NULL DEFAULT 0,
  ptd REAL NOT NULL DEFAULT 0,
  cmp REAL NOT NULL DEFAULT 0,
  att REAL NOT NULL DEFAULT 0,
  ry REAL NOT NULL DEFAULT 0,
  rtd REAL NOT NULL DEFAULT 0,
  car REAL NOT NULL DEFAULT 0,
  rec REAL NOT NULL DEFAULT 0,
  recy REAL NOT NULL DEFAULT 0,
  retd REAL NOT NULL DEFAULT 0,
  comp_pct REAL NOT NULL DEFAULT 0,
  ypc REAL NOT NULL DEFAULT 0,
  ypr REAL NOT NULL DEFAULT 0,
  PRIMARY KEY (season, phase, week, team_id)
);

-- CHI-27 / AFFL-007. Started-player NFL stat lines.
-- DST has no gsis. Missing skill weeks stay missing (no zero fill).
DROP VIEW IF EXISTS v_starter_nfl_week;
CREATE VIEW v_starter_nfl_week AS
SELECT r.season, r.week, r.team_id, r.player_id, p.name, p.position, p.gsis_id,
       r.slot, r.points AS affl_points,
       n.pass_yards, n.pass_tds, n.completions, n.attempts,
       n.rush_yards, n.rush_tds, n.carries,
       n.rec_yards, n.rec_tds, n.receptions, n.targets,
       n.epa,
       CASE WHEN n.gsis_id IS NOT NULL THEN 1 ELSE 0 END AS has_nfl
FROM fact_roster_week r
JOIN dim_player p ON p.player_id = r.player_id
LEFT JOIN fact_nfl_week n
  ON n.season = r.season AND n.week = r.week AND n.gsis_id = p.gsis_id
WHERE r.started = 1;

DROP VIEW IF EXISTS v_roto_standings;

CREATE VIEW v_roto_standings AS
SELECT r.season, r.phase, r.team_id, t.owner_id, t.owner_name, t.name AS team_name,
       r.games, r.py, r.ptd, r.cmp, r.att, r.comp_pct, r.ry, r.rtd, r.car, r.ypc,
       r.recy, r.retd, r.rec, r.ypr,
       r.py_rank, r.py_pts, r.ptd_rank, r.ptd_pts,
       r.comp_pct_rank, r.comp_pct_pts, r.ry_rank, r.ry_pts,
       r.rtd_rank, r.rtd_pts, r.ypc_rank, r.ypc_pts,
       r.recy_rank, r.recy_pts, r.retd_rank, r.retd_pts,
       r.rec_rank, r.rec_pts, r.ypr_rank, r.ypr_pts,
       r.total_pts, r.total_rank
  FROM fact_roto_team_season r
  JOIN v_team t ON t.season = r.season AND t.team_id = r.team_id;


-- ===========================================================================
-- Import provenance. CHI-24 / AFFL-004.
-- Checksum + adapter version + diagnostics. Not wiped on rebuild.
-- ===========================================================================
CREATE TABLE IF NOT EXISTS meta_import_run (
  run_id          INTEGER PRIMARY KEY AUTOINCREMENT,
  adapter         TEXT NOT NULL,
  adapter_version TEXT NOT NULL,
  dataset         TEXT NOT NULL,          -- matchup | roster | ...
  season          INTEGER,
  started_at      TEXT NOT NULL,          -- UTC ISO
  finished_at     TEXT,
  status          TEXT NOT NULL,          -- ok | fail
  row_count       INTEGER,
  diagnostics     TEXT                    -- JSON; no secrets
);
CREATE INDEX IF NOT EXISTS ix_import_run_ds ON meta_import_run(dataset, season);

CREATE TABLE IF NOT EXISTS meta_import_source (
  source_id       INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id          INTEGER NOT NULL REFERENCES meta_import_run(run_id),
  path            TEXT NOT NULL,          -- repo-relative, e.g. data/box_2025.json
  sha256          TEXT NOT NULL,
  bytes           INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_import_source_run ON meta_import_source(run_id);


-- ===========================================================================
-- Sidecar NFL context. CHI-72 Phase B. Loaded from cached JSON/CSV, not ESPN
-- at query time. Join on ESPN player_id / gsis_id already on dim_player.
-- Missing id stays NULL (honest empty). Do not invent 2014-17 benches.
-- ===========================================================================
CREATE TABLE IF NOT EXISTS fact_ngs (
  season          INTEGER NOT NULL,
  week            INTEGER NOT NULL,          -- 0 = season aggregate
  season_type     TEXT NOT NULL DEFAULT 'REG',
  gsis_id         TEXT NOT NULL,
  player_id       INTEGER,                   -- ESPN id when dim_player has it
  kind            TEXT NOT NULL,             -- passing | rushing | receiving
  attempts REAL, completions REAL, cmp_pct REAL,
  pass_yards REAL, pass_td REAL, interceptions REAL,
  passer_rating REAL, cpoe REAL, time_to_throw REAL, aggressiveness REAL,
  intended_air_yards REAL,
  rush_attempts REAL, rush_yards REAL, rush_td REAL,
  efficiency REAL, stacked_box_pct REAL, ryoe REAL, ryoe_per_att REAL,
  targets REAL, receptions REAL, rec_yards REAL, rec_td REAL,
  avg_cushion REAL, avg_separation REAL, yac_above_expectation REAL,
  intended_air_yards_share REAL,
  PRIMARY KEY (season, week, season_type, gsis_id, kind)
);
CREATE INDEX IF NOT EXISTS ix_ngs_gsis ON fact_ngs(gsis_id);
CREATE INDEX IF NOT EXISTS ix_ngs_player ON fact_ngs(player_id);
CREATE INDEX IF NOT EXISTS ix_ngs_season ON fact_ngs(season, kind);

CREATE TABLE IF NOT EXISTS dim_player_bio (
  player_id       INTEGER PRIMARY KEY,       -- ESPN
  gsis_id         TEXT,
  birth           TEXT,
  college         TEXT,
  college_logo    TEXT,
  draft_year      INTEGER,
  draft_round     INTEGER,
  draft_pick      INTEGER,
  draft_team      TEXT,
  breakout_age    REAL,
  dominator       REAL,
  early_declare   INTEGER,
  class_year      INTEGER,
  age_by_year     TEXT,                      -- JSON {season: age}
  nfl_by_year     TEXT                       -- JSON {season: nfl team}
);
CREATE INDEX IF NOT EXISTS ix_bio_gsis ON dim_player_bio(gsis_id);

CREATE TABLE IF NOT EXISTS fact_injury (
  player_id       INTEGER PRIMARY KEY,       -- ESPN athleteId; current snapshot
  gsis_id         TEXT,
  name            TEXT,
  status          TEXT,
  comment         TEXT,
  team            TEXT,
  date            TEXT
);
CREATE INDEX IF NOT EXISTS ix_injury_gsis ON fact_injury(gsis_id);

CREATE TABLE IF NOT EXISTS fact_depthchart (
  player_id       INTEGER PRIMARY KEY,       -- ESPN athleteId; current snapshot
  gsis_id         TEXT,
  name            TEXT,
  team            TEXT,
  pos             TEXT,
  rank            INTEGER,
  depth           TEXT
);
CREATE INDEX IF NOT EXISTS ix_depth_gsis ON fact_depthchart(gsis_id);

-- 9 rookies in the cache. Do not invent more.
CREATE TABLE IF NOT EXISTS fact_college (
  player_id       INTEGER PRIMARY KEY,
  gsis_id         TEXT,
  name            TEXT,
  college         TEXT,
  years           TEXT,                      -- JSON list of season ints
  line            TEXT,
  source          TEXT
);

-- Thin news/overview cache (15 players). Not a complete league feed.
CREATE TABLE IF NOT EXISTS fact_player_overview (
  player_id       INTEGER PRIMARY KEY,
  gsis_id         TEXT,
  name            TEXT,
  college         TEXT,
  draft           TEXT,
  headshot_fallback TEXT,
  next_game       TEXT,                      -- JSON
  news            TEXT,                      -- JSON array
  rotowire        TEXT
);

-- ── Savant-class NFL metrics (CHI-113 / CHI-114) ─────────────────────────
-- Merged from verify/full-audit. Play grain is never stored or shipped;
-- these are player-week and player-season rollups joined via gsis_id.

-- Play-by-play rolled to player-week. Raw nflverse PBP is ~20MB gzip / ~100MB
-- CSV per season; we do not keep play grain or ship it to the public site.
-- Join to AFFL via dim_player.gsis_id. Receptions here are volume, not PPR.
CREATE TABLE IF NOT EXISTS fact_pbp_agg (
  season          INTEGER NOT NULL,
  week            INTEGER NOT NULL,
  gsis_id         TEXT NOT NULL,
  dropbacks       REAL, pass_attempts REAL, completions REAL,
  pass_epa        REAL, cpoe REAL, cpoe_n REAL,
  pass_air_yards  REAL, pass_success REAL, pass_success_n REAL,
  pass_td         REAL, pass_xtd REAL, rz_pass REAL, gl_pass REAL,
  rush_att        REAL, rush_epa REAL, rush_success REAL, rush_success_n REAL,
  rush_td         REAL, rush_xtd REAL, rz_rush REAL, gl_rush REAL,
  targets         REAL, receptions REAL, rec_epa REAL,
  rec_air_yards   REAL, rec_success REAL, rec_success_n REAL,
  rec_td          REAL, rec_xtd REAL, rz_tgt REAL, gl_tgt REAL,
  xyac            REAL, xyac_n REAL,
  PRIMARY KEY (season, week, gsis_id)
);
CREATE INDEX IF NOT EXISTS ix_pbp_gsis ON fact_pbp_agg(gsis_id);

-- AFFL-scored expected fantasy points. Non-PPR: receptions are volume only.
CREATE TABLE IF NOT EXISTS fact_player_xfp (
  season          INTEGER NOT NULL,
  player_id       INTEGER NOT NULL,
  games           INTEGER,
  fp              REAL,          -- AFFL recomputed from fact_nfl_week
  xfp             REAL,          -- same engine, xTD + air/xYAC rec yards
  fpoe            REAL,          -- fp - xfp
  fp_g            REAL,
  xfp_g           REAL,
  st_games        INTEGER,       -- AFFL starts (2018+)
  st_fp           REAL,
  st_xfp          REAL,
  st_fpoe         REAL,
  wopr            REAL,
  target_share    REAL,
  air_yards_share REAL,
  rz_opp          REAL,
  gl_opp          REAL,
  xtd             REAL,
  td_luck         REAL,
  targets         REAL,
  carries         REAL,
  opp             REAL,
  PRIMARY KEY (season, player_id)
);
