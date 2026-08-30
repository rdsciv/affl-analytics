/* CHI-114 — two grains, three panes. Never mix grains.
   playerSeasonXfp = season+player_id → FP / XFP on pane 1, FPOE on its own pane.
   playerWeekNfl   = season+week+gsis_id → yards / TDs / volume only.
   2013 skips BOTH season panels (no XFP/FPOE). Receptions are volume, not PPR.
   Do not alias pass_air_yards / rec_air_yards as yards. */
(function () {
  const A = window.AFFL;
  const C = (A && A.C) || {
    blue: "#00a2ff", blue2: "#47d4ff", ice: "#9fd8ff",
    orange: "#ff6a00", gold: "#ffc400", green: "#c8ff00",
    red: "#ff2d1a", mut: "#7d8aa0", ink: "#eef4ff", grid: "#1b243366",
  };

  const XFP_YEARS = [2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025];
  const WEEK_YEARS = [2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025];
  const SEASON_KEYS = ["fp", "xfp", "fpoe"];
  const XFP_PLOT_KEYS = ["fp", "xfp"];
  const FPOE_PLOT_KEYS = ["fpoe"];
  const WEEK_KEYS = ["pass_yards", "rush_yards", "targets", "receptions", "rush_td", "pass_td", "rec_td"];
  const YARD_KEYS = ["pass_yards", "rush_yards"];
  const VOL_KEYS = ["targets", "receptions", "rush_td", "pass_td", "rec_td"];

  const SEASON_COLORS = { fp: C.gold, xfp: C.blue, fpoe: C.green };
  const WEEK_COLORS = {
    pass_yards: C.blue,
    rush_yards: C.orange,
    targets: C.ice,
    receptions: C.blue2,
    rush_td: C.gold,
    pass_td: C.green,
    rec_td: C.red,
  };
  const WEEK_LABELS = {
    pass_yards: "pass yds",
    rush_yards: "rush yds",
    targets: "targets",
    receptions: "receptions",
    rush_td: "rush TD",
    pass_td: "pass TD",
    rec_td: "rec TD",
  };

  const charts = {};
  let ready = null;
  const seasonByPid = new Map();
  const weekByPid = new Map();
  const weekByYear = new Map();

  function num(v) {
    if (v == null || v === "") return null;
    const n = Number(v);
    return Number.isFinite(n) ? n : null;
  }

  function pidKey(v) {
    if (v == null || v === "") return "";
    return String(v);
  }

  function samePid(a, b) {
    return pidKey(a) !== "" && pidKey(a) === pidKey(b);
  }

  /* Season grain only. Reads playerSeasonXfp.rows — fp / xfp / fpoe. No week fields. */
  function takeSeasonXfp(bundle) {
    const obj = bundle && bundle.playerSeasonXfp;
    if (!obj || !obj.rows) return [];
    const out = [];
    for (let i = 0; i < obj.rows.length; i++) {
      const r = obj.rows[i];
      const season = num(r.season);
      if (season == null || season === 2013) continue; /* 2013 skips XFP */
      const meta = ((bundle && bundle.pmeta) || {})[r.player_id]
        || ((bundle && bundle.pmeta) || {})[String(r.player_id)];
      const pos = Array.isArray(meta) ? (meta[1] || "") : "";
      out.push({
        season: season,
        player_id: r.player_id,
        fp: num(r.fp),
        xfp: num(r.xfp),
        fpoe: num(r.fpoe),
        pos: pos,
      });
    }
    return out;
  }

  /* Week grain only. Reads playerWeekNfl.rows — yards / TDs / volume. No xfp/fpoe/fp. */
  function takeWeekNfl(bundle) {
    const obj = bundle && bundle.playerWeekNfl;
    if (!obj || !obj.rows) return [];
    const out = [];
    for (let i = 0; i < obj.rows.length; i++) {
      const r = obj.rows[i];
      out.push({
        season: num(r.season),
        week: num(r.week),
        gsis_id: r.gsis_id,
        player_id: r.player_id,
        targets: num(r.targets),
        receptions: num(r.receptions),
        rush_td: num(r.rush_td),
        pass_td: num(r.pass_td),
        rec_td: num(r.rec_td),
        pass_yards: num(r.pass_yards),
        rush_yards: num(r.rush_yards),
      });
    }
    return out;
  }

  async function ensure() {
    if (ready) return ready;
    ready = (async function () {
      const years = WEEK_YEARS.slice();
      const loads = years.map(function (y) {
        return A.loadYear(y).then(function (d) { return { y: y, d: d }; }).catch(function () {
          return { y: y, d: null };
        });
      });
      const bags = await Promise.all(loads);
      bags.forEach(function (bag) {
        const sx = takeSeasonXfp(bag.d);
        const wk = takeWeekNfl(bag.d);
        weekByYear.set(bag.y, wk);
        sx.forEach(function (r) {
          const k = pidKey(r.player_id);
          if (!k) return;
          if (!seasonByPid.has(k)) seasonByPid.set(k, []);
          seasonByPid.get(k).push(r);
        });
        wk.forEach(function (r) {
          const k = pidKey(r.player_id);
          if (!k) return;
          if (!weekByPid.has(k)) weekByPid.set(k, []);
          weekByPid.get(k).push(r);
        });
      });
    })();
    return ready;
  }

  function seasonRowsForPid(pid) {
    const rows = (seasonByPid.get(pidKey(pid)) || []).slice();
    rows.sort(function (a, b) { return a.season - b.season; });
    return rows;
  }

  function weekRowsForPid(pid) {
    const rows = (weekByPid.get(pidKey(pid)) || []).slice();
    rows.sort(function (a, b) { return (a.season - b.season) || (a.week - b.week); });
    return rows;
  }

  function seasonRowsForPids(pidsByYear) {
    const out = [];
    Object.keys(pidsByYear || {}).forEach(function (y) {
      const year = +y;
      if (year === 2013) return;
      const set = pidsByYear[y];
      if (!set) return;
      set.forEach(function (pid) {
        (seasonByPid.get(pidKey(pid)) || []).forEach(function (r) {
          if (r.season === year) out.push(r);
        });
      });
    });
    out.sort(function (a, b) { return a.season - b.season; });
    return out;
  }

  function weekRowsForPids(pidsByYear) {
    const out = [];
    Object.keys(pidsByYear || {}).forEach(function (y) {
      const year = +y;
      const set = pidsByYear[y];
      if (!set) return;
      const rows = weekByYear.get(year) || [];
      rows.forEach(function (r) {
        if (r.player_id == null) return;
        if (set.has(r.player_id) || set.has(Number(r.player_id)) || set.has(String(r.player_id))) {
          out.push(r);
        }
      });
    });
    out.sort(function (a, b) { return (a.season - b.season) || (a.week - b.week); });
    return out;
  }

  function aggregateSeason(rows) {
    const by = {};
    rows.forEach(function (r) {
      const y = r.season;
      if (!by[y]) by[y] = { season: y, fp: 0, xfp: 0, fpoe: 0, n: 0 };
      SEASON_KEYS.forEach(function (k) {
        if (r[k] != null) by[y][k] += r[k];
      });
      by[y].n += 1;
    });
    return Object.keys(by).map(Number).sort(function (a, b) { return a - b; }).map(function (y) { return by[y]; });
  }

  const SKILL_POS = { QB: 1, RB: 1, WR: 1, TE: 1 };

  /* Team FPOE is mean of rostered skill players, never a roster sum. */
  function aggregateSeasonFpoe(rows) {
    const by = {};
    rows.forEach(function (r) {
      const pos = String(r.pos || "").toUpperCase();
      if (!SKILL_POS[pos]) return; /* missing pos is not skill */
      if (r.fpoe == null || r.season == null) return;
      const y = r.season;
      if (!by[y]) by[y] = { season: y, sum: 0, n: 0 };
      by[y].sum += r.fpoe;
      by[y].n += 1;
    });
    return Object.keys(by).map(Number).sort(function (a, b) { return a - b; }).map(function (y) {
      const b = by[y];
      return { season: y, fpoe: b.n ? (b.sum / b.n) : null, n: b.n };
    });
  }

  function aggregateWeek(rows) {
    const by = {};
    rows.forEach(function (r) {
      const key = r.season + ":" + r.week;
      if (!by[key]) {
        by[key] = {
          season: r.season, week: r.week,
          pass_yards: 0, rush_yards: 0, targets: 0, receptions: 0,
          rush_td: 0, pass_td: 0, rec_td: 0, n: 0,
        };
      }
      WEEK_KEYS.forEach(function (k) {
        if (r[k] != null) by[key][k] += r[k];
      });
      by[key].n += 1;
    });
    return Object.keys(by).map(function (k) { return by[k]; })
      .sort(function (a, b) { return (a.season - b.season) || (a.week - b.week); });
  }

  function kill(id) {
    const ch = charts[id];
    if (ch) {
      try { ch.destroy(); } catch (e) {}
      charts[id] = null;
    }
  }

  function chips(el, values, selected, onPick, allLabel) {
    if (!el) return;
    const sel = selected instanceof Set ? selected : new Set(selected || values);
    const bits = [];
    if (allLabel) {
      const allOn = values.every(function (v) { return sel.has(v); });
      bits.push('<button type="button" class="season-chip' + (allOn ? " on" : "") + '" data-all="1">' + allLabel + "</button>");
    }
    values.forEach(function (v) {
      bits.push('<button type="button" class="season-chip' + (sel.has(v) ? " on" : "") + '" data-v="' + v + '">' + v + "</button>");
    });
    el.innerHTML = bits.join("");
    el.querySelectorAll("button").forEach(function (b) {
      b.addEventListener("click", function () {
        if (b.dataset.all) {
          const allOn = values.every(function (v) { return sel.has(v); });
          sel.clear();
          if (!allOn) values.forEach(function (v) { sel.add(v); });
          if (!sel.size) values.forEach(function (v) { sel.add(v); });
        } else {
          const v = +b.dataset.v;
          if (sel.has(v)) {
            if (sel.size > 1) sel.delete(v);
          } else sel.add(v);
        }
        onPick(sel);
      });
    });
  }

  function renderMarks(el, items) {
    if (!el) return;
    el.innerHTML = (items || []).map(function (it) {
      const logo = it.logo
        ? '<img class="chi114-logo" src="' + it.logo + '" alt="" width="28" height="28">'
        : "";
      return '<span class="chi114-mark' + (it.on ? " is-on" : "") + '">' + logo +
        '<span>' + (it.label || "") + "</span></span>";
    }).join("");
  }

  function applyIsolate(chart, idx, n) {
    chart.data.datasets.forEach(function (ds) {
      const base = ds._chiColor || ds.borderColor;
      const dim = [];
      const rad = [];
      for (let i = 0; i < n; i++) {
        const on = idx == null || i === idx;
        dim.push(on ? base : base + "33");
        rad.push(on ? 5 : 2);
      }
      ds.pointBackgroundColor = dim;
      ds.pointBorderColor = dim;
      ds.pointRadius = rad;
      ds.borderColor = idx == null ? base : (base + "99");
    });
    chart.update("none");
  }

  function drawSeasonXfp(opts) { /* xfp-pane */
    const canvas = opts.canvas;
    const rowsIn = (opts.rows || []).filter(function (r) {
      return r && r.season != null && r.season !== 2013;
    });
    const pane = opts.pane;
    if (!canvas) return;
    kill(canvas.id);
    if (!rowsIn.length) {
      if (pane) pane.hidden = true;
      return;
    }
    if (pane) pane.hidden = false;

    const mode = opts.mode || "player";
    const series = mode === "team" ? aggregateSeason(rowsIn) : rowsIn;
    const yearsAvail = [];
    const seenY = {};
    series.forEach(function (r) {
      if (!seenY[r.season]) { seenY[r.season] = 1; yearsAvail.push(r.season); }
    });
    yearsAvail.sort(function (a, b) { return a - b; });

    const state = canvas._chi114s || { years: new Set(yearsAvail), iso: null };
    canvas._chi114s = state;
    yearsAvail.forEach(function (y) { if (!XFP_YEARS.includes(y)) state.years.delete(y); });

    chips(opts.chips, yearsAvail, state.years, function (sel) {
      state.years = sel;
      drawSeasonXfp(opts);
    }, "All");

    const rows = series.filter(function (r) { return state.years.has(r.season); });
    if (!rows.length) {
      kill(canvas.id);
      return;
    }

    const labels = rows.map(function (r) { return String(r.season); });
    const datasets = XFP_PLOT_KEYS.map(function (k) {
      const color = SEASON_COLORS[k];
      return {
        label: k.toUpperCase(),
        data: rows.map(function (r) { return r[k]; }),
        borderColor: color,
        backgroundColor: color,
        pointBackgroundColor: color,
        pointBorderColor: "#0b0e14",
        pointRadius: 4,
        pointHoverRadius: 6,
        borderWidth: 2,
        tension: 0.15,
        spanGaps: true,
        _chiColor: color,
      };
    });

    const latest = rows[rows.length - 1];
    const marks = [];
    if (opts.logoUrl && latest) {
      marks.push({ logo: opts.logoUrl, label: String(latest.season), on: true });
    }
    renderMarks(opts.marks, marks);

    const ctx = canvas.getContext("2d");
    charts[canvas.id] = new Chart(ctx, {
      type: "line",
      data: { labels: labels, datasets: datasets },
      options: {
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        onHover: function (_e, els, chart) {
          const idx = els && els[0] ? els[0].index : null;
          if (state.iso === idx) return;
          state.iso = idx;
          applyIsolate(chart, idx, labels.length);
          if (opts.logoUrl) {
            const hit = idx != null ? rows[idx] : latest;
            renderMarks(opts.marks, hit ? [{ logo: opts.logoUrl, label: String(hit.season), on: true }] : []);
          }
        },
        plugins: {
          legend: { display: true, labels: { boxWidth: 10, boxHeight: 10 } },
          tooltip: {
            callbacks: {
              label: function (c) {
                const r = rows[c.dataIndex];
                const key = XFP_PLOT_KEYS[c.datasetIndex];
                const v = r ? r[key] : null;
                return key.toUpperCase() + " " + (v == null ? "—" : Number(v).toFixed(1)) + " · non-PPR";
              },
            },
          },
        },
        scales: {
          y: {
            grid: { color: C.grid },
            border: { display: false },
            title: { display: true, text: "FP / XFP (non-PPR)" },
          },
          x: { grid: { display: false }, border: { display: false } },
        },
      },
    });
  }


  function drawSeasonFpoe(opts) {
    const canvas = opts.canvas;
    const rowsIn = (opts.rows || []).filter(function (r) {
      return r && r.season != null && r.season !== 2013;
    });
    const pane = opts.pane;
    if (!canvas) return;
    kill(canvas.id);
    if (!rowsIn.length) {
      if (pane) pane.hidden = true;
      return;
    }
    if (pane) pane.hidden = false;

    const mode = opts.mode || "player";
    const series = mode === "team" ? aggregateSeasonFpoe(rowsIn) : rowsIn;
    const yearsAvail = [];
    const seenY = {};
    series.forEach(function (r) {
      if (!seenY[r.season]) { seenY[r.season] = 1; yearsAvail.push(r.season); }
    });
    yearsAvail.sort(function (a, b) { return a - b; });

    const state = canvas._chi114f || { years: new Set(yearsAvail), iso: null };
    canvas._chi114f = state;
    yearsAvail.forEach(function (y) { if (!XFP_YEARS.includes(y)) state.years.delete(y); });

    chips(opts.chips, yearsAvail, state.years, function (sel) {
      state.years = sel;
      drawSeasonFpoe(opts);
    }, "All");

    const rows = series.filter(function (r) { return state.years.has(r.season); });
    if (!rows.length) {
      kill(canvas.id);
      return;
    }

    const labels = rows.map(function (r) { return String(r.season); });
    const datasets = FPOE_PLOT_KEYS.map(function (k) {
      const color = SEASON_COLORS[k];
      return {
        label: k.toUpperCase(),
        data: rows.map(function (r) { return r[k]; }),
        borderColor: color,
        backgroundColor: color,
        pointBackgroundColor: color,
        pointBorderColor: "#0b0e14",
        pointRadius: 4,
        pointHoverRadius: 6,
        borderWidth: 2,
        tension: 0.15,
        spanGaps: true,
        _chiColor: color,
      };
    });

    const latest = rows[rows.length - 1];
    const marks = [];
    if (opts.logoUrl && latest) {
      marks.push({ logo: opts.logoUrl, label: String(latest.season), on: true });
    }
    renderMarks(opts.marks, marks);

    const fpoeVals = rows.map(function (r) { return r.fpoe; }).filter(function (v) { return v != null; });
    const yMin = fpoeVals.length ? Math.min(0, Math.min.apply(null, fpoeVals)) : 0;
    const yMax = fpoeVals.length ? Math.max(0, Math.max.apply(null, fpoeVals)) : 0;

    const ctx = canvas.getContext("2d");
    charts[canvas.id] = new Chart(ctx, {
      type: "line",
      data: { labels: labels, datasets: datasets },
      options: {
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        onHover: function (_e, els, chart) {
          const idx = els && els[0] ? els[0].index : null;
          if (state.iso === idx) return;
          state.iso = idx;
          applyIsolate(chart, idx, labels.length);
          if (opts.logoUrl) {
            const hit = idx != null ? rows[idx] : latest;
            renderMarks(opts.marks, hit ? [{ logo: opts.logoUrl, label: String(hit.season), on: true }] : []);
          }
        },
        plugins: {
          legend: { display: true, labels: { boxWidth: 10, boxHeight: 10 } },
          tooltip: {
            callbacks: {
              label: function (c) {
                const r = rows[c.dataIndex];
                const key = FPOE_PLOT_KEYS[c.datasetIndex];
                const v = r ? r[key] : null;
                const extra = mode === "team" ? " · skill mean" : "";
                return key.toUpperCase() + " " + (v == null ? "—" : Number(v).toFixed(1)) + " · non-PPR" + extra;
              },
            },
          },
        },
        scales: {
          y: {
            min: yMin,
            max: yMax,
            grid: {
              color: function (ctx) {
                return ctx.tick && ctx.tick.value === 0 ? "rgba(238,244,255,0.45)" : C.grid;
              },
              lineWidth: function (ctx) {
                return ctx.tick && ctx.tick.value === 0 ? 1.5 : 1;
              },
            },
            border: { display: false },
            title: { display: true, text: "FPOE (non-PPR)" },
          },
          x: { grid: { display: false }, border: { display: false } },
        },
      },
    });
  }

  function drawWeekNfl(opts) {
    const canvas = opts.canvas;
    const rowsIn = (opts.rows || []).filter(function (r) {
      return r && r.season != null && r.week != null;
    });
    const pane = opts.pane;
    if (!canvas) return;
    kill(canvas.id);
    if (!rowsIn.length) {
      if (pane) pane.hidden = true;
      return;
    }
    if (pane) pane.hidden = false;

    const mode = opts.mode || "player";
    const series = mode === "team" ? aggregateWeek(rowsIn) : rowsIn;

    const yearsAvail = [];
    const seenY = {};
    series.forEach(function (r) {
      if (!seenY[r.season]) { seenY[r.season] = 1; yearsAvail.push(r.season); }
    });
    yearsAvail.sort(function (a, b) { return a - b; });

    const weeksAvail = [];
    const seenW = {};
    series.forEach(function (r) {
      if (!seenW[r.week]) { seenW[r.week] = 1; weeksAvail.push(r.week); }
    });
    weeksAvail.sort(function (a, b) { return a - b; });

    const state = canvas._chi114w || {
      years: new Set(yearsAvail.length ? [yearsAvail[yearsAvail.length - 1]] : []),
      weeks: new Set(weeksAvail),
      iso: null,
    };
    canvas._chi114w = state;

    chips(opts.yearChips, yearsAvail, state.years, function (sel) {
      state.years = sel;
      drawWeekNfl(opts);
    }, "All years");
    chips(opts.weekChips, weeksAvail, state.weeks, function (sel) {
      state.weeks = sel;
      drawWeekNfl(opts);
    }, "All weeks");

    const rows = series.filter(function (r) {
      return state.years.has(r.season) && state.weeks.has(r.week);
    });
    if (!rows.length) return;

    const multiYear = state.years.size > 1;
    const labels = rows.map(function (r) {
      return multiYear ? String(r.season).slice(2) + "-W" + r.week : "W" + r.week;
    });

    const datasets = WEEK_KEYS.map(function (k) {
      const color = WEEK_COLORS[k];
      const yAxisID = YARD_KEYS.indexOf(k) >= 0 ? "y" : "y1";
      return {
        label: WEEK_LABELS[k],
        data: rows.map(function (r) { return r[k]; }),
        borderColor: color,
        backgroundColor: color,
        pointBackgroundColor: color,
        pointBorderColor: "#0b0e14",
        pointRadius: 3,
        pointHoverRadius: 5,
        borderWidth: 2,
        tension: 0.15,
        spanGaps: true,
        yAxisID: yAxisID,
        _chiColor: color,
      };
    });

    const ctx = canvas.getContext("2d");
    charts[canvas.id] = new Chart(ctx, {
      type: "line",
      data: { labels: labels, datasets: datasets },
      options: {
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        onHover: function (_e, els, chart) {
          const idx = els && els[0] ? els[0].index : null;
          if (state.iso === idx) return;
          state.iso = idx;
          applyIsolate(chart, idx, labels.length);
        },
        plugins: {
          legend: { display: true, labels: { boxWidth: 10, boxHeight: 10 } },
          tooltip: {
            callbacks: {
              title: function (items) {
                const r = rows[items[0].dataIndex];
                return r ? (r.season + " week " + r.week) : "";
              },
              label: function (c) {
                const r = rows[c.dataIndex];
                const key = WEEK_KEYS[c.datasetIndex];
                const v = r ? r[key] : null;
                const extra = key === "receptions" ? " · volume" : "";
                return WEEK_LABELS[key] + " " + (v == null ? "—" : Number(v).toFixed(key.indexOf("yards") >= 0 ? 0 : 1)) + extra;
              },
            },
          },
        },
        scales: {
          y: {
            position: "left",
            grid: { color: C.grid },
            border: { display: false },
            title: { display: true, text: "yards" },
          },
          y1: {
            position: "right",
            grid: { display: false },
            border: { display: false },
            title: { display: true, text: "targets / rec / TDs" },
          },
          x: { grid: { display: false }, border: { display: false } },
        },
      },
    });
  }

  window.CHI114 = {
    ensure: ensure,
    takeSeasonXfp: takeSeasonXfp,
    takeWeekNfl: takeWeekNfl,
    seasonRowsForPid: seasonRowsForPid,
    weekRowsForPid: weekRowsForPid,
    seasonRowsForPids: seasonRowsForPids,
    weekRowsForPids: weekRowsForPids,
    drawSeasonXfp: drawSeasonXfp,
    drawSeasonFpoe: drawSeasonFpoe,
    drawWeekNfl: drawWeekNfl,
    XFP_YEARS: XFP_YEARS,
    WEEK_YEARS: WEEK_YEARS,
    SEASON_KEYS: SEASON_KEYS,
    WEEK_KEYS: WEEK_KEYS,
  };
})();
