/* AFFL Savant — every NFL skill player, filtered, plotted, hoverable.
 *
 * Data: site/savant/season_<year>.json, one file per season (~85KB), rows as
 * arrays with the key order in meta.json. AFFL scoring is non-PPR throughout;
 * receptions are volume and score nothing.
 *
 * AFFL context is keyed on franchise (member_id upstream), so a rename never
 * splits a franchise — Tittsburgh and Grand Teeton are one team, shown under
 * the current name.
 */
(async function () {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const BASE = "savant/";

  const POS_COLOR = { QB: "#00a2ff", RB: "#c8ff00", WR: "#ff6a00", TE: "#ffc400" };
  const POSITIONS = ["ALL", "QB", "RB", "WR", "TE"];

  /* metric key -> label + how to read it off a row */
  const METRICS = {
    opp:    { label: "Opportunities (tgt + car + att)", get: (r) => n(r.tgt) + n(r.car) + n(r.att) },
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
  };

  const MIN_OPP = [0, 25, 50, 100, 150, 200];

  const state = {
    season: null, pos: "ALL", view: "all", franchise: "",
    x: "opp", y: "fpts", minOpp: 25,
    sort: { key: "fpts", dir: -1 },
  };

  let META = null;
  let ROWS = [];
  let chart = null;
  const cache = new Map();

  function n(v) { return v == null ? 0 : +v; }
  function pct(v) { return v == null ? null : +v * 100; }

  function fmt(v, m) {
    if (v == null || Number.isNaN(v)) return "—";
    if (m && m.fmt === "pct") return v.toFixed(1) + "%";
    const nd = m && m.nd != null ? m.nd : 0;
    return (+v).toLocaleString(undefined, { minimumFractionDigits: nd, maximumFractionDigits: nd });
  }

  async function loadSeason(y) {
    if (cache.has(y)) return cache.get(y);
    const res = await fetch(`${BASE}season_${y}.json`);
    if (!res.ok) throw new Error(`season ${y} unavailable`);
    const raw = await res.json();
    const cols = META.cols;
    const rows = raw.map((arr) => {
      const o = {};
      cols.forEach((c, i) => { o[c] = arr[i]; });
      return o;
    });
    cache.set(y, rows);
    return rows;
  }

  /* ---------------------------------------------------------------- filters */

  function visible() {
    return ROWS.filter((r) => {
      if (state.pos !== "ALL" && r.pos !== state.pos) return false;
      if (state.view === "affl" && !r.starts) return false;
      if (state.franchise && r.fr !== state.franchise) return false;
      const opp = n(r.tgt) + n(r.car) + n(r.att);
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

  function renderChips() {
    chips($("season-picker"), META.seasons.map((y) => [y, y]), state.season, async (v) => {
      state.season = +v;
      ROWS = await loadSeason(state.season);
      renderAll();
    });
    chips($("pos-picker"), POSITIONS.map((p) => [p, p]), state.pos, (v) => {
      state.pos = v; renderAll();
    });
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

    $("franchise").innerHTML = `<option value="">All franchises</option>` +
      META.franchises.map((f) => `<option value="${f}">${f}</option>`).join("");
    $("franchise").value = state.franchise;
    $("franchise").onchange = () => { state.franchise = $("franchise").value; renderAll(); };

    $("min-opp").innerHTML = MIN_OPP
      .map((v) => `<option value="${v}">${v === 0 ? "No minimum" : v + "+"}</option>`).join("");
    $("min-opp").value = String(state.minOpp);
    $("min-opp").onchange = () => { state.minOpp = +$("min-opp").value; renderAll(); };
  }

  /* ------------------------------------------------------------------ chart */

  function renderChart(rows) {
    const mx = METRICS[state.x], my = METRICS[state.y];
    const byPos = {};
    rows.forEach((r) => {
      const x = mx.get(r), y = my.get(r);
      if (x == null || y == null || Number.isNaN(x) || Number.isNaN(y)) return;
      (byPos[r.pos] = byPos[r.pos] || []).push({ x, y, r });
    });

    const datasets = Object.keys(byPos).sort().map((p) => ({
      label: p,
      data: byPos[p],
      backgroundColor: (POS_COLOR[p] || "#7d8aa0") + "cc",
      borderColor: POS_COLOR[p] || "#7d8aa0",
      borderWidth: 1,
      pointRadius: 4,
      pointHoverRadius: 7,
    }));

    const cfg = {
      type: "scatter",
      data: { datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: "nearest", intersect: true },
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              title: (items) => {
                const r = items[0].raw.r;
                return `${r.name} · ${r.pos} · ${r.team || "FA"}`;
              },
              label: (item) => {
                const r = item.raw.r;
                const out = [
                  `${mx.label}: ${fmt(item.raw.x, mx)}`,
                  `${my.label}: ${fmt(item.raw.y, my)}`,
                  `${r.g} games · ${fmt(r.fpts, { nd: 1 })} AFFL pts`,
                ];
                if (r.starts) out.push(`Started ${r.starts}× by ${r.fr}`);
                else out.push("Never started in the AFFL this season");
                return out;
              },
            },
          },
        },
        scales: {
          x: { title: { display: true, text: mx.label }, grid: { color: "#1c2536" } },
          y: { title: { display: true, text: my.label }, grid: { color: "#1c2536" } },
        },
      },
    };

    if (chart) { chart.destroy(); chart = null; }
    chart = new Chart($("sv-scatter").getContext("2d"), cfg);

    $("sv-legend").innerHTML = Object.keys(byPos).sort().map((p) =>
      `<span class="sv-key"><span class="sv-dot" style="background:${POS_COLOR[p] || "#7d8aa0"}"></span>${p} (${byPos[p].length})</span>`
    ).join("");
  }

  /* ------------------------------------------------------------------ table */

  const TCOLS = [
    ["name", "Player"], ["pos", "Pos"], ["team", "Team"], ["g", "G"],
    ["opp", "Opp"], ["tgt", "Tgt"], ["car", "Car"], ["att", "Att"],
    ["fpts", "FPts"], ["fppg", "FP/G"], ["epa", "EPA"],
    ["starts", "AFFL starts"], ["fr", "Franchise"],
  ];

  function cell(r, key) {
    if (key === "opp") return n(r.tgt) + n(r.car) + n(r.att);
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
      <td>${esc(r.name)}</td>
      <td><span class="sv-pos">${esc(r.pos)}</span></td>
      <td>${esc(r.team || "—")}</td>
      <td>${r.g}</td>
      <td>${n(r.tgt) + n(r.car) + n(r.att)}</td>
      <td>${r.tgt}</td>
      <td>${r.car}</td>
      <td>${r.att}</td>
      <td>${fmt(r.fpts, { nd: 1 })}</td>
      <td>${fmt(r.fppg, { nd: 2 })}</td>
      <td>${fmt(r.epa, { nd: 1 })}</td>
      <td>${r.starts || "—"}</td>
      <td class="sv-fr">${esc(r.fr || "—")}</td>
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
    $("plot-sub").textContent = state.view === "affl"
      ? `${state.season} · only players an AFFL manager actually started · non-PPR`
      : `${state.season} · every NFL skill player · AFFL scoring, non-PPR`;

    renderChart(rows);
    renderTable(rows);

    const pre2018 = state.season < 2018;
    $("sv-note").textContent = pre2018
      ? "Weekly AFFL lineups do not exist before 2018, so “AFFL starters only” and the starts column are empty for this season. NFL data is complete."
      : "Hover any dot for the player. AFFL starts count weeks a manager put that player in a starting slot.";
  }

  /* ------------------------------------------------------------------- boot */

  try {
    if (window.A && A.chartDefaults) A.chartDefaults(Chart);
    META = await (await fetch(`${BASE}meta.json`)).json();
    const qs = new URLSearchParams(location.search);
    const want = +qs.get("season");
    state.season = META.seasons.includes(want) ? want : META.seasons[META.seasons.length - 1];
    ROWS = await loadSeason(state.season);
    renderSelects();
    renderAll();
  } catch (e) {
    document.querySelector(".frame").insertAdjacentHTML("beforeend",
      `<section class="card"><div class="sv-empty">Savant data failed to load: ${esc(e.message)}<br>
       Run <code>python3 export_savant.py</code> to build site/savant/.</div></section>`);
  }
})();
