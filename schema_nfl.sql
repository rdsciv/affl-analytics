-- ============================================================================
-- NFL database: NFL/player truth only
-- fact_nfl_week, fact_contract, fact_cap_hit
-- Also includes player_season for NFL club membership (this is NFL truth)
-- ============================================================================

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- a player's NFL club can change mid-career, so it is season-scoped
-- (duplicated from AFFL for convenience in NFL-only queries)
CREATE TABLE IF NOT EXISTS player_season (
  season          INTEGER NOT NULL,
  player_id       INTEGER NOT NULL,      -- ESPN id (for join back to AFFL)
  gsis_id         TEXT,                  -- nflverse join key
  nfl_team        TEXT,
  PRIMARY KEY (season, player_id)
);
CREATE INDEX IF NOT EXISTS ix_nfl_ps_gsis ON player_season(gsis_id);

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
  gsis_id         TEXT,                   -- nflverse join key
  position        TEXT,
  cap_hit         REAL,
  base_salary     REAL,
  signing_bonus   REAL,
  dead_cap        REAL,
  cap_pct         REAL,
  PRIMARY KEY (season, nfl_team, player_name)
);
CREATE INDEX IF NOT EXISTS ix_cap_player ON fact_cap_hit(player_id);
CREATE INDEX IF NOT EXISTS ix_cap_gsis ON fact_cap_hit(gsis_id);
