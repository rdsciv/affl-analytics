/* ============ AFFL Draft Room — all seasons ============ */
(async function () {
  const A = window.AFFL;
  const $ = (s) => document.querySelector(s);
  await A.boot();
  A.chartDefaults(Chart);
  const C = A.C, fmt = A.fmt;

  let year = A.years()[0];
  let YD = null, T = {}, chart = null;
  const S = { q: '', limit: 60 };

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

  /** value = points per dollar (auction) or points per pick slot (snake) */
  const scored = () => YD.draft.board.filter((p) => p.pts != null);

  function renderKPIs() {
    const board = YD.draft.board;
    const withPts = scored();
    const auction = YD.draft.auction;
    const totalSpend = board.reduce((a, p) => a + (p.bid || 0), 0);
    const hit = withPts.length ? withPts.filter((p) => p.pts >= 100).length / withPts.length : 0;
    const best = withPts.length
      ? [...withPts].sort((a, b) => (b.pts / Math.max(1, b.bid || 1)) - (a.pts / Math.max(1, a.bid || 1)))[0]
      : null;
    const priciest = [...board].sort((a, b) => (b.bid || 0) - (a.bid || 0))[0];

    const cards = [
      { n: '01 · FORMAT', color: C.gold, pct: 1, label: auction ? '$' : '#',
        title: auction ? 'Auction Draft' : 'Snake Draft',
        desc: `<strong>${board.length} picks</strong>${auction ? ` · $${fmt(totalSpend)} total spend` : ' · standard serpentine order'}` },
      priciest && { n: '02 · TOP DOLLAR', color: C.fire,
        pct: priciest.bid ? Math.min(1, priciest.bid / 100) : 1,
        label: auction ? '$' + priciest.bid : '1.01',
        title: auction ? 'Priciest Buy' : 'First Overall',
        desc: `<strong>${priciest.name}</strong>${priciest.pts != null ? ` · returned ${fmt(priciest.pts, 0)} pts` : ''}` },
      best && { n: '03 · BEST VALUE', color: C.green,
        pct: 1, label: auction ? `${fmt(best.pts / Math.max(1, best.bid || 1), 0)}x` : fmt(best.pts, 0),
        title: 'Steal Of The Draft',
        desc: `<strong>${best.name}</strong> · ${auction ? `$${best.bid || 0} → ` : ''}${fmt(best.pts, 0)} pts` },
      withPts.length && { n: '04 · HIT RATE', color: C.blue, pct: hit,
        label: Math.round(hit * 100) + '%', title: 'Draft Hit Rate',
        desc: `<strong>${withPts.filter((p) => p.pts >= 100).length} of ${withPts.length}</strong> drafted players cleared 100 points` },
    ].filter(Boolean);

    $('#draft-kpis').innerHTML = cards.map((c) => `
      <div class="card kpi">${ring(c.pct, c.color, c.label)}
      <div><div class="kpi-num" style="color:${c.color}">${c.n}</div>
      <div class="kpi-title">${c.title}</div><div class="kpi-desc">${c.desc}</div></div></div>`).join('');
  }

  function renderSpend() {
    const auction = YD.draft.auction;
    const POS_COLORS = { QB: C.blue, RB: C.green, WR: C.orange, TE: C.gold, K: C.ice, DST: C.steel };
    const per = {};
    YD.draft.board.forEach((p) => {
      const b = (per[p.tid] = per[p.tid] || { pts: 0, spend: 0, byPos: {} });
      b.spend += p.bid || 0;
      b.pts += p.pts || 0;
      const key = POS_COLORS[p.pos] ? p.pos : 'K';
      b.byPos[key] = (b.byPos[key] || 0) + (auction ? (p.bid || 0) : 1);
    });
    const rows = Object.entries(per).map(([tid, v]) => ({ tid: +tid, ...v }))
      .sort((a, b) => b.pts - a.pts);
    const anyPts = rows.some((r) => r.pts > 0);

    // Every manager spends the same fixed budget, so total spend is a flat line and
    // tells you nothing — what varies is how they allocated it and what it returned.
    $('#spend-sub').textContent = auction
      ? 'how each manager allocated their $200 across positions · line = points returned per dollar'
      : 'draft picks by position · line = points those picks returned';

    if (chart) chart.destroy();
    chart = new Chart($('#spend-chart'), {
      data: {
        labels: rows.map((r) => short(r.tid)),
        datasets: [
          ...Object.keys(POS_COLORS).map((pos) => ({
            type: 'bar', label: pos, stack: 'spend', yAxisID: 'y',
            data: rows.map((r) => r.byPos[pos] || 0),
            backgroundColor: POS_COLORS[pos], maxBarThickness: 30, order: 2,
          })),
          ...(anyPts ? [{
            type: 'line', label: auction ? 'Pts per $' : 'Total pts', yAxisID: 'y1',
            data: rows.map((r) => auction ? +(r.pts / Math.max(1, r.spend)).toFixed(2) : r.pts),
            borderColor: '#ffffff', backgroundColor: '#ffffff', borderWidth: 2,
            pointRadius: 3, pointBackgroundColor: '#fff', pointBorderColor: '#05060b',
            tension: 0.25, order: 1,
          }] : []),
        ],
      },
      options: {
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: { labels: { boxWidth: 10, boxHeight: 10, usePointStyle: true, pointStyle: 'circle' } },
          tooltip: { callbacks: { afterBody: (items) => {
            const r = rows[items[0].dataIndex];
            return auction
              ? `$${fmt(r.spend)} spent · ${fmt(r.pts, 0)} pts returned`
              : `${fmt(r.pts, 0)} pts from drafted players`;
          } } },
        },
        scales: {
          y: { stacked: true, beginAtZero: true, grid: { color: C.grid }, border: { display: false },
               title: { display: true, text: auction ? '$ spent' : 'picks' } },
          y1: { position: 'right', beginAtZero: true, grid: { display: false },
                border: { display: false }, display: anyPts,
                title: { display: anyPts, text: auction ? 'pts / $' : 'pts' } },
          x: { stacked: true, grid: { display: false }, border: { display: false },
               ticks: { maxRotation: 55, minRotation: 40 } },
        },
      },
    });
  }

  function renderValue() {
    const auction = YD.draft.auction;
    const withPts = scored();
    const val = (p) => auction ? p.pts / Math.max(1, p.bid || 1) : p.pts;
    const steals = [...withPts].filter((p) => auction ? (p.bid || 0) >= 1 : (p.overall || 99) > 60)
      .sort((a, b) => val(b) - val(a)).slice(0, 6);
    const busts = [...withPts].filter((p) => auction ? (p.bid || 0) >= 20 : (p.overall || 99) <= 24)
      .sort((a, b) => val(a) - val(b)).slice(0, 6);
    const row = (p, cls) => `<tr>
      <td><strong>${p.name}</strong> <span class="badge pos-${p.pos}">${p.pos}</span>
        <div class="own">${short(p.tid)}</div></td>
      <td>${auction ? '$' + (p.bid || 0) : '#' + p.overall}</td>
      <td><span class="badge ${cls}">${fmt(p.pts, 0)} pts</span></td></tr>`;
    const none = `<tr><td colspan="3" class="own">ESPN stores no weekly scoring for ${year}, so returns can't be graded.</td></tr>`;
    $('#steals-tbl tbody').innerHTML = steals.map((p) => row(p, 'steal')).join('') || none;
    $('#busts-tbl tbody').innerHTML = busts.map((p) => row(p, 'bust')).join('') || '';
  }

  function renderBoard() {
    const auction = YD.draft.auction;
    $('#cost-th').textContent = auction ? 'Cost' : 'Pick';
    const q = S.q.toLowerCase();
    const rows = YD.draft.board.filter((p) =>
      !q || p.name.toLowerCase().includes(q) || tName(p.tid).toLowerCase().includes(q));
    const withPts = scored();
    const avgVal = withPts.length && auction
      ? withPts.reduce((a, p) => a + p.pts / Math.max(1, p.bid || 1), 0) / withPts.length : null;

    $('#board-sub').textContent =
      `${YD.draft.board.length} picks · ${auction ? 'auction' : 'snake'}${YD.hasRosters ? '' : ' · no scoring data stored for this season'}`;

    $('#board-tbl tbody').innerHTML = rows.slice(0, S.limit).map((p) => {
      let badge = '<td class="own">—</td>';
      if (p.pts != null && auction) {
        const v = p.pts / Math.max(1, p.bid || 1);
        const good = avgVal && v >= avgVal;
        badge = `<td><span class="badge ${good ? 'steal' : 'bust'}">${v.toFixed(1)}/$</span></td>`;
      } else if (p.pts != null) {
        badge = `<td>${p.pts >= 100 ? '<span class="badge steal">hit</span>' : '<span class="badge bust">miss</span>'}</td>`;
      }
      return `<tr>
        <td><span class="rank-pill${p.overall === 1 ? ' gold' : ''}">${p.overall}</span></td>
        <td><strong>${p.name}</strong>${p.keeper ? ' <span class="badge">keeper</span>' : ''}</td>
        <td><span class="badge pos-${p.pos}">${p.pos}</span></td>
        <td class="own">${p.nfl || '—'}</td>
        <td><div class="team-cell">${A.logoHTML(T[p.tid], 'mini')}<span>${short(p.tid)}</span></div></td>
        <td><strong>${auction ? '$' + (p.bid || 0) : p.round + '.' + String(p.pick).padStart(2, '0')}</strong></td>
        <td>${p.pts != null ? fmt(p.pts, 1) : '—'}</td>
        ${badge}
      </tr>`;
    }).join('');
    $('#board-more').style.display = rows.length > S.limit ? 'block' : 'none';
  }

  async function pick(y) {
    year = y;
    S.limit = 60;
    YD = await A.loadYear(y);
    T = A.teams(y);
    A.yearPicker($('#year-picker'), year, pick);
    $('#page-sub').textContent = `${year} · ${YD.draft.auction ? 'auction' : 'snake'} draft · ${YD.draft.board.length} picks`;
    renderKPIs(); renderSpend(); renderValue(); renderBoard();
  }

  $('#board-more').addEventListener('click', () => { S.limit += 60; renderBoard(); });
  $('#draft-search').addEventListener('input', (e) => { S.q = e.target.value; S.limit = 60; renderBoard(); });

  const qs = new URLSearchParams(location.search);
  await pick(+qs.get('year') || A.years()[0]);
})();
