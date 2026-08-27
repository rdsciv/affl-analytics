# CHI-130 eval outline

Lock: `data.json` franchise.years is the book. Do not rewrite it.

## Must pass

1. m22 Gabagooners `years === []`. `franchisePlayedSeason(m22, y)` is false for every y in 2014–2025.
2. 2014 `ownersForSeason(2014)` is exactly m11 m09 m08 m16 m12 m02 m18 m15 m17 m13.
3. 2014 excludes m19 Pounders, m14 Pollywogs, m22 Gabagooners, m05 Shadowcöcks, m21 Pipers, m06 Fat Cats.
4. m18 Feelers played 2014 and 2025.
5. m19 Pounders false for 2014–2020, true for 2021–2025.
6. m14 Pollywogs same window as Pounders.
7. m07 Chupacabras true 2016–2023, false 2014–2015 and 2024–2025.
8. `seasonScope(null).year === null` (never 2025).
9. Live `history.js` must not contain `seasonYear = y == null ? latestFinished() : y`.
10. `clampYear(2014, "m22")` is null, not 2014.
11. Age scatter All still uses as-of year (CHI-128). Do not regress `ageScatterSeason`.
12. No `CURRENT_2026` season painted.

## Must not do

- Treat empty years as all league years.
- Invent 2014–17 benches or transactions.
- Adopt D3 / Plotly.
- Mark Linear Done before Ryan reviews live.
