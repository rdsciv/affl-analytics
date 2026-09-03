#!/usr/bin/env node
/* CHI-170: Career G is franchise H2H W+L+T; Scored G stays the 2018–2025 lock. */
const fs = require("fs");
const path = require("path");

const SITE = __dirname;
const ROOT = path.resolve(SITE, "..");
const fails = [];
const fail = (m) => fails.push(m);

const MERGE = { m01: "m07", m03: "m08", m20: "m10" };
function canon(id) {
  if (id == null || id === "") return id;
  return MERGE[String(id)] || String(id);
}

function careerGFor(franchises, oid) {
  const id = canon(oid);
  if (!id) return null;
  const f = (franchises || []).find((x) => canon(x.owner) === id);
  if (!f) return null;
  return (Number(f.wins) || 0) + (Number(f.losses) || 0) + (Number(f.ties) || 0);
}

const dataPath = path.join(SITE, "data.json");
if (!fs.existsSync(dataPath)) {
  fail("missing site/data.json");
  console.log("CHI-170 FAIL");
  fails.forEach((m) => console.log(" -", m));
  process.exit(1);
}

const data = JSON.parse(fs.readFileSync(dataPath, "utf8"));
const franchises = data.franchises || [];
const cats = franchises.find((f) => canon(f.owner) === "m06");
const feelers = franchises.find((f) => canon(f.owner) === "m18");
const thunder = franchises.find((f) => canon(f.owner) === "m16");

const catsG = careerGFor(franchises, "m06");
const feelersG = careerGFor(franchises, "m18");
const thunderG = careerGFor(franchises, "m16");

console.log("Fat Cats m06 Career G", catsG, cats && cats.years);
console.log("Feelers m18 Career G", feelersG, feelers && feelers.years);
console.log("Thunder m16 Career G", thunderG, thunder && thunder.years);

if (catsG !== 148) fail("Fat Cats (m06) Career G is " + catsG + " (need 148)");
if (feelersG !== 161) fail("Feelers (m18) Career G is " + feelersG + " (need 161)");
if (catsG === feelersG) fail("Cats Career G equals Feelers — 2014 parity still reads");

if (!cats || !Array.isArray(cats.years) || cats.years.indexOf(2014) >= 0) {
  fail("Fat Cats years include 2014 or are missing");
}
if (!thunder || JSON.stringify(thunder.years) !== JSON.stringify([2014])) {
  fail("Thunder m16 is not 2014-only: " + JSON.stringify(thunder && thunder.years));
}
if (canon(thunder && thunder.owner) === canon(cats && cats.owner)) {
  fail("Thunder m16 was merged into Fat Cats");
}

const SCORED = [2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025];
function scoredGFor(years) {
  let n13 = 0;
  let n14 = 0;
  for (const y of years || []) {
    if (y >= 2018 && y <= 2020) n13 += 1;
    if (y >= 2021 && y <= 2025) n14 += 1;
  }
  return 13 * n13 + 14 * n14;
}
const catsScored = scoredGFor(cats && cats.years);
const feelersScored = scoredGFor(feelers && feelers.years);
console.log("Fat Cats Scored G (schedule lock)", catsScored);
console.log("Feelers Scored G (schedule lock)", feelersScored);
if (catsScored !== 109) fail("Fat Cats Scored G is " + catsScored + " (need 109)");
if (feelersScored !== 109) fail("Feelers Scored G is " + feelersScored + " (need 109)");

