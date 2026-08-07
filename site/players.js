/* ============ PlayerProfiler — joined to the AFFL database ============ */
(async function () {
  const DATA = await fetch('data.json?v=' + Date.now(), { cache: 'no-store' }).then((r) => r.json());
  const $ = (s) => document.querySelector(s);
  const fmt = (n, d = 0) => n.toLocaleString('en-US', { maximumFractionDigits: d, minimumFractionDigits: d });

  const C = { blue: '#2f7bff', steel: '#3a4a63', grid: '#1b243366', mut: '#7d8aa0', ink: '#eef4ff' };
  Chart.defaults.color = C.mut;
  Chart.defaults.font.family = '"Avenir Next","Segoe UI",-apple-system,sans-serif';
  Chart.defaults.font.size = 11;
  Chart.defaults.plugins.tooltip.backgroundColor = '#05060bf2';
  Chart.defaults.plugins.tooltip.borderColor = '#1c2536';
  Chart.defaults.plugins.tooltip.borderWidth = 1;
  Chart.defaults.plugins.tooltip.titleColor = C.ink;

  const PLAYERS = DATA.nextgen.players;
  const T25 = {};
  DATA.seasons['2025'].teams.forEach((t) => { T25[t.id] = t; });
  const tName = (id) => (T25[id] || { name: '?' }).name;

  const initials = (n) => n.split(' ').map((x) => x[0]).join('').slice(0, 2);
  const hsHTML = (p, cls) => p.hs
    ? `<img class="${cls}" src="${p.hs}" alt="" onerror="this.outerHTML='<div class=&quot;${cls} fb&quot;>${initials(p.name)}</div>'">`
    : `<div class="${cls} fb">${initials(p.name)}</div>`;

  let chart = null;
  let cur = null;

  function loadPlayer(pid, push) {
    const p = PLAYERS.find((x) => x.pid === pid) || PLAYERS[0];
    cur = p;
    if (push) history.pushState(null, '', '?pid=' + p.pid);
    document.title = `${p.name} — PlayerProfiler`;

    // hero
    const stat = (v, l) => `<div class="pp-stat"><b>${v}</b><span>${l}</span></div>`;
    $('#pl-hero').innerHTML = `
      <div class="pl-hero-inner">
        ${hsHTML(p, 'pl-hs')}
        <div class="pl-id">
          <h2 class="pl-name">${p.name}</h2>
          <div class="pl-tags">
            <span class="badge pos-${p.pos}">${p.pos}</span>
            <span class="pl-nfl">${p.nfl || 'NFL'}</span>
            <span class="pl-team">finished with ${tName(p.mainTeam)}</span>
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
          ${stat(`${p.boom}/${p.bust}`, 'boom/bust wks')}
        </div>
      </div>`;

    // journey
    const items = [];
    items.push(p.draft
      ? { i: '🔨', t: `Auctioned for $${p.draft.bid}`, d: `to ${tName(p.draft.teamId)} on draft night` }
      : { i: '🧙', t: 'Undrafted', d: 'entered the AFFL through the waiver wire' });
    const teamsSeen = [...new Set(p.wk.map((w) => w[3]))];
    items.push({ i: '🏠', t: teamsSeen.length > 1 ? `${teamsSeen.length} AFFL homes` : 'One-team player', d: teamsSeen.map(tName).join(' → ') });
    const best = [...p.wk].sort((a, b) => b[1] - a[1])[0];
    if (best) items.push({ i: '💥', t: `Best week: ${fmt(best[1], 1)} pts`, d: `Week ${best[0]}${best[5] ? ' vs ' + best[5] : ''}${best[2] ? '' : ' — left on the bench!'}` });
    items.push({ i: '📊', t: `${fmt(p.stPts, 1)} pts delivered in lineups`, d: `across ${p.starts} start${p.starts === 1 ? '' : 's'}` });
    $('#pl-journey').innerHTML = items.map((x) => `
      <li><div class="story-ico" style="background:#2f7bff18">${x.i}</div>
      <div class="story-txt"><div class="t">${x.t}</div><div class="d">${x.d}</div></div></li>`).join('');

    // game log
    $('#pl-log tbody').innerHTML = p.wk.map((w) => {
      const [wk, pts, st, tid, slot, opp, yds, td, tgt, epa] = w;
      return `<tr class="${st ? '' : 'benched'}">
        <td><strong>W${wk}</strong>${wk > 14 ? ' 🏆' : ''}</td>
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

    // chart
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

  /* ---- database grid ---- */
  const PP = { q: '', pos: 'ALL', limit: 24 };
  function filtered() {
    const q = PP.q.toLowerCase();
    return PLAYERS.filter((p) =>
      (PP.pos === 'ALL' || p.pos === PP.pos) && (!q || p.name.toLowerCase().includes(q)));
  }
  function renderGrid() {
    const rows = filtered();
    $('#pp-grid').innerHTML = rows.slice(0, PP.limit).map((p) => `
      <div class="pp-card${cur && p.pid === cur.pid ? ' cur' : ''}" data-pid="${p.pid}">
        ${hsHTML(p, 'pp-hs')}
        <div>
          <div class="pp-nm">${p.name}</div>
          <div class="pp-sub"><span class="badge pos-${p.pos}">${p.pos}</span> ${p.nfl || ''} · ${tName(p.mainTeam).slice(0, 16)}</div>
        </div>
        <div class="pp-pts"><b>${fmt(p.tot, 1)}</b><span>season pts</span></div>
      </div>`).join('') || '<div class="card-sub">No players match.</div>';
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

  /* ---- boot: deep link from scoreboard/dashboard ---- */
  const pid = +new URLSearchParams(location.search).get('pid');
  loadPlayer(pid || PLAYERS[0].pid, false);
  renderGrid();
  window.addEventListener('popstate', () => {
    const pid2 = +new URLSearchParams(location.search).get('pid');
    if (pid2) { loadPlayer(pid2, false); renderGrid(); }
  });
})();
