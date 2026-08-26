/* CHI-120 real History book. All-Play on All = career 2014-2025. No remote core. */
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
