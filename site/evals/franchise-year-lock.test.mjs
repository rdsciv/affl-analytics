/* CHI-130 franchise-year lock. Identity is franchise owner, never ESPN slot. */
import { createContext, runInContext } from "node:vm";
import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));

function resolveBind() {
  if (process.env.AFFL_BIND) return process.env.AFFL_BIND;
  if (process.argv[2]) return process.argv[2];
  if (existsSync(join(here, "history.js")) && existsSync(join(here, "common.js"))) return here;
  const parent = join(here, "..");
  const outDir = join(parent, "out");
  if (existsSync(join(outDir, "history.js")) && existsSync(join(outDir, "common.js"))) return outDir;
  return parent;
}

function resolveData(bind) {
  const cands = [
    join(bind, "data.json"),
    join(dirname(bind), "data.json"),
    join(here, "..", "data.json"),
  ];
  for (const p of cands) if (existsSync(p)) return p;
  return cands[0];
}

const bind = resolveBind();
const histPath = join(bind, "history.js");
const commonPath = join(bind, "common.js");
const dataPath = resolveData(bind);

const historySrc = readFileSync(histPath, "utf8");
const commonSrc = readFileSync(commonPath, "utf8");
const DATA = JSON.parse(readFileSync(dataPath, "utf8"));

const LOCK = {
  m22: [],
  m19: [2021, 2022, 2023, 2024, 2025],
  m14: [2021, 2022, 2023, 2024, 2025],
  m18: [2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025],
  m07: [2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023],
};
const OWNERS_2014 = ["m11", "m09", "m08", "m16", "m12", "m02", "m18", "m15", "m17", "m13"];

let pass = 0;
let fail = 0;
const fails = [];

function eq(a, b) {
  if (Array.isArray(a) && Array.isArray(b)) {
    return a.length === b.length && a.every((v, i) => eq(v, b[i]));
  }
  return a === b;
}

function assert(cond, name, detail) {
  if (cond) {
    pass += 1;
    console.log("PASS  " + name);
  } else {
    fail += 1;
    const msg = detail ? name + " — " + detail : name;
    fails.push(msg);
    console.log("FAIL  " + msg);
  }
}

function extractFn(src, name) {
  const re = new RegExp("function\\s+" + name + "\\s*\\(");
  const start = src.search(re);
  if (start < 0) return null;
  const brace = src.indexOf("{", start);
  if (brace < 0) return null;
  let depth = 0;
  for (let i = brace; i < src.length; i++) {
    const c = src[i];
    if (c === "{") depth += 1;
    else if (c === "}") {
      depth -= 1;
      if (depth === 0) return src.slice(start, i + 1);
    }
  }
  return null;
}

function franchiseMap() {
  const out = {};
  (DATA.franchises || []).forEach((f) => { out[f.owner] = f; });
  return out;
}

/* ---------- data.json lock (must PASS on live) ---------- */
console.log("\n== data.json years ==");
const fmap = franchiseMap();
for (const [id, years] of Object.entries(LOCK)) {
  const f = fmap[id];
  assert(!!f, "data.json has " + id, "missing franchise");
  assert(eq(f && f.years, years), "data.json " + id + " years=" + JSON.stringify(years),
    "got " + JSON.stringify(f && f.years));
}
const s2014 = ((DATA.seasons || {})["2014"] || {}).teams || [];
const owners2014 = s2014.map((t) => t.owner);
assert(eq(owners2014, OWNERS_2014), "2014 owners exactly m11 m09 m08 m16 m12 m02 m18 m15 m17 m13",
  "got " + JSON.stringify(owners2014));
const seasonKeys = Object.keys(DATA.seasons || {}).map(Number).sort((a, b) => a - b);
assert(seasonKeys.indexOf(2026) < 0, "no AFFL 2026 season", "seasons=" + JSON.stringify(seasonKeys));
assert(seasonKeys[0] === 2014 && seasonKeys[seasonKeys.length - 1] === 2025,
  "seasons span 2014–2025", "got " + JSON.stringify(seasonKeys));
assert(eq(fmap.m22 && fmap.m22.years, []), "Gabagooners years=[] — never 2014–2025",
  "got " + JSON.stringify(fmap.m22 && fmap.m22.years));
assert(!(fmap.m19 && (fmap.m19.years || []).some((y) => y >= 2014 && y <= 2020)),
  "Pounders never 2014–2020", "got " + JSON.stringify(fmap.m19 && fmap.m19.years));
assert(!(fmap.m14 && (fmap.m14.years || []).some((y) => y >= 2014 && y <= 2020)),
  "Pollywogs never 2014–2020", "got " + JSON.stringify(fmap.m14 && fmap.m14.years));
for (const [id, years] of Object.entries(LOCK)) {
  const extra = (years || []).filter((y) => y >= 2014 && y <= 2017);
  if (id === "m19" || id === "m14" || id === "m22") {
    assert(extra.length === 0, id + " never invents 2014–17 years", "got " + JSON.stringify(years));
  }
}

