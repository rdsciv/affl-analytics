# CHI-180 — QB leaders proof (ScraprBot)

**Grain:** `fact_roster_week` started=1, AFFL `points` (NON_PPR). Not NFL FP.

## Warehouse career (truth)

| Player | ESPN id | Starts | AFFL started pts | Pts/start | Years
|--------|---------|-------:|-----------------:|----------:|------
| Patrick Mahomes | 3139477 | **111** | **2414.8** | 21.75 | 2018–2025
| Josh Allen (QB) | 3918298 | **100** | **2330.0** | 23.30 | 2018–2025
| Russell Wilson | 14881 | **103** | **1996.8** | 19.39 | 2014–2025

Ryan’s read is correct: Mahomes > Allen > Wilson on career AFFL started points.

## Why the site looks wrong

In `site/players.js` `careerPlayers()`:

1. Sums `years/*.json` `stPts`/`starts` (AFFL) — then **overwrites `tot` with `nflCareerPts(pid)`** from `nfl_weeks.json`.
2. DB sort label is **"AFFL pts"** but sorts/displays that NFL `tot`.
3. Wilson NFL career FP ≈ **3213.4** over 182 NFL games; years.json only has his **2018+** AFFL slice (**60** starts / **1141.8** stPts). **3213.4 / 60 ≈ 53.6** — matches the ~53 "pts/start" FAIL.

`site/years/*.json` also undercounts Wilson AFFL starts (60 vs book 103) because 2014–17 are not in year player payloads the same way.

## Fix (Ork)

- Leaders `tot` must be AFFL started pts (`stPts` career sum), never `nflCareerPts`.
- Career starts/pts for 2014–17 players must include pre-2018 starts (`pre2018_starts` / roster weeks), not years.json 2018+ only.
- Keep NFL FP as a separate column if needed — do not label it AFFL.
