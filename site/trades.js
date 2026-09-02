/* ============ AFFL Front Office — trades, waivers, free agents ============ */
(async function () {
  const A = window.AFFL;
  const $ = (s) => document.querySelector(s);
  await A.boot();
  A.chartDefaults(Chart);
  const C = A.C, fmt = A.fmt;

  let year = A.seasonFromURL();
  if (year == null) year = A.years()[0];
  let scope = A.seasonFromURL() == null ? "cum" : "season";
  let squad = A.squadFromURL();
  let YD = null, T = {}, chart = null, ALL = null, ACT = null;
  const S = { q: '', type: 'ALL', limit: 40 };

  function tName(id) {
    if (id == null || id === "" || (typeof id === "number" && Number.isNaN(id))) {
      return "unavailable";
    }
    const named = A.franchiseName(id);
    if (named) return named;
    const t = T[id] || T[String(id)] || T[A.canon?.(id)] || {};
    if (t.owner) {
      const fromOwner = A.franchiseName(t.owner);
      if (fromOwner) return fromOwner;
    }
    if (t.name) return t.name;
    return "unavailable";
  }
  function ownerKey(year, tid) {
    const n = Number(tid);
    if (Number.isFinite(n) && n <= 0) return null;
    if (Number.isFinite(n) && n < 1000) {
      const oid = A.ownerId(year, n);
      return oid ? A.canon(oid) : null;
    }
    return A.canon(tid);
  }
  /* Names whole — blotter, log, and axes all paint tName() in full.
     Never slice to 'Grand Teeton Fee…' / 'Squaw Valley Ski…'. */
  function matchesSquad(tid, y) {
    if (!squad) return true;
    const want = A.canon(squad);
    const oid = ownerKey(y || year, tid) || A.canon(tid);
    return oid && A.canon(oid) === want;
  }

  async function loadActivity() {
    if (ACT) return ACT;
    ACT = await fetch("activity.json?v=" + Date.now(), { cache: "no-store" }).then((r) => r.json());
    return ACT;
  }
  function fmtRate(num, den) {
    if (!den) return "unavailable";
    return (100 * num / den).toFixed(0) + "%";
  }
  function activityBundle() {
    if (!ACT) return { available: false, managers: {} };
    if (scope === "cum") return ACT.cumulative || { available: true, managers: {} };
    return (ACT.years || {})[String(year)] || { available: false, managers: {} };
  }
  function txUnavailable() {
    return scope === "season" && (year <= 2017 || !YD || YD.hasTx === false);
  }


  function ring(pct, color, label) {
    const r = 30, circ = 2 * Math.PI * r;
    const off = circ * (1 - Math.min(1, Math.max(0, pct || 0)));
    return `<div class="ring"><svg width="74" height="74" viewBox="0 0 74 74">
      <circle cx="37" cy="37" r="${r}" fill="none" stroke="#ffffff12" stroke-width="7"/>
      <circle cx="37" cy="37" r="${r}" fill="none" stroke="${color}" stroke-width="7"
        stroke-linecap="round" stroke-dasharray="${circ}" stroke-dashoffset="${off}"/>
      </svg><div class="pct" style="color:${color}">${label}</div></div>`;
  }

  function mergeTx(all) {
    const txByTeam = {};
    const trades = [];
    const moves = [];
    const traded = {};
    let usesFaab = false, hasTx = false, biggest = null;
    for (const { year: y, data } of all) {
      if (data.hasTx) hasTx = true;
      if (data.usesFaab) usesFaab = true;
      for (const trd of data.trades || []) {
        const sides = trd.sides.map((s) => Object.assign({}, s, { tid: A.ownerId(y, s.tid) || s.tid }));
        const row = Object.assign({}, trd, { year: y, sides });
        trades.push(row);
        const n = sides.reduce((a, s) => a + ((s.got || []).length), 0);
        if (!biggest || n > biggest.n) biggest = { n, wk: trd.wk, year: y, teams: sides.map((s) => s.tid) };
        sides.forEach((s) => (s.got || []).forEach((g) => {
          const k = g.pid != null ? String(g.pid) : g.name;
          traded[k] = traded[k] || { name: g.name, pid: g.pid, n: 0 };
          traded[k].n += 1;
        }));
      }
      for (const m of data.moves || []) {
        moves.push(Object.assign({}, m, { year: y, tid: A.ownerId(y, m.tid) || m.tid }));
      }
      Object.entries(data.txByTeam || {}).forEach(([tid, v]) => {
        const oid = ownerKey(y, tid);
        if (!oid) return;
        const a = txByTeam[oid] || { waiver: 0, fa: 0, trades: 0, drop: 0, spent: 0 };
        a.waiver += v.waiver || 0; a.fa += v.fa || 0; a.trades += v.trades || 0;
        a.drop += v.drop || 0; a.spent += v.spent || 0;
        txByTeam[oid] = a;
      });
    }
    const mostTraded = Object.values(traded).sort((a, b) => b.n - a.n).slice(0, 8);
    return { trades, moves, txByTeam, usesFaab, hasTx, biggestSwap: biggest, mostTraded, topAdds: [] };
  }

  function renderKPIs() {
    const missing = txUnavailable();
    const byTeam = YD.txByTeam || {};
    const entries = Object.entries(byTeam).map(([tid, v]) => ({ tid, ...v }));
    const waivers = entries.reduce((a, e) => a + e.waiver, 0);
    const fas = entries.reduce((a, e) => a + e.fa, 0);
    const spend = entries.reduce((a, e) => a + e.spent, 0);
    const topTrader = [...entries].sort((a, b) => b.trades - a.trades)[0];
    const topWire = [...entries].sort((a, b) => (b.waiver + b.fa) - (a.waiver + a.fa))[0];
    const accepted = missing ? null : YD.trades.length;
    const wire = missing ? null : (waivers + fas);
    const swap = missing ? null : YD.biggestSwap;
    const churn = missing ? null : (YD.mostTraded || [])[0];

    const cards = [
      { n: '01 · TRADES', color: C.red,
        pct: missing ? 0 : Math.min(1, (accepted || 0) / 40),
        label: missing ? '—' : String(accepted),
        title: 'Completed Trades',
        desc: missing
          ? `unavailable — ESPN does not retain a ${year} trade log`
          : (topTrader && topTrader.trades
            ? `<strong>${tName(topTrader.tid)}</strong> was busiest with ${topTrader.trades}`
            : 'no trades this season') },
      { n: '02 · BLOCKBUSTER', color: C.orange,
        pct: swap ? Math.min(1, swap.n / 8) : 0,
        label: swap ? String(swap.n) : '—',
        title: 'Biggest Swap',
        desc: missing
          ? `unavailable — no ${year} blockbuster in the ESPN log`
          : (swap
            ? `<strong>${swap.n} players</strong> changed hands in one Week ${swap.wk} deal between ` +
              swap.teams.map((t) => tName(t)).join(' and ')
            : 'no trades this season') },
      { n: '03 · THE WIRE', color: C.green,
        pct: missing ? 0 : Math.min(1, (wire || 0) / 600),
        label: missing ? '—' : fmt(wire),
        title: 'Wire Moves',
        desc: missing
          ? `unavailable — waiver and FA adds start in 2018`
          : (topWire
            ? `<strong>${tName(topWire.tid)}</strong> made ${topWire.waiver + topWire.fa} of them`
            : (scope === 'cum'
              ? 'waiver claims and free-agent adds across every season'
              : `waiver claims and free-agent adds in ${year}`)) },
      YD.usesFaab && !missing
        ? { n: '04 · FAAB', color: C.gold, pct: Math.min(1, spend / 1000),
            label: '$' + fmt(spend), title: 'Waiver Spend',
            desc: `<strong>${fmt(waivers)} claims</strong> across the season` }
        : (() => {
            if (churn) {
              return { n: '04 · HOT POTATO', color: C.gold,
                pct: Math.min(1, churn.n / 4), label: String(churn.n),
                title: 'Most-Traded Player',
                desc: `<strong>${A.playerLink(churn.pid, churn.name)}</strong> was traded ${churn.n} separate times` };
            }
            const t = missing ? null : (YD.topAdds || [])[0];
            return { n: '04 · MOST CHASED', color: C.gold,
              pct: t ? Math.min(1, t.n / 12) : 0, label: t ? String(t.n) : '—',
              title: 'Most-Added Player',
              desc: missing
                ? `unavailable — no ${year} add log`
                : (t ? `<strong>${A.playerLink(t.pid, t.name)}</strong> was picked up ${t.n} separate times`
                    : 'no add data') };
          })(),
    ].filter(Boolean);
    $('#tx-kpis').innerHTML = cards.map((c) => `
      <div class="card kpi">${ring(c.pct, c.color, c.label)}
      <div><div class="kpi-num" style="color:${c.color}">${c.n}</div>
      <div class="kpi-title">${c.title}</div>${c.desc ? `<div class="kpi-desc">${c.desc}</div>` : ''}</div></div>`).join('');
    window.__afflTradeKPIs = {
      year: scope === "cum" ? null : year,
      scope,
      txAvailable: !missing,
      completedTrades: accepted,
      wireMoves: wire,
      completedLabel: missing ? "—" : String(accepted),
      wireLabel: missing ? "—" : String(wire),
    };
  }

  function renderActivity() {
    const note = $("#activity-note");
    const sub = $("#activity-sub");
    const wrap = $("#activity-wrap");
    if (note) note.innerHTML = "";
    if (wrap) wrap.classList.remove("as-notice");

    const bag = activityBundle();
    const unavailable = scope === "season" && (year <= 2017 || bag.available === false);
    if (sub) {
      sub.textContent = unavailable
        ? `${year} transaction log unavailable`
        : scope === "cum"
          ? "2018–2025 · waiver submitted vs won · FA adds · trades proposed vs accepted · proposed on its own scale"
          : `${year} · waiver submitted vs won · FA adds · trades proposed vs accepted · proposed on its own scale`;
    }
    if (unavailable) {
      if (chart) { chart.destroy(); chart = null; }
      if (note) {
        note.innerHTML = A.notice(
          `ESPN does not retain transaction history for ${year}. Waiver, free-agent, and trade activity is available from 2018 on.`
        );
      }
      const tb0 = document.querySelector("#activity-rates tbody");
      if (tb0) tb0.innerHTML = "";
      const rw0 = document.getElementById("activity-rates-wrap");
      if (rw0) rw0.hidden = true;
      return;
    }

    const managers = bag.managers || {};
    const rows = Object.entries(managers).map(([tid, v]) => ({ tid, ...v }))
      .filter((r) => {
        const n = tName(r.tid);
        return n && n !== "unavailable" && matchesSquad(r.tid, scope === "cum" ? null : year);
      })
      .sort((a, b) => (
        ((b.waiverSubmitted || 0) + (b.waiverWon || 0) + (b.faAdds || 0) + (b.tradesProposed || 0) + (b.tradesAccepted || 0)) -
        ((a.waiverSubmitted || 0) + (a.waiverWon || 0) + (a.faAdds || 0) + (a.tradesProposed || 0) + (a.tradesAccepted || 0))
      ));
    if (chart) chart.destroy();
    const names = rows.map((r) => tName(r.tid));
    chart = new Chart($("#activity-chart"), {
      type: "bar",
      data: {
        labels: names,
        datasets: [
          { label: "Waiver submitted", data: rows.map((r) => r.waiverSubmitted || 0), backgroundColor: "#47a8ff99", maxBarThickness: 10, xAxisID: "x" },
          { label: "Waiver won", data: rows.map((r) => r.waiverWon || 0), backgroundColor: "#2f7bffcc", maxBarThickness: 10, xAxisID: "x" },
          { label: "FA adds", data: rows.map((r) => r.faAdds || 0), backgroundColor: "#93d500cc", maxBarThickness: 10, xAxisID: "x" },
          { label: "Trades proposed", data: rows.map((r) => r.tradesProposed || 0), backgroundColor: "#ff7a00cc", maxBarThickness: 10, xAxisID: "xProposed" },
          { label: "Trades accepted", data: rows.map((r) => r.tradesAccepted || 0), backgroundColor: "#ff2d1acc", maxBarThickness: 10, xAxisID: "x" },
        ],
      },
      options: {
        indexAxis: "y",
        maintainAspectRatio: false,
        layout: { padding: { left: 4, right: 8, top: 4, bottom: 4 } },
        plugins: {
          legend: { labels: { boxWidth: 10, boxHeight: 10, usePointStyle: true, pointStyle: "circle" } },
          tooltip: { callbacks: {
            title: (items) => names[items[0].dataIndex],
            afterBody: (items) => {
              const r = rows[items[0].dataIndex];
              const submitted = r.waiverSubmitted || 0;
              const won = r.waiverWon || 0;
              const accept = r.tradesAccepted || 0;
              const decline = r.tradesDeclined || 0;
              const veto = r.tradesVetoed || 0;
              const den = accept + decline + veto;
              return [
                `Waiver win rate ${fmtRate(won, submitted)} (${won}/${submitted})`,
                `Trade acceptance ${fmtRate(accept, den)} (${accept}/(${accept}+${decline}+${veto}))`,
              ];
            },
          } },
        },
        scales: {
          x: {
            stacked: false,
            position: "top",
            title: { display: true, text: "Waivers / FA / accepted", color: C.mut || C.ink, font: { size: 10 } },
            grid: { color: C.grid },
            border: { display: false },
          },
          xProposed: {
            stacked: false,
            position: "bottom",
            title: { display: true, text: "Trades proposed", color: C.mut || C.ink, font: { size: 10 } },
            grid: { display: false },
            border: { display: false },
          },
          y: {
            stacked: false,
            grid: { display: false },
            border: { display: false },
            /* CHI-112 — Activity Y-axis = current franchise / team names (never blank dashes) */
            ticks: {
              display: true,
              autoSkip: false,
              color: C.ink,
              font: { size: 11, weight: "600" },
              callback(value, index) {
                const label = names[index] || (typeof this.getLabelForValue === "function" ? this.getLabelForValue(value) : value);
                return label && label !== "—" && label !== "-" ? label : "unavailable";
              },
            },
            afterFit(scale) { scale.width = Math.max(scale.width, 196); },
          },
        },
      },
    });

    const rw = document.getElementById("activity-rates-wrap");
    if (rw) rw.hidden = false;
    const tb = document.querySelector("#activity-rates tbody");
    if (tb) {
      tb.innerHTML = rows.map((r) => {
        const submitted = r.waiverSubmitted || 0;
        const won = r.waiverWon || 0;
        const accept = r.tradesAccepted || 0;
        const decline = r.tradesDeclined || 0;
        const veto = r.tradesVetoed || 0;
        return `<tr>
          <td>${tName(r.tid)}</td>
          <td class="tnum">${fmtRate(won, submitted)}</td>
          <td class="tnum">${fmtRate(accept, accept + decline + veto)}</td>
          <td class="tnum">${submitted}</td>
          <td class="tnum">${won}</td>
          <td class="tnum">${r.faAdds || 0}</td>
          <td class="tnum">${r.tradesProposed || 0}</td>
          <td class="tnum">${accept}</td>
        </tr>`;
      }).join("");
    }
  }

  function renderTrades() {
    if (txUnavailable()) {
      $('#trade-sub').textContent = `${year} trade blotter unavailable`;
      $('#trade-list').innerHTML = A.notice(
        `ESPN does not retain transaction history for ${year}. Available from 2018 on.`);
      return;
    }
    const tradeRows = (YD.trades || []).filter((tr) =>
      !squad || (tr.sides || []).some((s) => matchesSquad(s.tid, tr.year || year)));
    $('#trade-sub').textContent = scope === 'cum'
      ? `${tradeRows.length} completed trades across every season`
      : `${tradeRows.length} completed trade${tradeRows.length === 1 ? '' : 's'} in ${year}`;
    if (!tradeRows.length) {
      $('#trade-list').innerHTML = A.notice(YD.hasTx
        ? `No completed trades in ${year}.`
        : `ESPN does not retain transaction history for ${year}. Available from 2018 on.`);
      return;
    }
    $('#trade-list').innerHTML = tradeRows.map((tr) => `
      <div class="trade">
        <div class="trade-head"><span class="trade-wk">${tr.year ? tr.year + " · " : ""}Week ${tr.wk}</span><span class="trade-date">${A.dateStr(tr.date)}</span></div>
        <div class="trade-body">
          ${tr.sides.map((s) => `
            <div class="trade-side">
              <div class="trade-team">${A.logoHTML(T[s.tid], 'mini')}<span title="${A.esc(tName(s.tid))}">${tName(s.tid)}</span></div>
              <div class="trade-got">${s.got.map((g) =>
                `<span class="trade-pl"><span class="badge pos-${g.pos}">${g.pos}</span> ${A.playerLink(g.pid, g.name)}</span>`).join('')}</div>
            </div>`).join('<div class="trade-swap">⇄</div>')}
        </div>
      </div>`).join('');
  }

  function renderLog() {
    if (txUnavailable()) {
      $('#log-sub').textContent = `${year} transaction log unavailable`;
      const yth0 = document.getElementById('year-th');
      if (yth0) yth0.hidden = true;
      $('#bid-th').style.display = 'none';
      $('#log-tbl tbody').innerHTML = `<tr><td colspan="7" class="own">ESPN does not retain transactions for ${year}.</td></tr>`;
      $('#log-more').style.display = 'none';
      return;
    }
    const q = S.q.toLowerCase();
    const rows = (YD.moves || []).filter((m) => {
      if (S.type !== 'ALL' && m.type !== S.type) return false;
      if (!matchesSquad(m.tid, m.year || year)) return false;
      if (!q) return true;
      const names = [...m.add, ...m.drop].map((x) => x.name.toLowerCase()).join(' ');
      return names.includes(q) || tName(m.tid).toLowerCase().includes(q);
    }).reverse();

    $('#log-sub').textContent = `${fmt(rows.length)} move${rows.length === 1 ? '' : 's'} · newest first`;
    const yth = document.getElementById('year-th');
    if (yth) yth.hidden = scope !== 'cum';
    $('#bid-th').style.display = YD.usesFaab ? '' : 'none';
    const plList = (arr, cls) => arr.length
      ? arr.map((x) => `<span class="mv ${cls}"><span class="badge pos-${x.pos}">${x.pos}</span> ${A.playerLink(x.pid, x.name)}</span>`).join('')
      : '<span class="own">—</span>';

    $('#log-tbl tbody').innerHTML = rows.slice(0, S.limit).map((m) => `
      <tr>
        ${scope === 'cum' ? `<td class="tnum">${m.year}</td>` : ''}
        <td><strong>W${m.wk}</strong></td>
        <td class="own">${A.dateStr(m.date)}</td>
        <td><div class="team-cell">${A.logoHTML(T[m.tid], 'mini')}<span title="${A.esc(tName(m.tid))}">${tName(m.tid)}</span></div></td>
        <td><span class="badge ${m.type === 'WAIVER' ? 'pos-QB' : 'pos-RB'}">${m.type === 'WAIVER' ? 'waiver' : 'free agent'}</span></td>
        ${YD.usesFaab ? `<td>${m.bid ? '$' + m.bid : '—'}</td>` : ''}
        <td>${plList(m.add, 'add')}</td>
        <td>${plList(m.drop, 'drop')}</td>
      </tr>`).join('') || `<tr><td colspan="7" class="own">${
        YD.hasTx ? 'No moves match.' : `ESPN does not retain transactions for ${year}.`}</td></tr>`;
    $('#log-more').style.display = rows.length > S.limit ? 'block' : 'none';
  }

  const TYPES = [['ALL', 'All'], ['WAIVER', 'Waivers'], ['FREEAGENT', 'Free Agents']];
  $('#tx-filters').innerHTML = TYPES.map(([v, l]) =>
    `<button class="pp-chip${v === 'ALL' ? ' on' : ''}" data-t="${v}">${l}</button>`).join('');
  $('#tx-filters').querySelectorAll('.pp-chip').forEach((b) =>
    b.addEventListener('click', () => {
      S.type = b.dataset.t; S.limit = 40;
      $('#tx-filters').querySelectorAll('.pp-chip').forEach((x) => x.classList.toggle('on', x === b));
      renderLog();
    }));
  $('#tx-search').addEventListener('input', (e) => { S.q = e.target.value; S.limit = 40; renderLog(); });
  $('#log-more').addEventListener('click', () => { S.limit += 40; renderLog(); });


  let GRID = null;
  let gridPin = "";
  let gridHover = "";

  function tradeOwners(y, tr) {
    const sides = tr.sides || [];
    const out = [];
    const push = (tid) => {
      if (tid == null || tid === "") return;
      const oid = A.canon(A.ownerId(y, tid) || tid);
      if (oid) out.push(oid);
    };
    if (sides.length >= 2) {
      sides.forEach((s) => push(s.tid));
    } else if (sides.length === 1) {
      push(sides[0].tid);
      (sides[0].got || []).forEach((g) => push(g.from));
    }
    return Array.from(new Set(out));
  }

  function gridFranchises() {
    return A.squads().filter((f) => f.active).sort((a, b) =>
      (a.currentName || "").localeCompare(b.currentName || ""));
  }

  function gridAbbr(name) {
    const last = String(name || "").split(/\s+/).filter(Boolean).pop() || name || "?";
    const clean = last.normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/[^A-Za-z]/g, "");
    return clean.slice(0, 3).toUpperCase();
  }

  function buildTradeGrid(all) {
    const fr = gridFranchises();
    const ids = fr.map((f) => A.canon(f.owner));
    const allow = {};
    ids.forEach((id) => { allow[id] = true; });
    const counts = {};
    ids.forEach((a) => {
      counts[a] = {};
      ids.forEach((b) => { counts[a][b] = 0; });
    });
    const seen = {};
    let deals = 0;
    (all || []).forEach((bundle) => {
      const y = bundle.year;
      ((bundle.data && bundle.data.trades) || []).forEach((tr) => {
        const owners = tradeOwners(y, tr).filter((o) => allow[o]);
        if (owners.length < 2) return;
        const pair = [owners[0], owners[1]].slice().sort();
        const key = y + ":" + (tr.date || "") + ":" + (tr.wk || "") + ":" + pair.join("|");
        if (seen[key]) return;
        seen[key] = 1;
        deals += 1;
        counts[pair[0]][pair[1]] += 1;
        counts[pair[1]][pair[0]] += 1;
      });
    });
    let max = 0;
    ids.forEach((a) => ids.forEach((b) => { if (a !== b && counts[a][b] > max) max = counts[a][b]; }));
    return { fr: fr, ids: ids, counts: counts, deals: deals, max: max };
  }

  function gridHeat(n, max) {
    if (!n || !max) return "";
    const t = n / max;
    const a = (0.10 + 0.42 * t).toFixed(2);
    return "background: rgba(157, 176, 204, " + a + ")";
  }

  function paintTradeGrid() {
    const g = GRID;
    const tbl = $("#trade-grid");
    if (!g || !tbl) return;
    const lit = gridHover || gridPin;
    const head = `<tr><th class="tg-y"></th>${g.fr.map((f, i) => {
      const id = g.ids[i];
      const on = lit === id ? " on tg-hi" : "";
      return `<th class="tg-x${on}" data-id="${id}" title="${A.esc(f.currentName)}">${A.esc(gridAbbr(f.currentName))}</th>`;
    }).join("")}</tr>`;
    const body = g.fr.map((f, i) => {
      const a = g.ids[i];
      const rowOn = lit === a ? " tg-hi" : "";
      const cells = g.ids.map((b, j) => {
        if (a === b) return `<td class="tg-diag"></td>`;
        const n = (g.counts[a] && g.counts[a][b]) || 0;
        const colOn = lit === b ? " tg-hi" : "";
        const z = n ? "" : " z";
        const other = g.fr[j].currentName;
        return `<td class="tg-n${z}${colOn}" data-a="${a}" data-b="${b}" style="${gridHeat(n, g.max)}" title="${A.esc(f.currentName)} ↔ ${A.esc(other)} · ${n}">${n || ""}</td>`;
      }).join("");
      return `<tr class="${rowOn}"><th class="tg-y${lit === a ? " on" : ""}" data-id="${a}">${A.esc(f.currentName)}</th>${cells}</tr>`;
    }).join("");
    tbl.innerHTML = head + body;
  }

  function wireTradeGrid() {
    const tbl = $("#trade-grid");
    if (!tbl || tbl.dataset.wired) return;
    tbl.dataset.wired = "1";
    tbl.addEventListener("mouseover", (e) => {
      const el = e.target.closest("[data-id]");
      if (!el || !tbl.contains(el)) return;
      if (gridHover === el.dataset.id) return;
      gridHover = el.dataset.id;
      paintTradeGrid();
    });
    tbl.addEventListener("mouseleave", () => {
      if (!gridHover) return;
      gridHover = "";
      paintTradeGrid();
    });
    tbl.addEventListener("click", (e) => {
      const el = e.target.closest("[data-id]");
      if (!el || !tbl.contains(el)) return;
      gridPin = gridPin === el.dataset.id ? "" : el.dataset.id;
      paintTradeGrid();
    });
  }

  async function renderTradeGrid() {
    const sub = $("#trade-grid-sub");
    const tbl = $("#trade-grid");
    const note = $("#trade-grid-note");
    const scroll = tbl && tbl.closest(".tg-scroll");
    const missing = txUnavailable();
    if (missing) {
      GRID = null;
      if (sub) sub.textContent = `${year} · trade grid unavailable · ESPN has no trade log before 2018`;
      if (tbl) tbl.innerHTML = "";
      if (scroll) scroll.hidden = true;
      if (note) {
        note.hidden = false;
        note.innerHTML = A.notice(
          `ESPN does not retain a trade log for ${year}. The completed-trade matrix starts in 2018.`
        );
      }
      window.__afflTradeGrid = {
        available: false,
        year,
        deals: null,
        max: null,
        names: [],
        span: String(year),
      };
      return;
    }
    ALL = ALL || await A.loadAllYears();
    const src = scope === "cum" ? ALL : ALL.filter((b) => Number(b.year) === Number(year));
    GRID = buildTradeGrid(src);
    if (note) { note.hidden = true; note.innerHTML = ""; }
    if (scroll) scroll.hidden = false;
    if (sub) {
      sub.textContent = scope === "cum"
        ? `${GRID.deals} completed trades among current franchises · 2018–2025 · ESPN has no trade log before 2018 · click a name to pin`
        : `${GRID.deals} completed trades among current franchises · ${year} · click a name to pin`;
    }
    paintTradeGrid();
    wireTradeGrid();
    window.__afflTradeGrid = {
      available: true,
      year: scope === "cum" ? null : year,
      deals: GRID.deals,
      max: GRID.max,
      names: GRID.fr.map((f) => f.currentName),
      span: scope === "cum" ? "2018–2025" : String(year),
    };
  }

  async function pick(y) {
    year = y;
    const seasonYear = scope === "cum" ? null : year;
    if (seasonYear != null && squad && !A.franchisePlayedSeason(squad, seasonYear)) {
      squad = "";
      A.stampNav("");
    }
    S.limit = 40;
    const ylist = squad ? A.squadYears(squad) : A.years();
    A.showYearRow(true);
    A.remountTeamSelect(document.getElementById('squad-picker'), squad, (s) => {
      squad = s || '';
      A.stampNav(squad);
      if (squad && scope === "season") {
        const next = A.clampYear(year, squad);
        if (next == null) { scope = "cum"; year = A.years()[0]; }
        else year = next;
      }
      pick(year);
    }, scope === "cum" ? null : year);
    A.stampNav(squad);
    A.seasonSelect($('#year-picker'), scope === "cum" ? null : year, (y) => {
      if (y == null) { scope = "cum"; pick(A.years()[0]); }
      else { scope = "season"; pick(y); }
    }, ylist);
    if (scope === 'cum') {
      ALL = ALL || await A.loadAllYears();
      YD = mergeTx(ALL);
      T = A.ownerTeams();
      $('#page-sub').textContent = `All · ${YD.trades.length} trades · ${fmt((YD.moves || []).length)} wire moves`;
    } else {
      YD = await A.loadYear(year);
      T = A.teams(year);
      $('#page-sub').textContent = YD.hasTx
        ? `${year} · ${YD.trades.length} trades · ${fmt((YD.moves || []).length)} wire moves`
        : `${year} · no transaction history stored`;
    }
    ACT = ACT || await loadActivity();
    renderKPIs(); renderActivity(); renderTrades(); renderLog();
    await renderTradeGrid();
  }

  const qs = new URLSearchParams(location.search);
  await pick(A.seasonFromURL() || A.years()[0]);
})();