/* ---------- boot common.js in vm ---------- */
console.log("\n== common.js clampYear / helpers ==");
const fakeManifest = {
  years: seasonKeys.map((y) => ({ year: y })),
};
const context = createContext({
  window: {},
  fetch: async (url) => ({
    ok: true,
    json: async () => {
      const u = String(url);
      if (u.includes("data.json")) return DATA;
      if (u.includes("index_years.json")) return fakeManifest;
      return {};
    },
  }),
  Date,
  Number,
  String,
  Object,
  Array,
  JSON,
  Math,
  Map,
  Promise,
  console,
  location: { href: "https://example.test/history.html", search: "", pathname: "/history.html" },
  document: {
    querySelectorAll: () => [],
    querySelector: () => null,
    getElementById: () => null,
    documentElement: { classList: { toggle() {} } },
    dispatchEvent() {},
    createElement() { return { className: "", id: "", style: {} }; },
  },
  history: { replaceState() {} },
  URL,
  URLSearchParams,
  localStorage: { getItem() { return null; }, setItem() {}, removeItem() {} },
  CustomEvent: class CustomEvent {},
});
runInContext(commonSrc, context);
await runInContext("window.AFFL.boot()", context);
const A = context.window.AFFL;

assert(typeof A.squadYears === "function", "squadYears exported");
assert(eq(A.squadYears("m22"), []), "squadYears empty-stays-empty for m22",
  "got " + JSON.stringify(A.squadYears("m22")));
assert(eq(A.squadYears("nope"), []), "squadYears missing franchise is []");

const clampSrc = extractFn(commonSrc, "clampYear") || "";
assert(!/ys\s*\[\s*0\s*\]\s*\|\|\s*year/.test(clampSrc),
  "clampYear never uses ys[0] || year",
  "live still has: return ys.indexOf(year) >= 0 ? year : (ys[0] || year)");

const clampEmpty = A.clampYear(2014, "m22");
assert(clampEmpty === null, "clampYear empty years returns null (m22/2014)",
  "got " + JSON.stringify(clampEmpty) + " — empty must not fall through to year");

const clampPounders = A.clampYear(2014, "m19");
assert(clampPounders === null || clampPounders === 2014 && false,
  "clampYear does not remap Pounders 2014 → latest squad year",
  "got " + JSON.stringify(clampPounders) + " (live remaps via ys[0])");
assert(A.clampYear(2023, "m19") === 2023, "clampYear keeps in-range Pounders 2023");
assert(A.clampYear(2022, "") === 2022, "clampYear without squad returns year");

assert(typeof A.franchiseYears === "function", "AFFL.franchiseYears exported");
assert(typeof A.franchisePlayedSeason === "function", "AFFL.franchisePlayedSeason exported");
assert(typeof A.ownersForSeason === "function", "AFFL.ownersForSeason exported");
assert(typeof A.seasonScope === "function", "AFFL.seasonScope exported");

if (typeof A.franchiseYears === "function") {
  assert(eq(A.franchiseYears("m22"), []), "franchiseYears m22=[]");
  assert(eq(A.franchiseYears("m19"), LOCK.m19) || eq((A.franchiseYears("m19") || []).slice().sort((a, b) => a - b), LOCK.m19),
    "franchiseYears m19=2021–2025", "got " + JSON.stringify(A.franchiseYears("m19")));
  assert(eq((A.franchiseYears("m07") || []).slice().sort((a, b) => a - b), LOCK.m07),
    "franchiseYears m07=2016–2023", "got " + JSON.stringify(A.franchiseYears("m07")));
}
if (typeof A.franchisePlayedSeason === "function") {
  assert(A.franchisePlayedSeason("m22", 2014) === false, "m22 never played 2014");
  assert(A.franchisePlayedSeason("m22", 2025) === false, "m22 never played 2025");
  assert(A.franchisePlayedSeason("m19", 2014) === false, "m19 never played 2014");
  assert(A.franchisePlayedSeason("m19", 2021) === true, "m19 played 2021");
  assert(A.franchisePlayedSeason("m14", 2020) === false, "m14 never played 2020");
  assert(A.franchisePlayedSeason("m18", 2014) === true, "m18 played 2014");
  assert(A.franchisePlayedSeason("m07", 2014) === false, "m07 never played 2014");
  assert(A.franchisePlayedSeason("m07", 2016) === true, "m07 played 2016");
}
if (typeof A.ownersForSeason === "function") {
  const o14 = (A.ownersForSeason(2014) || []).slice().sort();
  const expect14 = OWNERS_2014.slice().sort();
  assert(eq(o14, expect14), "ownersForSeason(2014) exact lock set",
    "got " + JSON.stringify(o14));
  assert((A.ownersForSeason(2014) || []).indexOf("m22") < 0, "Gabagooners not in 2014 owners");
  assert((A.ownersForSeason(2014) || []).indexOf("m19") < 0, "Pounders not in 2014 owners");
  assert((A.ownersForSeason(2014) || []).indexOf("m14") < 0, "Pollywogs not in 2014 owners");
}
if (typeof A.seasonScope === "function") {
  assert(A.seasonScope(null).year === null, "seasonScope(null).year is null (All)");
  assert(A.seasonScope("all").year === null, "seasonScope('all').year is null");
  assert(A.seasonScope(2025).year === 2025, "seasonScope(2025).year is 2025");
  assert(A.seasonScope(undefined).year === null, "seasonScope(undefined).year is null");
}

