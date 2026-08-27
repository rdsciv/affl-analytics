/* AFFL Savant — every NFL skill player, filtered, plotted, hoverable.
 *
 * CHI-129 restyle: nflsavant visual language on this page only.
 * CHI-127 / CHI-131 locks: default Cumulative / career 2014–2025;
 * dots colored by the current-name franchise of most AFFL points;
 * Auction $ on X and Y; 2014–15 snake years unavailable, never $0.
 *
 * Data: site/savant/season_<year>.json. AFFL scoring is non-PPR
 * throughout; receptions are volume and score nothing. Auction $ lives
 * in savant/bids.json keyed by GSIS pid. Years 2016–2025 only.
 *
 * AFFL context is keyed on franchise (member_id upstream), so a rename
 * never splits a franchise — Tittsburgh and Grand Teeton are one team,
 * shown under the current name.
 */
(async function () {
  "use strict";

  /* common.js mounts an Excel left rail on every page. Put the nav back
     in the nflsavant header so a cached common.js cannot leave a sidebar. */
  (function restoreSavantChrome() {
    const frame = document.querySelector(".frame");
    const header = document.querySelector("header.sv-mast");
    const nav = document.querySelector(".site-nav");
    if (!frame || !header || !nav) return;
    let navRow = header.querySelector(".topbar-nav-row");
    if (!navRow) {
      navRow = document.createElement("div");
      navRow.className = "topbar-nav-row";
      const tools = header.querySelector(".sv-tools");
      header.insertBefore(navRow, tools || null);
    }
    if (nav.parentElement !== navRow) navRow.appendChild(nav);
    const sheet = frame.querySelector(".sheet");
    if (!sheet) return;
    const main = sheet.querySelector(".sheet-main");
    if (main) {
      while (main.firstChild) frame.insertBefore(main.firstChild, sheet);
    }
    sheet.remove();
  })();

  const A = window.AFFL || {};
  const $ = (id) => document.getElementById(id);
  const BASE = "savant/";
  const ALL = "all";
  const PAGES = ["home", "explore", "leaderboards", "compare", "players", "fantasy"];

  const POS_COLOR = { QB: "#00a2ff", RB: "#c8ff00", WR: "#ff6a00", TE: "#ffc400" };
  const POSITIONS = ["ALL", "QB", "RB", "WR", "TE"];
  const MUTED = "#9aa3af";
  const TOPS = [10, 15, 25, 50, 100];

  /* NFL team bars for table / list identity. Scatter dots stay franchise. */
  const NFL_BAR = {
    ARI: ["#97233F", "#000000"], ATL: ["#A71930", "#000000"],
    BAL: ["#241773", "#9E7C0C"], BUF: ["#00338D", "#C60C30"],
    CAR: ["#0085CA", "#101820"], CHI: ["#0B162A", "#C83803"],
    CIN: ["#FB4F14", "#000000"], CLE: ["#311D00", "#FF3C00"],
    DAL: ["#003594", "#869397"], DEN: ["#FB4F14", "#002244"],
    DET: ["#0076B6", "#B0B7BC"], GB: ["#203731", "#FFB612"],
    HOU: ["#03202F", "#A71930"], IND: ["#002C5F", "#A2AAAD"],
    JAX: ["#006778", "#D7A22A"], JAC: ["#006778", "#D7A22A"],
    KC: ["#E31837", "#FFB81C"], LAC: ["#0080C6", "#FFC20E"],
    LAR: ["#003594", "#FFA300"], LA: ["#003594", "#FFA300"],
    LV: ["#000000", "#A5ACAF"], MIA: ["#008E97", "#FC4C02"],
    MIN: ["#4F2683", "#FFC62F"], NE: ["#002244", "#C60C30"],
    NO: ["#D3BC8D", "#101820"], NYG: ["#0B2265", "#A71930"],
    NYJ: ["#125740", "#000000"], PHI: ["#004C54", "#A5ACAF"],
    PIT: ["#FFB612", "#101820"], SEA: ["#002244", "#69BE28"],
    SF: ["#AA0000", "#B3995D"], TB: ["#D50A0A", "#34302B"],
    TEN: ["#0C2340", "#4B92DB"], WAS: ["#5A1414", "#FFB612"],
    WSH: ["#5A1414", "#FFB612"],
  };

  /* Fixed 19-color map on current franchise names. Feelers ≠ Warlords. */
  const FR_COLOR = {
    "Charleston Chewbacca": "#c9a36a",
    "Chula Vista Chupacabras": "#39d98a",
    "DC Mighty Cucks": "#ff4f8b",
    "Fairview Fat Cats": "#f5c518",
    "Goleta Gringos": "#3d9eff",
    "Grand Teeton Feelers": "#1ee0c2",
    "Green Bay Glory Holes": "#b6ff3d",
    "Honolulu Horndogs": "#ff7a1a",
    "L.O.B. Thunder": "#8b7cff",
    "Muck City Mad Dawgs": "#c26a3a",
    "Pasco Pounders": "#d7dde8",
    "Patagonia Pipers": "#5ec8ff",
    "Pawtucket Patriots": "#e23b4a",
    "Poulsbo Pollywogs": "#6ee7b7",
    "San Diego Shadowcöcks": "#c084fc",
    "Squaw Valley Skinners": "#ffe566",
    "Tijuana Sanchitos": "#ff9f43",
    "Westeros Warlords": "#9b1b30",
    "Winston-Salem Wake Snakes": "#7cb342",
    "Central Oregon Gabagooners": "#6ec6ff",
  };

  /* Former names stay on that franchise. Never a second chip. */
  const FR_ALIAS = {
    "Green Bay Glory Holes": "Chula Vista Chupacabras",
    "Glory Holes": "Chula Vista Chupacabras",
    "Tittsburgh Feelers": "Grand Teeton Feelers",
    "Pittsburgh Feelers": "Grand Teeton Feelers",
    "Kansas City Missourians": "DC Mighty Cucks",
    "The Dalles Cowboys": "DC Mighty Cucks",
  };

  function currentSquads() {
    if (A.CURRENT_2026 && A.CURRENT_2026.length) return A.CURRENT_2026;
    return [
      { owner: "m11", name: "Squaw Valley Skinners" },
      { owner: "m06", name: "Fairview Fat Cats" },
      { owner: "m08", name: "Goleta Gringos" },
      { owner: "m05", name: "San Diego Shadowcöcks" },
      { owner: "m02", name: "DC Mighty Cucks" },
      { owner: "m18", name: "Grand Teeton Feelers" },
      { owner: "m15", name: "Westeros Warlords" },
      { owner: "m17", name: "Tijuana Sanchitos" },
      { owner: "m21", name: "Patagonia Pipers" },
      { owner: "m13", name: "Honolulu Horndogs" },
      { owner: "m22", name: "Central Oregon Gabagooners" },
      { owner: "m07", name: "Chula Vista Chupacabras" },
    ];
  }

  function currentFr(name) {
    if (!name) return "";
    if (FR_ALIAS[name]) return FR_ALIAS[name];
    return name;
  }

  const FR_ABBR = {
    "Charleston Chewbacca": "CC",
    "Chula Vista Chupacabras": "CVC",
    "DC Mighty Cucks": "DMC",
    "Fairview Fat Cats": "FFC",
    "Goleta Gringos": "GG",
    "Grand Teeton Feelers": "GTF",
    "Green Bay Glory Holes": "GBG",
    "Honolulu Horndogs": "HON",
    "L.O.B. Thunder": "LOB",
    "Muck City Mad Dawgs": "MCM",
    "Pasco Pounders": "PND",
    "Patagonia Pipers": "PIP",
    "Pawtucket Patriots": "PAT",
    "Poulsbo Pollywogs": "POL",
    "San Diego Shadowcöcks": "SDS",
    "Squaw Valley Skinners": "SVS",
    "Tijuana Sanchitos": "TIJ",
    "Westeros Warlords": "WW",
    "Winston-Salem Wake Snakes": "WSS",
    "Central Oregon Gabagooners": "GAB",
  };

  const MERGE = { m01: "m07", m03: "m08", m20: "m10" };

  /* metric key -> label + how to read it off a row */
  const METRICS = {
    opp:    { label: "Opportunities (tgt + car + att)", get: (r) => r.opp != null ? +r.opp : n(r.tgt) + n(r.car) + n(r.att) },
    tgt:    { label: "Targets",              get: (r) => r.tgt },
    car:    { label: "Carries",              get: (r) => r.car },
    att:    { label: "Pass attempts",        get: (r) => r.att },
    ay:     { label: "Air yards",            get: (r) => r.ay },
    tgtsh:  { label: "Target share",         get: (r) => pct(r.tgtsh), fmt: "pct" },
    aysh:   { label: "Air yards share",      get: (r) => pct(r.aysh), fmt: "pct" },
    wopr:   { label: "WOPR",                 get: (r) => r.wopr, nd: 3 },
    racr:   { label: "RACR",                 get: (r) => r.racr, nd: 3 },
    fpts:   { label: "Fantasy points (AFFL)", get: (r) => r.fpts, nd: 1 },
    fppg:   { label: "Fantasy points / game", get: (r) => r.fppg, nd: 2 },
    epa:    { label: "EPA",                  get: (r) => r.epa, nd: 1 },
    recyd:  { label: "Receiving yards",      get: (r) => r.recyd },
    ruyd:   { label: "Rushing yards",        get: (r) => r.ruyd },
    payd:   { label: "Passing yards",        get: (r) => r.payd },
    td:     { label: "Total touchdowns",     get: (r) => n(r.rectd) + n(r.rutd) + n(r.patd) },
    g:      { label: "Games",                get: (r) => r.g },
    starts: { label: "AFFL starts",          get: (r) => r.starts },
    bid:    { label: "Auction $",            get: (r) => r.bid == null ? null : +r.bid, nd: 0 },
  };

  const MIN_OPP = [0, 25, 50, 100, 150, 200];
  const SUM_COLS = [
    "tgt", "rec", "recyd", "rectd", "ay", "car", "ruyd", "rutd",
    "att", "cmp", "payd", "patd", "int", "epa", "fpts", "starts", "g",
  ];
  const SHARE_NULL = ["tgtsh", "aysh", "wopr", "racr"];

  const state = {
    scope: "cum", season: ALL, pos: "ALL", view: "all", franchise: "",
    color: "franchise",
    x: "opp", y: "fpts", minOpp: 25,
    sort: { key: "fpts", dir: -1 },
    page: "home",
    top: 50,
    q: "",
    h2h: { a: null, b: null },
    moverPos: "ALL",
    lb: { board: "passing", season: null, team: "", qual: "qualified", name: "", sort: { key: "epap", dir: -1 } },
    cmp: { season: null, pos: "QB", pids: [] },
  };

  let META = null;
  let BIDS = {};
  let ROWS = [];
  let LEAGUE = null;
  let chart = null;
  const cache = new Map();

  function n(v) { return v == null ? 0 : +v; }
  function pct(v) { return v == null ? null : +v * 100; }

  function isAll() { return state.scope !== "season"; }

  function fmt(v, m) {
    if (v == null || Number.isNaN(v)) return "—";
    if (m && m.fmt === "pct") return v.toFixed(1) + "%";
    const nd = m && m.nd != null ? m.nd : 0;
    return (+v).toLocaleString(undefined, { minimumFractionDigits: nd, maximumFractionDigits: nd });
  }

  function fmtBid(v) {
    if (v == null || Number.isNaN(+v)) return "unavailable";
    return "$" + (+v).toLocaleString(undefined, { maximumFractionDigits: 0 });
  }

  /* CHI-121 — never paint Player {espnId}. */
  function unresolvedName(name) {
    if (A && A.unresolvedPlayerName) return A.unresolvedPlayerName(name);
    return name == null || name === "" || /^Player \d+$/.test(String(name).trim());
  }
  function displayName(r) {
    const name = r && r.name;
    if (unresolvedName(name)) return "unavailable";
    return name;
  }

  function frColor(fr) {
    if (!fr) return MUTED;
    return FR_COLOR[currentFr(fr)] || MUTED;
  }

  function nflBar(team) {
    const pair = NFL_BAR[String(team || "").toUpperCase()];
    return pair || [MUTED, "#6b7280"];
  }

  function barHTML(team, fr) {
    const pair = team ? nflBar(team) : [frColor(fr), frColor(fr)];
    return `<span class="sv-bar" style="--a:${pair[0]};--b:${pair[1]}" title="${esc(fr || team || "")}"></span>`;
  }

  function sqHTML(team, fr) {
    const pair = team ? nflBar(team) : [frColor(fr), frColor(fr)];
    return `<span class="sv-sq" style="--a:${pair[0]};--b:${pair[1]}" title="${esc(fr || team || "")}"></span>`;
  }

  function rate(num, den) {
    if (num == null || den == null || +den === 0) return null;
    return +num / +den;
  }

  /* Bids sidecar is GSIS-keyed. Missing year or pid => null, never 0. */
  function yearBid(year, gsis) {
    const bag = BIDS[String(year)];
    if (!bag || gsis == null || gsis === "") return null;
    const b = bag[String(gsis)];
    if (b == null) return null;
    return +b;
  }

  function attachBid(row, year) {
    row.bid = yearBid(year, row.pid);
    if (row.opp == null) row.opp = n(row.tgt) + n(row.car) + n(row.att);
    return row;
  }

  function decodeRows(raw) {
    const cols = META.cols;
    return raw.map((arr) => {
      const o = {};
      cols.forEach((c, i) => { o[c] = arr[i]; });
      return o;
    });
  }

  async function loadSeason(y) {
    if (cache.has(y)) return cache.get(y);
    const res = await fetch(`${BASE}season_${y}.json`);
    if (!res.ok) throw new Error(`season ${y} unavailable`);
    const rows = decodeRows(await res.json()).map((r) => attachBid(r, y));
    cache.set(y, rows);
    return rows;
  }

  function pickHomeFranchise(byFr) {
    const names = Object.keys(byFr).filter((fr) => byFr[fr].fpts > 0);
    if (!names.length) return null;
    names.sort((a, b) => {
      const d = byFr[b].fpts - byFr[a].fpts;
      if (d) return d;
      const s = byFr[b].starts - byFr[a].starts;
      if (s) return s;
      return a.localeCompare(b);
    });
    return names[0];
  }

  function careerBid(gsis) {
    if (gsis == null || gsis === "") return null;
    let sum = 0;
    let any = false;
    Object.keys(BIDS).forEach((y) => {
      const bag = BIDS[y];
      if (!bag) return;
      const b = bag[String(gsis)];
      if (b == null) return;
      sum += +b;
      any = true;
    });
    return any ? sum : null;
  }

  async function loadCareer() {
    if (cache.has(ALL)) return cache.get(ALL);
    const years = META.seasons.slice();
    const bags = await Promise.all(years.map(loadSeason));
    const by = new Map();
    years.forEach((y, i) => {
      bags[i].forEach((r) => {
        const pid = r.pid;
        if (pid == null || pid === "") return;
        let o = by.get(pid);
        if (!o) {
          o = {
            pid, name: "", pos: "", team: "",
            opp: 0, bid: null, fr: null, _byFr: {},
            _teamTgt: 0, _teamAy: 0, _racrNum: 0, _racrAy: 0,
          };
          SUM_COLS.forEach((c) => { o[c] = 0; });
          SHARE_NULL.forEach((c) => { o[c] = null; });
          by.set(pid, o);
        }
        SUM_COLS.forEach((c) => { o[c] = n(o[c]) + n(r[c]); });
        const tgt = n(r.tgt), ay = n(r.ay);
        if (r.tgtsh != null && +r.tgtsh > 0 && tgt > 0) o._teamTgt += tgt / +r.tgtsh;
        if (r.aysh != null && +r.aysh > 0 && ay > 0) o._teamAy += ay / +r.aysh;
        if (r.racr != null && ay > 0) { o._racrNum += +r.racr * ay; o._racrAy += ay; }
        if (r.name) o.name = r.name;
        if (r.pos) o.pos = r.pos;
        if (r.team) o.team = r.team;
        if (r.fr) {
          const bag = o._byFr[r.fr] || (o._byFr[r.fr] = { fpts: 0, starts: 0 });
          bag.fpts += n(r.fpts);
          bag.starts += n(r.starts);
        }
      });
    });
    const rows = [];
    by.forEach((o) => {
      o.opp = n(o.tgt) + n(o.car) + n(o.att);
      o.fppg = n(o.g) > 0 ? o.fpts / o.g : null;
      o.tgtsh = o._teamTgt > 0 ? n(o.tgt) / o._teamTgt : null;
      o.aysh = o._teamAy > 0 ? n(o.ay) / o._teamAy : null;
      o.wopr = (o.tgtsh != null || o.aysh != null) ? 1.5 * n(o.tgtsh) + 0.7 * n(o.aysh) : null;
      o.racr = o._racrAy > 0 ? o._racrNum / o._racrAy : null;
      o.fr = pickHomeFranchise(o._byFr);
      o.bid = careerBid(o.pid);
      delete o._byFr;
      delete o._teamTgt; delete o._teamAy; delete o._racrNum; delete o._racrAy;
      rows.push(o);
    });
    cache.set(ALL, rows);
    return rows;
  }

  async function loadScope() {
    if (isAll()) ROWS = await loadCareer();
    else ROWS = await loadSeason(state.season);
  }

  function snapshotYear() {
    if (!isAll()) return state.season;
    const ys = (META && META.seasons) || [];
    return ys.length ? ys[ys.length - 1] : null;
  }

  /* ---------------------------------------------------------------- filters */

  function visible(rows) {
    const src = rows || ROWS;
    return src.filter((r) => {
      if (state.pos !== "ALL" && r.pos !== state.pos) return false;
      if (state.view === "affl" && !r.starts) return false;
      if (state.franchise && currentFr(r.fr) !== state.franchise) return false;
      const opp = r.opp != null ? +r.opp : n(r.tgt) + n(r.car) + n(r.att);
      if (opp < state.minOpp) return false;
      if (state.q) {
        const q = state.q.toLowerCase();
        const blob = `${r.name || ""} ${r.team || ""} ${r.fr || ""} ${r.pos || ""}`.toLowerCase();
        if (!blob.includes(q)) return false;
      }
      return true;
    });
  }

  /* ------------------------------------------------------------------ chips */

  function chips(el, items, current, onPick, cls) {
    if (!el) return;
    const klass = cls || "season-chip";
    el.innerHTML = items.map(([v, l]) =>
      `<button type="button" class="${klass}${String(v) === String(current) ? " on" : ""}" data-v="${v}">${l}</button>`
    ).join("");
    el.querySelectorAll("button").forEach((b) => {
      b.addEventListener("click", () => onPick(b.dataset.v));
    });
  }

  function stampYear(v) {
    if (v === ALL || v == null) {
      state.scope = "cum";
      state.season = ALL;
    } else {
      state.scope = "season";
      state.season = +v;
    }
    stampScope();
  }

  function stampScope() {
    try {
      const u = new URL(location.href);
      if (state.scope === "season") {
        u.searchParams.set("scope", "season");
        if (state.season !== ALL && state.season != null) u.searchParams.set("year", String(state.season));
        else u.searchParams.delete("year");
      } else {
        u.searchParams.delete("scope");
        u.searchParams.delete("year");
        u.searchParams.delete("season");
      }
      history.replaceState(null, "", u.pathname.split("/").pop() + u.search + u.hash);
    } catch (e) { /* ignore */ }
  }

  function showYearRow(on) {
    const row = $("year-row");
    if (!row) return;
    if (on) { row.hidden = false; row.style.display = ""; }
    else { row.hidden = true; row.style.display = "none"; }
  }

  async function applyScope(scope, year) {
    if (scope === "season") {
      state.scope = "season";
      if (year === ALL || year == null) {
        const ys = (META && META.seasons) || [];
        state.season = ys.length ? ys[ys.length - 1] : ALL;
      } else {
        state.season = +year;
      }
      showYearRow(true);
    } else {
      state.scope = "cum";
      state.season = ALL;
      showYearRow(false);
    }
    stampScope();
    await loadScope();
    renderAll();
  }

  function stampPage(page) {
    try {
      const u = new URL(location.href);
      const hash = page === "home" ? "" : "#" + page;
      history.replaceState(null, "", u.pathname.split("/").pop() + u.search + hash);
    } catch (e) { /* ignore */ }
  }

  function setPage(page) {
    if (!PAGES.includes(page)) page = "home";
    state.page = page;
    PAGES.forEach((p) => {
      const el = $("page-" + p);
      if (el) el.hidden = p !== page;
    });
    document.querySelectorAll(".sv-subnav button").forEach((b) => {
      b.classList.toggle("on", b.dataset.page === page);
    });
    stampPage(page);
    if (page === "explore") renderExplore();
    if (page === "leaderboards") renderLeaderboards();
    if (page === "compare") renderCompare();
  }

  function renderChips() {
    chips($("scope-picker"), [["cum", "Cumulative"], ["season", "Season"]], state.scope, (v) => {
      applyScope(v, v === "season" ? state.season : ALL);
    });
    showYearRow(state.scope === "season");
    const seasons = META.seasons.map((y) => [y, y]);
    chips($("season-picker"), seasons, state.season, (v) => applyScope("season", +v));
    const squadEl = $("squad-picker");
    if (squadEl) {
      const items = [["", "All squads"]].concat(currentSquads().map((t) => [t.name, t.name]));
      chips(squadEl, items, state.franchise, (v) => {
        state.franchise = v;
        renderAll();
      });
    }
    const onSeason = (v) => applyScope(v === ALL ? "cum" : "season", v === ALL ? ALL : +v);
    const yearOpts = [[ALL, "All"]].concat(META.seasons.map((y) => [y, y]));
    chips($("pos-picker"), POSITIONS.map((p) => [p, p]), state.pos, (v) => {
      state.pos = v; renderAll();
    });
    chips($("view-picker"), [["all", "All NFL"], ["affl", "AFFL starters only"]], state.view, (v) => {
      state.view = v; renderAll();
    });
    const colorEl = $("color-picker");
    if (colorEl) {
      chips(colorEl, [["franchise", "Franchise"], ["position", "Position"]], state.color, (v) => {
        state.color = v; renderAll();
      });
    }
    chips($("home-pos"), POSITIONS.map((p) => [p, p]), state.pos, (v) => {
      state.pos = v; renderAll();
    }, "sv-chip");
    chips($("pl-pos"), POSITIONS.map((p) => [p, p]), state.pos, (v) => {
      state.pos = v; renderAll();
    }, "sv-chip");
    const fanYear = $("fan-year");
    if (fanYear && fanYear.tagName === "SELECT") {
      fanYear.innerHTML = yearOpts.map(([v, l]) =>
        `<option value="${v}">${v === ALL ? "All · career 2014–2025" : l}</option>`).join("");
      fanYear.value = String(state.season);
      fanYear.onchange = () => onSeason(fanYear.value);
    }
    const fanPos = $("fan-pos");
    if (fanPos && fanPos.tagName === "SELECT") {
      fanPos.innerHTML = POSITIONS.map((p) =>
        `<option value="${p}">${p === "ALL" ? "All positions" : p}</option>`).join("");
      fanPos.value = state.pos;
      fanPos.onchange = () => { state.pos = fanPos.value; renderAll(); };
    }
    chips($("h2h-pos"), POSITIONS.map((p) => [p, p]), state.pos, (v) => {
      state.pos = v; renderAll();
    }, "sv-chip");
    chips($("mover-pos"), POSITIONS.map((p) => [p, p]), state.moverPos, (v) => {
      state.moverPos = v; renderHome();
    }, "sv-chip");
    chips($("qb-show"), [
      ["ALL", "all"], ["QB", "passer"], ["RB", "rusher"], ["WR", "receiver"], ["TE", "TE"],
    ], state.pos, (v) => { state.pos = v; renderAll(); }, "sv-chip");
    chips($("qb-top"), TOPS.map((n) => [n, String(n)]), state.top, (v) => {
      state.top = +v; renderAll();
    }, "sv-chip");
  }

  function renderSelects() {
    const opts = Object.entries(METRICS)
      .map(([k, m]) => `<option value="${k}">${m.label}</option>`).join("");
    $("x-metric").innerHTML = opts;
    $("y-metric").innerHTML = opts;
    $("x-metric").value = state.x;
    $("y-metric").value = state.y;
    $("x-metric").onchange = () => { state.x = $("x-metric").value; renderAll(); };
    $("y-metric").onchange = () => { state.y = $("y-metric").value; renderAll(); };

    const frOpts = `<option value="">All franchises</option>` +
      META.franchises.map((f) => `<option value="${esc(f)}">${esc(f)}</option>`).join("");
    ["franchise", "pl-fr", "fan-fr"].forEach((id) => {
      const el = $(id);
      if (!el) return;
      el.innerHTML = frOpts;
      el.value = state.franchise;
      el.onchange = () => { state.franchise = el.value; renderAll(); };
    });

    $("min-opp").innerHTML = MIN_OPP
      .map((v) => `<option value="${v}">${v === 0 ? "No minimum" : v + "+"}</option>`).join("");
    $("min-opp").value = String(state.minOpp);
    $("min-opp").onchange = () => { state.minOpp = +$("min-opp").value; renderAll(); };

    if ($("pl-year")) {
      $("pl-year").innerHTML = `<option value="${ALL}">All · career 2014–2025</option>` +
        META.seasons.map((y) => `<option value="${y}">${y}</option>`).join("");
      $("pl-year").value = String(state.season);
      $("pl-year").onchange = () => {
        const y = parseYearParam($("pl-year").value);
        applyScope(y === ALL ? "cum" : "season", y);
      };
    }
  }

  function renderQueryChrome() {
    const compute = $("qb-compute");
    if (compute) {
      const keys = [state.x, state.y, "fpts", "bid"].filter((k, i, a) => a.indexOf(k) === i);
      compute.innerHTML = keys.map((k) => {
        const m = METRICS[k];
        return `<span class="sv-metric-chip">${esc(m ? m.label : k)}</span>`;
      }).join("") + `<span class="sv-metric-chip">+ metric on axes</span>`;
    }
    const where = $("qb-where");
    if (where) {
      const bits = [];
      bits.push(`<span class="sv-metric-chip">Season = ${isAll() ? "Cumulative · career 2014–2025" : state.season}</span>`);
      bits.push(`<span class="sv-metric-chip">Scoring = std · non-PPR</span>`);
      if (state.pos !== "ALL") bits.push(`<span class="sv-metric-chip">Pos = ${state.pos}</span>`);
      if (state.franchise) bits.push(`<span class="sv-metric-chip">Franchise = ${esc(state.franchise)}</span>`);
      if (state.minOpp) bits.push(`<span class="sv-metric-chip">Opp &gt;= ${state.minOpp}</span>`);
      if (state.view === "affl") bits.push(`<span class="sv-metric-chip">AFFL starters only</span>`);
      where.innerHTML = bits.join(" ");
    }
    const sum = $("qb-summary");
    if (sum) {
      const mx = METRICS[state.x], my = METRICS[state.y];
      sum.textContent =
        `QUERY Showing one row per player` +
        (isAll() ? " across Cumulative career 2014–2025" : ` for ${state.season}`) +
        (state.pos !== "ALL" ? ` where position is ${state.pos}` : "") +
        `. Sorted by ${METRICS[state.sort.key] ? METRICS[state.sort.key].label : state.sort.key}` +
        ` (${state.sort.dir < 0 ? "highest first" : "lowest first"}), min Opp >= ${state.minOpp}. Top ${state.top}.` +
        ` X = ${mx.label}; Y = ${my.label}. Scoring std, non-PPR.`;
    }
  }

  /* ------------------------------------------------------------------ chart */

  function groupKey(r) {
    if (state.color === "position") return r.pos || "?";
    return currentFr(r.fr);
  }

  function groupColor(key) {
    if (state.color === "position") return POS_COLOR[key] || MUTED;
    return key ? frColor(key) : MUTED;
  }

  function groupLabel(key, count) {
    if (state.color === "position") return `${key || "?"} (${count})`;
    if (!key) return `No AFFL points (${count})`;
    return `${key} (${count})`;
  }

  function renderChart(rows) {
    const canvas = $("sv-scatter");
    if (!canvas || $("page-explore").hidden) return;
    const mx = METRICS[state.x], my = METRICS[state.y];
    const by = {};
    rows.forEach((r) => {
      const x = mx.get(r), y = my.get(r);
      if (x == null || y == null || Number.isNaN(x) || Number.isNaN(y)) return;
      const k = groupKey(r);
      (by[k] = by[k] || []).push({ x, y, r });
    });

    const keys = Object.keys(by).sort((a, b) => {
      if (!a) return 1;
      if (!b) return -1;
      return a.localeCompare(b);
    });

    const datasets = keys.map((k) => {
      const col = groupColor(k);
      return {
        label: groupLabel(k, by[k].length),
        data: by[k],
        backgroundColor: col + "cc",
        borderColor: col,
        borderWidth: 1,
        pointRadius: 4,
        pointHoverRadius: 7,
        pointHitRadius: 14,
      };
    });

    function hideTip() {
      const tip = $("sv-tip");
      if (tip) tip.style.display = "none";
    }

    function showTip(evt, els) {
      const tip = $("sv-tip");
      if (!tip) return;
      if (!els || !els.length) { hideTip(); return; }
      const hit = els[0];
      const ds = chart.data.datasets[hit.datasetIndex];
      const raw = ds && ds.data ? ds.data[hit.index] : null;
      const r = raw && raw.r;
      if (!r) { hideTip(); return; }
      const fr = currentFr(r.fr);
      const lines = [
        `<b>${esc(displayName(r))}</b> · ${esc(r.pos || "—")} · ${esc(r.team || "FA")}`,
        `<span class="sv-tip-mut">${esc(mx.label)}: ${esc(fmt(raw.x, mx))}</span>`,
        `<span class="sv-tip-mut">${esc(my.label)}: ${esc(fmt(raw.y, my))}</span>`,
        `<span class="sv-tip-mut">${r.g == null ? "—" : r.g} games · ${esc(fmt(r.fpts, { nd: 1 }))} AFFL pts</span>`,
        `<span class="sv-tip-mut">${fr ? ("Franchise: " + esc(fr)) : "No AFFL points"}</span>`,
        `<span class="sv-tip-mut">Auction $: ${esc(fmtBid(r.bid))}</span>`,
      ];
      if (r.starts) lines.push(`<span class="sv-tip-mut">Started ${r.starts}×` + (fr ? ` by ${esc(fr)}` : "") + "</span>");
      else if (!isAll()) lines.push(`<span class="sv-tip-mut">Never started in the AFFL this season</span>`);
      tip.innerHTML = lines.join("<br>");
      const plot = tip.parentElement;
      const rec = plot.getBoundingClientRect();
      const nx = evt.native ? evt.native.clientX : (evt.clientX || 0);
      const ny = evt.native ? evt.native.clientY : (evt.clientY || 0);
      let left = nx - rec.left + 14;
      let top = ny - rec.top + 14;
      tip.style.display = "block";
      const tw = tip.offsetWidth || 200;
      const th = tip.offsetHeight || 80;
      if (left + tw > rec.width - 8) left = rec.width - tw - 8;
      if (top + th > rec.height - 8) top = rec.height - th - 8;
      if (left < 8) left = 8;
      if (top < 8) top = 8;
      tip.style.left = left + "px";
      tip.style.top = top + "px";
    }

    const grid = "#eef1f4";
    const tick = "#64748b";
    const cfg = {
      type: "scatter",
      data: { datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        events: ["mousemove", "mouseout", "click", "touchstart", "touchmove"],
        interaction: { mode: "nearest", intersect: true, axis: "xy" },
        onHover: (evt, els) => { showTip(evt, els); },
        plugins: {
          legend: { display: false },
          tooltip: {
            enabled: false,
            backgroundColor: "#111827f2",
            titleColor: "#fff",
            bodyColor: "#e5e7eb",
            callbacks: {
              title: (items) => {
                const r = items[0].raw.r;
                return `${displayName(r)} · ${r.pos || "—"} · ${r.team || "FA"}`;
              },
              label: (item) => {
                const r = item.raw.r;
                const out = [
                  `${mx.label}: ${fmt(item.raw.x, mx)}`,
                  `${my.label}: ${fmt(item.raw.y, my)}`,
                  `${r.g == null ? "—" : r.g} games · ${fmt(r.fpts, { nd: 1 })} AFFL pts`,
                  r.fr ? `Franchise: ${currentFr(r.fr)}` : "No AFFL points",
                  `Auction $: ${fmtBid(r.bid)}`,
                ];
                if (r.starts) out.push(`Started ${r.starts}×` + (r.fr ? ` by ${currentFr(r.fr)}` : ""));
                else if (!isAll()) out.push("Never started in the AFFL this season");
                return out;
              },
            },
          },
        },
        scales: {
          x: {
            title: { display: true, text: mx.label, color: "#111827" },
            grid: { color: grid },
            ticks: { color: tick },
          },
          y: {
            title: { display: true, text: my.label, color: "#111827" },
            grid: { color: grid },
            ticks: { color: tick },
          },
        },
      },
    };

    if (chart) { chart.destroy(); chart = null; }
    hideTip();
    chart = new Chart(canvas.getContext("2d"), cfg);
    canvas.onmouseleave = hideTip;

    $("sv-legend").innerHTML = keys.map((k) =>
      `<span class="sv-key"><span class="sv-dot" style="background:${groupColor(k)}"></span>${esc(groupLabel(k, by[k].length))}</span>`
    ).join("");
  }

  /* ------------------------------------------------------------------ table */

  const TCOLS = [
    ["name", "Player"], ["pos", "Pos"], ["team", "Team"], ["g", "G"],
    ["opp", "Opp"], ["tgt", "Tgt"], ["car", "Car"], ["att", "Att"],
    ["fpts", "FPts"], ["fppg", "FP/G"], ["epa", "EPA"],
    ["starts", "AFFL starts"], ["fr", "Franchise"], ["bid", "Auction $"],
  ];

  function cell(r, key) {
    if (key === "opp") return r.opp != null ? +r.opp : n(r.tgt) + n(r.car) + n(r.att);
    if (key === "bid") return r.bid == null ? null : +r.bid;
    return r[key];
  }

  function sortRows(rows, key, dir, limit) {
    const sorted = rows.slice().sort((a, b) => {
      const av = cell(a, key), bv = cell(b, key);
      if (typeof av === "string" || typeof bv === "string") {
        return String(av || "").localeCompare(String(bv || "")) * -dir;
      }
      return ((bv == null ? -Infinity : bv) - (av == null ? -Infinity : av)) * (dir < 0 ? 1 : -1);
    });
    return limit ? sorted.slice(0, limit) : sorted;
  }

  function playerCell(r) {
    return `<span class="sv-player">${barHTML(r.team, r.fr)}<span>${esc(displayName(r))}</span></span>`;
  }

  function renderTable(rows) {
    $("sv-head").innerHTML = TCOLS.map(([k, l]) =>
      `<th data-k="${k}" class="${state.sort.key === k ? "on" : ""}">${l}${state.sort.key === k ? (state.sort.dir < 0 ? " ▾" : " ▴") : ""}</th>`
    ).join("");
    $("sv-head").querySelectorAll("th").forEach((th) => {
      th.addEventListener("click", () => {
        const k = th.dataset.k;
        if (state.sort.key === k) state.sort.dir *= -1;
        else state.sort = { key: k, dir: -1 };
        renderAll();
      });
    });

    const sorted = sortRows(rows, state.sort.key, state.sort.dir, state.top);

    if (!sorted.length) {
      $("sv-body").innerHTML = `<tr><td class="sv-empty" colspan="${TCOLS.length}">No players match these filters.</td></tr>`;
      return;
    }

    $("sv-body").innerHTML = sorted.map((r) => `<tr>
      <td>${playerCell(r)}</td>
      <td><span class="sv-pos">${esc(r.pos)}</span></td>
      <td>${esc(r.team || "—")}</td>
      <td>${r.g == null ? "—" : r.g}</td>
      <td>${cell(r, "opp")}</td>
      <td>${r.tgt == null ? "—" : r.tgt}</td>
      <td>${r.car == null ? "—" : r.car}</td>
      <td>${r.att == null ? "—" : r.att}</td>
      <td class="${state.sort.key === "fpts" ? "sv-metric" : ""}">${fmt(r.fpts, { nd: 1 })}</td>
      <td>${fmt(r.fppg, { nd: 2 })}</td>
      <td>${fmt(r.epa, { nd: 1 })}</td>
      <td>${r.starts || "—"}</td>
      <td class="sv-fr">${esc(r.fr || "—")}</td>
      <td>${r.bid == null ? "—" : fmtBid(r.bid)}</td>
    </tr>`).join("");
  }

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g,
      (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  function exportCSV(rows) {
    const sorted = sortRows(rows, state.sort.key, state.sort.dir, state.top);
    const head = TCOLS.map(([, l]) => l).join(",");
    const body = sorted.map((r) => TCOLS.map(([k]) => {
      let v;
      if (k === "name") v = displayName(r);
      else if (k === "bid") v = r.bid == null ? "" : r.bid;
      else v = cell(r, k);
      if (v == null) return "";
      const s = String(v);
      return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
    }).join(",")).join("\n");
    const blob = new Blob([head + "\n" + body], { type: "text/csv" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `affl-savant-${isAll() ? "career" : state.season}.csv`;
    a.click();
    URL.revokeObjectURL(a.href);
  }

  /* ----------------------------------------------------------------- home */

  function mean(vals) {
    const xs = vals.filter((v) => v != null && !Number.isNaN(+v));
    if (!xs.length) return null;
    return xs.reduce((s, v) => s + +v, 0) / xs.length;
  }

  function rankedList(rows, metric, n) {
    const m = METRICS[metric];
    return sortRows(rows.filter((r) => {
      const v = m.get(r);
      return v != null && !Number.isNaN(+v);
    }), metric, -1, n);
  }

  async function renderHome() {
    const y = snapshotYear();
    let yearRows = [];
    try { if (y) yearRows = await loadSeason(y); } catch (e) { yearRows = []; }
    const pos = state.pos;
    const pool = yearRows.filter((r) => pos === "ALL" || r.pos === pos);

    const feat = rankedList(pool.filter((r) => n(r.g) >= 8), "fppg", 5);
    $("feat-title").textContent = "AFFL POINTS / GAME";
    $("feat-sub").textContent = `${y || "—"} · std non-PPR · min 8 games · empty stays empty`;
    $("feat-list").innerHTML = feat.length
      ? feat.map((r, i) => `<div class="sv-row">
          <span class="sv-rank">${i + 1}</span>
          ${barHTML(r.team, r.fr)}
          <div class="sv-who"><div class="nm">${esc(displayName(r))}</div>
            <div class="sub">${esc(r.pos || "")} · ${esc(r.team || "FA")}${r.fr ? " · " + esc(r.fr) : ""}</div></div>
          <span class="sv-val">${fmt(r.fppg, { nd: 2 })}</span>
        </div>`).join("")
      : `<div class="sv-empty">No qualified players in this scope.</div>`;

    await renderSlate(y);
    await renderMovers(y);
    renderPulse(yearRows, y);
    bindH2H(pool);
  }

  function canon(id) {
    if (id == null || id === "") return id;
    return MERGE[String(id)] || String(id);
  }

  function franchiseNow(owner) {
    if (A && A.franchiseName) return A.franchiseName(owner) || "";
    const frs = (LEAGUE && LEAGUE.franchises) || [];
    const f = frs.find((x) => canon(x.owner) === canon(owner));
    return (f && f.currentName) || "";
  }

  function teamByTid(year, tid) {
    if (A && A.teams) {
      const bag = A.teams(year) || {};
      return bag[tid] || bag[String(tid)] || null;
    }
    const teams = (((LEAGUE || {}).seasons || {})[String(year)] || {}).teams || [];
    return teams.find((t) => t.id === tid || String(t.id) === String(tid)) || null;
  }

  async function renderSlate(year) {
    const box = $("slate-list");
    $("slate-kicker").textContent = year ? `Week slate · ${year}` : "Week slate";
    $("slate-title").textContent = "AFFL MATCHUPS";
    if (!year) {
      box.innerHTML = `<div class="sv-empty">No season in scope.</div>`;
      return;
    }
    let yd = null;
    try {
      if (A && A.loadYear) yd = await A.loadYear(year);
      else {
        const res = await fetch(`years/${year}.json`);
        yd = res.ok ? await res.json() : null;
      }
    } catch (e) { yd = null; }
    const weeks = Object.keys((yd && yd.weeks) || {}).map(Number).sort((a, b) => a - b);
    if (!weeks.length) {
      box.innerHTML = `<div class="sv-empty">No matchup weeks stored for ${year}.</div>`;
      return;
    }
    const wk = weeks[weeks.length - 1];
    const games = yd.weeks[String(wk)] || [];
    $("slate-kicker").textContent = `Week slate · ${year} · W${wk}`;
    if (!games.length) {
      box.innerHTML = `<div class="sv-empty">No games stored for week ${wk}.</div>`;
      return;
    }
    box.innerHTML = games.map((g) => {
      const home = teamByTid(year, g.home && g.home.tid);
      const away = teamByTid(year, g.away && g.away.tid);
      const hn = franchiseNow((home && (home.owner || home.oid)) || "") || (home && home.name) || "—";
      const an = franchiseNow((away && (away.owner || away.oid)) || "") || (away && away.name) || "—";
      const ha = FR_ABBR[hn] || (home && home.abbrev) || "?";
      const aa = FR_ABBR[an] || (away && away.abbrev) || "?";
      const hp = g.home && g.home.pts != null ? g.home.pts : null;
      const ap = g.away && g.away.pts != null ? g.away.pts : null;
      return `<div class="sv-game">
        <div class="st">${hp != null ? "Final" : "—"}</div>
        <div class="sv-sides">
          <div class="sv-side">${barHTML(null, an)}<span>${esc(aa)}</span><span class="sc">${ap == null ? "—" : fmt(ap, { nd: 1 })}</span></div>
          <div class="sv-side">${barHTML(null, hn)}<span>${esc(ha)}</span><span class="sc">${hp == null ? "—" : fmt(hp, { nd: 1 })}</span></div>
        </div>
        <div class="sv-meta">${esc(an)} @ ${esc(hn)}</div>
      </div>`;
    }).join("");
  }

  async function renderMovers(year) {
    const box = $("mover-list");
    if (!year || !META.seasons.includes(year - 1)) {
      box.innerHTML = `<div class="sv-empty">No prior season to compare.</div>`;
      return;
    }
    let prev = [], cur = [];
    try {
      prev = await loadSeason(year - 1);
      cur = await loadSeason(year);
    } catch (e) {
      box.innerHTML = `<div class="sv-empty">Year-over-year rows unavailable.</div>`;
      return;
    }
    const byPrev = new Map(prev.map((r) => [r.pid, r]));
    const pos = state.moverPos;
    const movers = [];
    cur.forEach((r) => {
      if (pos !== "ALL" && r.pos !== pos) return;
      const p = byPrev.get(r.pid);
      if (!p || r.fpts == null || p.fpts == null) return;
      movers.push({ r, delta: +r.fpts - +p.fpts, prev: p });
    });
    movers.sort((a, b) => Math.abs(b.delta) - Math.abs(a.delta));
    const show = movers.slice(0, 6);
    if (!show.length) {
      box.innerHTML = `<div class="sv-empty">No overlapping players between ${year - 1} and ${year}.</div>`;
      return;
    }
    box.innerHTML = show.map((m) => {
      const up = m.delta >= 0;
      return `<div class="sv-row">
        <span class="sv-delta${up ? "" : " down"}">${up ? "↑" : "▼"} ${fmt(Math.abs(m.delta), { nd: 1 })}</span>
        ${barHTML(m.r.team, m.r.fr)}
        <div class="sv-who"><div class="nm">${esc(displayName(m.r))}</div>
          <div class="sub">${esc(m.r.pos || "")} · ${esc(m.r.team || "FA")} · FPTS ${year - 1}→${year}</div></div>
        <span class="sv-val${up ? "" : " neg"}">${up ? "+" : ""}${fmt(m.delta, { nd: 1 })}</span>
      </div>`;
    }).join("");
  }

  function renderPulse(yearRows, year) {
    const box = $("pulse-row");
    $("pulse-kicker").textContent = year ? `League pulse · ${year}` : "League pulse";
    const skilled = yearRows.filter((r) => n(r.g) >= 8);
    const cards = [];
    const avgFppg = mean(skilled.map((r) => r.fppg));
    const avgEpa = mean(skilled.map((r) => r.epa));
    let att = 0, rush = 0;
    yearRows.forEach((r) => { att += n(r.att); rush += n(r.car); });
    const mix = (att + rush) > 0 ? 100 * att / (att + rush) : null;
    const bids = yearRows.map((r) => r.bid).filter((v) => v != null);
    const avgBid = bids.length ? mean(bids) : null;
    function card(val, label, nd) {
      if (val == null) return "";
      return `<div class="sv-card"><div class="big">${fmt(val, { nd })}</div><div class="sv-k">${label}</div></div>`;
    }
    cards.push(card(avgFppg, "Avg FP/G · min 8g", 2));
    cards.push(card(avgEpa, "Avg EPA · min 8g", 1));
    cards.push(card(mix, "Pass att / (att+car)", 1));
    cards.push(card(avgBid, "Avg auction $ · drafted", 0));
    box.innerHTML = cards.filter(Boolean).join("") ||
      `<div class="sv-empty">No pulse columns in this scope.</div>`;
  }

  function bindH2H(pool) {
    function wire(inputId, listId, cardId, side) {
      const input = $(inputId), list = $(listId), card = $(cardId);
      if (!input) return;
      const paint = () => {
        const r = state.h2h[side];
        if (!r) { card.innerHTML = ""; return; }
        card.innerHTML = `<div class="sv-row" style="border:0;padding-top:10px">
          ${barHTML(r.team, r.fr)}
          <div class="sv-who"><div class="nm">${esc(displayName(r))}</div>
            <div class="sub">${esc(r.pos || "")} · ${esc(r.team || "FA")}</div></div>
        </div>
        <div class="sv-meta">${fmt(r.fpts, { nd: 1 })} AFFL pts · ${fmt(r.fppg, { nd: 2 })} /g · Auction ${fmtBid(r.bid)}</div>`;
      };
      input.oninput = () => {
        const q = input.value.trim().toLowerCase();
        if (q.length < 2) { list.hidden = true; list.innerHTML = ""; return; }
        const hits = pool.filter((r) => String(r.name || "").toLowerCase().includes(q)).slice(0, 8);
        if (!hits.length) { list.hidden = true; return; }
        list.hidden = false;
        list.innerHTML = hits.map((r) =>
          `<li data-pid="${esc(r.pid)}">${esc(displayName(r))} · ${esc(r.pos || "")} · ${esc(r.team || "")}</li>`
        ).join("");
        list.querySelectorAll("li").forEach((li) => {
          li.onclick = () => {
            const r = pool.find((x) => String(x.pid) === li.dataset.pid);
            state.h2h[side] = r || null;
            input.value = r ? displayName(r) : "";
            list.hidden = true;
            paint();
          };
        });
      };
      paint();
    }
    wire("h2h-a", "h2h-a-list", "h2h-a-card", "a");
    wire("h2h-b", "h2h-b-list", "h2h-b-card", "b");
  }

  /* -------------------------------------------------------------- players */

  function renderPlayers() {
    const rows = visible();
    const byPos = { QB: [], RB: [], WR: [], TE: [] };
    Object.keys(byPos).forEach((p) => {
      byPos[p] = rankedList(rows.filter((r) => r.pos === p && n(r.g) >= 1), "fpts", 5);
    });
    const labels = { QB: ["QUARTERBACKS", "AFFL pts"], RB: ["RUNNING BACKS", "AFFL pts"], WR: ["WIDE RECEIVERS", "AFFL pts"], TE: ["TIGHT ENDS", "AFFL pts"] };
    $("pl-spot").innerHTML = Object.keys(byPos).map((p) => {
      const list = byPos[p];
      const body = list.length
        ? list.map((r, i) => `<div class="sv-row">
            <span class="sv-rank">${i + 1}</span>${barHTML(r.team, r.fr)}
            <div class="sv-who"><div class="nm">${esc(displayName(r))}</div>
              <div class="sub">${esc(r.pos)} · ${esc(r.team || "FA")}</div></div>
            <span class="sv-val">${fmt(r.fpts, { nd: 1 })}</span>
          </div>`).join("")
        : `<div class="sv-empty">Empty.</div>`;
      return `<section class="sv-card">
        <div class="sv-card-head"><div class="sv-kicker">${p}</div><div class="sv-meta">${labels[p][1]}</div></div>
        <h2>${labels[p][0]}</h2>
        ${body}
        <p style="margin-top:10px"><button type="button" class="sv-link" data-go="leaderboards" data-board="${p === "QB" ? "passing" : p === "RB" ? "rushing" : "receiving"}" data-pos="${p}">View full board →</button></p>
      </section>`;
    }).join("");
    $("pl-spot").querySelectorAll("[data-go]").forEach((b) => {
      b.addEventListener("click", () => {
        if (b.dataset.pos) state.pos = b.dataset.pos;
        if (b.dataset.board) state.lb.board = b.dataset.board;
        setPage(b.dataset.go || "leaderboards");
        renderAll();
      });
    });

    const listed = sortRows(rows, "fpts", -1, state.top);
    $("pl-body").innerHTML = listed.length
      ? listed.map((r, i) => `<tr>
          <td>${i + 1}</td>
          <td>${playerCell(r)}</td>
          <td>${esc(r.pos || "—")}</td>
          <td>${esc(r.team || "—")}</td>
          <td>${r.g == null ? "—" : r.g}</td>
          <td class="sv-metric">${fmt(r.fpts, { nd: 1 })}</td>
          <td>${fmt(r.fppg, { nd: 2 })}</td>
          <td>${r.bid == null ? "—" : fmtBid(r.bid)}</td>
          <td class="sv-fr">${esc(r.fr || "—")}</td>
        </tr>`).join("")
      : `<tr><td class="sv-empty" colspan="9">No players match these filters.</td></tr>`;
  }

  /* -------------------------------------------------------------- fantasy */

  function renderFantasy() {
    const q = (($("fan-name") && $("fan-name").value) || "").trim().toLowerCase();
    const rows = visible().filter((r) => {
      if (!q) return true;
      return String(r.name || "").toLowerCase().includes(q);
    });
    const listed = sortRows(rows, "fpts", -1, state.top);
    $("fan-body").innerHTML = listed.length
      ? listed.map((r, i) => `<tr>
          <td>${i + 1}</td>
          <td>${playerCell(r)}</td>
          <td>${esc(r.pos || "—")}</td>
          <td>${cell(r, "opp")}</td>
          <td>${r.tgtsh == null ? "—" : fmt(pct(r.tgtsh), { nd: 1 }) + "%"}</td>
          <td>${fmt(r.wopr, { nd: 3 })}</td>
          <td class="sv-metric">${fmt(r.fpts, { nd: 1 })}</td>
          <td>${fmt(r.fppg, { nd: 2 })}</td>
          <td>${r.bid == null ? "—" : fmtBid(r.bid)}</td>
        </tr>`).join("")
      : `<tr><td class="sv-empty" colspan="9">No players match these filters.</td></tr>`;
  }

  /* -------------------------------------------------------------------- all */

  /* --------------------------------------------------------- leaderboards */

  function lastSeason() {
    const ys = (META && META.seasons) || [];
    return ys.length ? ys[ys.length - 1] : null;
  }

  function lbSeason() {
    return state.lb.season == null ? lastSeason() : state.lb.season;
  }

  function cmpSeason() {
    return state.cmp.season == null ? lastSeason() : state.cmp.season;
  }

  function heatClass(vals, v, lowerBetter) {
    const xs = vals.filter((x) => x != null && !Number.isNaN(+x)).map(Number).sort((a, b) => a - b);
    if (xs.length < 8 || v == null || Number.isNaN(+v)) return "";
    const lo = xs[Math.floor((xs.length - 1) * 0.1)];
    const hi = xs[Math.floor((xs.length - 1) * 0.9)];
    if (lowerBetter) {
      if (+v <= lo) return "sv-heat-hi";
      if (+v >= hi) return "sv-heat-lo";
    } else {
      if (+v >= hi) return "sv-heat-hi";
      if (+v <= lo) return "sv-heat-lo";
    }
    return "";
  }

  function percentile(vals, v) {
    const xs = vals.filter((x) => x != null && !Number.isNaN(+x)).map(Number).sort((a, b) => a - b);
    if (!xs.length || v == null || Number.isNaN(+v)) return null;
    let below = 0;
    xs.forEach((x) => { if (x <= +v) below += 1; });
    return Math.round(100 * below / xs.length);
  }

  const BOARDS = {
    passing: {
      title: "Passing · EPA/play",
      blurb: "Expected points added per pass attempt from stored nflverse EPA and attempts. Success %, CPOE, and aDOT are not in this warehouse — those cells stay empty. AFFL scoring is std, non-PPR.",
      label: "Passing",
      sort: "epap",
      chart: { x: "att", y: "epa", pos: "QB" },
      qual: (r, career) => n(r.att) >= (career ? 200 : 100),
      cols: [
        { k: "epap", l: "EPA/play", get: (r) => rate(r.epa, r.att), nd: 2 },
        { k: "succ", l: "Success %", get: () => null, empty: true },
        { k: "cmp", l: "Comp", get: (r) => r.cmp },
        { k: "att", l: "Att", get: (r) => r.att },
        { k: "cmpp", l: "Comp %", get: (r) => { const v = rate(r.cmp, r.att); return v == null ? null : v * 100; }, nd: 1, pct: true },
        { k: "cpoe", l: "CPOE", get: () => null, empty: true },
        { k: "payd", l: "Yds", get: (r) => r.payd },
        { k: "ya", l: "Y/A", get: (r) => rate(r.payd, r.att), nd: 1 },
        { k: "adot", l: "aDOT", get: () => null, empty: true },
        { k: "patd", l: "TD", get: (r) => r.patd },
        { k: "int", l: "INT", get: (r) => r.int, lower: true },
      ],
    },
    receiving: {
      title: "Receiving · AFFL pts",
      blurb: "Receiving volume and AFFL non-PPR points from stored columns. Receptions score zero. Share stats stay empty on career.",
      label: "Receiving",
      sort: "fpts",
      chart: { x: "tgt", y: "fpts", pos: "WR" },
      qual: (r, career) => n(r.tgt) >= (career ? 80 : 40),
      cols: [
        { k: "fpts", l: "FPts", get: (r) => r.fpts, nd: 1 },
        { k: "fppg", l: "FP/G", get: (r) => r.fppg, nd: 2 },
        { k: "tgt", l: "Tgt", get: (r) => r.tgt },
        { k: "rec", l: "Rec", get: (r) => r.rec },
        { k: "recyd", l: "Yds", get: (r) => r.recyd },
        { k: "rectd", l: "TD", get: (r) => r.rectd },
        { k: "wopr", l: "WOPR", get: (r) => r.wopr, nd: 3 },
        { k: "tgtsh", l: "Tgt%", get: (r) => r.tgtsh == null ? null : +r.tgtsh * 100, nd: 1, pct: true },
      ],
    },
    rushing: {
      title: "Rushing · AFFL pts",
      blurb: "Rushing volume and AFFL non-PPR points from stored columns. Empty stays empty.",
      label: "Rushing",
      sort: "fpts",
      chart: { x: "car", y: "fpts", pos: "RB" },
      qual: (r, career) => n(r.car) >= (career ? 100 : 50),
      cols: [
        { k: "fpts", l: "FPts", get: (r) => r.fpts, nd: 1 },
        { k: "fppg", l: "FP/G", get: (r) => r.fppg, nd: 2 },
        { k: "car", l: "Car", get: (r) => r.car },
        { k: "ruyd", l: "Yds", get: (r) => r.ruyd },
        { k: "rutd", l: "TD", get: (r) => r.rutd },
        { k: "epa", l: "EPA", get: (r) => r.epa, nd: 1 },
      ],
    },
    fantasy: {
      title: "Fantasy · AFFL pts",
      blurb: "AFFL non-PPR points. Scoring is std — receptions score zero. There is no PPR board.",
      label: "Fantasy",
      sort: "fpts",
      chart: { x: "opp", y: "fpts", pos: "ALL" },
      qual: (r) => n(r.g) >= 8,
      cols: [
        { k: "fpts", l: "FPts", get: (r) => r.fpts, nd: 1 },
        { k: "fppg", l: "FP/G", get: (r) => r.fppg, nd: 2 },
        { k: "opp", l: "Opp", get: (r) => r.opp != null ? +r.opp : n(r.tgt) + n(r.car) + n(r.att) },
        { k: "epa", l: "EPA", get: (r) => r.epa, nd: 1 },
        { k: "starts", l: "AFFL starts", get: (r) => r.starts },
        { k: "bid", l: "Auction $", get: (r) => r.bid, bid: true },
      ],
    },
    auction: {
      title: "Auction $",
      blurb: "GSIS-keyed auction bids. 2014–15 snake drafts are unavailable, never $0.",
      label: "Auction",
      sort: "bid",
      chart: { x: "bid", y: "fpts", pos: "ALL" },
      qual: (r) => r.bid != null,
      cols: [
        { k: "bid", l: "Auction $", get: (r) => r.bid, bid: true },
        { k: "fpts", l: "FPts", get: (r) => r.fpts, nd: 1 },
        { k: "fppg", l: "FP/G", get: (r) => r.fppg, nd: 2 },
        { k: "starts", l: "AFFL starts", get: (r) => r.starts },
      ],
    },
    movers: {
      title: "Movers · year over year",
      blurb: "AFFL non-PPR point change versus the prior stored season. Players without both years stay out.",
      label: "Movers",
      sort: "delta",
      chart: { x: "opp", y: "fpts", pos: "ALL" },
      qual: () => true,
      cols: [
        { k: "delta", l: "Δ FPts", get: (r) => r.delta, nd: 1 },
        { k: "fpts", l: "FPts", get: (r) => r.fpts, nd: 1 },
        { k: "prev", l: "Prior", get: (r) => r.prevFpts, nd: 1 },
        { k: "fppg", l: "FP/G", get: (r) => r.fppg, nd: 2 },
      ],
    },
  };

  async function scopeRows(year) {
    if (year === ALL || year == null) return loadCareer();
    return loadSeason(year);
  }

  async function renderLeaderboards() {
    const board = BOARDS[state.lb.board] || BOARDS.passing;
    $("lb-title").textContent = board.title;
    $("lb-blurb").textContent = board.blurb;
    const tabs = $("lb-tabs");
    tabs.innerHTML = Object.keys(BOARDS).map((k) =>
      `<button type="button" data-board="${k}" class="${k === state.lb.board ? "on" : ""}">${BOARDS[k].label}</button>`
    ).join("");
    tabs.querySelectorAll("button").forEach((b) => {
      b.onclick = () => {
        state.lb.board = b.dataset.board;
        const next = BOARDS[state.lb.board];
        state.lb.sort = { key: next.sort, dir: -1 };
        renderLeaderboards();
      };
    });

    const seasons = [[ALL, "All · career 2014–2025"]].concat(META.seasons.map((y) => [y, String(y)]));
    const ySel = $("lb-year");
    const yCur = lbSeason();
    if (ySel && !ySel.dataset.ready) {
      ySel.innerHTML = seasons.map(([v, l]) => `<option value="${v}">${l}</option>`).join("");
      ySel.dataset.ready = "1";
      ySel.onchange = () => {
        state.lb.season = ySel.value === ALL ? ALL : +ySel.value;
        renderLeaderboards();
      };
    }
    if (ySel) ySel.value = String(yCur);

    if ($("lb-qual")) $("lb-qual").onchange = () => {
      state.lb.qual = $("lb-qual").value;
      renderLeaderboards();
    };
    if ($("lb-qual")) $("lb-qual").value = state.lb.qual;
    if ($("lb-name")) $("lb-name").oninput = () => {
      state.lb.name = $("lb-name").value.trim().toLowerCase();
      renderLeaderboards();
    };

    let rows = [];
    try { rows = await scopeRows(yCur); } catch (e) { rows = []; }

    const teams = [...new Set(rows.map((r) => r.team).filter(Boolean))].sort();
    const tSel = $("lb-team");
    if (tSel) {
      const keep = tSel.value || state.lb.team || "";
      tSel.innerHTML = `<option value="">All teams</option>` +
        teams.map((t) => `<option value="${esc(t)}">${esc(t)}</option>`).join("");
      tSel.value = teams.includes(keep) ? keep : "";
      state.lb.team = tSel.value;
      tSel.onchange = () => { state.lb.team = tSel.value; renderLeaderboards(); };
    }

    const career = yCur === ALL;
    if (state.lb.board === "movers") {
      rows = await moverRows(yCur);
    }
    rows = rows.filter((r) => {
      if (state.lb.team && r.team !== state.lb.team) return false;
      if (state.lb.qual === "qualified" && !board.qual(r, career)) return false;
      if (state.lb.name) {
        const blob = `${r.name || ""} ${r.team || ""} ${r.pos || ""}`.toLowerCase();
        if (!blob.includes(state.lb.name)) return false;
      }
      return true;
    });

    const cols = board.cols;
    const heatBag = {};
    cols.forEach((c) => {
      heatBag[c.k] = rows.map((r) => c.get(r));
    });

    const head = ["#", "Player", "Pos", "Team"].concat(cols.map((c) => c.l));
    $("lb-head").innerHTML = ["#", "name", "pos", "team"].concat(cols.map((c) => c.k)).map((k, i) => {
      const on = state.lb.sort.key === k || (i >= 4 && cols[i - 4] && cols[i - 4].k === state.lb.sort.key);
      const label = head[i];
      const key = i < 4 ? (k === "name" ? "name" : k) : cols[i - 4].k;
      return `<th data-k="${key}" class="${on ? "on" : ""}">${label}${on ? (state.lb.sort.dir < 0 ? " ▾" : " ▴") : ""}</th>`;
    }).join("");
    $("lb-head").querySelectorAll("th").forEach((th) => {
      th.onclick = () => {
        const k = th.dataset.k;
        if (state.lb.sort.key === k) state.lb.sort.dir *= -1;
        else state.lb.sort = { key: k, dir: -1 };
        renderLeaderboards();
      };
    });

    const sorted = rows.slice().sort((a, b) => {
      const col = cols.find((c) => c.k === state.lb.sort.key);
      const av = col ? col.get(a) : (state.lb.sort.key === "name" ? displayName(a) : a[state.lb.sort.key]);
      const bv = col ? col.get(b) : (state.lb.sort.key === "name" ? displayName(b) : b[state.lb.sort.key]);
      if (typeof av === "string" || typeof bv === "string") {
        return String(av || "").localeCompare(String(bv || "")) * -state.lb.sort.dir;
      }
      return ((bv == null ? -Infinity : bv) - (av == null ? -Infinity : av)) * (state.lb.sort.dir < 0 ? 1 : -1);
    });

    if (!sorted.length) {
      $("lb-body").innerHTML = `<tr><td class="sv-empty" colspan="${head.length}">No players match these filters. Empty stays empty.</td></tr>`;
      return;
    }

    const paintRow = (r, i) => `<tr>
      <td>${i + 1}</td>
      <td><span class="sv-player">${sqHTML(r.team, r.fr)}<span>${esc(displayName(r))}</span></span></td>
      <td><span class="sv-pos">${esc(r.pos || "—")}</span></td>
      <td>${esc(r.team || "—")}</td>
      ${cols.map((c) => {
        const v = c.get(r);
        if (c.empty || v == null) return `<td>—</td>`;
        const txt = c.bid ? (r.bid == null ? "—" : fmtBid(r.bid))
          : (c.pct ? fmt(v, { nd: c.nd != null ? c.nd : 1 }) + "%" : fmt(v, { nd: c.nd != null ? c.nd : 0 }));
        const cls = heatClass(heatBag[c.k], v, !!c.lower);
        return `<td>${cls ? `<span class="${cls}">${txt}</span>` : txt}</td>`;
      }).join("")}
    </tr>`;

    const chunks = [];
    sorted.forEach((r, i) => {
      if (i > 0 && i % 25 === 0) {
        chunks.push(`<tr>${head.map((h) => `<th>${h}</th>`).join("")}</tr>`);
      }
      chunks.push(paintRow(r, i));
    });
    $("lb-body").innerHTML = chunks.join("");
    window._lbExport = { cols, rows: sorted, head };
  }

  async function moverRows(year) {
    if (year === ALL || year == null) {
      year = lastSeason();
    }
    if (!year || !META.seasons.includes(year - 1)) return [];
    const [prev, cur] = await Promise.all([loadSeason(year - 1), loadSeason(year)]);
    const byPrev = new Map(prev.map((r) => [r.pid, r]));
    const out = [];
    cur.forEach((r) => {
      const p = byPrev.get(r.pid);
      if (!p || r.fpts == null || p.fpts == null) return;
      out.push(Object.assign({}, r, { delta: +r.fpts - +p.fpts, prevFpts: +p.fpts }));
    });
    return out;
  }

  function exportLeaderboard() {
    const pack = window._lbExport;
    if (!pack) return;
    const cols = pack.cols;
    const head = ["#", "Player", "Pos", "Team"].concat(cols.map((c) => c.l)).join(",");
    const body = pack.rows.map((r, i) => {
      const cells = [i + 1, displayName(r), r.pos || "", r.team || ""].concat(cols.map((c) => {
        const v = c.get(r);
        return v == null ? "" : v;
      }));
      return cells.map((v) => {
        const s = String(v);
        return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
      }).join(",");
    }).join("\n");
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([head + "\n" + body], { type: "text/csv" }));
    a.download = `affl-savant-leaderboard-${state.lb.board}-${lbSeason()}.csv`;
    a.click();
  }

  /* -------------------------------------------------------------- compare */

  const TAPE = [
    { cat: "Efficiency" },
    { k: "fppg", l: "FP/G", get: (r) => r.fppg, nd: 2 },
    { k: "epa", l: "EPA", get: (r) => r.epa, nd: 1 },
    { k: "epap", l: "EPA / play", get: (r) => rate(r.epa, n(r.att) + n(r.car) + n(r.tgt)), nd: 3 },
    { k: "wopr", l: "WOPR", get: (r) => r.wopr, nd: 3 },
    { cat: "Volume" },
    { k: "fpts", l: "AFFL points", get: (r) => r.fpts, nd: 1 },
    { k: "opp", l: "Opportunities", get: (r) => r.opp != null ? +r.opp : n(r.tgt) + n(r.car) + n(r.att) },
    { k: "att", l: "Pass attempts", get: (r) => r.att },
    { k: "tgt", l: "Targets", get: (r) => r.tgt },
    { k: "car", l: "Carries", get: (r) => r.car },
    { cat: "Situational" },
    { k: "g", l: "Games", get: (r) => r.g },
    { k: "starts", l: "AFFL starts", get: (r) => r.starts },
    { k: "bid", l: "Auction $", get: (r) => r.bid, bid: true },
  ];

  async function renderCompare() {
    chips($("cmp-kind"), [["players", "Players"]], "players", () => {}, "sv-chip");
    chips($("cmp-pos"), POSITIONS.filter((p) => p !== "ALL").map((p) => [p, p]), state.cmp.pos, (v) => {
      state.cmp.pos = v;
      renderCompare();
    }, "sv-chip");

    const ySel = $("cmp-year");
    const yCur = cmpSeason();
    if (ySel && !ySel.dataset.ready) {
      ySel.innerHTML = META.seasons.map((y) => `<option value="${y}">${y}</option>`).join("");
      ySel.dataset.ready = "1";
      ySel.onchange = () => { state.cmp.season = +ySel.value; renderCompare(); };
    }
    if (ySel) ySel.value = String(yCur);

    let pool = [];
    try { pool = await scopeRows(yCur); } catch (e) { pool = []; }
    const posPool = pool.filter((r) => r.pos === state.cmp.pos);

    if (!state.cmp.pids.length) {
      ["a", "b"].forEach((side) => {
        const r = state.h2h[side];
        if (r && r.pid && !state.cmp.pids.includes(r.pid)) state.cmp.pids.push(r.pid);
      });
    }

    const picked = state.cmp.pids.map((pid) => pool.find((r) => r.pid === pid)).filter(Boolean);
    const cards = $("cmp-cards");
    const addSlot = picked.length < 3
      ? `<div class="sv-cmp-card add">
           <input id="cmp-add" placeholder="+ Add ${state.cmp.pos}" autocomplete="off">
           <ul class="sv-suggest" id="cmp-add-list" hidden></ul>
         </div>` : "";
    cards.innerHTML = picked.map((r) => `<div class="sv-cmp-card">
        ${sqHTML(r.team, r.fr)}
        <div class="nm">${esc(displayName(r))}</div>
        <div class="sub">${esc(r.pos || "")} · ${esc(r.team || "FA")}</div>
        <button type="button" class="sv-cmp-x" data-pid="${esc(r.pid)}">Remove</button>
      </div>`).join("") + addSlot;
    cards.querySelectorAll(".sv-cmp-x").forEach((b) => {
      b.onclick = () => {
        state.cmp.pids = state.cmp.pids.filter((p) => p !== b.dataset.pid);
        renderCompare();
      };
    });
    const add = $("cmp-add"), list = $("cmp-add-list");
    if (add) {
      add.oninput = () => {
        const q = add.value.trim().toLowerCase();
        if (q.length < 2) { list.hidden = true; return; }
        const hits = posPool.filter((r) =>
          String(r.name || "").toLowerCase().includes(q) && !state.cmp.pids.includes(r.pid)
        ).slice(0, 8);
        list.hidden = !hits.length;
        list.innerHTML = hits.map((r) =>
          `<li data-pid="${esc(r.pid)}">${esc(displayName(r))} · ${esc(r.team || "")}</li>`
        ).join("");
        list.querySelectorAll("li").forEach((li) => {
          li.onclick = () => {
            if (state.cmp.pids.length < 3) state.cmp.pids.push(li.dataset.pid);
            renderCompare();
          };
        });
      };
    }

    const tape = $("cmp-tape");
    if (!picked.length) {
      tape.innerHTML = `<div class="sv-empty">Add up to three players. Team identity is the color square — no unconstrained logos.</div>`;
      $("cmp-sim").innerHTML = `<div class="sv-empty">Pick a player to see similar profiles in this season.</div>`;
      return;
    }

    const nCol = picked.length + 1;
    let html = `<table class="sv-tape"><tbody>`;
    TAPE.forEach((row) => {
      if (row.cat) {
        html += `<tr><td class="cat" colspan="${nCol}">${row.cat}</td></tr>`;
        return;
      }
      const vals = picked.map((r) => row.get(r));
      const poolVals = posPool.map((r) => row.get(r));
      const best = vals.reduce((m, v) => (v == null ? m : (m == null || v > m ? v : m)), null);
      html += `<tr><td>${esc(row.l)}</td>`;
      picked.forEach((r, i) => {
        const v = vals[i];
        const pctile = percentile(poolVals, v);
        const lead = v != null && v === best && vals.filter((x) => x === best).length === 1;
        const shown = v == null ? "—" : (row.bid ? fmtBid(v) : fmt(v, { nd: row.nd != null ? row.nd : 0 }));
        html += `<td>
          <div class="${lead ? "lead" : ""}">${shown}${lead ? `<span class="lead-lab">Leads ${pctile != null ? pctile + "%" : ""}</span>` : ""}</div>
          ${pctile == null ? "" : `<div class="sv-pbar"><i style="width:${pctile}%"></i></div>`}
        </td>`;
      });
      html += `</tr>`;
    });
    html += `</tbody></table>`;
    tape.innerHTML = html;

    const focus = picked[0];
    $("cmp-sim-title").textContent = `Players like ${displayName(focus)}`;
    const keys = TAPE.filter((r) => r.get);
    const pickedSet = new Set(picked.map((r) => r.pid));
    const sim = posPool.filter((r) => !pickedSet.has(r.pid)).map((r) => {
      let acc = 0, used = 0;
      keys.forEach((m) => {
        const a = m.get(focus), b = m.get(r);
        if (a == null || b == null) return;
        const xs = posPool.map((x) => m.get(x)).filter((v) => v != null);
        const mu = mean(xs), sd = Math.sqrt(mean(xs.map((v) => (v - mu) ** 2)) || 1);
        if (!sd) return;
        acc += ((a - b) / sd) ** 2;
        used += 1;
      });
      return { r, dist: used ? Math.sqrt(acc / used) : Infinity };
    }).filter((x) => x.dist !== Infinity).sort((a, b) => a.dist - b.dist).slice(0, 6);
    $("cmp-sim").innerHTML = sim.length
      ? sim.map((s) => {
        const score = Math.max(0, Math.round(100 * (1 - s.dist / 4)));
        return `<div class="sv-row">
          ${sqHTML(s.r.team, s.r.fr)}
          <div class="sv-who"><div class="nm">${esc(displayName(s.r))}</div>
            <div class="sub">${esc(s.r.pos)} · ${esc(s.r.team || "FA")}</div></div>
          <span class="sv-val ink">${score}</span>
        </div>`;
      }).join("")
      : `<div class="sv-empty">No similar profiles in this stored season.</div>`;
  }

  function renderExplore() {
    const rows = visible();
    $("plot-count").textContent = `${rows.length} players`;
    if (isAll()) {
      $("plot-sub").textContent = state.view === "affl"
        ? "Cumulative · career 2014–2025 · only players an AFFL manager actually started · non-PPR"
        : "Cumulative · career 2014–2025 · every NFL skill player · AFFL scoring, non-PPR";
    } else {
      $("plot-sub").textContent = state.view === "affl"
        ? `${state.season} · only players an AFFL manager actually started · non-PPR`
        : `${state.season} · every NFL skill player · AFFL scoring, non-PPR`;
    }
    renderQueryChrome();
    renderChart(rows);
    renderTable(rows);
    const base = "Hover any dot for the player. AFFL starts count weeks a manager put that player in a starting slot. Dots are franchise-colored. Auction $ never fills snake years as $0.";
    if (isAll()) {
      $("sv-note").textContent = base +
        " 2014–2017 weekly lineups are incomplete (ESPN no longer serves them); those seasons keep only team-weeks that reconcile to the official score, so AFFL starts read low. NFL data is complete for every season. Auction $ sums auction-year bids; snake drafts are unavailable, never $0.";
    } else {
      const cov = (META.lineupCoverage || {})[String(state.season)];
      if (cov != null && cov < 100) {
        $("sv-note").textContent = base +
          ` ESPN no longer serves ${state.season} weekly lineups, so this season is reconstructed:` +
          ` ${cov}% of team-weeks are proven against the official score and shown here.` +
          " The rest are left out rather than guessed, so AFFL starts read low for this season." +
          " NFL data is complete for every season.";
      } else {
        $("sv-note").textContent = base;
      }
    }
  }

  function renderAll() {
    renderChips();
    renderHome();
    renderPlayers();
    renderFantasy();
    if (state.page === "explore") renderExplore();
    if (state.page === "leaderboards") renderLeaderboards();
    if (state.page === "compare") renderCompare();
    if (state.page !== "explore") {
      const rows = visible();
      if ($("plot-count")) $("plot-count").textContent = `${rows.length} players`;
    }
  }

  function parseYearParam(raw) {
    if (raw == null || raw === "" || String(raw).toLowerCase() === "all") return ALL;
    const y = +raw;
    if (META.seasons.includes(y)) return y;
    return ALL;
  }

  function parsePage() {
    const h = String(location.hash || "").replace("#", "").toLowerCase();
    if (PAGES.includes(h)) return h;
    const qs = new URLSearchParams(location.search).get("view");
    if (PAGES.includes(qs)) return qs;
    return "home";
  }

  function bindChrome() {
    document.querySelectorAll(".sv-subnav button").forEach((b) => {
      b.addEventListener("click", () => { setPage(b.dataset.page); });
    });
    document.querySelectorAll("[data-go]").forEach((b) => {
      b.addEventListener("click", () => {
        if (b.dataset.board) state.lb.board = b.dataset.board;
        setPage(b.dataset.go);
      });
    });
    const jump = (q) => {
      state.q = (q || "").trim();
      if ($("pl-search")) $("pl-search").value = state.q;
      setPage("players");
      renderAll();
    };
    ["sv-nav-search", "home-search"].forEach((id) => {
      const el = $(id);
      if (!el) return;
      el.addEventListener("keydown", (e) => {
        if (e.key === "Enter") jump(el.value);
      });
    });
    if ($("pl-search")) {
      $("pl-search").addEventListener("input", () => {
        state.q = $("pl-search").value.trim();
        renderPlayers();
      });
    }
    if ($("fan-name")) $("fan-name").addEventListener("input", renderFantasy);
    if ($("btn-csv")) $("btn-csv").addEventListener("click", () => exportCSV(visible()));
    if ($("btn-chart")) $("btn-chart").addEventListener("click", () => {
      $("sv-scatter").scrollIntoView({ behavior: "smooth", block: "center" });
    });
    if ($("lb-csv")) $("lb-csv").addEventListener("click", exportLeaderboard);
    if ($("lb-chart")) $("lb-chart").addEventListener("click", () => {
      const board = BOARDS[state.lb.board] || BOARDS.passing;
      if (board.chart) {
        state.x = board.chart.x;
        state.y = board.chart.y;
        if (board.chart.pos && board.chart.pos !== "ALL") state.pos = board.chart.pos;
        if (state.lb.season != null) {
          if (state.lb.season === ALL) applyScope("cum", ALL).then(() => setPage("explore"));
          else applyScope("season", state.lb.season).then(() => setPage("explore"));
          return;
        }
      }
      setPage("explore");
    });
    if ($("qb-reset")) {
      $("qb-reset").addEventListener("click", async () => {
        state.pos = "ALL";
        state.view = "all";
        state.franchise = "";
        state.minOpp = 25;
        state.sort = { key: "fpts", dir: -1 };
        state.top = 50;
        state.x = "opp";
        state.y = "fpts";
        state.color = "franchise";
        $("x-metric").value = state.x;
        $("y-metric").value = state.y;
        $("franchise").value = "";
        $("min-opp").value = "25";
        await applyScope("cum", ALL);
      });
    }
    window.addEventListener("hashchange", () => setPage(parsePage()));
  }

  /* ------------------------------------------------------------------- boot */

  try {
    if (A && A.boot) {
      try { await A.boot(); } catch (e) { /* slate can still fetch years/*.json */ }
    }
    LEAGUE = A && A.data ? A.data : null;
    const [meta, bids] = await Promise.all([
      fetch(`${BASE}meta.json`).then((r) => r.json()),
      fetch(`${BASE}bids.json`).then((r) => r.ok ? r.json() : {}),
    ]);
    META = meta;
    BIDS = bids || {};
    const qs = new URLSearchParams(location.search);
    const wantSeason = qs.get("scope") === "season" || (qs.get("year") && String(qs.get("year")).toLowerCase() !== "all");
    if (wantSeason) {
      state.scope = "season";
      state.season = parseYearParam(qs.get("year") || qs.get("season"));
      if (state.season === ALL) state.season = META.seasons[META.seasons.length - 1];
    } else {
      state.scope = "cum";
      state.season = ALL;
    }
    stampScope();
    state.page = parsePage();
    await loadScope();
    renderSelects();
    bindChrome();
    setPage(state.page);
    renderAll();
  } catch (e) {
    document.querySelector(".frame").insertAdjacentHTML("beforeend",
      `<section class="card"><div class="sv-empty">Savant data failed to load: ${esc(e.message)}<br>
       Run <code>python3 export_savant.py</code> to build site/savant/.</div></section>`);
  }
})();
