# Franchise-year lock Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every History binder plots only franchises whose `years[]` include that season; All without an as-of date never silently becomes 2025.

**Architecture:** Keep `data.json` frozen. Put membership on `window.AFFL` in `site/common.js`. Write failing Node evals first. Then stop `applySeasonYear(null)` from calling `latestFinished()`, filter seasonal widgets to a select-season empty state, and intersect career rollups with `franchisePlayedSeason`. Age scatter All stays on the as-of year (CHI-128). Chart.js stays.

**Tech Stack:** Existing site JS (`site/common.js`, `site/history.js`), Chart.js already on the page, Node evals, GitHub Pages `main`. No D3, no Plotly, no new deps.

## Global Constraints

- Identity is franchise owner id, never ESPN slot.
- Do not rewrite `site/data.json` unless a real wrong year is found.
- `years === []` means no seasons (Gabagooners). Never coerce to all league years.
- AFFL is non-PPR. No 2026 season before the draft. Never invent 2014–17 benches or transactions.
- Chart.js stays. Do not adopt D3 or Plotly.
- Ship to `main`. No PRs. Linear never Done until Ryan reviews live.
- QA in the box browser only. Do not drive Ryan's Chrome.
- Locked 2014 owners: m11, m09, m08, m16, m12, m02, m18, m15, m17, m13.
- Gabagooners (m22) never 2014–2025. Pounders (m19) and Pollywogs (m14) never 2014–2020. Feelers (m18) 2014–2025.

---

### Task 1: Failing evals

**Files:**
- Create: `site/evals/franchise-year-lock.test.mjs`
- Create: `/tmp/affl-data-plan/EVAL-OUTLINE.md` (already listed; keep in sync)
- Test: `site/evals/franchise-year-lock.test.mjs`

**Interfaces:**
- Consumes: live `site/data.json` franchises + a JS port of `franchiseYears` / `franchisePlayedSeason` / `ownersForSeason` / `seasonScope` copied from the eval file until Task 2 exports them
- Produces: `assertOwnersForSeason(year, ids)`, `assertNeverPlayed(id, years)`, `assertSeasonScopeAll()` 

- [ ] **Step 1: Write the failing test**

```js
// site/evals/franchise-year-lock.test.mjs
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const DATA = JSON.parse(readFileSync(join(root, "data.json"), "utf8"));
const Y2014 = ["m11","m09","m08","m16","m12","m02","m18","m15","m17","m13"];

function canon(id) { return String(id || "").toLowerCase(); }
function franchiseYears(id) {
  const f = (DATA.franchises || []).find((x) => canon(x.owner) === canon(id));
  return (f && f.years) ? f.years.map(Number) : [];
}
function franchisePlayedSeason(id, year) {
  const years = franchiseYears(id);
  if (canon(id) === "m22" && !years.length) return false;
  return years.includes(Number(year));
}
function ownersForSeason(year) {
  return (DATA.franchises || [])
    .map((f) => f.owner)
    .filter((id) => franchisePlayedSeason(id, year));
}
function seasonScope(pickedYear) {
  if (pickedYear == null) return { mode: "all", year: null };
  return { mode: "season", year: Number(pickedYear) };
}

assert.deepEqual(franchiseYears("m22"), []);
assert.equal(franchisePlayedSeason("m22", 2014), false);
assert.equal(franchisePlayedSeason("m22", 2025), false);
assert.deepEqual(ownersForSeason(2014).map(canon).sort(), Y2014.slice().sort());
for (const id of ["m19", "m14", "m22", "m05", "m21", "m06"]) {
  assert.equal(franchisePlayedSeason(id, 2014), false);
}
assert.equal(franchisePlayedSeason("m18", 2014), true);
assert.equal(franchisePlayedSeason("m19", 2020), false);
assert.equal(franchisePlayedSeason("m19", 2021), true);
assert.equal(seasonScope(null).year, null);
assert.notEqual(seasonScope(null).year, 2025);
console.log("eval fixtures ok");
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node site/evals/franchise-year-lock.test.mjs`

