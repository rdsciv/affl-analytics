/* AFFL History — current name, leeger career, positional PPD. */
(async function () {
  const A = window.AFFL;
  const { DATA } = await A.boot();
  const [ALL, MOVES, WAIVERS, NGS_PROFILES, PRE2018_SEASON_ROSTERS] = await Promise.all([
    A.loadAllYears(),
    fetch("moves.json?v=" + Date.now(), { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : {}))
      .catch(() => ({})),
    fetch("waivers.json?v=" + Date.now(), { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : {}))
      .catch(() => ({})),
    fetch("ngs_profiles.json?v=" + Date.now(), { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : { franchises: [] }))
      .catch(() => ({ franchises: [] })),
    fetch("pre2018_season_rosters.json?v=" + Date.now(), { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : {}))
      .catch(() => ({})),
  ]);
  await A.loadBios();
  const $ = (id) => document.getElementById(id);

  const MERGE = { m01: "m07", m03: "m08", m20: "m10" };
  const canon = (id) => MERGE[id] || id;
  const POS = ["QB", "RB", "WR", "TE", "K", "DST"];

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"]/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;",
    }[c]));
  }

  function latestFinished() {
    const ys = (A.years() || []).filter((y) => y >= 2014 && y <= 2025).sort((a, b) => b - a);
    return ys[0] || 2025;
  }
  function parseSeasonParam(raw) {
    if (raw == null || raw === "" || String(raw).toLowerCase() === "all") return null;
    const y = +raw;
    if (!y || y < 2014 || y > 2025) return null;
    if ((A.years() || []).indexOf(y) < 0) return null;
    return y;
  }

  /* remaining history.js loaded from same-origin after this boot patch */
  const qsYear = new URLSearchParams(location.search).get("year");
  let pickedYear = parseSeasonParam(qsYear);
  let seasonYear = pickedYear == null ? latestFinished() : pickedYear;

  window.__AFFL_CHI119 = { latestFinished, parseSeasonParam, pickedYear, seasonYear, esc, canon, MERGE, POS, $, ALL, MOVES, WAIVERS, NGS_PROFILES, PRE2018_SEASON_ROSTERS, DATA, A };
})();
