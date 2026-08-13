-- ============================================================================
-- AFFL database: League truth only
-- dim_season/member/team/player/scoring, fact_roster_week, fact_matchup,
-- fact_draft_pick, fact_transaction, fact_trade/_item
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

CREATE TABLE IF NOT EXISTS dim_member (
  member_id       TEXT PRIMARY KEY,       -- m01..m21 (never a real ESPN SWID)
  display_name    TEXT NOT NULL,
  is_active       INTEGER NOT NULL DEFAULT 0
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

-- trades are reconstructed from roster movement, not the transaction feed
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

-- ============================================================================
-- Views: AFFL-only metrics (those requiring joins to NFL will be in warehouse)
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

-- all-play / power ranking: how you'd do against the whole league every week
DROP VIEW IF EXISTS v_power;
CREATE VIEW v_power AS
SELECT season, team_id,
       SUM(beat_this_week)                                    AS allplay_w,
       SUM(field_size - beat_this_week)                       AS allplay_l,
       ROUND(1.0 * SUM(beat_this_week) /
             NULLIF(SUM(field_size), 0), 4)                   AS power_pct
FROM v_team_week
WHERE is_playoff = 0
GROUP BY season, team_id;

-- FantasyGenius luck: won while in the bottom half / lost while in the top half
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

DROP VIEW IF EXISTS v_pos_rank;
CREATE VIEW v_pos_rank AS
SELECT season, position, player_id, name, total_points,
       ROW_NUMBER() OVER (PARTITION BY season, position
                          ORDER BY total_points DESC) AS pos_rank
FROM v_player_season
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
FROM v_player_season ps
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
LEFT JOIN v_player_season ps ON ps.season = dp.season AND ps.player_id = dp.player_id
LEFT JOIN v_baseline rl ON rl.season = dp.season AND rl.position = p.position;
