#!/usr/bin/env node
/* CHI-136: run the actual common.js helpers against data.json. */
const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
const SITE = path.join(ROOT, "site");
const common = fs.readFileSync(path.join(SITE, "common.js"), "utf8");
const data = JSON.parse(fs.readFileSync(path.join(SITE, "data.json"), "utf8"));
const fails = [];
const fail = (m) => fails.push(m);

function grab(src, startNeedle) {
  const start = src.indexOf(startNeedle);
  if (start < 0) throw new Error("missing " + startNeedle);
  const brace = src.indexOf("{", start);
  let depth = 0;
  for (let i = brace; i < src.length; i++) {
    if (src[i] === "{") depth++;
    else if (src[i] === "}") {
      depth--;
      if (depth === 0) return src.slice(start, i + 1);
    }
  }
  throw new Error("unclosed " + startNeedle);
}

const mergeSrc = grab(common, "const MERGE =");
const canonSrc = grab(common, "function canon(");
const fySrc = grab(common, "function franchiseYears(");
const sySrc = grab(common, "function squadYears(");
const clampSrc = grab(common, "function clampYear(");

const factory = new Function(`
  const DATA = arguments[0];
  ${mergeSrc}
  ${canonSrc}
  ${fySrc}
  ${sySrc}
  ${clampSrc}
  return { MERGE, canon, franchiseYears, squadYears, clampYear };
`);
const A = factory({ seasons: data.seasons, franchises: data.franchises, members: data.members });

const m07 = A.squadYears("m07");
const m22 = A.squadYears("m22");
const m18 = A.squadYears("m18");
console.log("helper squadYears('m07')", m07);
console.log("helper squadYears('m22')", JSON.stringify(m22));
console.log("helper squadYears('m18')", m18);

if (JSON.stringify(m07) !== JSON.stringify([2023, 2022, 2021, 2020, 2019, 2018, 2017, 2016])) {
  fail("squadYears('m07') is not 2016-2023 newest-first: " + JSON.stringify(m07));
}
if (!Array.isArray(m22) || m22.length !== 0) fail("squadYears('m22') is not []: " + JSON.stringify(m22));
if (!m18.length) fail("squadYears('m18') empty");
if (m07.includes(2024) || m07.includes(2025)) fail("m07 chips include 2024/2025");

const clamped = A.clampYear(2025, "m07");
console.log("clampYear(2025, m07)", clamped);
if (clamped !== 2023) fail("clampYear(2025, m07) => " + clamped + " (need 2023)");
const empty = A.clampYear(2025, "m22");
console.log("clampYear(2025, m22)", empty);
if (empty !== null) fail("clampYear(2025, m22) => " + empty + " (need null)");

function defaultScope(qs, owner) {
  const params = new URLSearchParams(qs);
  if (params.get("scope") !== "season") return "cum";
  if (owner && !(A.squadYears(owner) || []).length) return "cum";
  return "season";
}
for (const owner of ["m07", "m22", "m18"]) {
  const s = defaultScope("?squad=" + owner, owner);
  console.log("default scope", owner, s);
  if (s !== "cum") fail("default scope for " + owner + " is " + s);
}
if (defaultScope("?squad=m07&year=2025", "m07") !== "cum") {
  fail("?year=2025&squad=m07 without scope did not stay cum");
}
if (defaultScope("?squad=m22&scope=season", "m22") !== "cum") {
  fail("m22 + scope=season did not stay cum");
}
if (defaultScope("?squad=m07&scope=season", "m07") !== "season") {
  fail("m07 + scope=season should honor Season (has years)");
}

function yearRowVisible(scope, squad) {
  const ylist = squad ? A.squadYears(squad) : [];
  return scope === "season" && !!squad && ylist.length > 0;
}
if (yearRowVisible("cum", "m07")) fail("year row visible on cum for m07");
if (yearRowVisible("season", "m22")) fail("year row visible for m22 even in season");
if (yearRowVisible("season", "")) fail("year row visible on all-squads");
if (!yearRowVisible("season", "m07")) fail("year row hidden for m07 season");

if (fails.length) {
  console.log("FAIL");
  fails.forEach((f) => console.log(" -", f));
  process.exit(1);
}
console.log("PASS");
console.log("CHI-136 helpers: opening cum; m22 no chips; m07 no 2024/2025");
