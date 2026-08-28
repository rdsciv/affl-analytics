/* CHI-120 real History book. All-Play on All = career 2014-2025. No remote core. */
/* AFFL History — current name, leeger career, positional PPD. */
(async function () {
  const A = window.AFFL;
  const { DATA } = await A.boot();
  const [ALL, MOVES, WAIVERS, NGS_PROFILES, PRE2018_SEASON_ROSTERS] = await Promise.all([
    A.loadAllYears(),
    fetch("moves.json?v=" + Date.now(), { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : {}))
      .catch(() => ({})),
    fetch("waivers.json?v=" + Date.now(), { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : {}))
      .catch(() => ({})),
    fetch("ngs_profiles.json?v=" + Date.now(), { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : { franchises: [] }))
      .catch(() => ({ franchises: [] })),
    fetch("pre2018_season_rosters.json?v=" + Date.now(), { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : {}))
      .catch(() => ({})),
  ]);
  await A.loadBios();
  const $ = (id) => document.getElementById(id);

  const MERGE = { m01: "m07", m03: "m08", m20: "m10" };
  const canon = (id) => MERGE[id] || id;
  const POS = ["QB", "RB", "WR", "TE", "K", "DST"];

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"]/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;",
    }[c]));
  }

  function ordinal(n) {
    if (n == null || n === "" || n === 99) return "—";
    const v = Number(n);
    if (Number.isNaN(v)) return "—";
    const j = v % 10, k = v % 100;
    const suf = (j === 1 && k !== 11) ? "st"
      : (j === 2 && k !== 12) ? "nd"
      : (j === 3 && k !== 13) ? "rd" : "th";
    return v + suf;
  }

  function shortTeam(name) {
    const parts = String(name || "").split(/\s+/).filter(Boolean);
    return parts.length ? parts[parts.length - 1] : name;
  }

  function median(arr) {
    if (!arr.length) return 0;
    const s = arr.slice().sort((a, b) => a - b);
    const m = Math.floor(s.length / 2);
    return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
  }

  function stdev(arr) {
    if (arr.length < 2) return 0;
    const mean = arr.reduce((a, b) => a + b, 0) / arr.length;
    const v = arr.reduce((a, b) => a + (b - mean) * (b - mean), 0) / arr.length;
    return Math.sqrt(v);
  }

  function streaksFromCum(cum) {
    let w = 0, l = 0, mw = 0, ml = 0, prev = 0;
    (cum || []).forEach((c) => {
      if (c > prev) { w += 1; l = 0; if (w > mw) mw = w; }
      else { l += 1; w = 0; if (l > ml) ml = l; }
      prev = c;
    });
    return { winStreak: mw, loseStreak: ml };
  }

  function movesBag(year, tid) {
    const y = MOVES[String(year)] || {};
    if (tid == null) return null;
    return y[String(tid)] || y[tid] || null;
  }

  function movesCount(year, tid) {
    const b = movesBag(year, tid);
    return b && b.moves != null ? Number(b.moves) : null;
  }

  function ownerByTid(year) {
    const out = {};
    ((DATA.seasons[String(year)] || {}).teams || []).forEach((t) => {
      if (t.owner) out[t.id] = canon(t.owner);
    });
    return out;
  }

  function rollFranchises() {
    const by = {};
    const years = Object.keys(DATA.seasons || {}).sort();
    const seasonBooks = [];
    years.forEach((y) => {
      const season = DATA.seasons[y] || {};
      const teams = season.teams || [];
      const n = teams.length;
      let topPf = -1;
      teams.forEach((t) => { if ((t.pf || 0) > topPf) topPf = t.pf || 0; });
      teams.forEach((t) => {
        const oid = canon(t.owner);
        if (!oid) return;
        if (!franchisePlayedSeason(oid, +y)) return;
        if (!by[oid]) {
          by[oid] = {
            owner: oid, name: t.name, logo: t.logo || "",
            seasons: 0, wins: 0, losses: 0, ties: 0, regWins: 0,
            pf: 0, pa: 0, allW: 0, allL: 0, expWins: 0, luck: 0,
            titles: 0, runnerUps: 0, thirds: 0, sackos: 0, playoffs: 0,
            scoreTitles: 0, bestFinish: 99, worstFinish: 0,
            maxScore: null, minScore: null, weekN: 0, weekSum: 0,
            weeks: [], finishes: {}, firstYear: +y, lastYear: +y, active: false,
            highPf: null, lowPf: null, tenWins: 0,
            winStreak: 0, loseStreak: 0, moves: 0, trades: 0, activate: 0,
          };
        }
        const r = by[oid];
        r.name = t.name;
        if (t.logo) r.logo = t.logo;
        r.lastYear = +y;
        if (r.firstYear == null || +y < r.firstYear) r.firstYear = +y;
        r.seasons += 1;
        const seasonPf = t.pf || 0;
        if (r.highPf == null || seasonPf > r.highPf) r.highPf = seasonPf;
        if (r.lowPf == null || seasonPf < r.lowPf) r.lowPf = seasonPf;
        if ((t.wins || 0) >= 10) r.tenWins += 1;
        r.wins += t.wins || 0;
        r.losses += t.losses || 0;
        r.ties += t.ties || 0;
        r.regWins += t.regWins != null ? t.regWins : (t.wins || 0);
        r.pf += t.pf || 0;
        r.pa += t.pa || 0;
        r.allW += t.allplayW || 0;
        r.allL += t.allplayL || 0;
        r.expWins += t.expWins || 0;
        r.luck += t.luck || 0;
        if (t.finalRank === 1) r.titles += 1;
        if (t.finalRank === 2) r.runnerUps += 1;
        if (t.finalRank === 3) r.thirds += 1;
        if (t.finalRank && t.finalRank === n) r.sackos += 1;
        if (t.playoffSeed && t.playoffSeed <= 6) r.playoffs += 1;
        if (t.finalRank && t.finalRank < r.bestFinish) r.bestFinish = t.finalRank;
        if (t.finalRank && t.finalRank > r.worstFinish) r.worstFinish = t.finalRank;
        if (topPf > 0 && t.pf === topPf) r.scoreTitles += 1;
        const st = streaksFromCum(t.cumWins);
        if (st.winStreak > r.winStreak) r.winStreak = st.winStreak;
        if (st.loseStreak > r.loseStreak) r.loseStreak = st.loseStreak;
        const bag = movesBag(y, t.id);
        if (bag) {
          if (bag.moves != null) r.moves += Number(bag.moves);
          if (bag.trades != null) r.trades += Number(bag.trades);
          if (bag.moveToActive != null) r.activate += Number(bag.moveToActive);
        }
        r.finishes[y] = {
          rank: t.finalRank || null,
          po: !!(t.playoffSeed && t.playoffSeed <= 6),
          sacko: t.finalRank === n,
        };
        (t.weekly || []).forEach((w) => {
          if (w == null) return;
          r.weekN += 1;
          r.weekSum += w;
          r.weeks.push(w);
          if (r.maxScore == null || w > r.maxScore) r.maxScore = w;
          if (r.minScore == null || w < r.minScore) r.minScore = w;
        });
        seasonBooks.push({
          year: +y, owner: oid, name: t.name, logo: t.logo,
          pf: t.pf || 0, luck: t.luck || 0, allW: t.allplayW || 0,
          winPct: (t.wins || 0) / Math.max(1, (t.wins || 0) + (t.losses || 0) + (t.ties || 0)),
          maxWeek: Math.max.apply(null, (t.weekly || []).filter((x) => x != null).concat([0])),
          moves: bag && bag.moves != null ? Number(bag.moves) : null,
          trades: bag && bag.trades != null ? Number(bag.trades) : null,
          moveToActive: bag && bag.moveToActive != null ? Number(bag.moveToActive) : null,
        });
      });
    });
    (DATA.franchises || []).forEach((f) => {
      const oid = canon(f.owner);
      if (!by[oid]) {
        by[oid] = {
          owner: oid, name: f.currentName || "", logo: f.logo || "",
          seasons: 0, wins: 0, losses: 0, ties: 0, regWins: 0,
          pf: 0, pa: 0, allW: 0, allL: 0, expWins: 0, luck: 0,
          titles: 0, runnerUps: 0, thirds: 0, sackos: 0, playoffs: 0,
          scoreTitles: 0, bestFinish: 99, worstFinish: 0,
          maxScore: null, minScore: null, weekN: 0, weekSum: 0,
          weeks: [], finishes: {}, firstYear: null, lastYear: null, active: false,
          highPf: null, lowPf: null, tenWins: 0,
          winStreak: 0, loseStreak: 0, moves: 0, trades: 0, activate: 0,
        };
      }
      const r = by[oid];
      if (f.currentName) r.name = f.currentName;
      if (f.logo) r.logo = f.logo;
      r.active = !!f.active;
      if (f.titles != null) r.titles = f.titles;
      if (f.runnerUps != null) r.runnerUps = f.runnerUps;
      if (f.playoffs != null) r.playoffs = f.playoffs;
      if (f.bestFinish != null) r.bestFinish = f.bestFinish;
      const ys = (f.years || []).slice().sort((a, b) => a - b);
      r.firstYear = ys.length ? ys[0] : null;
      r.lastYear = ys.length ? ys[ys.length - 1] : null;
      r.seasons = ys.length;
    });
    return {
      rows: Object.values(by).map((r) => {
        const games = r.wins + r.losses + r.ties;
        const ap = r.allW + r.allL;
        r.winPct = games ? r.wins / games : 0;
        r.allPct = ap ? r.allW / ap : 0;
        r.diff = r.pf - r.pa;
        r.avgPts = r.weekN ? r.weekSum / r.weekN : 0;
        r.ppg = r.weekN ? r.pf / r.weekN : 0;
        r.papg = r.weekN ? r.pa / r.weekN : 0;
        r.medPts = median(r.weeks);
        r.sdPts = stdev(r.weeks);
        r.poPct = r.seasons ? r.playoffs / r.seasons : 0;
        r.games = games;
        r.combined = (r.titles || 0) + (r.runnerUps || 0) + (r.thirds || 0) + (r.scoreTitles || 0) - (r.sackos || 0);
        return r;
      }),
      seasonBooks,
    };
  }

  function rollPPD() {
    const by = {};
    ALL.forEach(({ year, data }) => {
      const baselines = {};
      ((data.draftValue && data.draftValue.baselines) || []).forEach((b) => {
        baselines[b.position] = b.baseline;
      });
      const owners = ownerByTid(year);
      (((data.draft && data.draft.board) || [])).forEach((p) => {
        const oid = owners[p.tid];
        if (!oid) return;
        if (!by[oid]) {
          by[oid] = { spend: 0, draftPts: 0, par: 0, scoredSpend: 0, pos: {} };
          POS.forEach((pos) => { by[oid].pos[pos] = { spend: 0, pts: 0, par: 0, n: 0 }; });
        }
        const pos = p.pos === "D/ST" ? "DST" : p.pos;
        const bid = p.bid || 0;
        const pts = p.pts || 0;
        const base = baselines[pos];
        const r = by[oid];
        r.spend += bid;
        if (p.pts != null) {
          r.draftPts += pts;
          r.scoredSpend += bid;
          if (base != null) r.par += pts - base;
        }
        if (r.pos[pos]) {
          r.pos[pos].spend += bid;
          r.pos[pos].n += 1;
          if (p.pts != null) {
            r.pos[pos].pts += pts;
            if (base != null) r.pos[pos].par += pts - base;
          }
        }
      });
    });
    Object.values(by).forEach((r) => {
      r.ppd = r.scoredSpend ? r.draftPts / r.scoredSpend : 0;
      r.parpd = r.scoredSpend ? r.par / r.scoredSpend : 0;
      POS.forEach((pos) => {
        const p = r.pos[pos];
        p.ppd = p.spend ? p.pts / p.spend : 0;
        p.parpd = p.spend ? p.par / p.spend : 0;
        r["ppd" + pos] = p.ppd;
      });
    });
    return by;
  }

  function rollIQ() {
    const by = {};
    ALL.forEach(({ year, data }) => {
      const owners = ownerByTid(year);
      (data.lineupIQ || []).forEach((row) => {
        const oid = owners[row.teamId];
        if (!oid || row.eff == null) return;
        if (!by[oid]) by[oid] = { n: 0, eff: 0 };
        by[oid].n += 1;
        by[oid].eff += row.eff;
      });
    });
    const out = {};
    Object.keys(by).forEach((k) => { out[k] = by[k].n ? by[k].eff / by[k].n : 0; });
    return out;
  }

  const rolled = rollFranchises();
  const PPD = rollPPD();
  const IQ = rollIQ();
  const ROWS = rolled.rows.map((r) => {
    const p = PPD[r.owner] || { spend: 0, draftPts: 0, ppd: 0, parpd: 0, pos: {} };
    r.spend = p.spend || 0;
    r.draftPts = p.draftPts || 0;
    r.ppd = p.ppd || 0;
    r.parpd = p.parpd || 0;
    r.ppdPos = p.pos || {};
    POS.forEach((pos) => { r["ppd" + pos] = (p.pos[pos] && p.pos[pos].ppd) || 0; });
    r.iq = IQ[r.owner] || 0;
    return r;
  });
  const NAME = {};
  ROWS.forEach((r) => { NAME[r.owner] = r.name; });

  function careerRows() {
    return A.visibleFranchises(ROWS);
  }

  const KEYS = {
    name: (f) => f.name || "",
    seasons: (f) => f.seasons || 0,
    wins: (f) => f.wins || 0,
    winPct: (f) => f.winPct || 0,
    regWins: (f) => f.regWins || 0,
    titles: (f) => f.titles || 0,
    runnerUps: (f) => f.runnerUps || 0,
    thirds: (f) => f.thirds || 0,
    scoreTitles: (f) => f.scoreTitles || 0,
    sackos: (f) => f.sackos || 0,
    combined: (f) => (f.combined == null ? 0 : f.combined),
    highPf: (f) => f.highPf || 0,
    lowPf: (f) => (f.lowPf == null ? 99999 : f.lowPf),
    tenWins: (f) => f.tenWins || 0,
    firstYear: (f) => f.firstYear || 0,
    lastYear: (f) => f.lastYear || 0,
    playoffs: (f) => f.playoffs || 0,
    poPct: (f) => f.poPct || 0,
    bestFinish: (f) => (f.bestFinish == null ? 99 : f.bestFinish),
    worstFinish: (f) => f.worstFinish || 0,
    pf: (f) => f.pf || 0,
    pa: (f) => f.pa || 0,
    diff: (f) => f.diff || 0,
    allW: (f) => f.allW || 0,
    allPct: (f) => f.allPct || 0,
    expWins: (f) => f.expWins || 0,
    luck: (f) => f.luck || 0,
    iq: (f) => f.iq || 0,
    ppg: (f) => f.ppg || 0,
    papg: (f) => f.papg || 0,
    avgPts: (f) => f.avgPts || 0,
    medPts: (f) => f.medPts || 0,
    maxScore: (f) => f.maxScore || 0,
    minScore: (f) => f.minScore == null ? 9999 : f.minScore,
    sdPts: (f) => f.sdPts || 0,
    scoreTitles: (f) => f.scoreTitles || 0,
    winStreak: (f) => f.winStreak || 0,
    loseStreak: (f) => f.loseStreak || 0,
    spend: (f) => f.spend || 0,
    draftPts: (f) => f.draftPts || 0,
    ppd: (f) => f.ppd || 0,
    parpd: (f) => f.parpd || 0,
    ppdQB: (f) => f.ppdQB || 0,
    ppdRB: (f) => f.ppdRB || 0,
    ppdWR: (f) => f.ppdWR || 0,
    ppdTE: (f) => f.ppdTE || 0,
    ppdK: (f) => f.ppdK || 0,
    ppdDST: (f) => f.ppdDST || 0,
    moves: (f) => f.moves || 0,
    trades: (f) => f.trades || 0,
    activate: (f) => f.activate || 0,
  };

  let sortKey = "titles";
  let sortDir = -1;
  let scoreKey = "ppg";
  let scoreDir = -1;
  let ppdKey = "ppd";
  let ppdDir = -1;

  function defaultCmp(a, b) {
    return (b.titles - a.titles) || (b.winPct - a.winPct) || (b.pf - a.pf);
  }

  function cmpWith(key, dir, a, b) {
    const fn = KEYS[key];
    const av = fn ? fn(a) : 0;
    const bv = fn ? fn(b) : 0;
    let d;
    if (typeof av === "string") d = av.localeCompare(bv) * dir;
    else d = (av - bv) * dir;
    if (d) return d;
    return defaultCmp(a, b);
  }

  function rec(f) {
    return (f.wins || 0) + "-" + (f.losses || 0) + "-" + (f.ties || 0);
  }

  function teamCell(f) {
    const href = "teams.html?squad=" + encodeURIComponent(f.owner);
    return `<div class="team-cell">${A.logoHTML({ name: f.name, logo: f.logo }, "mini")}<div><a class="hist-name" href="${href}">${esc(f.name)}</a></div></div>`;
  }

  function pill(i) {
    const rank = i + 1;
    const cls = rank === 1 ? "gold" : rank === 2 ? "slv" : rank === 3 ? "brz" : "";
    return `<span class="rank-pill ${cls}">${rank}</span>`;
  }

  function renderTable() {
    const rows = careerRows().slice().sort((a, b) => cmpWith(sortKey, sortDir, a, b));
    const tb = document.querySelector("#franchise-tbl tbody");
    tb.innerHTML = rows.map((f, i) => {
      const pct = (f.winPct * 100).toFixed(1) + "%";
      const ap = (f.allPct * 100).toFixed(1) + "%";
      const po = (f.poPct * 100).toFixed(0) + "%";
      const luck = (f.luck >= 0 ? "+" : "") + A.fmt(f.luck, 2);
      const diff = (f.diff >= 0 ? "+" : "") + A.fmt(f.diff, 1);
      const iq = f.iq ? (f.iq * 100).toFixed(1) + "%" : "—";
      return `<tr>
        <td>${pill(i)}</td>
        <td>${teamCell(f)}</td>
        <td>${f.seasons}</td>
        <td>${rec(f)}</td>
        <td class="${f.winPct >= 0.5 ? "pos" : "neg"}"><strong>${pct}</strong></td>
        <td>${f.regWins || 0}</td>
        <td>${f.titles || 0}</td>
        <td>${f.runnerUps || 0}</td>
        <td>${f.thirds || 0}</td>
        <td>${f.scoreTitles || 0}</td>
        <td>${f.sackos || 0}</td>
        <td>${f.combined == null ? 0 : f.combined}</td>
        <td>${f.playoffs || 0}</td>
        <td>${po}</td>
        <td>${ordinal(f.bestFinish)}</td>
        <td>${ordinal(f.worstFinish)}</td>
        <td>${A.fmt(f.pf, 1)}</td>
        <td>${A.fmt(f.pa, 1)}</td>
        <td class="${f.diff >= 0 ? "pos" : "neg"}">${diff}</td>
        <td>${f.allW}-${f.allL}</td>
        <td>${ap}</td>
        <td>${A.fmt(f.expWins, 1)}</td>
        <td class="${f.luck >= 0 ? "pos" : "neg"}">${luck}</td>
        <td>${iq}</td>
        <td>${f.moves || 0}</td>
        <td>${f.trades || 0}</td>
        <td>${f.activate || 0}</td>
      </tr>`;
    }).join("");
    document.querySelectorAll("#franchise-tbl thead th").forEach((th) => {
      th.classList.toggle("on", th.dataset.k === sortKey);
    });
  }

  function renderScoring() {
    const rows = careerRows().slice().sort((a, b) => cmpWith(scoreKey, scoreDir, a, b));
    document.querySelector("#scoring-tbl tbody").innerHTML = rows.map((f, i) => `
      <tr>
        <td>${pill(i)}</td>
        <td>${teamCell(f)}</td>
        <td>${A.fmt(f.ppg, 1)}</td>
        <td>${A.fmt(f.papg, 1)}</td>
        <td>${A.fmt(f.avgPts, 1)}</td>
        <td>${A.fmt(f.medPts, 1)}</td>
        <td>${A.fmt(f.maxScore, 1)}</td>
        <td>${A.fmt(f.minScore, 1)}</td>
        <td>${A.fmt(f.sdPts, 1)}</td>
        <td>${f.scoreTitles || 0}</td>
        <td>${f.winStreak || 0}</td>
        <td>${f.loseStreak || 0}</td>
      </tr>`).join("");
    document.querySelectorAll("#scoring-tbl thead th").forEach((th) => {
      th.classList.toggle("on", th.dataset.k === scoreKey);
    });
  }

  function renderPPD() {
    const rows = careerRows().filter((f) => f.spend > 0).slice()
      .sort((a, b) => cmpWith(ppdKey, ppdDir, a, b));
    document.querySelector("#ppd-tbl tbody").innerHTML = rows.map((f, i) => {
      const cell = (pos) => {
        const p = f.ppdPos[pos];
        if (!p || !p.spend) return "—";
        return A.fmt(p.ppd, 1);
      };
      return `<tr>
        <td>${pill(i)}</td>
        <td>${teamCell(f)}</td>
        <td>$${A.fmt(f.spend)}</td>
        <td>${A.fmt(f.draftPts, 0)}</td>
        <td><strong>${A.fmt(f.ppd, 2)}</strong></td>
        <td class="${f.parpd >= 0 ? "pos" : "neg"}">${A.fmt(f.parpd, 2)}</td>
        <td>${cell("QB")}</td>
        <td>${cell("RB")}</td>
        <td>${cell("WR")}</td>
        <td>${cell("TE")}</td>
        <td>${cell("K")}</td>
        <td>${cell("DST")}</td>
      </tr>`;
    }).join("");
    document.querySelectorAll("#ppd-tbl thead th[data-k]").forEach((th) => {
      const on = th.dataset.k === ppdKey;
      th.classList.toggle("on", on);
      th.classList.toggle("asc", on && ppdDir > 0);
    });
  }

  function renderHeat() {
    const years = Object.keys(DATA.seasons || {}).sort();
    const rows = careerRows().slice().sort(defaultCmp);
    const head = `<tr><th></th><th>Team</th>${years.map((y) => `<th>${y}</th>`).join("")}</tr>`;
    const body = rows.map((f) => {
      const cells = years.map((y) => {
        const d = f.finishes[y];
        if (!d || !d.rank) return `<td class="fin-cell fin-none"></td>`;
        const cls = d.rank === 1 ? "fin-1" : d.rank === 2 ? "fin-2" : d.rank === 3 ? "fin-3"
          : d.sacko ? "fin-sack" : d.po ? "fin-po" : "fin-mid";
        return `<td class="fin-cell ${cls}">${d.rank}</td>`;
      }).join("");
      return `<tr><td></td><td>${teamCell(f)}</td>${cells}</tr>`;
    }).join("");
    $("finish-heat").innerHTML = `<table class="tbl finish-tbl"><thead>${head}</thead><tbody>${body}</tbody></table>`;
  }

  function renderBooks() {
    const books = rolled.seasonBooks;
    const pick = (key, dir) => {
      const s = books.slice().sort((a, b) => (a[key] - b[key]) * dir);
      return s[0];
    };
    const items = [
      { k: "Highest PF", row: pick("pf", -1), fmt: (r) => A.fmt(r.pf, 1) + " pts" },
      { k: "Luckiest", row: pick("luck", -1), fmt: (r) => (r.luck >= 0 ? "+" : "") + A.fmt(r.luck, 2) + " wins" },
      { k: "Unluckiest", row: pick("luck", 1), fmt: (r) => (r.luck >= 0 ? "+" : "") + A.fmt(r.luck, 2) + " wins" },
      { k: "Best all-play", row: pick("allW", -1), fmt: (r) => r.allW + " AP wins" },
      { k: "Hottest week", row: pick("maxWeek", -1), fmt: (r) => A.fmt(r.maxWeek, 1) + " pts" },
      { k: "Most Moves", row: pick("moves", -1), fmt: (r) => (r.moves == null ? "—" : r.moves + " moves") },
      { k: "Most Trades", row: pick("trades", -1), fmt: (r) => (r.trades == null ? "—" : r.trades + " trades") },
      { k: "Most Activates", row: pick("moveToActive", -1), fmt: (r) => (r.moveToActive == null ? "—" : r.moveToActive + " activates") },
    ].filter((x) => x.row && (
      (x.k !== "Most Moves" || x.row.moves != null) &&
      (x.k !== "Most Trades" || x.row.trades != null) &&
      (x.k !== "Most Activates" || x.row.moveToActive != null)
    ));
    $("record-book").innerHTML = items.map((it) => {
      const r = it.row;
      const ft = A.franchiseTeam(r.owner);
      const name = (ft && ft.name) || A.franchiseName(r.owner) || NAME[r.owner] || r.name;
      return `<div class="book-card">
        <div class="own">${esc(it.k)}</div>
        <div class="book-val">${esc(it.fmt(r))}</div>
        <div class="team-cell">${A.logoHTML(ft || { name, logo: r.logo }, "mini")}<div><strong>${esc(name)}</strong><div class="own">${r.year}</div></div></div>
      </div>`;
    }).join("");
  }

  function renderBars() {
    const titled = careerRows().filter((f) => f.titles > 0)
      .slice().sort((a, b) => (b.titles - a.titles) || (b.winPct - a.winPct));
    const max = (titled[0] && titled[0].titles) || 1;
    $("title-bars").innerHTML = titled.map((f) => `
      <div class="hist-bar">
        ${A.logoHTML({ name: f.name, logo: f.logo }, "mini")}
        <div class="hist-bar-lab">${esc(f.name)}</div>
        <div class="hist-bar-track"><div class="hist-bar-fill" style="width:${(f.titles / max) * 100}%"></div></div>
        <div class="hist-bar-n">${f.titles}</div>
      </div>`).join("");
  }

  function renderTimeline() {
    $("timeline").innerHTML = (DATA.timeline || []).map((t) => `
      <div class="tl-card">
        <div class="tl-year">${t.year}</div>
        <div class="tl-team">🏆 ${esc(t.team)}</div>
        <div class="tl-own">${esc(t.record)}</div>
      </div>`).join("");
  }

  function renderH2H() {
    const owners = (DATA.activeOwners || []).slice().sort((a, b) => {
      const an = NAME[canon(a)] || "";
      const bn = NAME[canon(b)] || "";
      return an.localeCompare(bn);
    });
    const recMap = {};
    (DATA.h2h || []).forEach((r) => {
      recMap[r.a + "|" + r.b] = [r.aW, r.bW];
      recMap[r.b + "|" + r.a] = [r.bW, r.aW];
    });
    const lab = (id) => shortTeam(NAME[canon(id)] || id);
    const head = "<tr><th></th>" + owners.map((o) => `<th>${esc(lab(o))}</th>`).join("") + "</tr>";
    const body = owners.map((a) => {
      const cells = owners.map((b) => {
        if (a === b) return `<td class="h2h-self"></td>`;
        const rec = recMap[a + "|" + b];
        if (!rec) return "<td>—</td>";
        const cls = rec[0] > rec[1] ? "pos" : rec[0] < rec[1] ? "neg" : "";
        return `<td class="${cls}">${rec[0]}–${rec[1]}</td>`;
      }).join("");
      return `<tr><th>${esc(lab(a))}</th>${cells}</tr>`;
    }).join("");
    $("h2h-tbl").innerHTML = head + body;
  }

  function bindSort(tableId, getKey, setKey, getDir, setDir, render) {
    document.querySelectorAll(tableId + " thead th[data-k]").forEach((th) => {
      th.addEventListener("click", () => {
        const k = th.dataset.k;
        if (getKey() === k) setDir(getDir() * -1);
        else {
          setKey(k);
          setDir(k === "name" || k === "bestFinish" || k === "minScore" || k === "rank" || k === "firstYear" || k === "lastYear" || k === "lowPf" ? 1 : -1);
        }
        render();
      });
    });
  }

  function latestFinished() {
    const ys = (A.years() || []).filter((y) => y >= 2014 && y <= 2025).sort((a, b) => b - a);
    return ys[0] || 2025;
  }
  function parseSeasonParam(raw) {
    if (raw == null || raw === "" || String(raw).toLowerCase() === "all") return null;
    const y = +raw;
    if (!y || y < 2014 || y > 2025) return null;
    if ((A.years() || []).indexOf(y) < 0) return null;
    return y;
  }
  const qsYear = new URLSearchParams(location.search).get("year");
  let pickedYear = parseSeasonParam(qsYear);
  let seasonYear = A.seasonScope(pickedYear).year;
  let squad = A.squadFromURL();
  let standKey = "rank";
  let standDir = 1;

  const STAND_KEYS = {
    name: (r) => r.name || "",
    rank: (r) => (r.rank == null ? 99 : r.rank),
    wins: (r) => r.wins || 0,
    pf: (r) => r.pf || 0,
    pa: (r) => r.pa || 0,
    allW: (r) => r.allW || 0,
    moves: (r) => (r.moves == null ? -1 : r.moves),
  };

  function seasonStandRows(y) {
    return ((DATA.seasons[String(y)] || {}).teams || []).filter((t) => {
      return franchisePlayedSeason(canon(t.owner), y);
    }).map((t) => {
      const oid = canon(t.owner);
      const name = A.franchiseName(oid) || NAME[oid] || "";
      const logo = A.franchiseLogo(oid) || t.logo || "";
      return {
        owner: oid,
        name: name,
        logo: logo,
        tid: t.id,
        rank: t.finalRank || null,
        wins: t.wins || 0,
        losses: t.losses || 0,
        ties: t.ties || 0,
        pf: t.pf || 0,
        pa: t.pa || 0,
        allW: t.allplayW || 0,
        allL: t.allplayL || 0,
        moves: movesCount(y, t.id),
      };
    });
  }

  function renderSeasonStandings() {
    const tb = document.querySelector("#season-tbl tbody");
    if (!tb) return;
    function careerStandRows() {
      const by = {};
      Object.keys(DATA.seasons || {}).forEach((ys) => {
        const year = +ys;
        if (year < 2014 || year > 2025) return;
        ((DATA.seasons[ys] || {}).teams || []).forEach((t) => {
          const oid = canon(t.owner);
          if (!oid) return;
          if (!franchisePlayedSeason(oid, year)) return;
          if (!by[oid]) {
            by[oid] = { owner: oid, name: "", logo: "", tid: t.id, rank: null, wins: 0, losses: 0, ties: 0, pf: 0, pa: 0, allW: 0, allL: 0, moves: 0 };
          }
          const r = by[oid];
          r.name = A.franchiseName(oid) || (typeof NAME !== "undefined" && NAME[oid]) || t.name || r.name;
          r.logo = A.franchiseLogo(oid) || t.logo || r.logo;
          r.wins += t.wins || 0;
          r.losses += t.losses || 0;
          r.ties += t.ties || 0;
          r.pf += t.pf || 0;
          r.pa += t.pa || 0;
          r.allW += t.allplayW || 0;
          r.allL += t.allplayL || 0;
          const mv = movesCount(year, t.id);
          if (mv != null) r.moves += mv;
        });
      });
      return Object.values(by).sort((a, b) => (b.allW - a.allW) || (a.allL - b.allL)).map((r, i) => { r.rank = i + 1; return r; });
    }
    const rawRows = (pickedYear == null ? careerStandRows() : seasonStandRows(seasonYear));
    const rows = rawRows.filter((r) => !squad || A.canon(r.owner) === A.canon(squad)).slice().sort((a, b) => {
      const fn = STAND_KEYS[standKey];
      const av = fn ? fn(a) : 0;
      const bv = fn ? fn(b) : 0;
      let d;
      if (typeof av === "string") d = av.localeCompare(bv) * standDir;
      else d = (av - bv) * standDir;
      if (d) return d;
      return (a.rank || 99) - (b.rank || 99);
    });
    tb.innerHTML = rows.map((r) => {
      const rec = (r.wins || 0) + "-" + (r.losses || 0) + (r.ties ? "-" + r.ties : "");
      const mv = r.moves == null ? "—" : r.moves;
      const pillCls = r.rank === 1 ? "gold" : r.rank === 2 ? "slv" : r.rank === 3 ? "brz" : "";
      return `<tr>
        <td>${r.rank ? `<span class="rank-pill ${pillCls}">${r.rank}</span>` : "—"}</td>
        <td>${teamCell(r)}</td>
        <td><strong>${rec}</strong></td>
        <td>${A.fmt(r.pf, 1)}</td>
        <td>${A.fmt(r.pa, 1)}</td>
        <td>${r.allW}-${r.allL}</td>
        <td>${mv}</td>
      </tr>`;
    }).join("");
    document.querySelectorAll("#season-tbl thead th").forEach((th) => {
      th.classList.toggle("on", th.dataset.k === standKey);
      th.classList.toggle("asc", th.dataset.k === standKey && standDir > 0);
    });
    const sub = $("season-sub");
    if (sub) {
      sub.textContent = pickedYear == null
        ? "All · career All-Play 2014–2025 · current franchise names"
        : seasonYear + " · ESPN Moves · current franchise names";
    }
  }


  let txnKey = "acq";
  let txnDir = -1;

  const TXN_KEYS = {
    name: (r) => r.name || "",
    acq: (r) => (r.acq == null ? -1 : r.acq),
    drops: (r) => (r.drops == null ? -1 : r.drops),
    trades: (r) => (r.trades == null ? -1 : r.trades),
    activate: (r) => (r.activate == null ? -1 : r.activate),
    ir: (r) => (r.ir == null ? -1 : r.ir),
    misc: (r) => (r.misc == null ? -1 : r.misc),
  };

  function seasonTxnRows(y) {
    return ((DATA.seasons[String(y)] || {}).teams || []).filter((t) => {
      return franchisePlayedSeason(canon(t.owner), y);
    }).map((t) => {
      const oid = canon(t.owner);
      const bag = movesBag(y, t.id) || {};
      return {
        owner: oid,
        name: A.franchiseName(oid) || NAME[oid] || "",
        logo: A.franchiseLogo(oid) || t.logo || "",
        tid: t.id,
        acq: bag.moves != null ? Number(bag.moves) : null,
        drops: bag.drops != null ? Number(bag.drops) : null,
        trades: bag.trades != null ? Number(bag.trades) : null,
        activate: bag.moveToActive != null ? Number(bag.moveToActive) : null,
        ir: bag.ir != null ? Number(bag.ir) : null,
        misc: bag.misc != null ? Number(bag.misc) : null,
        byWeek: bag.byWeek || {},
      };
    });
  }

  function sortTxnRows(rows) {
    return rows.slice().sort((a, b) => {
      const fn = TXN_KEYS[txnKey];
      const av = fn ? fn(a) : 0;
      const bv = fn ? fn(b) : 0;
      let d;
      if (typeof av === "string") d = av.localeCompare(bv) * txnDir;
      else d = (av - bv) * txnDir;
      if (d) return d;
      return String(a.name || "").localeCompare(String(b.name || ""));
    });
  }

  function dash(v) {
    return v == null ? "—" : v;
  }

  function renderTxnCounter() {
    const tb = document.querySelector("#txn-tbl tbody");
    if (!tb) return;
    if (seasonYear == null) {
      const sub = $("txn-sub");
      if (sub) sub.textContent = "All · pick a season";
      tb.innerHTML = `<tr><td colspan="7"><div class="notice">Pick a season.</div></td></tr>`;
      return;
    }
    const rows = sortTxnRows(seasonTxnRows(seasonYear));
    tb.innerHTML = rows.map((r) => `<tr>
        <td>${teamCell(r)}</td>
        <td>${dash(r.acq)}</td>
        <td>${dash(r.drops)}</td>
        <td>${dash(r.trades)}</td>
        <td>${dash(r.activate)}</td>
        <td>${dash(r.ir)}</td>
        <td>${dash(r.misc)}</td>
      </tr>`).join("");
    document.querySelectorAll("#txn-tbl thead th").forEach((th) => {
      th.classList.toggle("on", th.dataset.k === txnKey);
      th.classList.toggle("asc", th.dataset.k === txnKey && txnDir > 0);
    });
  }

  function weekKeysFor(rows) {
    const set = {};
    rows.forEach((r) => {
      Object.keys(r.byWeek || {}).forEach((k) => { set[k] = 1; });
    });
    return Object.keys(set).sort((a, b) => Number(a) - Number(b));
  }

  function renderAddsByWeek() {
    const tbl = $("week-acq-tbl");
    if (!tbl) return;
    if (seasonYear == null) {
      tbl.innerHTML = `<tbody><tr><td><div class="notice">Pick a season.</div></td></tr></tbody>`;
      return;
    }
    const rows = sortTxnRows(seasonTxnRows(seasonYear));
    const weeks = weekKeysFor(rows);
    const head = `<tr><th>Team</th>${weeks.map((w) => `<th>${esc(w)}</th>`).join("")}</tr>`;
    const body = rows.map((r) => {
      const cells = weeks.map((w) => {
        const raw = (r.byWeek || {})[w];
        const n = raw == null ? 0 : Number(raw);
        if (!n) return `<td class="wk wk-empty"></td>`;
        return `<td class="wk wk-on">${n}</td>`;
      }).join("");
      return `<tr><td>${teamCell(r)}</td>${cells}</tr>`;
    }).join("");
    tbl.innerHTML = `<thead>${head}</thead><tbody>${body}</tbody>`;
  }

  function renderTxnAndWeeks() {
    renderTxnCounter();
    renderAddsByWeek();
  }


  const WAIVER_PRE2018 = "Waiver claims start in 2018. ESPN did not keep item logs before that.";
  let waiverWeek = null;
  let waiverKey = "pos";
  let waiverDir = 1;
  let waiverFaKey = "pos";
  let waiverFaDir = 1;

  const WAIVER_KEYS = {
    pos: (r) => (r.pos == null ? 999 : r.pos),
    name: (r) => r.name || "",
    claim: (r) => r.claim || "",
    result: (r) => r.result || "",
  };

  function claimsForYear(y) {
    const weeks = WAIVERS[String(y)] || {};
    const out = {};
    Object.keys(weeks).forEach((wk) => {
      out[String(wk)] = (weeks[wk] || []).slice();
    });
    return out;
  }

  function teamFromTid(y, tid) {
    const teams = ((DATA.seasons[String(y)] || {}).teams) || [];
    let hit = null;
    teams.forEach((t) => {
      if (t.id === tid || t.id === Number(tid) || String(t.id) === String(tid)) hit = t;
    });
    const oid = canon(hit && hit.owner);
    return {
      owner: oid,
      name: A.franchiseName(oid) || NAME[oid] || "",
      logo: A.franchiseLogo(oid) || "",
    };
  }

  function itemName(it) {
    if (!it) return "";
    return it.name || (it.pid != null ? "#" + it.pid : "");
  }

  function addItem(row) {
    return ((row && row.items) || []).find((it) => it.act === "ADD") || null;
  }

  function dropItem(row) {
    return ((row && row.items) || []).find((it) => it.act === "DROP") || null;
  }

  function waiverResultText(row) {
    const drop = dropItem(row);
    const dropNm = itemName(drop);
    const st = row.status || "";
    if (st === "EXECUTED") {
      return dropNm ? ("Added. Dropped " + dropNm) : "Added.";
    }
    if (st === "CANCELED") return "Canceled (user pulled the claim).";
    if (st === "FAILED_ROSTERLOCK") return "Unsuccessful. Roster locked.";
    if (st === "FAILED_PLAYERALREADYDROPPED" || st === "FAILED_INVALIDPLAYERSOURCE") {
      return "Unsuccessful. Player already added";
    }
    if (st === "FAILED_MATCHUPACQUISITIONLIMIT") return "Unsuccessful. Acquisition limit";
    if (st === "FAILED_ROSTERLIMIT") return "Unsuccessful. Roster limit";
    if (st === "FAILED_POSITIONLIMIT") return "Unsuccessful. Position limit";
    if (st === "FAILED_IRSLOT") return "Unsuccessful. IR slot";
    if (st === "PENDING") return "Pending.";
    if (st.indexOf("FAILED") === 0) {
      return "Unsuccessful. " + st.replace(/^FAILED_/, "").replace(/_/g, " ").toLowerCase();
    }
    return st || "—";
  }

  function resultClass(st) {
    if (st === "EXECUTED") return "ok";
    if (st === "CANCELED") return "cancel";
    if (st === "PENDING") return "pend";
    if (st && st.indexOf("FAILED") === 0) return "fail";
    return "";
  }

  function processDay(ms) {
    if (!ms) return "";
    const d = new Date(ms);
    const y = d.getFullYear();
    const m = d.getMonth();
    const day = d.getDate();
    return y + "-" + String(m + 1).padStart(2, "0") + "-" + String(day).padStart(2, "0");
  }

  function formatBatchDate(ms) {
    if (!ms) return "";
    return new Date(ms).toLocaleDateString("en-US", {
      weekday: "short", month: "short", day: "numeric", year: "numeric",
    });
  }

  function decorateClaim(row) {
    const team = teamFromTid(seasonYear, row.tid);
    const add = addItem(row);
    return {
      raw: row,
      pos: row._pos,
      owner: team.owner,
      name: team.name,
      logo: team.logo,
      claim: itemName(add),
      result: waiverResultText(row),
      status: row.status || "",
      type: row.type,
    };
  }

  function sortWaiverRows(rows, key, dir) {
    return rows.slice().sort((a, b) => {
      const fn = WAIVER_KEYS[key];
      const av = fn ? fn(a) : 0;
      const bv = fn ? fn(b) : 0;
      let d;
      if (typeof av === "string") d = av.localeCompare(bv) * dir;
      else d = (av - bv) * dir;
      if (d) return d;
      return (a.pos || 999) - (b.pos || 999);
    });
  }

  function waiverTableHTML(id, rows, key, dir) {
    const sorted = sortWaiverRows(rows, key, dir);
    const head = `<thead><tr>
      <th class="s${key === "pos" ? " on" + (dir > 0 ? " asc" : "") : ""}" data-k="pos"></th>
      <th class="s${key === "name" ? " on" + (dir > 0 ? " asc" : "") : ""}" data-k="name">Team</th>
      <th class="s${key === "claim" ? " on" + (dir > 0 ? " asc" : "") : ""}" data-k="claim">Claim</th>
      <th class="s${key === "result" ? " on" + (dir > 0 ? " asc" : "") : ""}" data-k="result">Result</th>
    </tr></thead>`;
    const body = sorted.map((r) => {
      const fa = r.type === "FREEAGENT" ? ` <span class="badge fa">FA</span>` : "";
      const cls = resultClass(r.status);
      const pos = r.pos == null ? "—" : r.pos;
      return `<tr>
        <td>${pos}</td>
        <td>${teamCell(r)}</td>
        <td><strong>${esc(r.claim)}</strong>${fa}</td>
        <td class="waiver-res ${cls}">${esc(r.result)}</td>
      </tr>`;
    }).join("");
    return `<div class="table-scroll"><table class="tbl" id="${id}">${head}<tbody>${body}</tbody></table></div>`;
  }

  function bindWaiverSort(tableId, isFa) {
    const el = document.getElementById(tableId);
    if (!el) return;
    el.querySelectorAll("thead th[data-k]").forEach((th) => {
      th.addEventListener("click", () => {
        const k = th.dataset.k;
        if (isFa) {
          if (waiverFaKey === k) waiverFaDir *= -1;
          else {
            waiverFaKey = k;
            waiverFaDir = k === "name" || k === "claim" || k === "pos" ? 1 : -1;
          }
        } else {
          if (waiverKey === k) waiverDir *= -1;
          else {
            waiverKey = k;
            waiverDir = k === "name" || k === "claim" || k === "pos" ? 1 : -1;
          }
        }
        renderWaiverReport();
      });
    });
  }

  function assignPos(rows) {
    const processed = rows.filter((r) => r.processDate);
    processed.sort((a, b) => (a.processDate - b.processDate) || String(a.id).localeCompare(String(b.id)));
    const posOf = {};
    processed.forEach((r, i) => { posOf[r.id] = i + 1; });
    return rows.map((r) => {
      const copy = Object.assign({}, r);
      copy._pos = posOf[r.id] || null;
      return copy;
    });
  }

  function renderWaiverWeekPicker(weeks) {
    const el = $("waiver-week-picker");
    const row = $("waiver-week-row");
    if (!el || !row) return;
    if (!weeks.length) {
      row.hidden = true;
      el.innerHTML = "";
      return;
    }
    row.hidden = false;
    if (waiverWeek == null || weeks.indexOf(waiverWeek) < 0) {
      waiverWeek = weeks[weeks.length - 1];
    }
    el.innerHTML = weeks.map((w) =>
      `<button class="season-chip${w === waiverWeek ? " on" : ""}" data-w="${w}">${w}</button>`
    ).join("");
    el.querySelectorAll("button").forEach((b) => {
      b.addEventListener("click", () => {
        waiverWeek = +b.dataset.w;
        renderWaiverReport();
      });
    });
  }

  function renderWaiverReport() {
    const body = $("waiver-body");
    const sub = $("waiver-sub");
    const row = $("waiver-week-row");
    if (!body) return;
    if (seasonYear == null) {
      if (row) row.hidden = true;
      if (sub) sub.textContent = "All · pick a season";
      body.innerHTML = `<div class="notice">Pick a season.</div>`;
      return;
    }
    if (seasonYear < 2018) {
      if (row) row.hidden = true;
      if (sub) sub.textContent = seasonYear + " · no ESPN item log";
      body.innerHTML = `<div class="notice">${esc(WAIVER_PRE2018)}</div>`;
      return;
    }
    const byWeek = claimsForYear(seasonYear);
    const weeks = Object.keys(byWeek).map(Number).sort((a, b) => a - b);
    renderWaiverWeekPicker(weeks);
    if (!weeks.length) {
      if (sub) sub.textContent = seasonYear + " · no waiver claims";
      body.innerHTML = `<div class="notice">No waiver or free-agent claims in ${seasonYear}.</div>`;
      return;
    }
    const raw = assignPos(byWeek[String(waiverWeek)] || []);
    const waivers = raw.filter((r) => r.type === "WAIVER").map(decorateClaim).filter((r) => franchisePlayedSeason(r.owner, seasonYear));
    const fas = raw.filter((r) => r.type === "FREEAGENT").map(decorateClaim).filter((r) => franchisePlayedSeason(r.owner, seasonYear));
    const processed = (byWeek[String(waiverWeek)] || []).filter((r) => r.processDate);
    const batchMs = processed.length ? processed[0].processDate : null;
    const batchLab = batchMs ? formatBatchDate(batchMs) : ("Week " + waiverWeek);
    if (sub) {
      sub.textContent = seasonYear + " · week " + waiverWeek + " · current franchise names";
    }
    let html = "";
    if (waivers.length) {
      html += `<div class="waiver-batch">${esc(batchLab)}</div>`;
      html += waiverTableHTML("waiver-tbl", waivers, waiverKey, waiverDir);
    } else {
      html += `<div class="notice">No waiver claims in week ${waiverWeek}.</div>`;
    }
    if (fas.length) {
      html += `<div class="waiver-batch">Free agents</div>`;
      html += waiverTableHTML("waiver-fa-tbl", fas, waiverFaKey, waiverFaDir);
    }
    body.innerHTML = html;
    bindWaiverSort("waiver-tbl", false);
    bindWaiverSort("waiver-fa-tbl", true);
  }


  const TX_PRE2018 = "Transaction log starts in 2018. ESPN did not keep item logs before that.";
  const VALUE_PRE2018 = "Waiver value starts in 2018. ESPN did not keep item logs before that.";
  const PAR_PRE2018 = "Custody PAR is unavailable for 2014–2017. Weekly rosters start in 2018, so this is not a grade of zero.";
  let txPos = "ALL";
  let txTeam = "ALL";
  let txAct = "ALL";
  let txQ = "";
  let txKey = "week";
  let txDir = 1;
  let txFiltersBound = false;
  let txTeamYear = null;

  function yearBundle(y) {
    const hit = ALL.find((b) => b.year === +y);
    return (hit && hit.data) || {};
  }

  let ageAsOf = A.today();
  let ageChart = null;
  let ageAsOfBound = false;
  let ageScatterRows = [];

  function isoDay(d) {
    const x = d || A.today();
    const m = String(x.getMonth() + 1).padStart(2, "0");
    const day = String(x.getDate()).padStart(2, "0");
    return x.getFullYear() + "-" + m + "-" + day;
  }

  function rosterPids(year, tid) {
    const pids = [];
    const seen = {};
    const add = (pid) => {
      if (pid == null || pid === "") return;
      const k = String(pid);
      if (seen[k]) return;
      seen[k] = true;
      pids.push(pid);
    };
    if (year >= 2018) {
      const yd = yearBundle(year);
      (yd.players || []).forEach((p) => {
        const weeks = p.wk || [];
        const on = weeks.some((w) => w && A.sameId(w[3], tid));
        if (on) add(p.pid);
      });
    } else {
      const bag = ((PRE2018_SEASON_ROSTERS[String(year)] || {})[String(tid)]) || [];
      bag.forEach((row) => add(row && row.pid));
    }
    return pids;
  }

  function meanAge(ages) {
    if (!ages.length) return null;
    return ages.reduce((a, b) => a + b, 0) / ages.length;
  }

  function franchiseYears(oid) {
    if (A.franchiseYears) return A.franchiseYears(oid) || [];
    const id = canon(oid);
    const f = (DATA.franchises || []).find((x) => canon(x.owner) === id);
    return (f && f.years) ? f.years.slice() : [];
  }

  function franchisePlayedSeason(oid, year) {
    if (A.franchisePlayedSeason) return A.franchisePlayedSeason(oid, year);
    const id = canon(oid);
    if (!id) return false;
    const years = franchiseYears(id);
    if (!years.length) return false;
    const y = +year;
    return years.indexOf(y) >= 0 || years.indexOf(String(y)) >= 0;
  }

  function ageScatterSeason() {
    if (pickedYear != null) return pickedYear;
    const y = (ageAsOf && typeof ageAsOf.getFullYear === "function")
      ? ageAsOf.getFullYear()
      : latestFinished();
    if (y < 2014) return 2014;
    if (y > 2025) return 2025;
    return y;
  }

  function seasonAgeRows(year, asOf) {
    const yd = yearBundle(year);
    const power = {};
    (yd.power || []).forEach((r) => {
      if (r && r.teamId != null) {
        power[r.teamId] = r.pwrPct;
        power[String(r.teamId)] = r.pwrPct;
      }
    });
    const teams = ((DATA.seasons[String(year)] || {}).teams || []).filter((t) => {
      const oid = A.canon(t.owner);
      return franchisePlayedSeason(oid, year);
    });
    return teams.map((t) => {
      const oid = A.canon(t.owner);
      const pids = rosterPids(year, t.id);
      const ages = [];
      pids.forEach((pid) => {
        const rec = A.playerBio(pid, year, asOf);
        const birth = rec && rec.birth;
        const live = birth ? A.ageOn(birth, asOf) : null;
        const age = live && live.decimal != null ? live.decimal : (rec && rec.age);
        if (age != null && Number.isFinite(age)) ages.push(age);
      });
      const avg = meanAge(ages);
      const pwr = power[t.id] != null ? power[t.id] : power[String(t.id)];
      return {
        tid: t.id,
        owner: oid,
        name: A.franchiseName(oid) || "—",
        logo: A.franchiseLogo(oid) || "",
        n: ages.length,
        mean: avg,
        pwr: (pwr == null || Number.isNaN(Number(pwr))) ? null : Number(pwr),
      };
    }).filter((r) => r.mean != null && Number.isFinite(r.mean));
  }

  function bindAgeAsOf() {
    const el = $("age-asof");
    if (!el || ageAsOfBound) return;
    ageAsOfBound = true;
    el.value = isoDay(ageAsOf);
    el.addEventListener("change", () => {
      if (el.value) {
        const parts = el.value.split("-");
        ageAsOf = new Date(+parts[0], +parts[1] - 1, +parts[2]);
      } else ageAsOf = A.today();
      renderAgeScatter();
    });
  }

  function ageChip(tag, row, cls) {
    if (!row) {
      return `<div class="champ-spot ${cls}"><div><div class="tag">${esc(tag)}</div><div class="rec">unavailable</div></div></div>`;
    }
    const href = "teams.html?squad=" + encodeURIComponent(row.owner);
    const pwr = row.pwr == null ? "—" : A.fmt(row.pwr, 1) + "%";
    return `<div class="champ-spot ${cls}">
      ${A.logoHTML({ name: row.name, logo: row.logo }, "avatar")}
      <div>
        <div class="tag">${esc(tag)}</div>
        <div class="nm"><a class="hist-name" href="${href}">${esc(row.name)}</a></div>
        <div class="rec">${A.fmt(row.mean, 1)} yrs · ${row.n} rostered · PWR% ${pwr}</div>
      </div>
    </div>`;
  }

  const ageLabelPlugin = {
    id: "ageScatterLabels",
    afterDatasetsDraw: function (chart) {
      const meta = chart.getDatasetMeta(0);
      if (!meta || !meta.data) return;
      const ctx = chart.ctx;
      const C = A.C;
      ctx.save();
      ctx.fillStyle = C.ink;
      ctx.font = '10px "Avenir Next","Segoe UI",sans-serif';
      ctx.textAlign = "center";
      ctx.textBaseline = "bottom";
      ageScatterRows.forEach((r, i) => {
        const pt = meta.data[i];
        if (!pt) return;
        ctx.fillText(A.shortTeam(r.owner) || r.name, pt.x, pt.y - 7);
      });
      ctx.restore();
    },
  };

  function renderAgeScatter() {
    bindAgeAsOf();
    const chips = $("age-squads");
    const sub = $("age-scatter-sub");
    const canvas = $("age-scatter-chart");
    const empty = $("age-scatter-empty");
    const wrap = $("age-scatter-wrap");
    if (!chips || !canvas) return;

    const scatterYear = ageScatterSeason();
    const rows = seasonAgeRows(scatterYear, ageAsOf);
    const same = isoDay(ageAsOf) === isoDay(A.today());
    if (sub) {
      sub.textContent = rows.length
        ? (scatterYear + " · live roster age vs Power Win % · "
          + (same ? "as of today · updates at midnight" : "as of " + isoDay(ageAsOf))
          + " · current franchise names")
        : (scatterYear + " · roster age unavailable");
    }

    if (!rows.length) {
      chips.innerHTML = "";
      if (empty) {
        empty.hidden = false;
        empty.textContent = scatterYear < 2018
          ? scatterYear + " · no snapshot/draft roster ages"
          : scatterYear + " · no weekly roster ages";
      }
      if (wrap) wrap.hidden = true;
      if (ageChart) { ageChart.destroy(); ageChart = null; }
      return;
    }
    if (empty) empty.hidden = true;
    if (wrap) wrap.hidden = false;

    const ranked = rows.slice().sort((a, b) => a.mean - b.mean);
    const young = ranked[0];
    const old = ranked[ranked.length - 1];
    chips.innerHTML = ageChip("Youngest team", young, "young") + ageChip("Oldest team", old, "old");

    const scatterRows = rows.filter((r) => r.pwr != null && Number.isFinite(r.pwr));
    ageScatterRows = scatterRows;
    if (typeof Chart === "undefined") return;
    A.chartDefaults(Chart);
    if (ageChart) { ageChart.destroy(); ageChart = null; }
    const C = A.C;
    ageChart = new Chart(canvas, {
      type: "scatter",
      data: {
        datasets: [{
          label: "Age vs Power",
          data: scatterRows.map((r) => ({ x: r.mean, y: r.pwr })),
          backgroundColor: scatterRows.map((r) => {
            if (r.owner === old.owner) return C.orange;
            if (r.owner === young.owner) return C.ice;
            return C.blue + "cc";
          }),
          borderColor: scatterRows.map((r) => {
            if (r.owner === old.owner) return C.orange;
            if (r.owner === young.owner) return C.ice;
            return C.blue;
          }),
          pointRadius: 6,
          pointHoverRadius: 8,
        }],
      },
      options: {
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: (c) => {
                const r = scatterRows[c.dataIndex];
                if (!r) return "";
                return r.name + " · " + A.fmt(r.mean, 1) + " yrs · PWR% " + A.fmt(r.pwr, 1);
              },
            },
          },
        },
        scales: {
          x: {
            grid: { color: C.grid },
            border: { display: false },
            title: { display: true, text: "mean roster age" },
          },
          y: {
            grid: { color: C.grid },
            border: { display: false },
            title: { display: true, text: "Power Win %" },
          },
        },
      },
      plugins: [ageLabelPlugin],
    });
  }


  function pmetaOf(yd, pid) {
    const bag = (yd && yd.pmeta) || {};
    const v = bag[String(pid)] || bag[pid];
    if (!Array.isArray(v) || !v.length) return { name: "", pos: "", nfl: "" };
    return { name: v[0] || "", pos: v[1] || "", nfl: v[2] || "" };
  }

  function normPos(pos) {
    if (!pos) return "";
    const p = String(pos).toUpperCase();
    if (p === "D/ST" || p === "DEF" || p === "DST") return "DST";
    return p;
  }

  function playerLabel(it, yd) {
    const meta = pmetaOf(yd, it && it.pid);
    const name = (it && it.name) || meta.name || (it && it.pid != null ? "#" + it.pid : "");
    const pos = normPos((it && it.pos) || meta.pos);
    const nfl = (it && it.nfl) || meta.nfl || "";
    const extra = [pos, nfl].filter(Boolean).join(" ");
    return extra ? (name + " " + extra) : name;
  }

  function shortDate(ms) {
    if (!ms) return "";
    return new Date(ms).toLocaleDateString("en-US", { month: "short", day: "numeric" });
  }

  function claimAction(row) {
    const st = row.status || "";
    if (st === "CANCELED" || (st && st.indexOf("FAILED") === 0)) return "failed";
    if (row.type === "FREEAGENT") return "fa";
    if (row.type === "WAIVER") return "waiver";
    return "other";
  }

  function claimIcon(row) {
    const st = row.status || "";
    if (st === "CANCELED" || (st && st.indexOf("FAILED") === 0)) return "✕";
    if (row.type === "FREEAGENT") return "A";
    if (row.type === "WAIVER") return "W";
    return "D";
  }

  function claimPill(row) {
    const st = row.status || "";
    if (st === "CANCELED") return "Canceled";
    if (st && st.indexOf("FAILED") === 0) return "Failed";
    if (row.type === "FREEAGENT") return "Free agent";
    if (row.type === "WAIVER") return "Claim";
    return st || "—";
  }

  function claimDetail(row, yd) {
    const add = addItem(row);
    const drop = dropItem(row);
    const parts = [];
    if (add) parts.push("Added " + playerLabel(add, yd));
    if (drop) parts.push("Dropped " + playerLabel(drop, yd));
    return parts.join(" · ") || "—";
  }

  function claimPositions(row, yd) {
    const out = [];
    ((row && row.items) || []).forEach((it) => {
      const pos = normPos((it && it.pos) || pmetaOf(yd, it.pid).pos);
      if (pos) out.push(pos);
    });
    return out;
  }

  function buildClaimRows(y) {
    const yd = yearBundle(y);
    const weeks = claimsForYear(y);
    const rows = [];
    Object.keys(weeks).forEach((wk) => {
      (weeks[wk] || []).forEach((raw) => {
        const team = teamFromTid(y, raw.tid);
        const act = claimAction(raw);
        const detail = claimDetail(raw, yd);
        rows.push({
          kind: "claim",
          week: raw.wk != null ? raw.wk : +wk,
          date: raw.processDate || raw.date || 0,
          owner: team.owner,
          name: team.name,
          logo: team.logo,
          owners: team.owner ? [team.owner] : [],
          detail: detail,
          positions: claimPositions(raw, yd),
          pill: claimPill(raw),
          icon: claimIcon(raw),
          action: act,
          bid: raw.bid || 0,
          status: raw.status || "",
          type: raw.type,
          gold: act === "waiver" && raw.status === "EXECUTED",
          search: [team.name, detail, claimPill(raw), "WEEK " + (raw.wk != null ? raw.wk : wk)].join(" ").toLowerCase(),
        });
      });
    });
    return rows;
  }

  function buildTradeRows(y) {
    const yd = yearBundle(y);
    return (yd.trades || []).map((tr) => {
      const sides = tr.sides || [];
      const teams = sides.map((s) => teamFromTid(y, s.tid));
      const players = [];
      const parts = sides.map((s) => {
        const tm = teamFromTid(y, s.tid);
        const got = (s.got || []).map((p) => {
          players.push(p);
          return playerLabel(p, yd);
        });
        return shortTeam(tm.name) + " get " + (got.join(", ") || "—");
      });
      const owners = teams.map((t) => t.owner).filter(Boolean);
      const name = teams.map((t) => t.name).filter(Boolean).join(" / ");
      const detail = parts.join(" · ");
      return {
        kind: "trade",
        week: tr.wk,
        date: tr.date || 0,
        owner: owners[0] || "",
        name: name,
        logo: (teams[0] && teams[0].logo) || "",
        teams: teams,
        owners: owners,
        detail: detail,
        positions: players.map((p) => normPos(p.pos || pmetaOf(yd, p.pid).pos)).filter(Boolean),
        pill: "Trade",
        icon: "T",
        action: "trade",
        bid: 0,
        gold: false,
        search: (name + " " + detail + " trade week " + tr.wk).toLowerCase(),
      };
    });
  }

  function seasonTxRows(y) {
    return buildClaimRows(y).concat(buildTradeRows(y)).filter((r) => {
      const owners = r.owners || (r.owner ? [r.owner] : []);
      return owners.some((oid) => franchisePlayedSeason(oid, y));
    });
  }

  function franchiseOptions() {
    const all = ROWS.slice().sort((a, b) => String(a.name).localeCompare(String(b.name)));
    if (seasonYear == null) return all;
    return all.filter((f) => franchisePlayedSeason(f.owner, seasonYear));
  }

  function bindTxFilters() {
    if (txFiltersBound) return;
    const pos = $("tx-pos");
    const team = $("tx-team");
    const act = $("tx-act");
    const q = $("tx-q");
    if (!pos || !team || !act) return;
    pos.addEventListener("change", () => { txPos = pos.value; renderTxLog(); });
    team.addEventListener("change", () => { txTeam = team.value; renderTxLog(); });
    act.addEventListener("change", () => { txAct = act.value; renderTxLog(); });
    if (q) q.addEventListener("input", () => { txQ = q.value || ""; renderTxLog(); });
    document.querySelectorAll("#tx-log-tbl thead th[data-k]").forEach((th) => {
      th.addEventListener("click", () => {
        const k = th.dataset.k;
        if (txKey === k) txDir *= -1;
        else {
          txKey = k;
          txDir = (k === "week" || k === "name" || k === "detail") ? 1 : -1;
        }
        renderTxLog();
      });
    });
    txFiltersBound = true;
  }

  function fillTxTeamFilter() {
    const team = $("tx-team");
    if (!team) return;
    if (txTeamYear === seasonYear && team.options.length > 1) return;
    const cur = txTeam;
    const opts = franchiseOptions();
    team.innerHTML = `<option value="ALL">All</option>` + opts.map((f) =>
      `<option value="${esc(f.owner)}">${esc(f.name)}</option>`
    ).join("");
    if (opts.some((f) => f.owner === cur)) team.value = cur;
    else {
      txTeam = "ALL";
      team.value = "ALL";
    }
    txTeamYear = seasonYear;
  }

  function filterTxRows(rows) {
    const q = String(txQ || "").trim().toLowerCase();
    return rows.filter((r) => {
      if (txPos !== "ALL" && (r.positions || []).indexOf(txPos) < 0) return false;
      if (txTeam !== "ALL" && (r.owners || []).indexOf(txTeam) < 0) return false;
      if (txAct !== "ALL" && r.action !== txAct) return false;
      if (q && (r.search || "").indexOf(q) < 0) return false;
      return true;
    });
  }

  function sortTxRows(rows) {
    const key = txKey;
    return rows.slice().sort((a, b) => {
      let av, bv;
      if (key === "week") { av = a.week || 0; bv = b.week || 0; }
      else if (key === "name") { av = a.name || ""; bv = b.name || ""; }
      else if (key === "detail") { av = a.detail || ""; bv = b.detail || ""; }
      else if (key === "pill") { av = a.pill || ""; bv = b.pill || ""; }
      else { av = a.date || 0; bv = b.date || 0; }
      let d;
      if (typeof av === "string") d = av.localeCompare(bv) * txDir;
      else d = (av - bv) * txDir;
      if (d) return d;
      return (a.date || 0) - (b.date || 0) || (a.week || 0) - (b.week || 0);
    });
  }

  function txTeamCell(r) {
    if (r.kind === "trade" && r.teams && r.teams.length > 1) {
      return `<div class="team-cell tx-dual">${r.teams.map((t) =>
        `${A.logoHTML({ name: t.name, logo: t.logo }, "mini")}<span>${esc(t.name)}</span>`
      ).join("<span class='tx-vs'>/</span>")}</div>`;
    }
    return teamCell(r);
  }

  function renderTxLog() {
    bindTxFilters();
    fillTxTeamFilter();
    const tb = document.querySelector("#tx-log-tbl tbody");
    const sub = $("tx-log-sub");
    const filters = $("tx-log-filters");
    if (!tb) return;
    if (seasonYear == null) {
      if (filters) filters.hidden = true;
      if (sub) sub.textContent = "All · pick a season";
      tb.innerHTML = `<tr class="tx-empty"><td colspan="5"><div class="notice">Pick a season.</div></td></tr>`;
      return;
    }
    if (seasonYear < 2018) {
      if (filters) filters.hidden = true;
      if (sub) sub.textContent = seasonYear + " · no ESPN item log";
      tb.innerHTML = `<tr class="tx-empty"><td colspan="5"><div class="notice">${esc(TX_PRE2018)}</div></td></tr>`;
      return;
    }
    if (filters) filters.hidden = false;
    const all = seasonTxRows(seasonYear);
    const rows = sortTxRows(filterTxRows(all));
    if (sub) {
      sub.textContent = seasonYear + " · " + rows.length + " of " + all.length + " · current franchise names";
    }
    if (!rows.length) {
      tb.innerHTML = `<tr class="tx-empty"><td colspan="5"><div class="notice">No transactions match.</div></td></tr>`;
    } else {
      tb.innerHTML = rows.map((r) => {
        const when = shortDate(r.date);
        const weekLab = when
          ? `<span class="tx-date">${esc(when)}</span><span class="tx-wk">WEEK ${r.week}</span>`
          : `<span class="tx-wk">WEEK ${r.week}</span>`;
        const icoCls = r.icon === "W" ? "w" : r.icon === "A" ? "a" : r.icon === "T" ? "t" : r.icon === "✕" ? "x" : "d";
        const pillCls = r.pill === "Claim" ? "claim" : r.pill === "Free agent" ? "fa" : r.pill === "Trade" ? "trade"
          : r.pill === "Failed" ? "fail" : r.pill === "Canceled" ? "cancel" : "";
        return `<tr class="${r.gold ? "tx-gold" : ""}">
          <td class="tx-week">${weekLab}</td>
          <td class="tx-ico-td"><span class="tx-ico ${icoCls}">${r.icon}</span></td>
          <td>${txTeamCell(r)}</td>
          <td class="tx-detail">${esc(r.detail)}</td>
          <td><span class="tx-pill ${pillCls}">${esc(r.pill)}</span></td>
        </tr>`;
      }).join("");
    }
    document.querySelectorAll("#tx-log-tbl thead th[data-k]").forEach((th) => {
      th.classList.toggle("on", th.dataset.k === txKey);
      th.classList.toggle("asc", th.dataset.k === txKey && txDir > 0);
    });
  }

  function rosterPtsMaps(yd) {
    const byTeamPid = {};
    const byPid = {};
    const weeks = (yd && yd.weeks) || {};
    Object.keys(weeks).forEach((wk) => {
      const w = +wk;
      (weeks[wk] || []).forEach((m) => {
        ["home", "away"].forEach((side) => {
          const s = m[side];
          if (!s) return;
          (s.roster || []).forEach((row) => {
            const pid = row[0];
            const pts = row[2] || 0;
            const tk = s.tid + "|" + pid;
            if (!byTeamPid[tk]) byTeamPid[tk] = [];
            byTeamPid[tk].push({ w: w, pts: pts });
            if (!byPid[pid]) byPid[pid] = [];
            byPid[pid].push({ w: w, tid: s.tid, pts: pts });
          });
        });
      });
    });
    return { byTeamPid, byPid };
  }

  function ptsAfterAdd(map, tid, pid, claimWk) {
    const rows = map[tid + "|" + pid] || [];
    let pts = 0, n = 0;
    rows.forEach((r) => {
      if (r.w > claimWk) { pts += r.pts; n += 1; }
    });
    return { pts: pts, n: n };
  }

  function ptsAfterDrop(byPid, pid, claimWk, notTid) {
    let pts = 0;
    (byPid[pid] || []).forEach((r) => {
      if (r.w > claimWk && r.tid !== notTid) pts += r.pts;
    });
    return pts;
  }

  function waiverValueRows(y) {
    const yd = yearBundle(y);
    const maps = rosterPtsMaps(yd);
    const out = [];
    const weeks = claimsForYear(y);
    Object.keys(weeks).forEach((wk) => {
      (weeks[wk] || []).forEach((raw) => {
        if (raw.status !== "EXECUTED") return;
        if (raw.type !== "WAIVER" && raw.type !== "FREEAGENT") return;
        const add = addItem(raw);
        if (!add) return;
        const drop = dropItem(raw);
        const team = teamFromTid(y, raw.tid);
        if (!franchisePlayedSeason(team.owner, y)) return;
        const after = ptsAfterAdd(maps.byTeamPid, raw.tid, add.pid, raw.wk);
        let gave = null;
        if (drop && drop.pid != null) {
          gave = ptsAfterDrop(maps.byPid, drop.pid, raw.wk, raw.tid);
        }
        out.push({
          owner: team.owner,
          name: team.name,
          logo: team.logo,
          addName: playerLabel(add, yd),
          dropName: drop ? playerLabel(drop, yd) : "",
          ptsAfter: after.pts,
          weeksOn: after.n,
          gave: gave,
          net: gave == null ? null : after.pts - gave,
          bid: raw.bid || 0,
          wk: raw.wk,
          type: raw.type,
        });
      });
    });
    return out;
  }

  function wvPtsCell(n) {
    if (n === 0) return `<span class="wv-pts wv-zero">0 pts</span>`;
    const cls = n > 0 ? "pos" : "neg";
    return `<span class="wv-pts ${cls}">${A.fmt(n, 1)}</span>`;
  }

  function wvAddRow(r) {
    const drop = r.dropName ? ` · Dropped ${esc(r.dropName)}` : "";
    return `<tr>
      <td>${teamCell(r)}</td>
      <td class="wv-detail">Added ${esc(r.addName)}${drop}</td>
      <td>${wvPtsCell(r.ptsAfter)}</td>
    </tr>`;
  }

  function renderWaiverValue() {
    const body = $("waiver-value-body");
    const sub = $("waiver-value-sub");
    if (!body) return;
    if (seasonYear == null) {
      if (sub) sub.textContent = "All · pick a season";
      body.innerHTML = `<div class="notice">Pick a season.</div>`;
      return;
    }
    if (seasonYear < 2018) {
      if (sub) sub.textContent = seasonYear + " · no ESPN item log";
      body.innerHTML = `<div class="notice">${esc(VALUE_PRE2018)}</div>`;
      return;
    }
    const rows = waiverValueRows(seasonYear);
    const top = rows.slice().sort((a, b) => (b.ptsAfter - a.ptsAfter) || (b.weeksOn - a.weeksOn)).slice(0, 10);
    const worst = rows.filter((r) => r.weeksOn >= 1)
      .slice().sort((a, b) => (a.ptsAfter - b.ptsAfter) || (a.weeksOn - b.weeksOn)).slice(0, 10);
    const byTeam = {};
    rows.forEach((r) => {
      const k = r.owner || String(r.name);
      if (!byTeam[k]) byTeam[k] = { owner: r.owner, name: r.name, logo: r.logo, pts: 0, n: 0 };
      byTeam[k].pts += r.ptsAfter;
      byTeam[k].n += 1;
    });
    const teams = Object.values(byTeam).sort((a, b) => (b.pts - a.pts) || String(a.name).localeCompare(String(b.name)));
    const maxBid = rows.reduce((m, r) => Math.max(m, r.bid || 0), 0);
    const faabOn = maxBid > 0;
    if (sub) {
      sub.textContent = seasonYear + " · points after the claim week · current franchise names"
        + (faabOn ? "" : " · FAAB columns appear when the league starts bidding.");
    }
    const topTbl = `<table class="tbl" id="wv-top-tbl"><thead><tr>
      <th>Team</th><th>Add / Drop</th><th>After</th>
    </tr></thead><tbody>${top.map(wvAddRow).join("") || `<tr><td colspan="3"><div class="notice">No executed adds.</div></td></tr>`}</tbody></table>`;
    const worstTbl = `<table class="tbl" id="wv-worst-tbl"><thead><tr>
      <th>Team</th><th>Add / Drop</th><th>After</th>
    </tr></thead><tbody>${worst.map(wvAddRow).join("") || `<tr><td colspan="3"><div class="notice">No rostered adds.</div></td></tr>`}</tbody></table>`;
    const teamTbl = `<table class="tbl" id="wv-team-tbl"><thead><tr>
      <th>Team</th><th>Adds</th><th>Pts after</th>
    </tr></thead><tbody>${teams.map((t) => `<tr>
      <td>${teamCell(t)}</td>
      <td>${t.n}</td>
      <td>${wvPtsCell(t.pts)}</td>
    </tr>`).join("")}</tbody></table>`;
    let faab = "";
    if (faabOn) {
      const spent = rows.reduce((s, r) => s + (r.bid || 0), 0);
      const nTeams = Math.max(1, teams.length);
      const valued = rows.filter((r) => r.bid > 0);
      const vps = valued.length ? valued.reduce((s, r) => s + r.ptsAfter, 0) / valued.reduce((s, r) => s + r.bid, 0) : 0;
      faab = `<div class="wv-faab">
        <div class="lab-chip"><b>$${A.fmt(spent)}</b><span>Total FAAB Spent</span></div>
        <div class="lab-chip"><b>$${A.fmt(spent / nTeams, 1)}</b><span>Avg FAAB</span></div>
        <div class="lab-chip"><b>${A.fmt(vps, 2)}</b><span>Value / $</span></div>
      </div>`;
    }
    body.innerHTML = `<div class="wv-grid">
      <div><div class="wv-h">Top adds</div><div class="table-scroll">${topTbl}</div></div>
      <div><div class="wv-h">Worst adds</div><div class="table-scroll">${worstTbl}</div></div>
    </div>
    <div class="wv-h">Team waiver points</div>
    <div class="table-scroll">${teamTbl}</div>${faab}`;
  }


  let parKey = "parTotal";
  let parDir = -1;
  const PAR_KEYS = {
    name: (r) => r.name || "",
    parTotal: (r) => r.parTotal || 0,
    parDrafted: (r) => r.parDrafted || 0,
    parTradedIn: (r) => r.parTradedIn || 0,
    parWaiver: (r) => r.parWaiver || 0,
    parFa: (r) => r.parFa || 0,
    parUnknown: (r) => r.parUnknown || 0,
  };

  function custodyParRows(y) {
    const yd = yearBundle(y);
    const c = yd && yd.custody;
    if (!c || c.grain !== "weekly" || !Array.isArray(c.teams)) return null;
    const owners = ownerByTid(y);
    return c.teams.map((row) => {
      const oid = owners[row.tid] || owners[Number(row.tid)] || owners[String(row.tid)];
      const ft = oid ? A.franchiseTeam(oid) : { owner: oid || "", name: "—", logo: "" };
      const drafted = Number(row.parDrafted) || 0;
      const traded = Number(row.parTradedIn) || 0;
      const waiver = Number(row.parWaiver) || 0;
      const fa = Number(row.parFa) || 0;
      const unk = Number(row.parUnknown) || 0;
      const total = row.parTotal != null ? Number(row.parTotal)
        : drafted + traded + waiver + fa + unk;
      return {
        owner: ft.owner || oid,
        name: ft.name || A.franchiseName(oid) || "—",
        logo: ft.logo || A.franchiseLogo(oid) || "",
        tid: row.tid,
        parTotal: total,
        parDrafted: drafted,
        parTradedIn: traded,
        parWaiver: waiver,
        parFa: fa,
        parUnknown: unk,
      };
    }).filter((r) => franchisePlayedSeason(r.owner, y));
  }

  function parTd(n, strong) {
    const v = Number(n) || 0;
    const cls = v > 0.05 ? "pos" : (v < -0.05 ? "neg" : "");
    const body = strong ? `<strong>${A.fmt(v, 1)}</strong>` : A.fmt(v, 1);
    return `<td class="${cls}">${body}</td>`;
  }

  function renderCustodyPar() {
    const sub = $("custody-par-sub");
    const tb = document.querySelector("#custody-par-tbl tbody");
    const unkTh = $("par-unknown-th");
    if (!tb) return;
    if (seasonYear == null) {
      if (sub) sub.textContent = "All · pick a season";
      if (unkTh) unkTh.hidden = true;
      tb.innerHTML = `<tr><td colspan="8"><div class="notice">Pick a season.</div></td></tr>`;
      return;
    }
    if (seasonYear < 2018) {
      if (sub) sub.textContent = seasonYear + " · unavailable · weekly rosters start in 2018";
      if (unkTh) unkTh.hidden = true;
      tb.innerHTML = `<tr><td colspan="8"><div class="notice">${esc(PAR_PRE2018)}</div></td></tr>`;
      return;
    }
    const rows = custodyParRows(seasonYear);
    if (!rows || !rows.length) {
      if (sub) sub.textContent = seasonYear + " · unavailable";
      if (unkTh) unkTh.hidden = true;
      tb.innerHTML = `<tr><td colspan="8"><div class="notice">${esc(PAR_PRE2018)}</div></td></tr>`;
      return;
    }
    const showUnk = rows.some((r) => Math.abs(r.parUnknown) > 0.05);
    if (unkTh) unkTh.hidden = !showUnk;
    if (sub) {
      sub.textContent = seasonYear
        + " · rostered-week PAR (started + benched) · the GM grade, not starter points"
        + " · Trade Alpha is not in the total (unavailable — no consensus ROS)";
    }
    const fn = PAR_KEYS[parKey] || PAR_KEYS.parTotal;
    rows.sort((a, b) => {
      const av = fn(a), bv = fn(b);
      if (typeof av === "string") return av.localeCompare(bv) * parDir;
      const d = ((av || 0) - (bv || 0)) * parDir;
      if (d) return d;
      return String(a.name).localeCompare(String(b.name));
    });
    tb.innerHTML = rows.map((r, i) => {
      const unkTd = showUnk ? parTd(r.parUnknown) : `<td hidden>${A.fmt(r.parUnknown, 1)}</td>`;
      return `<tr>
        <td>${pill(i)}</td>
        <td>${teamCell(r)}</td>
        ${parTd(r.parTotal, true)}
        ${parTd(r.parDrafted)}
        ${parTd(r.parTradedIn)}
        ${parTd(r.parWaiver)}
        ${parTd(r.parFa)}
        ${unkTd}
      </tr>`;
    }).join("");
    document.querySelectorAll("#custody-par-tbl thead th[data-k]").forEach((th) => {
      const on = th.dataset.k === parKey;
      th.classList.toggle("on", on);
      th.classList.toggle("asc", on && parDir > 0);
    });
  }

  function stampSeasonYear(y) {
    const u = new URL(location.href);
    if (y == null) u.searchParams.delete("year");
    else u.searchParams.set("year", y);
    history.replaceState(null, "", u.pathname.split("/").pop() + u.search + u.hash);
  }

  function applySeasonYear(y) {
    pickedYear = y;
    seasonYear = A.seasonScope(y).year;
    stampSeasonYear(y);
    bindYearSelect();
    renderSeasonStandings();
    renderTxnAndWeeks();
    renderWaiverReport();
    renderTxLog();
    renderWaiverValue();
    renderCustodyPar();
    renderAgeScatter();
    renderRace();
  }

  function bindYearSelect() {
    const el = $("year-picker");
    if (!el) return;
    if (pickedYear != null && squad && !A.franchisePlayedSeason(squad, pickedYear)) {
      squad = "";
      A.stampNav("");
    }
    const ylist = squad ? A.squadYears(squad) : A.years();
    A.seasonPicker(el, pickedYear, applySeasonYear, ylist);
    A.remountTeamSelect($("squad-picker"), squad, (s) => {
      squad = s || "";
      A.stampNav(squad);
      if (squad && pickedYear != null) {
        const ys = A.squadYears(squad) || [];
        if (!ys.length) applySeasonYear(null);
        else if (ys.indexOf(pickedYear) < 0) applySeasonYear(ys[0]);
        else applySeasonYear(pickedYear);
      } else {
        bindYearSelect();
        renderSeasonStandings();
        renderTxnAndWeeks();
        renderWaiverReport();
        renderTxLog();
        renderWaiverValue();
        renderCustodyPar();
        renderAgeScatter();
        renderRace();
      }
    }, pickedYear);
  }
  bindYearSelect();

  let raceChart = null;
  function renderRace() {
    const canvas = $("race-chart");
    const sub = $("race-sub");
    if (!canvas) return;
    if (seasonYear == null) {
      if (sub) sub.textContent = "All · pick a season";
      if (raceChart) { raceChart.destroy(); raceChart = null; }
      return;
    }
    const y = seasonYear;
    const s = DATA.seasons[String(y)] || { teams: [], regWeeks: [] };
    const top4 = (s.teams || []).filter((t) => franchisePlayedSeason(canon(t.owner), y)).slice().sort((a, b) => (a.finalRank || 99) - (b.finalRank || 99)).slice(0, 4);
    if (sub) sub.textContent = y + " · cumulative wins · top four finishers · current franchise names";
    if (typeof Chart === "undefined") return;
    if (!top4.length) {
      if (raceChart) { raceChart.destroy(); raceChart = null; }
      return;
    }
    const C = A.C;
    const colors = [C.blue, C.gold, C.blue2, C.ice];
    A.chartDefaults(Chart);
    if (raceChart) { raceChart.destroy(); raceChart = null; }
    raceChart = new Chart(canvas, {
      type: "line",
      data: {
        labels: (s.regWeeks || []).map((w) => "W" + w),
        datasets: top4.map((t, i) => {
          const oid = canon(t.owner);
          const name = A.franchiseName(oid) || t.name || "—";
          return {
            label: name.length > 16 ? name.slice(0, 15) + "…" : name,
            data: t.cumWins || [],
            borderColor: colors[i],
            backgroundColor: colors[i],
            borderWidth: 2,
            pointRadius: 3,
            pointBorderColor: "#12142e",
            pointBorderWidth: 1.5,
            tension: 0.2,
          };
        }),
      },
      options: {
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        plugins: { legend: { labels: { boxWidth: 10, boxHeight: 10, usePointStyle: true, pointStyle: "circle" } } },
        scales: {
          y: { grid: { color: C.grid }, border: { display: false }, ticks: { stepSize: 2 }, title: { display: true, text: "wins" } },
          x: { grid: { display: false }, border: { display: false } },
        },
      },
    });
  }

  let ngsKey = "routeYards";
  let ngsDir = -1;
  function ngsShare(x) {
    if (!x || x.share == null) return "—";
    return (Number(x.share) * 100).toFixed(1) + "%";
  }
  function renderNgs() {
    const tb = document.querySelector("#ngs-tbl tbody");
    if (!tb) return;
    const rows = (NGS_PROFILES.franchises || []).map((f) => ({
      owner: f.owner,
      name: A.franchiseName(f.owner) || f.name || "—",
      logo: A.franchiseLogo(f.owner) || "",
      routeYards: f.routeYards || 0,
      holeYards: f.holeYards || 0,
      topRoute: f.topRoute,
      topHole: f.topHole,
    }));
    const keyfn = {
      name: (r) => r.name || "",
      routeYards: (r) => r.routeYards || 0,
      topRoute: (r) => (r.topRoute && r.topRoute.yds) || 0,
      holeYards: (r) => r.holeYards || 0,
      topHole: (r) => (r.topHole && r.topHole.yds) || 0,
    }[ngsKey] || ((r) => r.routeYards || 0);
    rows.sort((a, b) => {
      const av = keyfn(a), bv = keyfn(b);
      const cmp = (typeof av === "string")
        ? String(av).localeCompare(String(bv))
        : ((av || 0) - (bv || 0));
      return ngsDir * cmp || String(a.name).localeCompare(String(b.name));
    });
    tb.innerHTML = rows.map((f, i) => {
      const tr = f.topRoute;
      const th = f.topHole;
      return `<tr>
        <td>${pill(i)}</td>
        <td>${teamCell(f)}</td>
        <td>${A.fmt(f.routeYards, 0)}</td>
        <td>${tr ? esc(tr.route) + " · " + ngsShare(tr) : "—"}</td>
        <td>${A.fmt(f.holeYards, 0)}</td>
        <td>${th ? esc(th.hole) + " · " + ngsShare(th) : "—"}</td>
      </tr>`;
    }).join("");
    document.querySelectorAll("#ngs-tbl thead th[data-k]").forEach((th) => {
      const on = th.dataset.k === ngsKey;
      th.classList.toggle("on", on);
      th.classList.toggle("asc", on && ngsDir > 0);
    });
  }


  let titleKey = "titles";
  let titleDir = -1;
  function renderTitles() {
    const tb = document.querySelector("#titles-tbl tbody");
    if (!tb) return;
    const rows = careerRows().slice().sort((a, b) => cmpWith(titleKey, titleDir, a, b));
    tb.innerHTML = rows.map((f, i) => `
      <tr>
        <td>${pill(i)}</td>
        <td>${teamCell(f)}</td>
        <td>${f.titles || 0}</td>
        <td>${f.runnerUps || 0}</td>
        <td>${f.thirds || 0}</td>
        <td>${f.scoreTitles || 0}</td>
        <td>${f.sackos || 0}</td>
        <td><strong>${f.combined == null ? 0 : f.combined}</strong></td>
      </tr>`).join("");
    document.querySelectorAll("#titles-tbl thead th[data-k]").forEach((th) => {
      const on = th.dataset.k === titleKey;
      th.classList.toggle("on", on);
      th.classList.toggle("asc", on && titleDir > 0);
    });
  }

  function ownerOfTid(year, tid) {
    const teams = ((DATA.seasons[String(year)] || {}).teams) || [];
    for (let i = 0; i < teams.length; i++) {
      const t = teams[i];
      if (t.id === tid || t.id === Number(tid) || String(t.id) === String(tid)) {
        return canon(t.owner);
      }
    }
    return "";
  }

  function computeWeeklyStreaks() {
    const seq = {};
    let nGames = 0;
    ALL.slice().sort((a, b) => a.year - b.year).forEach(({ year, data }) => {
      const weeks = (data && data.weeks) || {};
      Object.keys(weeks).map(Number).filter((w) => w > 0).sort((a, b) => a - b).forEach((wk) => {
        const bag = weeks[String(wk)] || weeks[wk] || [];
        bag.forEach((m) => {
          const h = m && m.home, a = m && m.away;
          if (!h || !a || h.pts == null || a.pts == null) return;
          const hp = Number(h.pts), ap = Number(a.pts);
          if (!Number.isFinite(hp) || !Number.isFinite(ap)) return;
          nGames += 1;
          const ho = ownerOfTid(year, h.tid);
          const ao = ownerOfTid(year, a.tid);
          const mark = (oid, res) => {
            if (!oid) return;
            if (!seq[oid]) seq[oid] = [];
            seq[oid].push({ year: year, week: wk, res: res });
          };
          if (hp > ap) { mark(ho, "W"); mark(ao, "L"); }
          else if (ap > hp) { mark(ao, "W"); mark(ho, "L"); }
          else { mark(ho, "T"); mark(ao, "T"); }
        });
      });
    });
    const wins = [], losses = [];
    Object.keys(seq).forEach((oid) => {
      let cur = null;
      const flush = () => {
        if (!cur || cur.len < 1) return;
        const row = {
          owner: oid,
          name: NAME[oid] || A.franchiseName(oid) || oid,
          logo: A.franchiseLogo(oid) || "",
          len: cur.len,
          start: cur.start,
          end: cur.end,
        };
        if (cur.res === "W") wins.push(row);
        else if (cur.res === "L") losses.push(row);
      };
      seq[oid].forEach((g) => {
        if (!cur || cur.res !== g.res || g.res === "T") {
          flush();
          cur = g.res === "T" ? null : { res: g.res, len: 1, start: g, end: g };
        } else {
          cur.len += 1;
          cur.end = g;
        }
      });
      flush();
    });
    wins.sort((a, b) => (b.len - a.len) || String(a.name).localeCompare(String(b.name)));
    losses.sort((a, b) => (b.len - a.len) || String(a.name).localeCompare(String(b.name)));
    return { wins: wins, losses: losses, have: nGames > 0 };
  }

  function streakSpan(s) {
    if (!s || !s.start) return "—";
    const a = s.start.year + " W" + s.start.week;
    const b = s.end.year + " W" + s.end.week;
    return a === b ? a : (a + " – " + b);
  }

  function renderStreaks() {
    const body = $("rb-streaks-body");
    const sub = $("rb-streaks-sub");
    if (!body) return;
    const st = computeWeeklyStreaks();
    if (!st.have) {
      if (sub) sub.textContent = "need weekly results";
      body.innerHTML = `<div class="notice">need weekly results</div>`;
      return;
    }
    if (sub) sub.textContent = "weekly matchup results · current franchise names";
    const block = (title, rows) => {
      const top = rows.slice(0, 10);
      const tr = top.map((r, i) => `<tr>
        <td>${pill(i)}</td>
        <td>${teamCell(r)}</td>
        <td><strong>${r.len}</strong></td>
        <td>${esc(streakSpan(r))}</td>
      </tr>`).join("") || `<tr><td colspan="4"><div class="notice">No streaks.</div></td></tr>`;
      return `<div class="rb-streak-col">
        <div class="rb-h">${esc(title)}</div>
        <div class="table-scroll"><table class="tbl">
          <thead><tr><th></th><th>Team</th><th>Streak</th><th>Span</th></tr></thead>
          <tbody>${tr}</tbody>
        </table></div>
      </div>`;
    };
    body.innerHTML = `<div class="rb-streak-grid">${block("Longest winning streaks", st.wins)}${block("Longest losing streaks", st.losses)}</div>`;
  }

  let teamRecKey = "highPf";
  let teamRecDir = -1;
  function renderTeamRecords() {
    const tb = document.querySelector("#rb-team-tbl tbody");
    if (!tb) return;
    const rows = careerRows().slice().sort((a, b) => cmpWith(teamRecKey, teamRecDir, a, b));
    tb.innerHTML = rows.map((f, i) => `<tr>
      <td>${pill(i)}</td>
      <td>${teamCell(f)}</td>
      <td>${A.fmt(f.highPf, 1)}</td>
      <td>${A.fmt(f.lowPf, 1)}</td>
      <td>${f.tenWins || 0}</td>
      <td>${f.playoffs || 0}</td>
      <td>${f.scoreTitles || 0}</td>
      <td>${f.titles || 0}</td>
    </tr>`).join("");
    document.querySelectorAll("#rb-team-tbl thead th[data-k]").forEach((th) => {
      const on = th.dataset.k === teamRecKey;
      th.classList.toggle("on", on);
      th.classList.toggle("asc", on && teamRecDir > 0);
    });
  }

  const RB_POS_COLOR = {
    QB: "#2f7bff", RB: "#93d500", WR: "#ff7a00",
    TE: "#ffc400", K: "#9fd8ff", DST: "#9fb0cc",
  };

  function computeHof() {
    const rows = [];
    let yearsWith = [];
    ALL.forEach(({ year, data }) => {
      const players = (data && data.players) || [];
      if (!players.length) return;
      yearsWith.push(year);
      players.forEach((p) => {
        const pos = normPos(p.pos);
        if (!pos || POS.indexOf(pos) < 0) return;
        (p.wk || []).forEach((w) => {
          if (!w || w[1] == null) return;
          const pts = Number(w[1]);
          if (!Number.isFinite(pts)) return;
          rows.push({
            year: year,
            week: w[0],
            pts: pts,
            name: p.name || ("#" + p.pid),
            pid: p.pid,
            pos: pos,
            tid: w[3],
            owner: ownerOfTid(year, w[3]),
          });
        });
      });
    });
    const byPos = {};
    POS.forEach((pos) => {
      byPos[pos] = rows.filter((r) => r.pos === pos)
        .sort((a, b) => (b.pts - a.pts) || (b.year - a.year))
        .slice(0, 8);
    });
    return { rows: rows, byPos: byPos, have: rows.length > 0, years: yearsWith };
  }

  function hofPlayerLink(r) {
    const href = "players.html?year=" + encodeURIComponent(r.year) + "&pid=" + encodeURIComponent(r.pid);
    return `<a class="hist-name" href="${href}">${esc(r.name)}</a>`;
  }

  function renderHof() {
    const body = $("rb-hof-body");
    const sub = $("rb-hof-sub");
    if (!body) return;
    const hof = computeHof();
    if (!hof.have) {
      if (sub) sub.textContent = "2014–2025 · player week grain missing";
      body.innerHTML = `<div class="notice">Player week grain is missing — cannot list single-week scores.</div>`;
      return;
    }
    const missing = [];
    for (let y = 2014; y <= 2025; y++) {
      if (hof.years.indexOf(y) < 0) missing.push(y);
    }
    if (sub) {
      sub.textContent = (hof.years.length ? (Math.min.apply(null, hof.years) + "–" + Math.max.apply(null, hof.years)) : "")
        + " · top single-week AFFL scores by position"
        + (missing.length ? " · " + missing[0] + "–" + missing[missing.length - 1] + " player week grain missing" : "");
    }
    body.innerHTML = `<div class="rb-hof-grid">` + POS.map((pos) => {
      const rows = hof.byPos[pos] || [];
      const tr = rows.map((r, i) => {
        const tm = r.owner ? (NAME[r.owner] || A.franchiseName(r.owner) || "") : "";
        return `<tr>
          <td>${i + 1}</td>
          <td>${hofPlayerLink(r)}</td>
          <td>${esc(tm)}</td>
          <td>${r.year} W${r.week}</td>
          <td><strong>${A.fmt(r.pts, 1)}</strong></td>
        </tr>`;
      }).join("") || `<tr><td colspan="5"><div class="notice">No ${pos} week scores.</div></td></tr>`;
      return `<div class="rb-hof-col rb-pos-${pos}">
        <div class="rb-h rb-pos-lab">${pos}</div>
        <div class="table-scroll"><table class="tbl">
          <thead><tr><th></th><th>Player</th><th>Team</th><th>When</th><th>Pts</th></tr></thead>
          <tbody>${tr}</tbody>
        </table></div>
      </div>`;
    }).join("") + `</div>`;
  }

  let hofScatterChart = null;
  function renderHofScatter() {
    const wrap = $("rb-hof-scatter-wrap");
    const empty = $("rb-hof-scatter-empty");
    const canvas = $("rb-hof-scatter-chart");
    const sub = $("rb-hof-scatter-sub");
    if (!canvas) return;
    const hof = computeHof();
    if (!hof.have) {
      if (sub) sub.textContent = "player week grain missing";
      if (empty) {
        empty.hidden = false;
        empty.textContent = "Player week grain is missing — no HOF scatter.";
      }
      if (wrap) wrap.hidden = true;
      if (hofScatterChart) { hofScatterChart.destroy(); hofScatterChart = null; }
      return;
    }
    if (empty) empty.hidden = true;
    if (wrap) wrap.hidden = false;
    if (sub) sub.textContent = "top single-week AFFL scores · color by position · 2018–2025";
    if (typeof Chart === "undefined") return;
    A.chartDefaults(Chart);
    if (hofScatterChart) { hofScatterChart.destroy(); hofScatterChart = null; }
    const datasets = POS.map((pos) => {
      const rows = (hof.byPos[pos] || []).slice(0, 8);
      return {
        label: pos,
        data: rows.map((r) => ({
          x: r.year + ((Number(r.week) || 1) - 1) / 18,
          y: r.pts,
          name: r.name,
          week: r.week,
          year: r.year,
          pos: pos,
        })),
        backgroundColor: RB_POS_COLOR[pos] || "#9fb0cc",
        borderColor: RB_POS_COLOR[pos] || "#9fb0cc",
        pointRadius: 6,
        pointHoverRadius: 8,
      };
    });
    hofScatterChart = new Chart(canvas, {
      type: "scatter",
      data: { datasets: datasets },
      options: {
        maintainAspectRatio: false,
        plugins: {
          legend: { display: true, labels: { color: A.C.ink, boxWidth: 10 } },
          tooltip: {
            callbacks: {
              label: (c) => {
                const r = c.raw || {};
                return (r.pos || "") + " · " + (r.name || "") + " · " + r.year + " W" + r.week + " · " + A.fmt(r.y, 1);
              },
            },
          },
        },
        scales: {
          x: {
            grid: { color: A.C.grid },
            border: { display: false },
            title: { display: true, text: "season" },
            ticks: { callback: (v) => String(Math.round(v)) },
          },
          y: {
            grid: { color: A.C.grid },
            border: { display: false },
            title: { display: true, text: "AFFL pts" },
          },
        },
      },
    });
  }

  let ownKey = "seasons";
  let ownDir = -1;
  function renderOwnersTenure() {
    const tb = document.querySelector("#rb-owners-tbl tbody");
    if (!tb) return;
    const rows = careerRows().slice().sort((a, b) => cmpWith(ownKey, ownDir, a, b));
    tb.innerHTML = rows.map((f, i) => `<tr>
      <td>${pill(i)}</td>
      <td>${teamCell(f)}</td>
      <td>${f.seasons || 0}</td>
      <td>${f.firstYear || "—"}</td>
      <td>${f.lastYear || "—"}</td>
    </tr>`).join("");
    document.querySelectorAll("#rb-owners-tbl thead th[data-k]").forEach((th) => {
      const on = th.dataset.k === ownKey;
      th.classList.toggle("on", on);
      th.classList.toggle("asc", on && ownDir > 0);
    });
  }

  function renderAwardIcons() {
    const el = $("rb-award-row");
    if (!el) return;
    const trophies = {};
    rollTrophies().forEach((r) => { trophies[r.owner] = r; });
    const rows = careerRows().slice().sort((a, b) => String(a.name).localeCompare(String(b.name)));
    const icons = (f) => {
      const t = trophies[f.owner] || { cup: 0, median: 0, allPlay: 0, roto: 0 };
      const bits = [];
      const add = (n, cls, lab) => {
        for (let i = 0; i < (n || 0); i++) bits.push(`<span class="rb-ico ${cls}" title="${esc(lab)}">${esc(lab)}</span>`);
      };
      add(t.cup, "cup", "Cup");
      add(t.median, "board", "Board");
      add(t.allPlay, "ap", "All-Play");
      add(t.roto, "roto", "Roto");
      add(f.sackos, "sacko", "Sacko");
      return bits.join("") || `<span class="rb-ico none">—</span>`;
    };
    el.innerHTML = rows.map((f) => {
      const href = "teams.html?squad=" + encodeURIComponent(f.owner);
      return `<a class="rb-award" href="${href}">
        ${A.logoHTML({ name: f.name, logo: f.logo }, "mini")}
        <div class="rb-award-name">${esc(f.name)}</div>
        <div class="rb-award-icons">${icons(f)}</div>
      </a>`;
    }).join("");
  }

  function renderRecordBook() {
    renderStreaks();
    renderTeamRecords();
    renderHof();
    renderHofScatter();
    renderOwnersTenure();
    renderAwardIcons();
  }


  bindSort("#franchise-tbl", () => sortKey, (k) => { sortKey = k; }, () => sortDir, (d) => { sortDir = d; }, renderTable);
  bindSort("#titles-tbl", () => titleKey, (k) => { titleKey = k; }, () => titleDir, (d) => { titleDir = d; }, renderTitles);
  bindSort("#rb-team-tbl", () => teamRecKey, (k) => { teamRecKey = k; }, () => teamRecDir, (d) => { teamRecDir = d; }, renderTeamRecords);
  bindSort("#rb-owners-tbl", () => ownKey, (k) => { ownKey = k; }, () => ownDir, (d) => { ownDir = d; }, renderOwnersTenure);
  bindSort("#scoring-tbl", () => scoreKey, (k) => { scoreKey = k; }, () => scoreDir, (d) => { scoreDir = d; }, renderScoring);
  bindSort("#ppd-tbl", () => ppdKey, (k) => { ppdKey = k; }, () => ppdDir, (d) => { ppdDir = d; }, renderPPD);
  bindSort("#season-tbl", () => standKey, (k) => { standKey = k; }, () => standDir, (d) => { standDir = d; }, renderSeasonStandings);
  bindSort("#txn-tbl", () => txnKey, (k) => { txnKey = k; }, () => txnDir, (d) => { txnDir = d; }, renderTxnAndWeeks);
  bindSort("#custody-par-tbl", () => parKey, (k) => { parKey = k; }, () => parDir, (d) => { parDir = d; }, renderCustodyPar);
  bindSort("#ngs-tbl", () => ngsKey, (k) => { ngsKey = k; }, () => ngsDir, (d) => { ngsDir = d; }, renderNgs);

  renderSeasonStandings();
  renderTxnAndWeeks();
  renderWaiverReport();
  renderTxLog();
  renderWaiverValue();
  renderCustodyPar();
  renderAgeScatter();
  renderRace();
  renderTable();
  renderNgs();
  renderScoring();
  renderPPD();
  renderHeat();
  renderBooks();
  renderBars();
  renderTitles();
  renderTimeline();
  renderH2H();
  try { renderRecordBook(); } catch (e) { console.warn(e); }

  function rollTrophies() {
    const by = {};
    ALL.forEach(({ year, data }) => {
      const t = data && data.trophies;
      if (!t) return;
      const owners = ownerByTid(year);
      const add = (tid, key) => {
        if (tid == null || tid === "") return;
        const oid = owners[tid] || owners[Number(tid)] || owners[String(tid)];
        if (!oid) return;
        if (!by[oid]) by[oid] = { owner: oid, cup: 0, median: 0, allPlay: 0, roto: 0 };
        by[oid][key] += 1;
      };
      add(t.h2hChampionTid, "cup");
      add(t.medianChampionTid, "median");
      add(t.allPlayChampionTid, "allPlay");
      add(t.rotoChampionTid, "roto");
    });
    return Object.keys(by).map((oid) => {
      const r = by[oid];
      r.name = A.franchiseName(oid) || NAME[oid] || "—";
      r.logo = A.franchiseLogo(oid) || "";
      return r;
    });
  }

  function renderTrophyCase() {
    const tb = document.querySelector("#trophy-tbl tbody");
    if (!tb) return;
    const rows = rollTrophies().filter((r) => r.cup || r.median || r.allPlay || r.roto);
    if (!rows.length) {
      tb.innerHTML = `<tr><td colspan="6"><div class="notice">Trophy counts appear when year files include trophies.</div></td></tr>`;
      return;
    }
    rows.sort((a, b) => (b.cup - a.cup) || (b.median - a.median) || (b.allPlay - a.allPlay) || (b.roto - a.roto) || String(a.name).localeCompare(String(b.name)));
    tb.innerHTML = rows.map((f, i) => `
      <tr>
        <td>${pill(i)}</td>
        <td>${teamCell(f)}</td>
        <td>${f.cup || 0}</td>
        <td>${f.median || 0}</td>
        <td>${f.allPlay || 0}</td>
        <td>${f.roto || 0}</td>
      </tr>`).join("");
  }

  try { renderTrophyCase(); } catch (e) { console.warn(e); }

  document.addEventListener("affl:show-former", () => {
    renderTable();
    renderScoring();
    renderPPD();
    renderHeat();
    renderBars();
    try { renderTitles(); } catch (e) {}
    try { renderRecordBook(); } catch (e) {}
  });

  A.onNextMidnight(() => {
    ageAsOf = A.today();
    const el = $("age-asof");
    if (el) el.value = isoDay(ageAsOf);
    renderAgeScatter();
  });
})();
