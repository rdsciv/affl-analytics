/* ============ AFFL Front Office — trades, waivers, free agents ============ */
(async function () {
  const A = window.AFFL;
  const $ = (s) => document.querySelector(s);
  await A.boot();
  A.chartDefaults(Chart);
  const C = A.C, fmt = A.fmt;

  let year = A.years()[0];
  let scope = A.scopeFromURL();
  let squad = A.squadFromURL();
  let YD = null, T = {}, chart = null, ALL = null;
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
  const short = (id) => tName(id).length > 17 ? tName(id).slice(0, 16) + '…' : tName(id);

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
    const byTeam = YD.txByTeam || {};
    const entries = Object.entries(byTeam).map(([tid, v]) => ({ tid, ...v }));
    const waivers = entries.reduce((a, e) => a + e.waiver, 0);
    const fas = entries.reduce((a, e) => a + e.fa, 0);
    const spend = entries.reduce((a, e) => a + e.spent, 0);
    const topTrader = [...entries].sort((a, b) => b.trades - a.trades)[0];
    const topWire = [...entries].sort((a, b) => (b.waiver + b.fa) - (a.waiver + a.fa))[0];
    const accepted = YD.trades.length;
    const swap = YD.biggestSwap;
    const churn = (YD.mostTraded || [])[0];

    const cards = [
      { n: '01 · TRADES', color: C.red, pct: Math.min(1, accepted / 40),
        label: String(accepted), title: 'Completed Trades',
        desc: topTrader && topTrader.trades
          ? `<strong>${tName(topTrader.tid)}</strong> was busiest with ${topTrader.trades}`
          : 'no trades this season' },
      { n: '02 · BLOCKBUSTER', color: C.orange,
        pct: swap ? Math.min(1, swap.n / 8) : 0,
        label: swap ? String(swap.n) : '—',
        title: 'Biggest Swap',
        desc: swap
          ? `<strong>${swap.n} players</strong> changed hands in one Week ${swap.wk} deal between ` +
            swap.teams.map((t) => tName(t)).join(' and ')
          : 'no trades this season' },
      { n: '03 · THE WIRE', color: C.green, pct: Math.min(1, (waivers + fas) / 600),
        label: fmt(waivers + fas), title: 'Wire Moves',
        desc: topWire ? `<strong>${tName(topWire.tid)}</strong> made ${topWire.waiver + topWire.fa} of them` : '' },
      YD.usesFaab
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
            const t = (YD.topAdds || [])[0];
            return { n: '04 · MOST CHASED', color: C.gold,
              pct: t ? Math.min(1, t.n / 12) : 0, label: t ? String(t.n) : '—',
              title: 'Most-Added Player',
              desc: t ? `<strong>${A.playerLink(t.pid, t.name)}</strong> was picked up ${t.n} separate times`
                      : 'no add data' };
          })(),
    ].filter(Boolean);
    $('#tx-kpis').innerHTML = cards.map((c) => `
      <div class="card kpi">${ring(c.pct, c.color, c.label)}
      <div><div class="kpi-num" style="color:${c.color}">${c.n}</div>
      <div class="kpi-title">${c.title}</div><div class="kpi-desc">${c.desc}</div></div></div>`).join('');
  }

  function renderActivity() {
    const rows = Object.entries(YD.txByTeam || {}).map(([tid, v]) => ({ tid, ...v }))
      .filter((r) => {
        const n = tName(r.tid);
        return n && n !== "unavailable";
      })
      .sort((a, b) => (b.waiver + b.fa + b.trades) - (a.waiver + a.fa + a.trades));
    if (chart) chart.destroy();
    const names = rows.map((r) => tName(r.tid));
    chart = new Chart($('#activity-chart'), {
      type: 'bar',
      data: {
        labels: names,
        datasets: [
          { label: 'Waiver claims', data: rows.map((r) => r.waiver), backgroundColor: '#2f7bffcc', stack: 'a', maxBarThickness: 15 },
          { label: 'Free agents', data: rows.map((r) => r.fa), backgroundColor: '#93d500cc', stack: 'a', maxBarThickness: 15 },
          { label: 'Trades', data: rows.map((r) => r.trades), backgroundColor: '#ff2d1acc', stack: 'a', maxBarThickness: 15 },
        ],
      },
      options: {
        indexAxis: 'y',
        maintainAspectRatio: false,
        layout: { padding: { left: 4, right: 8, top: 4, bottom: 4 } },
        plugins: {
          legend: { labels: { boxWidth: 10, boxHeight: 10, usePointStyle: true, pointStyle: 'circle' } },
          tooltip: { callbacks: {
            title: (items) => names[items[0].dataIndex],
            afterBody: (items) => {
            const r = rows[items[0].dataIndex];
            const parts = [`${r.waiver + r.fa} wire moves`, `${r.drop} drops`, `${r.trades} trades`];
            if (YD.usesFaab) parts.push(`$${r.spent} spent`);
            return parts.join(' · ');
          } } },
        },
        scales: {
          x: { stacked: true, grid: { color: C.grid }, border: { display: false } },
          y: {
            stacked: true,
            grid: { display: false },
            border: { display: false },
            ticks: { display: true, autoSkip: false, color: C.ink, font: { size: 11, weight: '600' } },
            afterFit(scale) { scale.width = Math.max(scale.width, 196); },
          },
        },
      },
    });
  }

  function renderTrades() {
    $('#trade-sub').textContent = scope === 'cum'
      ? `${YD.trades.length} completed trades across every season`
      : `${YD.trades.length} completed trade${YD.trades.length === 1 ? '' : 's'} in ${year}`;
    if (!YD.trades.length) {
      $('#trade-list').innerHTML = A.notice(YD.hasTx
        ? `No completed trades in ${year}.`
        : `ESPN does not retain transaction history for ${year}. Available from 2018 on.`);
      return;
    }
    $('#trade-list').innerHTML = YD.trades.map((tr) => `
      <div class="trade">
        <div class="trade-head"><span class="trade-wk">${tr.year ? tr.year + " · " : ""}Week ${tr.wk}</span><span class="trade-date">${A.dateStr(tr.date)}</span></div>
        <div class="trade-body">
          ${tr.sides.map((s) => `
            <div class="trade-side">
              <div class="trade-team">${A.logoHTML(T[s.tid], 'mini')}<span>${short(s.tid)}</span></div>
              <div class="trade-got">${s.got.map((g) =>
                `<span class="trade-pl"><span class="badge pos-${g.pos}">${g.pos}</span> ${A.playerLink(g.pid, g.name)}</span>`).join('')}</div>
            </div>`).join('<div class="trade-swap">⇄</div>')}
        </div>
      </div>`).join('');
  }

  function renderLog() {
    const q = S.q.toLowerCase();
    const rows = (YD.moves || []).filter((m) => {
      if (S.type !== 'ALL' && m.type !== S.type) return false;
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
        <td><div class="team-cell">${A.logoHTML(T[m.tid], 'mini')}<span>${short(m.tid)}</span></div></td>
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
    ALL = ALL || await A.loadAllYears();
    GRID = buildTradeGrid(ALL);
    if (sub) {
      sub.textContent = `${GRID.deals} completed trades among current franchises · 2018–2025 · ESPN has no trade log before 2018 · click a name to pin`;
    }
    paintTradeGrid();
    wireTradeGrid();
    window.__afflTradeGrid = {
      deals: GRID.deals,
      max: GRID.max,
      names: GRID.fr.map((f) => f.currentName),
    };
  }

  async function pick(y) {
    year = y;
    S.limit = 40;
    A.scopePicker(document.getElementById('scope-picker'), scope, (s) => { scope = s; pick(year); });
    A.showYearRow(scope === 'season');
    A.squadPicker(document.getElementById('squad-picker'), squad, (s) => {
      if (s) { A.goTeam(s, year, { scope }); return; }
      squad = ''; A.stampNav(squad); pick(year);
    });
    A.stampNav(squad);
    A.yearPicker($('#year-picker'), year, pick, (i) => i.hasTx ? '' : '*');
    if (scope === 'cum') {
      ALL = ALL || await A.loadAllYears();
      YD = mergeTx(ALL);
      T = A.ownerTeams();
      $('#page-sub').textContent = `Cumulative · ${YD.trades.length} trades · ${fmt((YD.moves || []).length)} wire moves`;
    } else {
      YD = await A.loadYear(year);
      T = A.teams(year);
      $('#page-sub').textContent = YD.hasTx
        ? `${year} · ${YD.trades.length} trades · ${fmt((YD.moves || []).length)} wire moves`
        : `${year} · no transaction history stored`;
    }
    renderKPIs(); renderActivity(); renderTrades(); renderLog();
    await renderTradeGrid();
  }

  const qs = new URLSearchParams(location.search);
  await pick(+qs.get('year') || A.years()[0]);
})();
