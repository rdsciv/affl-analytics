/* CHI-119 History: Season dropdown + The Race. Runs the last full History book with year/Race patched in. */
(async function () {
  async function loadCore() {
    const urls = [
      "https://raw.githubusercontent.com/rdsciv/affl-analytics/19603e59c972e689ca2d49c3dde0811f7df57418/site/history.js?v=17",
      "https://cdn.jsdelivr.net/gh/rdsciv/affl-analytics@19603e59c972e689ca2d49c3dde0811f7df57418/site/history.js",
    ];
    let last = "history core unavailable";
    for (let i = 0; i < urls.length; i++) {
      try {
        const r = await fetch(urls[i], { cache: "no-store" });
        if (r.ok) return await r.text();
        last = "history core " + r.status;
      } catch (e) {
        last = String(e && e.message ? e.message : e);
      }
    }
    throw new Error(last);
  }
  const src = await loadCore();

  const oldYearInit = "  const qsYear = new URLSearchParams(location.search).get(\"year\");\n  let seasonYear = +qsYear || (A.years()[0]);\n  if (A.years().indexOf(seasonYear) < 0) seasonYear = A.years()[0];";

  const newYearInit = "  function latestFinished() {\n    const ys = (A.years() || []).filter((y) => y >= 2014 && y <= 2025).sort((a, b) => b - a);\n    return ys[0] || 2025;\n  }\n  function parseSeasonParam(raw) {\n    if (raw == null || raw === \"\" || String(raw).toLowerCase() === \"all\") return null;\n    const y = +raw;\n    if (!y || y < 2014 || y > 2025) return null;\n    if ((A.years() || []).indexOf(y) < 0) return null;\n    return y;\n  }\n  const qsYear = new URLSearchParams(location.search).get(\"year\");\n  let pickedYear = parseSeasonParam(qsYear);\n  let seasonYear = pickedYear == null ? latestFinished() : pickedYear;";

  const oldSub = "    if (sub) sub.textContent = seasonYear + \" · ESPN Moves · current franchise names\";";
  const newSub = "    if (sub) {\n      sub.textContent = (pickedYear == null ? seasonYear + \" · latest finished · \" : seasonYear + \" · \")\n        + \"ESPN Moves · current franchise names\";\n    }";

  const oldPicker = "  function stampSeasonYear(y) {\n    const u = new URL(location.href);\n    u.searchParams.set(\"year\", y);\n    history.replaceState(null, \"\", u.pathname.split(\"/\").pop() + u.search + u.hash);\n  }\n\n  if ($(\"year-picker\")) {\n    A.yearPicker($(\"year-picker\"), seasonYear, (y) => {\n      seasonYear = y;\n      stampSeasonYear(y);\n      renderSeasonStandings();\n      renderTxnAndWeeks();\n      renderWaiverReport();\n      renderTxLog();\n      renderWaiverValue();\n      renderCustodyPar();\n      renderAgeScatter();\n    });\n  }";

  const newPicker = "  function stampSeasonYear(y) {\n    const u = new URL(location.href);\n    if (y == null) u.searchParams.delete(\"year\");\n    else u.searchParams.set(\"year\", y);\n    history.replaceState(null, \"\", u.pathname.split(\"/\").pop() + u.search + u.hash);\n  }\n\n  function applySeasonYear(y) {\n    pickedYear = y;\n    seasonYear = y == null ? latestFinished() : y;\n    stampSeasonYear(y);\n    renderSeasonStandings();\n    renderTxnAndWeeks();\n    renderWaiverReport();\n    renderTxLog();\n    renderWaiverValue();\n    renderCustodyPar();\n    renderAgeScatter();\n    renderRace();\n  }\n\n  function bindYearSelect() {\n    const el = $(\"year-picker\");\n    if (!el || el.tagName !== \"SELECT\") return;\n    el.value = pickedYear == null ? \"all\" : String(pickedYear);\n    el.addEventListener(\"change\", () => {\n      applySeasonYear(parseSeasonParam(el.value));\n    });\n  }\n  bindYearSelect();\n\n  let raceChart = null;\n  function renderRace() {\n    const canvas = $(\"race-chart\");\n    const sub = $(\"race-sub\");\n    if (!canvas) return;\n    const y = seasonYear;\n    const s = DATA.seasons[String(y)] || { teams: [], regWeeks: [] };\n    const top4 = (s.teams || []).slice().sort((a, b) => (a.finalRank || 99) - (b.finalRank || 99)).slice(0, 4);\n    if (sub) sub.textContent = y + \" · cumulative wins · top four finishers · current franchise names\";\n    if (typeof Chart === \"undefined\") return;\n    if (!top4.length) {\n      if (raceChart) { raceChart.destroy(); raceChart = null; }\n      return;\n    }\n    const C = A.C;\n    const colors = [C.blue, C.gold, C.blue2, C.ice];\n    A.chartDefaults(Chart);\n    if (raceChart) { raceChart.destroy(); raceChart = null; }\n    raceChart = new Chart(canvas, {\n      type: \"line\",\n      data: {\n        labels: (s.regWeeks || []).map((w) => \"W\" + w),\n        datasets: top4.map((t, i) => {\n          const oid = canon(t.owner);\n          const name = A.franchiseName(oid) || t.name || \"—\";\n          return {\n            label: name.length > 16 ? name.slice(0, 15) + \"…\" : name,\n            data: t.cumWins || [],\n            borderColor: colors[i],\n            backgroundColor: colors[i],\n            borderWidth: 2,\n            pointRadius: 3,\n            pointBorderColor: \"#12142e\",\n            pointBorderWidth: 1.5,\n            tension: 0.2,\n          };\n        }),\n      },\n      options: {\n        maintainAspectRatio: false,\n        interaction: { mode: \"index\", intersect: false },\n        plugins: { legend: { labels: { boxWidth: 10, boxHeight: 10, usePointStyle: true, pointStyle: \"circle\" } } },\n        scales: {\n          y: { grid: { color: C.grid }, border: { display: false }, ticks: { stepSize: 2 }, title: { display: true, text: \"wins\" } },\n          x: { grid: { display: false }, border: { display: false } },\n        },\n      },\n    });\n  }";

  const oldCalls = "  renderSeasonStandings();\n  renderTxnAndWeeks();\n  renderWaiverReport();\n  renderTxLog();\n  renderWaiverValue();\n  renderCustodyPar();\n  renderAgeScatter();\n  renderTable();";
  const newCalls = "  renderSeasonStandings();\n  renderTxnAndWeeks();\n  renderWaiverReport();\n  renderTxLog();\n  renderWaiverValue();\n  renderCustodyPar();\n  renderAgeScatter();\n  renderRace();\n  renderTable();";

  if (src.indexOf(oldYearInit) < 0) throw new Error("history core missing year init");
  if (src.indexOf(oldSub) < 0) throw new Error("history core missing season sub");
  if (src.indexOf(oldPicker) < 0) throw new Error("history core missing year picker");
  if (src.indexOf(oldCalls) < 0) throw new Error("history core missing render calls");

  let s = src;
  s = s.replace(oldYearInit, newYearInit);
  s = s.replace(oldSub, newSub);
  s = s.replace(oldPicker, newPicker);
  s = s.replace(oldCalls, newCalls);
  (0, eval)(s);
})();
