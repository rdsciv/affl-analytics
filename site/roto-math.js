/* Port of AFFL_Pillars src/lib/phase.ts + categoryStats.ts + rotoCareer.ts
 * Methodology only. Totals are computed from pillars/boxscores/*.json at runtime.
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

  function computeCategoryStats(box, season, phase, includeConsolation) {
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

    const teamMeta = new Map((season.teams || []).map((t) => [t.teamId, t]));
    const nTeams = totals.size;
    const derived = [...totals.entries()].map(([teamId, raw]) => ({
      teamId,
      games: raw.games,
      values: {
        py: raw.py,
        ptd: raw.ptd,
        compPct: raw.att > 0 ? (raw.cmp / raw.att) * 100 : 0,
        ry: raw.ry,
        rtd: raw.rtd,
        ypc: raw.car > 0 ? raw.ry / raw.car : 0,
        recy: raw.recy,
        retd: raw.retd,
        rec: raw.rec,
        ypr: raw.rec > 0 ? raw.recy / raw.rec : 0,
      },
    }));

    const rankAndNorm = new Map();
    for (const cat of CATS) {
      const vals = derived.map((d) => d.values[cat.key]);
      const min = Math.min(...vals);
      const max = Math.max(...vals);
      const span = max - min || 1;
      const sorted = [...derived].sort((a, b) => b.values[cat.key] - a.values[cat.key]);
      sorted.forEach((d, i) => {
        const rank = i + 1;
        const pts = nTeams - rank + 1;
        const norm = (d.values[cat.key] - min) / span;
        if (!rankAndNorm.has(d.teamId)) rankAndNorm.set(d.teamId, new Map());
        rankAndNorm.get(d.teamId).set(cat.key, { rank, pts, norm });
      });
    }

    const out = derived.map((d) => {
      const t = teamMeta.get(d.teamId);
      const categories = CATS.map((cat) => {
        const rn = rankAndNorm.get(d.teamId).get(cat.key);
        return { key: cat.key, label: cat.label, group: cat.group, value: d.values[cat.key], ...rn };
      });
      const totalPts = categories.reduce((a, c) => a + c.pts, 0);
      return {
        teamId: d.teamId,
        ownerId: (t && t.ownerId) || "",
        teamName: (t && t.teamName) || "Team " + d.teamId,
        categories,
        totalPts,
        totalRank: 0,
        games: d.games,
      };
    });
    out.sort((a, b) => b.totalPts - a.totalPts);
    out.forEach((t, i) => { t.totalRank = i + 1; });
    return out;
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
      const vals = teams.map((t) => t.categories.find((c) => c.key === cat.key).value);
      const min = Math.min.apply(null, vals);
      const max = Math.max.apply(null, vals);
      const span = max - min || 1;
      const mean = vals.reduce((a, v) => a + v, 0) / vals.length;
      avg[cat.key] = (mean - min) / span;
    }
    return avg;
  }

  function formatCatValue(c) {
    if (c.key === "compPct") return c.value.toFixed(1) + "%";
    if (c.key === "ypc" || c.key === "ypr") return c.value.toFixed(2);
    return Math.round(c.value).toLocaleString();
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

  global.AFFLRoto = {
    CATS, PHASE_LABEL, tierInPhase, computeCategoryStats, buildRotoCareer,
    leagueAverageNorm, formatCatValue, rankCellBg, ordinal,
  };
})(window);
