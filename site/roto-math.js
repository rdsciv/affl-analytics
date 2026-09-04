/* Port of AFFL_Pillars category stats + CHI-149 All-grain career roto.
 * Season tables: one year, equal G. All: scored seasons 2014–2025 (2014–17 = AFFL starter × nflverse week, NON_PPR).
 * Rate cats on All are pooled (cmp/att, ry/car, recy/rec), never mean of yearly rates.
 */
(function (global) {
  const CATS = [
    { key: "py", label: "Pass Yds", group: "Passing" },
    { key: "ptd", label: "Pass TD", group: "Passing" },
    { key: "compPct", label: "Comp%", group: "Passing" },
    { key: "ry", label: "Rush Yds", group: "Rushing" },
    { key: "rtd", label: "Rush TD", group: "Rushing" },
    { key: "ypc", label: "YPC", group: "Rushing" },
    { key: "recy", label: "Rec Yds", group: "Receiving" },
    { key: "retd", label: "Rec TD", group: "Receiving" },
    { key: "rec", label: "Rec", group: "Receiving" },
    { key: "ypr", label: "YPR", group: "Receiving" },
  ];

  const COUNTING_KEYS = ["py", "ptd", "ry", "rtd", "recy", "retd", "rec"];
  const RATE_KEYS = ["compPct", "ypc", "ypr"];
  const SCORED_YEARS = [2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025];
  const UNAVAILABLE_YEARS = []; /* CHI-162: 2014–17 now scored via starter×nflverse */
  const PHASE_LABEL = { reg: "Regular", post: "Postseason", combined: "Combined" };

  function isConsolation(tier) {
    return tier === "WINNERS_CONSOLATION_LADDER" || tier === "LOSERS_CONSOLATION_LADDER";
  }

  function tierInPhase(tier, phase, includeConsolation) {
    if (isConsolation(tier) && !includeConsolation) return false;
    if (phase === "combined") return true;
    return phase === "reg" ? tier === "NONE" : tier !== "NONE";
  }

  function emptyTotals() {
    return { py: 0, ptd: 0, cmp: 0, att: 0, ry: 0, rtd: 0, car: 0, rec: 0, recy: 0, retd: 0, games: 0 };
  }

  function addRaw(dst, src) {
    dst.py += src.py || 0;
    dst.ptd += src.ptd || 0;
    dst.cmp += src.cmp || 0;
    dst.att += src.att || 0;
    dst.ry += src.ry || 0;
    dst.rtd += src.rtd || 0;
    dst.car += src.car || 0;
    dst.rec += src.rec || 0;
    dst.recy += src.recy || 0;
    dst.retd += src.retd || 0;
    dst.games += src.games || 0;
    return dst;
  }

  function scheduleG(year) {
    const y = +year;
    if (y >= 2021 && y <= 2025) return 14;
    if (y >= 2014 && y <= 2020) return 13;
    return 0;
  }

  function isScoredYear(year) {
    const y = +year;
    return y >= 2014 && y <= 2025;
  }

  function isUnavailableYear(year) {
    return false; /* CHI-162: 2014–17 scored */
  }

  function valuesFromRaw(raw) {
    return {
      py: raw.py,
      ptd: raw.ptd,
      compPct: raw.att > 0 ? (raw.cmp / raw.att) * 100 : null,
      ry: raw.ry,
      rtd: raw.rtd,
      ypc: raw.car > 0 ? raw.ry / raw.car : null,
      recy: raw.recy,
      retd: raw.retd,
      rec: raw.rec,
      ypr: raw.rec > 0 ? raw.recy / raw.rec : null,
    };
  }

  function accumulateRaw(box, phase, includeConsolation) {
    phase = phase || "reg";
    includeConsolation = !!includeConsolation;
    const totals = new Map();
    const T = (tid) => {
      if (!totals.has(tid)) totals.set(tid, emptyTotals());
      return totals.get(tid);
    };
    const weeks = box && box.weeks ? Object.values(box.weeks) : [];
    for (const games of weeks) {
      for (const g of games) {
        if (!tierInPhase(g.tier, phase, includeConsolation)) continue;
        for (const side of [g.home, g.away]) {
          if (!side || side.teamId == null) continue;
          const t = T(side.teamId);
          t.games += 1;
          for (const p of side.starters || []) {
            if (!p.st) continue;
            t.py += p.st.py || 0;
            t.ptd += p.st.ptd || 0;
            t.cmp += p.st.cmp || 0;
            t.att += p.st.att || 0;
            t.ry += p.st.ry || 0;
            t.rtd += p.st.rtd || 0;
            t.car += p.st.car || 0;
            t.rec += p.st.rec || 0;
            t.recy += p.st.recy || 0;
            t.retd += p.st.retd || 0;
          }
        }
      }
    }
    return totals;
  }

  function rankTeams(derived, metaOf) {
    const nTeams = derived.length;
    const rankAndNorm = new Map();
    for (const cat of CATS) {
      const present = derived.filter((d) => {
        const v = d.values[cat.key];
        return v != null && !Number.isNaN(Number(v));
      });
      const vals = present.map((d) => d.values[cat.key]);
      const min = vals.length ? Math.min.apply(null, vals) : 0;
      const max = vals.length ? Math.max.apply(null, vals) : 0;
      const span = max - min || 1;
      const sorted = present.slice().sort((a, b) => b.values[cat.key] - a.values[cat.key]);
      sorted.forEach((d, i) => {
        const rank = i + 1;
        const pts = nTeams - rank + 1;
        const norm = (d.values[cat.key] - min) / span;
        if (!rankAndNorm.has(d.id)) rankAndNorm.set(d.id, new Map());
        rankAndNorm.get(d.id).set(cat.key, { rank, pts, norm });
      });
      derived.forEach((d) => {
        if (!rankAndNorm.has(d.id)) rankAndNorm.set(d.id, new Map());
        if (!rankAndNorm.get(d.id).has(cat.key)) {
          rankAndNorm.get(d.id).set(cat.key, { rank: nTeams, pts: 1, norm: null });
        }
      });
    }
    const out = derived.map((d) => {
      const meta = metaOf ? metaOf(d) : {};
      const categories = CATS.map((cat) => {
        const rn = rankAndNorm.get(d.id).get(cat.key);
        return { key: cat.key, label: cat.label, group: cat.group, value: d.values[cat.key], ...rn };
      });
      const totalPts = categories.reduce((a, c) => a + c.pts, 0);
      return {
        teamId: d.teamId,
        ownerId: d.ownerId || (meta && meta.ownerId) || "",
        teamName: d.teamName || (meta && meta.teamName) || "Team " + d.id,
        categories,
        totalPts,
        totalRank: 0,
        games: d.games,
        nSeasons: d.nSeasons || 1,
        years: d.years || [],
        raw: d.raw,
      };
    });
    out.sort((a, b) => b.totalPts - a.totalPts || a.teamName.localeCompare(b.teamName));
    out.forEach((t, i) => { t.totalRank = i + 1; });
    return out;
  }

  function computeCategoryStats(box, season, phase, includeConsolation) {
    phase = phase || "reg";
    includeConsolation = !!includeConsolation;
    const totals = accumulateRaw(box, phase, includeConsolation);
    const year = (season && season.year) || (box && box.year);
    const teamMeta = new Map(((season && season.teams) || []).map((t) => [t.teamId, t]));
    const sched = phase === "reg" ? scheduleG(year) : 0;
    const derived = [...totals.entries()].map(([teamId, raw]) => {
      const t = teamMeta.get(teamId);
      return {
        id: teamId,
        teamId,
        ownerId: (t && t.ownerId) || "",
        teamName: (t && t.teamName) || "Team " + teamId,
        games: phase === "reg" && sched ? sched : raw.games,
        values: valuesFromRaw(raw),
        raw,
        nSeasons: 1,
        years: year ? [year] : [],
      };
    });
    return rankTeams(derived);
  }

  /* CHI-149 All grain.
   * ownerOf(year, teamId) -> franchise id (already canon). Skip owners with 0 scored years.
   * grain: "averages" (default) | "totals"
   * Counting cats: total / nScoredYears (averages) or career sum (totals).
   * Rate cats: always pooled from raw cmp/att, ry/car, recy/rec.
   * TOTAL PTS: ranks of the DISPLAYED numbers, not mean of yearly TOTAL PTS.
   * G (reg): (13*n13 + 14*n14) / n  or the sum. Post/combined: mean/sum of actual games.
   */
  function buildAllRoto(loads, phase, grain, opts) {
    phase = phase || "reg";
    grain = grain === "totals" ? "totals" : "averages";
    opts = opts || {};
    const ownerOf = opts.ownerOf;
    const skip = opts.skipOwners || { m22: true };
    const buckets = new Map();
    const scoredYears = [];
    const missingYears = [];

    for (const load of loads || []) {
      const year = load.year;
      if (!isScoredYear(year)) {
        if (year != null) missingYears.push(year);
        continue;
      }
      if (!load.box || !load.season) { missingYears.push(year); continue; }
      const totals = accumulateRaw(load.box, phase, false);
      if (!totals.size) { missingYears.push(year); continue; }
      scoredYears.push(year);
      const sched = scheduleG(year);
      for (const [teamId, raw] of totals.entries()) {
        const oid = ownerOf ? ownerOf(year, teamId) : raw.ownerId;
        if (!oid || skip[oid]) continue;
        let b = buckets.get(oid);
        if (!b) {
          b = { ownerId: oid, years: [], n13: 0, n14: 0, raw: emptyTotals(), boxGames: 0 };
          buckets.set(oid, b);
        }
        addRaw(b.raw, raw);
        b.boxGames += raw.games || 0;
        if (b.years.indexOf(year) < 0) {
          b.years.push(year);
          if (year >= 2014 && year <= 2020) b.n13 += 1;
          if (year >= 2021 && year <= 2025) b.n14 += 1;
        }
      }
    }

    const rows = [...buckets.values()].filter((b) => b.years.length > 0);
    if (!rows.length) {
      return { teams: [], scoredYears, missingYears, evidence: "Unavailable", grain };
    }

    const derived = rows.map((b) => {
      const n = b.years.length;
      const raw = b.raw;
      const pooled = valuesFromRaw(raw);
      const values = {
        py: grain === "totals" ? raw.py : raw.py / n,
        ptd: grain === "totals" ? raw.ptd : raw.ptd / n,
        ry: grain === "totals" ? raw.ry : raw.ry / n,
        rtd: grain === "totals" ? raw.rtd : raw.rtd / n,
        recy: grain === "totals" ? raw.recy : raw.recy / n,
        retd: grain === "totals" ? raw.retd : raw.retd / n,
        rec: grain === "totals" ? raw.rec : raw.rec / n,
        compPct: pooled.compPct,
        ypc: pooled.ypc,
        ypr: pooled.ypr,
      };
      let games;
      if (phase === "reg") {
        const gSum = 13 * b.n13 + 14 * b.n14;
        games = grain === "totals" ? gSum : (n ? gSum / n : 0);
      } else {
        games = grain === "totals" ? b.boxGames : (n ? b.boxGames / n : 0);
      }
      return {
        id: b.ownerId,
        teamId: b.ownerId,
        ownerId: b.ownerId,
        teamName: b.ownerId,
        games,
        values,
        raw,
        nSeasons: n,
        years: b.years.slice().sort((a, c) => a - c),
        n13: b.n13,
        n14: b.n14,
      };
    });

    const teams = rankTeams(derived);
    return {
      teams,
      scoredYears: scoredYears.slice().sort((a, b) => a - b),
      missingYears,
      evidence: missingYears.length ? "Partial" : "Verified",
      grain,
    };
  }

  function buildRotoCareer(loads, phase, includeConsolation) {
    phase = phase || "reg";
    const scoredYears = [];
    const missingYears = [];
    const acc = new Map();
    for (const { year, season, box } of loads) {
      if (!season || !box) { missingYears.push(year); continue; }
      const teams = computeCategoryStats(box, season, phase, includeConsolation);
      if (!teams.length) { missingYears.push(year); continue; }
      scoredYears.push(year);
      for (const t of teams) {
        if (!t.ownerId) continue;
        const c = acc.get(t.ownerId) || {
          ownerId: t.ownerId, seasons: 0, avgRank: 0, bestRank: Infinity, worstRank: 0, avgPts: 0, byYear: new Map(),
        };
        c.seasons += 1;
        c.avgRank += t.totalRank;
        c.avgPts += t.totalPts;
        c.bestRank = Math.min(c.bestRank, t.totalRank);
        c.worstRank = Math.max(c.worstRank, t.totalRank);
        c.byYear.set(year, { rank: t.totalRank, pts: t.totalPts, nTeams: teams.length });
        acc.set(t.ownerId, c);
      }
    }
    if (!scoredYears.length) {
      return { rows: [], scoredYears, missingYears, evidence: "Unavailable" };
    }
    const rows = [...acc.values()]
      .map((c) => ({ ...c, avgRank: c.avgRank / c.seasons, avgPts: c.avgPts / c.seasons }))
      .sort((a, b) => a.avgRank - b.avgRank);
    return {
      rows,
      scoredYears,
      missingYears,
      evidence: missingYears.length ? "Partial" : "Verified",
    };
  }

  function leagueAverageNorm(teams) {
    const avg = {};
    if (!teams.length) return avg;
    for (const cat of CATS) {
      const vals = teams.map((t) => t.categories.find((c) => c.key === cat.key).value).filter((v) => v != null && !Number.isNaN(Number(v)));
      if (!vals.length) { avg[cat.key] = 0; continue; }
      const min = Math.min.apply(null, vals);
      const max = Math.max.apply(null, vals);
      const span = max - min || 1;
      const mean = vals.reduce((a, v) => a + v, 0) / vals.length;
      avg[cat.key] = (mean - min) / span;
    }
    return avg;
  }

  function formatCatValue(c) {
    if (c.value == null || Number.isNaN(Number(c.value))) return "—";
    if (c.key === "compPct") return Number(c.value).toFixed(1) + "%";
    if (c.key === "ypc" || c.key === "ypr") return Number(c.value).toFixed(2);
    return Math.round(c.value).toLocaleString();
  }

  function formatGames(g, grain, allMode) {
    if (g == null || Number.isNaN(Number(g))) return "—";
    if (allMode && grain === "averages") return Number(g).toFixed(1);
    return String(Math.round(Number(g)));
  }

  function rankCellBg(rank, nTeams) {
    const p = nTeams > 1 ? 1 - (rank - 1) / (nTeams - 1) : 0.5;
    const d = Math.abs(p - 0.5);
    if (d < 1e-6) return "transparent";
    const a = Math.min(0.85, 0.12 + d * 0.7);
    return p > 0.5 ? "rgba(55,207,131," + a + ")" : "rgba(236,106,106," + a + ")";
  }

  function ordinal(n) {
    const s = ["th", "st", "nd", "rd"];
    const v = n % 100;
    return n + (s[(v - 20) % 10] || s[v] || s[0]);
  }

  function yearlyRatesMean(yearValues, key) {
    if (!yearValues || !yearValues.length) return 0;
    return yearValues.reduce((a, v) => a + (v[key] || 0), 0) / yearValues.length;
  }

  const api = {
    CATS, COUNTING_KEYS, RATE_KEYS, SCORED_YEARS, UNAVAILABLE_YEARS, PHASE_LABEL,
    tierInPhase, emptyTotals, addRaw, scheduleG, isScoredYear, isUnavailableYear,
    valuesFromRaw, accumulateRaw, computeCategoryStats, buildAllRoto, buildRotoCareer,
    leagueAverageNorm, formatCatValue, formatGames, rankCellBg, ordinal, yearlyRatesMean,
  };

  if (typeof module !== "undefined" && module.exports) module.exports = api;
  global.AFFLRoto = api;
})(typeof window !== "undefined" ? window : (typeof global !== "undefined" ? global : this));
