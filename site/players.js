/* Stars, Scrubs, & Duds — full NFL career logs + NGS. Blue=started (2018+ weekly and 2014–2017 recovered starters), gray=benched, teal=NFL-only (2018+). Gold=2014–2017 on AFFL roster (weekly lineup not recovered). */
(async function () {
  // goTeam: deep-links to Teams live on common; players stays league-wide.

  const A = window.AFFL;
  const $ = (s) => document.querySelector(s);
  await A.boot();
  await A.loadBios();
  window.__afflRenderPlayer = () => { if (cur) loadPlayer(cur.pid, false); };
  A.onNextMidnight(() => window.__afflRenderPlayer());
  A.chartDefaults(Chart);
  const C = A.C;
  const fmt = A.fmt;

  const INDEX = await fetch("player_index.json?v=" + Date.now(), { cache: "no-store" }).then((r) => r.json());
  const PROJ = await fetch("proj.json?v=" + Date.now(), { cache: "no-store" })
    .then((r) => (r.ok ? r.json() : {}))
    .catch(() => ({}));
  const NFL = await fetch("nfl_weeks.json?v=" + Date.now(), { cache: "no-store" })
    .then((r) => (r.ok ? r.json() : {}))
    .catch(() => ({}));
  const NGS = await fetch("ngs.json?v=" + Date.now(), { cache: "no-store" })
    .then((r) => (r.ok ? r.json() : {}))
    .catch(() => ({}));
  const YOFF = await fetch("yoff.json?v=" + Date.now(), { cache: "no-store" })
    .then((r) => (r.ok ? r.json() : {}))
    .catch(() => ({}));
  const PRE2018 = await fetch("pre2018_rosters.json?v=" + Date.now(), { cache: "no-store" })
    .then((r) => (r.ok ? r.json() : {}))
    .catch(() => ({}));
  const PRE2018_STARTS = await fetch("pre2018_starts.json?v=" + Date.now(), { cache: "no-store" })
    .then((r) => (r.ok ? r.json() : {}))
    .catch(() => ({}));
  const NGS_PROFILES = await fetch("ngs_profiles.json?v=" + Date.now(), { cache: "no-store" })
    .then((r) => (r.ok ? r.json() : { players: {} }))
    .catch(() => ({ players: {} }));
  const COLLEGE = await fetch("college_stats.json?v=" + Date.now(), { cache: "no-store" })
    .then((r) => (r.ok ? r.json() : {}))
    .catch(() => ({}));
  const OVERVIEW = await fetch("player_overview.json?v=" + Date.now(), { cache: "no-store" })
    .then((r) => (r.ok ? r.json() : {}))
    .catch(() => ({}));

  function weekProj(year, pid, wk) {
    const rec = ((PROJ[String(year)] || {})[String(pid)]) || {};
    const key = String(wk);
    if (!Object.prototype.hasOwnProperty.call(rec, key)) return null;
    const n = Number(rec[key]);
    return Number.isFinite(n) ? n : null;
  }

  function nflBlock(pid) {
    return NFL[String(pid)] || {};
  }

  function nflYearWeeks(pid, y) {
    return nflBlock(pid)[String(y)] || {};
  }

  function weekNgs(year, pid, wk) {
    const rec = ((NGS[String(pid)] || {})[String(year)]) || {};
    return rec[String(wk)] || null;
  }

  function isYearKey(k) { return /^\d{4}$/.test(String(k)); }
  function isWeekKey(k) { return /^\d+$/.test(String(k)) && +k > 0; }

  function nflSeasonPts(pid, y) {
    const rec = nflYearWeeks(pid, y);
    let s = 0, n = 0;
    Object.keys(rec).forEach((wk) => {
      if (!isWeekKey(wk)) return;
      const pts = rec[wk] && rec[wk].pts;
      if (pts != null && Number.isFinite(Number(pts))) { s += Number(pts); n++; }
    });
    return n ? s : null;
  }

  function nflCareerPts(pid) {
    const rec = nflBlock(pid);
    let s = 0, n = 0;
    Object.keys(rec).forEach((y) => {
      if (!isYearKey(y)) return;
      const v = nflSeasonPts(pid, y);
      if (v != null) { s += v; n++; }
    });
    return n ? s : null;
  }

  function nflTeam(pid, y) {
    const rec = y === "all" ? null : nflYearWeeks(pid, y);
    if (!rec) return "";
    const wks = Object.keys(rec).filter(isWeekKey).sort((a, b) => +a - +b);
    for (let i = wks.length - 1; i >= 0; i--) {
      if (rec[wks[i]] && rec[wks[i]].team) return rec[wks[i]].team;
    }
    return "";
  }

  function stubPlayer(pid) {
    const m = meta(pid);
    const md = nflBlock(pid).meta || {};
    const bioY = logYear === "all" ? ((m.years || [])[0]) : logYear;
    const bio = (A.playerBio(pid, bioY, A.today()) || {});
    return {
      pid: +pid,
      name: m.name || md.name || ("#" + pid),
      pos: m.pos || md.pos || "",
      nfl: md.nfl || nflTeam(pid, bioY) || bio.nfl || "",
      hs: md.hs || "",
      tot: 0, stPts: 0, starts: 0, wk: [], mainTeam: null,
    };
  }

  let RANK = null;
  function buildRanks() {
    if (RANK) return RANK;
    const rows = Object.keys(INDEX).map((pid) => ({
      pid: String(pid),
      pts: nflCareerPts(pid) || 0,
      pos: (INDEX[pid] && INDEX[pid].pos) || "",
    })).filter((r) => r.pts > 0);
    rows.sort((a, b) => b.pts - a.pts);
    const all = {};
    rows.forEach((r, i) => { all[r.pid] = { rank: i + 1, n: rows.length, pts: r.pts }; });
    const buckets = {};
    rows.forEach((r) => { if (r.pos) (buckets[r.pos] = buckets[r.pos] || []).push(r); });
    const pos = {};
    Object.keys(buckets).forEach((k) => {
      buckets[k].forEach((r, i) => { pos[r.pid] = { rank: i + 1, n: buckets[k].length, pos: k }; });
    });
    RANK = { all, pos };
    return RANK;
  }

  function bestWeek(rows) {
    const scored = (rows || []).filter((r) => r && r.w && r.w[1] != null);
    if (!scored.length) return null;
    return scored.slice().sort((a, b) => b.w[1] - a.w[1])[0];
  }

  let year = A.seasonFromURL();
  if (year == null) year = A.years()[0];
  let scope = A.seasonFromURL() == null ? "cum" : "season";
  let squad = A.squadFromURL();
  let YD = null, T = {}, cur = null, chart = null, ngsChart = null, careerChart = null, careerList = null;
  const YEAR_META = {};
  let logYear = null; // number or "all"
  let logSortKey = "week";
  let logSortDir = 1;
  let logView = null;
  let logFilter = { season: "all", owner: "all", role: "all" };
  let custodyMode = "table";
  const fgCharts = {};
  let seasonSortKey = "year";
  let seasonSortDir = -1;
  let franSortKey = "pts";
  let franSortDir = -1;
  let careerView = null;
  const PP = { q: "", pos: "QB", sort: "tot", limit: 24 };

  function tName(id, y) {
    const t = A.teams(y || year)[id];
    if (!t) return "—";
    return A.franchiseName(t.owner) || t.name || "—";
  }

  /* Card line: current A.franchiseName only. Never slice / singularise. */
  function cardOwner(p) {
    if (!p) return null;
    if (scope === "cum" && p.tids) {
      const ys = Object.keys(p.tids).map(Number).filter(Number.isFinite).sort((a, b) => b - a);
      for (let i = 0; i < ys.length; i++) {
        const y = ys[i];
        const tid = p.tids[y];
        const owner = A.ownerId(y, tid) || ((A.teams(y)[tid] || {}).owner);
        if (owner) return A.canon(owner);
      }
    }
    if (p.mainTeam != null && scope !== "cum") {
      const owner = A.ownerId(year, p.mainTeam) || ((A.teams(year)[p.mainTeam] || {}).owner);
      if (owner) return A.canon(owner);
    }
    return null;
  }

  function cardFranchise(p) {
    const owner = cardOwner(p);
    const name = owner ? A.franchiseName(owner) : "";
    return name || "unavailable";
  }

  function money(n) {
    if (n == null || Number.isNaN(Number(n))) return "—";
    const v = Number(n);
    const a = Math.abs(v);
    const sign = v < 0 ? "-" : "";
    if (a >= 1e6) return sign + "$" + (a / 1e6).toFixed(1) + "M";
    if (a >= 1e3) return sign + "$" + Math.round(a / 1e3) + "K";
    return sign + "$" + Math.round(a);
  }

  function meta(pid) {
    return INDEX[String(pid)] || { years: [], cap: [], contracts: [], xtd: {} };
  }

  function playerYears(pid) {
    const affl = (meta(pid).years || []).slice();
    const rec = nflBlock(pid);
    const nfl = Object.keys(rec).filter(isYearKey).map(Number);
    const pre = [];
    Object.keys(PRE2018 || {}).forEach((y) => {
      if ((PRE2018[y] || {})[String(pid)]) pre.push(+y);
    });
    Object.keys(PRE2018_STARTS || {}).forEach((y) => {
      if ((PRE2018_STARTS[y] || {})[String(pid)]) pre.push(+y);
    });
    return Array.from(new Set(affl.concat(nfl).concat(pre))).sort((a, b) => b - a);
  }

  function afflYears(pid) {
    const ys = new Set();
    (meta(pid).years || []).forEach((y) => ys.add(+y));
    Object.keys(PRE2018 || {}).forEach((y) => {
      const rec = (PRE2018[y] || {})[String(pid)];
      if (rec && (rec.tid != null || rec.draftTid != null)) ys.add(+y);
    });
    Object.keys(PRE2018_STARTS || {}).forEach((y) => {
      if ((PRE2018_STARTS[y] || {})[String(pid)]) ys.add(+y);
    });
    return Array.from(ys).sort((a, b) => a - b);
  }

  function afflSeasonCount(pid) {
    return afflYears(pid).length;
  }

  function yearHome(pid, y, rows) {
    const snap = preSnap(pid, y);
    if (snap && snap.tid != null) return snap.tid;
    if (snap && snap.draftTid != null) return snap.draftTid;
    let last = null;
    (rows || []).forEach((r) => {
      if (Number(r.y) !== Number(y) || r.w[3] == null) return;
      if (r.state === "nfl" || r.state === "unrecovered") return;
      if (!last || Number(r.w[0]) >= Number(last.w[0])) last = r;
    });
    return last ? last.w[3] : null;
  }

  function rosterStints(rows, y) {
    const list = (rows || []).filter((r) => {
      if (y != null && y !== "all" && Number(r.y) !== Number(y)) return false;
      if (r.state === "nfl" || r.state === "unrecovered") return false;
      return r.w[3] != null;
    }).slice().sort((a, b) => (Number(a.y) - Number(b.y)) || (Number(a.w[0]) - Number(b.w[0])));
    const stints = [];
    list.forEach((r) => {
      const tid = r.w[3];
      const wk = Number(r.w[0]);
      const yr = Number(r.y);
      const prev = stints[stints.length - 1];
      if (prev && Number(prev.tid) === Number(tid) && Number(prev.year) === yr) {
        prev.to = wk;
        prev.weeks.push(wk);
      } else {
        stints.push({ tid: tid, year: yr, from: wk, to: wk, weeks: [wk] });
      }
    });
    return stints;
  }

  function teamMark(tid, y) {
    const name = tName(tid, y);
    const t = A.teams(y || year)[tid] || {};
    const owner = t.owner;
    const logo = (owner && A.franchiseLogo(owner)) || t.logo || "";
    return { name: name, logo: logo, owner: owner, html: A.logoHTML({ name: name, logo: logo }, "journey-logo") };
  }

  function findPlayerTrade(pid, y, fromTid, toTid, wk) {
    const trades = ((YEAR_META[y] || {}).trades) || [];
    const hit = (t, needWk) => {
      if (needWk && wk != null && Number(t.wk) !== Number(wk)) return false;
      return (t.sides || []).some((s) => {
        if (toTid != null && Number(s.tid) !== Number(toTid)) return false;
        return (s.got || []).some((g) =>
          Number(g.pid) === Number(pid) && (fromTid == null || Number(g.from) === Number(fromTid)));
      });
    };
    return trades.find((t) => hit(t, true)) || trades.find((t) => hit(t, false)) || null;
  }

  function findPlayerClaim(pid, y, toTid, wk) {
    const moves = ((YEAR_META[y] || {}).moves) || [];
    for (let i = 0; i < moves.length; i++) {
      const m = moves[i];
      if (wk != null && Number(m.wk) !== Number(wk)) continue;
      if (toTid != null && m.tid != null && Number(m.tid) !== Number(toTid)) continue;
      const add = m.add;
      const items = Array.isArray(add) ? add : (add ? [add] : []);
      for (let j = 0; j < items.length; j++) {
        const a = items[j];
        const apid = (a && typeof a === "object") ? a.pid : a;
        if (Number(apid) === Number(pid)) return m;
      }
    }
    return null;
  }

  function movePhrase(pid, y, fromTid, toTid, wk) {
    const fromN = tName(fromTid, y);
    const toN = tName(toTid, y);
    const tr = findPlayerTrade(pid, y, fromTid, toTid, wk);
    if (tr) return "Traded W" + tr.wk + " " + fromN + " → " + toN;
    const mv = findPlayerClaim(pid, y, toTid, wk);
    if (mv) {
      const kind = String(mv.type || "waiver").toLowerCase();
      const label = (kind === "waiver" || kind === "freeagent" || kind === "add") ? "Waiver" : "Moved";
      return label + " W" + (mv.wk || wk) + " " + fromN + " → " + toN;
    }
    if (wk != null) return "Moved W" + wk + " " + fromN + " → " + toN;
    return "Moved " + fromN + " → " + toN;
  }

  function preSnap(pid, y) {
    if (y == null || y === "all" || +y >= 2018) return null;
    return ((PRE2018[String(y)] || {})[String(pid)]) || null;
  }

  function preStartsFor(pid, y) {
    if (y == null || y === "all" || +y >= 2018) return {};
    return ((PRE2018_STARTS[String(y)] || {})[String(pid)]) || {};
  }

  function isPre2018(y) {
    return y != null && y !== "all" && +y < 2018;
  }

  function ownerForTid(y, tid) {
    if (tid == null) return null;
    const oid = A.ownerId(y, tid);
    return oid ? A.canon(oid) : null;
  }

  function seasonFranchiseTid(pid, y, weekRows, yearPlayer) {
    if (yearPlayer && yearPlayer.mainTeam != null) return yearPlayer.mainTeam;
    const snap = preSnap(pid, y);
    if (snap && snap.tid != null) return snap.tid;
    if (snap && snap.draftTid != null) return snap.draftTid;
    return yearHome(pid, y, weekRows);
  }

  function countStarts(weekRows, yearPlayer, pid, y) {
    const yRows = (weekRows || []).filter((r) => Number(r.y) === Number(y));
    if (yRows.length) {
      const started = yRows.filter((r) => r.state === "started" || (r.state == null && r.w[2]));
      return { starts: started.length, stPts: started.reduce((a, r) => a + (Number(r.w[1]) || 0), 0), known: true };
    }
    if (yearPlayer && (yearPlayer.starts != null || yearPlayer.stPts != null)) {
      return { starts: yearPlayer.starts || 0, stPts: yearPlayer.stPts || 0, known: true };
    }
    const bag = preStartsFor(pid, y);
    const wks = Object.keys(bag || {});
    if (wks.length) {
      return {
        starts: wks.length,
        stPts: wks.reduce((a, k) => a + (Number(bag[k] && bag[k].pts) || 0), 0),
        known: true,
      };
    }
    return { starts: null, stPts: null, known: false };
  }

  async function careerSeasonRows(pid, weekRows) {
    const years = playerYears(pid);
    const out = [];
    for (const y of years) {
      let yp = null;
      try {
        const d = await A.loadYear(y);
        yp = ((d && d.players) || []).find((x) => Number(x.pid) === Number(pid)) || null;
      } catch (e) { yp = null; }
      const tid = seasonFranchiseTid(pid, y, weekRows, yp);
      const owner = ownerForTid(y, tid);
      const st = countStarts(weekRows, yp, pid, y);
      out.push({
        year: +y,
        owner: owner || null,
        franchise: owner ? (A.franchiseName(owner) || "—") : "—",
        logo: owner ? A.franchiseLogo(owner) : "",
        nfl: nflTeam(pid, y) || "",
        pts: nflSeasonPts(pid, y),
        starts: st.known ? st.starts : null,
        stPts: st.known ? st.stPts : null,
      });
    }
    return out;
  }

  function careerFranchiseRows(seasons) {
    const by = {};
    (seasons || []).forEach((s) => {
      if (!s.owner) return;
      const id = A.canon(s.owner);
      const a = by[id] || {
        owner: id,
        name: A.franchiseName(id) || "—",
        logo: A.franchiseLogo(id) || "",
        seasons: 0,
        pts: 0,
        starts: 0,
        hasPts: false,
        hasStarts: false,
      };
      a.seasons += 1;
      if (s.stPts != null) { a.pts += Number(s.stPts) || 0; a.hasPts = true; }
      if (s.starts != null) { a.starts += Number(s.starts) || 0; a.hasStarts = true; }
      by[id] = a;
    });
    return Object.values(by);
  }

  function franCell(owner, name, logo) {
    if (!owner || !name || name === "—") return "—";
    const href = "teams.html?squad=" + encodeURIComponent(owner);
    return `<div class="team-cell">${A.logoHTML({ name: name, logo: logo }, "mini")}<div><a class="hist-name" href="${href}">${A.esc(name)}</a></div></div>`;
  }

  function sortCareer(rows, key, dir, fallback) {
    return rows.slice().sort((a, b) => {
      const av = a[key], bv = b[key];
      const aMiss = av == null || av === "";
      const bMiss = bv == null || bv === "";
      if (aMiss && bMiss) return fallback(a, b);
      if (aMiss) return 1;
      if (bMiss) return -1;
      if (typeof av === "string" || typeof bv === "string") {
        const c = String(av).localeCompare(String(bv), undefined, { numeric: true });
        return c * dir || fallback(a, b);
      }
      if (Number(av) !== Number(bv)) return (Number(av) - Number(bv)) * dir;
      return fallback(a, b);
    });
  }

  function careerMark(key, label, cur, dir) {
    const on = cur === key;
    return `<th class="s${on ? " on" : ""}${on && dir > 0 ? " asc" : ""}" data-k="${key}">${label}</th>`;
  }

  function bindCareerSort() {
    const bind = (sel, getK, setK, getD, setD) => {
      const tbl = $(sel);
      if (!tbl || tbl.dataset.sortBound) return;
      tbl.dataset.sortBound = "1";
      tbl.addEventListener("click", (e) => {
        const th = e.target.closest("th[data-k]");
        if (!th || !tbl.contains(th)) return;
        const k = th.dataset.k;
        if (getK() === k) setD(getD() * -1);
        else { setK(k); setD((k === "year" || k === "name" || k === "franchise" || k === "nfl") ? 1 : -1); }
        if (careerView) renderCareerTables(careerView.pid, careerView.rows, careerView.seasons);
      });
    };
    bind("#pl-season-tbl", () => seasonSortKey, (k) => { seasonSortKey = k; }, () => seasonSortDir, (d) => { seasonSortDir = d; });
    bind("#pl-franchise-tbl", () => franSortKey, (k) => { franSortKey = k; }, () => franSortDir, (d) => { franSortDir = d; });
  }

  function renderCareerTables(pid, weekRows, seasons) {
    careerView = { pid: pid, rows: weekRows, seasons: seasons };
    const sec = $("#pl-career");
    if (!sec) return;
    sec.hidden = false;
    const seas = sortCareer(seasons, seasonSortKey, seasonSortDir, (a, b) => b.year - a.year);
    const frans = sortCareer(careerFranchiseRows(seasons), franSortKey, franSortDir, (a, b) => (b.pts - a.pts) || (b.starts - a.starts));
    const sh = (k, l) => careerMark(k, l, seasonSortKey, seasonSortDir);
    const fh = (k, l) => careerMark(k, l, franSortKey, franSortDir);
    $("#pl-season-tbl thead").innerHTML = `<tr>
      ${sh("year", "Year")}${sh("franchise", "AFFL")}${sh("nfl", "NFL")}${sh("pts", "Season pts")}${sh("starts", "Starts")}${sh("stPts", "Started pts")}
    </tr>`;
    $("#pl-season-tbl tbody").innerHTML = seas.length ? seas.map((s) => `<tr>
      <td class="tnum">${s.year}</td>
      <td>${franCell(s.owner, s.franchise, s.logo)}</td>
      <td>${s.nfl ? `${A.nflLogoHTML(s.nfl, "nfl-logo")}${A.esc(s.nfl)}` : "—"}</td>
      <td class="tnum">${s.pts != null ? fmt(s.pts, 1) : "—"}</td>
      <td class="tnum">${s.starts != null ? s.starts : "—"}</td>
      <td class="tnum">${s.stPts != null ? fmt(s.stPts, 1) : "—"}</td>
    </tr>`).join("") : `<tr><td colspan="6">${A.notice("No season log for this player.")}</td></tr>`;
    $("#pl-franchise-tbl thead").innerHTML = `<tr>
      ${fh("name", "Franchise")}${fh("seasons", "Seasons")}${fh("pts", "Pts")}${fh("starts", "Starts")}
    </tr>`;
    $("#pl-franchise-tbl tbody").innerHTML = frans.length ? frans.map((f) => `<tr>
      <td>${franCell(f.owner, f.name, f.logo)}</td>
      <td class="tnum">${f.seasons}</td>
      <td class="tnum">${f.hasPts ? fmt(f.pts, 1) : "—"}</td>
      <td class="tnum">${f.hasStarts ? f.starts : "—"}</td>
    </tr>`).join("") : `<tr><td colspan="4">${A.notice("No AFFL franchise seasons.")}</td></tr>`;
    bindCareerSort();
  }

  function rowState(started, hasAffl, y, snap) {
    if (isPre2018(y)) {
      if (started) return "started";
      if (snap && (snap.tid != null || snap.draftTid != null)) return "snapshot";
      return "unrecovered";
    }
    if (hasAffl && started) return "started";
    if (hasAffl) return "benched";
    return "nfl"; // three-state: NFL week, not on an AFFL roster (2018+ only)
  }

  async function gatherLogs(pid) {
    const years = logYear === "all" ? playerYears(pid) : [logYear];
    const out = [];
    for (const y of years) {
      if (y == null || y === "all") continue;
      let d = null;
      try { d = await A.loadYear(y); } catch (e) { d = null; }
      if (d) {
        YEAR_META[y] = {
          trades: d.trades || [],
          moves: d.moves || [],
          auction: !!(d.auctionDraft || (d.draft && d.draft.auction)),
          weeks: d.weeks || {},
        };
      }
      const p = (d && (d.players || []).find((x) => x.pid === pid)) || null;
      const afflByWk = {};
      if (p) {
        for (const w of p.wk || []) afflByWk[Number(w[0])] = w;
      }
      const nflByWk = nflYearWeeks(pid, y);
      const startsByWk = preStartsFor(pid, y);
      const weeks = new Set();
      Object.keys(afflByWk).forEach((k) => weeks.add(Number(k)));
      Object.keys(nflByWk).forEach((k) => { if (isWeekKey(k)) weeks.add(Number(k)); });
      Object.keys(startsByWk).forEach((k) => { if (isWeekKey(k)) weeks.add(Number(k)); });
      const stub = p || stubPlayer(pid);
      const snap = preSnap(pid, y);
      if (snap && snap.tid != null) stub.mainTeam = snap.tid;
      [...weeks].sort((a, b) => a - b).forEach((wk) => {
        const affl = afflByWk[wk];
        const nfl = nflByWk[String(wk)] || null;
        const start = startsByWk[String(wk)] || null;
        const hasAffl = !!(affl || start || (nfl && (nfl.tid != null || nfl.slot)));
        let started = 0, tid = null, slot = "—";
        if (start) {
          started = 1;
          tid = start.tid;
          slot = start.slot || "—";
        } else if (affl) {
          started = affl[2] ? 1 : 0;
          tid = affl[3];
          slot = affl[4];
        } else if (nfl && (nfl.tid != null || nfl.slot)) {
          started = nfl.started ? 1 : 0;
          tid = nfl.tid;
          slot = nfl.slot || "BN";
        } else if (isPre2018(y) && snap && (snap.tid != null || snap.draftTid != null)) {
          tid = snap.tid != null ? snap.tid : snap.draftTid;
          slot = "—";
          started = 0;
        } else if (isPre2018(y)) {
          slot = "—";
        } else {
          slot = "NFL";
        }
        const pts = (nfl && nfl.pts != null) ? nfl.pts : (start && start.pts != null) ? start.pts : (affl ? affl[1] : 0);
        const opp = (nfl && nfl.opp) || (affl && affl[5]) || "";
        const yds = (nfl && nfl.yds != null) ? nfl.yds : (affl ? affl[6] : null);
        const td = (nfl && nfl.td != null) ? nfl.td : (affl ? affl[7] : null);
        const tgt = (nfl && nfl.tgt != null) ? nfl.tgt : (affl ? affl[8] : null);
        const epa = (nfl && nfl.epa != null) ? nfl.epa : (affl ? affl[9] : null);
        const xtd = (nfl && nfl.xtd != null) ? nfl.xtd : (affl && affl.length > 10 ? affl[10] : null);
        const res = (nfl && nfl.res != null) ? nfl.res : (affl && affl.length > 11 ? affl[11] : null);
        const w = [wk, pts, started, tid, slot, opp, yds, td, tgt, epa, xtd, res];
        out.push({ y, p: stub, w, state: rowState(started, hasAffl, y, snap), nfl: nfl || null });
      });
    }
    return out;
  }

  async function loadPlayer(pid, push) {
    const pool = enrichedPool();
    const want = pid == null || pid === "" ? null : Number(pid);
    let p = want ? pool.find((x) => Number(x.pid) === want) : null;
    if (!p && want && INDEX[String(want)]) p = stubPlayer(want);
    if (!p && want && A.HYDRATE_PLAYERS) {
      const rec = A.HYDRATE_PLAYERS[want] || A.HYDRATE_PLAYERS[String(want)];
      if (rec) p = { pid: want, name: rec.name, pos: rec.pos || "", nfl: rec.nfl || "" };
    }
    if (!p && want) {
      $("#pl-hero").innerHTML = A.notice("This player page is unavailable.");
      const chiMiss = $("#pl-chi114"); if (chiMiss) chiMiss.hidden = true;
      const col = $("#pl-college"); if (col) col.innerHTML = "";
      const ov = $("#pl-overview"); if (ov) { ov.hidden = true; ov.innerHTML = ""; }
      return;
    }
    if (!p) p = pool[0];
    if (!p) {
      $("#pl-hero").innerHTML = A.notice(`No player data stored for ${year}. ESPN retains weekly lineups from 2018 on.`);
      const col = $("#pl-college");
      if (col) col.innerHTML = "";
      const ov = $("#pl-overview");
      if (ov) { ov.hidden = true; ov.innerHTML = ""; }
      const ngsEl = $("#pl-ngs-profile");
      if (ngsEl) { ngsEl.hidden = true; ngsEl.innerHTML = ""; }
      const career = $("#pl-career");
      if (career) {
        career.hidden = true;
        const st = $("#pl-season-tbl tbody");
        const ft = $("#pl-franchise-tbl tbody");
        if (st) st.innerHTML = "";
        if (ft) ft.innerHTML = "";
      }
      $("#pl-log tbody").innerHTML = "";
      $("#pl-log thead").innerHTML = "";
      $("#pl-journey").innerHTML = "";
      $("#pl-money").innerHTML = "";
      $("#player-year-row").hidden = true;
      if (chart) { chart.destroy(); chart = null; }
      if (ngsChart) { ngsChart.destroy(); ngsChart = null; }
      if (careerChart) { careerChart.destroy(); careerChart = null; }
      return;
    }
    cur = p;
    if (isPre2018(logYear)) {
      const snap = preSnap(p.pid, logYear);
      const extra = {};
      if (snap && snap.tid != null) extra.mainTeam = snap.tid;
      try {
        const d = await A.loadYear(logYear);
        const hit = ((d.draft || {}).board || []).find((x) => x.pid === p.pid);
        if (hit) extra.draft = { teamId: hit.tid, round: hit.round, overall: hit.overall, bid: hit.bid, keeper: hit.keeper };
      } catch (e) {}
      if (!extra.draft && snap && snap.draftTid != null) extra.draft = { teamId: snap.draftTid };
      if (Object.keys(extra).length) {
        p = Object.assign({}, p, extra);
        cur = p;
      }
    }
    const years = playerYears(p.pid);
    if (logYear !== "all" && years.length && years.indexOf(logYear) < 0) logYear = "all";
    if (logYear == null) logYear = "all";
    logSortKey = "week";
    logSortDir = 1;
    if (push) {
      const q = logYear === "all" ? `?pid=${p.pid}&log=all` : `?pid=${p.pid}&log=${logYear}`;
      history.pushState(null, "", q);
    }
    document.title = `${p.name} — Stars, Scrubs, & Duds`;

    renderYearChips(p.pid);
    setPageMode("profile");
    const savedLogYear = logYear;
    logYear = "all";
    const careerRows = await gatherLogs(p.pid);
    logYear = savedLogYear;
    const rows = (logYear === "all")
      ? careerRows
      : careerRows.filter((r) => Number(r.y) === Number(logYear));
    const chartRows = (logYear === "all")
      ? careerRows
      : careerRows.filter((r) => Number(r.y) === Number(logYear));
    let focus = logYear === "all" ? p : ((rows[0] && rows[0].p) || p);
    if (isPre2018(logYear)) {
      focus = Object.assign({}, focus, {
        mainTeam: p.mainTeam != null ? p.mainTeam : focus.mainTeam,
        draft: p.draft || focus.draft,
      });
    }
    const m = meta(p.pid);
    renderHero(focus, m, rows);
    renderOverview(focus);
    renderChart(focus, chartRows);
    renderCareerChart(focus, careerRows);
    if (chart) chart.resize();
    if (careerChart) careerChart.resize();
    renderJourney(focus, rows);
    renderCollege(focus);
    renderNgsProfile(focus);
    const seasons = await careerSeasonRows(p.pid, rows);
    renderCareerTables(p.pid, rows, seasons);
    renderLog(focus, rows);
    renderMoney(p.pid, m);
    renderFgStrip(focus, rows);
    renderCustody(focus, rows);
    renderAchievements(focus, rows);
    renderFgCharts(focus, rows);
    await renderPlayerChi114(p.pid);
    setPageMode("profile");
  }

  function renderYearChips(pid) {
    const years = playerYears(pid);
    const el = $("#player-year-picker");
    const row = $("#player-year-row");
    if (row) row.hidden = true;
    if (!el) return;
    if (!years.length) { el.innerHTML = ""; return; }
    const allOn = logYear === "all";
    const chips = [`<button type="button" class="season-chip${allOn ? " on" : ""}" data-y="all">All</button>`]
      .concat(years.map((y) => `<button type="button" class="season-chip${!allOn && y === logYear ? " on" : ""}" data-y="${y}">${y}</button>`));
    el.innerHTML = chips.join("");
    el.querySelectorAll("button").forEach((b) => {
      b.onclick = () => {
        logYear = b.dataset.y === "all" ? "all" : +b.dataset.y;
        loadPlayer(pid, true);
      };
    });
  }

  function seasonXtd(m, y) {
    if (y === "all") {
      const vals = (m.years || []).map((yr) => (m.xtd || {})[String(yr)]).filter(Boolean);
      if (!vals.length) return null;
      return {
        td: vals.reduce((a, v) => a + (v.td || 0), 0),
        xtd: vals.reduce((a, v) => a + (v.xtd || 0), 0),
        res: vals.reduce((a, v) => a + (v.res || 0), 0),
      };
    }
    return (m.xtd || {})[String(y)] || null;
  }

  function capFor(m, y) {
    const rows = m.cap || [];
    if (y === "all") return rows;
    return rows.filter((c) => c.season === y);
  }

  function dash(v) {
    return (v == null || v === "") ? "—" : v;
  }


  function playerChi114Logo(pid) {
    const rec = nflBlock(pid);
    const md = (rec && rec.meta) || {};
    let nfl = md.nfl || "";
    if (!nfl) {
      const ys = Object.keys(rec || {}).filter(isYearKey).sort();
      if (ys.length) nfl = nflTeam(pid, +ys[ys.length - 1]) || "";
    }
    if (!nfl && A.nflSlug) {
      const bio = A.playerBio(pid, null, A.today()) || {};
      nfl = bio.nfl || "";
    }
    if (!nfl || !A.nflSlug) return "";
    const slug = A.nflSlug(nfl);
    return slug ? ("logos/nfl/" + slug + ".png") : "";
  }

  /* CHI-114 season grain: playerSeasonXfp → FP / XFP only. 2013 skipped. */
  function renderChi114SeasonXfp(pid) {
    const X = window.CHI114;
    if (!X) return;
    X.drawSeasonXfp({
      canvas: $("#pl-chi114-season"),
      chips: $("#pl-chi114-season-years"),
      marks: $("#pl-chi114-season-marks"),
      pane: $("#pl-chi114-season-pane"),
      rows: X.seasonRowsForPid(pid),
      mode: "player",
      logoUrl: playerChi114Logo(pid),
    });
  }

  /* CHI-114 season grain: playerSeasonXfp → FPOE on its own scale. 2013 skipped. */
  function renderChi114SeasonFpoe(pid) {
    const X = window.CHI114;
    if (!X) return;
    X.drawSeasonFpoe({
      canvas: $("#pl-chi114-fpoe"),
      chips: $("#pl-chi114-fpoe-years"),
      marks: $("#pl-chi114-fpoe-marks"),
      pane: $("#pl-chi114-fpoe-pane"),
      rows: X.seasonRowsForPid(pid),
      mode: "player",
      logoUrl: playerChi114Logo(pid),
    });
  }

  /* CHI-114 week grain: playerWeekNfl → yards / TDs / volume only. */
  function renderChi114WeekNfl(pid) {
    const X = window.CHI114;
    if (!X) return;
    X.drawWeekNfl({
      canvas: $("#pl-chi114-week"),
      yearChips: $("#pl-chi114-week-years"),
      weekChips: $("#pl-chi114-week-weeks"),
      pane: $("#pl-chi114-week-pane"),
      rows: X.weekRowsForPid(pid),
      mode: "player",
    });
  }

  async function renderPlayerChi114(pid) {
    const block = $("#pl-chi114");
    if (!block || !window.CHI114) return;
    block.hidden = false;
    await window.CHI114.ensure();
    renderChi114SeasonXfp(pid);
    renderChi114SeasonFpoe(pid);
    renderChi114WeekNfl(pid);
  }

  function setPageMode(mode) {
    const profile = mode === "profile";
    const hide = (sel, on) => { const el = $(sel); if (el) el.hidden = !!on; };
    hide("#pl-hero", !profile);
    hide(".pl-detail", !profile);
    hide("#pl-college", !profile);
    if (!profile) {
      hide("#pl-overview", true);
      const ov = $("#pl-overview");
      if (ov) ov.innerHTML = "";
    }
    hide("#pl-log-card", !profile);
    hide("#pl-money", !profile);
    hide("#pl-back", !profile);
    // Advanced cards only when a player is open (profile). Landing = clean DB list.
    hide("#pl-compare", true);
    hide("#wopr-persist", true);
    hide("#pl-fg-strip", !profile);
    hide("#pl-custody", !profile);
    hide("#pl-achievements", !profile);
    hide("#pl-fg-charts", !profile);
    hide("#pl-chi114", !profile);
    hide("#pl-db-break", profile);
    hide("#pl-db", profile);
    if (!profile) {
      const ngs = $("#pl-ngs-profile");
      if (ngs) { ngs.hidden = true; ngs.innerHTML = ""; }
      const career = $("#pl-career");
      if (career) career.hidden = true;
      hide("#player-year-row", true);
    }
  }

  function fmtDominator(v) {
    if (v == null || v === "") return "—";
    const n = Number(v);
    if (Number.isNaN(n)) return "—";
    if (Math.abs(n) <= 1) return (n * 100).toFixed(1) + "%";
    return n.toFixed(1) + "%";
  }

  function draftCapital(bio) {
    bio = bio || {};
    const parts = [];
    if (bio.draftRound != null && bio.draftRound !== "") parts.push("R" + bio.draftRound);
    if (bio.draftPick != null && bio.draftPick !== "") parts.push("P" + bio.draftPick);
    if (bio.draftTeam) parts.push(bio.draftTeam);
    if (bio.draftYear != null && bio.draftYear !== "") parts.push(String(bio.draftYear));
    const nfl = bio.nflDraft;
    if (nfl != null && nfl !== "") {
      if (typeof nfl !== "object") {
        if (parts.indexOf(String(nfl)) < 0) parts.push(String(nfl));
      } else {
        if (nfl.round != null && parts.indexOf("R" + nfl.round) < 0) parts.push("R" + nfl.round);
        if (nfl.pick != null && parts.indexOf("P" + nfl.pick) < 0) parts.push("P" + nfl.pick);
        if (nfl.team && parts.indexOf(nfl.team) < 0) parts.push(nfl.team);
      }
    }
    return parts.length ? parts.join(" · ") : "—";
  }

  function combineLine(c) {
    if (c == null || c === "") return "—";
    if (typeof c !== "object") return String(c);
    const keys = ["forty", "40", "vertical", "bench", "broad", "shuttle", "cone", "height", "weight"];
    const bits = [];
    keys.forEach((k) => {
      if (c[k] != null && c[k] !== "") bits.push(k + " " + c[k]);
    });
    return bits.length ? bits.join(" · ") : "—";
  }

  function isRookieOrFirstAffl(pid) {
    const years = ((INDEX[String(pid)] || {}).years) || [];
    if (years.length >= 3) return false;
    const bioY = logYear === "all" ? (years[0] || 2025) : logYear;
    const bio = A.playerBio(pid, bioY, A.today()) || {};
    if (bio.draftYear != null && Number(bio.draftYear) <= 2022) return false;
    const first = years.length <= 1;
    const rookie = bio.draftYear != null && Number(bio.draftYear) >= 2025;
    return first || rookie;
  }

  function collegeCacheRec(pid) {
    if (!pid || !isRookieOrFirstAffl(pid)) return null;
    return COLLEGE[String(pid)] || null;
  }

  function overviewRec(pid) {
    if (pid == null || pid === "") return null;
    return OVERVIEW[String(pid)] || null;
  }

  function heroHeadshotUrl(p) {
    const existing = p && p.hs;
    if (existing) return existing;
    const rec = overviewRec(p && p.pid);
    return (rec && rec.headshotFallback) || "";
  }

  function nextGameChipHTML(p) {
    const rec = overviewRec(p && p.pid);
    const g = rec && rec.nextGame;
    if (!g || (!g.shortName && !g.name)) return "";
    const name = g.shortName || g.name;
    const when = g.weekText || "";
    const tip = [g.displayName, g.name, g.location].filter(Boolean).join(" · ");
    return `<span class="pl-next-chip"${tip ? ` title="${A.esc(tip)}"` : ""}>${A.esc(name)}${when ? " · " + A.esc(when) : ""}</span>`;
  }

  function overviewBioHTML(p) {
    const rec = overviewRec(p && p.pid);
    if (!rec) return "";
    if (collegeCacheRec(p && p.pid)) return "";
    const college = rec.college || "";
    const draft = rec.draft || "";
    if (!college && !draft) return "";
    const bits = [];
    if (college) bits.push(A.esc(college));
    if (draft) bits.push(A.esc(draft));
    return `<div class="pl-ov-bio">${bits.join(" · ")}</div>`;
  }

  function fmtNewsPublished(raw) {
    if (!raw) return "";
    const d = new Date(raw);
    if (Number.isNaN(d.getTime())) return String(raw);
    return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
  }

  function renderOverview(p) {
    let el = $("#pl-overview");
    const rec = overviewRec(p && p.pid);
    const news = (rec && rec.news) || [];
    const note = (rec && rec.rotowire) || "";
    if (!rec || (!news.length && !note)) {
      if (el) { el.hidden = true; el.innerHTML = ""; el.remove(); }
      return;
    }
    if (!el) {
      el = document.createElement("section");
      el.id = "pl-overview";
      el.className = "card";
      const chi = $("#pl-chi114");
      const hero = $("#pl-hero");
      const parent = (chi && chi.parentNode) || (hero && hero.parentNode);
      if (!parent) return;
      parent.insertBefore(el, chi || (hero && hero.nextSibling) || null);
    }
    const items = news.map((n) => {
      const when = fmtNewsPublished(n.published);
      return `<li><span class="pl-news-hed">${A.esc(n.headline || "")}</span>${when ? `<span class="pl-news-when">${A.esc(when)}</span>` : ""}</li>`;
    }).join("");
    const wire = note ? `<p class="pl-ov-note">${A.esc(note)}</p>` : "";
    el.hidden = false;
    el.innerHTML = `
      <div class="card-head">
        <div>
          <h2>News</h2>
          <div class="card-sub">from the local ESPN overview cache · missing stays empty</div>
        </div>
      </div>
      ${wire}
      ${items ? `<ul class="story-list pl-news-list">${items}</ul>` : ""}`;
  }

  function renderCollege(p) {
    const el = $("#pl-college");
    if (!el) return;
    const bio = (p && A.playerBio(p.pid, logYear === "all" ? ((meta(p.pid).years || [])[0]) : logYear, A.today())) || {};
    let breakout = "—";
    try {
      if (bio.breakoutAge != null && bio.breakoutAge !== "") breakout = A.fmt(bio.breakoutAge, 1);
    } catch (e) { breakout = "—"; }
    const early = (bio.earlyDeclare == null || bio.earlyDeclare === "")
      ? "—"
      : (bio.earlyDeclare ? "Yes" : "No");
    const college = bio.college ? A.esc(bio.college) : "<span class=\"mut\">unavailable</span>";
    const logo = A.collegeLogoHTML(bio);
    const cached = collegeCacheRec(p && p.pid);
    let career = "";
    if (cached) {
      const ys = cached.years || [];
      let span = "";
      if (ys.length === 1) span = String(ys[0]);
      else if (ys.length > 1) span = ys[0] + "–" + String(ys[ys.length - 1]).slice(-2);
      const line = cached.line ? String(cached.line) : "—";
      career = `<div class="pl-college-line">${span ? A.esc(span) + " · " : ""}${A.esc(line)}</div>`;
    }
    const stat = (v, l) => `<div class="pp-stat"><b>${v}</b><span>${l}</span></div>`;
    el.innerHTML = `
      <div class="card-head">
        <div>
          <h2>College</h2>
          <div class="card-sub">school · breakout · draft capital · missing fields stay —</div>
        </div>
      </div>
      <div class="pl-college-inner">
        <div class="pl-college-id">
          ${logo}
          <div>
            <div class="pl-college-name">${college}</div>
            ${career}
          </div>
        </div>
        <div class="pp-stats pl-college-tiles">
          ${stat(breakout, "breakout age")}
          ${stat(fmtDominator(bio.dominator), "dominator")}
          ${stat(A.esc(draftCapital(bio)), "draft capital")}
          ${stat(early, "early declare")}
          ${stat(A.esc(combineLine(bio.combine)), "combine")}
        </div>
      </div>`;
  }

  function parseNgsList(raw) {
    if (!raw) return [];
    if (Array.isArray(raw)) return raw;
    try { return JSON.parse(raw); } catch (e) { return []; }
  }

  /* CHI-59: yard-share tree/fan from stored NGS routes/holes only. Not RP success. */
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

  function ngsPosAvgShare(kind, pos) {
    if (!_ngsPosAvg) _ngsPosAvg = buildNgsPosAvg();
    return ((_ngsPosAvg[kind] || {})[pos] || {});
  }
  function buildNgsPosAvg() {
    const out = { route: {}, hole: {} };
    const acc = { route: {}, hole: {} };
    const players = (NGS_PROFILES && NGS_PROFILES.players) || {};
    Object.keys(players).forEach((id) => {
      const rec = players[id];
      const pos = rec && rec.pos;
      if (!pos) return;
      const routes = parseNgsList(rec.top_routes_json);
      const holes = parseNgsList(rec.top_holes_json);
      if (routes.length) {
        acc.route[pos] = acc.route[pos] || { tot: 0, by: {} };
        routes.forEach((r) => {
          const k = r && r.route;
          if (!k) return;
          const y = Number(r.yds) || 0;
          acc.route[pos].by[k] = (acc.route[pos].by[k] || 0) + y;
          acc.route[pos].tot += y;
        });
      }
      if (holes.length) {
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
    ["route", "hole"].forEach((kind) => {
      Object.keys(acc[kind]).forEach((pos) => {
        const pack = acc[kind][pos];
        out[kind][pos] = {};
        if (!(pack.tot > 0)) return;
        Object.keys(pack.by).forEach((k) => { out[kind][pos][k] = pack.by[k] / pack.tot; });
      });
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
  function renderNgsProfile(p) {
    const el = $("#pl-ngs-profile");
    if (!el) return;
    const rec = ((NGS_PROFILES && NGS_PROFILES.players) || {})[String(p && p.pid)];
    if (!rec) {
      el.hidden = true;
      el.innerHTML = "";
      return;
    }
    el.hidden = false;
    const routes = parseNgsList(rec.top_routes_json);
    const holes = parseNgsList(rec.top_holes_json);
    const pos = rec.pos || (p && p.pos);
    const stat = (v, l) => `<div class="pp-stat"><b>${v == null || v === "" ? "—" : fmt(v, 2)}</b><span>${l}</span></div>`;
    const tree = renderNgsRouteTree(routes, pos);
    const scheme = renderNgsHoleScheme(holes, pos);
    el.innerHTML = `
      <div class="card-head">
        <div>
          <h2>NGS 2025</h2>
          <div class="card-sub">season profile · CPOE / TTT / RYOE/att / sep / YACoE · missing stays —</div>
        </div>
      </div>
      <div class="pp-stats pl-ngs-tiles">
        ${stat(rec.pass_2025_cpoe, "CPOE")}
        ${stat(rec.pass_2025_ttt, "TTT")}
        ${stat(rec.rush_2025_ryoe_att, "RYOE/att")}
        ${stat(rec.rec_2025_sep, "sep")}
        ${stat(rec.rec_2025_yacoe, "YACoE")}
      </div>
      <div class="pl-ngs-mix">
        <div>
          <div class="card-sub">Routes</div>
          ${tree}
        </div>
        <div>
          <div class="card-sub">Run scheme</div>
          ${scheme}
        </div>
      </div>`;
  }

  function heroTeamLine(p, y, m) {
    if (y === "all") return afflSeasonCount(p.pid) + " AFFL seasons";
    if (p.mainTeam) return "finished with " + tName(p.mainTeam, y);
    if (isPre2018(y)) {
      const snap = preSnap(p.pid, y);
      if (snap && snap.tid != null) return "finished with " + tName(snap.tid, y);
      if (snap && snap.draftTid != null) return "drafted by " + tName(snap.draftTid, y);
      return y + " AFFL weekly rosters not recovered";
    }
    if (nflTeam(p.pid, y)) return "NFL · " + nflTeam(p.pid, y);
    return "NFL weeks";
  }

  function renderHero(p, m, rows) {
    const y = logYear;
    const xs = seasonXtd(m, y);
    const caps = capFor(m, y);
    const capHit = caps.reduce((a, c) => a + (c.hit || 0), 0) || null;
    const tot = rows.reduce((a, r) => a + (r.w[1] || 0), 0);
    const starts = rows.filter((r) => r.state === "started" || (r.state == null && r.w[2])).length;
    const stPts = rows.filter((r) => r.state === "started" || (r.state == null && r.w[2])).reduce((a, r) => a + (r.w[1] || 0), 0);
    const epa = rows.reduce((a, r) => a + (r.w[9] || 0), 0);
    const hasEpa = rows.some((r) => r.w[9] != null);
    const stat = (v, l, tip) => `<div class="pp-stat"${tip ? ` title="${A.esc(tip)}"` : ""}><b>${v}</b><span>${l}</span></div>`;
    const yrLabel = y === "all" ? "career" : String(y);
    const teamLine = heroTeamLine(p, y, m);
    const bio = A.playerBio(p.pid, y === "all" ? (m.years || [])[0] : y, A.today());
    const bioAge = bio && bio.ageText ? bio.ageText : (bio && bio.age);
    const yo = YOFF[String(p.pid)] || {};
    const nYoff = yo.nYoff || 0;
    const graded = nYoff >= 3 && yo.yoffstud != null;
    const yoffTip = graded
      ? `${fmt(yo.yoffPpg, 1)} ppg in ${nYoff} playoff starts vs ${fmt(yo.regPpg, 1)} regular`
      : (nYoff ? `${nYoff} playoff start${nYoff === 1 ? "" : "s"} (need 3 to grade)` : "no winners-bracket starts");
    const draftN = yo.draftsN || 0;
    const draftPo = yo.draftPlayoffs || 0;
    const rings = yo.rings || 0;
    const ringYears = (yo.ringYears || []).join(", ");
    const ranks = buildRanks();
    const ar = ranks.all[String(p.pid)];
    const pr = ranks.pos[String(p.pid)];
    const bw = bestWeek(rows);
    const heroP = Object.assign({}, p, { hs: heroHeadshotUrl(p) });
    $("#pl-hero").innerHTML = `
      <div class="pl-hero-inner">
        ${A.headshotHTML(heroP, "pl-hs")}
        <div class="pl-id">
          <h2 class="pl-name">${p.name}</h2>
          <div class="pl-tags">
            <span class="badge pos-${p.pos}">${p.pos}</span>
            <span class="pl-nfl">${A.nflLogoHTML(p.nfl, "nfl-logo")}${p.nfl || "NFL"}</span>
            <span class="pl-team">${yrLabel} · ${teamLine}</span>
            ${nextGameChipHTML(p)}
          </div>
          ${overviewBioHTML(p)}
        </div>
        <div class="pp-stats pl-tiles">
          ${stat(fmt(tot, 1), y === "all" ? "career pts" : "season pts")}
          ${stat(fmt(stPts, 1), "affl started pts")}
          ${stat(starts ? fmt(stPts / starts, 1) : "—", "ppg started")}
          ${stat(starts, "affl starts")}
          ${stat(p.cons != null && y !== "all" ? Math.round(p.cons * 100) + "%" : "—", "consistency")}
          ${stat(bioAge != null && bioAge !== "" ? bioAge : "—", "age today")}
          ${stat(hasEpa ? (epa >= 0 ? "+" : "") + fmt(epa, 1) : "—", "nfl epa")}
          ${stat(xs ? fmt(xs.xtd, 2) : "—", "xTD")}
          ${stat(xs ? ((xs.res >= 0 ? "+" : "") + fmt(xs.res, 2)) : "—", "TD − xTD")}
          ${stat(capHit != null ? money(capHit) : "—", y === "all" ? "spotrac cap (sum)" : "spotrac cap")}
          ${stat(graded ? fmt(yo.yoffstud, 1) : "—", "yoffstud", yoffTip)}
          ${stat(graded ? fmt(yo.yoffdud, 1) : "—", "yoffdud", yoffTip)}
          ${stat(draftPo + "/" + draftN, "drafted → yoff", draftPo + " of " + draftN + " drafts made the playoffs")}
          ${stat(rings, "AFFL titles", ringYears || "no AFFL titles")}
          ${stat(ar ? ("#" + ar.rank) : "—", "all-time", ar ? ("#" + ar.rank + " of " + ar.n + " AFFL players by career NFL pts") : "no career points")}
          ${stat(pr ? ("#" + pr.rank + " " + (p.pos || "")) : "—", "pos rank", pr ? ("#" + pr.rank + " of " + pr.n + " " + (p.pos || "") + "s") : "no position rank")}
          ${stat(bw ? fmt(bw.w[1], 1) : "—", "best week", bw ? (bw.y + " W" + bw.w[0] + (bw.w[5] ? " vs " + bw.w[5] : "")) : "no scored week")}
        </div>
      </div>`;
  }

  function weekRange(st) {
    if (st.from == null && st.to == null) return "before W1";
    if (st.from === st.to) return "W" + st.from;
    return "W" + st.from + "–W" + st.to;
  }

  function journeyNode(kind, title, detail, mark) {
    const face = mark ? `<div class="journey-face">${mark.html}</div>` : "";
    return `<div class="journey-node ${kind}">${face}
      <div class="journey-k">${A.esc(title)}</div>
      <div class="journey-n">${A.esc(detail)}</div>
    </div>`;
  }

  function journeyArrow() {
    return `<div class="journey-arrow" aria-hidden="true">→</div>`;
  }

  function journeyMove(text) {
    return `<div class="journey-move">${A.esc(text)}</div>`;
  }

  function enteredNode(p, y) {
    const auction = ((YEAR_META[y] || {}).auction) || (p.draft && p.draft.bid != null);
    if (p.draft && (p.draft.bid != null || p.draft.round != null || p.draft.teamId != null)) {
      const mark = p.draft.teamId != null ? teamMark(p.draft.teamId, y) : null;
      if (auction && p.draft.bid != null) {
        return journeyNode("enter", "Auction",
          "$" + p.draft.bid + " to " + tName(p.draft.teamId, y) + (p.draft.keeper ? " as a keeper" : ""), mark);
      }
      if (p.draft.round != null) {
        return journeyNode("enter", "Draft",
          p.draft.round + "." + p.draft.overall + " by " + tName(p.draft.teamId, y), mark);
      }
      return journeyNode("enter", "Drafted", "by " + tName(p.draft.teamId, y), mark);
    }
    return journeyNode("enter", "Waiver", "entered the AFFL through the waiver wire", null);
  }

  function journeyFootnote(rows) {
    const scored = (rows || []).filter((r) => r && r.w && r.w[1] != null);
    const best = scored.length ? scored.slice().sort((a, b) => b.w[1] - a.w[1])[0] : null;
    const started = (rows || []).filter((r) => r.state === "started" || (r.state == null && r.w[2]));
    const stPts = started.reduce((a, r) => a + (Number(r.w[1]) || 0), 0);
    const bits = [];
    if (best) {
      let tag = "";
      if (best.state === "benched") tag = " · benched";
      else if (best.state === "snapshot") tag = " · on AFFL roster (weekly lineup not recovered)";
      else if (best.state === "unrecovered" || isPre2018(best.y)) tag = " · AFFL weekly rosters not recovered";
      else if (best.state === "nfl") tag = " · NFL week (2018+)";
      bits.push("Best week " + fmt(best.w[1], 1) + " · " + best.y + " W" + best.w[0] + (best.w[5] ? " vs " + best.w[5] : "") + tag);
    }
    bits.push(fmt(stPts, 1) + " started pts · " + started.length + " start" + (started.length === 1 ? "" : "s"));
    return `<p class="journey-note">${bits.join(" · ")}</p>`;
  }

  function renderPre2018Journey(p) {
    const parts = [];
    const snap = preSnap(p.pid, logYear);
    const draftTid = (p.draft && p.draft.teamId != null) ? p.draft.teamId
      : (snap && snap.draftTid != null ? snap.draftTid : null);
    const snapTid = snap && snap.tid;
    if (p.draft && p.draft.round != null) {
      parts.push(journeyNode("enter", "Draft", p.draft.round + "." + p.draft.overall + " by " + tName(draftTid, logYear),
        draftTid != null ? teamMark(draftTid, logYear) : null));
    } else if (draftTid != null) {
      parts.push(journeyNode("enter", "Drafted", "by " + tName(draftTid, logYear), teamMark(draftTid, logYear)));
    }
    if (snapTid != null && draftTid != null && Number(draftTid) !== Number(snapTid)) {
      parts.push(journeyArrow());
      parts.push(journeyNode("stint", String(logYear),
        "drafted by " + tName(draftTid, logYear) + ", finished on " + tName(snapTid, logYear) + " · snapshot",
        teamMark(snapTid, logYear)));
    } else if (snapTid != null) {
      parts.push(journeyArrow());
      parts.push(journeyNode("stint", String(logYear) + " · " + tName(snapTid, logYear),
        "on AFFL roster (weekly lineup not recovered)", teamMark(snapTid, logYear)));
    } else if (draftTid != null) {
      parts.push(journeyArrow());
      parts.push(journeyNode("stint", String(logYear),
        logYear + " AFFL weekly rosters not recovered", teamMark(draftTid, logYear)));
    } else {
      parts.push(journeyNode("stint", String(logYear),
        "snapshot has no row · weekly start unknown", null));
    }
    if (snapTid != null) {
      parts.push(journeyArrow());
      parts.push(journeyNode("finish", "Finished with", tName(snapTid, logYear), teamMark(snapTid, logYear)));
    }
    return `<div class="journey-rail">${parts.join("")}</div>
      <p class="journey-note">${logYear} AFFL weekly rosters not recovered · snapshot only · no invented trades</p>`;
  }

  function renderSeasonJourney(p, rows, y) {
    const parts = [];
    parts.push(enteredNode(p, y));
    const weekly = rosterStints(rows, y);
    const draftTid = (p.draft && p.draft.teamId != null) ? p.draft.teamId : null;
    const stints = weekly.slice();
    if (draftTid != null && stints.length && Number(stints[0].tid) !== Number(draftTid)) {
      stints.unshift({ tid: draftTid, year: Number(y), from: null, to: null, weeks: [], draft: true });
    } else if (draftTid != null && !stints.length) {
      stints.push({ tid: draftTid, year: Number(y), from: null, to: null, weeks: [], draft: true });
    }
    stints.forEach((st, i) => {
      const mark = teamMark(st.tid, y);
      const range = st.draft ? "auction / draft desk" : weekRange(st);
      parts.push(journeyArrow());
      parts.push(journeyNode("stint", mark.name, range, mark));
      const nxt = stints[i + 1];
      if (nxt && Number(nxt.tid) !== Number(st.tid)) {
        const wk = nxt.from != null ? nxt.from : 1;
        parts.push(journeyMove(movePhrase(p.pid, y, st.tid, nxt.tid, wk)));
      }
    });
    if (stints.length) {
      const last = stints[stints.length - 1];
      const mark = teamMark(last.tid, y);
      parts.push(journeyArrow());
      parts.push(journeyNode("finish", "Finished with", mark.name, mark));
    }
    const yRows = (rows || []).filter((r) => Number(r.y) === Number(y));
    return `<div class="journey-rail">${parts.join("")}</div>${journeyFootnote(yRows)}`;
  }

  function renderCareerJourney(p, rows) {
    const parts = [];
    const ys = afflYears(p.pid);
    const firstY = ys[0];
    const firstP = ((rows || []).find((r) => Number(r.y) === Number(firstY) && r.p && r.p.draft) || {}).p || p;
    if (firstY && !isPre2018(firstY)) parts.push(enteredNode(firstP, firstY));
    else if (firstY) {
      const snap = preSnap(p.pid, firstY);
      const dTid = (firstP.draft && firstP.draft.teamId != null) ? firstP.draft.teamId
        : (snap && snap.draftTid != null ? snap.draftTid : null);
      if (dTid != null) parts.push(journeyNode("enter", String(firstY), "started with " + tName(dTid, firstY), teamMark(dTid, firstY)));
    }
    const homes = [];
    const spans = [];
    for (const y of ys) {
      const tid = yearHome(p.pid, y, rows);
      if (tid == null) continue;
      const name = tName(tid, y);
      if (!name || name === "—") continue;
      if (homes.length && homes[homes.length - 1] === name) {
        spans[spans.length - 1].to = y;
        continue;
      }
      homes.push(name);
      spans.push({ name: name, tid: tid, from: y, to: y });
    }
    spans.forEach((sp) => {
      const mark = teamMark(sp.tid, sp.to);
      const yrs = sp.from === sp.to ? String(sp.from) : (sp.from + "–" + sp.to);
      parts.push(journeyArrow());
      parts.push(journeyNode("stint", mark.name, yrs, mark));
    });
    if (spans.length) {
      const last = spans[spans.length - 1];
      parts.push(journeyArrow());
      parts.push(journeyNode("finish", "Finished with", last.name, teamMark(last.tid, last.to)));
    }
    return `<div class="journey-rail">${parts.join("")}</div>${journeyFootnote(rows)}`;
  }

  function renderJourney(p, rows) {
    const el = $("#pl-journey");
    if (!el) return;
    if (isPre2018(logYear)) {
      el.innerHTML = renderPre2018Journey(p);
      return;
    }
    if (logYear === "all") {
      el.innerHTML = renderCareerJourney(p, rows);
      return;
    }
    el.innerHTML = renderSeasonJourney(p, rows, logYear);
  }


  function matchupFor(y, wk, tid) {
    if (tid == null || y == null || isPre2018(y)) return null;
    const bag = ((YEAR_META[y] || {}).weeks || {})[String(wk)] || [];
    for (let i = 0; i < bag.length; i++) {
      const m = bag[i] || {};
      const home = m.home || {}, away = m.away || {};
      let mine = null, opp = null;
      if (Number(home.tid) === Number(tid)) { mine = home; opp = away; }
      else if (Number(away.tid) === Number(tid)) { mine = away; opp = home; }
      if (!mine || !opp || mine.pts == null || opp.pts == null) continue;
      const diff = Number(mine.pts) - Number(opp.pts);
      return { result: diff > 0 ? "W" : diff < 0 ? "L" : "T", pf: mine.pts, pa: opp.pts, margin: diff };
    }
    return null;
  }

  const FG_PALETTE = ["#2f7bff","#ff7a00","#ffc400","#93d500","#47a8ff","#ff2d1a","#c77dff","#2a9d8c","#ff6b9d","#9fd8ff","#e8a838","#7d8aa0"];
  function ownerColor(oid) {
    const id = String(A.canon(oid) || oid || "");
    let h = 0;
    for (let i = 0; i < id.length; i++) h = (h * 31 + id.charCodeAt(i)) >>> 0;
    return FG_PALETTE[h % FG_PALETTE.length];
  }

  function mkFg(id, cfg) {
    if (fgCharts[id]) { fgCharts[id].destroy(); delete fgCharts[id]; }
    const el = $(id);
    if (!el) return null;
    fgCharts[id] = new Chart(el, cfg);
    return fgCharts[id];
  }

  function rosteredRows(rows) {
    return (rows || []).filter((r) => r.state !== "nfl" && r.state !== "unrecovered" && r.w[3] != null);
  }

  function startedRows(rows) {
    return (rows || []).filter((r) => r.state === "started" || (r.state == null && r.w[2]));
  }

  function wlForRows(rows) {
    let w = 0, l = 0, t = 0, n = 0;
    (rows || []).forEach((r) => {
      const mu = matchupFor(r.y, r.w[0], r.w[3]);
      if (!mu) return;
      n++;
      if (mu.result === "W") w++;
      else if (mu.result === "L") l++;
      else t++;
    });
    return { w: w, l: l, t: t, n: n, pct: (w + l) ? w / (w + l) : null };
  }

  function custodyStints(p, rows, y) {
    const weekly = rosterStints(rows, y === "all" ? "all" : y);
    const byYear = {};
    weekly.forEach((st) => {
      (byYear[st.year] = byYear[st.year] || []).push(st);
    });
    const out = [];
    const years = y === "all" ? Object.keys(byYear).map(Number).sort((a, b) => a - b) : [Number(y)];
    years.forEach((yr) => {
      const list = (byYear[yr] || []).slice();
      if (!isPre2018(yr)) {
        const hit = (rows || []).find((r) => Number(r.y) === Number(yr) && r.p && r.p.draft && r.p.draft.teamId != null);
        const draftTid = hit ? hit.p.draft.teamId : ((p.draft && Number(p.draft.teamId) && Number(yr) === Number(y)) ? p.draft.teamId : null);
        if (draftTid != null && list.length && Number(list[0].tid) !== Number(draftTid)) {
          list.unshift({ tid: draftTid, year: yr, from: null, to: null, weeks: [], draft: true });
        }
      }
      list.forEach((st) => out.push(st));
    });
    return out;
  }

  function custodyRows(p, rows, y) {
    return custodyStints(p, rows, y).map((st) => {
      const mark = teamMark(st.tid, st.year || y);
      const owner = ownerForTid(st.year || y, st.tid);
      const slice = st.draft ? [] : (rows || []).filter((r) => {
        if (Number(r.y) !== Number(st.year)) return false;
        if (Number(r.w[3]) !== Number(st.tid)) return false;
        if (r.state === "nfl" || r.state === "unrecovered") return false;
        const wk = Number(r.w[0]);
        return wk >= st.from && wk <= st.to;
      });
      const wl = wlForRows(slice);
      const gs = startedRows(slice).length;
      const pts = slice.reduce((a, r) => a + (Number(r.w[1]) || 0), 0);
      const g = slice.length;
      const span = st.draft ? (st.year + " · before W1") : (String(st.year) + " " + weekRange(st));
      return { mark: mark, owner: owner, st: st, span: span, g: g, gs: gs, pts: pts, ppg: g ? pts / g : null, wl: wl };
    });
  }

  function renderFgStrip(p, rows) {
    const el = $("#pl-fg-strip-tiles");
    if (!el) return;
    const rostered = rosteredRows(rows);
    const started = startedRows(rows);
    const games = rostered.length;
    const starts = started.length;
    const seasons = new Set(rostered.map((r) => r.y)).size || afflYears(p.pid).length;
    const tot = started.reduce((a, r) => a + (Number(r.w[1]) || 0), 0);
    const ppg = starts ? tot / starts : null;
    const startPct = games ? starts / games : null;
    const nflN = (rows || []).filter((r) => r.state === "nfl").length;
    const ownedPct = (games + nflN) ? games / (games + nflN) : null;
    const wl = wlForRows(started);
    const rec = wl.n ? (wl.w + "-" + wl.l + (wl.t ? "-" + wl.t : "")) : "—";
    const stat = (v, l) => `<div class="pp-stat"><b>${v}</b><span>${l}</span></div>`;
    el.innerHTML = [
      stat(seasons || "—", "seasons"),
      stat(games || "—", "games"),
      stat(starts || "—", "starts"),
      stat(startPct == null ? "—" : Math.round(startPct * 100) + "%", "start %"),
      stat(starts ? fmt(tot, 1) : "—", "total pts"),
      stat(ppg == null ? "—" : fmt(ppg, 1), "avg PPG"),
      stat(wl.pct == null ? "—" : Math.round(wl.pct * 100) + "%", "AFFL win%"),
      stat(rec, "team W-L"),
      stat(ownedPct == null ? "—" : Math.round(ownedPct * 100) + "%", "owned %"),
    ].join("");
  }

  function renderCustody(p, rows) {
    const y = logYear === "all" ? "all" : logYear;
    const recs = custodyRows(p, rows, y);
    const tbl = $("#pl-custody-tbl");
    const tl = $("#pl-custody-tl");
    const wrap = $("#pl-custody-table-wrap");
    if (!tbl) return;
    tbl.querySelector("thead").innerHTML = `<tr>
      <th>Franchise</th><th>Span</th><th>G</th><th>GS</th><th>PTS</th><th>PPG</th><th>Win%</th><th>W-L</th>
    </tr>`;
    tbl.querySelector("tbody").innerHTML = recs.length ? recs.map((r) => {
      const rec = r.wl.n ? (r.wl.w + "-" + r.wl.l + (r.wl.t ? "-" + r.wl.t : "")) : "—";
      const pct = r.wl.pct == null ? "—" : Math.round(r.wl.pct * 100) + "%";
      return `<tr>
        <td>${franCell(r.owner, r.mark.name, r.mark.logo)}</td>
        <td>${A.esc(r.span)}</td>
        <td class="tnum">${r.g || (r.st.draft ? "—" : 0)}</td>
        <td class="tnum">${r.gs || (r.st.draft ? "—" : 0)}</td>
        <td class="tnum">${r.g ? fmt(r.pts, 1) : "—"}</td>
        <td class="tnum">${r.ppg == null ? "—" : fmt(r.ppg, 1)}</td>
        <td class="tnum">${pct}</td>
        <td class="tnum">${rec}</td>
      </tr>`;
    }).join("") : `<tr><td colspan="8">${A.notice("No AFFL stints in this slice.")}</td></tr>`;
    if (tl) {
      tl.innerHTML = recs.map((r) => {
        const rec = r.wl.n ? (r.wl.w + "-" + r.wl.l) : "";
        return journeyNode("stint", r.mark.name, r.span + (rec ? " · " + rec : ""), r.mark);
      }).join(journeyArrow());
    }
    if (wrap) wrap.hidden = custodyMode !== "table";
    if (tl) tl.hidden = custodyMode !== "timeline";
    const mode = $("#pl-custody-mode");
    if (mode && !mode.dataset.bound) {
      mode.dataset.bound = "1";
      mode.querySelectorAll("button").forEach((b) => {
        b.addEventListener("click", () => {
          custodyMode = b.dataset.mode === "timeline" ? "timeline" : "table";
          mode.querySelectorAll("button").forEach((x) => x.classList.toggle("on", x === b));
          if (wrap) wrap.hidden = custodyMode !== "table";
          if (tl) tl.hidden = custodyMode !== "timeline";
        });
      });
    }
  }

  function renderAchievements(p, rows) {
    const el = $("#pl-achievements-list");
    if (!el) return;
    const started = startedRows(rows);
    const benched = (rows || []).filter((r) => r.state === "benched");
    const items = [];
    if (started.length) {
      const best = started.slice().sort((a, b) => b.w[1] - a.w[1])[0];
      items.push({ k: "Career high", t: fmt(best.w[1], 1) + " pts", d: best.y + " W" + best.w[0] + " · " + tName(best.w[3], best.y) });
      const eggs = started.filter((r) => Number(r.w[1]) <= 4);
      if (eggs.length) {
        const egg = eggs.slice().sort((a, b) => a.w[1] - b.w[1])[0];
        items.push({ k: "Laid an egg", t: fmt(egg.w[1], 1) + " pts started", d: egg.y + " W" + egg.w[0] + " · " + tName(egg.w[3], egg.y) });
      }
      const heroes = started.filter((r) => Number(r.w[1]) >= 20);
      if (heroes.length) {
        const h = heroes.slice().sort((a, b) => b.w[1] - a.w[1])[0];
        items.push({ k: "Team on the back", t: fmt(h.w[1], 1) + " pts", d: h.y + " W" + h.w[0] + " · heroic start · " + tName(h.w[3], h.y) });
      }
    }
    const leftovers = benched.filter((r) => Number(r.w[1]) >= 15);
    if (leftovers.length) {
      const b = leftovers.slice().sort((a, b) => b.w[1] - a.w[1])[0];
      items.push({ k: "Shouldn't have started", t: fmt(b.w[1], 1) + " pts on the bench", d: b.y + " W" + b.w[0] + " · " + tName(b.w[3], b.y) });
    }
    const clutch = started.filter((r) => {
      const mu = matchupFor(r.y, r.w[0], r.w[3]);
      return mu && mu.result === "W" && mu.margin > 0 && mu.margin <= 5 && Number(r.w[1]) >= mu.margin;
    });
    if (clutch.length) {
      const c = clutch.slice().sort((a, b) => b.w[1] - a.w[1])[0];
      const mu = matchupFor(c.y, c.w[0], c.w[3]);
      items.push({ k: "Clutch", t: fmt(c.w[1], 1) + " pts in a " + fmt(mu.margin, 1) + "-pt win", d: c.y + " W" + c.w[0] + " · " + tName(c.w[3], c.y) });
    }
    el.innerHTML = items.length ? items.map((x) => `
      <li><div class="story-ico" style="background:#2f7bff18">★</div>
      <div class="story-txt"><div class="t">${A.esc(x.k)}</div><div class="d">${A.esc(x.t)} · ${A.esc(x.d)}</div></div></li>`).join("")
      : `<li>${A.notice("No achievement-sized weeks in this slice.")}</li>`;
  }

  function ownerBags(rows) {
    const by = {};
    rosteredRows(rows).forEach((r) => {
      const oid = ownerForTid(r.y, r.w[3]) || ("tid:" + r.w[3]);
      const id = A.canon(oid) || oid;
      const a = by[id] || { owner: id, name: tName(r.w[3], r.y), color: ownerColor(id), pts: [] };
      a.pts.push(Number(r.w[1]) || 0);
      if (!a.name || a.name === "—") a.name = tName(r.w[3], r.y);
      by[id] = a;
    });
    return Object.values(by);
  }

  function renderFgCharts(p, rows) {
    const rostered = rosteredRows(rows).slice().sort((a, b) => weekOrder(a) - weekOrder(b));
    const bags = ownerBags(rows);
    const bands = $("#pl-avg-bands");
    if (bands) {
      if (!rostered.length) bands.innerHTML = "";
      else {
        const groups = [];
        rostered.forEach((r) => {
          const oid = A.canon(ownerForTid(r.y, r.w[3]) || ("tid:" + r.w[3]));
          const last = groups[groups.length - 1];
          if (last && last.oid === oid) last.n++;
          else groups.push({ oid: oid, name: tName(r.w[3], r.y), n: 1, color: ownerColor(oid) });
        });
        const tot = rostered.length;
        bands.innerHTML = groups.map((g) =>
          `<div class="fg-band" style="flex:${g.n};background:${g.color}" title="${A.esc(g.name)} · ${g.n} wk">${g.n / tot > 0.12 ? A.esc(g.name) : ""}</div>`
        ).join("");
      }
    }
    const started = startedRows(rows);
    const avg = started.length ? started.reduce((a, r) => a + (Number(r.w[1]) || 0), 0) / started.length : null;
    const labels = rostered.map((r) => (logYear === "all" ? String(r.y).slice(2) + "-W" + r.w[0] : "W" + r.w[0]));
    const colors = rostered.map((r) => ownerColor(ownerForTid(r.y, r.w[3])));
    mkFg("#pl-avg-line", {
      type: "line",
      data: {
        labels: labels,
        datasets: [
          {
            label: "weekly pts",
            data: rostered.map((r) => r.w[1]),
            borderColor: "#9fd8ff",
            pointBackgroundColor: colors,
            pointBorderColor: "#0b0e14",
            pointRadius: 3,
            borderWidth: 1.5,
            tension: 0.15,
            spanGaps: false,
          },
          avg == null ? null : {
            label: "career avg " + fmt(avg, 1),
            data: rostered.map(() => avg),
            borderColor: "#ffc400",
            borderDash: [6, 4],
            pointRadius: 0,
            borderWidth: 1.5,
          },
        ].filter(Boolean),
      },
      options: {
        maintainAspectRatio: false,
        plugins: { legend: { labels: { boxWidth: 10, boxHeight: 10 } } },
        scales: {
          y: { grid: { color: C.grid }, border: { display: false } },
          x: { grid: { display: false }, border: { display: false } },
        },
      },
    });
    mkFg("#pl-swarm", {
      type: "scatter",
      data: {
        datasets: bags.map((b, i) => ({
          label: b.name,
          data: b.pts.map((v) => ({ x: i + (Math.random() - 0.5) * 0.35, y: v })),
          backgroundColor: b.color,
          pointRadius: 4,
        })),
      },
      options: {
        maintainAspectRatio: false,
        plugins: { legend: { labels: { boxWidth: 10, boxHeight: 10 } } },
        scales: {
          x: {
            min: -0.6, max: Math.max(0.6, bags.length - 0.4),
            ticks: { callback: (v) => (bags[Math.round(v)] ? bags[Math.round(v)].name : "") },
            grid: { display: false }, border: { display: false },
          },
          y: { grid: { color: C.grid }, border: { display: false }, title: { display: true, text: "pts" } },
        },
      },
    });
    mkFg("#pl-owner-range", {
      type: "bar",
      data: {
        labels: bags.map((b) => b.name),
        datasets: [{
          label: "min-max",
          data: bags.map((b) => {
            const lo = Math.min.apply(null, b.pts);
            const hi = Math.max.apply(null, b.pts);
            return [lo, hi];
          }),
          backgroundColor: bags.map((b) => b.color + "cc"),
          borderSkipped: false,
        }],
      },
      options: {
        indexAxis: "y",
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: { callbacks: { label: (c) => {
            const b = bags[c.dataIndex];
            const lo = Math.min.apply(null, b.pts), hi = Math.max.apply(null, b.pts);
            const mean = b.pts.reduce((a, v) => a + v, 0) / b.pts.length;
            return fmt(lo, 1) + "-" + fmt(hi, 1) + " · avg " + fmt(mean, 1);
          } } },
        },
        scales: {
          x: { grid: { color: C.grid }, border: { display: false } },
          y: { grid: { display: false }, border: { display: false } },
        },
      },
    });
  }

  function ngsCols(pos) {
    pos = (pos || "").toUpperCase();
    if (pos === "WR" || pos === "TE") return ["sep", "cushion", "yacoe", "tshare"];
    if (pos === "RB") return ["ryoe", "eff", "box8"];
    if (pos === "QB") return ["cpoe", "ttt", "agg"];
    return [];
  }

  function ngsHead(key) {
    return ({
      sep: "Sep", cushion: "Cushion", yacoe: "YAC−xYAC", tshare: "Tgt%",
      ryoe: "RYOE", eff: "Eff", box8: "8+ Box%",
      cpoe: "CPOE", ttt: "TTT", agg: "Agg%",
    })[key] || key;
  }

  function ngsCell(key, ngs, nfl) {
    if (key === "tshare") {
      const v = nfl && nfl.tshare != null ? nfl.tshare : (ngs && ngs.tshare);
      if (v == null) return "—";
      return (Number(v) * 100).toFixed(1) + "%";
    }
    if (!ngs || ngs[key] == null) return "—";
    const v = Number(ngs[key]);
    if (!Number.isFinite(v)) return "—";
    if (key === "box8" || key === "agg") return v.toFixed(1) + "%";
    if (key === "cpoe" || key === "yacoe" || key === "ryoe") return (v >= 0 ? "+" : "") + v.toFixed(2);
    return v.toFixed(2);
  }

  function weekOrder(r) {
    return (Number(r.y) || 0) * 100 + (Number(r.w[0]) || 0);
  }

  function logCellVal(r, key, p) {
    const w = r.w;
    if (key === "year") return Number(r.y) || 0;
    if (key === "week") return weekOrder(r);
    if (key === "opp") return String(w[5] || "").toLowerCase();
    if (key === "team") return String(tName(w[3], r.y) || "").toLowerCase();
    if (key === "owner") return String(tName(w[3], r.y) || "").toLowerCase();
    if (key === "role") return String(r.state || (w[2] ? "started" : "benched"));
    if (key === "wl") {
      const mu = matchupFor(r.y, w[0], w[3]);
      return mu ? mu.result : "";
    }
    if (key === "slot") return String(w[4] || "").toLowerCase();
    if (key === "pts") return w[1];
    if (key === "proj") return weekProj(r.y, p.pid, w[0]);
    if (key === "yds") return w[6];
    if (key === "td") return w[7];
    if (key === "xtd") return w[10];
    if (key === "res") return w[11];
    if (key === "tgt") return w[8];
    if (key === "epa") return w[9];
    if (key.indexOf("ngs:") === 0) {
      const nk = key.slice(4);
      const ngs = weekNgs(r.y, p.pid, w[0]);
      if (nk === "tshare") {
        const nfl = r.nfl;
        return (nfl && nfl.tshare != null) ? nfl.tshare : (ngs && ngs.tshare);
      }
      return ngs ? ngs[nk] : null;
    }
    return null;
  }

  function sortedLogRows(rows, p) {
    const key = logSortKey;
    const dir = logSortDir;
    return rows.slice().sort((a, b) => {
      const av = logCellVal(a, key, p);
      const bv = logCellVal(b, key, p);
      const aMiss = av == null || av === "";
      const bMiss = bv == null || bv === "";
      if (aMiss && bMiss) return weekOrder(a) - weekOrder(b);
      if (aMiss) return 1;
      if (bMiss) return -1;
      if (typeof av === "string" || typeof bv === "string") {
        const c = String(av).localeCompare(String(bv), undefined, { numeric: true });
        return c * dir || (weekOrder(a) - weekOrder(b));
      }
      if (Number(av) !== Number(bv)) return (Number(av) - Number(bv)) * dir;
      return weekOrder(a) - weekOrder(b);
    });
  }

  function bindLogSort() {
    const tbl = $("#pl-log");
    if (!tbl || tbl.dataset.sortBound) return;
    tbl.dataset.sortBound = "1";
    tbl.addEventListener("click", (e) => {
      const th = e.target.closest("th[data-k]");
      if (!th || !tbl.contains(th)) return;
      const k = th.dataset.k;
      if (logSortKey === k) logSortDir *= -1;
      else { logSortKey = k; logSortDir = -1; }
      if (logView) renderLog(logView.p, logView.rows);
    });
  }

  function filteredLogRows(rows) {
    return (rows || []).filter((r) => {
      if (logFilter.season !== "all" && Number(r.y) !== Number(logFilter.season)) return false;
      const oid = A.canon(ownerForTid(r.y, r.w[3]) || "");
      if (logFilter.owner !== "all" && oid !== logFilter.owner) return false;
      const st = r.state || (r.w[2] ? "started" : "benched");
      if (logFilter.role === "start" && st !== "started") return false;
      if (logFilter.role === "bench" && st !== "benched") return false;
      if (logFilter.role === "rostered" && st !== "started" && st !== "benched") return false;
      return true;
    });
  }

  function renderLogFilters(rows) {
    const el = $("#pl-log-filters");
    if (!el) return;
    const years = Array.from(new Set((rows || []).map((r) => r.y))).sort((a, b) => b - a);
    const owners = [];
    const seen = {};
    (rows || []).forEach((r) => {
      const oid = A.canon(ownerForTid(r.y, r.w[3]) || "");
      if (!oid || seen[oid]) return;
      seen[oid] = 1;
      owners.push({ id: oid, name: tName(r.w[3], r.y) });
    });
    owners.sort((a, b) => a.name.localeCompare(b.name));
    const chip = (key, val, label) =>
      `<button class="season-chip${logFilter[key] === val ? " on" : ""}" data-k="${key}" data-v="${val}">${label}</button>`;
    el.innerHTML = `
      <div class="fg-filter-row"><span class="picker-label">Season</span>
        ${chip("season", "all", "All")}${years.map((y) => chip("season", String(y), String(y))).join("")}</div>
      <div class="fg-filter-row"><span class="picker-label">Owner</span>
        ${chip("owner", "all", "All")}${owners.map((o) => chip("owner", o.id, o.name)).join("")}</div>
      <div class="fg-filter-row"><span class="picker-label">Role</span>
        ${chip("role", "all", "All")}${chip("role", "rostered", "Start+bench")}${chip("role", "start", "Started")}${chip("role", "bench", "Benched")}</div>`;
    el.querySelectorAll("button").forEach((b) => {
      b.addEventListener("click", () => {
        logFilter[b.dataset.k] = b.dataset.v;
        if (logView) renderLog(logView.p, logView.rows);
      });
    });
  }

  function renderLog(p, rows) {
    logView = { p: p, rows: rows };
    renderLogFilters(rows);
    const showY = logYear === "all";
    const ordered = sortedLogRows(filteredLogRows(rows), p);
    const projs = ordered.map((r) => weekProj(r.y, p.pid, r.w[0]));
    const hasProj = projs.some((v) => v != null);
    const cols = ngsCols(p.pos);
    const ngsRows = ordered.map((r) => weekNgs(r.y, p.pid, r.w[0]));
    if (showY) {
      $("#pl-log-sub").textContent = "Full NFL career weeks · blue = AFFL start (2018+ weekly and 2014–2017 recovered) · gray = benched · teal = NFL week not on an AFFL roster (2018+) · gold = on AFFL roster (weekly lineup not recovered) · NGS blank below attempt minimums · click a header to sort";
    } else if (isPre2018(logYear)) {
      $("#pl-log-sub").textContent = `${logYear} · blue = recovered AFFL start · gold = on AFFL roster (weekly lineup not recovered) · NGS dash = no row · click a header to sort`;
    } else {
      $("#pl-log-sub").textContent = `${logYear} · blue = started · gray = benched · teal = NFL week not on an AFFL roster · NGS dash = no row · click a header to sort`;
    }
    const mark = (k, label) => {
      const on = logSortKey === k;
      return `<th class="s${on ? " on" : ""}${on && logSortDir > 0 ? " asc" : ""}" data-k="${k}">${label}</th>`;
    };
    const ngsHeads = cols.map((k) => mark("ngs:" + k, ngsHead(k))).join("");
    $("#pl-log thead").innerHTML = `<tr>
      ${showY ? mark("year", "Year") : ""}
      ${mark("week", "Wk")}${mark("opp", "Opp")}${mark("team", "AFFL Team")}${mark("owner", "Owner")}${mark("role", "Role")}${mark("wl", "W-L")}${mark("slot", "Slot")}
      ${mark("pts", "Fan Pts")}${mark("proj", "Proj")}${mark("yds", "Yds")}${mark("td", "TD")}${mark("xtd", "xTD")}${mark("res", "TD−xTD")}${mark("tgt", "Tgt")}${mark("epa", "EPA")}${ngsHeads}
    </tr>`;
    bindLogSort();
    if (!ordered.length) {
      $("#pl-log tbody").innerHTML = `<tr><td colspan="14">${A.notice("No weekly lineups for this slice.")}</td></tr>`;
      return;
    }
    $("#pl-log tbody").innerHTML = ordered.map((r, i) => {
      const [wk, pts, st, tid, slot, opp, yds, td, tgt, epa, xtd, res] = r.w;
      const resCls = res > 0 ? "pos" : res < 0 ? "neg" : "";
      const epaCls = epa > 0 ? "pos" : epa < 0 ? "neg" : "";
      const pj = projs[i];
      const state = r.state || (st ? "started" : "benched");
      const trCls = state === "started" ? ""
        : state === "benched" ? "benched"
        : state === "snapshot" ? "snapshot-roster"
        : state === "unrecovered" ? "unrecovered"
        : "nfl-only";
      const ngs = ngsRows[i];
      const ngsTds = cols.map((k) => `<td class="tnum">${ngsCell(k, ngs, r.nfl)}</td>`).join("");
      const teamLabel = (state === "nfl" || state === "unrecovered") ? "—" : tName(tid, r.y);
      const slotCls = state === "nfl" ? "nfl-slot" : state === "snapshot" ? "snapshot-slot" : "";
      return `<tr class="${trCls}">
        ${showY ? `<td class="tnum">${r.y}</td>` : ""}
        <td><strong>W${wk}</strong></td>
        <td>${opp || "—"}</td>
        <td class="own">${teamLabel}</td>
        <td class="own">${(state === "nfl" || state === "unrecovered") ? "—" : teamLabel}</td>
        <td>${state === "started" ? '<span class="fg-badge start">Start</span>' : state === "benched" ? '<span class="fg-badge bench">Bench</span>' : '<span class="fg-badge na">—</span>'}</td>
        <td class="tnum">${(() => { const mu = matchupFor(r.y, wk, tid); return mu ? mu.result : "—"; })()}</td>
        <td><span class="sb-slot ${st ? "started" : ""} ${slotCls}">${slot}</span></td>
        <td><strong>${fmt(pts, 1)}</strong></td>
        <td class="tnum">${pj != null ? fmt(pj, 1) : "—"}</td>
        <td>${yds != null ? fmt(yds) : "—"}</td>
        <td>${td != null ? td : "—"}</td>
        <td class="tnum">${xtd != null ? fmt(xtd, 2) : "—"}</td>
        <td class="tnum ${resCls}">${res != null ? (res >= 0 ? "+" : "") + fmt(res, 2) : "—"}</td>
        <td>${tgt != null && p.pos !== "QB" ? tgt : "—"}</td>
        <td class="${epaCls}">${epa != null ? (epa >= 0 ? "+" : "") + epa : "—"}</td>
        ${ngsTds}
      </tr>`;
    }).join("");
  }

  function renderMoney(pid, m) {
    const caps = (m.cap || []).slice().sort((a, b) => b.season - a.season || (a.nfl || "").localeCompare(b.nfl || ""));
    const deals = (m.contracts || []).slice().sort((a, b) => (b.signed || 0) - (a.signed || 0));
    const capTbl = caps.length ? `
      <div class="table-scroll">
        <table class="tbl">
          <thead><tr><th>Year</th><th>NFL</th><th>Cap hit</th><th>Base</th><th>Signing</th><th>Dead</th><th>Cap %</th></tr></thead>
          <tbody>
            ${caps.map((c) => `<tr>
              <td class="tnum">${c.season}</td>
              <td>${c.nfl || "—"}</td>
              <td class="tnum">${money(c.hit)}</td>
              <td class="tnum">${money(c.base)}</td>
              <td class="tnum">${money(c.bonus)}</td>
              <td class="tnum">${money(c.dead)}</td>
              <td class="tnum">${c.pct != null ? (c.pct * 100).toFixed(1) + "%" : "—"}</td>
            </tr>`).join("")}
          </tbody>
        </table>
      </div>` : `<p class="empty">No Spotrac cap row matched this player.</p>`;
    const dealTbl = deals.length ? `
      <div class="table-scroll" style="margin-top:14px">
        <table class="tbl">
          <thead><tr><th>Signed</th><th>NFL</th><th>Years</th><th>Value</th><th>APY</th><th>Guaranteed</th><th></th></tr></thead>
          <tbody>
            ${deals.map((d) => `<tr>
              <td class="tnum">${d.signed || "—"}</td>
              <td>${d.nfl || "—"}</td>
              <td class="tnum">${d.years != null ? d.years : "—"}</td>
              <td class="tnum">${money(d.value)}</td>
              <td class="tnum">${money(d.apy)}</td>
              <td class="tnum">${money(d.gtd)}</td>
              <td>${d.active ? '<span class="badge steal">active</span>' : ""}</td>
            </tr>`).join("")}
          </tbody>
        </table>
      </div>` : `<p class="empty">No contract signing row on file.</p>`;
    $("#pl-money").innerHTML = `
      <div class="card-head">
        <div>
          <h2>NFL Contract</h2>
          <div class="card-sub">Annual cap hits from Spotrac · signing terms from Over The Cap via nflverse</div>
        </div>
      </div>
      ${capTbl}
      ${dealTbl}`;
  }

  function barStyle(r) {
    const state = r.state || (r.w[2] ? "started" : "benched");
    if (state === "started") return { bg: "#2f7bffcc", bd: "#2f7bff", bw: 0 };
    if (state === "benched") return { bg: "#3a4a6388", bd: "#3a4a63", bw: 0 };
    if (state === "snapshot") return { bg: "#d4a01788", bd: "#d4a017", bw: 1 };
    if (state === "unrecovered") return { bg: "#3a4a6333", bd: "#7d8aa0", bw: 1 };
    return { bg: "#2a9d8c33", bd: "#2a9d8c", bw: 2 }; // outline / muted teal = NFL, not rostered (2018+)
  }

  function renderChart(p, rows) {
    if (chart) chart.destroy();
    if (!rows.length) { chart = null; renderNgsChart(p, rows); return; }
    const projData = rows.map((r) => weekProj(r.y, p.pid, r.w[0]));
    const styles = rows.map(barStyle);
    chart = new Chart($("#pl-chart"), {
      type: "bar",
      data: {
        labels: rows.map((r) => (logYear === "all" ? String(r.y).slice(2) + "-W" + r.w[0] : "W" + r.w[0])),
        datasets: [{
          type: "bar",
          label: "actual (started / benched / NFL / snapshot)",
          data: rows.map((r) => r.w[1]),
          backgroundColor: styles.map((x) => x.bg),
          borderColor: styles.map((x) => x.bd),
          borderWidth: styles.map((x) => x.bw),
          borderRadius: 3, maxBarThickness: 26,
          order: 1,
        }, {
          type: "line",
          label: "ESPN proj",
          data: projData,
          borderColor: C.gold,
          backgroundColor: C.gold,
          pointBackgroundColor: C.gold,
          pointBorderColor: "#0b0e14",
          pointRadius: 2.5,
          pointHoverRadius: 4,
          borderWidth: 2,
          tension: 0.2,
          spanGaps: false,
          order: 0,
        }],
      },
      options: {
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        plugins: {
          legend: { display: true, labels: { boxWidth: 10, boxHeight: 10 } },
          tooltip: {
            filter: (item) => item.datasetIndex === 0,
            callbacks: {
              label: (c) => {
                const r = rows[c.dataIndex];
                const actual = r.w[1];
                const proj = projData[c.dataIndex];
                const state = r.state || (r.w[2] ? "started" : "benched");
                let who;
                if (state === "snapshot") who = `on AFFL roster (weekly lineup not recovered) · ${tName(r.w[3], r.y)}`;
                else if (state === "unrecovered") who = `${r.y} AFFL weekly rosters not recovered`;
                else if (state === "nfl") who = "NFL week, not on an AFFL roster";
                else who = `${state} by ${tName(r.w[3], r.y)}`;
                const lines = [`actual ${fmt(actual, 1)} pts · ${who}`];
                if (proj != null) {
                  const dlt = actual - proj;
                  lines.push(`ESPN proj ${fmt(proj, 1)}`);
                  lines.push(`delta ${dlt >= 0 ? "+" : ""}${fmt(dlt, 1)}`);
                }
                return lines;
              },
            },
          },
        },
        scales: {
          y: { grid: { color: C.grid }, border: { display: false } },
          x: { grid: { display: false }, border: { display: false } },
        },
      },
    });
    renderNgsChart(p, rows);
  }

  function renderCareerChart(p, rows) {
    if (careerChart) { careerChart.destroy(); careerChart = null; }
    const canvas = $("#pl-career-chart");
    if (!canvas) return;
    if (!rows.length) return;
    const projData = rows.map((r) => weekProj(r.y, p.pid, r.w[0]));
    const styles = rows.map(barStyle);
    careerChart = new Chart(canvas, {
      type: "bar",
      data: {
        labels: rows.map((r) => String(r.y).slice(2) + "-W" + r.w[0]),
        datasets: [{
          type: "bar",
          label: "actual (started / benched / NFL / snapshot)",
          data: rows.map((r) => r.w[1]),
          backgroundColor: styles.map((x) => x.bg),
          borderColor: styles.map((x) => x.bd),
          borderWidth: styles.map((x) => x.bw),
          borderRadius: 3, maxBarThickness: 18,
          order: 1,
        }, {
          type: "line",
          label: "ESPN proj",
          data: projData,
          borderColor: C.gold,
          backgroundColor: C.gold,
          pointBackgroundColor: C.gold,
          pointBorderColor: "#0b0e14",
          pointRadius: 1.5,
          pointHoverRadius: 3,
          borderWidth: 1.5,
          tension: 0.2,
          spanGaps: false,
          order: 0,
        }],
      },
      options: {
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        plugins: {
          legend: { display: true, labels: { boxWidth: 10, boxHeight: 10 } },
          tooltip: {
            filter: (item) => item.datasetIndex === 0,
            callbacks: {
              label: (c) => {
                const r = rows[c.dataIndex];
                const actual = r.w[1];
                const state = r.state || (r.w[2] ? "started" : "benched");
                let who;
                if (state === "snapshot") who = `on AFFL roster (weekly lineup not recovered) · ${tName(r.w[3], r.y)}`;
                else if (state === "unrecovered") who = `${r.y} AFFL weekly rosters not recovered`;
                else if (state === "nfl") who = "NFL week, not on an AFFL roster";
                else who = `${state} by ${tName(r.w[3], r.y)}`;
                return `${r.y} W${r.w[0]} · actual ${fmt(actual, 1)} pts · ${who}`;
              },
            },
          },
        },
        scales: {
          y: { grid: { color: C.grid }, border: { display: false } },
          x: { grid: { display: false }, border: { display: false } },
        },
      },
    });
  }

  function ngsSeries(pos) {
    pos = (pos || "").toUpperCase();
    if (pos === "WR" || pos === "TE") return [
      { key: "sep", label: "avg separation", color: "#2a9d8c" },
      { key: "yacoe", label: "YAC − xYAC", color: "#ffc400" },
    ];
    if (pos === "RB") return [
      { key: "ryoe", label: "RYOE", color: "#2a9d8c" },
      { key: "eff", label: "efficiency", color: "#ffc400" },
    ];
    if (pos === "QB") return [
      { key: "cpoe", label: "CPOE", color: "#2a9d8c" },
      { key: "ttt", label: "time to throw", color: "#ffc400" },
    ];
    return [];
  }

  function renderNgsChart(p, rows) {
    if (ngsChart) { ngsChart.destroy(); ngsChart = null; }
    const wrap = $("#pl-ngs");
    const canvas = $("#pl-ngs-chart");
    if (!wrap || !canvas) return;
    const series = ngsSeries(p.pos);
    const points = rows.map((r) => weekNgs(r.y, p.pid, r.w[0]));
    const has = series.some((s) => points.some((g) => g && g[s.key] != null));
    wrap.hidden = !has;
    if (!has) return;
    const labels = rows.map((r) => (logYear === "all" ? String(r.y).slice(2) + "-W" + r.w[0] : "W" + r.w[0]));
    ngsChart = new Chart(canvas, {
      type: "line",
      data: {
        labels,
        datasets: series.map((s) => ({
          label: s.label,
          data: points.map((g) => (g && g[s.key] != null ? g[s.key] : null)),
          borderColor: s.color,
          backgroundColor: s.color,
          pointRadius: 2.5,
          borderWidth: 2,
          tension: 0.2,
          spanGaps: true,
        })),
      },
      options: {
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        plugins: { legend: { display: true, labels: { boxWidth: 10, boxHeight: 10 } } },
        scales: {
          y: { grid: { color: C.grid }, border: { display: false } },
          x: { grid: { display: false }, border: { display: false } },
        },
      },
    });
  }

  function enrichedPool() {
    const src = scope === "cum" ? (careerList || []) : (YD && YD.players) || [];
    const by = {};
    src.forEach((pl) => { by[pl.pid] = Object.assign({}, pl); });
    Object.keys(INDEX).forEach((key) => {
      const id = +key;
      const years = playerYears(id);
      if (scope !== "cum") {
        const hasYear = years.indexOf(year) >= 0
          || Object.keys(nflYearWeeks(id, year)).some(isWeekKey);
        if (!hasYear) return;
      }
      if (!by[id]) by[id] = stubPlayer(id);
      const pts = scope === "cum" ? nflCareerPts(id) : nflSeasonPts(id, year);
      if (pts != null) by[id].tot = pts;
    });
    return Object.values(by);
  }

  async function careerPlayers() {
    if (careerList) return careerList;
    const all = await A.loadAllYears();
    const by = {};
    for (const { year: y, data } of all) {
      for (const p of data.players || []) {
        const a = by[p.pid] || Object.assign({}, p, { tot: 0, stPts: 0, starts: 0, years: [] });
        a.tot += p.tot || 0;
        a.stPts += p.stPts || 0;
        a.starts += p.starts || 0;
        a.years.push(y);
        a.tids = a.tids || {};
        a.tids[y] = p.mainTeam;
        if (p.hs) a.hs = p.hs;
        if (p.name) a.name = p.name;
        if (p.pos) a.pos = p.pos;
        by[p.pid] = a;
      }
    }
    Object.keys(INDEX).forEach((key) => {
      const id = +key;
      if (by[id]) return;
      const pts = nflCareerPts(id);
      if (pts == null && !(meta(id).years || []).length) return;
      const stub = stubPlayer(id);
      stub.tot = pts || 0;
      by[id] = stub;
    });
    careerList = Object.values(by).map((p) => {
      const nfl = nflCareerPts(p.pid);
      return Object.assign({}, p, {
        tot: nfl != null ? nfl : p.tot,
        ppg: p.starts ? +(p.stPts / p.starts).toFixed(1) : 0,
      });
    }).sort((a, b) => b.tot - a.tot);
    return careerList;
  }

  const DB_SORTS = [
    { key: "tot", label: "AFFL pts", short: "career pts", digits: 1 },
    { key: "td", label: "TD", short: "TD", digits: 0 },
    { key: "xtd", label: "xTD", short: "xTD", digits: 2 },
    { key: "starts", label: "AFFL starts", short: "starts", digits: 0 },
    { key: "yds", label: "Yards", short: "yards", digits: 0 },
  ];

  function indexCareerBox(pid) {
    const bag = (meta(pid).xtd || {});
    let td = 0, xtd = 0, nTd = 0, nXtd = 0;
    Object.keys(bag).forEach((y) => {
      const r = bag[y];
      if (!r) return;
      if (r.td != null && Number.isFinite(Number(r.td))) { td += Number(r.td); nTd += 1; }
      if (r.xtd != null && Number.isFinite(Number(r.xtd))) { xtd += Number(r.xtd); nXtd += 1; }
    });
    let yds = 0, nYds = 0;
    const rec = nflBlock(pid);
    Object.keys(rec).forEach((y) => {
      if (!isYearKey(y)) return;
      const weeks = rec[y] || {};
      Object.keys(weeks).forEach((wk) => {
        if (!isWeekKey(wk)) return;
        const w = weeks[wk];
        if (w && w.yds != null && Number.isFinite(Number(w.yds))) { yds += Number(w.yds); nYds += 1; }
      });
    });
    return { td: nTd ? td : null, xtd: nXtd ? xtd : null, yds: nYds ? yds : null };
  }

  function dbMetric(p, key) {
    if (key === "tot") return (p.tot != null && Number.isFinite(Number(p.tot))) ? Number(p.tot) : null;
    if (key === "starts") return p.starts ? Number(p.starts) : null;
    if (key === "td") return p.td != null ? Number(p.td) : null;
    if (key === "xtd") return p.xtd != null ? Number(p.xtd) : null;
    if (key === "yds") return p.yds != null ? Number(p.yds) : null;
    return null;
  }

  function filtered() {
    const q = PP.q.toLowerCase();
    const src = enrichedPool();
    const rows = src.filter((p) => {
      if (PP.pos !== "ALL" && p.pos !== PP.pos) return false;
      if (q && !p.name.toLowerCase().includes(q)) return false;
      if (squad) {
        const want = A.canon(squad);
        const hit = (tid, y) => {
          if (tid == null) return false;
          const owner = A.ownerId(y || year, tid) || ((A.teams(y || year)[tid] || {}).owner);
          return owner && A.canon(owner) === want;
        };
        if (scope === "cum" && p.tids) {
          if (!Object.entries(p.tids).some(([y, tid]) => hit(tid, +y))) return false;
        } else if (!hit(p.mainTeam, year)) return false;
      }
      return true;
    }).map((p) => {
      const box = indexCareerBox(p.pid);
      return Object.assign({}, p, box);
    });
    rows.sort((a, b) => {
      const vb = dbMetric(b, PP.sort);
      const va = dbMetric(a, PP.sort);
      if (vb == null && va == null) return String(a.name || "").localeCompare(String(b.name || ""));
      if (vb == null) return 1;
      if (va == null) return -1;
      if (vb !== va) return vb - va;
      return String(a.name || "").localeCompare(String(b.name || ""));
    });
    return rows;
  }

  function renderGrid() {
    const rows = filtered();
    const sortDef = DB_SORTS.find((s) => s.key === PP.sort) || DB_SORTS[0];
    $("#db-span").textContent = (PP.pos === "ALL" ? "all positions" : PP.pos) + " · " + sortDef.short + " · " + (scope === "cum" ? "all seasons" : String(year));
    $("#pp-grid").innerHTML = rows.slice(0, PP.limit).map((p) => {
      const v = dbMetric(p, PP.sort);
      const shown = v == null ? "unavailable" : fmt(v, sortDef.digits);
      const fran = cardFranchise(p);
      return `
      <div class="pp-card${cur && p.pid === cur.pid ? " cur" : ""}" data-pid="${p.pid}">
        ${A.headshotHTML(p, "pp-hs")}
        <div class="pp-meta">
          <div class="pp-nm">${A.playerLink(p.pid, p.name, { log: "all" })}</div>
          <div class="pp-sub"><span class="badge pos-${p.pos}">${p.pos}</span> ${A.esc(p.nfl || "")} · <span class="pp-fran" title="${A.esc(fran)}">${A.esc(fran)}</span></div>
        </div>
        <div class="pp-pts"><b>${shown}</b><span>${sortDef.short}</span></div>
      </div>`;
    }).join("") ||
      A.notice(enrichedPool().length ? "No players match." :
        "No player profiles stored.");
    $("#pp-more").style.display = rows.length > PP.limit ? "block" : "none";
    document.querySelectorAll(".pp-card").forEach((el) =>
      el.addEventListener("click", () => {
        logYear = "all";
        loadPlayer(+el.dataset.pid, true);
        renderGrid();
        window.scrollTo({ top: 0, behavior: "smooth" });
      }));
  }

  const POSES = ["ALL", "QB", "RB", "WR", "TE", "K", "DST"];
  function paintDbChips() {
    $("#pp-filters").innerHTML = POSES.map((p) =>
      `<button class="pp-chip${p === PP.pos ? " on" : ""}" data-pos="${p}">${p}</button>`).join("");
    const sortEl = $("#pp-sort");
    if (sortEl) {
      sortEl.innerHTML = DB_SORTS.map((s) =>
        `<button class="pp-chip${s.key === PP.sort ? " on" : ""}" data-sort="${s.key}">${s.label}</button>`).join("");
    }
    document.querySelectorAll("#pp-filters .pp-chip").forEach((b) =>
      b.addEventListener("click", () => {
        PP.pos = b.dataset.pos; PP.limit = 24;
        paintDbChips();
        renderGrid();
      }));
    document.querySelectorAll("#pp-sort .pp-chip").forEach((b) =>
      b.addEventListener("click", () => {
        PP.sort = b.dataset.sort; PP.limit = 24;
        paintDbChips();
        renderGrid();
      }));
  }
  paintDbChips();
  $("#pp-search").addEventListener("input", (e) => { PP.q = e.target.value; PP.limit = 24; renderGrid(); });
  $("#pp-more").addEventListener("click", () => { PP.limit += 24; renderGrid(); });


  /* Usage that sticks: same-year WOPR vs AFFL (non-PPR) FPpG. */
  const WOPR_MIN_YEAR = 2018;
  const WOPR_POS = { WR: C.orange, TE: C.gold };
  let woprYear = null;
  let woprChart = null;
  let woprWired = false;

  function woprNum(v) {
    if (v == null || v === "") return null;
    const n = Number(v);
    return Number.isFinite(n) ? n : null;
  }

  function woprFirstNum(row, keys) {
    if (!row) return null;
    for (let i = 0; i < keys.length; i++) {
      if (row[keys[i]] != null) {
        const n = woprNum(row[keys[i]]);
        if (n != null) return n;
      }
    }
    return null;
  }

  function woprByPid(rows) {
    const out = {};
    (rows || []).forEach((r) => {
      if (r && r.pid != null) out[Number(r.pid)] = r;
    });
    return out;
  }

  function woprYearNSampleOk(row) {
    const games = woprFirstNum(row, ["games", "g", "gp"]);
    const targets = woprFirstNum(row, ["targets", "tgt"]);
    if (games != null || targets != null) {
      return (games != null && games >= 8) || (targets != null && targets >= 30);
    }
    return woprNum(row && row.fp) != null;
  }

  function woprNflGames(pid, year, row, player) {
    const fromRow = woprFirstNum(row, ["games", "g", "gp"]);
    if (fromRow && fromRow > 0) return fromRow;
    const fromPl = woprFirstNum(player, ["games", "g", "gp"]);
    if (fromPl && fromPl > 0) return fromPl;
    if (pid != null && year != null) {
      const rec = nflYearWeeks(pid, year);
      let n = 0;
      Object.keys(rec).forEach((wk) => { if (isWeekKey(wk)) n++; });
      if (n > 0) return n;
    }
    return null;
  }

  function woprNextAfflFppg(row, player, year) {
    const fp = woprNum(row && row.fp);
    if (fp == null) return null;
    const pid = (row && row.pid != null) ? row.pid
      : (player && player.pid != null) ? player.pid : null;
    const games = woprNflGames(pid, year, row, player);
    if (!games || games <= 0) return null;
    return fp / games;
  }

  function woprPersistYears() {
    return A.years().filter((y) => y >= WOPR_MIN_YEAR).sort((a, b) => b - a);
  }

  function woprPersistPoints(yd) {
    const year = (yd && yd.year != null) ? yd.year : null;
    const usage = woprByPid(yd && yd.receivingUsage);
    const players = woprByPid(yd && yd.players);
    const out = [];
    Object.keys(usage).forEach((k) => {
      const row = usage[k];
      const pos = String(row.pos || "").toUpperCase();
      if (pos !== "WR" && pos !== "TE") return;
      const wopr = woprNum(row.wopr);
      if (wopr == null) return;
      if (!woprYearNSampleOk(row)) return;
      if (woprNum(row.fp) == null) return;
      const fppg = woprNextAfflFppg(row, players[k], year);
      if (fppg == null) return;
      const pl = players[k] || {};
      out.push({
        pid: Number(row.pid),
        name: row.name || pl.name || ("#" + row.pid),
        pos: pos,
        wopr: wopr,
        fppg: fppg,
        fp: row.fp,
        x: wopr,
        y: fppg,
      });
    });
    return out;
  }

  function woprR2(pts) {
    const n = (pts || []).length;
    if (n < 2) return null;
    let sx = 0, sy = 0;
    pts.forEach((p) => { sx += p.x; sy += p.y; });
    const mx = sx / n, my = sy / n;
    let sxx = 0, syy = 0, sxy = 0;
    pts.forEach((p) => {
      const dx = p.x - mx, dy = p.y - my;
      sxx += dx * dx;
      syy += dy * dy;
      sxy += dx * dy;
    });
    if (sxx === 0 || syy === 0) return null;
    const r = sxy / Math.sqrt(sxx * syy);
    return r * r;
  }

  function woprFitLine(pts) {
    const n = (pts || []).length;
    if (n < 2) return null;
    let sx = 0, sy = 0, sxx = 0, sxy = 0;
    let xmin = Infinity, xmax = -Infinity;
    pts.forEach((p) => {
      sx += p.x; sy += p.y; sxx += p.x * p.x; sxy += p.x * p.y;
      if (p.x < xmin) xmin = p.x;
      if (p.x > xmax) xmax = p.x;
    });
    const den = n * sxx - sx * sx;
    if (!den) return null;
    const b = (n * sxy - sx * sy) / den;
    const a = (sy - b * sx) / n;
    return [{ x: xmin, y: a + b * xmin }, { x: xmax, y: a + b * xmax }];
  }

  function renderWoprYearChips(years) {
    const el = $("#wopr-persist-years");
    if (!el) return;
    el.innerHTML = years.map((y) =>
      `<button class="season-chip${y === woprYear ? " on" : ""}" data-y="${y}">${y}</button>`
    ).join("");
    el.querySelectorAll("button").forEach((btn) => {
      btn.addEventListener("click", () => {
        woprYear = +btn.dataset.y;
        renderWoprPersist();
      });
    });
  }

  async function renderWoprPersist() {
    const card = $("#wopr-persist");
    const sub = $("#wopr-persist-sub");
    const wrap = $("#wopr-persist-wrap");
    const canvas = $("#wopr-persist-chart");
    const legend = $("#wopr-persist-legend");
    if (!card || !canvas) return;
    const years = woprPersistYears();
    if (!years.length) {
      if (sub) sub.textContent = "needs 2018+ seasons with receiving usage";
      if (wrap) wrap.innerHTML = A.notice("No 2018+ seasons to plot.");
      return;
    }
    if (woprYear == null || years.indexOf(woprYear) < 0) {
      woprYear = null;
      for (let i = 0; i < years.length; i++) {
        let probe = null;
        try { probe = await A.loadYear(years[i]); } catch (e) { probe = null; }
        if (probe && (probe.receivingUsage || []).length) {
          woprYear = years[i];
          break;
        }
      }
      if (woprYear == null) {
        if (sub) sub.textContent = "needs a season with receiving usage";
        if (wrap) wrap.innerHTML = A.notice("No receiving usage to plot.");
        return;
      }
    }
    renderWoprYearChips(years);
    let yd = null;
    try { yd = await A.loadYear(woprYear); } catch (e) { yd = null; }
    const pts = yd ? woprPersistPoints(yd) : [];
    const r2 = woprR2(pts);
    const r2txt = r2 == null ? "—" : r2.toFixed(3);
    if (sub) {
      sub.textContent = `${woprYear} WOPR vs ${woprYear} AFFL Fantasy Points Per Game · WR/TE · non-PPR · R² ${r2txt} · n=${pts.length}`;
    }
    if (legend) {
      legend.innerHTML = Object.keys(WOPR_POS).map((pos) =>
        `<span><i class="wopr-swatch" style="background:${WOPR_POS[pos]}"></i>${pos}</span>`
      ).join("");
    }
    if (woprChart) { woprChart.destroy(); woprChart = null; }
    if (!pts.length) {
      wrap.classList.add("as-notice");
      wrap.innerHTML = A.notice(`No WR/TE with ${woprYear} WOPR and AFFL points.`);
      return;
    }
    wrap.classList.remove("as-notice");
    if (!wrap.querySelector("canvas")) {
      wrap.innerHTML = `<canvas id="wopr-persist-chart"></canvas>`;
    }
    const ctx = $("#wopr-persist-chart");
    if (!ctx) return;
    const datasets = Object.keys(WOPR_POS).map((pos) => {
      const rows = pts.filter((p) => p.pos === pos);
      return {
        label: pos,
        data: rows.map((p) => ({ x: p.x, y: p.y, r: p })),
        backgroundColor: WOPR_POS[pos] + "cc",
        borderColor: WOPR_POS[pos],
        pointRadius: 4,
        pointHoverRadius: 6,
      };
    });
    const fit = woprFitLine(pts);
    if (fit) {
      datasets.push({
        type: "line",
        label: "fit",
        data: fit,
        borderColor: C.ice,
        borderWidth: 1.5,
        borderDash: [5, 4],
        pointRadius: 0,
        fill: false,
        tension: 0,
      });
    }
    woprChart = new Chart(ctx, {
      type: "scatter",
      data: { datasets },
      options: {
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: (c) => {
                const p = c.raw && c.raw.r;
                if (!p) return "";
                return `${p.name} · ${p.pos} · WOPR ${fmt(p.wopr, 3)} · ${woprYear} AFFL ${fmt(p.fppg, 1)} Fantasy Points Per Game`;
              },
            },
          },
        },
        scales: {
          x: {
            grid: { color: C.grid },
            border: { display: false },
            title: { display: true, text: woprYear + " WOPR" },
          },
          y: {
            grid: { color: C.grid },
            border: { display: false },
            title: { display: true, text: woprYear + " AFFL Fantasy Points Per Game (non-PPR)" },
          },
        },
        onClick: (_e, els) => {
          if (!els || !els.length) return;
          const ds = woprChart.data.datasets[els[0].datasetIndex];
          const raw = ds && ds.data && ds.data[els[0].index];
          const p = raw && raw.r;
          if (!p || p.pid == null) return;
          logYear = "all";
          loadPlayer(p.pid, true);
          renderGrid();
          window.scrollTo({ top: 0, behavior: "smooth" });
        },
      },
    });
    window.__afflWoprPersist = { year: woprYear, yearN: woprYear, yearN1: woprYear, n: pts.length, r2: r2, points: pts };
  }

  async function initWoprPersist() {
    if (woprWired) return renderWoprPersist();
    woprWired = true;
    await renderWoprPersist();
  }


  /* Flock-style compare: 2025 AFFL + advanced CSVs. Non-PPR. Missing stays —. */
  const CMP_DEFAULT = [4429795, 4430807];
  let CMP_ADV = { players: {} };
  let cmpYear = 2025;
  let cmpPerGame = true;
  let cmpPids = CMP_DEFAULT.slice();
  let cmpUsage = {};
  let cmpYearPlayers = {};
  let cmpWired = false;

  function cmpNum(v) {
    if (v == null || v === "") return null;
    const n = Number(v);
    return Number.isFinite(n) ? n : null;
  }

  function cmpNflSeason(pid, y) {
    const rec = nflYearWeeks(pid, y);
    let pts = 0, games = 0, yds = 0, td = 0, tgt = 0, epa = 0, xtd = 0;
    let nYds = 0, nTd = 0, nTgt = 0, nEpa = 0, nXtd = 0;
    Object.keys(rec).forEach((wk) => {
      if (!isWeekKey(wk)) return;
      const w = rec[wk];
      if (!w) return;
      games += 1;
      if (w.pts != null && Number.isFinite(Number(w.pts))) pts += Number(w.pts);
      if (w.yds != null) { yds += Number(w.yds); nYds += 1; }
      if (w.td != null) { td += Number(w.td); nTd += 1; }
      if (w.tgt != null) { tgt += Number(w.tgt); nTgt += 1; }
      if (w.epa != null) { epa += Number(w.epa); nEpa += 1; }
      if (w.xtd != null) { xtd += Number(w.xtd); nXtd += 1; }
    });
    return {
      pts: games ? pts : null,
      games: games || null,
      yds: nYds ? yds : null,
      td: nTd ? td : null,
      tgt: nTgt ? tgt : null,
      epa: nEpa ? epa : null,
      xtd: nXtd ? xtd : null,
    };
  }

  function cmpBundle(pid) {
    const id = String(pid);
    const m = INDEX[id] || {};
    const adv = (CMP_ADV.players || {})[id] || {};
    const box = cmpNflSeason(pid, cmpYear);
    const usage = cmpUsage[Number(pid)] || cmpUsage[id] || {};
    const ngs = ((NGS_PROFILES && NGS_PROFILES.players) || {})[id] || {};
    const yp = cmpYearPlayers[Number(pid)] || cmpYearPlayers[id] || {};
    const games = cmpNum(adv.games) || box.games;
    const pts = box.pts;
    const fppg = (pts != null && box.games) ? pts / box.games : null;
    let owner = null, tid = yp.mainTeam;
    if (tid != null) owner = ownerForTid(cmpYear, tid);
    return {
      pid: Number(pid),
      name: m.name || adv.name || yp.name || ("#" + pid),
      pos: (m.pos || adv.pos || yp.pos || "").toUpperCase(),
      nfl: adv.nfl || yp.nfl || nflTeam(pid, cmpYear) || "",
      hs: (nflBlock(pid).meta || {}).hs || yp.hs || "",
      owner: owner,
      franchise: owner ? (A.franchiseName(owner) || "—") : "—",
      logo: owner ? A.franchiseLogo(owner) : "",
      games: games,
      affl_pts: pts,
      affl_fppg: fppg,
      adv: adv,
      usage: usage,
      ngs: ngs,
      box: box,
    };
  }

  function cmpMetricDefs(pos) {
    const common = [
      { key: "affl_fppg", label: "AFFL FPpG", kind: "rate", digits: 1 },
      { key: "affl_pts", label: "AFFL pts", kind: "count", digits: 1 },
      { key: "pos_finish", label: "AFFL pos finish", kind: "rank", digits: 0 },
      { key: "games", label: "Games", kind: "rate", digits: 0 },
      { key: "qg_pct", label: "Quality+Great %", kind: "pct", digits: 0, adv: "qg_pct" },
      { key: "snap_pct", label: "Snap %", kind: "pct", digits: 0, adv: "snap_pct" },
      { key: "util_pct", label: "Util %", kind: "pct", digits: 0, adv: "util_pct" },
      { key: "pts_per_100", label: "AFFL pts / 100 snaps", kind: "rate", digits: 1, adv: "pts_per_100" },
    ];
    if (pos === "RB") {
      return common.concat([
        { key: "rush_att", label: "Rush attempts", kind: "count", digits: 1, adv: "rush_att" },
        { key: "rush_yds", label: "Rush yards", kind: "count", digits: 1, adv: "rush_yds" },
        { key: "ypc", label: "Yards/carry", kind: "rate", digits: 2, adv: "ypc" },
        { key: "rush_brktkl", label: "Broken tackles", kind: "count", digits: 1, adv: "rush_brktkl" },
        { key: "tgt", label: "Targets", kind: "count", digits: 1, adv: "tgt" },
        { key: "rec", label: "Receptions", kind: "count", digits: 1, adv: "rec" },
        { key: "rz_tgt", label: "RZ targets", kind: "count", digits: 1, adv: "rz_tgt" },
        { key: "tgt_share", label: "Target share", kind: "pct1", digits: 1, usage: "tgtShare" },
        { key: "wopr", label: "WOPR", kind: "rate", digits: 3, usage: "wopr" },
        { key: "ryoe", label: "RYOE/att", kind: "rate", digits: 2, ngs: "rush_2025_ryoe_att" },
      ]);
    }
    if (pos === "WR" || pos === "TE") {
      return common.concat([
        { key: "rec", label: "Receptions", kind: "count", digits: 1, adv: "rec" },
        { key: "rec_yds", label: "Rec yards", kind: "count", digits: 1, adv: "rec_yds" },
        { key: "ypr", label: "Yards/rec", kind: "rate", digits: 1, adv: "ypr" },
        { key: "tgt", label: "Targets", kind: "count", digits: 1, adv: "tgt" },
        { key: "tgt_tm", label: "Team target %", kind: "pct", digits: 1, adv: "tgt_tm" },
        { key: "rz_tgt", label: "RZ targets", kind: "count", digits: 1, adv: "rz_tgt" },
        { key: "yac", label: "YAC", kind: "count", digits: 1, adv: "yac" },
        { key: "drops", label: "Drops", kind: "count", digits: 1, adv: "drops", invert: true },
        { key: "tgt_share", label: "Target share", kind: "pct1", digits: 1, usage: "tgtShare" },
        { key: "wopr", label: "WOPR", kind: "rate", digits: 3, usage: "wopr" },
        { key: "sep", label: "Separation", kind: "rate", digits: 2, ngs: "rec_2025_sep" },
        { key: "yacoe", label: "YACoE", kind: "rate", digits: 2, ngs: "rec_2025_yacoe" },
      ]);
    }
    if (pos === "QB") {
      return common.concat([
        { key: "pass_cmp", label: "Completions", kind: "count", digits: 1, adv: "pass_cmp" },
        { key: "pass_att", label: "Pass attempts", kind: "count", digits: 1, adv: "pass_att" },
        { key: "pass_pct", label: "Comp %", kind: "pct", digits: 1, adv: "pass_pct" },
        { key: "pass_yds", label: "Pass yards", kind: "count", digits: 1, adv: "pass_yds" },
        { key: "ypa", label: "Yards/att", kind: "rate", digits: 1, adv: "ypa" },
        { key: "sacks", label: "Sacks taken", kind: "count", digits: 1, adv: "sacks", invert: true },
        { key: "pass_rtg", label: "Passer rating", kind: "rate", digits: 0, adv: "pass_rtg" },
        { key: "cpoe", label: "CPOE", kind: "rate", digits: 2, ngs: "pass_2025_cpoe" },
        { key: "ttt", label: "Time to throw", kind: "rate", digits: 2, ngs: "pass_2025_ttt" },
      ]);
    }
    return common.concat([
      { key: "yds", label: "Yards", kind: "count", digits: 1, nfl: "yds" },
      { key: "td", label: "TDs", kind: "count", digits: 1, nfl: "td" },
    ]);
  }

  function cmpRawValue(b, def) {
    if (def.key === "affl_fppg") return b.affl_fppg;
    if (def.key === "affl_pts") return b.affl_pts;
    if (def.key === "games") return b.games;
    if (def.key === "pos_finish") return b.affl_pts;
    if (def.adv) return cmpNum(b.adv[def.adv]);
    if (def.usage) return cmpNum(b.usage[def.usage]);
    if (def.ngs) return cmpNum(b.ngs[def.ngs]);
    if (def.nfl) return cmpNum(b.box[def.nfl]);
    return null;
  }

  function cmpDisplayValue(b, def) {
    const raw = cmpRawValue(b, def);
    if (raw == null) return null;
    if (def.key === "pos_finish") return raw;
    if (cmpPerGame && def.kind === "count") {
      const g = def.adv ? (cmpNum(b.adv.games) || b.games) : (b.box && b.box.games) || b.games;
      if (g) return raw / g;
    }
    return raw;
  }

  function cmpFormat(def, v) {
    if (v == null) return "—";
    if (def.kind === "pct") return fmt(v, def.digits) + "%";
    if (def.kind === "pct1") return (Math.abs(v) <= 1 ? fmt(v * 100, def.digits) : fmt(v, def.digits)) + "%";
    return fmt(v, def.digits);
  }

  let cmpPoolCache = {};
  function cmpPosPool(pos) {
    if (cmpPoolCache[pos]) return cmpPoolCache[pos];
    const out = [];
    Object.keys(INDEX).forEach((pid) => {
      const p = (INDEX[pid] && INDEX[pid].pos) || "";
      if (String(p).toUpperCase() !== pos) return;
      out.push(cmpBundle(pid));
    });
    cmpPoolCache[pos] = out;
    return out;
  }

  function cmpRank(def, pos, value) {
    if (value == null) return null;
    const pool = cmpPosPool(pos).map((b) => cmpDisplayValue(b, def)).filter((v) => v != null);
    if (!pool.length) return null;
    const invert = !!def.invert;
    const better = pool.filter((v) => invert ? v < value : v > value).length;
    return { rank: better + 1, n: pool.length };
  }

  function cmpTier(rank, n) {
    if (rank == null || !n) return "na";
    if (rank === 1) return "hi";
    const a = Math.ceil(n / 3);
    const b = Math.ceil((2 * n) / 3);
    if (rank <= a) return "hi";
    if (rank <= b) return "mid";
    return "lo";
  }

  function cmpWriteURL() {
    const u = new URL(location.href);
    u.searchParams.set("compare", cmpPids.filter(Boolean).join(","));
    history.replaceState(null, "", u.pathname.split("/").pop() + u.search + u.hash);
  }

  function cmpReadURL() {
    const raw = new URLSearchParams(location.search).get("compare");
    if (!raw) return;
    const ids = raw.split(",").map((x) => +x).filter((n) => n > 0);
    if (ids.length >= 2) cmpPids = ids.slice(0, 2);
    else if (ids.length === 1) cmpPids = [ids[0], CMP_DEFAULT[1] === ids[0] ? CMP_DEFAULT[0] : CMP_DEFAULT[1]];
  }

  function cmpSuggest(q) {
    const s = String(q || "").trim().toLowerCase();
    if (s.length < 2) return [];
    const hits = Object.keys(INDEX).map((pid) => {
      const m = INDEX[pid] || {};
      const live = !!(CMP_ADV.players || {})[pid] || !!cmpNflSeason(pid, cmpYear).games;
      return { pid: +pid, name: m.name || ("#" + pid), pos: m.pos || "", live: live };
    }).filter((p) => p.name.toLowerCase().indexOf(s) >= 0);
    hits.sort((a, b) => (b.live - a.live) || a.name.localeCompare(b.name));
    return hits.slice(0, 12);
  }

  function renderCompare() {
    const grid = $("#pl-compare-grid");
    const sub = $("#pl-compare-sub");
    if (!grid) return;
    const mode = cmpPerGame ? "Per game" : "Season";
    if (sub) sub.textContent = `2025 ${mode} · AFFL non-PPR · advanced box from the 2025 dumps · rank is among that position`;
    cmpPoolCache = {};
    const bags = cmpPids.map((pid) => cmpBundle(pid));
    grid.innerHTML = bags.map((b, slot) => {
      const pos = b.pos || "RB";
      const has2025 = b.affl_pts != null || (b.adv && (b.adv.rush_att != null || b.adv.tgt != null || b.adv.pass_att != null || b.adv.snap_pct != null));
      const defs = cmpMetricDefs(pos).filter((def) => {
        if (cmpPerGame && def.key === "affl_pts") return false;
        if (!cmpPerGame && def.key === "affl_fppg") return false;
        return true;
      });
      const rows = defs.map((def) => {
        const val = cmpDisplayValue(b, def);
        let rk = cmpRank(def, pos, val);
        let shown = val;
        if (def.key === "pos_finish") {
          rk = cmpRank({ key: "affl_pts", kind: "rate" }, pos, b.affl_pts);
          shown = rk ? rk.rank : null;
        }
        const tier = cmpTier(rk && rk.rank, rk && rk.n);
        const vtxt = def.key === "pos_finish" ? (shown == null ? "—" : String(shown)) : cmpFormat(def, shown);
        const rtxt = rk ? String(rk.rank) : "—";
        return `<tr>
          <td class="cmp-m">${A.esc(def.label)}</td>
          <td class="cmp-v"><span class="cmp-box ${tier}">${vtxt}</span></td>
          <td class="cmp-r"><span class="cmp-box ${tier}">${rtxt}</span></td>
        </tr>`;
      }).join("");
      const ini = A.initials(b.name);
      const face = A.headshotHTML({ pid: b.pid, name: b.name, pos: b.pos, nfl: b.nfl, hs: b.hs }, "pl-hs");
      const fran = b.franchise && b.franchise !== "—" ? A.esc(b.franchise) : "—";
      const body = has2025 ? `<table class="cmp-tbl">
          <thead><tr><th>Metric</th><th>Value</th><th>Rank</th></tr></thead>
          <tbody>${rows}</tbody>
        </table>` : `<p class="notice">No 2025 season on file. Compare is 2025 only.</p>`;
      return `<article class="cmp-card" data-slot="${slot}">
        <div class="cmp-id">
          <div class="cmp-ini">${A.esc(ini)}</div>
          <div class="cmp-face">
            ${face}
            <div>
              <div class="cmp-name">${A.playerLink(b.pid, b.name, { log: cmpYear })}</div>
              <div class="cmp-tags">
                <span class="badge pos-${A.esc(b.pos)}">${A.esc(b.pos || "—")}</span>
                <span class="badge">${A.esc(b.nfl || "NFL")}</span>
                <span class="cmp-fran">${fran}</span>
              </div>
            </div>
          </div>
          <div class="cmp-search-wrap">
            <input class="cmp-search" data-slot="${slot}" type="search" placeholder="Swap player…" aria-label="Swap compare player">
            <div class="cmp-suggest" data-slot="${slot}" hidden></div>
          </div>
        </div>
        <div class="cmp-tf">Timeframe: season ${cmpYear}</div>
        ${body}
      </article>`;
    }).join("");
    grid.querySelectorAll(".cmp-search").forEach((inp) => {
      const slot = +inp.dataset.slot;
      const box = grid.querySelector(`.cmp-suggest[data-slot="${slot}"]`);
      inp.addEventListener("input", () => {
        const hits = cmpSuggest(inp.value);
        if (!hits.length) { box.hidden = true; box.innerHTML = ""; return; }
        box.hidden = false;
        box.innerHTML = hits.map((p) =>
          `<button type="button" data-pid="${p.pid}">${A.esc(p.name)} · ${A.esc(p.pos)}</button>`
        ).join("");
        box.querySelectorAll("button").forEach((btn) => {
          btn.addEventListener("click", () => {
            cmpPids[slot] = +btn.dataset.pid;
            cmpWriteURL();
            renderCompare();
          });
        });
      });
    });
    window.__afflCompare = {
      year: cmpYear,
      perGame: cmpPerGame,
      pids: cmpPids.slice(),
      scoring: "AFFL non-PPR",
    };
  }

  function wireCompare() {
    if (cmpWired) return;
    cmpWired = true;
    const mode = $("#pl-compare-mode");
    if (mode) {
      mode.querySelectorAll("button").forEach((b) => {
        b.addEventListener("click", () => {
          cmpPerGame = b.dataset.mode !== "season";
          mode.querySelectorAll("button").forEach((x) => x.classList.toggle("on", x === b));
          renderCompare();
        });
      });
    }
  }

  async function initCompare() {
    cmpReadURL();
    try {
      CMP_ADV = await fetch("compare_adv.json?v=" + Date.now(), { cache: "no-store" }).then((r) => r.ok ? r.json() : { players: {} });
    } catch (e) { CMP_ADV = { players: {} }; }
    try {
      const yd = await A.loadYear(cmpYear);
      cmpUsage = {};
      (yd.receivingUsage || []).forEach((r) => { if (r && r.pid != null) cmpUsage[Number(r.pid)] = r; });
      cmpYearPlayers = {};
      (yd.players || []).forEach((r) => { if (r && r.pid != null) cmpYearPlayers[Number(r.pid)] = r; });
    } catch (e) { cmpUsage = {}; cmpYearPlayers = {}; }
    wireCompare();
    renderCompare();
  }

  function paintChrome() {
    const seasonYear = scope === "cum" ? null : year;
    if (seasonYear != null && squad && !A.franchisePlayedSeason(squad, seasonYear)) {
      squad = "";
      A.stampNav("");
    }
    const ylist = squad ? A.squadYears(squad) : A.years();
    A.seasonSelect(document.getElementById("year-picker"), seasonYear, async (y) => {
      if (y == null) scope = "cum";
      else { scope = "season"; year = y; try { YD = await A.loadYear(year); T = A.teams(year); } catch (e) {} }
      if (year != null && squad && !A.franchisePlayedSeason(squad, year)) {
        squad = "";
        A.stampNav("");
      }
      paintChrome();
      renderGrid();
    }, ylist);
    A.remountTeamSelect(document.getElementById("squad-picker"), squad, (s) => {
      squad = s || "";
      A.stampNav(squad);
      if (squad && scope === "season") {
        const next = A.clampYear(year, squad);
        if (next == null) scope = "cum";
        else year = next;
      }
      paintChrome();
      renderGrid();
    }, seasonYear);
  }

  async function pick(pid, ly) {
    cur = null;
    PP.limit = 24;
    A.stampNav(squad);
    paintChrome();
    logYear = ly == null ? "all" : ly;
    // Force clean landing state immediately.
    setPageMode("landing");
    const g = $("#pp-grid");
    if (g && !pid) g.innerHTML = A.notice("Loading players…");
    if (chart) { chart.destroy(); chart = null; }
    if (ngsChart) { ngsChart.destroy(); ngsChart = null; }
    if (careerChart) { careerChart.destroy(); careerChart = null; }
    try {
      await careerPlayers();
      YD = await A.loadYear(year);
      T = A.teams(year);
      if (pid) {
        await loadPlayer(pid, false);
      } else {
        setPageMode("landing");
      }
      renderGrid();
      const g2 = $("#pp-grid");
      if (g2) g2.dataset.ready = "1";
    } catch (e) {
      console.error("players pick failed", e);
      const g = $("#pp-grid");
      if (g) g.innerHTML = A.notice("Could not load player database. Check the console / network tab.");
      setPageMode("landing");
    }
  }

  const qs = new URLSearchParams(location.search);
  const lyRaw = qs.get("log");
  const ly = lyRaw === "all" ? "all" : (lyRaw ? +lyRaw : null);
  await pick(+qs.get("pid") || null, ly);
  await initWoprPersist();
  await initCompare();
  window.addEventListener("popstate", () => {
    const q2 = new URLSearchParams(location.search);
    const ly2 = q2.get("log") === "all" ? "all" : (q2.get("log") ? +q2.get("log") : null);
    pick(+q2.get("pid") || null, ly2);
  });
})();