/* ---------- history.js All must not collapse to latestFinished ---------- */
console.log("\n== history.js seasonYear / All ==");
const applySrc = extractFn(historySrc, "applySeasonYear") || "";
assert(!!applySrc, "applySeasonYear exists");
assert(!/latestFinished\s*\(/.test(applySrc),
  "applySeasonYear never calls latestFinished()",
  "live still has: seasonYear = y == null ? latestFinished() : y");
assert(/seasonScope\s*\(/.test(applySrc),
  "applySeasonYear uses seasonScope(y).year (null on All)",
  "missing seasonScope — All still collapses to a year");

const initMatch = historySrc.match(/let\s+seasonYear\s*=\s*([^;]+);/);
const initExpr = initMatch ? initMatch[1].trim() : "";
assert(!/latestFinished\s*\(/.test(initExpr),
  "init seasonYear never uses latestFinished() for All",
  "live still has: " + initExpr);
assert(/seasonScope\s*\(/.test(initExpr),
  "init seasonYear = seasonScope(...).year",
  "got " + initExpr);

/* CHI-128 no-regress */
const ageFn = extractFn(historySrc, "ageScatterSeason") || "";
assert(/ageAsOf/.test(ageFn) && /getFullYear/.test(ageFn),
  "CHI-128 ageScatterSeason() still uses as-of year");
const ageRows = extractFn(historySrc, "seasonAgeRows") || "";
assert(/franchisePlayedSeason/.test(ageRows),
  "CHI-128 seasonAgeRows still filters franchisePlayedSeason");

/* Seasonal widgets: All → pick-a-season, never paint 2025 */
const seasonal = [
  "renderTxnAndWeeks", "renderTxnCounter", "renderAddsByWeek",
  "renderWaiverReport", "renderTxLog", "renderWaiverValue",
  "renderCustodyPar", "renderRace",
];
const seasonalSrc = seasonal.map((n) => extractFn(historySrc, n) || "").join("\n");
assert(/seasonYear\s*==\s*null|seasonYear\s*===\s*null/.test(extractFn(historySrc, "renderWaiverReport") || ""),
  "renderWaiverReport empty-state when seasonYear == null");
assert(/seasonYear\s*==\s*null|seasonYear\s*===\s*null/.test(extractFn(historySrc, "renderTxLog") || ""),
  "renderTxLog empty-state when seasonYear == null");
assert(/seasonYear\s*==\s*null|seasonYear\s*===\s*null/.test(extractFn(historySrc, "renderWaiverValue") || ""),
  "renderWaiverValue empty-state when seasonYear == null");
assert(/seasonYear\s*==\s*null|seasonYear\s*===\s*null/.test(extractFn(historySrc, "renderCustodyPar") || ""),
  "renderCustodyPar empty-state when seasonYear == null");
assert(/seasonYear\s*==\s*null|seasonYear\s*===\s*null/.test(extractFn(historySrc, "renderRace") || ""),
  "renderRace empty-state when seasonYear == null");
const txnGuard = (extractFn(historySrc, "renderTxnAndWeeks") || "")
  + (extractFn(historySrc, "renderTxnCounter") || "")
  + (extractFn(historySrc, "renderAddsByWeek") || "");
assert(/seasonYear\s*==\s*null|seasonYear\s*===\s*null/.test(txnGuard),
  "renderTxnAndWeeks empty-state when seasonYear == null");
assert(/Pick a season|pick a season|pick-a-season/i.test(seasonalSrc),
  "seasonal widgets show pick-a-season empty copy");

/* Career rollups use franchise.years */
const rollSrc = extractFn(historySrc, "rollFranchises") || "";
assert(/franchisePlayedSeason|franchiseYears|\.years/.test(rollSrc),
  "rollFranchises honors franchise.years / franchisePlayedSeason");
const careerStand = extractFn(historySrc, "careerStandRows") || "";
assert(/franchisePlayedSeason|franchiseYears/.test(careerStand),
  "careerStandRows skips seasons not in franchise.years");

/* Chart.js stays; no D3/Plotly adoption */
assert(!/\bPlotly\b/.test(historySrc) && !/\bd3\b/.test(historySrc),
  "Chart.js stays — no D3/Plotly");

console.log("\n== summary ==");
console.log("bind: " + bind);
console.log("PASS " + pass + "  FAIL " + fail);
if (fails.length) {
  console.log("FAIL reasons:");
  fails.forEach((f, i) => console.log("  " + (i + 1) + ". " + f));
}
process.exitCode = fail ? 1 : 0;
