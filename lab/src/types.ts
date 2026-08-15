export interface PlayerWeek {
  season: number
  week: number
  player_name: string
  position: string
  team_name: string
  fantasy_points: number
  nfl_epa: number | null
  pass_yards: number | null
  pass_tds: number | null
  rush_yards: number | null
  rush_tds: number | null
  receptions: number | null
  rec_yards: number | null
  rec_tds: number | null
  cap_hit_m: number | null
}
