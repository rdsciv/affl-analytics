/* Roto page — CHI-149 All grain, CHI-150 click-to-sort standings. Season All | year (default All). All = career over scored seasons 2018–2025. */
(async function () {
  const A = window.AFFL;
  await A.boot();
  const R = window.AFFLRoto;
  const root = "pillars/";

  const phaseNoteSeason = {
    reg: "Regular season only — every team plays the same number of games, so category totals are directly comparable.",
    post: "Winners-bracket games only. Teams play unequal numbers of playoff games (byes, 2- vs 3-game paths), so totals are not directly comparable — the games column shows each team’s sample.",
    combined: "Regular season + winners bracket. Consolation games are excluded. Playoff teams play more games than eliminated ones, so counting totals favor deeper runs.",
  };
  const phaseNoteAll = {
    reg: "Career roto covers 2018–2025, the years with full player category boxscores (pass / rush / rec). Career G = franchise H2H tenure; Scored G = roto sample 2018–2025. 2014–2017 still show on Scoreboard (starters + fantasy points + team scores), but those years have no category lines for roto, so they stay out. Counting stats default to per-season averages, or career sums on Totals. Rates are pooled career rates (cmp/att, yards/carry, yards/reception) — never an average of yearly rates. Ranks and TOTAL PTS use what’s on screen.",
    post: "Career postseason roto over scored seasons that have winners-bracket games. Teams play unequal playoff paths — G is the sample, not a common schedule.",
    combined: "Career combined (regular + winners bracket) over scored seasons 2018–2025. Playoff teams add extra games; counting totals favor deeper runs.",
  };

  const league = await fetch(root + "league.json").then((r) => r.json());
  const scoredYears = R.SCORED_YEARS.slice();
  const attempted = await Promise.all(scoredYears.map(async (year) => {
    const season = (league.seasons || []).find((s) => s.year === year);
    try {
      const res = await fetch(root + "boxscores/" + year + ".json");
      if (!res.ok) return { year, season, box: null };
      return { year, season, box: await res.json() };
    } catch (e) {
      return { year, season, box: null };
    }
  }));
  const loads = attempted.filter((l) => l.box && l.season);

  let year = A.seasonFromURL();
  let squad = A.squadFromURL() || "";
  let phase = "reg";
  let grain = "averages";
  let focusOwner = squad || "";
  let radarChart = null;
  let careerChart = null;
  let sortKey = "totalPts";
  let sortDir = -1;
  let lastTable = { teams: [], selected: null, allMode: false };

  const $ = (id) => document.getElementById(id);
  const MERGE = A.MERGE || { m01: "m07", m03: "m08", m20: "m10" };
  function canon(id) {
    if (A.canon) return A.canon(id);
    if (id == null || id === "") return id;
    return MERGE[String(id)] || String(id);
  }
  function ownerOf(y, teamId) {
    const oid = A.ownerId(y, teamId);
    return oid ? canon(oid) : "";
  }
  function decorateSeason(teams, y) {
    return (teams || []).map((t) => {
      const oid = ownerOf(y, t.teamId);
      const ft = oid ? A.franchiseTeam(oid) : { owner: "", name: t.teamName, logo: "" };
      return Object.assign({}, t, {
        ownerId: oid,
        teamName: ft.name || t.teamName,
        logo: ft.logo || "",
      });
    });
  }
  function careerGFor(oid) {
    const f = ((A.data && A.data.franchises) || []).find((x) => canon(x.owner) === canon(oid));
    if (!f) return 0;
    return (f.wins || 0) + (f.losses || 0) + (f.ties || 0);
  }

  function decorateAll(teams) {
    return (teams || []).map((t) => {
      const oid = canon(t.ownerId);
      const ft = oid ? A.franchiseTeam(oid) : { owner: oid, name: t.teamName, logo: "" };
      return Object.assign({}, t, {
        ownerId: oid,
        teamName: ft.name || t.teamName,
        logo: ft.logo || "",
        careerG: careerGFor(oid),
      });
    });
  }

  function applyYear(y) {
    year = (y == null || y === "" || y === "all") ? null : +y;
    if (year != null && squad && !A.franchisePlayedSeason(squad, year)) {
      squad = "";
      focusOwner = "";
      A.rememberSquad("");
    }
    render();
  }

  function paintUnavailable(y) {
    $("stand-h2").textContent = "Roto Standings";
    $("season-sub").textContent = y + " · categories unavailable";
    $("season-table").innerHTML =
      `<div class="empty roto-unavailable">Roto categories are unavailable for ${y}. Full player category boxscores (pass / rush / rec) start in 2018 — 2014–2017 still show on Scoreboard, but have no category lines for roto. This year is not scored as zeros.</div>`;
    $("breakdown").innerHTML = "";
    $("radar-sub").textContent = "";
    $("radar-meta").innerHTML = "";
    $("break-sub").textContent = "";
    if (radarChart) { radarChart.destroy(); radarChart = null; }
    if (careerChart) { careerChart.destroy(); careerChart = null; }
    $("career-graph-block").hidden = true;
    $("graphs-block").hidden = true;
  }

  function teamCell(t) {
    const ft = { owner: t.ownerId, name: t.teamName, logo: t.logo };
    const href = t.ownerId ? ("teams.html?squad=" + encodeURIComponent(t.ownerId)) : "#";
    return `<div class="team-cell">${A.logoHTML(ft, "mini")}<div><a class="hist-name" href="${href}">${esc(t.teamName)}</a></div></div>`;
  }

  function missingSortVal(v) {
    return v == null || v === "" || v === "—" || (typeof v === "number" && Number.isNaN(v));
  }

  function sortValue(t, key) {
    if (key === "team") return t.teamName || "";
    if (key === "careerG") return t.careerG;
    if (key === "g") return t.games;
    if (key === "totalPts") return t.totalPts;
    const c = (t.categories || []).find((x) => x.key === key);
    return c ? c.value : null;
  }

  function firstDirFor(key) {
    return key === "team" ? 1 : -1;
  }

  function columnExists(key, cols) {
    if (key === "team" || key === "g" || key === "totalPts") return true;
    if (key === "careerG") return !!(lastTable && lastTable.allMode);
    return (cols || []).some((c) => c.key === key);
  }

  function ensureSortKey(cols) {
    if (!columnExists(sortKey, cols)) {
      sortKey = "totalPts";
      sortDir = -1;
    }
  }

  function sortTeams(teams, key, dir) {
    return (teams || []).slice().sort((a, b) => {
      const av = sortValue(a, key);
      const bv = sortValue(b, key);
      const aMiss = key === "team" ? (av == null || av === "") : missingSortVal(av);
      const bMiss = key === "team" ? (bv == null || bv === "") : missingSortVal(bv);
      if (aMiss && bMiss) {
        return String(a.teamName || "").localeCompare(String(b.teamName || ""), undefined, { sensitivity: "base" });
      }
      if (aMiss) return 1;
      if (bMiss) return -1;
      let d;
      if (key === "team" || typeof av === "string" || typeof bv === "string") {
        d = String(av).localeCompare(String(bv), undefined, { sensitivity: "base" });
      } else {
        d = Number(av) - Number(bv);
      }
      d *= dir;
      if (d) return d;
      return String(a.teamName || "").localeCompare(String(b.teamName || ""), undefined, { sensitivity: "base" });
    });
  }

  function thClass(key) {
    const on = sortKey === key;
    return "s" + (on ? " on" : "") + (on && sortDir > 0 ? " asc" : "");
  }

  function renderTable(teams, selected, allMode) {
    lastTable = { teams: teams || [], selected: selected, allMode: !!allMode };
    const n = (teams || []).length;
    const cols = (selected && selected.categories) || (teams[0] && teams[0].categories) || [];
    ensureSortKey(cols);
    const ranked = sortTeams(teams, sortKey, sortDir);
    $("season-table").innerHTML = `
      <div class="table-scroll">
        <table class="tbl roto-tbl">
          <thead><tr>
            <th class="left ${thClass("team")}" data-k="team">Team</th>
            ${allMode ? `<th class="${thClass("careerG")}" data-k="careerG" title="Career H2H games = franchise wins + losses + ties (same source as Franchise Records). Fat Cats 148 from 2015–2025; Feelers 161.">Career G</th>` : ""}
            <th class="${thClass("g")}" data-k="g" title="${allMode ? (grain === "averages" ? "Mean regular-season games per scored roto year (2018–2025). Not career H2H games." : "Sum of regular-season games in scored roto years only (2018–2025). Not career H2H — e.g. Fat Cats H2H is 148 from 2015–2025.") : "Eligible games in this phase"}">${allMode ? (grain === "averages" ? "G/yr" : "Scored G") : "G"}</th>
            ${cols.map((c) => `<th class="${thClass(c.key)}" data-k="${c.key}" title="${c.group} · ${c.label}">${c.label}</th>`).join("")}
            <th class="${thClass("totalPts")}" data-k="totalPts">Total Pts</th>
          </tr></thead>
          <tbody>
            ${ranked.map((t) => `
              <tr data-oid="${esc(t.ownerId || "")}" class="${t.ownerId && t.ownerId === (selected && selected.ownerId) ? "on" : ""}">
                <td class="left">${teamCell(t)}</td>
                ${allMode ? `<td class="tnum mut">${t.careerG == null || Number.isNaN(Number(t.careerG)) ? "—" : Number(t.careerG)}</td>` : ""}
                <td class="tnum mut">${R.formatGames(t.games, grain, allMode)}</td>
                ${t.categories.map((c) => {
                  const miss = c.value == null || Number.isNaN(Number(c.value));
                  const bg = miss ? "transparent" : R.rankCellBg(c.rank, n);
                  const tip = miss ? (c.label + ": unavailable") : (c.label + ": " + R.formatCatValue(c) + " · rank #" + c.rank + "/" + n);
                  return `<td class="tnum" style="background:${bg}" title="${tip}">${R.formatCatValue(c)}</td>`;
                }).join("")}
                <td class="tnum gold">${t.totalPts}</td>
              </tr>`).join("")}
          </tbody>
        </table>
      </div>`;
    $("season-table").querySelectorAll("thead th.s").forEach((th) => {
      th.onclick = (e) => {
        e.preventDefault();
        const k = th.dataset.k;
        if (!k) return;
        if (sortKey === k) sortDir = -sortDir;
        else {
          sortKey = k;
          sortDir = firstDirFor(k);
        }
        renderTable(lastTable.teams, lastTable.selected, lastTable.allMode);
      };
    });
    $("season-table").querySelectorAll("tr[data-oid]").forEach((tr) => {
      tr.onclick = () => {
        focusOwner = tr.dataset.oid || "";
        render();
      };
    });
  }

  function render() {
    A.seasonSelect($("year-picker"), year, applyYear, A.years());
    A.stampSeason(year);
    const liveSquad = A.remountTeamSelect($("squad-picker"), squad, (s) => {
      squad = s || "";
      focusOwner = squad || focusOwner;
      A.stampNav(squad);
      if (squad && year != null && !A.franchisePlayedSeason(squad, year)) {
        applyYear(null);
        return;
      }
      render();
    }, year);
    if (liveSquad !== undefined) squad = liveSquad || "";
    A.stampNav(squad);
    if (squad) focusOwner = canon(squad);

    const allMode = year == null;
    const grainRow = $("grain-row");
    if (grainRow) grainRow.hidden = !allMode;
    $("grain-picker").innerHTML = [["averages", "Averages"], ["totals", "Totals"]].map(([v, l]) =>
      `<button class="season-chip${v === grain ? " on" : ""}" data-g="${v}">${l}</button>`
    ).join("");
    $("grain-picker").querySelectorAll("button").forEach((b) => {
      b.onclick = () => { grain = b.dataset.g; render(); };
    });

    $("phase-picker").innerHTML = ["reg", "post", "combined"].map((p) =>
      `<button class="season-chip${p === phase ? " on" : ""}" data-phase="${p}">${R.PHASE_LABEL[p]}</button>`
    ).join("");
    $("phase-picker").querySelectorAll("button").forEach((b) => {
      b.onclick = () => { phase = b.dataset.phase; render(); };
    });

    $("phase-note").textContent = allMode ? phaseNoteAll[phase] : phaseNoteSeason[phase];

    if (!allMode && R.isUnavailableYear(year)) {
      paintUnavailable(year);
      return;
    }

    $("graphs-block").hidden = false;
    $("career-graph-block").hidden = !allMode;
    $("stand-h2").textContent = allMode ? "Career Roto" : "Roto Standings";

    if (allMode) {
      const built = R.buildAllRoto(loads, phase, grain, { ownerOf, skipOwners: { m22: true } });
      const teams = decorateAll(built.teams);
      if (!teams.length) {
        $("season-table").innerHTML = `<div class="empty">Career roto is unavailable — no scored seasons could be loaded.</div>`;
        $("graphs-block").hidden = true;
        $("career-graph-block").hidden = true;
        return;
      }
      const selected = teams.find((t) => t.ownerId && t.ownerId === canon(focusOwner)) || teams[0];
      focusOwner = selected.ownerId;
      const grainLabel = grain === "totals" ? "career totals" : "per-season averages";
      $("season-sub").textContent =
        `All · ${grainLabel} · Career G = franchise H2H tenure · Scored G = roto sample 2018–2025 · scored seasons ${built.scoredYears[0]}–${built.scoredYears[built.scoredYears.length - 1]} · ${R.PHASE_LABEL[phase]} · cells colored by rank on this grain · TOTAL PTS is the sum of category ranks of the displayed numbers · current franchise names`;
      renderTable(teams, selected, true);
      renderBreakdown(selected, teams.length, allMode);
      renderRadar(selected, teams);
      renderCareerChart(teams);
      return;
    }

    const load = loads.find((l) => l.year === year);
    if (!load || !load.box || !load.season) {
      paintUnavailable(year);
      return;
    }
    const rawTeams = R.computeCategoryStats(load.box, load.season, phase, false);
    const teams = decorateSeason(rawTeams, year);
    if (!teams.length) {
      $("season-table").innerHTML = `<div class="empty">No ${R.PHASE_LABEL[phase].toLowerCase()} games scored for ${year}.</div>`;
      $("breakdown").innerHTML = "";
      $("graphs-block").hidden = true;
      return;
    }
    const selected = teams.find((t) => t.ownerId && t.ownerId === canon(focusOwner)) || teams[0];
    focusOwner = selected.ownerId;
    $("season-sub").textContent =
      `Cells colored by category rank (green = best, red = worst) · Pts is category rank · ${year} · ${R.PHASE_LABEL[phase]} · current franchise names`;
    renderTable(teams, selected, false);
    renderBreakdown(selected, teams.length, false);
    renderRadar(selected, teams);
  }

  function renderBreakdown(team, n, allMode) {
    const gLabel = R.formatGames(team.games, grain, allMode);
    $("break-sub").textContent = `#${team.totalRank} · ${team.totalPts} pts · ${gLabel} ${allMode ? (grain === "averages" ? "G/yr" : "scored G") : "G"}` +
      (allMode && team.nSeasons ? ` · ${team.nSeasons} scored season${team.nSeasons === 1 ? "" : "s"}` : "");
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
    const labels = team.categories.map((c) => c.label);
    radarChart = new Chart(ctx, {
      type: "radar",
      data: {
        labels,
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
            ticks: { display: false, count: 5 },
            grid: { color: "#1c2536" },
            angleLines: { color: "#1c2536" },
            pointLabels: { color: "#9fd8ff", font: { size: 11 } },
          },
        },
      },
    });
  }

  function renderCareerChart(allTeams) {
    if (careerChart) careerChart.destroy();
    const ctx = $("career-chart");
    const years = R.SCORED_YEARS.slice();
    if (!ctx || typeof Chart === "undefined" || !years.length) return;
    const byOwner = {};
    for (const load of loads) {
      const teams = decorateSeason(R.computeCategoryStats(load.box, load.season, phase, false), load.year);
      for (const t of teams) {
        if (!t.ownerId) continue;
        if (!byOwner[t.ownerId]) {
          const ft = A.franchiseTeam(t.ownerId);
          byOwner[t.ownerId] = { ownerId: t.ownerId, name: ft.name || t.teamName, byYear: {} };
        }
        byOwner[t.ownerId].byYear[load.year] = t.totalRank;
      }
    }
    const focus = canon(focusOwner) || (allTeams[0] && allTeams[0].ownerId);
    const names = Object.keys(byOwner).map((oid) => byOwner[oid].name).filter(Boolean);
    const datasets = Object.keys(byOwner).map((oid) => {
      const c = byOwner[oid];
      const on = oid === focus;
      return {
        label: c.name,
        data: years.map((y) => (c.byYear[y] != null ? c.byYear[y] : null)),
        borderColor: on ? "#00a2ff" : "#3a4a6388",
        backgroundColor: "transparent",
        borderWidth: on ? 2.5 : 1,
        pointRadius: on ? 3 : 0,
        spanGaps: true,
        tension: 0.2,
      };
    });
    const maxFinish = Math.max(12, ...datasets.flatMap((d) => d.data.filter((v) => v != null)));
    careerChart = new Chart(ctx, {
      type: "line",
      data: { labels: years.map(String), datasets },
      options: {
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          y: {
            reverse: true,
            min: 1,
            max: maxFinish,
            title: { display: true, text: "finish", color: "#7d8aa0" },
            grid: { color: "#1c253644" },
            ticks: { color: "#7d8aa0", stepSize: 1 },
          },
          x: {
            title: { display: true, text: "season", color: "#7d8aa0" },
            grid: { display: false },
            ticks: { color: "#7d8aa0" },
          },
        },
      },
    });
    void names;
  }

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  }

  $("lede").textContent =
    "AFFL is a head-to-head points league, but every team's underlying NFL production also scores the way a 10-category rotisserie league would — passing, rushing, and receiving stats ranked across the league, each category worth 1 (worst) to n (best) points. Career G = franchise H2H tenure; Scored G = roto sample 2018–2025. 2014–2017 still show on Scoreboard but stay out of roto. All defaults to per-season averages so a long-running franchise does not win by existing.";

  render();
})();
