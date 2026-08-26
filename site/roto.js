/* Roto page: load Pillars boxscores + league.json, compute at runtime. */
(async function () {
  const A = window.AFFL;
  await A.boot();
  const R = window.AFFLRoto;
  const root = "pillars/";
  const phaseNote = {
    reg: "Regular season only — every team plays the same number of games, so category totals are directly comparable.",
    post: "Winners-bracket games only. Teams play unequal numbers of playoff games (byes, 2- vs 3-game paths), so totals are not directly comparable — the games column shows each team’s sample.",
    combined: "Regular season + winners bracket. Consolation games are excluded. Playoff teams play more games than eliminated ones, so counting totals favor deeper runs.",
  };

  const league = await fetch(root + "league.json").then((r) => r.json());
  const ownerName = (id) => (league.ownerNames && league.ownerNames[id]) || id;
  const seasons = league.seasons || [];
  const expectedYears = (league.meta && league.meta.seasons) || seasons.map((s) => s.year);
  const lastSeason = (league.meta && league.meta.lastSeason) || expectedYears[expectedYears.length - 1];

  // Attempt every season in league.json. Years without a boxscore file stay out of
  // the career rollup (same as Pillars hasBoxscores), not folded in as sit-outs.
  const attempted = await Promise.all(expectedYears.map(async (year) => {
    const season = seasons.find((s) => s.year === year);
    try {
      const res = await fetch(root + "boxscores/" + year + ".json");
      if (!res.ok) return { year, season, box: null };
      return { year, season, box: await res.json() };
    } catch (e) {
      return { year, season, box: null };
    }
  }));
  const loads = attempted.filter((l) => l.box && l.season);
  const boxYears = loads.map((l) => l.year);
  let scope = A.scopeFromURL();
  let squad = A.squadFromURL();
  let phase = "reg";
  let year = boxYears.indexOf(lastSeason) >= 0 ? lastSeason : (boxYears.length ? boxYears[boxYears.length - 1] : null);
  let teamId = null;
  let ownerId = null;
  let radarChart = null;
  let careerChart = null;

  const $ = (id) => document.getElementById(id);

  function pillarsOwner(sq) {
    if (!sq) return null;
    for (const y of A.squadYears(sq)) {
      const tid = A.teamIdFor(y, sq);
      const load = loads.find((l) => l.year === y);
      if (!load || !tid || !load.season) continue;
      const t = (load.season.teams || []).find((x) => x.teamId === tid);
      if (t && t.ownerId) return t.ownerId;
    }
    return null;
  }

  function visibleYears() {
    return boxYears.slice();
  }


  function render() {
    const scopeEl = $("scope-picker");
    if (scopeEl) {
      scopeEl.innerHTML = [["season","Season"],["cum","Cumulative"]].map(([v,l]) =>
        `<button class="season-chip${v===scope?" on":""}" data-s="${v}">${l}</button>`).join("");
      scopeEl.querySelectorAll("button").forEach((b) => {
        b.onclick = () => { scope = b.dataset.s; render(); };
      });
    }
    A.squadPicker($("squad-picker"), squad, (s) => {
      if (s) { A.goTeam(s, year, { scope }); return; }
      squad = ""; A.stampNav(squad); render();
    });
    A.stampNav(squad);
    const careerBlock = $("career-block");
    const seasonBlock = $("season-block");
    const yearRow = $("year-row");
    const graphs = $("graphs-block");
    const careerGraph = $("career-graph-block");
    if (careerBlock) careerBlock.hidden = scope !== "cum";
    if (careerGraph) careerGraph.hidden = scope !== "cum";
    if (seasonBlock) seasonBlock.hidden = scope !== "season";
    if (yearRow) yearRow.hidden = scope !== "season";
    if (graphs) graphs.hidden = false;

    $("phase-note").textContent = phaseNote[phase];
    $("phase-picker").innerHTML = ["reg", "post", "combined"].map((p) =>
      `<button class="season-chip${p === phase ? " on" : ""}" data-phase="${p}">${R.PHASE_LABEL[p]}</button>`
    ).join("");
    $("phase-picker").querySelectorAll("button").forEach((b) => {
      b.onclick = () => { phase = b.dataset.phase; teamId = null; render(); };
    });

    const career = R.buildRotoCareer(loads, phase, false);
    renderCareer(career);
    if (scope === "cum") {
      renderCareerChart(career);
      renderCareerRadar(career);
      return;
    }

    const yearsShown = visibleYears();
    if (yearsShown.length && yearsShown.indexOf(year) < 0) year = yearsShown[yearsShown.length - 1];
    $("year-picker").innerHTML = yearsShown.map((y) =>
      `<button class="season-chip${y === year ? " on" : ""}" data-y="${y}">${y}</button>`
    ).join("");
    $("year-picker").querySelectorAll("button").forEach((b) => {
      b.onclick = () => { year = +b.dataset.y; teamId = null; render(); };
    });

    const load = loads.find((l) => l.year === year);
    if (!load || !load.box || !load.season) {
      $("season-table").innerHTML = `<div class="empty">No boxscore for ${year}.</div>`;
      $("breakdown").innerHTML = "";
      return;
    }
    const teams = R.computeCategoryStats(load.box, load.season, phase, false);
    if (!teams.length) {
      $("season-table").innerHTML = `<div class="empty">No ${R.PHASE_LABEL[phase].toLowerCase()} games scored for ${year}.</div>`;
      $("breakdown").innerHTML = "";
      return;
    }
    const selected = teams.find((t) => A.sameId(t.teamId, teamId)) || teams[0];
    teamId = selected.teamId;
    const n = teams.length;
    const displayTeams = teams;
    const cols = selected.categories;
    $("season-sub").textContent =
      `Cells colored by category rank (green = best, red = worst) · Pts is category rank · ${year} · ${R.PHASE_LABEL[phase]}`;
    $("season-table").innerHTML = `
      <div class="table-scroll">
        <table class="tbl roto-tbl">
          <thead><tr>
            <th class="left">Team</th>
            <th title="Eligible games in this phase">G</th>
            ${cols.map((c) => `<th title="${c.group} · ${c.label}">${c.label}</th>`).join("")}
            <th>Total Pts</th>
          </tr></thead>
          <tbody>
            ${displayTeams.map((t) => `
              <tr data-tid="${t.teamId}" class="${t.teamId === selected.teamId ? "on" : ""}">
                <td class="left">${esc(t.teamName)}</td>
                <td class="tnum mut">${t.games}</td>
                ${t.categories.map((c) =>
                  `<td class="tnum" style="background:${R.rankCellBg(c.rank, n)}" title="${c.label}: ${R.formatCatValue(c)} · rank #${c.rank}/${n}">${R.formatCatValue(c)}</td>`
                ).join("")}
                <td class="tnum gold">${t.totalPts}</td>
              </tr>`).join("")}
          </tbody>
        </table>
      </div>`;
    $("season-table").querySelectorAll("tr[data-tid]").forEach((tr) => {
      tr.onclick = () => { teamId = +tr.dataset.tid; render(); };
    });
    renderBreakdown(selected, n);
    renderRadar(selected, teams);
  }

  function renderCareer(career) {
    const el = $("career-table");
    $("career-sub").textContent = career.scoredYears.length
      ? `Mean roto placement across ${career.scoredYears.length} scored season${career.scoredYears.length === 1 ? "" : "s"} (${career.scoredYears[0]}–${career.scoredYears[career.scoredYears.length - 1]}) · lower is better`
      : "Career rollup";
    if (career.evidence === "Unavailable") {
      el.innerHTML = `<div class="empty">Career roto is unavailable — no season boxscores could be loaded.</div>`;
      return;
    }
    const gap = career.evidence === "Partial"
      ? `<p class="gap-note">${career.missingYears.join(", ")} could not be loaded and ${career.missingYears.length === 1 ? "is" : "are"} excluded from every average. Data gaps, not sit-outs.</p>`
      : "";
    el.innerHTML = gap + `
      <div class="table-scroll">
        <table class="tbl roto-tbl">
          <thead><tr>
            <th class="left">Manager</th><th>Seasons</th><th>Avg finish</th><th>Best</th><th>Worst</th><th>Avg pts</th>
            ${career.scoredYears.map((y) => `<th>${String(y).slice(2)}</th>`).join("")}
            ${career.missingYears.map((y) => `<th class="mut" title="${y} data unavailable">${String(y).slice(2)}</th>`).join("")}
          </tr></thead>
          <tbody>
            ${career.rows.map((c) => `
              <tr data-oid="${c.ownerId}" class="${c.ownerId === ownerId ? "on" : ""}">
                <td class="left">${esc(ownerName(c.ownerId))}</td>
                <td class="tnum">${c.seasons}</td>
                <td class="tnum gold">${c.avgRank.toFixed(2)}</td>
                <td class="tnum">${R.ordinal(c.bestRank)}</td>
                <td class="tnum">${R.ordinal(c.worstRank)}</td>
                <td class="tnum">${c.avgPts.toFixed(1)}</td>
                ${career.scoredYears.map((y) => {
                  const cell = c.byYear.get(y);
                  if (!cell) return `<td class="tnum mut" title="Did not play">—</td>`;
                  return `<td class="tnum" style="background:${R.rankCellBg(cell.rank, cell.nTeams)}">${cell.rank}</td>`;
                }).join("")}
                ${career.missingYears.map((y) => `<td class="tnum mut" title="${y} unavailable">?</td>`).join("")}
              </tr>`).join("")}
          </tbody>
        </table>
      </div>`;
    el.querySelectorAll("tr[data-oid]").forEach((tr) => {
      tr.onclick = () => { ownerId = tr.dataset.oid; render(); };
    });
  }

  function renderBreakdown(team, n) {
    $("break-sub").textContent = `#${team.totalRank} · ${team.totalPts} pts · ${team.games} games`;
    let last = "";
    $("breakdown").innerHTML = `
      <div class="table-scroll">
        <table class="tbl roto-tbl">
          <thead><tr>
            <th class="left">Group</th><th class="left">Category</th>
            <th>Value</th><th>Rank</th><th>Pts</th><th class="left">Strength</th>
          </tr></thead>
          <tbody>
            ${team.categories.map((c) => {
              const show = c.group !== last;
              last = c.group;
              const cells = Array.from({ length: n }, (_, i) => {
                const r = i + 1;
                const on = r === c.rank;
                return `<i class="str-cell${on ? " on" : ""}" style="background:${on ? R.rankCellBg(c.rank, n) : "#1c253644"}"></i>`;
              }).join("");
              return `<tr>
                <td class="left mut">${show ? c.group : ""}</td>
                <td class="left">${c.label}</td>
                <td class="tnum">${R.formatCatValue(c)}</td>
                <td class="tnum">#${c.rank}/${n}</td>
                <td class="tnum">${c.pts}</td>
                <td><div class="str-bar">${cells}</div></td>
              </tr>`;
            }).join("")}
            <tr>
              <td></td><td class="left">Total</td><td></td>
              <td class="tnum">#${team.totalRank}/${n}</td>
              <td class="tnum gold">${team.totalPts}</td><td></td>
            </tr>
          </tbody>
        </table>
      </div>`;
  }

  function renderRadar(team, teams) {
    const n = teams.length;
    const avg = R.leagueAverageNorm(teams);
    const best = [...team.categories].sort((a, b) => a.rank - b.rank)[0];
    const worst = [...team.categories].sort((a, b) => b.rank - a.rank).slice(0, 2);
    $("radar-sub").textContent = `${team.teamName} ranks ${team.totalRank} of ${n} · filled = this team · outline = league average`;
    $("radar-meta").innerHTML = `
      <div class="radar-chip good"><b>Strength</b><span>${best.label} · #${best.rank}/${n}</span></div>
      ${worst.map((w) => `<div class="radar-chip bad"><b>Weakness</b><span>${w.label} · #${w.rank}/${n}</span></div>`).join("")}`;
    if (radarChart) radarChart.destroy();
    const ctx = $("roto-radar");
    if (!ctx || typeof Chart === "undefined") return;
    radarChart = new Chart(ctx, {
      type: "radar",
      data: {
        labels: team.categories.map((c) => c.label),
        datasets: [
          {
            label: team.teamName,
            data: team.categories.map((c) => c.norm),
            backgroundColor: "rgba(0,162,255,0.28)",
            borderColor: "#00a2ff",
            borderWidth: 2,
            pointBackgroundColor: "#00a2ff",
            pointRadius: 3,
          },
          {
            label: "League avg",
            data: team.categories.map((c) => avg[c.key] || 0),
            backgroundColor: "rgba(125,138,160,0.08)",
            borderColor: "#7d8aa0",
            borderWidth: 1.5,
            borderDash: [4, 3],
            pointRadius: 0,
          },
        ],
      },
      options: {
        maintainAspectRatio: false,
        plugins: { legend: { labels: { boxWidth: 10, usePointStyle: true, pointStyle: "circle", color: "#7d8aa0" } } },
        scales: {
          r: {
            min: 0, max: 1,
            ticks: { display: false },
            grid: { color: "#1c2536" },
            angleLines: { color: "#1c2536" },
            pointLabels: { color: "#9fd8ff", font: { size: 11 } },
          },
        },
      },
    });
  }

  function renderCareerChart(career) {
    if (careerChart) careerChart.destroy();
    const ctx = $("career-chart");
    if (!ctx || typeof Chart === "undefined" || !career.scoredYears.length) return;
    const years = career.scoredYears;
    const focus = ownerId || (career.rows[0] && career.rows[0].ownerId);
    ownerId = focus;
    const rows = career.rows;
    const datasets = rows.map((c) => {
      const on = c.ownerId === focus;
      return {
        label: ownerName(c.ownerId),
        data: years.map((y) => {
          const cell = c.byYear.get(y);
          return cell ? cell.rank : null;
        }),
        borderColor: on ? "#00a2ff" : "#3a4a6388",
        backgroundColor: "transparent",
        borderWidth: on ? 2.5 : 1,
        pointRadius: on ? 3 : 0,
        spanGaps: true,
        tension: 0.2,
      };
    });
    careerChart = new Chart(ctx, {
      type: "line",
      data: { labels: years, datasets },
      options: {
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          y: {
            reverse: true, min: 1,
            title: { display: true, text: "finish", color: "#7d8aa0" },
            grid: { color: "#1c253644" },
            ticks: { color: "#7d8aa0", stepSize: 1 },
          },
          x: { grid: { display: false }, ticks: { color: "#7d8aa0" } },
        },
      },
    });
  }

  function renderCareerRadar(career) {
    const focus = ownerId || (career.rows[0] && career.rows[0].ownerId);
    if (!focus) return;
    const acc = {};
    let n = 0;
    const leagueAcc = {};
    let leagueN = 0;
    for (const load of loads) {
      const teams = R.computeCategoryStats(load.box, load.season, phase, false);
      if (!teams.length) continue;
      const avg = R.leagueAverageNorm(teams);
      leagueN += 1;
      R.CATS.forEach((cat) => { leagueAcc[cat.key] = (leagueAcc[cat.key] || 0) + (avg[cat.key] || 0); });
      const t = teams.find((x) => x.ownerId === focus);
      if (!t) continue;
      n += 1;
      t.categories.forEach((c) => { acc[c.key] = (acc[c.key] || 0) + c.norm; });
    }
    if (!n) return;
    const fake = {
      teamName: ownerName(focus),
      totalRank: (career.rows.find((r) => r.ownerId === focus) || {}).avgRank || 0,
      totalPts: 0,
      games: n,
      categories: R.CATS.map((cat) => ({
        key: cat.key, label: cat.label, group: cat.group,
        norm: acc[cat.key] / n,
        rank: 0, pts: 0, value: 0,
      })),
    };
    const dummyTeams = [fake];
    // reuse radar with career-average norms vs mean league-avg
    const avg = {};
    R.CATS.forEach((cat) => { avg[cat.key] = leagueN ? leagueAcc[cat.key] / leagueN : 0; });
    $("radar-sub").textContent = `${fake.teamName} · mean category shape across ${n} scored seasons · outline = league average`;
    const ranked = [...fake.categories].sort((a, b) => b.norm - a.norm);
    $("radar-meta").innerHTML = `
      <div class="radar-chip good"><b>Strength</b><span>${ranked[0].label}</span></div>
      <div class="radar-chip bad"><b>Weakness</b><span>${ranked[ranked.length - 1].label}</span></div>`;
    $("break-sub").textContent = `career-average norm · ${n} seasons`;
    $("breakdown").innerHTML = `
      <div class="table-scroll">
        <table class="tbl roto-tbl">
          <thead><tr><th class="left">Category</th><th>Mean strength</th></tr></thead>
          <tbody>
            ${fake.categories.map((c) => `<tr>
              <td class="left">${c.label}</td>
              <td class="tnum">${(c.norm * 100).toFixed(0)}</td>
            </tr>`).join("")}
          </tbody>
        </table>
      </div>`;
    if (radarChart) radarChart.destroy();
    const ctx = $("roto-radar");
    if (!ctx || typeof Chart === "undefined") return;
    radarChart = new Chart(ctx, {
      type: "radar",
      data: {
        labels: fake.categories.map((c) => c.label),
        datasets: [
          {
            label: fake.teamName,
            data: fake.categories.map((c) => c.norm),
            backgroundColor: "rgba(0,162,255,0.28)",
            borderColor: "#00a2ff",
            borderWidth: 2,
            pointBackgroundColor: "#00a2ff",
            pointRadius: 3,
          },
          {
            label: "League avg",
            data: fake.categories.map((c) => avg[c.key] || 0),
            backgroundColor: "rgba(125,138,160,0.08)",
            borderColor: "#7d8aa0",
            borderWidth: 1.5,
            borderDash: [4, 3],
            pointRadius: 0,
          },
        ],
      },
      options: {
        maintainAspectRatio: false,
        plugins: { legend: { labels: { boxWidth: 10, usePointStyle: true, pointStyle: "circle", color: "#7d8aa0" } } },
        scales: {
          r: {
            min: 0, max: 1,
            ticks: { display: false },
            grid: { color: "#1c2536" },
            angleLines: { color: "#1c2536" },
            pointLabels: { color: "#9fd8ff", font: { size: 11 } },
          },
        },
      },
    });
  }

  function esc(s) {
    return String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  }

  $("lede").textContent =
    "AFFL is a head-to-head points league, but every team's underlying NFL production also scores the way a 10-category rotisserie league would — passing, rushing, and receiving stats ranked across the league, each category worth 1 (worst) to n (best) points. Player-level boxscores begin in 2018 (ESPN history cutoff). Years without a boxscore file are not scored.";

  render();
})();
