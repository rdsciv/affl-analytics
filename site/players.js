/* ============ PlayerProfiler — all seasons ============ */
(async function () {
  const A = window.AFFL;
  const $ = (s) => document.querySelector(s);
  await A.boot();
  A.chartDefaults(Chart);
  const C = A.C;
  const fmt = A.fmt;

  let year = A.years()[0];
  let YD = null, T = {}, cur = null, chart = null;
  const PP = { q: '', pos: 'ALL', limit: 24 };

  const tName = (id) => (T[id] || { name: '?' }).name;

  function loadPlayer(pid, push) {
    const p = YD.players.find((x) => x.pid === pid) || YD.players[0];
    if (!p) {
      $('#pl-hero').innerHTML = A.notice(`No player data stored for ${year}. ESPN retains weekly lineups from 2018 on.`);
      $('#pl-log tbody').innerHTML = '';
      $('#pl-journey').innerHTML = '';
      if ($('#pl-xfp')) $('#pl-xfp').innerHTML = '';
      if (chart) { chart.destroy(); chart = null; }
      return;
    }
    cur = p;
    if (push) history.pushState(null, '', `?year=${year}&pid=${p.pid}`);
    document.title = `${p.name} ${year} — PlayerProfiler`;

    const stat = (v, l) => `<div class="pp-stat"><b>${v}</b><span>${l}</span></div>`;
    $('#pl-hero').innerHTML = `
      <div class="pl-hero-inner">
        ${A.headshotHTML(p, 'pl-hs')}
        <div class="pl-id">
          <h2 class="pl-name">${p.name}</h2>
          <div class="pl-tags">
            <span class="badge pos-${p.pos}">${p.pos}</span>
            <span class="pl-nfl">${p.nfl || 'NFL'}</span>
            <span class="pl-team">${year} · finished with ${tName(p.mainTeam)}</span>
          </div>
        </div>
        <div class="pp-stats pl-tiles">
          ${stat(fmt(p.tot, 1), 'season pts')}
          ${stat(fmt(p.ppg, 1), 'ppg started')}
          ${stat(p.starts, 'affl starts')}
          ${stat(p.cons != null ? Math.round(p.cons * 100) + '%' : '—', 'consistency')}
          ${stat(p.epa != null ? (p.epa >= 0 ? '+' : '') + fmt(p.epa, 1) : '—', 'nfl epa')}
          ${stat(p.wopr != null ? p.wopr.toFixed(2) : '—', 'wopr')}
          ${stat(p.tsh != null ? (p.tsh * 100).toFixed(1) + '%' : '—', 'target share')}
          ${stat(p.cpoe != null ? (p.cpoe >= 0 ? '+' : '') + fmt(p.cpoe, 1) : '—', 'cpoe')}
          ${stat(p.adot != null ? fmt(p.adot, 1) : '—', 'adot')}
          ${stat(p.success != null ? Math.round(p.success * 100) + '%' : '—', 'success')}
          ${stat(p.xtd != null ? fmt(p.xtd, 1) : '—', 'xtd')}
          ${stat(p.tdLuck != null ? (p.tdLuck >= 0 ? '+' : '') + fmt(p.tdLuck, 1) : '—', 'td luck')}
          ${stat(p.fpoe != null ? (p.fpoe >= 0 ? '+' : '') + fmt(p.fpoe, 1) : '—', 'fpoe')}
          ${stat(`${p.boom}/${p.bust}`, 'boom/bust wks')}
        </div>
      </div>`;

    const signed = (v, d) => v == null ? '—' : ((v >= 0 ? '+' : '') + fmt(v, d));
    const pct = (v) => v == null ? '—' : (v * 100).toFixed(1) + '%';
    $('#pl-xfp').innerHTML = [
      stat(p.fp != null ? fmt(p.fp, 1) : '—', 'affl fp'),
      stat(p.xfp != null ? fmt(p.xfp, 1) : '—', 'affl xfp'),
      stat(signed(p.fpoe, 1), 'fpoe'),
      stat(p.fpG != null ? fmt(p.fpG, 1) : '—', 'fp/g'),
      stat(p.xfpG != null ? fmt(p.xfpG, 1) : '—', 'xfp/g'),
      stat(p.stFpoe != null ? signed(p.stFpoe, 1) : '—', 'started fpoe'),
      stat(p.opp != null ? fmt(p.opp, 0) : '—', 'opp'),
      stat(p.wopr != null ? p.wopr.toFixed(2) : '—', 'wopr'),
      stat(pct(p.tsh), 'tgt%'),
      stat(pct(p.ayShare), 'ay%'),
      stat(p.rzOpp != null ? fmt(p.rzOpp, 0) : '—', 'rz opp'),
      stat(p.glOpp != null ? fmt(p.glOpp, 0) : '—', 'gl opp'),
      stat(p.xtd != null ? fmt(p.xtd, 1) : '—', 'xtd'),
      stat(signed(p.tdLuck, 1), 'td luck'),
    ].join('');

    const items = [];
    if (p.draft) {
      items.push(YD.draft.auction
        ? { i: '🔨', t: `Auctioned for $${p.draft.bid}`, d: `to ${tName(p.draft.teamId)}${p.draft.keeper ? ' as a keeper' : ''}` }
        : { i: '🔨', t: `Drafted ${p.draft.round}.${p.draft.overall}`, d: `by ${tName(p.draft.teamId)}` });
    } else {
      items.push({ i: '🧙', t: 'Undrafted', d: 'entered the AFFL through the waiver wire' });
    }
    const seen = [...new Set(p.wk.map((w) => w[3]))];
    items.push({ i: '🏠', t: seen.length > 1 ? `${seen.length} AFFL homes` : 'One-team player', d: seen.map(tName).join(' → ') });
    const best = [...p.wk].sort((a, b) => b[1] - a[1])[0];
    if (best) items.push({ i: '💥', t: `Best week: ${fmt(best[1], 1)} pts`, d: `Week ${best[0]}${best[5] ? ' vs ' + best[5] : ''}${best[2] ? '' : ' — benched!'}` });
    items.push({ i: '📊', t: `${fmt(p.stPts, 1)} pts delivered in lineups`, d: `across ${p.starts} start${p.starts === 1 ? '' : 's'}` });
    $('#pl-journey').innerHTML = items.map((x) => `
      <li><div class="story-ico" style="background:#2f7bff18">${x.i}</div>
      <div class="story-txt"><div class="t">${x.t}</div><div class="d">${x.d}</div></div></li>`).join('');

    $('#pl-log tbody').innerHTML = p.wk.map((w) => {
      const [wk, pts, st, tid, slot, opp, yds, td, tgt, epa] = w;
      return `<tr class="${st ? '' : 'benched'}">
        <td><strong>W${wk}</strong>${wk > YD.regWeeks ? ' 🏆' : ''}</td>
        <td>${opp || '—'}</td>
        <td class="own">${tName(tid)}</td>
        <td><span class="sb-slot ${st ? 'started' : ''}">${slot}</span></td>
        <td><strong>${fmt(pts, 1)}</strong></td>
        <td>${yds != null ? fmt(yds) : '—'}</td>
        <td>${td != null ? td : '—'}</td>
        <td>${tgt != null && p.pos !== 'QB' ? tgt : '—'}</td>
        <td class="${epa > 0 ? 'pos' : epa < 0 ? 'neg' : ''}">${epa != null ? (epa >= 0 ? '+' : '') + epa : '—'}</td>
      </tr>`;
    }).join('');

    if (chart) chart.destroy();
    chart = new Chart($('#pl-chart'), {
      type: 'bar',
      data: {
        labels: p.wk.map((w) => 'W' + w[0]),
        datasets: [{
          data: p.wk.map((w) => w[1]),
          backgroundColor: p.wk.map((w) => w[2] ? '#2f7bffcc' : '#3a4a6388'),
          borderRadius: 3, maxBarThickness: 26,
        }],
      },
      options: {
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: { callbacks: {
            label: (c) => `${fmt(c.parsed.y, 1)} pts · ${p.wk[c.dataIndex][2] ? 'started' : 'benched'} by ${tName(p.wk[c.dataIndex][3])}`,
          } },
        },
        scales: {
          y: { grid: { color: C.grid }, border: { display: false } },
          x: { grid: { display: false }, border: { display: false } },
        },
      },
    });
  }

  function filtered() {
    const q = PP.q.toLowerCase();
    return YD.players.filter((p) =>
      (PP.pos === 'ALL' || p.pos === PP.pos) && (!q || p.name.toLowerCase().includes(q)));
  }

  function renderGrid() {
    const rows = filtered();
    $('#pp-grid').innerHTML = rows.slice(0, PP.limit).map((p) => `
      <div class="pp-card${cur && p.pid === cur.pid ? ' cur' : ''}" data-pid="${p.pid}">
        ${A.headshotHTML(p, 'pp-hs')}
        <div>
          <div class="pp-nm">${p.name}</div>
          <div class="pp-sub"><span class="badge pos-${p.pos}">${p.pos}</span> ${p.nfl || ''} · ${tName(p.mainTeam).slice(0, 16)}</div>
        </div>
        <div class="pp-pts"><b>${fmt(p.tot, 1)}</b><span>season pts</span></div>
      </div>`).join('') ||
      A.notice(YD.players.length ? 'No players match.' :
        `ESPN does not retain weekly lineups for ${year}, so there are no player profiles. Try 2018 or later.`);
    $('#pp-more').style.display = rows.length > PP.limit ? 'block' : 'none';
    document.querySelectorAll('.pp-card').forEach((el) =>
      el.addEventListener('click', () => {
        loadPlayer(+el.dataset.pid, true);
        renderGrid();
        window.scrollTo({ top: 0, behavior: 'smooth' });
      }));
  }

  const POSES = ['ALL', 'QB', 'RB', 'WR', 'TE', 'K', 'DST'];
  $('#pp-filters').innerHTML = POSES.map((p) =>
    `<button class="pp-chip${p === 'ALL' ? ' on' : ''}" data-pos="${p}">${p}</button>`).join('');
  document.querySelectorAll('.pp-chip').forEach((b) =>
    b.addEventListener('click', () => {
      PP.pos = b.dataset.pos; PP.limit = 24;
      document.querySelectorAll('.pp-chip').forEach((x) => x.classList.toggle('on', x === b));
      renderGrid();
    }));
  $('#pp-search').addEventListener('input', (e) => { PP.q = e.target.value; PP.limit = 24; renderGrid(); });
  $('#pp-more').addEventListener('click', () => { PP.limit += 24; renderGrid(); });

  async function pick(y, pid) {
    year = y;
    cur = null;
    PP.limit = 24;
    YD = await A.loadYear(y);
    T = A.teams(y);
    A.yearPicker($('#year-picker'), year, (yy) => pick(yy), (i) => i.players ? '' : '*');
    loadPlayer(pid || (YD.players[0] || {}).pid, false);
    renderGrid();
  }

  const qs = new URLSearchParams(location.search);
  await pick(+qs.get('year') || A.years()[0], +qs.get('pid') || null);
  window.addEventListener('popstate', () => {
    const q2 = new URLSearchParams(location.search);
    pick(+q2.get('year') || year, +q2.get('pid') || null);
  });
})();
