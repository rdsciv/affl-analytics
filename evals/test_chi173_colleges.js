#!/usr/bin/env node
/* CHI-173: Colleges leaderboard — real AFFL start weeks by bio.college, CHI-114 join. */
const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
const site = path.join(ROOT, "site");
const fails = [];
function fail(m) { fails.push(m); }

const html = fs.readFileSync(path.join(site, "players.html"), "utf8");
const js = fs.readFileSync(path.join(site, "players.js"), "utf8");
const css = fs.readFileSync(path.join(site, "styles.css"), "utf8");

if (!html.includes('id="pl-colleges"')) fail("players.html missing #pl-colleges");
if (!/styles\.css\?v=(\d+)/.test(html) || Number(RegExp.$1) < 54) fail("styles.css pin < 54");
if (!/players\.js\?v=(\d+)/.test(html) || Number(RegExp.$1) < 46) fail("players.js pin < 46");
if (!js.includes("async function renderColleges")) fail("renderColleges missing");
if (!js.includes("buildCollegeRows")) fail("buildCollegeRows missing");
if (!js.includes("playerSeasonXfp")) fail("CHI-114 playerSeasonXfp join missing");
if (!js.includes("unavailable college")) fail("unavailable footnote missing");
if (/luck|playoff/.test(js.match(/async function renderColleges[\s\S]*?function setPageMode/)?.[0] || "") &&
    /luckCard|playoffTrip/.test(js.match(/async function buildCollegeRows[\s\S]*?async function renderColleges/)?.[0] || "")) {
  fail("college rows must not add luck/playoff columns");
}
if (!css.includes(".colleges-tbl")) fail("colleges dense CSS missing");
if (!css.includes("colleges-ncaa") && !css.includes(".colleges-tbl .ncaa-logo")) fail("capped college logos CSS missing");

const bio = JSON.parse(fs.readFileSync(path.join(site, "player_bio.json"), "utf8"));
const years = [2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025];
const by = Object.create(null);
let missWks = 0, joined = 0;
for (const y of years) {
  const d = JSON.parse(fs.readFileSync(path.join(site, "years", y + ".json"), "utf8"));
  const xfpBy = Object.create(null);
  for (const r of (d.playerSeasonXfp && d.playerSeasonXfp.rows) || []) {
    xfpBy[String(r.player_id)] = r;
  }
  for (const p of d.players || []) {
    const starts = Number(p.starts) || 0;
    if (!starts) continue;
    const college = String(((bio[String(p.pid)] || {}).college) || "").trim();
    if (!college) { missWks += starts; continue; }
    const row = by[college] || (by[college] = { college, wks: 0, affl: 0, nflFp: 0, xfp: 0, fpoe: 0, hasXfp: false });
    row.wks += starts;
    row.affl += Number(p.stPts) || 0;
    const xr = xfpBy[String(p.pid)];
    if (xr) {
      joined += 1;
      row.hasXfp = true;
      if (xr.fp != null) row.nflFp += Number(xr.fp) || 0;
      if (xr.xfp != null) row.xfp += Number(xr.xfp) || 0;
      if (xr.fpoe != null) row.fpoe += Number(xr.fpoe) || 0;
    }
  }
}
const rows = Object.values(by).sort((a, b) => b.affl - a.affl);
if (!rows.length) fail("no college rows");
if (rows[0].college !== "Alabama") fail("expected Alabama #1 by AFFL PTS, got " + rows[0].college);
if (rows[0].affl < 5000) fail("Alabama AFFL PTS implausibly low: " + rows[0].affl);
const ga = rows.find((r) => r.college === "Georgia");
if (!ga) fail("Georgia missing");
if (ga.affl < 2000) fail("Georgia AFFL PTS implausibly low: " + ga.affl);
if (joined < 100) fail("CHI-114 join too sparse: " + joined);
if (missWks <= 0) fail("expected some unavailable start weeks for footnote");
if (rows.some((r) => r.college === "—" || r.college === "unavailable")) fail("ranked list includes missing-college bucket");

if (fails.length) {
  console.log("FAIL");
  fails.forEach((f) => console.log(" -", f));
  process.exit(1);
}
console.log("PASS");
console.log("top5", rows.slice(0, 5).map((r, i) => ({
  rank: i + 1, college: r.college, wks: r.wks, affl: +r.affl.toFixed(1), nflFp: +r.nflFp.toFixed(1), xfp: +r.xfp.toFixed(1), fpoe: +r.fpoe.toFixed(1),
})));
console.log("unavailable_wks", missWks, "joined_xfp_rows", joined);