Expected: FAIL until Task 2 if the eval imports live helpers. If this file uses local copies, this step PASSES on fixtures (data.json already correct). Keep it as the lock. A second eval file that greps/parses `history.js` must FAIL:

```js
const js = readFileSync(join(root, "history.js"), "utf8");
assert.equal(
  /seasonYear = y == null \? latestFinished\(\) : y/.test(js),
  false,
  "applySeasonYear must not bind All to latestFinished"
);
```

Expected: FAIL with that assertion message on current main.

- [ ] **Step 3: Do not implement binders yet**

Leave `history.js` broken. Commit only the eval.

- [ ] **Step 4: Copy eval into the worktree**

`~/Projects/ccDesktopAFFL/site/evals/franchise-year-lock.test.mjs`

- [ ] **Step 5: Commit**

```bash
git add site/evals/franchise-year-lock.test.mjs
git commit -m "test: CHI-130 franchise-year lock evals first"
```

Ryan does not want PRs. Push the eval to main only with the binder fix in Task 4, or ship eval + fix together. Do not open a PR.

---

### Task 2: Membership helpers on AFFL

**Files:**
- Modify: `site/common.js` (`squadYears` ~279, `clampYear` ~326)
- Test: `site/evals/franchise-year-lock.test.mjs`

**Interfaces:**
- Consumes: `DATA.franchises[].owner`, `DATA.franchises[].years`
- Produces:
  - `AFFL.franchiseYears(id) -> number[]`
  - `AFFL.franchisePlayedSeason(id, year) -> boolean`
  - `AFFL.ownersForSeason(year) -> string[]`
  - `AFFL.seasonScope(pickedYear) -> { mode: "all"|"season", year: number|null }`
  - `AFFL.squadYears(id) -> number[]` (empty stays empty; already shipped)
  - `AFFL.clampYear(year, squad)` must not return `year` when `years` is empty; return `null`

- [ ] **Step 1: Write the failing clampYear assertion**

```js
assert.equal(clampYear(2014, "m22"), null);
```

- [ ] **Step 2: Run it. Expected FAIL** (`ys[0] || year` returns 2014).

- [ ] **Step 3: Write minimal implementation**

```js
function franchiseYears(id) {
  const f = squadInfo(id);
  return (f && f.years && f.years.length) ? f.years.map(Number) : [];
}
function franchisePlayedSeason(id, year) {
  const years = franchiseYears(id);
  if (!years.length) return false;
  return years.indexOf(Number(year)) >= 0;
}
function ownersForSeason(year) {
  return (DATA.franchises || []).map((f) => f.owner).filter((id) => franchisePlayedSeason(id, year));
}
function seasonScope(pickedYear) {
  if (pickedYear == null || pickedYear === "") return { mode: "all", year: null };
  return { mode: "season", year: Number(pickedYear) };
}
function clampYear(year, squad) {
  const y = Number(year);
  const ys = franchiseYears(squad);
  if (!ys.length) return null;
  return ys.indexOf(y) >= 0 ? y : ys[0];
}
```

Export all five on `window.AFFL`. Keep `squadYears` as:

```js
if (!f || !f.years || !f.years.length) return [];
return f.years.slice().sort((a, b) => b - a);
```

- [ ] **Step 4: Run evals. Expected: clampYear / membership PASS. history.js grep still FAIL.**

- [ ] **Step 5: Commit with the history.js fix in Task 3, not alone, unless you are mid-loop locally.**

---

### Task 3: History All is career, not 2025

**Files:**
- Modify: `site/history.js` (`applySeasonYear` ~1878, `seasonYear` init ~612)
- Keep: `ageScatterSeason()` (~1143) using as-of year
- Test: `site/evals/franchise-year-lock.test.mjs`

**Interfaces:**
- Consumes: `AFFL.seasonScope`, `AFFL.franchisePlayedSeason`, `AFFL.ownersForSeason`
- Produces: `seasonYear` is `null` when History All is selected; seasonal renderers must handle null

- [ ] **Step 1: Confirm the failing grep from Task 1 still fails.**

- [ ] **Step 2: Change applySeasonYear**

```js
function applySeasonYear(y) {
  pickedYear = y;
  const scope = AFFL.seasonScope(y);
  seasonYear = scope.year; // null on All — do not call latestFinished()
  // re-render all history widgets
}
```

