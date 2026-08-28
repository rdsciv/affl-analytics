/* AFFL Savant — every NFL skill player, filtered, plotted, hoverable.
 *
 * Data: site/savant/season_<year>.json, one file per season (~85KB), rows as
 * arrays with the key order in meta.json. AFFL scoring is non-PPR throughout;
 * receptions are volume and score nothing. Auction $ lives in savant/bids.json
 * keyed by GSIS pid (same as season row.pid). Years 2016–2025 only; snake
 * drafts are omitted, never coerced to $0.
 *
 * AFFL context is keyed on franchise (member_id upstream), so a rename never
 * splits a franchise — Tittsburgh and Grand Teeton are one team, shown under
 * the current name.
 *
 * CHI-140 landing: identity marks (face / NFL abbrev / AFFL abbrev), one
 * compact control row, Season All|year and Team All|name. Franchise color
 * is a toggle, off on arrival.
 */
(async function () {
  "use strict";

  const A = window.AFFL || {};
  const $ = (id) => document.getElementById(id);
  const BASE = "savant/";
  const ALL = "all";

  const POS_COLOR = { QB: "#00a2ff", RB: "#c8ff00", WR: "#ff6a00", TE: "#ffc400" };
  const POSITIONS = ["ALL", "QB", "RB", "WR", "TE"];
  const MUTED = "#7d8aa0";

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

  const FR_ABBREV = {
    "Charleston Chewbacca": "CHW",
    "Chula Vista Chupacabras": "CVC",
    "DC Mighty Cucks": "DMC",
    "Fairview Fat Cats": "FFC",
    "Goleta Gringos": "GOL",
    "Grand Teeton Feelers": "GTF",
    "Honolulu Horndogs": "HNL",
    "L.O.B. Thunder": "LOB",
    "Muck City Mad Dawgs": "MCK",
    "Pasco Pounders": "PSC",
    "Patagonia Pipers": "PIP",
    "Pawtucket Patriots": "PWT",
    "Poulsbo Pollywogs": "PLB",
    "San Diego Shadowcöcks": "SDS",
    "Squaw Valley Skinners": "SVS",
    "Tijuana Sanchitos": "TIJ",
    "Westeros Warlords": "WAR",
    "Winston-Salem Wake Snakes": "WSS",
    "Central Oregon Gabagooners": "GAB",
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

  function afflAbbrev(fr) {
    if (!fr) return "";
    if (FR_ABBREV[fr]) return FR_ABBREV[fr];
    const parts = String(fr).split(/\s+/).filter(Boolean);
    return parts.map((p) => p[0]).join("").slice(0, 3).toUpperCase();
  }

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
    season: ALL, pos: "ALL", view: "all", franchise: "",
    color: "identity",
    x: "opp", y: "fpts", minOpp: 25,
    sort: { key: "fpts", dir: -1 },
  };

  let META = null;
  let BIDS = {};
  let ROWS = [];
  let chart = null;
  let ESPN_BY_NAME = new Map();
  const cache = new Map();

  function n(v) { return v == null ? 0 : +v; }
  function pct(v) { return v == null ? null : +v * 100; }

  function isAll() { return state.season === ALL || state.season == null; }

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
    if (A.unresolvedPlayerName) return A.unresolvedPlayerName(name);
    return name == null || name === "" || /^Player \d+$/.test(String(name).trim());
  }
  function displayName(r) {
    const name = r && r.name;
    if (unresolvedName(name)) return "unavailable";
    return name;
  }

  function frColor(fr) {
    if (!fr) return MUTED;
    return FR_COLOR[fr] || MUTED;
  }

  function espnIdFor(r) {
    if (!r || !ESPN_BY_NAME.size) return "";
    return ESPN_BY_NAME.get((r.name || "") + "|" + (r.pos || "")) || "";
  }

  function identityKind(r) {
    if (espnIdFor(r)) return "face";
    if (r && r.team) return "nfl";
    return "affl";
  }

  function markHTML(r) {
    const espn = espnIdFor(r);
    if (espn) {
      const src = "https://a.espncdn.com/i/headshots/nfl/players/full/" + espn + ".png";
      const fb = (r.team ? r.team : (afflAbbrev(currentFr(r.fr)) || "?"));
      return `<img class="sv-mark-face" src="${src}" alt="" width="28" height="28" loading="lazy" data-fb="${esc(fb)}"
        onerror="this.outerHTML='<span class=&quot;sv-mark-abbr&quot;>'+this.getAttribute('data-fb')+'</span>'">`;
    }
    if (r && r.team) return `<span class="sv-mark-abbr">${esc(r.team)}</span>`;
    return `<span class="sv-mark-abbr">${esc(afflAbbrev(currentFr(r && r.fr)) || "?")}</span>`;
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

  /* CHI-139 — "Started Nx by {fr}" is starter weeks THAT franchise
   * actually started him. Career starts stay on r.starts. Missing
   * stint stays unavailable, never 0, never hung on pickHomeFranchise. */
  function hoverStartedLine(r, fr) {
    if (isAll()) {
      const n = r.frStarts;
      if (n == null || n === "") return "";
      if (!(+n > 0)) return "";
      return "Started " + (+n) + "\u00d7" + (fr ? " by " + fr : "");
    }
    if (r.starts) return "Started " + r.starts + "\u00d7" + (fr ? " by " + fr : "");
    return "Never started in the AFFL this season";
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
          const fr = currentFr(r.fr);
          const bag = o._byFr[fr] || (o._byFr[fr] = { fpts: 0, starts: 0 });
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
      /* CHI-139 — starts by the home franchise, not career starts. */
      o.frStarts = (o.fr && o._byFr[o.fr] && o._byFr[o.fr].starts != null)
        ? o._byFr[o.fr].starts
        : null;
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

  /* ---------------------------------------------------------------- filters */

  function visible() {
    return ROWS.filter((r) => {
      if (state.pos !== "ALL" && r.pos !== state.pos) return false;
      if (state.view === "affl" && !r.starts) return false;
      if (state.franchise && currentFr(r.fr) !== state.franchise) return false;
      const opp = r.opp != null ? +r.opp : n(r.tgt) + n(r.car) + n(r.att);
      if (opp < state.minOpp) return false;
      return true;
    });
  }

  /* ------------------------------------------------------------------ chips */

  function chips(el, items, current, onPick) {
    if (!el) return;
    el.innerHTML = items.map(([v, l]) =>
      `<button type="button" class="season-chip${String(v) === String(current) ? " on" : ""}" data-v="${v}">${l}</button>`
    ).join("");
    el.querySelectorAll(".season-chip").forEach((b) => {
      b.addEventListener("click", () => onPick(b.dataset.v));
    });
  }

  function fillSelect(el, items, current, onPick) {
    if (!el) return;
    el.innerHTML = items.map(([v, l]) =>
      `<option value="${esc(v)}"${String(v) === String(current) ? " selected" : ""}>${l}</option>`
    ).join("");
    el.onchange = () => onPick(el.value);
  }

  function stampScope() {
    try {
      const u = new URL(location.href);
      if (!isAll()) {
        u.searchParams.set("year", String(state.season));
        u.searchParams.delete("scope");
        u.searchParams.delete("season");
      } else {
        u.searchParams.delete("scope");
        u.searchParams.delete("year");
        u.searchParams.delete("season");
      }
      if (state.franchise) u.searchParams.set("team", state.franchise);
      else u.searchParams.delete("team");
      history.replaceState(null, "", u.pathname.split("/").pop() + u.search + u.hash);
    } catch (e) { /* ignore */ }
  }

  function setFranchise(v) {
    state.franchise = v || "";
    stampScope();
    renderAll();
  }

  function yearsForFranchise() {
    if (!state.franchise) return (META.seasons || []).slice();
    const t = currentSquads().find((x) => x.name === state.franchise);
    if (!t || !A.squadYears) return (META.seasons || []).slice();
    return A.squadYears(t.owner) || [];
  }

  function teamsForSeason() {
    const all = currentSquads();
    if (isAll()) return all;
    if (A.squadsForSeason) {
      const allow = new Set(A.squadsForSeason(state.season).map((f) => A.canon(f.owner)));
      return all.filter((t) => allow.has(A.canon(t.owner)));
    }
    return all.filter((t) => A.franchisePlayedSeason && A.franchisePlayedSeason(t.owner, state.season));
  }

  function renderControls() {
    if (!isAll() && state.franchise) {
      const t = currentSquads().find((x) => x.name === state.franchise);
      if (t && A.franchisePlayedSeason && !A.franchisePlayedSeason(t.owner, state.season)) {
        state.franchise = "";
      }
    }
    let ylist = yearsForFranchise();
    if (state.franchise && !ylist.length) {
      state.season = ALL;
    } else if (!isAll() && ylist.length && ylist.indexOf(state.season) < 0 && ylist.indexOf(+state.season) < 0) {
      state.season = ALL;
    }
    const seasons = [[ALL, "All"]].concat(ylist.slice().sort((a, b) => b - a).map((y) => [y, String(y)]));
    fillSelect($("season-picker"), seasons, state.season, async (v) => {
      state.season = v === ALL || String(v).toLowerCase() === "all" ? ALL : +v;
      stampScope();
      await loadScope();
      renderAll();
    });

    const shown = teamsForSeason();
    const teams = [["", "All"]].concat(shown.map((t) => [t.name, t.name]));
    fillSelect($("team-picker"), teams, state.franchise, setFranchise);

    fillSelect($("pos-select"), POSITIONS.map((p) => [p, p === "ALL" ? "All" : p]), state.pos, (v) => {
      state.pos = v; renderAll();
    });

    fillSelect($("color-select"), [
      ["identity", "Identity"],
      ["franchise", "Franchise color"],
    ], state.color, (v) => {
      state.color = v; renderAll();
    });

    const chipEl = $("team-chips");
    if (chipEl) {
      const items = [["", "All"]].concat(shown.map((t) => [t.name, t.name]));
      chips(chipEl, items, state.franchise, setFranchise);
    }
    chips($("view-picker"), [["all", "All NFL"], ["affl", "AFFL starters only"]], state.view, (v) => {
      state.view = v; renderAll();
    });
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

    $("min-opp").innerHTML = MIN_OPP
      .map((v) => `<option value="${v}">${v === 0 ? "No minimum" : v + "+"}</option>`).join("");
    $("min-opp").value = String(state.minOpp);
    $("min-opp").onchange = () => { state.minOpp = +$("min-opp").value; renderAll(); };
  }

  /* ------------------------------------------------------------------ chart */

  function groupKey(r) {
    if (state.color === "position") return r.pos || "?";
    if (state.color === "identity") return "identity";
    return currentFr(r.fr);
  }

  function groupColor(key) {
    if (state.color === "identity") return MUTED;
    if (state.color === "position") return POS_COLOR[key] || MUTED;
    return key ? frColor(key) : MUTED;
  }

  function groupLabel(key, count) {
    if (state.color === "identity") return `Players (${count})`;
    if (state.color === "position") return `${key || "?"} (${count})`;
    if (!key) return `No AFFL points (${count})`;
    return `${key} (${count})`;
  }

  function clearMarks() {
    const layer = $("sv-marks");
    if (layer) layer.innerHTML = "";
  }

  function paintMarks() {
    const layer = $("sv-marks");
    if (!layer || !chart) return;
    layer.innerHTML = "";
    if (state.color !== "identity") return;
    const canvas = $("sv-scatter");
    if (!canvas) return;
    chart.data.datasets.forEach((ds, di) => {
      const meta = chart.getDatasetMeta(di);
      if (!meta || !meta.data) return;
      const players = ds.players || [];
      meta.data.forEach((pt, i) => {
        if (!pt || pt.skip) return;
        const r = players[i];
        if (!r) return;
        const el = document.createElement("div");
        el.className = "sv-mark";
        el.dataset.kind = identityKind(r);
        el.style.left = pt.x + "px";
        el.style.top = pt.y + "px";
        el.innerHTML = markHTML(r);
        layer.appendChild(el);
      });
    });
  }

  function renderChart(rows) {
    const mx = METRICS[state.x], my = METRICS[state.y];
    const by = {};
    rows.forEach((r) => {
      const x = mx.get(r), y = my.get(r);
      if (x == null || y == null || Number.isNaN(x) || Number.isNaN(y)) return;
      const k = groupKey(r);
      (by[k] = by[k] || []).push({ x, y, player: r });
    });

    const keys = Object.keys(by).sort((a, b) => {
      if (!a) return 1;
      if (!b) return -1;
      return a.localeCompare(b);
    });

    const identity = state.color === "identity";
    const datasets = keys.map((k) => {
      const col = groupColor(k);
      const pts = by[k];
      return {
        label: groupLabel(k, pts.length),
        data: pts.map((p) => ({ x: p.x, y: p.y })),
        players: pts.map((p) => p.player),
        backgroundColor: identity ? "rgba(180,190,210,0.12)" : col + "cc",
        borderColor: identity ? "rgba(180,190,210,0.28)" : col,
        borderWidth: identity ? 0 : 1,
        pointRadius: identity ? 9 : 5,
        pointHoverRadius: identity ? 11 : 8,
        pointHitRadius: identity ? 14 : 14,
      };
    });

    function playerAt(ds, idx) {
      if (!ds || idx == null) return null;
      const bag = ds.players || [];
      return bag[idx] || null;
    }

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
      const r = playerAt(ds, hit.index);
      if (!r) { hideTip(); return; }
      const fr = currentFr(r.fr);
      const lines = [
        `<b>${esc(displayName(r))}</b> · ${esc(r.pos || "—")} · ${esc(r.team || "FA")}`,
        `<span class="sv-tip-mut">${esc(mx.label)}: ${esc(fmt((ds.data[hit.index] || {}).x, mx))}</span>`,
        `<span class="sv-tip-mut">${esc(my.label)}: ${esc(fmt((ds.data[hit.index] || {}).y, my))}</span>`,
        `<span class="sv-tip-mut">${r.g == null ? "—" : r.g} games · ${esc(fmt(r.fpts, { nd: 1 }))} AFFL pts` +
          (isAll() && r.starts ? ` · ${esc(String(r.starts))} AFFL starts` : "") + `</span>`,
        `<span class="sv-tip-mut">${fr ? ("Franchise: " + esc(fr)) : "No AFFL points"}</span>`,
        `<span class="sv-tip-mut">Auction $: ${esc(fmtBid(r.bid))}</span>`,
      ];
      const started = hoverStartedLine(r, fr);
      if (started) lines.push(`<span class="sv-tip-mut">${esc(started)}</span>`);
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

    const cfg = {
      type: "scatter",
      data: { datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        events: ["mousemove", "mouseout", "click", "touchstart", "touchmove"],
        interaction: { mode: "nearest", intersect: true, axis: "xy" },
        onHover: (evt, els) => { showTip(evt, els); },
        onResize: () => { requestAnimationFrame(paintMarks); },
        animation: {
          onComplete: () => { paintMarks(); },
        },
        plugins: {
          legend: { display: false },
          tooltip: { enabled: false },
        },
        scales: {
          x: { title: { display: true, text: mx.label }, grid: { color: "#1c2536" } },
          y: { title: { display: true, text: my.label }, grid: { color: "#1c2536" } },
        },
      },
    };

    if (chart) { chart.destroy(); chart = null; }
    hideTip();
    clearMarks();
    chart = new Chart($("sv-scatter").getContext("2d"), cfg);
    const canvas = $("sv-scatter");
    canvas.onmouseleave = hideTip;
    requestAnimationFrame(paintMarks);

    if (identity) {
      $("sv-legend").innerHTML = `<span class="sv-key">Identity marks · face if we have one, else NFL abbrev, else AFFL abbrev</span>`;
    } else {
      $("sv-legend").innerHTML = keys.map((k) =>
        `<span class="sv-key"><span class="sv-dot" style="background:${groupColor(k)}"></span>${esc(groupLabel(k, by[k].length))}</span>`
      ).join("");
    }
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

    const sorted = rows.slice().sort((a, b) => {
      const av = cell(a, state.sort.key), bv = cell(b, state.sort.key);
      if (typeof av === "string" || typeof bv === "string") {
        return String(av || "").localeCompare(String(bv || "")) * -state.sort.dir;
      }
      return ((bv == null ? -Infinity : bv) - (av == null ? -Infinity : av)) * (state.sort.dir < 0 ? 1 : -1);
    }).slice(0, 250);

    if (!sorted.length) {
      $("sv-body").innerHTML = `<tr><td class="sv-empty" colspan="${TCOLS.length}">No players match these filters.</td></tr>`;
      return;
    }

    $("sv-body").innerHTML = sorted.map((r) => `<tr>
      <td>${esc(displayName(r))}</td>
      <td><span class="sv-pos">${esc(r.pos)}</span></td>
      <td>${esc(r.team || "—")}</td>
      <td>${r.g == null ? "—" : r.g}</td>
      <td>${cell(r, "opp")}</td>
      <td>${r.tgt == null ? "—" : r.tgt}</td>
      <td>${r.car == null ? "—" : r.car}</td>
      <td>${r.att == null ? "—" : r.att}</td>
      <td>${fmt(r.fpts, { nd: 1 })}</td>
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

  /* -------------------------------------------------------------------- all */

  function renderAll() {
    renderControls();
    const rows = visible();
    $("plot-count").textContent = `${rows.length} players`;
    if (isAll()) {
      $("plot-sub").textContent = state.view === "affl"
        ? "All · career 2014–2025 · only players an AFFL manager actually started · non-PPR"
        : "All · career 2014–2025 · every NFL skill player · AFFL scoring, non-PPR";
    } else {
      $("plot-sub").textContent = state.view === "affl"
        ? `${state.season} · only players an AFFL manager actually started · non-PPR`
        : `${state.season} · every NFL skill player · AFFL scoring, non-PPR`;
    }

    renderChart(rows);
    renderTable(rows);

    const base = "Hover any mark for the player. AFFL starts count weeks a manager put that player in a starting slot.";
    if (isAll()) {
      $("sv-note").textContent = base +
        " 2014–2017 weekly lineups are incomplete (ESPN no longer serves them); those seasons keep only team-weeks that reconcile to the official score, so AFFL starts read low. NFL data is complete for every season. Auction $ sums auction-year bids; snake drafts are unavailable, never $0.";
      return;
    }
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

  function parseYearParam(raw) {
    if (raw == null || raw === "" || String(raw).toLowerCase() === "all") return ALL;
    const y = +raw;
    if (META.seasons.includes(y)) return y;
    return ALL;
  }

  /* ------------------------------------------------------------------- boot */

  try {
    if (A.chartDefaults) A.chartDefaults(Chart);
    const [meta, bids, index] = await Promise.all([
      fetch(`${BASE}meta.json`).then((r) => r.json()),
      fetch(`${BASE}bids.json`).then((r) => r.ok ? r.json() : {}),
      fetch("player_index.json").then((r) => r.ok ? r.json() : {}),
    ]);
    META = meta;
    BIDS = bids || {};
    ESPN_BY_NAME = new Map();
    Object.keys(index || {}).forEach((id) => {
      const rec = index[id];
      if (!rec || !rec.name || !rec.pos) return;
      ESPN_BY_NAME.set(rec.name + "|" + rec.pos, String(id));
    });
    const qs = new URLSearchParams(location.search);
    const yearRaw = qs.get("year") || qs.get("season");
    const wantYear = yearRaw && String(yearRaw).toLowerCase() !== "all";
    if (wantYear) {
      state.season = parseYearParam(yearRaw);
      if (state.season === ALL) state.season = META.seasons[META.seasons.length - 1];
    } else {
      state.season = ALL;
    }
    const teamQ = qs.get("team") || qs.get("squad") || "";
    if (teamQ) {
      const byOwner = currentSquads().find((x) => x.owner === teamQ);
      if (byOwner) state.franchise = byOwner.name;
      else {
        const names = currentSquads().map((x) => x.name);
        const hit = names.find((n) => n === teamQ || n.toLowerCase() === teamQ.toLowerCase());
        state.franchise = hit || currentFr(teamQ) || "";
      }
    }
    stampScope();
    await loadScope();
    renderSelects();
    renderAll();
  } catch (e) {
    document.querySelector(".frame").insertAdjacentHTML("beforeend",
      `<section class="card"><div class="sv-empty">Savant data failed to load: ${esc(e.message)}<br>
       Run <code>python3 export_savant.py</code> to build site/savant/.</div></section>`);
  }
})();
