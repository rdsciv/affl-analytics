/* ============ AFFL Scoreboard — all seasons ============ */
(async function () {
  // goTeam: squad deep-links live on Teams; scoreboard filters in place.

  const A = window.AFFL;
  const $ = (s) => document.querySelector(s);
  await A.boot();

  const TIER = { WINNERS_BRACKET: 'Playoffs', LOSERS_CONSOLATION_LADDER: 'Consolation',
                 WINNERS_CONSOLATION_LADDER: 'Consolation', NONE: '' };
  const SLOT_ORDER = { QB: 0, RB: 1, WR: 2, TE: 3, FLEX: 4, 'RB/WR': 4, 'WR/TE': 4, OP: 4, 'D/ST': 5, K: 6 };

  let year = A.years()[0];
  let week = null;
  let scope = A.scopeFromURL();
  let squad = A.squadFromURL();
  let YD = null, T = {}, ALL = null;
  let PRE_STARTS = {}, PRE_ROSTERS = {}, PINDEX = {};
  let INJ = {}, DEPTH = {}, Y2025 = null;
  let dropNotice = ""; // CHI-165 persistent season/squad mismatch notice
  const urlDropSquad = (new URLSearchParams(location.search).get("squad") || "");

  await Promise.all([
    fetch("pre2018_starts.json?v=" + Date.now(), { cache: "no-store" }).then((r) => r.ok ? r.json() : {}).catch(() => ({})),
    fetch("pre2018_rosters.json?v=" + Date.now(), { cache: "no-store" }).then((r) => r.ok ? r.json() : {}).catch(() => ({})),
    fetch("player_index.json?v=" + Date.now(), { cache: "no-store" }).then((r) => r.ok ? r.json() : {}).catch(() => ({})),
    fetch("injuries.json?v=" + Date.now(), { cache: "no-store" }).then((r) => r.ok ? r.json() : {}).catch(() => ({})),
    fetch("depthcharts.json?v=" + Date.now(), { cache: "no-store" }).then((r) => r.ok ? r.json() : {}).catch(() => ({})),
    A.loadYear(2025).catch(() => null),
  ]).then(([s, r, i, inj, depth, y25]) => {
    PRE_STARTS = s || {}; PRE_ROSTERS = r || {}; PINDEX = i || {};
    INJ = inj || {}; DEPTH = depth || {}; Y2025 = y25;
  });

  /* 2014–2016 year-JSON keys are matchup periods, not NFL weeks:
     1–13 = that NFL week; 14 = NFL 14–15 (R1); 15 = NFL 16–17 (Final).
     2017 is single-week playoffs; championship is period 16 only. */
  function twoWeekPlayoffs(y) { return y >= 2014 && y <= 2016; }

  function nflWeeksForPeriod(y, period) {
    const p = +period;
    if (twoWeekPlayoffs(y)) {
      if (p === 14) return [14, 15];
      if (p === 15) return [16, 17];
    }
    return [p];
  }

  function weekChipLabel(y, period) {
    const p = +period;
    if (twoWeekPlayoffs(y)) {
      if (p === 14) return "R1 · W14–15";
      if (p === 15) return "Final · W16–17";
      return "W" + p;
    }
    return "W" + p;
  }

  function isChampionshipPeriod(y, period, regWeeks) {
    const p = +period;
    if (twoWeekPlayoffs(y)) return p === 15;
    if (y === 2017) return p === 16;
    return p > (regWeeks || 13);
  }

  function weekViewSubtitle(y, period) {
    const p = +period;
    if (twoWeekPlayoffs(y)) {
      if (p === 14) return "Round 1 (NFL weeks 14–15)";
      if (p === 15) return "Championship (NFL weeks 16–17)";
    }
    if (y === 2017) {
      if (p === 16) return "Championship";
      if (p === 14 || p === 15) return "Playoff";
    }
    return "";
  }

  function playerName(pid) {
    const m = (YD && YD.pmeta || {})[String(pid)];
    if (m && m[0] && !A.unresolvedPlayerName(m[0])) return m[0];
    const idx = PINDEX[String(pid)];
    if (idx && idx.name && !A.unresolvedPlayerName(idx.name)) return idx.name;
    const snap = ((PRE_ROSTERS[String(year)] || {})[String(pid)]) || {};
    if (snap.name && !A.unresolvedPlayerName(snap.name)) return snap.name;
    return A.resolvePlayerName(pid, "");
  }

  function playerNfl(pid) {
    const m = (YD && YD.pmeta || {})[String(pid)];
    if (m && m[2]) return m[2];
    const idx = PINDEX[String(pid)];
    return (idx && (idx.nfl || idx.pro)) || "";
  }

  function playerCell(pid) {
    return A.playerLink(pid, playerName(pid), { cls: "sb-name link", year: year, squad: squad });
  }

  function franchiseDisplay(t, tid) {
    const owner = t && t.owner;
    const name = (owner && A.franchiseName(owner)) || (t && t.name) || ("Team " + tid);
    const logo = (owner && A.franchiseLogo(owner)) || (t && t.logo) || "";
    return { name: name, logo: logo, owner: owner };
  }

  function currentSquads() {
    /* CHI-154/162 — only franchises that actually played this season.
       Fat Cats (m06) must not appear on 2014; Thunder (m16) owns that year. */
    if (scope === "cum") {
      return A.squads().filter((f) => f.active || A.showFormer());
    }
    const list = (A.squadsForSeason && A.squadsForSeason(year)) || A.squads();
    return list.filter((f) => {
      if (A.franchisePlayedSeason && !A.franchisePlayedSeason(f.owner, year)) return false;
      if (f.active) return true;
      return !!(A.showFormer && A.showFormer());
    });
  }


  function paintDropNotice() {
    const el = document.getElementById("sb-drop-notice");
    if (!el) return;
    if (!dropNotice) {
      el.hidden = true;
      el.innerHTML = "";
      return;
    }
    el.hidden = false;
    el.innerHTML = A.notice(dropNotice);
  }

  function dropMessageFor(owner, y) {
    if (!owner) return "";
    const name = A.franchiseName(owner) || owner;
    if (+y === 2014 && A.canon(owner) === "m06") {
      return "Fairview Fat Cats did not play in 2014 — that seat was L.O.B. Thunder.";
    }
    return name + " did not play in " + y + ".";
  }

  function ensureSquadForYear() {
    if (scope === "cum") { dropNotice = ""; paintDropNotice(); return false; }
    const candidate = squad || "";
    if (candidate) {
      if (A.franchisePlayedSeason && A.franchisePlayedSeason(candidate, year)) {
        /* Valid for this year — clear any stale drop notice. */
        dropNotice = "";
        paintDropNotice();
        return false;
      }
      dropNotice = dropMessageFor(candidate, year);
      squad = "";
      A.rememberSquad("");
      const u = new URL(location.href);
      u.searchParams.delete("squad");
      history.replaceState(null, "", u.pathname.split("/").pop() + u.search + u.hash);
      paintDropNotice();
      return dropNotice;
    }
    /* Squad already cleared to All — keep sticky notice for this year if URL opened with an invalid franchise. */
    if (dropNotice) { paintDropNotice(); return dropNotice; }
    if (urlDropSquad && !(A.franchisePlayedSeason && A.franchisePlayedSeason(urlDropSquad, year))) {
      dropNotice = dropMessageFor(urlDropSquad, year);
      paintDropNotice();
      return dropNotice;
    }
    paintDropNotice();
    return false;
  }

  function squadTidFor(y, owner) {
    if (!owner) return null;
    const c = A.canon(owner);
    const ts = A.teams(y);
    for (const id of Object.keys(ts)) {
      const t = ts[id];
      if (t && A.canon(t.owner) === c) return t.id;
    }
    return null;
  }

  function gameHasSquad(g, y, owner) {
    if (!owner) return true;
    const tid = squadTidFor(y, owner);
    if (tid == null) return false;
    return A.sameId(g.home && g.home.tid, tid) || A.sameId(g.away && g.away.tid, tid);
  }

  function filterGames(games, y) {
    if (!squad) return games;
    return (games || []).filter((g) => gameHasSquad(g, y, squad));
  }

  function collectStarts(y, tid, nflWeeks) {
    const ymap = PRE_STARTS[String(y)] || {};
    const byPid = {};
    nflWeeks.forEach((wk) => {
      const key = String(wk);
      Object.keys(ymap).forEach((pid) => {
        const row = ymap[pid][key];
        if (!row || Number(row.tid) !== Number(tid)) return;
        if (!byPid[pid]) byPid[pid] = { weeks: {}, slot: row.slot || "—", last: -1 };
        byPid[pid].weeks[key] = row.pts;
        if (wk >= byPid[pid].last) {
          byPid[pid].slot = row.slot || byPid[pid].slot;
          byPid[pid].last = wk;
        }
      });
    });
    const rows = [];
    Object.keys(byPid).forEach((pid) => {
      const rec = byPid[pid];
      const vals = nflWeeks.map((w) => rec.weeks[String(w)])
        .filter((v) => v != null && v !== "");
      let pts = 0;
      if (vals.length === 2 && Number(vals[0]) === Number(vals[1])) pts = Number(vals[0]);
      else pts = vals.reduce((a, b) => a + Number(b || 0), 0);
      rows.push([pid, rec.slot || "—", pts]);
    });
    rows.sort((a, b) => (SLOT_ORDER[a[1]] ?? 9) - (SLOT_ORDER[b[1]] ?? 9));
    return rows;
  }

  function snapshotUnrecovered(y, tid, startedPids) {
    const ymap = PRE_ROSTERS[String(y)] || {};
    const out = [];
    Object.keys(ymap).forEach((pid) => {
      const rec = ymap[pid];
      if (rec.tid == null || Number(rec.tid) !== Number(tid)) return;
      if (startedPids.has(String(pid))) return;
      out.push({ pid: pid, name: rec.name || "", slot: rec.slot });
    });
    out.sort((a, b) => playerName(a.pid).localeCompare(playerName(b.pid)));
    return out;
  }

  function enrichSide(y, period, side) {
    if (y >= 2018) return { roster: side.roster || [], unrecovered: [] };
    if (side.roster && side.roster.length) return { roster: side.roster, unrecovered: [] };
    const weeks = nflWeeksForPeriod(y, period);
    const roster = collectStarts(y, side.tid, weeks);
    const started = new Set(roster.map((r) => String(r[0])));
    return { roster: roster, unrecovered: snapshotUnrecovered(y, side.tid, started) };
  }

  function starterRow(r) {
    return `<div class="sb-row">
        <span class="sb-slot">${A.esc(r[1])}</span>
        ${playerCell(r[0])}
        <span class="sb-nfl">${A.esc(playerNfl(r[0]) || "")}</span>
        <span class="sb-pts">${Number(r[2] || 0).toFixed(1)}</span>
      </div>`;
  }

  function unrecoveredRow(u) {
    const pos = playerNfl(u.pid);
    const meta = (YD && YD.pmeta || {})[String(u.pid)];
    const slot = (meta && meta[1]) || (PINDEX[String(u.pid)] && PINDEX[String(u.pid)].pos) || "—";
    return `<div class="sb-row">
        <span class="sb-slot">${A.esc(slot)}</span>
        ${playerCell(u.pid)}
        <span class="sb-nfl">${A.esc(pos || "")}</span>
        <span class="sb-pts">—</span>
      </div>`;
  }

  function rosterHTML(side, extra) {
    extra = extra || {};
    const starters = (side.roster || []).filter((r) => r[1] !== "BN" && r[1] !== "IR")
      .sort((a, b) => (SLOT_ORDER[a[1]] ?? 9) - (SLOT_ORDER[b[1]] ?? 9));
    const bench = (side.roster || []).filter((r) => r[1] === "BN" || r[1] === "IR")
      .sort((a, b) => b[2] - a[2]);
    const unrecovered = extra.unrecovered || [];
    if (!starters.length && !bench.length && !unrecovered.length) return "";
    const benchPts = bench.reduce((a, r) => a + r[2], 0);
    const benchBlock = (year >= 2018 && bench.length)
      ? `<details class="sb-bench"><summary>Bench · ${benchPts.toFixed(1)} pts unused</summary>${bench.map(starterRow).join("")}</details>`
      : "";
    const recBlock = unrecovered.length
      ? `<details class="sb-bench sb-unrecovered"><summary>On roster (start not recovered)</summary>${unrecovered.map(unrecoveredRow).join("")}</details>`
      : "";
    return `${starters.map(starterRow).join("")}${benchBlock}${recBlock}`;
  }

  function gameCard(g, y, teams, yd, period) {
    const hWin = g.home.pts > g.away.pts;
    const prevY = year; const prevYD = YD; const prevT = T;
    year = y; YD = yd; T = teams;
    const side = (s, win) => {
      const t = T[s.tid] || { name: "Team " + s.tid };
      const ident = franchiseDisplay(t, s.tid);
      const filled = enrichSide(y, period, s);
      return `<div class="sb-team${win ? " win" : ""}">
        <div class="sb-team-head">
          ${A.logoHTML(ident)}
          <div class="sb-team-name">${A.esc(ident.name)}</div>
          <div class="sb-total${win ? " w" : ""}">${s.pts.toFixed(1)}</div>
        </div>
        ${rosterHTML({ roster: filled.roster }, { unrecovered: filled.unrecovered })}
      </div>`;
    };
    const tier = TIER[g.tier] || "";
    const html = `<div class="card sb-card" data-home="${g.home.tid}" data-away="${g.away.tid}">
        ${tier ? `<div class="sb-tier">${tier}</div>` : ""}
        <div class="sb-match">
          ${side(g.away, !hWin)}<div class="sb-vs">VS</div>${side(g.home, hWin)}
        </div>
      </div>`;
    year = prevY; YD = prevYD; T = prevT;
    return html;
  }


  const INJ_RANK = { Out: 0, "Injured Reserve": 1, Doubtful: 2, Questionable: 3, Suspension: 4 };

  function injStatusRank(st) {
    if (!st) return 80;
    if (INJ_RANK[st] != null) return INJ_RANK[st];
    if (/^active$/i.test(st) || /^healthy$/i.test(st)) return 90;
    return 50;
  }

  function renderNflInjuries() {
    const card = document.getElementById("nfl-injury-card");
    const list = document.getElementById("nfl-injury-list");
    const countEl = document.getElementById("nfl-injury-count");
    if (!card || !list) return;
    /* CHI-165 — injury cache is current season only. Never paint 2025 injuries on 2014. */
    const ys = (A.years && A.years()) || [];
    const injYear = ys.length ? Math.max.apply(null, ys.map(Number)) : 2025;
    const caption = card.querySelector(".nfl-inj-caption");
    const historic = (scope === "season" && year && +year !== +injYear) || scope === "cum";
    if (historic) {
      card.setAttribute("data-inj-scope", "historic");
      if (countEl) countEl.textContent = "n/a · " + (scope === "cum" ? "current only" : String(year));
      if (caption) {
        caption.textContent = scope === "cum"
          ? ("NFL injury report covers the current season (" + injYear + ") only — pick " + injYear + " to view.")
          : ("NFL injury report covers " + injYear + " only — not available for " + year + ".");
      }
      list.innerHTML = '<div class="nfl-inj-empty">No historic injury cache — current-season injuries are hidden for this year.</div>';
      return;
    }
    card.setAttribute("data-inj-scope", "current");
    if (caption) caption.textContent = "NFL injury/depth from local cache — not AFFL roster status.";
    const teams = A.teams(injYear);
    const affl = {};
    (Y2025 && Y2025.players || []).forEach((p) => {
      if (p && p.pid != null) affl[String(p.pid)] = p;
    });
    let rows = [];
    Object.keys(INJ).forEach((aid) => {
      const rec = INJ[aid] || {};
      const p = affl[aid];
      if (!p) return;
      const t = teams[p.mainTeam] || {};
      const owner = t.owner;
      const franchise = (owner && A.franchiseName(owner)) || t.name || "";
      const depth = (DEPTH[aid] && DEPTH[aid].depth) || "";
      rows.push({
        pid: aid,
        name: rec.name || p.name || "",
        status: rec.status || "",
        comment: rec.comment || "",
        team: rec.team || p.nfl || "",
        franchise: franchise,
        owner: owner || "",
        tid: p.mainTeam,
        depth: depth,
        date: rec.date || "",
      });
    });
    if (squad) {
      const c = A.canon(squad);
      const tid = squadTidFor(injYear, squad);
      if (tid == null) rows = [];
      else rows = rows.filter((r) =>
        (tid != null && A.sameId(r.tid, tid)) || (r.owner && A.canon(r.owner) === c));
    }
    rows.sort((a, b) => injStatusRank(a.status) - injStatusRank(b.status)
      || String(a.name).localeCompare(String(b.name)));
    const designations = rows.filter((r) => injStatusRank(r.status) < 80);
    const shown = designations.length ? designations : rows.slice(0, 8);
    if (countEl) {
      countEl.textContent = designations.length
        ? (designations.length + " AFFL")
        : (rows.length ? rows.length + " notes" : "none");
    }
    if (!rows.length) {
      list.innerHTML = squad
        ? '<div class="nfl-inj-empty">No injured AFFL players for this squad.</div>'
        : '<div class="nfl-inj-empty">No AFFL-rostered players in the NFL injury cache.</div>';
      return;
    }
    if (!designations.length) {
      list.innerHTML = '<div class="nfl-inj-empty">No Out / Doubtful / Questionable / IR designations for AFFL-rostered players.</div>'
        + shown.map(injRowHTML).join("");
      return;
    }
    list.innerHTML = shown.map(injRowHTML).join("");
  }

  function injRowHTML(r) {
    const st = r.status || "";
    const cls = /out|reserve|^ir$/i.test(st) ? "out"
      : /doubt/i.test(st) ? "doubt"
      : /quest/i.test(st) ? "q"
      : /susp/i.test(st) ? "susp"
      : "active";
    const depth = r.depth ? `<span class="nfl-inj-depth">${A.esc(r.depth)}</span>` : "";
    const fr = r.franchise ? `<span class="nfl-inj-fr">${A.esc(r.franchise)}</span>` : "";
    return `<div class="nfl-inj-row">
      <span class="nfl-inj-st ${cls}">${A.esc(st || "—")}</span>
      ${A.playerLink(r.pid, r.name, { cls: "nfl-inj-name link", year: (A.years && A.years()[0]) || 2025, squad: squad })}
      <span class="nfl-inj-meta">${A.esc(r.team || "")}${depth}${fr}</span>
    </div>`;
  }

  function setSubtitle() {
    if (scope === "cum") {
      $("#sb-sub").textContent = `Cumulative · week ${week || "—"} across every season`;
      return;
    }
    const special = weekViewSubtitle(year, week);
    if (special) {
      $("#sb-sub").textContent = `${year} · ${special}`;
      return;
    }
    const recovered = year < 2018 && Object.keys(PRE_STARTS[String(year)] || {}).length;
    $("#sb-sub").textContent = `${year} · ${YD && YD.hasRosters ? "full lineups" : (recovered ? "recovered starters" : "scores only")}`;
  }

  function render() {
    if (scope === "cum") { renderCum(); return; }
    const dropped = ensureSquadForYear();
    if (dropped) drawSquadFilter();
    const dropMsg = dropNotice || "";
    const weeks = Object.keys(YD.weeks || {}).map(Number).sort((a, b) => a - b);
    if (!weeks.length) {
      $("#week-picker").innerHTML = "";
      paintDropNotice();
      $("#sb-grid").innerHTML = A.notice(
        `ESPN has no matchup data stored for ${year}.`);
      setSubtitle();
      return;
    }
    if (!weeks.includes(week)) week = weeks[0];

    $("#week-picker").innerHTML = weeks.map((w) =>
      `<button class="season-chip${w === week ? " on" : ""}" data-w="${w}">${weekChipLabel(year, w)}${isChampionshipPeriod(year, w, YD.regWeeks) ? " 🏆" : ""}</button>`).join("");
    $("#week-picker").querySelectorAll(".season-chip").forEach((b) =>
      b.addEventListener("click", () => { week = +b.dataset.w; render(); }));

    let games = filterGames([...YD.weeks[String(week)]], year);
    games.sort((a, b) =>
      (a.tier === "WINNERS_BRACKET" ? 0 : 1) - (b.tier === "WINNERS_BRACKET" ? 0 : 1));

    let banner = "";
    if (!YD.hasRosters) {
      banner = A.notice(
        `ESPN compacted weekly lineups for ${year}. Showing recovered starters where we have them; snapshot players without a start row are listed as start not recovered.`);
    }

    const note = weekViewSubtitle(year, week);
    const noteHTML = note ? `<div class="sb-week-note">${A.esc(note)}</div>` : "";

    paintDropNotice();
    const cards = games.length
      ? games.map((g) => gameCard(g, year, T, YD, week)).join("")
      : A.notice(squad ? "No matchup for this squad this week." : "No games stored.");
    $("#sb-grid").innerHTML = banner + noteHTML + cards;
    setSubtitle();
  }

  function renderCum() {
    const weekSet = new Set();
    ALL.forEach(({ data }) => Object.keys(data.weeks || {}).forEach((w) => weekSet.add(+w)));
    const weeks = [...weekSet].sort((a, b) => a - b);
    if (!weeks.length) {
      $("#week-picker").innerHTML = "";
      $("#sb-grid").innerHTML = A.notice("No matchup data stored.");
      setSubtitle();
      return;
    }
    if (!weeks.includes(week)) week = weeks[0];
    $("#week-picker").innerHTML = weeks.map((w) =>
      `<button class="season-chip${w === week ? " on" : ""}" data-w="${w}">W${w}</button>`).join("");
    $("#week-picker").querySelectorAll(".season-chip").forEach((b) =>
      b.addEventListener("click", () => { week = +b.dataset.w; render(); }));

    const chunks = [];
    for (const { year: y, data } of ALL) {
      let games = data.weeks && data.weeks[String(week)];
      if (!games || !games.length) continue;
      games = filterGames(games, y);
      if (!games.length) continue;
      const teams = A.teams(y);
      const sorted = [...games].sort((a, b) =>
        (a.tier === "WINNERS_BRACKET" ? 0 : 1) - (b.tier === "WINNERS_BRACKET" ? 0 : 1));
      const special = weekViewSubtitle(y, week);
      const label = special ? special : `week ${week}`;
      chunks.push(`<div class="section-break"><h2>${y} <span>${A.esc(label)}</span></h2></div>` +
        sorted.map((g) => gameCard(g, y, teams, data, week)).join(""));
    }
    $("#sb-grid").innerHTML = chunks.join("") || A.notice(`No games stored for week ${week}.`);
    setSubtitle();
  }

  async function pick(y) {
    if (+y !== +year) dropNotice = "";
    year = y;
    week = week;
    $("#sb-grid").innerHTML = '<div class="loading">Loading…</div>';
    if (scope === "cum") {
      ALL = ALL || await A.loadAllYears();
      YD = ALL.find((x) => x.year === year)?.data || ALL[0].data;
      T = A.teams(year);
    } else {
      YD = await A.loadYear(y);
      T = A.teams(y);
    }
    ensureSquadForYear();
    draw();
    render();
    paintDropNotice();
    renderNflInjuries();
  }


  function drawSquadFilter() {
    const el = document.getElementById("squad-picker");
    if (!el) return;
    const list = currentSquads();
    const bits = [`<button type="button" class="season-chip${squad ? "" : " on"}" data-squad="">All</button>`];
    list.forEach((f) => {
      const name = A.franchiseName(f.owner) || f.currentName || "";
      const short = A.shortTeam(f.owner) || name;
      const on = !!(squad && A.canon(squad) === A.canon(f.owner));
      bits.push(`<button type="button" class="season-chip${on ? " on" : ""}" data-squad="${A.esc(f.owner)}" data-tid="${A.esc(squadTidFor(year, f.owner) || "")}" title="${A.esc(name)}">${A.esc(short)}</button>`);
    });
    el.innerHTML = bits.join("");
    el.querySelectorAll("button").forEach((b) => {
      b.addEventListener("click", () => {
        squad = b.dataset.squad || "";
        dropNotice = "";
        paintDropNotice();
        A.rememberSquad(squad);
        const u = new URL(location.href);
        if (squad) u.searchParams.set("squad", squad);
        else u.searchParams.delete("squad");
        history.replaceState(null, "", u.pathname.split("/").pop() + u.search + u.hash);
        A.stampNav(squad);
        drawSquadFilter();
        render();
        renderNflInjuries();
      });
    });
  }

  function draw() {
    A.scopePicker(document.getElementById("scope-picker"), scope, (s) => {
      scope = s;
      A.showYearRow(s === "season");
      pick(year);
    });
    drawSquadFilter();
    A.stampNav(squad);
    A.showYearRow(scope === "season");
    A.yearPicker($("#year-picker"), year, (yy) => { week = null; pick(yy); }, (i) => i.hasRosters ? "" : "*");
    setSubtitle();
  }

  const qs = new URLSearchParams(location.search);
  if (qs.get("week")) week = +qs.get("week");
  await pick(+qs.get("year") || A.years()[0]);
})();