Init at top:

```js
let seasonYear = AFFL.seasonScope(pickedYear).year;
```

Do **not** change `ageScatterSeason()`. CHI-128 All + as-of stays.

- [ ] **Step 3: Empty state for seasonal widgets when `seasonYear == null`**

In `renderTxnAndWeeks`, `renderWaiverReport`, `renderTxLog`, `renderWaiverValue`, `renderCustodyPar`, `renderRace`:

```js
if (seasonYear == null) {
  // show "Pick a season" / hide the 2025 table. Do not call seasonTxnRows(2025).
  return;
}
```

When `seasonYear` is a number, filter rows:

```js
rows = rows.filter((r) => AFFL.franchisePlayedSeason(r.owner, seasonYear));
```

- [ ] **Step 4: Run the history.js grep eval. Expected PASS.**

- [ ] **Step 5: Commit**

```bash
git add site/common.js site/history.js site/evals/franchise-year-lock.test.mjs
git commit -m "fix: CHI-130 History All no longer binds to 2025"
```

---

### Task 4: Career rollups use franchise.years

**Files:**
- Modify: `site/history.js` (`rollFranchises` ~93 and every career walker listed in the spec)
- Test: `site/evals/franchise-year-lock.test.mjs`

**Interfaces:**
- Consumes: `AFFL.franchiseYears`, `AFFL.franchisePlayedSeason`
- Produces: `firstYear` / `lastYear` / `seasons` from `franchise.years` only

- [ ] **Step 1: Write failing evals on rollup outputs**

```js
const years = franchiseYears("m22");
assert.equal(years.length, 0);
assert.equal(franchiseYears("m19")[0], 2021);
assert.ok(!franchiseYears("m07").includes(2014));
assert.ok(!franchiseYears("m07").includes(2024));
```

If `rollFranchises` is extractable, also assert Gabagooners `seasons === 0` and Pounders `firstYear === 2021`.

- [ ] **Step 2: Run. Expected FAIL if rollFranchises still min/maxes season-file presence.**

- [ ] **Step 3: Minimal fix**

Inside `rollFranchises` (and `careerStandRows`, `rollPPD`, `rollIQ`, `rollTrophies`, `computeWeeklyStreaks`, `computeHof`, `renderOwnersTenure`, `renderHeat`):

```js
if (!AFFL.franchisePlayedSeason(owner, season)) continue;
```

Tenure:

```js
const ys = AFFL.franchiseYears(owner);
const firstYear = ys.length ? Math.min(...ys) : null;
const lastYear = ys.length ? Math.max(...ys) : null;
const seasons = ys.length;
```

- [ ] **Step 4: Run evals. Expected PASS.**

- [ ] **Step 5: Cache-bust `site/history.html` (`common.js` and `history.js` query params +1). Commit. PUT to main. Linear In QA, not Done.**

---

### Task 5: Live checks (box browser only)

**Files:**
- None new. Verify https://rdsciv.github.io/affl-analytics/history.html after Pages.

- [ ] **Step 1:** History All + as-of 2014-09-26 Age scatter: exactly the ten 2014 owners. No Pounders, Pollywogs, Gabagooners, Shadowcöcks, Pipers, Fat Cats.
- [ ] **Step 2:** History All (no year chip): txn / waiver / race / custody PAR do not show 2025 tables.
- [ ] **Step 3:** History 2014 chip: Feelers present. Gabagooners absent. Pounders absent.
- [ ] **Step 4:** Owners Tenure: Gabagooners empty; Pounders start 2021; Chupacabras 2016–2023.
- [ ] **Step 5:** Tell Ryan to refresh History. Leave CHI-130 In QA.

## Self-review

1. Spec coverage: leftover seasonal widgets (Task 3), career rollups (Task 4), clampYear (Task 2), evals first (Task 1), Age scatter not regressed (Task 3 keep).
2. No TBD / "handle edge cases" / "similar to Task N".
3. Names match: `franchiseYears`, `franchisePlayedSeason`, `ownersForSeason`, `seasonScope`, `clampYear`.
