/* AFFL History — Matchup Scores by Season (regular-season team games). */
(function () {
  const YEARS = [];
  for (let y = 2014; y <= 2025; y++) YEARS.push(y);

  const PLAYOFF_TIER = /BRACKET|PLAYOFF|CONSOLATION/i;

  function injectStyle() {
    if (document.getElementById("score-trend-css")) return;
    const s = document.createElement("style");
    s.id = "score-trend-css";
    s.textContent = [
      "#score-trend-card .chart-wrap { height: 380px; }",
      "#score-trend-note { color: var(--mut, #7d8aa0); font-size: 11px; margin-top: 10px; line-height: 1.45; }",
    ].join("\n");
    document.head.appendChild(s);
  }

  function sideScore(side) {
    if (!side) return null;
    if (side.pts == null || side.pts === "") return null;
    const n = Number(side.pts);
    return Number.isFinite(n) ? n : null;
  }

  function regularWeekSet(yd) {
    const set = new Set();
    const raw = yd && yd.regWeeks;
    if (Array.isArray(raw) && raw.length) {
      raw.forEach((w) => {
        const n = Number(w);
        if (Number.isFinite(n)) set.add(n);
      });
      return set;
    }
    const n = Number(raw);
    if (Number.isFinite(n) && n > 0) {
      for (let w = 1; w <= n; w++) set.add(w);
      return set;
    }
    return set;
  }

  function isRegularMatchup(weekNum, matchup, regSet) {
    if (!regSet.has(Number(weekNum))) return false;
    const tier = (matchup && matchup.tier) || "NONE";
    if (tier && tier !== "NONE" && PLAYOFF_TIER.test(String(tier))) return false;
    return true;
  }

  function seasonSides(yd) {
    const scores = [];
    const regSet = regularWeekSet(yd);
    const weeks = (yd && yd.weeks) || {};
    Object.keys(weeks).forEach((wk) => {
      const w = Number(wk);
      const matchups = weeks[wk] || [];
      matchups.forEach((m) => {
        if (!isRegularMatchup(w, m, regSet)) return;
        const h = sideScore(m.home);
        const a = sideScore(m.away);
        if (h != null) scores.push(h);
        if (a != null) scores.push(a);
      });
    });
    return scores;
  }

  function seasonStats(year, yd) {
    const scores = seasonSides(yd);
    if (!scores.length) return null;
    const n = scores.length;
    const avg = scores.reduce((s, x) => s + x, 0) / n;
    const high = Math.max.apply(null, scores);
    const low = Math.min.apply(null, scores);
    return {
      year: year,
      n: n,
      avg: avg,
      high: high,
      low: low,
      spread: high - low,
    };
  }

  async function loadYearBundles() {
    if (window.AFFL && window.AFFL.boot && window.AFFL.loadAllYears) {
      await window.AFFL.boot();
      const all = await window.AFFL.loadAllYears();
      return all.map((row) => ({
        year: row.year != null ? row.year : (row.data && row.data.year),
        data: row.data || row,
      }));
    }
    const out = [];
    for (let i = 0; i < YEARS.length; i++) {
      const y = YEARS[i];
      const d = await fetch("years/" + y + ".json?v=" + Date.now(), { cache: "no-store" }).then((r) => r.json());
      out.push({ year: y, data: d });
    }
    return out;
  }

  function fmt1(n) {
    return Number(n).toLocaleString("en-US", { maximumFractionDigits: 1, minimumFractionDigits: 1 });
  }

  function renderChart(rows) {
    const canvas = document.getElementById("score-trend-chart");
    if (!canvas || typeof Chart === "undefined") return;
    if (window.AFFL && window.AFFL.chartDefaults) window.AFFL.chartDefaults(Chart);

    const C = (window.AFFL && window.AFFL.C) || {
      blue: "#00a2ff", green: "#c8ff00", red: "#ff2d1a",
      mut: "#7d8aa0", ink: "#eef4ff", grid: "#1b243366",
    };
    const green = "#c8ff00";
    const blue = C.blue || "#00a2ff";
    const red = C.red || "#ff2d1a";

    const labels = rows.map((r) => String(r.year));
    const spreadPlugin = {
      id: "scoreTrendSpreadLabels",
      afterDatasetsDraw: function (chart) {
        const meta = chart.getDatasetMeta(1);
        if (!meta || !meta.data) return;
        const ctx = chart.ctx;
        ctx.save();
        ctx.fillStyle = C.mut || "#7d8aa0";
        ctx.font = '10px "Avenir Next","Segoe UI",sans-serif';
        ctx.textAlign = "center";
        ctx.textBaseline = "bottom";
        rows.forEach((r, i) => {
          const pt = meta.data[i];
          if (!pt) return;
          ctx.fillText(fmt1(r.spread), pt.x, pt.y - 6);
        });
        ctx.restore();
      },
    };

    new Chart(canvas, {
      data: {
        labels: labels,
        datasets: [
          {
            type: "bar",
            label: "Spread (high − low)",
            data: rows.map((r) => [r.low, r.high]),
            backgroundColor: "rgba(47, 123, 255, 0.14)",
            hoverBackgroundColor: "rgba(47, 123, 255, 0.24)",
            borderWidth: 0,
            barPercentage: 0.5,
            categoryPercentage: 0.75,
            order: 10,
          },
          {
            type: "line",
            label: "High game",
            data: rows.map((r) => r.high),
            borderColor: green,
            backgroundColor: green,
            pointBackgroundColor: green,
            pointBorderColor: "#05060b",
            pointBorderWidth: 1.5,
            pointRadius: 4,
            pointHoverRadius: 6,
            borderWidth: 2.2,
            tension: 0.28,
            order: 1,
          },
          {
            type: "line",
            label: "Average",
            data: rows.map((r) => r.avg),
            borderColor: blue,
            backgroundColor: blue,
            pointBackgroundColor: blue,
            pointBorderColor: "#05060b",
            pointBorderWidth: 1.5,
            pointRadius: 4,
            pointHoverRadius: 6,
            borderWidth: 2.4,
            tension: 0.28,
            order: 0,
          },
          {
            type: "line",
            label: "Low",
            data: rows.map((r) => r.low),
            borderColor: red,
            backgroundColor: red,
            pointBackgroundColor: red,
            pointBorderColor: "#05060b",
            pointBorderWidth: 1.5,
            pointRadius: 4,
            pointHoverRadius: 6,
            borderWidth: 2.2,
            tension: 0.28,
            order: 2,
          },
        ],
      },
      options: {
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        layout: { padding: { top: 18, right: 8 } },
        plugins: {
          legend: {
            labels: {
              boxWidth: 10,
              boxHeight: 10,
              usePointStyle: true,
              pointStyle: "circle",
              color: C.mut,
            },
          },
          tooltip: {
            callbacks: {
              label: function (ctx) {
                const r = rows[ctx.dataIndex];
                if (!r) return "";
                const lab = ctx.dataset.label || "";
                if (lab.indexOf("Spread") === 0) return "Spread (high − low): " + fmt1(r.spread);
                if (lab === "High game") return "High game: " + fmt1(r.high);
                if (lab === "Average") return "Average: " + fmt1(r.avg) + "  (" + r.n + " team games)";
                if (lab === "Low") return "Low: " + fmt1(r.low);
                return lab;
              },
            },
          },
        },
        scales: {
          y: {
            suggestedMin: 20,
            suggestedMax: 180,
            ticks: { callback: function (v) { return v + " pts"; } },
            grid: { color: C.grid || "#1b243366" },
            border: { display: false },
          },
          x: {
            grid: { display: false },
            border: { display: false },
          },
        },
      },
      plugins: [spreadPlugin],
    });
  }

  async function main() {
    const card = document.getElementById("score-trend-card");
    if (!card) return;
    injectStyle();
    const bundles = await loadYearBundles();
    const byYear = {};
    bundles.forEach((b) => {
      const y = Number(b.year);
      if (Number.isFinite(y)) byYear[y] = b.data;
    });
    const rows = [];
    YEARS.forEach((y) => {
      const yd = byYear[y];
      if (!yd) return;
      const row = seasonStats(y, yd);
      if (row) rows.push(row);
    });
    window.AFFL_SCORE_TREND = { rows: rows, seasonStats: seasonStats, seasonSides: seasonSides };
    if (!rows.length) {
      const wrap = card.querySelector(".chart-wrap");
      if (wrap) wrap.innerHTML = '<div class="notice">No completed regular-season scores.</div>';
      return;
    }
    renderChart(rows);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () { main().catch(console.error); });
  } else {
    main().catch(console.error);
  }
})();
