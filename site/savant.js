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
 */
(async function () {
  "use strict";

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

  function currentSquads() {
    if (window.AFFL && A.CURRENT_2026 && A.CURRENT_2026.length) return A.CURRENT_2026;
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
  };

  let META = null;
  let BIDS = {};
  let ROWS = [];
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
    if (window.AFFL && A.unresolvedPlayerName) return A.unresolvedPlayerName(name);
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
          };
          SUM_COLS.forEach((c) => { o[c] = 0; });
          SHARE_NULL.forEach((c) => { o[c] = null; });
          by.set(pid, o);
        }
        SUM_COLS.forEach((c) => { o[c] = n(o[c]) + n(r[c]); });
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
      o.fr = pickHomeFranchise(o._byFr);
      o.bid = careerBid(o.pid);
      delete o._byFr;
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
    el.innerHTML = items.map(([v, l]) =>
      `<button type="button" class="season-chip${String(v) === String(current) ? " on" : ""}" data-v="${v}">${l}</button>`
    ).join("");
    el.querySelectorAll(".season-chip").forEach((b) => {
      b.addEventListener("click", () => onPick(b.dataset.v));
    });
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

  function renderChips() {
    chips($("scope-picker"), [["cum", "Cumulative"], ["season", "Season"]], state.scope, async (v) => {
      state.scope = v;
      if (v === "season") {
        if (state.season === ALL || state.season == null) {
          state.season = META.seasons[META.seasons.length - 1];
        }
        showYearRow(true);
      } else {
        state.season = ALL;
        showYearRow(false);
      }
      stampScope();
      await loadScope();
      renderAll();
    });
    showYearRow(state.scope === "season");
    const seasons = META.seasons.map((y) => [y, y]);
    chips($("season-picker"), seasons, state.season, async (v) => {
      state.scope = "season";
      state.season = +v;
      showYearRow(true);
      stampScope();
      await loadScope();
      renderAll();
    });
    const squadEl = $("squad-picker");
    if (squadEl) {
      const items = [["", "All squads"]].concat(currentSquads().map((t) => [t.name, t.name]));
      chips(squadEl, items, state.franchise, (v) => {
        state.franchise = v;
        renderAll();
      });
    }
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

    const datasets = keys.map((k) => {
      const col = groupColor(k);
      const pts = by[k];
      return {
        label: groupLabel(k, pts.length),
        data: pts.map((p) => ({ x: p.x, y: p.y })),
        players: pts.map((p) => p.player),
        backgroundColor: col + "cc",
        borderColor: col,
        borderWidth: 1,
        pointRadius: 5,
        pointHoverRadius: 8,
        pointHitRadius: 14,
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
        `<span class="sv-tip-mut">${esc(mx.label)}: ${esc(fmt(evt && evt.x, mx) !== "—" ? fmt((ds.data[hit.index] || {}).x, mx) : fmt((ds.data[hit.index] || {}).x, mx))}</span>`,
        `<span class="sv-tip-mut">${esc(my.label)}: ${esc(fmt((ds.data[hit.index] || {}).y, my))}</span>`,
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
    chart = new Chart($("sv-scatter").getContext("2d"), cfg);
    const canvas = $("sv-scatter");
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
    renderChips();
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

    renderChart(rows);
    renderTable(rows);

    const base = "Hover any dot for the player. AFFL starts count weeks a manager put that player in a starting slot.";
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
    if (window.A && A.chartDefaults) A.chartDefaults(Chart);
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
    await loadScope();
    renderSelects();
    renderAll();
  } catch (e) {
    document.querySelector(".frame").insertAdjacentHTML("beforeend",
      `<section class="card"><div class="sv-empty">Savant data failed to load: ${esc(e.message)}<br>
       Run <code>python3 export_savant.py</code> to build site/savant/.</div></section>`);
  }
})();
