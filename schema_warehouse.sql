-- ============================================================================
-- Warehouse views: cross-database joins between affl.db and nfl.db
-- This file is executed after ATTACH DATABASE 'nfl.db' AS nfl
-- ============================================================================

-- A player traded mid-season appears on BOTH NFL teams' cap tables (the old club
-- carries dead money), which double-counted him in roster payroll. Name-only
-- matching can also merge two different players who share a name -- there is a
-- QB Lamar Jackson and a CB Lamar Jackson. Resolve to exactly one row per
-- season+player, preferring the club the player actually played for that season.
DROP VIEW IF EXISTS v_player_cap;
CREATE VIEW v_player_cap AS
SELECT season, player_id, gsis_id, nfl_team, player_name, position,
       cap_hit, base_salary, signing_bonus, dead_cap, cap_pct
FROM (
  SELECT c.*,
         ROW_NUMBER() OVER (
           PARTITION BY c.season, c.player_id
           ORDER BY CASE WHEN c.nfl_team = ps.nfl_team THEN 0 ELSE 1 END,
                    c.cap_hit DESC) AS rn
    FROM nfl.fact_cap_hit c
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

-- Started fantasy points vs NFL EPA: the join-based view for TanStack lab
DROP VIEW IF EXISTS v_started_vs_nfl;
CREATE VIEW v_started_vs_nfl AS
SELECT r.season, r.week, r.team_id, t.name AS team_name, t.member_id,
       r.player_id, p.name AS player_name, p.position,
       r.points AS fantasy_points,
       n.epa AS nfl_epa,
       n.pass_yards, n.pass_tds, n.rush_yards, n.rush_tds,
       n.rec_yards, n.rec_tds, n.receptions, n.targets,
       c.cap_hit, c.nfl_team
FROM fact_roster_week r
JOIN dim_player p ON p.player_id = r.player_id
JOIN dim_team t ON t.season = r.season AND t.team_id = r.team_id
LEFT JOIN nfl.fact_nfl_week n ON n.season = r.season AND n.week = r.week
                                AND n.gsis_id = p.gsis_id
LEFT JOIN nfl.fact_cap_hit c ON c.season = r.season AND c.player_id = r.player_id
WHERE r.started = 1 AND p.position IN ('QB','RB','WR','TE');
