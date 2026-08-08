/* ============ AFFL Front Office — trades, waivers, free agents ============ */
(async function () {
  const A = window.AFFL;
  const $ = (s) => document.querySelector(s);
  await A.boot();
  A.chartDefaults(Chart);
  const C = A.C, fmt = A.fmt;

  let year = A.years()[0];
  let YD = null, T = {}, chart = null;
  const S = { q: '', type: 'ALL', limit: 40 };

  const tName = (id) => (T[id] || { name: '?' }).name;
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

  function renderKPIs() {
    const byTeam = YD.txByTeam || {};
    const entries = Object.entries(byTeam).map(([tid, v]) => ({ tid: +tid, ...v }));
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
                desc: `<strong>${churn.name}</strong> was traded ${churn.n} separate times` };
            }
            const t = (YD.topAdds || [])[0];
            return { n: '04 · MOST CHASED', color: C.gold,
              pct: t ? Math.min(1, t.n / 12) : 0, label: t ? String(t.n) : '—',
              title: 'Most-Added Player',
              desc: t ? `<strong>${t.name}</strong> was picked up ${t.n} separate times`
                      : 'no add data' };
          })(),
    ].filter(Boolean);
    $('#tx-kpis').innerHTML = cards.map((c) => `
      <div class="card kpi">${ring(c.pct, c.color, c.label)}
      <div><div class="kpi-num" style="color:${c.color}">${c.n}</div>
      <div class="kpi-title">${c.title}</div><div class="kpi-desc">${c.desc}</div></div></div>`).join('');
  }

  function renderActivity() {
    const rows = Object.entries(YD.txByTeam || {}).map(([tid, v]) => ({ tid: +tid, ...v }))
      .sort((a, b) => (b.waiver + b.fa + b.trades) - (a.waiver + a.fa + a.trades));
    if (chart) chart.destroy();
    chart = new Chart($('#activity-chart'), {
      type: 'bar',
      data: {
        labels: rows.map((r) => short(r.tid)),
        datasets: [
          { label: 'Waiver claims', data: rows.map((r) => r.waiver), backgroundColor: '#2f7bffcc', stack: 'a', maxBarThickness: 15 },
          { label: 'Free agents', data: rows.map((r) => r.fa), backgroundColor: '#93d500cc', stack: 'a', maxBarThickness: 15 },
          { label: 'Trades', data: rows.map((r) => r.trades), backgroundColor: '#ff2d1acc', stack: 'a', maxBarThickness: 15 },
        ],
      },
      options: {
        indexAxis: 'y',
        maintainAspectRatio: false,
        plugins: {
          legend: { labels: { boxWidth: 10, boxHeight: 10, usePointStyle: true, pointStyle: 'circle' } },
          tooltip: { callbacks: { afterBody: (items) => {
            const r = rows[items[0].dataIndex];
            const parts = [`${r.waiver + r.fa} wire moves`, `${r.drop} drops`, `${r.trades} trades`];
            if (YD.usesFaab) parts.push(`$${r.spent} spent`);
            return parts.join(' · ');
          } } },
        },
        scales: {
          x: { stacked: true, grid: { color: C.grid }, border: { display: false } },
          y: { stacked: true, grid: { display: false }, border: { display: false } },
        },
      },
    });
  }

  function renderTrades() {
    $('#trade-sub').textContent = `${YD.trades.length} completed trade${YD.trades.length === 1 ? '' : 's'} in ${year}`;
    if (!YD.trades.length) {
      $('#trade-list').innerHTML = A.notice(YD.hasTx
        ? `No completed trades in ${year}.`
        : `ESPN does not retain transaction history for ${year}. Available from 2018 on.`);
      return;
    }
    $('#trade-list').innerHTML = YD.trades.map((tr) => `
      <div class="trade">
        <div class="trade-head"><span class="trade-wk">Week ${tr.wk}</span><span class="trade-date">${A.dateStr(tr.date)}</span></div>
        <div class="trade-body">
          ${tr.sides.map((s) => `
            <div class="trade-side">
              <div class="trade-team">${A.logoHTML(T[s.tid], 'mini')}<span>${short(s.tid)}</span></div>
              <div class="trade-got">${s.got.map((g) =>
                `<span class="trade-pl"><span class="badge pos-${g.pos}">${g.pos}</span> ${g.name}</span>`).join('')}</div>
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
    $('#bid-th').style.display = YD.usesFaab ? '' : 'none';
    const plList = (arr, cls) => arr.length
      ? arr.map((x) => `<span class="mv ${cls}"><span class="badge pos-${x.pos}">${x.pos}</span> ${x.name}</span>`).join('')
      : '<span class="own">—</span>';

    $('#log-tbl tbody').innerHTML = rows.slice(0, S.limit).map((m) => `
      <tr>
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

  async function pick(y) {
    year = y;
    S.limit = 40;
    YD = await A.loadYear(y);
    T = A.teams(y);
    A.yearPicker($('#year-picker'), year, pick, (i) => i.hasTx ? '' : '*');
    $('#page-sub').textContent = YD.hasTx
      ? `${year} · ${YD.trades.length} trades · ${fmt((YD.moves || []).length)} wire moves`
      : `${year} · no transaction history stored`;
    renderKPIs(); renderActivity(); renderTrades(); renderLog();
  }

  const qs = new URLSearchParams(location.search);
  await pick(+qs.get('year') || A.years()[0]);
})();
