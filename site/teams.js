/* AFFL Teams — one franchise's record, games, draft, trades, roster, roto. */
(async function () {
  const A = window.AFFL;
  const R = window.AFFLRoto;
  const $ = (id) => document.getElementById(id);
  await A.boot();
  if (typeof Chart !== "undefined") A.chartDefaults(Chart);

  const LEADERS = await fetch("franchise_leaders.json?v=" + Date.now(), { cache: "no-store" })
    .then((r) => (r.ok ? r.json() : {}))
    .catch(() => ({}));
  const MOVES = await fetch("moves.json?v=" + Date.now(), { cache: "no-store" })
    .then((r) => (r.ok ? r.json() : {}))
    .catch(() => ({}));
  const PRE2018_SEASON_ROSTERS = await fetch("pre2018_season_rosters.json?v=" + Date.now(), { cache: "no-store" })
    .then((r) => (r.ok ? r.json() : {}))
    .catch(() => ({}));
  const NGS_PROFILES = await fetch("ngs_profiles.json?v=" + Date.now(), { cache: "no-store" })
    .then((r) => (r.ok ? r.json() : { franchises: [] }))
    .catch(() => ({ franchises: [] }));
  const TEAM_ACT = await fetch("team_activity.json?v=" + Date.now(), { cache: "no-store" })
    .then((r) => (r.ok ? r.json() : null))
    .catch(() => null);
  let actChart = null;

  function movesBag(y, tid) {
    const bag = MOVES[String(y)] || {};
    if (tid == null) return null;
    return bag[String(tid)] || bag[tid] || null;
  }

  function movesCount(y, tid) {
    const b = movesBag(y, tid);
    return b && b.moves != null ? Number(b.moves) : null;
  }

  const qs = new URLSearchParams(location.search);
  function teamScopeFromURL() {
    return new URLSearchParams(location.search).get("scope") === "season" ? "season" : "cum";
  }
  let scope = teamScopeFromURL();
  let squad = A.squadFromURL();
  let year = +qs.get("year") || A.years()[0];
  year = A.clampYear(year, squad);

  let radarChart = null;
  let spendChart = null;
  let pillars = null;
  let openPid = null;
  let rosterCache = { players: [], y: null };
  let draftPicks = [];
  let draftSortKey = "year";
  let draftSortDir = -1;

  const TIER = {
    WINNERS_BRACKET: "Playoffs",
    LOSERS_CONSOLATION_LADDER: "Consolation",
    WINNERS_CONSOLATION_LADDER: "Consolation",
    NONE: "",
  };

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"]/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;",
    }[c]));
  }

  function rec(t) {
    if (!t) return "—";
    const ties = t.ties ? "-" + t.ties : "";
    return (t.wins || 0) + "-" + (t.losses || 0) + ties;
  }

  function finish(t) {
    if (!t || t.finalRank == null) return "—";
    return R && R.ordinal ? R.ordinal(t.finalRank) : "#" + t.finalRank;
  }

  function teamOf(owner, y) {
    return ((A.data.seasons[String(y)] || {}).teams || []).find((x) => x.owner === owner) || null;
  }

  function faceFor(owner) {
    const mark = A.franchiseLogo(owner);
    const ys = A.squadYears(owner);
    for (const y of ys) {
      const tid = A.teamIdFor(y, owner);
      const t = tid != null ? A.teams(y)[tid] : null;
      if (t) return Object.assign({}, t, { owner: owner, logo: mark || t.logo });
    }
    const f = A.squadInfo(owner);
    return { owner: owner, name: (f && f.currentName) || A.memberName(owner), logo: mark || "" };
  }

  function careerRollup(owner) {
    let w = 0, l = 0, t = 0, pf = 0, pa = 0, titles = 0, allW = 0, allL = 0, luck = 0, n = 0, moves = 0;
    const rows = [];
    for (const y of A.squadYears(owner).slice().sort((a, b) => b - a)) {
      const tm = teamOf(owner, y);
      if (!tm) continue;
      w += tm.wins || 0;
      l += tm.losses || 0;
      t += tm.ties || 0;
      pf += tm.pf || 0;
      pa += tm.pa || 0;
      if (tm.finalRank === 1) titles += 1;
      allW += tm.allplayW || 0;
      allL += tm.allplayL || 0;
      luck += tm.luck || 0;
      n += 1;
      const mv = movesCount(y, tm.id);
      if (mv != null) moves += mv;
      rows.push({ year: y, t: tm, moves: mv });
    }
    return { w, l, t, pf, pa, titles, allW, allL, luck, n, moves, rows };
  }

  function sliceYear(yd, tid) {
    const picks = ((yd.draft && yd.draft.board) || []).filter((p) => A.sameId(p.tid, tid));
    const trades = (yd.trades || []).filter((tr) =>
      (tr.sides || []).some((s) => A.sameId(s.tid, tid)));
    const players = (yd.players || []).filter((p) =>
      A.sameId(p.mainTeam, tid) || (p.wk || []).some((w) => A.sameId(w[3], tid)));
    const mine = [];
    Object.entries(yd.weeks || {}).forEach(([wk, gs]) => {
      (gs || []).forEach((g) => {
        if (A.sameId(g.home.tid, tid) || A.sameId(g.away.tid, tid)) {
          mine.push({ wk: +wk, year: yd.year, g: g });
        }
      });
    });
    mine.sort((a, b) => (a.year - b.year) || (a.wk - b.wk));
    return { picks: picks, trades: trades, players: players, mine: mine };
  }

  function showTeam(on) {
    if (!on) {
      killLabCharts();
      if (actChart) { try { actChart.destroy(); } catch (e) {} actChart = null; }
    }
    $("franchise-grid").hidden = on;
    ["team-hero", "team-kpis", "scorers-block", "ngs-block", "years-block", "games-block", "draft-block",
      "spend-block", "trades-block", "activity-block", "roster-block", "season-roster-block", "roto-block", "lab-block"].forEach((id) => {
      const el = $(id);
      if (el) el.hidden = !on;
    });
  }

  function renderGrid() {
    showTeam(false);
    $("years-block").hidden = true;
    const list = A.visibleFranchises(A.squads());
    $("franchise-grid").innerHTML = list.map((f) => {
      const face = faceFor(f.owner);
      const ys = f.years || [];
      const span = ys.length ? Math.min.apply(null, ys) + "–" + Math.max.apply(null, ys) : "";
      const historic = A.isHistoric(f.owner);
      return `<button type="button" class="fr-card${historic ? " former" : ""}" data-owner="${esc(f.owner)}">
        ${A.logoHTML(face, "fr-logo")}
        <div class="fr-meta">
          <div class="fr-name">${esc(f.currentName)}</div>
          <div class="fr-own">${esc(f.ownerName || A.memberName(f.owner))}</div>
          <div class="fr-yrs">${ys.length} season${ys.length === 1 ? "" : "s"}${span ? " · " + span : ""}${historic ? " · historic" : ""}</div>
        </div>
      </button>`;
    }).join("");
    $("franchise-grid").querySelectorAll("[data-owner]").forEach((btn) => {
      btn.addEventListener("click", () => {
        squad = btn.dataset.owner;
        A.rememberSquad(squad);
        const u = new URL(location.href);
        u.searchParams.set("squad", squad);
        history.replaceState(null, "", u.pathname.split("/").pop() + u.search + u.hash);
        year = A.clampYear(year, squad);
        render();
      });
    });
    $("page-sub").textContent = "pick a franchise · " + list.length + " squads";
  }

  function kpiCard(title, desc) {
    return `<div class="card kpi kpi-static"><div class="kpi-title">${title}</div><div class="kpi-desc">${desc}</div></div>`;
  }

  function renderHero(t, career) {
    const f = A.squadInfo(squad) || {};
    const owner = f.ownerName || A.memberName(squad);
    const name = (t && t.name) || f.currentName || "Franchise";
    const face = t || faceFor(squad);
    let tiles;
    if (career) {
      tiles = [
        ["record", rec({ wins: career.w, losses: career.l, ties: career.t })],
        ["seasons", career.n],
        ["titles", career.titles],
        ["points for", A.fmt(career.pf, 1)],
        ["points against", A.fmt(career.pa, 1)],
        ["all-play", career.allW + "-" + career.allL],
        ["net luck", (career.luck >= 0 ? "+" : "") + A.fmt(career.luck, 2)],
        ["moves", career.moves || 0],
      ];
    } else {
      const seasonMoves = t && t.id != null ? movesCount(year, t.id) : null;
      tiles = [
        ["record", rec(t)],
        ["finish", finish(t)],
        ["seed", t && t.playoffSeed != null ? t.playoffSeed : "—"],
        ["points for", A.fmt(t && t.pf, 1)],
        ["points against", A.fmt(t && t.pa, 1)],
        ["all-play", t ? (t.allplayW || 0) + "-" + (t.allplayL || 0) : "—"],
        ["luck", t && t.luck != null ? ((t.luck >= 0 ? "+" : "") + A.fmt(t.luck, 2)) : "—"],
        ["moves", seasonMoves == null ? "—" : seasonMoves],
      ];
    }
    $("team-hero").innerHTML = `
      <div class="th-inner">
        ${A.logoHTML(face, "th-logo")}
        <div class="th-id">
          <h2 class="th-name">${esc(name)}</h2>
          <div class="th-own">${esc(owner)}${t && t.abbrev ? " · " + esc(t.abbrev) : ""}</div>
        </div>
        <div class="th-tiles">
          ${tiles.map(([l, v]) => `<div class="pp-stat"><b>${v}</b><span>${l}</span></div>`).join("")}
        </div>
      </div>`;
    if (career) {
      $("team-kpis").innerHTML = "";
      $("team-kpis").hidden = true;
    } else {
      $("team-kpis").innerHTML = "";
      $("team-kpis").hidden = true;
    }
  }

  function mountTeamToc() {
    let toc = $("team-toc");
    if (!toc) {
      toc = document.createElement("nav");
      toc.id = "team-toc";
      toc.className = "team-toc";
      toc.setAttribute("aria-label", "On this page");
      const hero = $("team-hero");
      if (hero && hero.parentNode) hero.insertAdjacentElement("afterend", toc);
      else return;
    }
    const links = [
      ["scorers-block", "Scorers"],
      ["games-block", "Games"],
      ["activity-block", "Activity"],
      ["ngs-block", "NGS"],
      ["draft-block", "Draft"],
      ["trades-block", "Trades"],
      ["roster-block", "Roster"],
      ["roto-block", "Roto"],
      ["lab-block", "Lab"],
    ].filter(([id]) => {
      const el = $(id);
      return el && !el.hidden;
    });
    toc.innerHTML = links.map(([id, lab]) =>
      `<a href="#${id}">${lab}</a>`
    ).join("");
    toc.hidden = links.length < 2;
  }

  function renderScorers() {
    const el = $("scorers-block");
    if (!el) return;
    el.hidden = false;
    const rec = LEADERS[A.canon(squad)] || LEADERS[squad] || {};
    const POS = [["QB", "QB"], ["RB", "RB"], ["WR", "WR"], ["TE", "TE"], ["K", "K"], ["DST", "D/ST"]];
    el.innerHTML = `
      <div class="card-head"><div><h2>All-time scorers</h2>
        <div class="card-sub">AFFL started points · 2018–2025 · this franchise only</div></div></div>
      <div class="scorers-grid">
        ${POS.map(([key, label]) => {
          const rows = rec[key] || [];
          return `<div class="scorers-pos">
            <h3>${label}</h3>
            ${rows.length ? `<ol>${rows.map((r) => {
              const ys = r.years || [];
              const span = !ys.length ? "" : (ys[0] === ys[ys.length - 1] ? String(ys[0]) : ys[0] + "–" + ys[ys.length - 1]);
              return `<li>
                <span class="sc-name">${A.playerLink(r.pid, r.name, { log: "all", squad: squad })}</span>
                <span class="sc-pts">${A.fmt(r.pts, 1)}</span>
                <span class="sc-yrs">${span}</span>
              </li>`;
            }).join("")}</ol>` : `<div class="sc-empty">—</div>`}
          </div>`;
        }).join("")}
      </div>`;
  }

  function renderYears(career) {
    const el = $("years-block");
    if (scope !== "cum") { el.hidden = true; el.innerHTML = ""; return; }
    el.hidden = false;
    el.innerHTML = `
      <div class="card-head"><div><h2>Year by Year</h2>
        <div class="card-sub">every season this franchise played · from league standings</div></div></div>
      <div class="table-scroll"><table class="tbl">
        <thead><tr><th>Year</th><th>Team</th><th>W-L</th><th>PF</th><th>PA</th><th>Seed</th><th>Finish</th><th>All-Play</th><th>Luck</th><th>Moves</th></tr></thead>
        <tbody>
          ${career.rows.map((r) => `<tr>
            <td class="tnum">${r.year}</td>
            <td><div class="team-cell">${A.logoHTML(r.t, "mini")}<span>${esc(r.t.name)}</span></div></td>
            <td class="tnum">${rec(r.t)}</td>
            <td class="tnum">${A.fmt(r.t.pf, 1)}</td>
            <td class="tnum">${A.fmt(r.t.pa, 1)}</td>
            <td class="tnum">${r.t.playoffSeed != null ? r.t.playoffSeed : "—"}</td>
            <td class="tnum">${finish(r.t)}</td>
            <td class="tnum">${(r.t.allplayW || 0) + "-" + (r.t.allplayL || 0)}</td>
            <td class="tnum">${r.t.luck != null ? ((r.t.luck >= 0 ? "+" : "") + A.fmt(r.t.luck, 2)) : "—"}</td>
            <td class="tnum">${r.moves != null ? r.moves : "—"}</td>
          </tr>`).join("")}
        </tbody>
      </table></div>`;
  }

  function gameRow(item, tid, teams) {
    const g = item.g;
    const home = A.sameId(g.home.tid, tid);
    const me = home ? g.home : g.away;
    const opp = home ? g.away : g.home;
    const ot = teams[opp.tid] || { name: "Team " + opp.tid };
    const win = me.pts > opp.pts;
    const tie = me.pts === opp.pts;
    const res = tie ? "T" : win ? "W" : "L";
    const resCls = tie ? "t" : win ? "w" : "l";
    const tier = TIER[g.tier] || "";
    const href = `scoreboard.html?year=${item.year}&week=${item.wk}&squad=${encodeURIComponent(squad)}`;
    return `<a class="gm-row" href="${href}">
      <span class="gm-wk">${item.year && scope === "cum" ? item.year + " · " : ""}W${item.wk}${tier ? " · " + tier : ""}</span>
      <span class="gm-opp">${A.logoHTML(ot, "gm-logo")}<span>${esc(ot.name)}</span></span>
      <span class="gm-score">${A.fmt(me.pts, 1)}–${A.fmt(opp.pts, 1)}</span>
      <span class="gm-res ${resCls}">${res}</span>
    </a>`;
  }

  function renderGames(items, tid, teams) {
    const el = $("games-block");
    el.innerHTML = `
      <div class="card-head"><div><h2>Games</h2>
        <div class="card-sub">${items.length} game${items.length === 1 ? "" : "s"} · click a row for the full scoreboard</div></div></div>
      ${items.length
        ? `<div class="gm-list">${items.map((it) => gameRow(it, tid, teams)).join("")}</div>`
        : A.notice("No games stored for this franchise in the selected range.")}`;
  }


  function renderSpendMix(picks, auction, note) {
    const el = $("spend-block");
    if (!el) return;
    el.hidden = false;
    if (spendChart) { spendChart.destroy(); spendChart = null; }
    if (!auction) {
      el.innerHTML = `
        <div class="card-head"><div><h2>Spend Mix</h2>
          <div class="card-sub">auction dollars · this franchise only</div></div></div>
        ${A.notice(note || "This season was a snake draft — no auction dollars to allocate. Spend mix is only available in auction years.")}`;
      return;
    }
    const POS = ["QB", "RB", "WR", "TE", "K", "DST"];
    const COLORS = { QB: A.C.blue, RB: A.C.green, WR: A.C.orange, TE: A.C.gold, K: A.C.ice, DST: A.C.steel };
    const byPos = {};
    POS.forEach((pos) => { byPos[pos] = { spend: 0, pts: 0, par: 0, n: 0 }; });
    let spend = 0, pts = 0, parTot = 0, parN = 0;
    const extras = arguments[3] || {};
    const defaultBases = extras.bases || {};
    (picks || []).forEach((p) => {
      const pos = byPos[p.pos] ? p.pos : (p.pos === "D/ST" ? "DST" : null);
      const bid = p.bid || 0;
      const pr = p.pts || 0;
      const bases = (extras.basesFor && extras.basesFor(p)) || defaultBases;
      const par = pickPar(p, bases);
      spend += bid;
      pts += pr;
      if (par != null) { parTot += par; parN += 1; }
      if (!pos) return;
      byPos[pos].spend += bid;
      byPos[pos].pts += pr;
      if (par != null) byPos[pos].par += par;
      byPos[pos].n += 1;
    });
    const rows = POS.filter((pos) => byPos[pos].n).map((pos) => {
      const r = byPos[pos];
      return {
        pos: pos,
        spend: r.spend,
        pts: r.pts,
        n: r.n,
        ppd: r.spend ? r.pts / r.spend : null,
        par: r.par,
        parpd: r.spend ? r.par / r.spend : null,
        share: spend ? r.spend / spend : 0,
      };
    });
    const ppd = spend ? pts / spend : null;
    el.innerHTML = `
      <div class="card-head"><div><h2>Spend Mix</h2>
        <div class="card-sub">this franchise only · $ from summed bids · grade is PAR/$ vs the position median (Pts/$ is secondary)</div></div></div>
      ${note ? `<p class="card-sub" style="margin-bottom:12px">${esc(note)}</p>` : ""}
      <div class="spend-mix">
        <div class="chart-wrap"><canvas id="spend-mix-chart"></canvas></div>
        <div class="table-scroll"><table class="tbl">
          <thead><tr><th>Pos</th><th>Picks</th><th>$</th><th>Share</th><th>Pts</th><th>Pts / $</th><th>PAR / $</th><th>vs pos med</th></tr></thead>
          <tbody>
            ${rows.map((r) => `<tr>
              <td><span class="badge pos-${esc(r.pos)}">${esc(r.pos)}</span></td>
              <td class="tnum">${r.n}</td>
              <td class="tnum">$${A.fmt(r.spend)}</td>
              <td class="tnum">${A.fmt(r.share * 100, 0)}%</td>
              <td class="tnum">${A.fmt(r.pts, 1)}</td>
              <td class="tnum">${r.ppd != null ? A.fmt(r.ppd, 2) : "—"}</td>
              <td class="tnum">${r.parpd != null ? A.fmt(r.parpd, 2) : "—"}</td>
              <td class="tnum">${(function () {
                const m = (extras.posMed || {})[r.pos];
                if (r.parpd == null || m == null) return "—";
                const d = r.parpd - m;
                return (d >= 0 ? "+" : "") + A.fmt(d, 2);
              })()}</td>
            </tr>`).join("")}
            <tr>
              <td class="left">Total</td>
              <td class="tnum">${(picks || []).length}</td>
              <td class="tnum gold">$${A.fmt(spend)}</td>
              <td class="tnum">100%</td>
              <td class="tnum">${A.fmt(pts, 1)}</td>
              <td class="tnum gold">${ppd != null ? A.fmt(ppd, 2) : "—"}</td>
              <td class="tnum">${parN ? A.fmt(parTot / (spend || 1), 2) : "—"}</td>
              <td class="tnum">—</td>
            </tr>
          </tbody>
        </table></div>
      </div>`;
    const ctx = $("spend-mix-chart");
    if (!ctx || typeof Chart === "undefined" || !rows.length) return;
    spendChart = new Chart(ctx, {
      type: "doughnut",
      data: {
        labels: rows.map((r) => r.pos),
        datasets: [{
          data: rows.map((r) => r.spend),
          backgroundColor: rows.map((r) => COLORS[r.pos] || A.C.steel),
          borderColor: "#0e1119",
          borderWidth: 2,
        }],
      },
      options: {
        maintainAspectRatio: false,
        plugins: {
          legend: { position: "bottom", labels: { boxWidth: 10, usePointStyle: true, pointStyle: "circle", color: "#7d8aa0" } },
          tooltip: { callbacks: { label: (c) => {
            const r = rows[c.dataIndex];
            return r.pos + " · $" + A.fmt(r.spend) + " · " + A.fmt(r.share * 100, 0) + "%";
          } } },
        },
        cutout: "58%",
      },
    });
  }

  function sortDraftPicks(picks) {
    const key = draftSortKey;
    const dir = draftSortDir;
    return picks.slice().sort((a, b) => {
      let av, bv;
      if (key === "cost") {
        av = a.bid != null ? a.bid : (a.overall || 0);
        bv = b.bid != null ? b.bid : (b.overall || 0);
      } else if (key === "pts") {
        av = a.pts != null ? a.pts : -1;
        bv = b.pts != null ? b.pts : -1;
      } else if (key === "year") {
        av = a.year || 0;
        bv = b.year || 0;
      } else {
        av = a.overall || 0;
        bv = b.overall || 0;
      }
      if (av !== bv) return (av - bv) * dir;
      return ((b.year || 0) - (a.year || 0)) || ((a.overall || 0) - (b.overall || 0));
    });
  }

  function bindDraftSort() {
    const el = $("draft-block");
    if (!el || el.dataset.sortBound) return;
    el.dataset.sortBound = "1";
    el.addEventListener("click", (e) => {
      const th = e.target.closest("th[data-k]");
      if (!th || !el.contains(th)) return;
      const k = th.dataset.k;
      if (draftSortKey === k) draftSortDir *= -1;
      else { draftSortKey = k; draftSortDir = -1; }
      renderDraft();
    });
  }

  function renderDraft(picks) {
    if (picks) draftPicks = picks;
    const el = $("draft-block");
    const rows = sortDraftPicks(draftPicks);
    const auction = rows.some((p) => p.bid != null && p.bid > 0);
    const mark = (k) => {
      const on = draftSortKey === k;
      return ` class="s${on ? " on" : ""}${on && draftSortDir > 0 ? " asc" : ""}" data-k="${k}"`;
    };
    el.innerHTML = `
      <div class="card-head"><div><h2>Draft</h2>
        <div class="card-sub">${rows.length} pick${rows.length === 1 ? "" : "s"} · this franchise only · click Cost or Season Pts to sort</div></div></div>
      ${rows.length ? `
      <div class="table-scroll"><table class="tbl" id="team-draft-tbl">
        <thead><tr>${scope === "cum" ? "<th" + mark("year") + ">Year</th>" : ""}<th${mark("overall")}>#</th><th>Player</th><th>Pos</th><th>NFL</th><th${mark("cost")}>${auction ? "Cost" : "Pick"}</th><th${mark("pts")}>Season Pts</th></tr></thead>
        <tbody>
          ${rows.map((p) => {
            const y = p.year || year;
            return `<tr>
              ${scope === "cum" ? `<td class="tnum">${y}</td>` : ""}
              <td><span class="rank-pill${p.overall === 1 ? " gold" : ""}">${p.overall}</span></td>
              <td>${A.playerLink(p.pid, p.name, { year: y, squad: squad, cls: "sb-name link" })}${p.keeper ? ' <span class="badge">keeper</span>' : ""}</td>
              <td><span class="badge pos-${esc(p.pos)}">${esc(p.pos)}</span></td>
              <td class="own">${esc(p.nfl || "—")}</td>
              <td><strong>${auction ? "$" + (p.bid || 0) : (p.round + "." + String(p.pick).padStart(2, "0"))}</strong></td>
              <td class="tnum">${p.pts != null ? A.fmt(p.pts, 1) : "—"}</td>
            </tr>`;
          }).join("")}
        </tbody>
      </table></div>` : A.notice("No draft picks stored for this franchise in the selected range.")}`;
    bindDraftSort();
  }

  function renderTrades(trades, lookup) {
    const el = $("trades-block");
    el.innerHTML = `
      <div class="card-head"><div><h2>Trades</h2>
        <div class="card-sub">${trades.length} trade${trades.length === 1 ? "" : "s"} this franchise was in</div></div></div>
      ${trades.length ? `<div class="trade-list">${trades.map((tr) => {
        const y = tr.year || year;
        const T = lookup(y);
        const short = (id) => {
          const n = (T[id] || { name: "?" }).name;
          return n.length > 17 ? n.slice(0, 16) + "…" : n;
        };
        return `<div class="trade">
          <div class="trade-head"><span class="trade-wk">${y} · Week ${tr.wk}</span><span class="trade-date">${A.dateStr(tr.date)}</span></div>
          <div class="trade-body">
            ${(tr.sides || []).map((s) => `
              <div class="trade-side">
                <div class="trade-team">${A.logoHTML(T[s.tid], "mini")}<span>${esc(short(s.tid))}</span></div>
                <div class="trade-got">${(s.got || []).map((g) =>
                  `<span class="trade-pl"><span class="badge pos-${esc(g.pos)}">${esc(g.pos)}</span> ${A.playerLink(g.pid, g.name, { year: y, squad: squad })}</span>`).join("")}</div>
              </div>`).join('<div class="trade-swap">⇄</div>')}
          </div>
        </div>`;
      }).join("")}</div>` : A.notice("No trades involving this franchise in the selected range. ESPN retains transactions from 2018 on.")}`;
  }

  function renderActivity(tid, y) {
    const el = $("activity-block");
    if (!el) return;
    if (actChart) { try { actChart.destroy(); } catch (e) {} actChart = null; }
    if (y < 2018) {
      el.hidden = false;
      el.innerHTML = `<div class="card-head"><div><h2>Team activity</h2>
        <div class="card-sub">2018+ only</div></div></div>
        ${A.notice("ESPN does not keep transaction timestamps before 2018. Activity grid and value-added are unavailable for " + y + ".")}`;
      return;
    }
    if (!TEAM_ACT || !TEAM_ACT.seasons || !TEAM_ACT.seasons[String(y)]) {
      el.hidden = false;
      el.innerHTML = `<div class="card-head"><div><h2>Team activity</h2></div></div>
        ${A.notice("Activity data missing — run scripts/compute_team_activity.py.")}`;
      return;
    }
    const bag = TEAM_ACT.seasons[String(y)];
    const team = (bag.teams || {})[String(tid)];
    if (!team || !team.grid) {
      el.hidden = false;
      el.innerHTML = `<div class="card-head"><div><h2>Team activity</h2></div></div>
        ${A.notice("No activity payload for this team-season.")}`;
      return;
    }
    const g = team.grid;
    const maxC = Math.max(1, g.maxCell || 1);
    const shade = (n) => {
      if (!n) return "";
      const t = Math.min(1, n / maxC);
      const a = (0.12 + 0.78 * t).toFixed(2);
      return `background:rgba(0,162,255,${a})`;
    };
    const head = (g.dow || []).map((d) => `<th>${d}</th>`).join("");
    const body = (g.weeks || []).map((wk, i) => {
      const row = (g.counts && g.counts[i]) || [];
      const cells = row.map((n, j) => {
        const dow = (g.dow || [])[j] || "";
        const key = wk + ":" + dow;
        const det = (g.details && g.details[key]) || [];
        const title = det.length
          ? `${wk} · ${dow}\n` + det.map((m) => `${m.op} ${A.displayPlayerName(m.name)}`).join("\n")
          : (n ? `${wk} · ${dow}: ${n} move${n === 1 ? "" : "s"}` : "");
        return `<td class="act-cell${n ? " on" : ""}" style="${shade(n)}" title="${esc(title)}">${n || ""}</td>`;
      }).join("");
      return `<tr><th scope="row">W${wk}</th>${cells}</tr>`;
    }).join("");

    const scatter = bag.scatter || [];
    const med = bag.medianValueAdded != null ? bag.medianValueAdded : 0;

    el.hidden = false;
    el.innerHTML = `
      <div class="card-head"><div><h2>Activity grid</h2>
        <div class="card-sub">Day of week × week · transaction activity · ${y}</div></div></div>
      <div class="act-grid-wrap">
        <table class="act-grid" aria-label="Transaction activity by week and weekday">
          <thead><tr><th></th>${head}</tr></thead>
          <tbody>${body}</tbody>
        </table>
      </div>
      <p class="draft-note">Every add, drop, and trade by the day of the week you made it (America/Chicago). Lineup changes aren't shown — ESPN doesn't give a real timestamp for when a lineup was set, only for actual roster moves.</p>

      <div class="card-head" style="margin-top:18px"><div><h2>Team activity</h2>
        <div class="card-sub">Transactions (X) vs in-season value added (Y) · ${y}</div></div>
        <div class="card-sub">This team: <strong>${team.transactions}</strong> arrivals · VA <strong>${A.fmt ? A.fmt(team.valueAdded, 1) : team.valueAdded}</strong> pts</div>
      </div>
      <div class="chart-wrap tall"><canvas id="act-scatter"></canvas></div>
      <p class="draft-note">Value added = started points from in-season acquisitions minus same-week points of the paired drop (0 if unknown). Drafted players excluded. Solid line = 0; dashed = league median (${med}). Across = how often you moved; up = whether it worked.</p>
    `;

    const canvas = $("act-scatter");
    if (!canvas || typeof Chart === "undefined") return;
    const pts = scatter.map((p) => ({
      x: p.transactions,
      y: p.valueAdded,
      label: p.name,
      tid: p.tid,
      self: A.sameId(p.tid, tid),
    }));
    const others = pts.filter((p) => !p.self);
    const mine = pts.filter((p) => p.self);
    actChart = new Chart(canvas, {
      type: "scatter",
      data: {
        datasets: [
          {
            label: "League",
            data: others,
            backgroundColor: "#7d8aa088",
            borderColor: "#7d8aa0",
            pointRadius: 5,
          },
          {
            label: team.name || "This team",
            data: mine,
            backgroundColor: "#00a2ff",
            borderColor: "#47d4ff",
            pointRadius: 8,
            pointHoverRadius: 10,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: true, labels: { color: "#7d8aa0", boxWidth: 10 } },
          tooltip: {
            callbacks: {
              label: (ctx) => {
                const r = ctx.raw || {};
                return `${r.label || ""} · tx ${r.x} · VA ${Number(r.y).toFixed(1)}`;
              },
            },
          },
          annotation: undefined,
        },
        scales: {
          x: {
            title: { display: true, text: "Transactions →", color: "#7d8aa0" },
            grid: { color: "#1b243366" },
            ticks: { color: "#7d8aa0" },
            beginAtZero: true,
          },
          y: {
            title: { display: true, text: "Value added (pts)", color: "#7d8aa0" },
            grid: {
              color: (ctx) => (ctx.tick && ctx.tick.value === 0 ? "#eef4ff55" : "#1b243366"),
              lineWidth: (ctx) => (ctx.tick && ctx.tick.value === 0 ? 2 : 1),
            },
            ticks: { color: "#7d8aa0" },
          },
        },
      },
      plugins: [{
        id: "medianLine",
        afterDraw(chart) {
          const yScale = chart.scales.y;
          const { left, right } = chart.chartArea;
          const y = yScale.getPixelForValue(med);
          const ctx = chart.ctx;
          ctx.save();
          ctx.beginPath();
          ctx.setLineDash([5, 5]);
          ctx.strokeStyle = "#ffc400aa";
          ctx.lineWidth = 1.5;
          ctx.moveTo(left, y);
          ctx.lineTo(right, y);
          ctx.stroke();
          ctx.restore();
        },
      }],
    });
  }

  function playerLogs(p, y) {
    if (p.logs && p.logs.length) return p.logs;
    return (p.wk || []).map((w) => ({ y: p.year || y, w: w }));
  }

  function keepLog(r) {
    const tid = A.teamIdFor(r.y, squad);
    return tid != null && A.sameId(r.w[3], tid);
  }

  function signed(n, d) {
    if (n == null || Number.isNaN(Number(n))) return "—";
    const v = Number(n);
    return (v >= 0 ? "+" : "") + A.fmt(v, d);
  }

  function statItem(k, v) {
    return `<div class="tm-stat"><div class="tm-stat-k">${k}</div><div class="tm-stat-v">${v}</div></div>`;
  }

  function statCard(p, y) {
    const rows = playerLogs(p, y).filter(keepLog);
    let starts = 0, stPts = 0, tot = 0, yds = 0, td = 0, res = 0, epa = 0, n = 0;
    let hasYds = false, hasTd = false, hasRes = false, hasEpa = false;
    rows.forEach((r) => {
      const w = r.w || [];
      const pts = w[1], st = w[2], ydsW = w[6], tdW = w[7], epaW = w[9], resW = w[11];
      n += 1;
      tot += pts || 0;
      if (st) { starts += 1; stPts += pts || 0; }
      if (ydsW != null) { yds += ydsW; hasYds = true; }
      if (tdW != null) { td += tdW; hasTd = true; }
      if (resW != null) { res += resW; hasRes = true; }
      if (epaW != null) { epa += epaW; hasEpa = true; }
    });
    if (!n) {
      starts = p.starts || 0;
      stPts = p.stPts || 0;
      tot = p.tot || 0;
      if (p.xtdRes != null) { res = p.xtdRes; hasRes = true; }
      if (p.epa != null) { epa = p.epa; hasEpa = true; }
    }
    const ppg = starts ? stPts / starts : (p.ppg != null ? p.ppg : null);
    const ypg = n && hasYds ? yds / n : null;
    const epag = n && hasEpa ? epa / n : null;
    const empty = !n && !starts && !tot;
    if (empty) {
      return A.notice("No scoring line for this player on this team. Weekly lineups start in 2018.");
    }
    return `<div class="tm-card">
      <div class="tm-card-row">
        <div class="tm-card-lab">Totals</div>
        <div class="tm-card-stats">
          ${statItem("Starts", starts || "—")}
          ${statItem("St Pts", A.fmt(stPts, 1))}
          ${statItem("Tot", A.fmt(tot, 1))}
          ${statItem("Yds", hasYds ? A.fmt(yds, 0) : "—")}
          ${statItem("TD", hasTd ? A.fmt(td, 0) : "—")}
          ${statItem("xTD Res", hasRes ? signed(res, 2) : "—")}
          ${statItem("EPA", hasEpa ? signed(epa, 1) : "—")}
        </div>
      </div>
      <div class="tm-card-row">
        <div class="tm-card-lab">Averages</div>
        <div class="tm-card-stats">
          ${statItem("PPG", ppg != null ? A.fmt(ppg, 1) : "—")}
          ${statItem("Yds/G", ypg != null ? A.fmt(ypg, 1) : "—")}
          ${statItem("EPA/G", epag != null ? signed(epag, 2) : "—")}
        </div>
      </div>
    </div>`;
  }

  function renderRoster(players, y) {
    rosterCache = { players: players || [], y: y };
    const el = $("roster-block");
    const rows = rosterCache.players.slice().sort((a, b) => (b.stPts || 0) - (a.stPts || 0) || (b.tot || 0) - (a.tot || 0));
    const cols = scope === "cum" ? 8 : 7;
    el.innerHTML = `
      <div class="card-head"><div><h2>Roster</h2>
        <div class="card-sub">${rows.length} player${rows.length === 1 ? "" : "s"} · name opens the profile · ▸ shows totals and averages</div></div></div>
      ${rows.length ? `
      <div class="table-scroll"><table class="tbl">
        <thead><tr>${scope === "cum" ? "<th>Years</th>" : ""}<th>Player</th><th>Pos</th><th>NFL</th><th>Starts</th><th>St Pts</th><th>Tot</th><th>xTD Res</th></tr></thead>
        <tbody>
          ${rows.map((p) => {
            const open = A.sameId(openPid, p.pid);
            return `<tr>
              ${scope === "cum" ? `<td class="tnum">${p.years ? p.years.length : ""}</td>` : ""}
              <td>${A.playerLink(p.pid, p.name, { cls: "tm-name", year: scope === "cum" ? null : y, squad: squad })} <button type="button" class="tm-toggle" data-pid="${p.pid}" aria-label="Show totals">▸</button></td>
              <td><span class="badge pos-${esc(p.pos)}">${esc(p.pos)}</span></td>
              <td class="own">${esc(p.nfl || "—")}</td>
              <td class="tnum">${p.starts != null ? p.starts : "—"}</td>
              <td class="tnum">${p.stPts != null ? A.fmt(p.stPts, 1) : "—"}</td>
              <td class="tnum">${p.tot != null ? A.fmt(p.tot, 1) : "—"}</td>
              <td class="tnum">${p.xtdRes != null ? ((p.xtdRes >= 0 ? "+" : "") + A.fmt(p.xtdRes, 2)) : "—"}</td>
            </tr>` + (open ? `<tr class="tm-log-row"><td colspan="${cols}">${statCard(p, y)}</td></tr>` : "");
          }).join("")}
        </tbody>
      </table></div>` : A.notice("No rostered-player logs for this franchise in the selected range. Weekly lineups start in 2018.")}`;
    el.querySelectorAll(".tm-toggle").forEach((b) => {
      b.addEventListener("click", () => {
        const pid = b.getAttribute("data-pid");
        openPid = A.sameId(openPid, pid) ? null : pid;
        renderRoster(rosterCache.players, rosterCache.y);
      });
    });
  }

  function isPre2018(y) {
    return y != null && Number(y) < 2018;
  }

  function seasonRosterRows(y, tid) {
    const bag = PRE2018_SEASON_ROSTERS[String(y)] || {};
    return bag[String(tid)] || bag[tid] || [];
  }

  function renderSeasonRoster(tid, y) {
    const el = $("season-roster-block");
    if (!el) return;
    const show = scope === "season" && isPre2018(y) && tid != null;
    if (!show) {
      el.hidden = true;
      el.innerHTML = "";
      return;
    }
    const f = A.squadInfo(squad) || {};
    const franchise = f.currentName || "Franchise";
    const rows = seasonRosterRows(y, tid);
    el.hidden = false;
    el.innerHTML = `
      <div class="card-head"><div><h2>Season roster</h2>
        <div class="card-sub">${esc(franchise)} · draft + weekly starts + final snapshot · weekly benches not in ESPN’s API</div></div></div>
      ${rows.length ? `
      <div class="table-scroll"><table class="tbl sr-tbl">
        <thead><tr>
          <th>Slot</th><th>Player</th><th>NFL season pts</th><th>Avg</th><th>AFFL starts</th>
        </tr></thead>
        <tbody>
          ${rows.map((p) => {
            const pts = p.nflPts;
            const g = p.nflG;
            let avg = null;
            if (pts != null && g) avg = pts / g;
            else if (pts != null && p.starts) avg = pts / p.starts;
            const tags = [];
            if (p.drafted) tags.push(["drafted", "drafted"]);
            if ((p.starts || 0) > 0) tags.push(["started", "started"]);
            if (p.snapshot) tags.push(["finished", "finished"]);
            const gone = p.drafted && !p.snapshot;
            const add = !p.drafted && !p.snapshot;
            return `<tr class="${gone ? "sr-gone" : add ? "sr-add" : ""}">
              <td class="sr-slot">${esc(p.slotName || "—")}</td>
              <td>${A.playerLink(p.pid, p.name, { cls: "tm-name", year: y, squad: squad })}
                <div class="sr-src">${tags.map(([k, lab]) => `<span class="sr-tag ${k}">${lab}</span>`).join("")}</div></td>
              <td class="tnum">${pts != null ? A.fmt(pts, 1) : "—"}</td>
              <td class="tnum">${avg != null ? A.fmt(avg, 1) : "—"}</td>
              <td class="tnum">${p.starts != null ? p.starts : "—"}</td>
            </tr>`;
          }).join("")}
        </tbody>
      </table></div>` : A.notice("No season-long roster recovered for this franchise in " + y + ".")}`;
  }

  async function loadPillars() {
    if (pillars) return pillars;
    const root = "pillars/";
    const league = await fetch(root + "league.json").then((r) => r.json());
    const seasons = league.seasons || [];
    const expectedYears = (league.meta && league.meta.seasons) || seasons.map((s) => s.year);
    const attempted = await Promise.all(expectedYears.map(async (y) => {
      const season = seasons.find((s) => s.year === y);
      try {
        const res = await fetch(root + "boxscores/" + y + ".json");
        if (!res.ok) return { year: y, season: season, box: null };
        return { year: y, season: season, box: await res.json() };
      } catch (e) {
        return { year: y, season: season, box: null };
      }
    }));
    pillars = {
      league: league,
      loads: attempted.filter((l) => l.box && l.season),
      attempted: attempted,
    };
    return pillars;
  }

  function pillarsOwner(sq, loads) {
    if (!sq) return null;
    for (const y of A.squadYears(sq)) {
      const tid = A.teamIdFor(y, sq);
      const load = loads.find((l) => l.year === y);
      if (!load || !tid || !load.season) continue;
      const t = (load.season.teams || []).find((x) => A.sameId(x.teamId, tid));
      if (t && t.ownerId) return t.ownerId;
    }
    return null;
  }

  function renderBreakdown(team, n, host) {
    let last = "";
    host.innerHTML = `
      <div class="table-scroll"><table class="tbl roto-tbl">
        <thead><tr>
          <th class="left">Group</th><th class="left">Category</th>
          <th>Value</th><th>Rank</th><th>Pts</th>
        </tr></thead>
        <tbody>
          ${team.categories.map((c) => {
            const show = c.group !== last;
            last = c.group;
            return `<tr>
              <td class="left mut">${show ? esc(c.group) : ""}</td>
              <td class="left">${esc(c.label)}</td>
              <td class="tnum">${R.formatCatValue(c)}</td>
              <td class="tnum">#${c.rank}/${n}</td>
              <td class="tnum">${c.pts}</td>
            </tr>`;
          }).join("")}
          <tr>
            <td></td><td class="left">Total</td><td></td>
            <td class="tnum">#${team.totalRank}/${n}</td>
            <td class="tnum gold">${team.totalPts}</td>
          </tr>
        </tbody>
      </table></div>`;
  }

  function renderRadar(team, teams, canvas) {
    if (radarChart) { radarChart.destroy(); radarChart = null; }
    if (!canvas || typeof Chart === "undefined") return;
    const avg = R.leagueAverageNorm(teams);
    radarChart = new Chart(canvas, {
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

  async function renderRotoSeason(tid) {
    const el = $("roto-block");
    const P = await loadPillars();
    const load = P.loads.find((l) => l.year === year);
    if (!load) {
      el.innerHTML = `
        <div class="card-head"><div><h2>Roto</h2>
          <div class="card-sub">${year}</div></div></div>
        ${A.notice("Player-level boxscores start in 2018. " + year + " has no ESPN starter-level lineups, so roto ranks are unavailable — not zero.")}`;
      return;
    }
    const teams = R.computeCategoryStats(load.box, load.season, "reg", false);
    const hit = teams.find((t) => A.sameId(t.teamId, tid));
    if (!hit) {
      el.innerHTML = `
        <div class="card-head"><div><h2>Roto</h2></div></div>
        ${A.notice("No roto row for this franchise in " + year + ".")}`;
      return;
    }
    const n = teams.length;
    const displayTeams = teams.filter((t) => A.sameId(t.teamId, tid));
    const best = [...hit.categories].sort((a, b) => a.rank - b.rank)[0];
    const worst = [...hit.categories].sort((a, b) => b.rank - a.rank)[0];
    el.innerHTML = `
      <div class="card-head"><div><h2>Roto</h2>
        <div class="card-sub">this franchise only · ranks computed against the full ${n}-team league · ${year} regular season</div></div></div>
      <div class="table-scroll"><table class="tbl roto-tbl">
        <thead><tr>
          <th class="left">Team</th><th>G</th>
          ${hit.categories.map((c) => `<th title="${esc(c.group)} · ${esc(c.label)}">${esc(c.label)}</th>`).join("")}
          <th>Total Pts</th>
        </tr></thead>
        <tbody>
          ${displayTeams.map((t) => `<tr>
            <td class="left">${esc(t.teamName)}</td>
            <td class="tnum mut">${t.games}</td>
            ${t.categories.map((c) =>
              `<td class="tnum" style="background:${R.rankCellBg(c.rank, n)}">${R.formatCatValue(c)}</td>`).join("")}
            <td class="tnum gold">${t.totalPts}</td>
          </tr>`).join("")}
        </tbody>
      </table></div>
      <div class="second-grid" style="margin-top:16px">
        <div>
          <div class="card-sub" id="radar-sub">${esc(hit.teamName)} ranks ${hit.totalRank} of ${n} · filled = this team · outline = league average</div>
          <div class="radar-meta">
            <div class="radar-chip good"><b>Strength</b><span>${esc(best.label)} · #${best.rank}/${n}</span></div>
            <div class="radar-chip bad"><b>Weakness</b><span>${esc(worst.label)} · #${worst.rank}/${n}</span></div>
          </div>
          <div class="chart-wrap tall"><canvas id="roto-radar"></canvas></div>
        </div>
        <div>
          <div class="card-sub" id="break-sub">#${hit.totalRank} · ${hit.totalPts} pts · ${hit.games} games</div>
          <div id="breakdown"></div>
        </div>
      </div>`;
    renderBreakdown(hit, n, $("breakdown"));
    renderRadar(hit, teams, $("roto-radar"));
  }

  async function renderRotoCareer() {
    const el = $("roto-block");
    const P = await loadPillars();
    const oid = pillarsOwner(squad, P.loads);
    const career = R.buildRotoCareer(P.loads, "reg", false);
    const allowed = new Set(A.squadYears(squad));
    const scored = career.scoredYears.filter((y) => allowed.has(y));
    const row = career.rows.find((c) => c.ownerId === oid);
    const missing = (career.missingYears || []).filter((y) => allowed.has(y));
    const early = A.squadYears(squad).filter((y) => y < 2018);
    if (!row || !scored.length) {
      el.innerHTML = `
        <div class="card-head"><div><h2>Roto</h2><div class="card-sub">career</div></div></div>
        ${A.notice("Career roto only uses years with a player-level boxscore (2018+). " +
          (early.length ? (early[0] + "–" + early[early.length - 1] + " are unavailable — not sit-outs.") : ""))}`;
      return;
    }
    const gap = (missing.length || early.length)
      ? `<p class="gap-note">${[...new Set(early.concat(missing))].sort().join(", ")} ` +
        `could not be scored (no ESPN player-level lineups) and ${early.concat(missing).length === 1 ? "is" : "are"} excluded from the average. Data gaps, not sit-outs.</p>`
      : "";
    el.innerHTML = `
      <div class="card-head"><div><h2>Roto</h2>
        <div class="card-sub">career average across ${scored.length} scored season${scored.length === 1 ? "" : "s"} · ranks from the full league each year</div></div></div>
      ${gap}
      <div class="table-scroll"><table class="tbl roto-tbl">
        <thead><tr>
          <th class="left">Manager</th><th>Seasons</th><th>Avg finish</th><th>Best</th><th>Worst</th><th>Avg pts</th>
          ${scored.map((y) => `<th>${String(y).slice(2)}</th>`).join("")}
        </tr></thead>
        <tbody><tr>
          <td class="left">${esc((P.league.ownerNames && P.league.ownerNames[oid]) || A.memberName(squad))}</td>
          <td class="tnum">${row.seasons}</td>
          <td class="tnum gold">${row.avgRank.toFixed(2)}</td>
          <td class="tnum">${R.ordinal(row.bestRank)}</td>
          <td class="tnum">${R.ordinal(row.worstRank)}</td>
          <td class="tnum">${row.avgPts.toFixed(1)}</td>
          ${scored.map((y) => {
            const cell = row.byYear.get(y);
            if (!cell) return `<td class="tnum mut">—</td>`;
            return `<td class="tnum" style="background:${R.rankCellBg(cell.rank, cell.nTeams)}">${cell.rank}</td>`;
          }).join("")}
        </tr></tbody>
      </table></div>
      <div class="second-grid" style="margin-top:16px">
        <div>
          <div class="card-sub" id="radar-sub">mean category shape across scored seasons · outline = league average</div>
          <div class="radar-meta" id="radar-meta"></div>
          <div class="chart-wrap tall"><canvas id="roto-radar"></canvas></div>
        </div>
        <div>
          <div class="card-sub" id="break-sub">career-average norm</div>
          <div id="breakdown"></div>
        </div>
      </div>`;

    const acc = {};
    let n = 0;
    const leagueAcc = {};
    let leagueN = 0;
    for (const load of P.loads) {
      if (!allowed.has(load.year)) continue;
      const teams = R.computeCategoryStats(load.box, load.season, "reg", false);
      if (!teams.length) continue;
      const avg = R.leagueAverageNorm(teams);
      leagueN += 1;
      R.CATS.forEach((cat) => { leagueAcc[cat.key] = (leagueAcc[cat.key] || 0) + (avg[cat.key] || 0); });
      const tm = teams.find((x) => x.ownerId === oid);
      if (!tm) continue;
      n += 1;
      tm.categories.forEach((c) => { acc[c.key] = (acc[c.key] || 0) + c.norm; });
    }
    if (!n) return;
    const fake = {
      teamName: A.memberName(squad),
      categories: R.CATS.map((cat) => ({
        key: cat.key, label: cat.label, group: cat.group,
        norm: acc[cat.key] / n, rank: 0, pts: 0, value: 0,
      })),
    };
    const ranked = [...fake.categories].sort((a, b) => b.norm - a.norm);
    $("radar-meta").innerHTML = `
      <div class="radar-chip good"><b>Strength</b><span>${esc(ranked[0].label)}</span></div>
      <div class="radar-chip bad"><b>Weakness</b><span>${esc(ranked[ranked.length - 1].label)}</span></div>`;
    $("breakdown").innerHTML = `
      <div class="table-scroll"><table class="tbl roto-tbl">
        <thead><tr><th class="left">Category</th><th>Mean strength</th></tr></thead>
        <tbody>${fake.categories.map((c) => `<tr>
          <td class="left">${esc(c.label)}</td>
          <td class="tnum">${(c.norm * 100).toFixed(0)}</td>
        </tr>`).join("")}</tbody>
      </table></div>`;
    const dummyTeams = [fake];
    dummyTeams[0].categories.forEach((c) => { c.value = c.norm; });
    const avg = {};
    R.CATS.forEach((cat) => { avg[cat.key] = leagueN ? leagueAcc[cat.key] / leagueN : 0; });
    if (radarChart) { radarChart.destroy(); radarChart = null; }
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

  function mergePlayers(bags) {
    const by = {};
    bags.forEach(({ year: y, players }) => {
      players.forEach((p) => {
        const a = by[p.pid] || {
          pid: p.pid, name: p.name, pos: p.pos, nfl: p.nfl,
          tot: 0, stPts: 0, starts: 0, xtdRes: 0, years: [], year: y, logs: [],
        };
        a.tot += p.tot || 0;
        a.stPts += p.stPts || 0;
        a.starts += p.starts || 0;
        if (p.xtdRes != null) a.xtdRes += p.xtdRes;
        if (p.name) a.name = p.name;
        if (p.pos) a.pos = p.pos;
        if (p.nfl) a.nfl = p.nfl;
        (p.wk || []).forEach((w) => a.logs.push({ y: y, w: w }));
        a.years.push(y);
        a.year = y;
        by[p.pid] = a;
      });
    });
    return Object.values(by);
  }


  const POS_ORDER = ["QB", "RB", "WR", "TE", "K", "DST"];
  const POS_COLORS = { QB: A.C.blue, RB: A.C.green, WR: A.C.orange, TE: A.C.gold, K: A.C.ice, DST: A.C.steel };
  const labCharts = {};
  let PLAYER_INDEX = null;

  function killLabCharts() {
    Object.keys(labCharts).forEach((k) => {
      try { labCharts[k].destroy(); } catch (e) {}
      delete labCharts[k];
    });
  }

  function mkLab(id, cfg) {
    if (labCharts[id]) { try { labCharts[id].destroy(); } catch (e) {} labCharts[id] = null; }
    const el = $(id);
    if (!el || typeof Chart === "undefined") return null;
    labCharts[id] = new Chart(el, cfg);
    return labCharts[id];
  }

  async function loadPlayerIndex() {
    if (PLAYER_INDEX) return PLAYER_INDEX;
    try {
      PLAYER_INDEX = await fetch("player_index.json?v=" + Date.now(), { cache: "no-store" }).then((r) => r.json());
    } catch (e) {
      PLAYER_INDEX = {};
    }
    return PLAYER_INDEX;
  }

  function normPos(pos) {
    if (pos === "D/ST" || pos === "DEF" || pos === "D") return "DST";
    return pos || "";
  }

  function baselineMap(yd) {
    const out = {};
    ((((yd || {}).draftValue) || {}).baselines || []).forEach((b) => {
      if (b && b.position) out[b.position] = b.baseline;
    });
    return out;
  }

  function pickPar(p, bases) {
    if (p && p.par != null) return p.par;
    const pos = normPos(p && p.pos);
    const base = bases && bases[pos];
    if (base == null || !p || p.pts == null) return null;
    return p.pts - base;
  }

  function medianNums(xs) {
    const a = (xs || []).filter((n) => n != null && !Number.isNaN(Number(n))).map(Number).sort((x, y) => x - y);
    if (!a.length) return null;
    const m = Math.floor(a.length / 2);
    return a.length % 2 ? a[m] : (a[m - 1] + a[m]) / 2;
  }

  function rankOf(values, mine, desc) {
    if (mine == null || Number.isNaN(Number(mine))) return null;
    const pool = (values || []).filter((v) => v != null && !Number.isNaN(Number(v))).map(Number);
    if (!pool.length) return null;
    const better = pool.filter((v) => (desc ? v > mine : v < mine)).length;
    return better + 1;
  }

  function rankLine(rank, n) {
    if (rank == null || !n) return "";
    return "#" + rank + " of " + n;
  }

  function gradeChip(g) {
    if (!g) return "—";
    return `<span class="grade g${esc(String(g)[0])}">${esc(g)}</span>`;
  }

  function moneyM(n) {
    if (n == null || Number.isNaN(Number(n))) return "—";
    const v = Number(n);
    const a = Math.abs(v);
    const sign = v < 0 ? "-" : "";
    if (a >= 1e6) return sign + "$" + (a / 1e6).toFixed(1) + "M";
    if (a >= 1e3) return sign + "$" + Math.round(a / 1e3) + "K";
    return sign + "$" + Math.round(a);
  }

  function capHitFor(pid, y) {
    const rec = (PLAYER_INDEX || {})[String(pid)] || {};
    const hits = (rec.cap || []).filter((c) => c.season === y);
    const tot = hits.reduce((a, c) => a + (c.hit || 0), 0);
    return tot > 0 ? tot : null;
  }

  function ptsOnTeam(p, tid) {
    let pts = 0, n = 0;
    (p.wk || []).forEach((w) => {
      if (A.sameId(w[3], tid)) { pts += w[1] || 0; n += 1; }
    });
    if (!n && A.sameId(p.mainTeam, tid)) return p.tot || 0;
    return pts;
  }

  function posMedianPpm(yd) {
    const by = {};
    (yd.players || []).forEach((p) => {
      const pos = normPos(p.pos);
      const cap = capHitFor(p.pid, yd.year);
      if (!cap || !POS_ORDER.includes(pos)) return;
      const pts = p.tot || 0;
      (by[pos] = by[pos] || []).push(pts / (cap / 1e6));
    });
    const med = {};
    POS_ORDER.forEach((pos) => { med[pos] = medianNums(by[pos]); });
    return med;
  }

  function posMedianParpd(board, bases) {
    const by = {};
    (board || []).forEach((p) => {
      const bid = p.bid || 0;
      if (bid <= 0) return;
      const par = pickPar(p, bases);
      if (par == null) return;
      const pos = normPos(p.pos);
      (by[pos] = by[pos] || []).push(par / bid);
    });
    const med = {};
    Object.keys(by).forEach((pos) => { med[pos] = medianNums(by[pos]); });
    return med;
  }

  function weeklyScores(yd, tid) {
    const n = yd.regWeeks || ((yd.scoreWeek || []).length) || 0;
    const out = [];
    for (let w = 1; w <= n; w++) {
      const gs = (yd.weeks || {})[String(w)] || [];
      let pts = null;
      gs.forEach((g) => {
        if (A.sameId(g.home.tid, tid)) pts = g.home.pts;
        else if (A.sameId(g.away.tid, tid)) pts = g.away.pts;
      });
      const sw = (yd.scoreWeek || []).find((s) => s.week === w);
      out.push({ week: w, pts: pts, avg: sw && sw.avgPts, min: sw && sw.minPts, max: sw && sw.maxPts });
    }
    return out;
  }

  function trophyWins(yd, tid) {
    const t = (yd && yd.trophies) || {};
    const won = [];
    if (A.sameId(t.h2hChampionTid, tid)) won.push({ key: "Cup", rec: "H2H champion" });
    const med = A.sameId(t.medianChampionTid, tid);
    const ap = A.sameId(t.allPlayChampionTid, tid);
    if (med && ap) won.push({ key: "Board", rec: "median / all-play" });
    else if (med) won.push({ key: "Board", rec: "median champion" });
    else if (ap) won.push({ key: "Board", rec: "all-play champion" });
    if (A.sameId(t.rotoChampionTid, tid)) won.push({ key: "Roto", rec: "roto champion" });
    return won;
  }

  function labCard(title, sub, body) {
    return `<section class="card lab-card"><div class="card-head"><div><h2>${title}</h2><div class="card-sub">${sub}</div></div></div>${body}</section>`;
  }

  function emptyLab(msg) {
    return A.notice(msg);
  }

  function axisOpts(yTitle) {
    return {
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: { legend: { labels: { boxWidth: 10, usePointStyle: true, pointStyle: "circle", color: "#7d8aa0" } } },
      scales: {
        y: { grid: { color: A.C.grid }, border: { display: false }, title: yTitle ? { display: true, text: yTitle } : undefined },
        x: { grid: { display: false }, border: { display: false } },
      },
    };
  }

  function collectLabRows(all, one) {
    if (one) return [one];
    const allowed = new Set(A.squadYears(squad));
    const rows = [];
    (all || []).forEach(({ year: y, data }) => {
      if (!allowed.has(y)) return;
      const tid = A.teamIdFor(y, squad);
      if (tid == null) return;
      rows.push({ y: y, yd: Object.assign({ year: y }, data), tid: tid, t: teamOf(squad, y) });
    });
    rows.sort((a, b) => a.y - b.y);
    return rows;
  }

  function chip(val, lab, rank, n) {
    const rk = rankLine(rank, n);
    return `<div class="lab-chip"><b>${val}</b><span>${lab}${rk ? ' <span class="rk">' + rk + "</span>" : ""}</span></div>`;
  }

  async function renderLab(opts) {
    const el = $("lab-block");
    if (!el) return;
    killLabCharts();
    await loadPlayerIndex();
    const rows = collectLabRows(opts.all, opts.one);
    const face = A.squadInfo(squad) || {};
    const fname = face.currentName || A.franchiseName(squad) || "Franchise";
    if (!rows.length) {
      el.hidden = false;
      el.innerHTML = labCard("Franchise Lab", fname, emptyLab("No season payload for this franchise in the selected range."));
      return;
    }
    const cum = scope === "cum";
    const sub = cum
      ? fname + " · year-to-year · ranks computed from each season file"
      : fname + " · " + rows[0].y + " · one franchise + league rank";
    const html = [];
    html.push(`<div class="section-break"><h2>Franchise Lab <span>${esc(sub)}</span></h2></div>`);
    html.push(labScoringHTML(rows, cum));
    html.push('<div class="second-grid">');
    html.push(labRecordHTML(rows, cum));
    html.push(labLuckHTML(rows, cum));
    html.push("</div>");
    html.push('<div class="second-grid">');
    html.push(labIQHTML(rows, cum));
    html.push(labDNAHTML(rows, cum));
    html.push("</div>");
    html.push('<div class="second-grid">');
    html.push(labEPAHTML(rows, cum));
    html.push(labTrophiesHTML(rows, cum));
    html.push("</div>");
    html.push('<div class="second-grid">');
    html.push(labReportHTML(rows, cum));
    html.push(labWhatIfHTML(rows, cum));
    html.push("</div>");
    html.push('<div class="second-grid">');
    html.push(labWaiverHTML(rows, cum));
    html.push(labParHTML(rows, cum));
    html.push("</div>");
    html.push(labSpotracHTML(rows, cum));
    el.hidden = false;
    el.innerHTML = html.join("");
    paintScoring(rows, cum);
    paintRecord(rows, cum);
    paintLuck(rows, cum);
    paintIQ(rows, cum);
    paintDNA(rows, cum);
    paintEPA(rows, cum);
    paintReport(rows, cum);
    paintWhatIf(rows, cum);
    paintPar(rows, cum);
    paintSpotrac(rows, cum);
  }

  function labScoringHTML(rows, cum) {
    const last = rows[rows.length - 1];
    const leaguePF = last && last.t ? ((A.data.seasons[String(last.y)] || {}).teams || []).map((x) => x.pf) : [];
    const rk = last && last.t ? rankOf(leaguePF, last.t.pf, true) : null;
    const sub = cum
      ? "points for and points per game · each season this franchise played"
      : "weekly line · this franchise · league high / avg / low as context" + (rk ? " · PF " + rankLine(rk, leaguePF.length) : "");
    return labCard("Scoring", sub, `<div class="chart-wrap tall"><canvas id="lab-score-chart"></canvas></div>`);
  }

  function paintScoring(rows, cum) {
    if (cum) {
      const labels = rows.map((r) => String(r.y));
      const pf = rows.map((r) => r.t ? r.t.pf : null);
      const gp = rows.map((r) => r.t ? ((r.t.wins || 0) + (r.t.losses || 0) + (r.t.ties || 0)) : 0);
      const ppg = rows.map((r, i) => (gp[i] ? (r.t.pf || 0) / gp[i] : null));
      mkLab("lab-score-chart", {
        type: "bar",
        data: {
          labels: labels,
          datasets: [
            { type: "bar", label: "Points for", data: pf, backgroundColor: "#2f7bff99", borderRadius: 5, maxBarThickness: 28, yAxisID: "y" },
            { type: "line", label: "PPG", data: ppg, borderColor: A.C.gold, backgroundColor: A.C.gold, borderWidth: 2, pointRadius: 3, yAxisID: "y1", tension: 0.25 },
          ],
        },
        options: {
          maintainAspectRatio: false,
          interaction: { mode: "index", intersect: false },
          plugins: { legend: { labels: { boxWidth: 10, usePointStyle: true, pointStyle: "circle", color: "#7d8aa0" } } },
          scales: {
            y: { grid: { color: A.C.grid }, border: { display: false }, title: { display: true, text: "PF" } },
            y1: { position: "right", grid: { display: false }, border: { display: false }, title: { display: true, text: "PPG" } },
            x: { grid: { display: false }, border: { display: false } },
          },
        },
      });
      return;
    }
    const r = rows[0];
    const wks = weeklyScores(r.yd, r.tid);
    if (!wks.length) {
      const wrap = $("lab-score-chart") && $("lab-score-chart").parentNode;
      if (wrap) wrap.innerHTML = emptyLab("No weekly scores stored for this season.");
      return;
    }
    mkLab("lab-score-chart", {
      type: "line",
      data: {
        labels: wks.map((w) => "W" + w.week),
        datasets: [
          { label: "League high", data: wks.map((w) => w.max), borderColor: "#ff8a3d", borderWidth: 1.5, pointRadius: 0, tension: 0.4, fill: false },
          { label: "League average", data: wks.map((w) => w.avg), borderColor: A.C.blue, borderWidth: 1.5, pointRadius: 0, tension: 0.4, borderDash: [4, 3], fill: false },
          { label: "League low", data: wks.map((w) => w.min), borderColor: A.C.steel, borderWidth: 1, pointRadius: 0, tension: 0.4, fill: false },
          { label: "This franchise", data: wks.map((w) => w.pts), borderColor: A.C.gold, backgroundColor: A.C.gold, borderWidth: 2.5, pointRadius: 3.5, pointBorderColor: "#05060b", tension: 0.3, fill: false },
        ],
      },
      options: axisOpts("pts"),
    });
  }

  function labRecordHTML(rows, cum) {
    const last = rows[rows.length - 1];
    const t = last && last.t;
    const teams = last ? ((A.data.seasons[String(last.y)] || {}).teams || []) : [];
    const ap = t ? (t.allplayW || 0) / Math.max(1, (t.allplayW || 0) + (t.allplayL || 0)) : null;
    const aps = teams.map((x) => (x.allplayW || 0) / Math.max(1, (x.allplayW || 0) + (x.allplayL || 0)));
    const wins = teams.map((x) => x.wins || 0);
    const sub = cum
      ? "regular-season W-L and all-play% · each season"
      : ("this season · " + rec(t) + (t && t.finalRank != null ? " · finish " + finish(t) : "") +
        (ap != null ? " · all-play " + A.fmt(ap * 100, 1) + "% " + rankLine(rankOf(aps, ap, true), teams.length) : ""));
    const chips = (!cum && t) ? `<div class="lab-rankline">
      ${chip(rec(t), "W-L", rankOf(wins, t.wins || 0, true), teams.length)}
      ${chip(ap != null ? A.fmt(ap * 100, 1) + "%" : "—", "all-play", rankOf(aps, ap, true), teams.length)}
      ${chip(finish(t), "finish", t.finalRank, teams.length)}
    </div>` : "";
    return labCard("Record / Race", sub, chips + `<div class="chart-wrap"><canvas id="lab-record-chart"></canvas></div>`);
  }

  function paintRecord(rows, cum) {
    if (!cum) {
      const r = rows[0];
      let w = 0;
      const cumW = [];
      const labels = [];
      Object.entries(r.yd.weeks || {}).forEach(([wk, gs]) => {
        if (r.yd.regWeeks && +wk > r.yd.regWeeks) return;
        (gs || []).forEach((g) => {
          if (!(A.sameId(g.home.tid, r.tid) || A.sameId(g.away.tid, r.tid))) return;
          const me = A.sameId(g.home.tid, r.tid) ? g.home : g.away;
          const opp = A.sameId(g.home.tid, r.tid) ? g.away : g.home;
          if (me.pts > opp.pts) w += 1;
          labels.push("W" + wk);
          cumW.push(w);
        });
      });
      if (!labels.length) return;
      mkLab("lab-record-chart", {
        type: "line",
        data: { labels: labels, datasets: [{ label: "Cumulative wins", data: cumW, borderColor: A.C.blue, backgroundColor: A.C.blue, borderWidth: 2, pointRadius: 3, tension: 0.2 }] },
        options: axisOpts("wins"),
      });
      return;
    }
    const labels = rows.map((r) => String(r.y));
    const winPct = rows.map((r) => {
      if (!r.t) return null;
      const g = (r.t.wins || 0) + (r.t.losses || 0) + (r.t.ties || 0);
      return g ? (r.t.wins || 0) / g : null;
    });
    const ap = rows.map((r) => {
      if (!r.t) return null;
      const g = (r.t.allplayW || 0) + (r.t.allplayL || 0);
      return g ? (r.t.allplayW || 0) / g : null;
    });
    mkLab("lab-record-chart", {
      type: "line",
      data: {
        labels: labels,
        datasets: [
          { label: "Win%", data: winPct.map((v) => v == null ? null : v * 100), borderColor: A.C.blue, backgroundColor: A.C.blue, borderWidth: 2, pointRadius: 3, tension: 0.2 },
          { label: "All-play%", data: ap.map((v) => v == null ? null : v * 100), borderColor: A.C.gold, backgroundColor: A.C.gold, borderWidth: 2, pointRadius: 3, tension: 0.2 },
        ],
      },
      options: axisOpts("%"),
    });
  }

  function labLuckHTML(rows, cum) {
    const last = rows[rows.length - 1];
    const lc = last ? ((last.yd.luckCard || []).find((x) => A.sameId(x.tid, last.tid)) || null) : null;
    const lucks = last ? (last.yd.luckCard || []).map((x) => x.scheduleLuckWins) : [];
    const rk = lc ? rankOf(lucks, lc.scheduleLuckWins, true) : null;
    const sub = cum
      ? "luckCard · schedule luck wins · median W-L · each season"
      : (lc
        ? ("actual " + lc.actualW + "-" + lc.actualL + " · median " + lc.medianW + "-" + lc.medianL +
          " · sched luck " + signed(lc.scheduleLuckWins, 2) + (rk ? " · " + rankLine(rk, lucks.length) : ""))
        : "luckCard is not in this season file");
    const body = (cum || lc)
      ? `<div class="chart-wrap"><canvas id="lab-luck-chart"></canvas></div>`
      : emptyLab("Luck card is not in this season file.");
    return labCard("Luck", sub, body);
  }

  function paintLuck(rows, cum) {
    const series = rows.map((r) => {
      const lc = (r.yd.luckCard || []).find((x) => A.sameId(x.tid, r.tid));
      return {
        y: r.y,
        luck: r.t && r.t.luck != null ? r.t.luck : (lc && lc.scheduleLuckWins),
        sched: lc && lc.scheduleLuckWins,
        medW: lc && lc.medianW,
      };
    });
    if (!cum) {
      const s = series[0];
      if (!s || (s.luck == null && s.sched == null)) return;
      mkLab("lab-luck-chart", {
        type: "bar",
        data: {
          labels: ["Luck", "Sched luck", "Median W"],
          datasets: [{ data: [s.luck, s.sched, s.medW], backgroundColor: [s.luck >= 0 ? "#c8ff00cc" : "#3a4a63cc", "#47a8ffcc", "#ffc400cc"], borderRadius: 5, maxBarThickness: 36 }],
        },
        options: { maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { y: { grid: { color: A.C.grid }, border: { display: false } }, x: { grid: { display: false }, border: { display: false } } } },
      });
      return;
    }
    if (!series.some((s) => s.luck != null || s.sched != null)) {
      const c = $("lab-luck-chart");
      if (c && c.parentNode) c.parentNode.innerHTML = emptyLab("No luckCard rows across these seasons.");
      return;
    }
    mkLab("lab-luck-chart", {
      type: "line",
      data: {
        labels: series.map((s) => String(s.y)),
        datasets: [
          { label: "Luck", data: series.map((s) => s.luck), borderColor: A.C.green, backgroundColor: A.C.green, borderWidth: 2, pointRadius: 3, tension: 0.2, spanGaps: true },
          { label: "Sched luck W", data: series.map((s) => s.sched), borderColor: A.C.blue, backgroundColor: A.C.blue, borderWidth: 2, pointRadius: 3, tension: 0.2, spanGaps: true },
          { label: "Median W", data: series.map((s) => s.medW), borderColor: A.C.gold, backgroundColor: A.C.gold, borderWidth: 2, pointRadius: 3, tension: 0.2, spanGaps: true },
        ],
      },
      options: axisOpts(""),
    });
  }

  function labIQHTML(rows, cum) {
    const last = rows[rows.length - 1];
    const iq = last ? ((last.yd.lineupIQ || []).find((x) => A.sameId(x.teamId, last.tid)) || null) : null;
    const effs = last ? (last.yd.lineupIQ || []).map((x) => x.eff) : [];
    const rk = iq ? rankOf(effs, iq.eff, true) : null;
    const sub = cum
      ? "actual vs wasted · efficiency% · years with lineups"
      : (iq
        ? (A.fmt(iq.actual, 1) + " started · " + A.fmt(iq.wasted, 1) + " wasted · " + A.fmt(iq.eff * 100, 1) + "% eff" + (rk ? " · " + rankLine(rk, effs.length) : ""))
        : "lineupIQ is not in this season file");
    const body = (cum || iq)
      ? `<div class="chart-wrap"><canvas id="lab-iq-chart"></canvas></div>`
      : emptyLab("Lineup IQ needs weekly lineups, which start in 2018.");
    return labCard("Lineup IQ", sub, body);
  }

  function paintIQ(rows, cum) {
    const series = rows.map((r) => {
      const iq = (r.yd.lineupIQ || []).find((x) => A.sameId(x.teamId, r.tid));
      return { y: r.y, iq: iq };
    });
    if (!cum) {
      const iq = series[0] && series[0].iq;
      if (!iq) return;
      mkLab("lab-iq-chart", {
        type: "bar",
        data: {
          labels: ["This franchise"],
          datasets: [
            { label: "Points started", data: [iq.actual], backgroundColor: "#2f7bffcc", stack: "s", borderRadius: 4, maxBarThickness: 28 },
            { label: "Left on bench", data: [iq.wasted], backgroundColor: "#ff2d1abb", stack: "s", borderRadius: 4, maxBarThickness: 28 },
          ],
        },
        options: {
          indexAxis: "y",
          maintainAspectRatio: false,
          plugins: { legend: { labels: { boxWidth: 10, usePointStyle: true, pointStyle: "circle", color: "#7d8aa0" } } },
          scales: { x: { stacked: true, grid: { color: A.C.grid }, border: { display: false } }, y: { stacked: true, grid: { display: false }, border: { display: false } } },
        },
      });
      return;
    }
    if (!series.some((s) => s.iq)) {
      const c = $("lab-iq-chart");
      if (c && c.parentNode) c.parentNode.innerHTML = emptyLab("No lineupIQ rows across these seasons. Weekly lineups start in 2018.");
      return;
    }
    mkLab("lab-iq-chart", {
      type: "bar",
      data: {
        labels: series.map((s) => String(s.y)),
        datasets: [
          { label: "Started", data: series.map((s) => s.iq ? s.iq.actual : null), backgroundColor: "#2f7bffcc", stack: "s", maxBarThickness: 22 },
          { label: "Wasted", data: series.map((s) => s.iq ? s.iq.wasted : null), backgroundColor: "#ff2d1abb", stack: "s", maxBarThickness: 22 },
          { type: "line", label: "Eff %", data: series.map((s) => s.iq ? s.iq.eff * 100 : null), borderColor: A.C.gold, backgroundColor: A.C.gold, borderWidth: 2, pointRadius: 3, yAxisID: "y1", spanGaps: true },
        ],
      },
      options: {
        maintainAspectRatio: false,
        plugins: { legend: { labels: { boxWidth: 10, usePointStyle: true, pointStyle: "circle", color: "#7d8aa0" } } },
        scales: {
          y: { stacked: true, grid: { color: A.C.grid }, border: { display: false } },
          y1: { position: "right", min: 70, max: 100, grid: { display: false }, border: { display: false }, title: { display: true, text: "eff %" } },
          x: { stacked: true, grid: { display: false }, border: { display: false } },
        },
      },
    });
  }

  function labDNAHTML(rows, cum) {
    const last = rows[rows.length - 1];
    const mine = last ? ((last.yd.posDNA || {})[String(last.tid)] || (last.yd.posDNA || {})[last.tid]) : null;
    const sub = cum
      ? "started points by position · stacked by year"
      : (mine ? "this franchise vs league-average mix · started points" : "posDNA is not in this season file");
    const body = (cum || mine)
      ? `<div class="chart-wrap"><canvas id="lab-dna-chart"></canvas></div>`
      : emptyLab("Position DNA needs weekly lineups, which start in 2018.");
    return labCard("Position DNA", sub, body);
  }

  function paintDNA(rows, cum) {
    if (!cum) {
      const r = rows[0];
      const dna = r.yd.posDNA || {};
      const mine = dna[String(r.tid)] || dna[r.tid];
      if (!mine || !Object.keys(dna).length) return;
      const n = Object.keys(dna).length;
      const avg = {};
      POS_ORDER.forEach((p) => {
        let s = 0;
        Object.values(dna).forEach((d) => { s += (d && d[p]) || 0; });
        avg[p] = n ? s / n : 0;
      });
      mkLab("lab-dna-chart", {
        type: "bar",
        data: {
          labels: ["This franchise", "League avg"],
          datasets: POS_ORDER.map((p) => ({
            label: p, data: [mine[p] || 0, avg[p] || 0], backgroundColor: POS_COLORS[p], stack: "dna", maxBarThickness: 40,
          })),
        },
        options: {
          maintainAspectRatio: false,
          plugins: { legend: { labels: { boxWidth: 10, usePointStyle: true, pointStyle: "circle", color: "#7d8aa0" } } },
          scales: { x: { stacked: true, grid: { display: false }, border: { display: false } }, y: { stacked: true, grid: { color: A.C.grid }, border: { display: false } } },
        },
      });
      return;
    }
    if (!rows.some((r) => r.yd.posDNA && (r.yd.posDNA[String(r.tid)] || r.yd.posDNA[r.tid]))) {
      const c = $("lab-dna-chart");
      if (c && c.parentNode) c.parentNode.innerHTML = emptyLab("No posDNA across these seasons. Weekly lineups start in 2018.");
      return;
    }
    mkLab("lab-dna-chart", {
      type: "bar",
      data: {
        labels: rows.map((r) => String(r.y)),
        datasets: POS_ORDER.map((p) => ({
          label: p,
          data: rows.map((r) => {
            const d = (r.yd.posDNA || {})[String(r.tid)] || (r.yd.posDNA || {})[r.tid] || {};
            return d[p] || null;
          }),
          backgroundColor: POS_COLORS[p], stack: "dna", maxBarThickness: 22,
        })),
      },
      options: {
        maintainAspectRatio: false,
        plugins: { legend: { labels: { boxWidth: 10, usePointStyle: true, pointStyle: "circle", color: "#7d8aa0" } } },
        scales: { x: { stacked: true, grid: { display: false }, border: { display: false } }, y: { stacked: true, grid: { color: A.C.grid }, border: { display: false } } },
      },
    });
  }

  function labEPAHTML(rows, cum) {
    const last = rows[rows.length - 1];
    const fa = last ? ((last.yd.franchiseAdv || []).find((x) => A.sameId(x.teamId, last.tid)) || null) : null;
    const epas = last ? (last.yd.franchiseAdv || []).map((x) => x.epa) : [];
    const rk = fa ? rankOf(epas, fa.epa, true) : null;
    const sub = cum
      ? "starter EPA · franchiseAdv · each season with nflverse"
      : (fa ? (signed(fa.epa, 1) + " EPA" + (rk ? " · " + rankLine(rk, epas.length) : "")) : "franchiseAdv is not in this season file");
    const body = (cum || fa)
      ? `<div class="chart-wrap"><canvas id="lab-epa-chart"></canvas></div>`
      : emptyLab("Starter EPA needs weekly lineups joined to nflverse (2018+).");
    return labCard("Starter EPA", sub, body);
  }

  function paintEPA(rows, cum) {
    const series = rows.map((r) => {
      const fa = (r.yd.franchiseAdv || []).find((x) => A.sameId(x.teamId, r.tid));
      return { y: r.y, epa: fa && fa.epa };
    });
    if (!cum) {
      const s = series[0];
      if (!s || s.epa == null) return;
      mkLab("lab-epa-chart", {
        type: "bar",
        data: { labels: ["This franchise"], datasets: [{ data: [s.epa], backgroundColor: s.epa >= 0 ? "#47a8ffcc" : "#ff2d1acc", borderRadius: 4, maxBarThickness: 36 }] },
        options: { indexAxis: "y", maintainAspectRatio: false, plugins: { legend: { display: false }, tooltip: { callbacks: { label: (c) => A.fmt(c.parsed.x, 1) + " EPA" } } }, scales: { x: { grid: { color: A.C.grid }, border: { display: false } }, y: { grid: { display: false }, border: { display: false } } } },
      });
      return;
    }
    if (!series.some((s) => s.epa != null)) {
      const c = $("lab-epa-chart");
      if (c && c.parentNode) c.parentNode.innerHTML = emptyLab("No franchiseAdv EPA across these seasons.");
      return;
    }
    mkLab("lab-epa-chart", {
      type: "bar",
      data: {
        labels: series.map((s) => String(s.y)),
        datasets: [{ label: "EPA", data: series.map((s) => s.epa), backgroundColor: series.map((s) => s.epa == null ? "#3a4a63" : (s.epa >= 0 ? "#47a8ffcc" : "#ff2d1acc")), borderRadius: 4, maxBarThickness: 22 }],
      },
      options: axisOpts("EPA"),
    });
  }

  function labTrophiesHTML(rows, cum) {
    const counts = { Cup: 0, Board: 0, Roto: 0 };
    const hits = [];
    rows.forEach((r) => {
      trophyWins(r.yd, r.tid).forEach((w) => {
        counts[w.key] = (counts[w.key] || 0) + 1;
        hits.push({ y: r.y, key: w.key, rec: w.rec });
      });
    });
    const last = rows[rows.length - 1];
    const seasonWon = last ? trophyWins(last.yd, last.tid) : [];
    const sub = cum
      ? ("career counts from trophies.h2hChampionTid / median / all-play / roto · " +
        counts.Cup + " Cup · " + counts.Board + " Board · " + counts.Roto + " Roto")
      : (seasonWon.length ? seasonWon.map((w) => w.key + " · " + w.rec).join(" · ") : "no trophy in " + (last ? last.y : "this season"));
    let body;
    if (cum) {
      body = `<div class="lab-trophy-list">
        ${["Cup", "Board", "Roto"].map((k) => `<div class="lab-trophy"><div class="tag">${k}</div><div class="nm">${counts[k]}</div><div class="rec">career</div></div>`).join("")}
      </div>` + (hits.length
        ? `<div class="table-scroll" style="margin-top:12px"><table class="tbl"><thead><tr><th>Year</th><th>Trophy</th><th>How</th></tr></thead><tbody>${
          hits.slice().reverse().map((h) => `<tr><td class="tnum">${h.y}</td><td>${esc(h.key)}</td><td>${esc(h.rec)}</td></tr>`).join("")
        }</tbody></table></div>`
        : emptyLab("This franchise has no Cup / Board / Roto rows in the year files."));
    } else if (seasonWon.length) {
      body = `<div class="lab-trophy-list">${seasonWon.map((w) => `<div class="lab-trophy"><div class="tag">${esc(w.key)}</div><div class="nm">${esc(w.rec)}</div></div>`).join("")}</div>`;
    } else {
      body = emptyLab("This franchise did not win Cup, Board, or Roto this season.");
    }
    return labCard("Trophies", sub, body);
  }

  function labReportHTML(rows, cum) {
    const last = rows[rows.length - 1];
    const rep = last ? ((last.yd.report || []).find((x) => A.sameId(x.teamId, last.tid)) || null) : null;
    const gpas = last ? (last.yd.report || []).map((x) => x.gpa) : [];
    const rk = rep ? rankOf(gpas, rep.gpa, true) : null;
    const sub = cum
      ? "gDraft · gLineup · gWaiver · gLuck · GPA by year"
      : (rep ? ("GPA " + A.fmt(rep.gpa, 2) + (rk ? " · " + rankLine(rk, gpas.length) : "") + (rep.verdict ? " · " + esc(rep.verdict) : "")) : "report card is not in this season file");
    if (!cum && !rep) return labCard("Report Card", sub, emptyLab("Manager grades need weekly lineups, which start in 2018."));
    const chips = (!cum && rep) ? `<div class="lab-rankline">
      ${chip(gradeChip(rep.gDraft), "draft")}
      ${chip(gradeChip(rep.gLineup), "lineups")}
      ${chip(gradeChip(rep.gWaiver), "waivers")}
      ${chip(gradeChip(rep.gLuck), "luck")}
      ${chip(A.fmt(rep.gpa, 2), "GPA", rk, gpas.length)}
    </div>` : "";
    const tbl = cum ? `<div class="table-scroll"><table class="tbl">
      <thead><tr><th>Year</th><th>Draft</th><th>Lineups</th><th>Waivers</th><th>Luck</th><th>GPA</th></tr></thead>
      <tbody>${rows.map((r) => {
        const rp = (r.yd.report || []).find((x) => A.sameId(x.teamId, r.tid));
        if (!rp) return `<tr><td class="tnum">${r.y}</td><td colspan="5" class="own">unavailable</td></tr>`;
        return `<tr><td class="tnum">${r.y}</td><td>${gradeChip(rp.gDraft)}</td><td>${gradeChip(rp.gLineup)}</td><td>${gradeChip(rp.gWaiver)}</td><td>${gradeChip(rp.gLuck)}</td><td class="tnum"><span class="gpa-badge">${A.fmt(rp.gpa, 2)}</span></td></tr>`;
      }).join("")}</tbody></table></div>` : "";
    return labCard("Report Card", sub, chips + tbl + `<div class="chart-wrap"><canvas id="lab-report-chart"></canvas></div>`);
  }

  function paintReport(rows, cum) {
    const series = rows.map((r) => {
      const rp = (r.yd.report || []).find((x) => A.sameId(x.teamId, r.tid));
      return { y: r.y, gpa: rp && rp.gpa };
    });
    if (!series.some((s) => s.gpa != null)) {
      const c = $("lab-report-chart");
      if (c && c.parentNode) c.parentNode.innerHTML = "";
      return;
    }
    mkLab("lab-report-chart", {
      type: cum ? "line" : "bar",
      data: {
        labels: series.map((s) => String(s.y)),
        datasets: [{ label: "GPA", data: series.map((s) => s.gpa), borderColor: A.C.gold, backgroundColor: cum ? A.C.gold : "#ffc40099", borderWidth: 2, pointRadius: 3, tension: 0.2, borderRadius: 4, maxBarThickness: 36, spanGaps: true }],
      },
      options: axisOpts("GPA"),
    });
  }

  function labWhatIfHTML(rows, cum) {
    const last = rows[rows.length - 1];
    const wi = last ? ((last.yd.whatif || []).find((x) => A.sameId(x.teamId, last.tid)) || null) : null;
    const sub = cum
      ? "what-if regular-season rank vs actual regular-season rank · each year"
      : (wi
        ? ("actual reg. rank #" + wi.actRank + " (" + wi.actW + "-" + wi.actL + ") · perfect #" + wi.optRank + " (" + wi.optW + "-" + wi.optL + ")")
        : "whatif is not in this season file");
    const body = (cum || wi)
      ? `<div class="chart-wrap"><canvas id="lab-whatif-chart"></canvas></div>`
      : emptyLab("What-if ranks need weekly lineups, which start in 2018.");
    return labCard("What-If", sub, body);
  }

  function paintWhatIf(rows, cum) {
    const series = rows.map((r) => {
      const wi = (r.yd.whatif || []).find((x) => A.sameId(x.teamId, r.tid));
      return { y: r.y, act: wi && wi.actRank, opt: wi && wi.optRank, fin: r.t && r.t.finalRank };
    });
    if (!series.some((s) => s.act != null || s.opt != null)) {
      const c = $("lab-whatif-chart");
      if (c && c.parentNode) c.parentNode.innerHTML = emptyLab("No what-if rows across these seasons.");
      return;
    }
    mkLab("lab-whatif-chart", {
      type: "line",
      data: {
        labels: series.map((s) => String(s.y)),
        datasets: [
          { label: "Actual reg. rank", data: series.map((s) => s.act), borderColor: A.C.blue, backgroundColor: A.C.blue, borderWidth: 2, pointRadius: 3, tension: 0.2, spanGaps: true },
          { label: "Perfect rank", data: series.map((s) => s.opt), borderColor: A.C.gold, backgroundColor: A.C.gold, borderWidth: 2, pointRadius: 3, tension: 0.2, spanGaps: true },
          { label: "Final finish", data: series.map((s) => s.fin), borderColor: A.C.ice, backgroundColor: A.C.ice, borderWidth: 1.5, borderDash: [4, 3], pointRadius: 2, tension: 0.2, spanGaps: true },
        ],
      },
      options: Object.assign(axisOpts("rank"), { scales: { y: { reverse: true, min: 1, max: 12, grid: { color: A.C.grid }, border: { display: false }, ticks: { stepSize: 1 } }, x: { grid: { display: false }, border: { display: false } } } }),
    });
  }

  function waiverPid(yd, name, tid) {
    const p = (yd.players || []).find((x) => x.name === name && (
      A.sameId(x.mainTeam, tid) || (x.wk || []).some((w) => A.sameId(w[3], tid))
    ));
    return p ? p.pid : null;
  }

  function labWaiverHTML(rows, cum) {
    const items = [];
    rows.forEach((r) => {
      (r.yd.waiver || []).forEach((w) => {
        if (A.sameId(w.teamId, r.tid)) items.push(Object.assign({ y: r.y }, w, { pid: w.pid || waiverPid(r.yd, w.name, r.tid) }));
      });
    });
    const sub = cum
      ? "undrafted / started adds from the year waiver list · this franchise only"
      : "undrafted / started adds on this franchise from the year waiver list";
    if (!items.length) {
      return labCard("Waiver", sub, emptyLab("No waiver-wire adds for this franchise in the selected range (or the year file has no waiver list)."));
    }
    const body = `<ul class="lab-waiver">${items.slice().reverse().map((w) => `
      <li>
        <span class="badge pos-${esc(w.pos)}">${esc(w.pos)}</span>
        ${A.playerLink(w.pid, w.name, { year: w.y, squad: squad })}
        <span class="own">${cum ? w.y + " · " : ""}${esc(w.nfl || "")}</span>
        <span class="pts">${A.fmt(w.stPts, 1)} st</span>
      </li>`).join("")}</ul>`;
    return labCard("Waiver", sub, body);
  }

  function labParHTML(rows, cum) {
    const sub = cum
      ? "auction PAR/$ by year · replacement baseline at the player's position · not raw league-wide Pts/$"
      : "each pick's PAR = pts − position replacement · grade is PAR/$ vs the league median PAR/$ at that position";
    if (cum) {
      return labCard("Auction PAR / $", sub, `<div class="chart-wrap"><canvas id="lab-par-chart"></canvas></div>`);
    }
    const r = rows[0];
    const auction = r.yd.draft && r.yd.draft.auction;
    if (!auction) {
      return labCard("Auction PAR / $", sub, emptyLab("This season was a snake draft — no auction dollars. PAR/$ is only graded in auction years."));
    }
    const bases = baselineMap(r.yd);
    if (!Object.keys(bases).length) {
      return labCard("Auction PAR / $", sub, emptyLab("No draftValue.baselines in this season file."));
    }
    const med = posMedianParpd((r.yd.draft && r.yd.draft.board) || [], bases);
    const picks = ((r.yd.draft && r.yd.draft.board) || []).filter((p) => A.sameId(p.tid, r.tid));
    const body = `<div class="table-scroll"><table class="tbl" id="lab-par-tbl">
      <thead><tr><th>Player</th><th>Pos</th><th>$</th><th>Pts</th><th>PAR</th><th>Pts / $</th><th>PAR / $</th><th>Pos med PAR/$</th><th>Residual</th></tr></thead>
      <tbody>${picks.map((p) => {
        const par = pickPar(p, bases);
        const bid = p.bid || 0;
        const ppd = bid ? (p.pts || 0) / bid : null;
        const parpd = (bid && par != null) ? par / bid : null;
        const m = med[normPos(p.pos)];
        const resid = (parpd != null && m != null) ? parpd - m : null;
        const cls = resid == null ? "" : (resid >= 0 ? "pos" : "neg");
        return `<tr>
          <td>${A.playerLink(p.pid, p.name, { year: r.y, squad: squad })}</td>
          <td><span class="badge pos-${esc(normPos(p.pos))}">${esc(p.pos)}</span></td>
          <td class="tnum">$${A.fmt(bid)}</td>
          <td class="tnum">${p.pts != null ? A.fmt(p.pts, 1) : "—"}</td>
          <td class="tnum">${par != null ? signed(par, 1) : "—"}</td>
          <td class="tnum">${ppd != null ? A.fmt(ppd, 2) : "—"}</td>
          <td class="tnum">${parpd != null ? A.fmt(parpd, 2) : "—"}</td>
          <td class="tnum">${m != null ? A.fmt(m, 2) : "—"}</td>
          <td class="tnum lab-resid ${cls}">${resid != null ? signed(resid, 2) : "—"}</td>
        </tr>`;
      }).join("")}</tbody></table></div>
      <p class="lab-note">Grade is PAR/$ versus the league median PAR/$ at that same position this year — never raw league-wide Pts/$. Pts/$ stays as a secondary column.</p>
      <div class="chart-wrap"><canvas id="lab-par-chart"></canvas></div>`;
    return labCard("Auction PAR / $", sub, body);
  }

  function paintPar(rows, cum) {
    if (cum) {
      const series = rows.map((r) => {
        const te = ((r.yd.draftValue || {}).teamEff || []).find((x) => A.sameId(x.teamId, r.tid));
        return { y: r.y, parpd: te && te.parPerDollar };
      });
      if (!series.some((s) => s.parpd != null)) {
        const c = $("lab-par-chart");
        if (c && c.parentNode) c.parentNode.innerHTML = emptyLab("No teamEff PAR/$ across these seasons (snake years have no auction dollars).");
        return;
      }
      mkLab("lab-par-chart", {
        type: "line",
        data: {
          labels: series.map((s) => String(s.y)),
          datasets: [
            { label: "PAR / $", data: series.map((s) => s.parpd), borderColor: A.C.gold, backgroundColor: A.C.gold, borderWidth: 2, pointRadius: 3, tension: 0.2, spanGaps: true },
            { label: "Replacement (0)", data: series.map(() => 0), borderColor: A.C.steel, borderWidth: 1, borderDash: [4, 3], pointRadius: 0 },
          ],
        },
        options: axisOpts("PAR/$"),
      });
      return;
    }
    const r = rows[0];
    const bases = baselineMap(r.yd);
    const med = posMedianParpd((r.yd.draft && r.yd.draft.board) || [], bases);
    const picks = ((r.yd.draft && r.yd.draft.board) || []).filter((p) => A.sameId(p.tid, r.tid));
    const byPos = {};
    picks.forEach((p) => {
      const pos = normPos(p.pos);
      const bid = p.bid || 0;
      const par = pickPar(p, bases);
      if (!byPos[pos]) byPos[pos] = { par: 0, spend: 0 };
      byPos[pos].par += par || 0;
      byPos[pos].spend += bid;
    });
    const labels = POS_ORDER.filter((p) => byPos[p] && byPos[p].spend);
    if (!labels.length) return;
    mkLab("lab-par-chart", {
      type: "bar",
      data: {
        labels: labels,
        datasets: [
          { label: "This franchise PAR/$", data: labels.map((p) => byPos[p].par / byPos[p].spend), backgroundColor: labels.map((p) => POS_COLORS[p]), borderRadius: 4, maxBarThickness: 28 },
          { label: "Pos median PAR/$", data: labels.map((p) => med[p]), backgroundColor: "#3a4a6388", borderRadius: 4, maxBarThickness: 28 },
        ],
      },
      options: axisOpts("PAR/$"),
    });
  }

  function spotracRowsFor(r) {
    const capBag = r.yd.nflCap || {};
    const hasTeamCap = (capBag.byTeam || []).length || (capBag.final || []).length || (capBag.topPlayers || []).length;
    const med = posMedianPpm(r.yd);
    const out = [];
    (r.yd.players || []).forEach((p) => {
      const on = A.sameId(p.mainTeam, r.tid) || (p.wk || []).some((w) => A.sameId(w[3], r.tid));
      if (!on) return;
      const cap = capHitFor(p.pid, r.y);
      if (cap == null) return;
      const pts = ptsOnTeam(p, r.tid);
      const ppm = cap ? pts / (cap / 1e6) : null;
      const pos = normPos(p.pos);
      const m = med[pos];
      const resid = (ppm != null && m != null) ? ppm - m : null;
      out.push({ pid: p.pid, name: p.name, pos: pos, cap: cap, pts: pts, ppm: ppm, med: m, resid: resid, y: r.y });
    });
    return { rows: out, hasTeamCap: !!hasTeamCap, med: med };
  }

  function labSpotracHTML(rows, cum) {
    const sub = cum
      ? "Spotrac residual vs the league median pts/$1M at that same position · by year — a $20M QB is not graded next to a $4M RB"
      : "this franchise's rostered players · NFL cap · fantasy pts while on this team · pts/$M vs the position median · residual";
    const packs = rows.map((r) => Object.assign({ y: r.y }, spotracRowsFor(r)));
    const any = packs.some((p) => p.rows.length);
    const anyCap = packs.some((p) => p.hasTeamCap || p.rows.length);
    if (!anyCap) {
      return labCard("Spotrac · pts / $1M", sub, emptyLab("No NFL cap / Spotrac rows in the selected range. Empty state — not a zero payroll."));
    }
    if (!any) {
      return labCard("Spotrac · pts / $1M", sub, emptyLab("Cap totals exist at the team grain, but no player-level cap hits matched this roster (or player_index has no hits)."));
    }
    let tables;
    if (cum) {
      tables = `<div class="table-scroll"><table class="tbl">
        <thead><tr><th>Year</th><th>Players</th><th>Median residual</th><th>Best residual</th><th>Worst residual</th></tr></thead>
        <tbody>${packs.slice().reverse().map((p) => {
          const res = p.rows.map((x) => x.resid).filter((v) => v != null);
          const medR = medianNums(res);
          const best = res.length ? Math.max.apply(null, res) : null;
          const worst = res.length ? Math.min.apply(null, res) : null;
          const cls = medR == null ? "" : (medR >= 0 ? "pos" : "neg");
          return `<tr>
            <td class="tnum">${p.y}</td>
            <td class="tnum">${p.rows.length}</td>
            <td class="tnum lab-resid ${cls}">${medR != null ? signed(medR, 1) : "—"}</td>
            <td class="tnum">${best != null ? signed(best, 1) : "—"}</td>
            <td class="tnum">${worst != null ? signed(worst, 1) : "—"}</td>
          </tr>`;
        }).join("")}</tbody></table></div>`;
    } else {
      const p = packs[packs.length - 1];
      const list = p.rows.slice().sort((a, b) => (b.resid == null) - (a.resid == null) || (b.resid || 0) - (a.resid || 0));
      tables = `<div class="table-scroll"><table class="tbl" id="lab-spotrac-tbl">
        <thead><tr><th>Player</th><th>Pos</th><th>NFL cap</th><th>Pts on team</th><th>Pts / $1M</th><th>Pos median pts/$M</th><th>Residual</th></tr></thead>
        <tbody>${list.map((x) => {
          const cls = x.resid == null ? "" : (x.resid >= 0 ? "pos" : "neg");
          return `<tr>
            <td>${A.playerLink(x.pid, x.name, { year: x.y, squad: squad })}</td>
            <td><span class="badge pos-${esc(x.pos)}">${esc(x.pos)}</span></td>
            <td class="tnum">${moneyM(x.cap)}</td>
            <td class="tnum">${A.fmt(x.pts, 1)}</td>
            <td class="tnum">${x.ppm != null ? A.fmt(x.ppm, 1) : "—"}</td>
            <td class="tnum">${x.med != null ? A.fmt(x.med, 1) : "—"}</td>
            <td class="tnum lab-resid ${cls}">${x.resid != null ? signed(x.resid, 1) : "—"}</td>
          </tr>`;
        }).join("")}</tbody></table></div>`;
    }
    return labCard("Spotrac · pts / $1M", sub,
      tables + `<p class="lab-note">Residual = this player's pts/$1M minus the league median pts/$1M at that same position that year. Raw league-wide spend is not the grade.</p>
      <div class="chart-wrap"><canvas id="lab-spotrac-chart"></canvas></div>`);
  }

  function paintSpotrac(rows, cum) {
    const packs = rows.map((r) => Object.assign({ y: r.y }, spotracRowsFor(r)));
    if (cum) {
      const labels = packs.map((p) => String(p.y));
      const mean = packs.map((p) => medianNums(p.rows.map((x) => x.resid)));
      if (!packs.some((p) => p.rows.length)) return;
      mkLab("lab-spotrac-chart", {
        type: "bar",
        data: { labels: labels, datasets: [{ label: "Median residual vs pos", data: mean, backgroundColor: mean.map((v) => v == null ? "#3a4a63" : (v >= 0 ? "#c8ff00cc" : "#ff2d1acc")), borderRadius: 4, maxBarThickness: 22 }] },
        options: axisOpts("pts/$M residual"),
      });
      return;
    }
    const pack = packs[0];
    if (!pack || !pack.rows.length) return;
    const by = {};
    pack.rows.forEach((x) => {
      if (x.resid == null) return;
      (by[x.pos] = by[x.pos] || []).push(x.resid);
    });
    const labels = POS_ORDER.filter((p) => by[p] && by[p].length);
    if (!labels.length) return;
    mkLab("lab-spotrac-chart", {
      type: "bar",
      data: {
        labels: labels,
        datasets: [{ label: "Median residual vs pos", data: labels.map((p) => medianNums(by[p])), backgroundColor: labels.map((p) => POS_COLORS[p]), borderRadius: 4, maxBarThickness: 28 }],
      },
      options: axisOpts("pts/$M residual"),
    });
  }


  /* CHI-84: franchise NGS route tree + O-line gap bars. */
  const RP_ROUTE_SHAPES = {
    GO: [[0, 0], [0, -152]],
    POST: [[0, 0], [0, -92], [-52, -150]],
    CORNER: [[0, 0], [0, -92], [56, -150]],
    CROSS: [[0, 0], [-18, -72], [-118, -88]],
    IN: [[0, 0], [0, -82], [-72, -82]],
    OUT: [[0, 0], [0, -82], [78, -82]],
    SLANT: [[0, 0], [-58, -72]],
    HITCH: [[0, 0], [0, -58], [10, -50]],
    SCREEN: [[0, 0], [22, 10], [58, 20]],
    FLAT: [[0, 0], [78, -10]]
  };
  const RP_TONE = { green: "#c8ff00", yellow: "#ffc400", red: "#ff2d1a" };
  let _ngsPosAvg = null;

  function parseNgsList(raw) {
    if (!raw) return [];
    if (Array.isArray(raw)) return raw;
    try { return JSON.parse(raw); } catch (e) { return []; }
  }
  function ngsPosAvgShare(kind, pos) {
    if (!_ngsPosAvg) _ngsPosAvg = buildNgsPosAvg();
    const bag = _ngsPosAvg[kind] || {};
    if (pos && bag[pos] && Object.keys(bag[pos]).length) return bag[pos];
    return bag._league || {};
  }
  function buildNgsPosAvg() {
    const out = { route: {}, hole: {} };
    const acc = { route: {}, hole: {} };
    const league = { route: { tot: 0, by: {} }, hole: { tot: 0, by: {} } };
    const players = (NGS_PROFILES && NGS_PROFILES.players) || {};
    Object.keys(players).forEach((id) => {
      const rec = players[id];
      const pos = rec && rec.pos;
      const routes = parseNgsList(rec && rec.top_routes_json);
      const holes = parseNgsList(rec && rec.top_holes_json);
      if (routes.length && pos) {
        acc.route[pos] = acc.route[pos] || { tot: 0, by: {} };
        routes.forEach((r) => {
          const k = r && r.route;
          if (!k) return;
          const y = Number(r.yds) || 0;
          acc.route[pos].by[k] = (acc.route[pos].by[k] || 0) + y;
          acc.route[pos].tot += y;
        });
      }
      if (holes.length && pos) {
        acc.hole[pos] = acc.hole[pos] || { tot: 0, by: {} };
        holes.forEach((h) => {
          const k = h && h.hole;
          if (!k) return;
          const y = Number(h.yds) || 0;
          acc.hole[pos].by[k] = (acc.hole[pos].by[k] || 0) + y;
          acc.hole[pos].tot += y;
        });
      }
    });
    (NGS_PROFILES.franchises || []).forEach((f) => {
      (f.routes || []).forEach((r) => {
        const k = r && r.route;
        if (!k) return;
        const y = Number(r.yds) || 0;
        league.route.by[k] = (league.route.by[k] || 0) + y;
        league.route.tot += y;
      });
      (f.holes || []).forEach((h) => {
        const k = h && h.hole;
        if (!k) return;
        const y = Number(h.yds) || 0;
        league.hole.by[k] = (league.hole.by[k] || 0) + y;
        league.hole.tot += y;
      });
    });
    ["route", "hole"].forEach((kind) => {
      Object.keys(acc[kind]).forEach((pos) => {
        const pack = acc[kind][pos];
        out[kind][pos] = {};
        if (!(pack.tot > 0)) return;
        Object.keys(pack.by).forEach((k) => { out[kind][pos][k] = pack.by[k] / pack.tot; });
      });
      out[kind]._league = {};
      if (league[kind].tot > 0) {
        Object.keys(league[kind].by).forEach((k) => {
          out[kind]._league[k] = league[kind].by[k] / league[kind].tot;
        });
      }
    });
    return out;
  }
  function ngsShareTone(share, avg) {
    if (share == null || avg == null || !(avg > 0)) return "yellow";
    const r = share / avg;
    if (r > 1.15) return "green";
    if (r < 0.85) return "red";
    return "yellow";
  }
  function ngsYardShares(items, nameKey) {
    const tot = (items || []).reduce((a, x) => a + (Number(x && x.yds) || 0), 0);
    return (items || []).map((x) => {
      const yds = Number(x && x.yds) || 0;
      return { name: x && x[nameKey], yds: yds, share: tot > 0 ? yds / tot : 0 };
    }).filter((x) => x.name);
  }
  function ngsSvgPath(pts, ox, oy) {
    return pts.map((p, i) => (i ? "L" : "M") + (ox + p[0]) + "," + (oy + p[1])).join(" ");
  }
  function renderNgsRouteTree(routes, pos) {
    if (!routes || !routes.length) return "";
    const rows = ngsYardShares(routes, "route");
    if (!rows.length) return "";
    const avgMap = ngsPosAvgShare("route", pos);
    const ox = 200, oy = 230;
    const LABEL_NUDGE = {
      GO: [0, -14], POST: [-18, -12], CORNER: [18, -12],
      CROSS: [-20, -6], IN: [-16, -8], OUT: [18, -8],
      SLANT: [-16, -6], HITCH: [20, 6], SCREEN: [18, 16], FLAT: [22, 4]
    };
    const extraKeys = rows.filter((r) => !RP_ROUTE_SHAPES[r.name]);
    let extraI = 0;
    const hashes = [];
    for (let y = 46; y <= 210; y += 20) {
      hashes.push(`<line x1="36" y1="${y}" x2="54" y2="${y}" stroke="#2a3a28" stroke-width="1"/>`);
      hashes.push(`<line x1="346" y1="${y}" x2="364" y2="${y}" stroke="#2a3a28" stroke-width="1"/>`);
    }
    const branches = rows.map((r) => {
      let shape = RP_ROUTE_SHAPES[r.name];
      if (!shape) {
        const span = extraKeys.length <= 1 ? 0 : (extraI / (extraKeys.length - 1) - 0.5) * 100;
        extraI += 1;
        shape = [[0, 0], [span, -130]];
      }
      const tone = ngsShareTone(r.share, avgMap[r.name]);
      const color = RP_TONE[tone];
      const end = shape[shape.length - 1];
      const nudge = LABEL_NUDGE[r.name] || [0, -10];
      const sw = 1.8 + r.share * 6;
      const label = A.esc(String(r.name)) + " " + (r.share * 100).toFixed(0) + "%";
      return `<path d="${ngsSvgPath(shape, ox, oy)}" fill="none" stroke="${color}" stroke-width="${sw.toFixed(1)}" stroke-linecap="round" stroke-linejoin="round"/>` +
        `<circle cx="${ox + end[0]}" cy="${oy + end[1]}" r="3.4" fill="${color}"/>` +
        `<text x="${ox + end[0] + nudge[0]}" y="${oy + end[1] + nudge[1]}" text-anchor="middle" fill="${color}" font-size="11" font-weight="700">${label}</text>`;
    }).join("");
    return `<figure class="rp-tree"><svg viewBox="0 0 400 280" role="img" aria-label="NGS route tree">` +
      `<rect x="24" y="16" width="352" height="248" rx="8" fill="#10180f"/>` +
      hashes.join("") +
      `<line x1="40" y1="${oy}" x2="360" y2="${oy}" stroke="#5a6a58" stroke-width="1.4" stroke-dasharray="4 4"/>` +
      branches +
      `<circle cx="${ox}" cy="${oy}" r="4.5" fill="#eef4ff"/></svg></figure>`;
  }
  function renderNgsHoleScheme(holes, pos) {
    if (!holes || !holes.length) return "";
    const rows = ngsYardShares(holes, "hole");
    if (!rows.length) return "";
    const avgMap = ngsPosAvgShare("hole", pos);
    const ORDER = ["LE", "LT", "LG", "MID", "RG", "RT", "RE"];
    const by = {};
    rows.forEach((r) => { by[r.name] = r; });
    const maxShare = Math.max(0.01, ...ORDER.map((k) => (by[k] && by[k].share) || 0));
    const baseY = 200, barMax = 140;
    const gapX = [40, 88, 136, 184, 232, 280, 328];
    const bars = ORDER.map((k, i) => {
      const r = by[k] || { name: k, yds: 0, share: 0 };
      const h = (r.share / maxShare) * barMax;
      const x = gapX[i];
      const tone = ngsShareTone(r.share || null, avgMap[k]);
      const color = RP_TONE[tone];
      const pct = (r.share * 100).toFixed(0) + "%";
      return `<rect class="rp-gap-bar" x="${x}" y="${(baseY - h).toFixed(1)}" width="28" height="${Math.max(h, 2).toFixed(1)}" rx="3" fill="${color}"/>` +
        `<text x="${x + 14}" y="${(baseY - h - 6).toFixed(1)}" text-anchor="middle" fill="${color}" font-size="11" font-weight="700">${pct}</text>` +
        `<text x="${x + 14}" y="${baseY + 16}" text-anchor="middle" fill="#c8d0dc" font-size="10" font-weight="700">${k}</text>`;
    }).join("");
    const ol = [[76, "LT"], [124, "LG"], [172, "C"], [220, "RG"], [268, "RT"]].map(([x, lab]) =>
      `<rect x="${x}" y="222" width="36" height="22" rx="4" fill="#1c2430" stroke="#3a4a63"/>` +
      `<text x="${x + 18}" y="237" text-anchor="middle" fill="#9aa8b8" font-size="9" font-weight="700">${lab}</text>`
    ).join("");
    return `<figure class="rp-scheme"><svg viewBox="0 0 400 260" role="img" aria-label="NGS run scheme">${bars}${ol}</svg></figure>`;
  }
  function ngsShare(x) {
    if (!x || x.share == null) return "—";
    return (Number(x.share) * 100).toFixed(1) + "%";
  }
  function renderNgs() {
    const el = $("ngs-block");
    if (!el) return;
    el.hidden = false;
    if (scope === "season" && year !== 2025) {
      el.innerHTML = `<div class="card-head"><div><h2>Franchise NGS 2025</h2>
        <div class="card-sub">routes and holes are 2025-only</div></div></div>
        ${A.notice("NGS routes and holes exist for 2025. Switch the season picker to 2025 or open career view.")}`;
      return;
    }
    const f = (NGS_PROFILES.franchises || []).find((x) => x.owner === squad);
    if (!f) {
      el.innerHTML = `<div class="card-head"><div><h2>Franchise NGS 2025</h2>
        <div class="card-sub">routes from rostered WR/TE/RB · holes from rostered RBs</div></div></div>
        ${A.notice("No 2025 NGS routes or holes for this franchise.")}`;
      return;
    }
    const name = A.franchiseName(f.owner) || f.name || "—";
    const topR = f.topRoute;
    const topH = f.topHole;
    const tree = renderNgsRouteTree(f.routes || []);
    const scheme = renderNgsHoleScheme(f.holes || []);
    el.innerHTML = `
      <div class="card-head">
        <div>
          <h2>Franchise NGS 2025</h2>
          <div class="card-sub">${A.esc(name)} · route yds ${A.fmt(f.routeYards, 0)} · hole yds ${A.fmt(f.holeYards, 0)} · 2025 only</div>
        </div>
      </div>
      <div class="ngs-mix">
        <div>
          <div class="card-sub">Routes · ${topR ? A.esc(topR.route) + " " + ngsShare(topR) : "—"}</div>
          ${tree}
        </div>
        <div>
          <div class="card-sub">Run scheme · ${topH ? A.esc(topH.hole) + " " + ngsShare(topH) : "—"}</div>
          ${scheme}
        </div>
      </div>`;
  }

    async function renderSeason() {
    const yd = await A.loadYear(year);
    const T = A.teams(year);
    const tid = A.teamIdFor(year, squad);
    const t = tid != null ? T[tid] : teamOf(squad, year);
    if (!t || tid == null) {
      showTeam(true);
      $("team-hero").innerHTML = A.notice("This franchise has no team in " + year + ".");
      ["team-kpis", "ngs-block", "years-block", "games-block", "draft-block", "spend-block", "trades-block", "activity-block", "roster-block", "season-roster-block", "roto-block", "lab-block"]
        .forEach((id) => { $(id).hidden = true; $(id).innerHTML = ""; });
      renderScorers();
      return;
    }
    showTeam(true);
    $("years-block").hidden = true;
    const sl = sliceYear(yd, tid);
    renderHero(t, careerRollup(squad));
    renderScorers();
    renderNgs();
    renderGames(sl.mine, tid, T);
    renderDraft(sl.picks, () => T);
    const bases = baselineMap(yd);
    renderSpendMix(sl.picks, !!(yd.draft && yd.draft.auction), "", {
      bases: bases,
      posMed: posMedianParpd(((yd.draft && yd.draft.board) || []), bases),
    });
    renderTrades(sl.trades, () => T);
    renderActivity(tid, year);
    renderSeasonRoster(tid, year);
    if (isPre2018(year)) {
      $("roster-block").hidden = true;
      $("roster-block").innerHTML = "";
    } else {
      renderRoster(sl.players, year);
    }
    await renderRotoSeason(tid);
    await renderLab({ one: { y: year, yd: Object.assign({ year: year }, yd), tid: tid, t: t } });
    mountTeamToc();
    const f = A.squadInfo(squad) || {};
    $("page-sub").textContent = (f.currentName || "") + " · " + year;
  }

  async function renderCum() {
    const all = await A.loadAllYears();
    const allowed = new Set(A.squadYears(squad));
    const bags = [];
    const picks = [];
    const trades = [];
    const mine = [];
    all.forEach(({ year: y, data }) => {
      if (!allowed.has(y)) return;
      const tid = A.teamIdFor(y, squad);
      if (tid == null) return;
      const sl = sliceYear(Object.assign({ year: y }, data), tid);
      sl.picks.forEach((p) => picks.push(Object.assign({}, p, { year: y })));
      sl.trades.forEach((tr) => trades.push(Object.assign({}, tr, { year: y })));
      sl.mine.forEach((g) => mine.push(g));
      bags.push({ year: y, players: sl.players });
    });
    picks.sort((a, b) => b.year - a.year || a.overall - b.overall);
    trades.sort((a, b) => b.year - a.year || a.wk - b.wk);
    mine.sort((a, b) => b.year - a.year || a.wk - b.wk);
    const players = mergePlayers(bags);
    const career = careerRollup(squad);
    const latest = career.rows[0] && career.rows[0].t;
    showTeam(true);
    renderHero(latest, career);
    renderScorers();
    renderNgs();
    renderYears(career);
    $("games-block").innerHTML = `
      <div class="card-head"><div><h2>Games</h2>
        <div class="card-sub">${mine.length} game${mine.length === 1 ? "" : "s"} across this franchise's seasons</div></div></div>
      ${mine.length
        ? `<div class="gm-list">${mine.map((it) => {
            const tid = A.teamIdFor(it.year, squad);
            return gameRow(it, tid, A.teams(it.year));
          }).join("")}</div>`
        : A.notice("No games stored for this franchise.")}`;
    renderDraft(picks);
    const auctionPicks = [];
    const snakeYears = [];
    all.forEach(({ year: y, data }) => {
      if (!allowed.has(y)) return;
      if (data.draft && data.draft.auction) {
        const tid = A.teamIdFor(y, squad);
        if (tid == null) return;
        ((data.draft && data.draft.board) || []).forEach((p) => {
          if (A.sameId(p.tid, tid)) auctionPicks.push(Object.assign({}, p, { year: y }));
        });
      } else if (data.draft) {
        snakeYears.push(y);
      }
    });
    renderSpendMix(
      auctionPicks,
      auctionPicks.length > 0,
      snakeYears.length
        ? ("Snake-draft years (" + snakeYears.join(", ") + ") have no auction dollars and are left out of this mix.")
        : (auctionPicks.length ? "" : "No auction seasons on file for this franchise."),
      {
        basesFor: (p) => {
          const bag = all.find((x) => x.year === p.year);
          return baselineMap(bag && bag.data);
        },
      }
    );
    renderTrades(trades, (y) => A.teams(y));
    const actEl = $("activity-block");
    if (actEl) {
      if (actChart) { try { actChart.destroy(); } catch (e) {} actChart = null; }
      actEl.hidden = true;
      actEl.innerHTML = "";
    }
    renderSeasonRoster(null, year);
    renderRoster(players, year);
    await renderRotoCareer();
    await renderLab({ all: all });
    mountTeamToc();
    const f = A.squadInfo(squad) || {};
    $("page-sub").textContent = (f.currentName || "") + " · career";
  }


  const TCOMP_SLOT_ORDER = ["QB", "RB", "WR", "TE", "FLEX", "K", "DST"];
  const TCOMP_ESPN_SLOT = { 0: "QB", 2: "RB", 4: "WR", 6: "TE", 16: "DST", 17: "K", 20: "BN", 21: "IR", 23: "FLEX" };
  const TCOMP_CAPTION_PRE = "2014–17: season snapshot, weekly benches and moves not recovered.";

  function tcompNormSlot(slot) {
    if (slot == null || slot === "") return "—";
    if (TCOMP_ESPN_SLOT[slot] != null) return TCOMP_ESPN_SLOT[slot];
    const n = Number(slot);
    if (!Number.isNaN(n) && TCOMP_ESPN_SLOT[n] != null) return TCOMP_ESPN_SLOT[n];
    const s = String(slot).toUpperCase();
    if (s === "D/ST" || s === "DEF") return "DST";
    if (s === "BE" || s === "BENCH") return "BN";
    return s;
  }

  function tcompIsStarter(slot) {
    return TCOMP_SLOT_ORDER.indexOf(tcompNormSlot(slot)) >= 0;
  }

  function tcompSlotRank(slot) {
    const s = tcompNormSlot(slot);
    const i = TCOMP_SLOT_ORDER.indexOf(s);
    if (i >= 0) return i;
    if (s === "BN") return 50;
    if (s === "IR") return 51;
    return 99;
  }

  function tcompYearSlots(yd) {
    const raw = (yd && yd.slots) || { QB: 1, RB: 2, WR: 2, TE: 1, FLEX: 1, K: 1, DST: 1 };
    const out = {};
    Object.keys(raw).forEach((k) => { out[tcompNormSlot(k)] = raw[k]; });
    return out;
  }

  function tcompName(owner) {
    return A.franchiseName(owner) || "—";
  }

  function tcompFace(owner) {
    return A.franchiseTeam(owner);
  }

  function tcompPid(v) {
    const n = Number(v);
    return Number.isNaN(n) ? v : n;
  }

  function tcompHowMaps(yd) {
    const draft = {};
    const trade = {};
    const waiver = {};
    const fa = {};
    function add(bag, tid, pid) {
      if (tid == null || pid == null || pid === "") return;
      const key = String(tid);
      if (!bag[key]) bag[key] = new Set();
      bag[key].add(tcompPid(pid));
    }
    ((yd && yd.draft && yd.draft.board) || []).forEach((p) => add(draft, p.tid, p.pid));
    ((yd && yd.trades) || []).forEach((tr) => {
      (tr.sides || []).forEach((s) => {
        (s.got || []).forEach((g) => add(trade, s.tid, g.pid));
      });
    });
    ((yd && yd.moves) || []).forEach((m) => {
      const bag = m.type === "WAIVER" ? waiver : (m.type === "FREEAGENT" ? fa : null);
      if (!bag) return;
      (m.add || []).forEach((a) => add(bag, m.tid, a.pid));
    });
    return { draft: draft, trade: trade, waiver: waiver, fa: fa };
  }

  function tcompHas(bag, tid, pid) {
    const set = bag[String(tid)];
    if (!set) return false;
    return set.has(tcompPid(pid));
  }

  function tcompHow(y, tid, pid, maps, drafted) {
    if (y < 2018) {
      if (drafted || tcompHas(maps.draft, tid, pid)) return "Draft";
      return "Snapshot";
    }
    if (tcompHas(maps.trade, tid, pid)) return "Trade";
    if (tcompHas(maps.draft, tid, pid)) return "Draft";
    if (tcompHas(maps.waiver, tid, pid)) return "Waiver";
    if (tcompHas(maps.fa, tid, pid)) return "FA";
    return "—";
  }

  function tcompLeagueWeek(yd) {
    if (!yd || Number(yd.year) < 2018) return { week: null, recovered: false, mode: "snapshot" };
    let has1 = false;
    let minW = null;
    (yd.players || []).forEach((p) => {
      (p.wk || []).forEach((w) => {
        const wk = +w[0];
        if (!wk) return;
        if (wk === 1) has1 = true;
        if (minW == null || wk < minW) minW = wk;
      });
    });
    if (has1) return { week: 1, recovered: true, mode: "weekly" };
    if (minW != null) return { week: minW, recovered: false, mode: "weekly" };
    return { week: null, recovered: false, mode: "missing" };
  }

  function tcompSnapshotRows(y, tid, yd) {
    const maps = tcompHowMaps(yd);
    const rows = seasonRosterRows(y, tid).filter((p) => p.snapshot);
    return rows.map((p) => {
      const slot = tcompNormSlot(p.slotName || p.slot);
      return {
        pid: p.pid,
        name: p.name,
        pos: p.pos,
        slot: slot,
        how: tcompHow(y, tid, p.pid, maps, !!p.drafted),
        pts: p.nflPts,
        starter: tcompIsStarter(slot),
      };
    });
  }

  function tcompWeeklyRows(y, tid, yd, week) {
    const maps = tcompHowMaps(yd);
    const out = [];
    (yd.players || []).forEach((p) => {
      const hit = (p.wk || []).find((w) => +w[0] === week && A.sameId(w[3], tid));
      if (!hit) return;
      const slot = tcompNormSlot(hit[4]);
      out.push({
        pid: p.pid,
        name: p.name,
        pos: p.pos,
        slot: slot,
        how: tcompHow(y, tid, p.pid, maps, false),
        pts: p.stPts != null ? p.stPts : p.tot,
        starter: tcompIsStarter(slot),
      });
    });
    return out;
  }

  function tcompSortRows(rows) {
    return rows.slice().sort((a, b) => {
      const ra = tcompSlotRank(a.slot);
      const rb = tcompSlotRank(b.slot);
      if (ra !== rb) return ra - rb;
      return String(a.name || "").localeCompare(String(b.name || ""));
    });
  }

  function tcompRoster(y, tid, yd) {
    if (y < 2018) return tcompSortRows(tcompSnapshotRows(y, tid, yd));
    const wk = tcompLeagueWeek(yd);
    if (wk.week == null) return [];
    return tcompSortRows(tcompWeeklyRows(y, tid, yd, wk.week));
  }

  function tcompTid(y, owner) {
    const c = A.canon(owner);
    const teams = ((A.data.seasons[String(y)] || {}).teams) || [];
    const t = teams.find((x) => A.canon(x.owner) === c);
    return t ? t.id : null;
  }

  function tcompYearFranchises(y) {
    const teams = ((A.data.seasons[String(y)] || {}).teams) || [];
    return teams.slice().sort((a, b) => tcompName(a.owner).localeCompare(tcompName(b.owner)));
  }

  function tcompHowChip(how) {
    const key = String(how || "—").toLowerCase().replace(/[^a-z]+/g, "");
    const lab = how || "—";
    return `<span class="tcomp-how tcomp-how-${esc(key || "unk")}">${esc(lab)}</span>`;
  }

  function tcompPlayerRow(p, y) {
    return `<li class="tcomp-row${p.starter ? "" : " tcomp-bn"}">
      <span class="tcomp-slot">${esc(p.slot)}</span>
      ${A.playerLink(p.pid, p.name, { year: y, squad: squad || undefined, cls: "tcomp-pl" })}
      ${tcompHowChip(p.how)}
    </li>`;
  }

  function tcompCard(y, team, yd) {
    const owner = team.owner;
    const name = tcompName(owner);
    const face = tcompFace(owner);
    const rows = tcompRoster(y, team.id, yd);
    const starters = rows.filter((r) => r.starter);
    const bench = rows.filter((r) => !r.starter);
    const slots = tcompYearSlots(yd);
    const slotLine = TCOMP_SLOT_ORDER.filter((s) => slots[s]).map((s) => (slots[s] > 1 ? slots[s] + s : s)).join(" · ");
    let body;
    if (!rows.length) {
      body = `<p class="tcomp-miss">${y < 2018 ? "Snapshot / not recovered." : "Weekly lineup not recovered."}</p>`;
    } else {
      body = `<ol class="tcomp-slots">${starters.map((p) => tcompPlayerRow(p, y)).join("")}</ol>`;
      if (bench.length) {
        const blab = y < 2018 ? "Bench · snapshot" : "Bench";
        body += `<div class="tcomp-bench-lab">${blab}</div>
          <ol class="tcomp-slots tcomp-bench">${bench.map((p) => tcompPlayerRow(p, y)).join("")}</ol>`;
      } else if (y < 2018) {
        body += `<p class="tcomp-miss">Weekly benches not recovered.</p>`;
      }
    }
    const on = squad && A.canon(squad) === A.canon(owner);
    return `<article class="tcomp-card${on ? " tcomp-on" : ""}" data-owner="${esc(owner)}">
      <header class="tcomp-head">
        ${A.logoHTML(face, "tcomp-logo")}
        <div class="tcomp-ident">
          <div class="tcomp-name">${esc(name)}</div>
          <div class="tcomp-meta">${starters.length} starter${starters.length === 1 ? "" : "s"}${slotLine ? " · " + esc(slotLine) : ""}</div>
        </div>
      </header>
      ${body}
    </article>`;
  }

  function tcompYearHTML(y, yd) {
    const teams = tcompYearFranchises(y);
    const wk = tcompLeagueWeek(Object.assign({ year: y }, yd));
    let cap;
    let sub;
    if (y < 2018) {
      cap = TCOMP_CAPTION_PRE;
      sub = y + " · season snapshot · " + teams.length + " franchise" + (teams.length === 1 ? "" : "s") + " · current names";
    } else if (wk.mode === "missing") {
      cap = "Weekly lineups not recovered.";
      sub = y + " · " + teams.length + " franchise" + (teams.length === 1 ? "" : "s");
    } else if (!wk.recovered) {
      cap = "Week 1 not recovered · showing week " + wk.week + " snapshot.";
      sub = y + " · week " + wk.week + " · " + teams.length + " franchise" + (teams.length === 1 ? "" : "s");
    } else {
      cap = "Week 1 starters and bench · how-built from draft, trades, and waivers when present.";
      sub = y + " · week 1 · " + teams.length + " franchise" + (teams.length === 1 ? "" : "s") + " · current names";
    }
    return `<div class="card-head"><div>
        <h2>Team composition</h2>
        <div class="card-sub">${esc(sub)}</div>
      </div></div>
      <p class="tcomp-caption">${esc(cap)}</p>
      <div class="tcomp-grid">${teams.map((t) => tcompCard(y, t, yd)).join("")}</div>`;
  }

  function tcompTop(rows) {
    let best = null;
    rows.forEach((r) => {
      if (r.pts == null) return;
      if (!best || r.pts > best.pts) best = r;
    });
    return best;
  }

  function tcompCumHTML(all) {
    const years = A.years().slice().sort((a, b) => a - b);
    const bag = {};
    all.forEach((item) => { bag[item.year] = item.data; });
    const fracs = A.squads().slice().sort((a, b) => {
      if (!!a.active !== !!b.active) return a.active ? -1 : 1;
      return (a.currentName || "").localeCompare(b.currentName || "");
    });
    const head = `<tr><th class="tcomp-fr">Franchise</th>${years.map((y) => `<th class="tnum">${y}</th>`).join("")}</tr>`;
    const body = fracs.map((f) => {
      const name = tcompName(f.owner);
      const cells = years.map((y) => {
        const tid = tcompTid(y, f.owner);
        if (tid == null) return `<td class="tcomp-cell tcomp-empty">—</td>`;
        const yd = bag[y] || {};
        const rows = tid == null ? [] : tcompRoster(y, tid, Object.assign({ year: y }, yd));
        const n = rows.filter((r) => r.starter).length;
        const top = tcompTop(rows.filter((r) => r.starter));
        const label = n ? String(n) : "—";
        const who = top && top.name ? `<span class="tcomp-top">${esc(top.name)}</span>` : "";
        return `<td class="tcomp-cell">
          <button type="button" class="tcomp-jump" data-tcomp-y="${y}" title="${esc(name + " · " + y)}">${label}${who}</button>
        </td>`;
      }).join("");
      const on = squad && A.canon(squad) === A.canon(f.owner);
      return `<tr class="${on ? "tcomp-on" : ""}"><th class="tcomp-fr">${esc(name)}</th>${cells}</tr>`;
    }).join("");
    return `<div class="card-head"><div>
        <h2>Team composition</h2>
        <div class="card-sub">franchise × year · starter count and top snapshot / week-1 scorer · current names · click a year</div>
      </div></div>
      <p class="tcomp-caption">${esc(TCOMP_CAPTION_PRE)}</p>
      <div class="table-scroll"><table class="tbl tcomp-cum">
        <thead>${head}</thead>
        <tbody>${body}</tbody>
      </table></div>`;
  }

  function tcompBindCum(el) {
    el.querySelectorAll("[data-tcomp-y]").forEach((b) => {
      b.addEventListener("click", () => {
        year = +b.dataset.tcompY;
        scope = "season";
        render();
      });
    });
  }

  async function renderTeamComp() {
    const el = $("tcomp-block");
    if (!el) return;
    el.hidden = false;
    if (scope === "cum") {
      const all = await A.loadAllYears();
      el.innerHTML = tcompCumHTML(all);
      tcompBindCum(el);
      return;
    }
    const yd = await A.loadYear(year);
    el.innerHTML = tcompYearHTML(year, Object.assign({ year: year }, yd));
  }

  async function render() {
    A.scopePicker($("scope-picker"), scope, (s) => { scope = s; render(); });
    A.squadPicker($("squad-picker"), squad, (s) => {
      squad = s;
      A.stampNav(squad);
      year = A.clampYear(year, squad);
      render();
    });
    A.stampNav(squad);
    A.showYearRow(scope === "season");
    const ylist = squad ? A.squadYears(squad) : A.years();
    if (squad) year = A.clampYear(year, squad);
    A.yearPicker($("year-picker"), year, (y) => { year = y; render(); }, null, ylist);

    if (!squad) {
      renderGrid();
      await renderTeamComp();
      return;
    }
    if (scope === "cum") await renderCum();
    else await renderSeason();
    await renderTeamComp();
  }

  document.addEventListener("affl:show-former", () => {
    if (!squad) render();
  });

  await render();
})();