const html = fs.readFileSync(path.join(SITE, "roto.html"), "utf8");
if (!html.includes("roto.js?v=9")) fail("roto.html does not load roto.js?v=9");
if (/roto\.js\?v=[0-8]["']/.test(html)) fail("roto.html still loads an older roto.js cache");

const js = fs.readFileSync(path.join(SITE, "roto.js"), "utf8");
if (!js.includes("function careerGFor(")) fail("roto.js missing careerGFor");
if (!js.includes("A.data.franchises") && !js.includes("A.data && A.data.franchises")) {
  fail("careerGFor does not read A.data.franchises");
}
if (!js.includes("careerG: careerGFor(oid)")) fail("decorateAll does not set careerG");
if (!js.includes(">Career G</th>")) fail("roto.js All table missing Career G header");
if (!js.includes('data-k="careerG"')) fail("roto.js missing careerG sort key");
if (!js.includes("if (key === \"careerG\")")) fail("sortValue/columnExists missing careerG");
if (!js.includes("Career H2H games = franchise W+L+T")) fail("Career G tooltip missing W+L+T copy");
if (!js.includes("Fat Cats 148 from 2015–2025; Feelers 161")) {
  fail("Career G tooltip missing Cats 148 / Feelers 161 lock");
}
if (!js.includes("Career G = franchise H2H tenure")) fail("blurb/subtitle missing Career G tenure copy");
if (!js.includes("Scored G = roto sample")) fail("blurb/subtitle missing Scored G sample copy");

const mathSrc = fs.readFileSync(path.join(SITE, "roto-math.js"), "utf8");
if (!mathSrc.includes("const SCORED_YEARS = [2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025]")) {
  fail("SCORED_YEARS is not the 2018–2025 lock");
}
if (/UNAVAILABLE_YEARS = \[2014, 2015, 2016, 2017\]/.test(mathSrc) === false) {
  fail("2014–2017 are no longer marked unavailable for category lines");
}

const boxDir = path.join(SITE, "pillars", "boxscores");
const leaguePath = path.join(SITE, "pillars", "league.json");
if (fs.existsSync(boxDir) && fs.existsSync(leaguePath)) {
  const R = require(path.join(SITE, "roto-math.js"));
  const league = JSON.parse(fs.readFileSync(leaguePath, "utf8"));
  function ownerOf(y, teamId) {
    const teams = ((data.seasons && data.seasons[String(y)]) || {}).teams || [];
    const t = teams.find((x) => x.id === teamId || String(x.id) === String(teamId));
    return t ? canon(t.owner) : "";
  }
  const loads = SCORED.map((year) => {
    const season = (league.seasons || []).find((s) => s.year === year);
    const boxFile = path.join(boxDir, year + ".json");
    if (!season || !fs.existsSync(boxFile)) return { year, season, box: null };
    return { year, season, box: JSON.parse(fs.readFileSync(boxFile, "utf8")) };
  }).filter((l) => l.box && l.season);
  const built = R.buildAllRoto(loads, "reg", "totals", { ownerOf, skipOwners: { m22: true } });
  const byOid = {};
  for (const t of built.teams || []) byOid[canon(t.ownerId)] = t;
  const catsRow = byOid.m06;
  const feelersRow = byOid.m18;
  const thunderRow = byOid.m16;
  console.log("buildAllRoto Cats games", catsRow && catsRow.games, "years", catsRow && catsRow.years);
  console.log("buildAllRoto Feelers games", feelersRow && feelersRow.games, "years", feelersRow && feelersRow.years);
  console.log("buildAllRoto Thunder row", thunderRow ? thunderRow.games : "absent (expected)");
  if (!catsRow || catsRow.games !== 109) fail("buildAllRoto Cats Scored G is " + (catsRow && catsRow.games) + " (need 109)");
  if (!feelersRow || feelersRow.games !== 109) fail("buildAllRoto Feelers Scored G is " + (feelersRow && feelersRow.games) + " (need 109)");
  if (thunderRow) fail("Thunder m16 has a scored-window roto row (2014-only franchise)");
  const invented = (built.scoredYears || []).some((y) => y < 2018);
  if (invented) fail("buildAllRoto invented pre-2018 scored years: " + JSON.stringify(built.scoredYears));
} else {
  console.log("pillars missing — skipped live boxscore Scored G check");
}

if (fails.length) {
  console.log("CHI-170 FAIL " + fails.length);
  fails.forEach((m) => console.log(" -", m));
  process.exit(1);
}
console.log("CHI-170 PASS");
process.exit(0);
