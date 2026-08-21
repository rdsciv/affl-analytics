/* ============ AFFL Analytics ============ */
(async function () {
  const DATA = await (await fetch('data.json?v=' + Date.now(), {cache: 'no-store'})).json();
  const $ = (s) => document.querySelector(s);

  const C = {
    blue: '#2f7bff', blue2: '#47a8ff', ice: '#9fd8ff', steel: '#3a4a63',
    orange: '#ff7a00', fire: '#ff5a1e', gold: '#ffc400', gold2: '#ffcc33',
    green: '#93d500', red: '#ff2d1a',
    mut: '#7d8aa0', ink: '#eef4ff', grid: '#1b243366',
  };

  Chart.defaults.color = C.mut;
  Chart.defaults.font.family = '"Avenir Next","Segoe UI",-apple-system,sans-serif';
  Chart.defaults.font.size = 11;
  Chart.defaults.borderColor = C.grid;
  Chart.defaults.plugins.tooltip.backgroundColor = '#05060bf2';
  Chart.defaults.plugins.tooltip.borderColor = '#1c2536';
  Chart.defaults.plugins.tooltip.borderWidth = 1;
  Chart.defaults.plugins.tooltip.padding = 10;
  Chart.defaults.plugins.tooltip.titleColor = C.ink;

  const charts = {};
  function mkChart(id, cfg) {
    if (charts[id]) charts[id].destroy();
    charts[id] = new Chart($(id), cfg);
    return charts[id];
  }
  function grad(ctx, area, top, bottom) {
    const g = ctx.createLinearGradient(0, area.top, 0, area.bottom);
    g.addColorStop(0, top); g.addColorStop(1, bottom);
    return g;
  }
  const fmt = (n, d = 0) => n.toLocaleString('en-US', { maximumFractionDigits: d, minimumFractionDigits: d });
  const memberName = (id) => DATA.members[id] || '—';
  const firstName = (id) => memberName(id).split(' ')[0];
  const shortOwner = (id) => {
    const p = memberName(id).split(' ');
    return p.length > 1 ? `${p[0]} ${p[1][0]}.` : p[0];
  };

  function avatarHTML(team, size) {
    const initial = (team.name || '?').replace(/[^A-Za-z0-9]/g, '').charAt(0).toUpperCase() || '?';
    const cls = size === 'mini' ? 'mini' : 'avatar';
    if (team.logo && /^(https?:|logos\/)/.test(team.logo)) {
      return `<img class="${cls}" src="${team.logo}" alt="" loading="lazy"
        onerror="if(this.parentNode)this.outerHTML='<div class=&quot;${cls} ${size === 'mini' ? '' : 'fallback'}&quot;>${initial}</div>'">`;
    }
    return `<div class="${cls} ${size === 'mini' ? '' : 'fallback'}">${initial}</div>`;
  }

  function ring(pct, color, label) {
    const r = 30, circ = 2 * Math.PI * r;
    const off = circ * (1 - Math.min(1, Math.max(0, pct)));
    return `<div class="ring">
      <svg width="74" height="74" viewBox="0 0 74 74">
        <circle cx="37" cy="37" r="${r}" fill="none" stroke="#ffffff12" stroke-width="7"/>
        <circle cx="37" cy="37" r="${r}" fill="none" stroke="${color}" stroke-width="7"
          stroke-linecap="round" stroke-dasharray="${circ}" stroke-dashoffset="${off}"/>
      </svg>
      <div class="pct" style="color:${color}">${label}</div>
    </div>`;
  }

  /* ================= state ================= */
  const years = Object.keys(DATA.seasons).map(Number).sort((a, b) => a - b);
  const qsYear = +new URLSearchParams(location.search).get('year');
  let curYear = years.includes(qsYear) ? qsYear : DATA.latest;
  let spotlightId = null;

  const S = () => DATA.seasons[String(curYear)];
  const teamById = (id) => S().teams.find((t) => t.id === id);

  /* ================= season picker ================= */
  function renderPicker() {
    $('#season-picker').innerHTML = years
      .map((y) => `<button class="season-chip${y === curYear ? ' on' : ''}" data-y="${y}">${y}</button>`)
      .join('');
    document.querySelectorAll('.season-chip').forEach((b) =>
      b.addEventListener('click', () => {
        curYear = +b.dataset.y;
        history.replaceState(null, '', '?year=' + curYear);
        spotlightId = null;
        PP.q = ''; PP.pos = 'ALL'; PP.limit = 20;
        const s = $('#pp-search'); if (s) s.value = '';
        document.querySelectorAll('.pp-chip').forEach((x) =>
          x.classList.toggle('on', x.dataset.pos === 'ALL'));
        renderSeason();
      }));
  }

  /* ================= KPI row ================= */
  function renderKPIs() {
    const s = S();
    const champ = teamById(s.champion);
    const ptsLeader = [...s.teams].sort((a, b) => b.pf - a.pf)[0];
    const lucky = [...s.teams].sort((a, b) => b.luck - a.luck)[0];
    const unlucky = [...s.teams].sort((a, b) => a.luck - b.luck)[0];
    const apPct = (t) => t.allplayW / Math.max(1, t.allplayW + t.allplayL);

    const cards = [
      champ && {
        n: '01 · CROWN', color: C.gold, title: 'The Champion',
        pct: champ.wins / Math.max(1, champ.wins + champ.losses),
        label: Math.round((champ.wins / Math.max(1, champ.wins + champ.losses)) * 100) + '%',
        desc: `<strong>${champ.name}</strong> · ${champ.wins}-${champ.losses} · ${firstName(champ.owner)} takes the crown`,
      },
      {
        n: '02 · FIREPOWER', color: C.fire, title: 'Points Leader',
        pct: apPct(ptsLeader), label: fmt(ptsLeader.pf),
        desc: `<strong>${ptsLeader.name}</strong> · ${fmt(ptsLeader.avgPts, 1)} per week, ${Math.round(apPct(ptsLeader) * 100)}% all-play`,
      },
      {
        n: '03 · FORTUNE', color: C.green, title: 'Luck Lottery',
        pct: Math.min(1, lucky.regWins / Math.max(0.1, lucky.expWins) / 2),
        label: '+' + fmt(lucky.luck, 1),
        desc: `<strong>${lucky.name}</strong> won ${fmt(lucky.luck, 1)} more games than their scores deserved`,
      },
      {
        n: '04 · MISFORTUNE', color: C.red, title: 'Snakebitten',
        pct: Math.min(1, unlucky.regWins / Math.max(0.1, unlucky.expWins)),
        label: fmt(unlucky.luck, 1),
        desc: `<strong>${unlucky.name}</strong> robbed of ${fmt(Math.abs(unlucky.luck), 1)} wins by the schedule`,
      },
    ].filter(Boolean);

    $('#kpi-row').innerHTML = cards.map((c) => `
      <div class="card kpi">
        ${ring(c.pct, c.color, c.label)}
        <div>
          <div class="kpi-num" style="color:${c.color}">${c.n}</div>
          <div class="kpi-title">${c.title}</div>
          <div class="kpi-desc">${c.desc}</div>
        </div>
      </div>`).join('');
  }

  /* ================= area chart ================= */
  function renderArea() {
    const s = S();
    const spot = teamById(spotlightId) || teamById(s.champion) || s.teams[0];
    spotlightId = spot.id;

    const sel = $('#spotlight-team');
    sel.innerHTML = [...s.teams].sort((a, b) => a.name.localeCompare(b.name))
      .map((t) => `<option value="${t.id}"${t.id === spot.id ? ' selected' : ''}>${t.name}</option>`).join('');
    sel.onchange = () => { spotlightId = +sel.value; renderArea(); };

    const labels = s.regWeeks.map((w) => 'W' + w);
    mkChart('#area-chart', {
      type: 'line',
      data: {
        labels,
        datasets: [
          {
            label: 'League high', data: s.wkMax, borderColor: '#ff8a3d', borderWidth: 2,
            pointRadius: 0, tension: 0.45, fill: 'origin', order: 3,
            backgroundColor: (c) => c.chart.chartArea ? grad(c.chart.ctx, c.chart.chartArea, '#ff5a1e73', '#ff5a1e08') : '#ff5a1e33',
          },
          {
            label: 'League average', data: s.wkAvg, borderColor: C.blue, borderWidth: 2,
            pointRadius: 0, tension: 0.45, fill: 'origin', order: 2,
            backgroundColor: (c) => c.chart.chartArea ? grad(c.chart.ctx, c.chart.chartArea, '#2f7bff80', '#2f7bff08') : '#2f7bff33',
          },
          {
            label: 'League low', data: s.wkMin, borderColor: '#3a4a63', borderWidth: 1.5,
            pointRadius: 0, tension: 0.45, fill: 'origin', order: 1,
            backgroundColor: (c) => c.chart.chartArea ? grad(c.chart.ctx, c.chart.chartArea, '#12182699', '#12182620') : '#12182666',
          },
          {
            label: spot.name, data: spot.weekly, borderColor: C.gold, borderWidth: 2.5,
            pointRadius: 3.5, pointBackgroundColor: C.gold, pointBorderColor: '#05060b',
            pointBorderWidth: 1.5, tension: 0.35, fill: false, order: 0,
          },
        ],
      },
      options: {
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: { legend: { labels: { boxWidth: 10, boxHeight: 10, usePointStyle: true, pointStyle: 'circle' } } },
        scales: {
          y: { grid: { color: C.grid }, border: { display: false }, ticks: { callback: (v) => v + ' pts' } },
          x: { grid: { display: false }, border: { display: false } },
        },
      },
    });
  }

  /* ================= side card ================= */
  function renderSide() {
    const s = S();
    const champ = teamById(s.champion);
    const tn = (id) => (teamById(id) || { name: '?' }).name;

    $('#champ-spot').innerHTML = champ ? `
      ${avatarHTML(champ)}
      <div>
        <div class="tag">🏆 League Champion</div>
        <div class="nm">${champ.name}</div>
        <div class="rec">${memberName(champ.owner)} · ${champ.wins}-${champ.losses} · ${fmt(champ.pf)} PF</div>
      </div>` : '<div class="rec">Season in progress</div>';

    const items = [
      { i: '💥', bg: '#ff5a1e22', t: 'Best single week', d: `${tn(s.bestWeek.teamId)} · Week ${s.bestWeek.week}`, v: fmt(s.bestWeek.pts, 1), c: '#ff8a3d' },
      { i: '🥶', bg: '#2f7bff22', t: 'Worst single week', d: `${tn(s.worstWeek.teamId)} · Week ${s.worstWeek.week}`, v: fmt(s.worstWeek.pts, 1), c: C.blue2 },
      { i: '⚔️', bg: '#9fd8ff22', t: 'Closest call', d: `${tn(s.closest.winnerId)} over ${tn(s.closest.loserId)} · W${s.closest.week}`, v: '+' + fmt(s.closest.margin, 2), c: C.ice },
      { i: '🔨', bg: '#ffc40022', t: 'Biggest beatdown', d: `${tn(s.blowout.winnerId)} over ${tn(s.blowout.loserId)} · W${s.blowout.week}`, v: '+' + fmt(s.blowout.margin, 1), c: C.gold },
    ];
    $('#story-list').innerHTML = items.map((x) => `
      <li>
        <div class="story-ico" style="background:${x.bg}">${x.i}</div>
        <div class="story-txt"><div class="t">${x.t}</div><div class="d">${x.d}</div></div>
        <div class="story-val" style="color:${x.c}">${x.v}</div>
      </li>`).join('');

    $('#side-total').textContent = fmt(s.totalPts) + ' pts';
    document.querySelector('.side-total span').textContent = 'reg-season total';
    $('#hs-total').textContent = fmt(s.totalPts);
    const games = s.teams.reduce((a, t) => a + t.wins + t.losses + t.ties, 0) / 2;
    $('#hs-games').textContent = fmt(games);
    $('#hdr-sub').textContent = `${s.teams.length}-team league · ${curYear} season · est. 2014`;
  }

  /* ================= bar chart ================= */
  function renderBar() {
    const s = S();
    const rows = [...s.teams].sort((a, b) => b.avgPts - a.avgPts);
    mkChart('#bar-chart', {
      type: 'bar',
      data: {
        labels: rows.map((t) => t.name.length > 14 ? t.name.slice(0, 13) + '…' : t.name),
        datasets: [{
          data: rows.map((t) => t.avgPts),
          borderRadius: 6, maxBarThickness: 34,
          backgroundColor: (c) => {
            if (!c.chart.chartArea) return C.orange;
            const isChamp = rows[c.dataIndex].id === s.champion;
            return grad(c.chart.ctx, c.chart.chartArea,
              isChamp ? C.gold : C.blue, isChamp ? '#ffc40018' : '#2f7bff14');
          },
        }],
      },
      options: {
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: { callbacks: { label: (c) => `${fmt(c.parsed.y, 1)} pts / week` } },
        },
        scales: {
          y: { grid: { color: C.grid }, border: { display: false } },
          x: { grid: { display: false }, border: { display: false }, ticks: { maxRotation: 55, minRotation: 40 } },
        },
      },
    });
  }

  /* ================= race chart ================= */
  function renderRace() {
    const s = S();
    const top4 = [...s.teams].sort((a, b) => (a.finalRank || 99) - (b.finalRank || 99)).slice(0, 4);
    const colors = [C.blue, C.gold, C.fire, C.green];
    mkChart('#race-chart', {
      type: 'line',
      data: {
        labels: s.regWeeks.map((w) => 'W' + w),
        datasets: top4.map((t, i) => ({
          label: t.name.length > 16 ? t.name.slice(0, 15) + '…' : t.name,
          data: t.cumWins, borderColor: colors[i], backgroundColor: colors[i],
          borderWidth: 2, pointRadius: 3, pointBorderColor: '#12142e', pointBorderWidth: 1.5,
          tension: 0.2,
        })),
      },
      options: {
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: { legend: { labels: { boxWidth: 10, boxHeight: 10, usePointStyle: true, pointStyle: 'circle' } } },
        scales: {
          y: { grid: { color: C.grid }, border: { display: false }, ticks: { stepSize: 2 }, title: { display: true, text: 'wins' } },
          x: { grid: { display: false }, border: { display: false } },
        },
      },
    });
  }

  /* ================= standings ================= */
  function renderStandings() {
    const s = S();
    const rows = [...s.teams].sort((a, b) => (a.finalRank || 99) - (b.finalRank || 99));
    const pillCls = (r) => r === 1 ? 'gold' : r === 2 ? 'slv' : r === 3 ? 'brz' : '';
    $('#standings-tbl tbody').innerHTML = rows.map((t) => `
      <tr>
        <td><span class="rank-pill ${pillCls(t.finalRank)}">${t.finalRank || '–'}</span></td>
        <td><div class="team-cell">${avatarHTML(t, 'mini')}<div>${t.name}<div class="own">${memberName(t.owner)}</div></div></div></td>
        <td><strong>${t.wins}-${t.losses}${t.ties ? '-' + t.ties : ''}</strong></td>
        <td>${fmt(t.pf, 1)}</td>
        <td>${fmt(t.pa, 1)}</td>
        <td>${fmt(t.avgPts, 1)}</td>
        <td class="own">${t.allplayW}-${t.allplayL}</td>
      </tr>`).join('');
  }

  /* ================= luck chart ================= */
  function renderLuck() {
    const s = S();
    const rows = [...s.teams].sort((a, b) => b.luck - a.luck);
    mkChart('#luck-chart', {
      type: 'bar',
      data: {
        labels: rows.map((t) => t.name.length > 18 ? t.name.slice(0, 17) + '…' : t.name),
        datasets: [{
          data: rows.map((t) => t.luck),
          backgroundColor: rows.map((t) => t.luck >= 0 ? '#93d500cc' : '#ff2d1acc'),
          borderRadius: 5, maxBarThickness: 16,
        }],
      },
      options: {
        indexAxis: 'y',
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: { callbacks: { label: (c) => `${c.parsed.x >= 0 ? '+' : ''}${fmt(c.parsed.x, 2)} wins vs expectation` } },
        },
        scales: {
          x: { grid: { color: C.grid }, border: { display: false }, ticks: { callback: (v) => (v > 0 ? '+' : '') + v } },
          y: { grid: { display: false }, border: { display: false } },
        },
      },
    });
  }

  /* ================= all-time (static) ================= */
  function renderTimeline() {
    $('#timeline').innerHTML = DATA.timeline.map((t) => `
      <div class="tl-card">
        <div class="tl-year">${t.year}</div>
        <div class="tl-team">🏆 ${t.team}</div>
        <div class="tl-own">${t.owner} · ${t.record}</div>
      </div>`).join('');
  }

  function renderFranchises() {
    const rows = DATA.franchises;
    $('#franchise-tbl tbody').innerHTML = rows.map((f) => `
      <tr>
        <td><strong>${f.ownerName}</strong>${f.active ? '' : ' <span class="own">(inactive)</span>'}</td>
        <td class="own">${f.currentName}</td>
        <td>${f.seasons}</td>
        <td>${f.wins}-${f.losses}${f.ties ? '-' + f.ties : ''}</td>
        <td class="${f.winPct >= 0.5 ? 'pos' : 'neg'}"><strong>${(f.winPct * 100).toFixed(1)}%</strong></td>
        <td>${'🏆'.repeat(f.titles) || '–'}</td>
        <td>${fmt(f.pf)}</td>
      </tr>`).join('');
  }

  function renderEra() {
    const active = DATA.franchises.filter((f) => f.active);
    const top6 = [...active].sort((a, b) => b.pf - a.pf).slice(0, 6);
    document.querySelector('#era-chart').closest('.card').querySelector('.card-sub').textContent =
      'points per season · top six active franchises by all-time points';
    const colors = [C.blue, C.gold, C.fire, C.green, C.ice, C.orange];
    mkChart('#era-chart', {
      type: 'line',
      data: {
        labels: years,
        datasets: top6.map((f, i) => ({
          label: f.ownerName.split(' ')[0],
          data: years.map((y) => f.pfBySeason[y] ?? null),
          borderColor: colors[i], backgroundColor: colors[i],
          borderWidth: 2, pointRadius: 2.5, tension: 0.3, spanGaps: true,
        })),
      },
      options: {
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: { legend: { labels: { boxWidth: 10, boxHeight: 10, usePointStyle: true, pointStyle: 'circle' } } },
        scales: {
          y: { grid: { color: C.grid }, border: { display: false } },
          x: { grid: { display: false }, border: { display: false } },
        },
      },
    });
  }

  function renderH2H() {
    const owners = DATA.activeOwners
      .slice()
      .sort((a, b) => DATA.franchises.findIndex((f) => f.owner === a) - DATA.franchises.findIndex((f) => f.owner === b));
    const rec = {};
    DATA.h2h.forEach((r) => {
      rec[r.a + '|' + r.b] = [r.aW, r.bW];
      rec[r.b + '|' + r.a] = [r.bW, r.aW];
    });
    const head = '<tr><th></th>' + owners.map((o) => `<th>${shortOwner(o)}</th>`).join('') + '</tr>';
    const body = owners.map((row) => {
      const cells = owners.map((col) => {
        if (row === col) return '<td class="h2h-x">—</td>';
        const r = rec[row + '|' + col];
        if (!r) return '<td class="h2h-x">·</td>';
        const cls = r[0] > r[1] ? 'h2h-w' : r[0] < r[1] ? 'h2h-l' : 'h2h-e';
        return `<td><span class="h2h-cell ${cls}">${r[0]}–${r[1]}</span></td>`;
      }).join('');
      return `<tr><td>${shortOwner(row)}</td>${cells}</tr>`;
    }).join('');
    $('#h2h-tbl').innerHTML = head + body;
  }

  /* ================= next gen lab (per season) =================
     NG and T25 are reassigned every time the season changes; every renderer
     below reads them, so all lower sections follow the picker. */
  let NG = null;
  let T25 = {};
  const tName25 = (id) => (T25[id] || { name: '?' }).name;
  const shortName25 = (id) => {
    const n = tName25(id);
    return n.length > 17 ? n.slice(0, 16) + '…' : n;
  };
  const yearCache = new Map();
  async function loadYearBundle(y) {
    if (!yearCache.has(y)) {
      yearCache.set(y, await fetch(`years/${y}.json?v=` + Date.now(),
        { cache: 'no-store' }).then((r) => r.json()));
    }
    NG = yearCache.get(y);
    T25 = {};
    (DATA.seasons[String(y)] || { teams: [] }).teams.forEach((t) => { T25[t.id] = t; });
    return NG;
  }
  const noLineups = (msg) =>
    `<div class="notice">${msg || `ESPN does not retain weekly lineups for ${curYear}, so this needs 2018 or later.`}</div>`;
  /** Hide a chart card's canvas and show a notice in its place. Safe to call
      repeatedly — on a second no-data season the canvas is already gone. */
  function chartNotice(sel, msg) {
    const id = sel.slice(1);
    const wrap = document.querySelector(`[data-canvas="${id}"]`)
      || ($(sel) && $(sel).closest('.chart-wrap'));
    if (!wrap) return;
    if (charts[sel]) { charts[sel].destroy(); delete charts[sel]; }
    wrap.innerHTML = noLineups(msg);
    wrap.classList.add('as-notice');
  }
  /** Restore a canvas that a previous season replaced with a notice. */
  function ensureCanvas(sel) {
    const id = sel.slice(1);
    if ($(sel)) return true;
    const wrap = document.querySelector(`[data-canvas="${id}"]`);
    if (!wrap) return false;
    wrap.classList.remove('as-notice');
    wrap.innerHTML = `<canvas id="${id}"></canvas>`;
    return true;
  }

  function renderLineupIQ() {
    if (!NG.hasRosters || !NG.lineupIQ.length) return chartNotice('#lineup-chart');
    if (!ensureCanvas('#lineup-chart')) return;
    const rows = NG.lineupIQ;
    mkChart('#lineup-chart', {
      type: 'bar',
      data: {
        labels: rows.map((r) => shortName25(r.teamId)),
        datasets: [
          {
            label: 'Points started', data: rows.map((r) => r.actual),
            backgroundColor: '#2f7bffcc', borderRadius: 4, maxBarThickness: 15, stack: 's',
          },
          {
            label: 'Left on bench', data: rows.map((r) => r.wasted),
            backgroundColor: '#ff2d1abb', borderRadius: 4, maxBarThickness: 15, stack: 's',
          },
        ],
      },
      options: {
        indexAxis: 'y',
        maintainAspectRatio: false,
        plugins: {
          legend: { labels: { boxWidth: 10, boxHeight: 10, usePointStyle: true, pointStyle: 'circle' } },
          tooltip: { callbacks: {
            afterBody: (items) => {
              const r = rows[items[0].dataIndex];
              return `lineup efficiency ${(r.eff * 100).toFixed(1)}% · ${r.perfect} perfect week${r.perfect === 1 ? '' : 's'}`;
            },
          } },
        },
        scales: {
          x: { stacked: true, grid: { color: C.grid }, border: { display: false } },
          y: { stacked: true, grid: { display: false }, border: { display: false } },
        },
      },
    });
  }

  function renderDraft() {
    const d = NG.draftValue || { steals: [], busts: [], teamEff: [] };
    const auction = NG.draft.auction;
    if (!d.steals.length) {
      $('#steals-tbl tbody').innerHTML =
        `<tr><td class="own">No scoring data stored for ${curYear} — see the Draft page for the board.</td></tr>`;
      $('#busts-tbl tbody').innerHTML = '';
      $('#draft-note').innerHTML =
        `${NG.draft.board.length} picks recorded (${auction ? 'auction' : 'snake'}), but ESPN keeps no weekly scoring this far back, so returns can't be graded.`;
      return;
    }
    // points above replacement, from v_draft_value
    const row = (p, cls) => `
      <tr>
        <td><strong>${p.name}</strong> <span class="badge pos-${p.pos}">${p.pos}</span><div class="own">${shortName25(p.tid)}</div></td>
        <td>${auction ? '$' + (p.bid || 0) : '#' + p.overall}</td>
        <td><span class="badge ${cls}">${p.par >= 0 ? '+' : ''}${fmt(p.par, 0)} PAR</span></td>
      </tr>`;
    $('#steals-tbl tbody').innerHTML = d.steals.slice(0, 5).map((p) => row(p, 'steal')).join('');
    $('#busts-tbl tbody').innerHTML = d.busts.slice(0, 5).map((p) => row(p, 'bust')).join('');
    const best = d.teamEff[0], worst = d.teamEff[d.teamEff.length - 1];
    if (!best) { $('#draft-note').innerHTML = ''; return; }
    $('#draft-note').innerHTML = auction
      ? `Sharpest auction: <strong>${tName25(best.teamId)}</strong> — ${fmt(best.par, 0)} points above replacement ` +
        `on a $${fmt(best.spent)} board (${best.parPerDollar}/$). ` +
        `Loosest wallet: <strong>${tName25(worst.teamId)}</strong> at ${worst.parPerDollar}/$.`
      : `Best haul: <strong>${tName25(best.teamId)}</strong> pulled ${fmt(best.par, 0)} points above replacement out of their picks.`;
  }

  function renderDNA() {
    if (!NG.hasRosters || !Object.keys(NG.posDNA).length) return chartNotice('#dna-chart');
    if (!ensureCanvas('#dna-chart')) return;
    const order = Object.keys(NG.posDNA).map(Number).sort((a, b) =>
      ((T25[a] || {}).finalRank || 99) - ((T25[b] || {}).finalRank || 99));
    const POS_COLORS = { QB: C.blue, RB: C.green, WR: C.orange, TE: C.gold, K: C.ice, DST: C.steel };
    mkChart('#dna-chart', {
      type: 'bar',
      data: {
        labels: order.map(shortName25),
        datasets: Object.keys(POS_COLORS).map((p) => ({
          label: p, data: order.map((tid) => (NG.posDNA[String(tid)] || {})[p] || 0),
          backgroundColor: POS_COLORS[p], stack: 'dna', maxBarThickness: 34,
        })),
      },
      options: {
        maintainAspectRatio: false,
        plugins: { legend: { labels: { boxWidth: 10, boxHeight: 10, usePointStyle: true, pointStyle: 'circle' } } },
        scales: {
          x: { stacked: true, grid: { display: false }, border: { display: false }, ticks: { maxRotation: 55, minRotation: 40 } },
          y: { stacked: true, grid: { color: C.grid }, border: { display: false } },
        },
      },
    });
  }

  function renderEPA() {
    if (!NG.hasRosters || !NG.franchiseAdv.length) return chartNotice('#epa-chart');
    if (!ensureCanvas('#epa-chart')) return;
    const rows = NG.franchiseAdv;
    mkChart('#epa-chart', {
      type: 'bar',
      data: {
        labels: rows.map((r) => shortName25(r.teamId)),
        datasets: [{
          data: rows.map((r) => r.epa),
          backgroundColor: rows.map((r) => r.epa >= 0 ? '#47a8ffcc' : '#ff2d1acc'),
          borderRadius: 4, maxBarThickness: 16,
        }],
      },
      options: {
        indexAxis: 'y',
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: { callbacks: {
            label: (c) => `${fmt(c.parsed.x, 1)} EPA from starters`,
            afterBody: (items) => {
              const r = rows[items[0].dataIndex];
              return `${fmt(r.air)} air yards · avg WOPR ${r.wopr}`;
            },
          } },
        },
        scales: {
          x: { grid: { color: C.grid }, border: { display: false } },
          y: { grid: { display: false }, border: { display: false } },
        },
      },
    });
  }

  function rk(n) {
    return n == null ? '' : ` <span class="rk">#${n}</span>`;
  }

  function renderSkillRadar() {
    const sr = NG.skillRadar;
    if (!sr || !sr.teams || !sr.teams.length) {
      $('#radar-tbl tbody').innerHTML =
        `<tr><td colspan="12">${noLineups('Skill Radar needs weekly lineups (2018+) and nflverse PBP.')}</td></tr>`;
      return;
    }
    const cell = (v, digits, rank, cls) => {
      if (v == null) return `<td>—</td>`;
      const shown = typeof v === 'number' ? fmt(v, digits) : v;
      return `<td class="${cls || ''}">${shown}${rk(rank)}</td>`;
    };
    $('#radar-tbl tbody').innerHTML = sr.teams.map((t) => `
      <tr>
        <td><div class="team-cell">${avatarHTML(T25[t.teamId] || { name: '?' }, 'mini')}<div>${tName25(t.teamId)}</div></div></td>
        ${cell(t.passYds, 0, t.passYdsRk)}
        ${cell(t.passTd, 0, t.passTdRk)}
        ${cell(t.compPct, 1, t.compPctRk)}
        ${cell(t.rushYds, 0, t.rushYdsRk)}
        ${cell(t.ypc, 2, t.ypcRk)}
        ${cell(t.recYds, 0, t.recYdsRk)}
        ${cell(t.rec, 0, t.recRk)}
        ${cell(t.ypr, 2, t.yprRk)}
        ${cell(t.epa, 1, t.epaRk, t.epa >= 0 ? 'pos' : 'neg')}
        ${cell(t.cpoe, 1, t.cpoeRk, t.cpoe >= 0 ? 'pos' : 'neg')}
        ${cell(t.tdLuck, 1, null, t.tdLuck >= 0 ? 'pos' : 'neg')}
      </tr>`).join('');
  }

  function renderFPOE() {
    const rows = ((NG.afflFantasy || {}).started || []).slice(0, 12);
    if (!rows.length) {
      $('#fpoe-tbl tbody').innerHTML =
        `<tr><td colspan="12">${noLineups('AFFL FPOE needs weekly lineups (2018+) and nflverse PBP.')}</td></tr>`;
      return;
    }
    const pct = (v) => v == null ? '—' : (v * 100).toFixed(1) + '%';
    const signed = (v) => v == null ? '—' : ((v >= 0 ? '+' : '') + fmt(v, 1));
    $('#fpoe-tbl tbody').innerHTML = rows.map((p) => `
      <tr>
        <td><strong>${p.name}</strong></td>
        <td><span class="badge pos-${p.pos}">${p.pos}</span></td>
        <td>${p.starts ?? '—'}</td>
        <td>${p.fp != null ? fmt(p.fp, 1) : '—'}</td>
        <td>${p.xfp != null ? fmt(p.xfp, 1) : '—'}</td>
        <td class="${p.fpoe >= 0 ? 'pos' : 'neg'}">${signed(p.fpoe)}</td>
        <td>${p.wopr != null ? p.wopr.toFixed(2) : '—'}</td>
        <td>${pct(p.tsh)}</td>
        <td>${pct(p.ayShare)}</td>
        <td>${p.rzOpp != null ? fmt(p.rzOpp, 0) : '—'}</td>
        <td>${p.xtd != null ? fmt(p.xtd, 1) : '—'}</td>
        <td class="${p.tdLuck >= 0 ? 'pos' : 'neg'}">${signed(p.tdLuck)}</td>
      </tr>`).join('');
  }

  function renderSpotlight() {
    if (!NG.spotlight.length) {
      $('#spotlight-tbl tbody').innerHTML =
        `<tr><td colspan="8">${noLineups()}</td></tr>`;
      return;
    }
    $('#spotlight-tbl tbody').innerHTML = NG.spotlight.map((p, i) => `
      <tr>
        <td><strong>${p.name}</strong>${i === 0 ? ' 👑' : ''}</td>
        <td><span class="badge pos-${p.pos}">${p.pos}</span></td>
        <td class="own">${tName25(p.teamId)}</td>
        <td><strong>${fmt(p.pts, 1)}</strong></td>
        <td>${fmt(p.ppg, 1)}</td>
        <td class="${p.epa >= 0 ? 'pos' : 'neg'}">${p.epa >= 0 ? '+' : ''}${fmt(p.epa, 1)}</td>
        <td>${p.wopr != null ? p.wopr.toFixed(2) : '—'}</td>
        <td>${p.tsh != null ? (p.tsh * 100).toFixed(1) + '%' : '—'}</td>
      </tr>`).join('');
  }

  /* ================= player profiler ================= */
  const PP = { q: '', pos: 'ALL', limit: 20 };
  let profilerWired = false;

  function ppCardHTML(p, i) {
    const hs = p.hs
      ? `<img class="pp-hs" src="${p.hs}" alt="" loading="lazy" onerror="if(this.parentNode)this.outerHTML='<div class=&quot;pp-hs fb&quot;>${p.name.split(' ').map(x=>x[0]).join('').slice(0,2)}</div>'">`
      : `<div class="pp-hs fb">${p.name.split(' ').map(x => x[0]).join('').slice(0, 2)}</div>`;
    return `<div class="pp-card" data-pid="${p.pid}">
      ${hs}
      <div>
        <div class="pp-nm">${p.name}</div>
        <div class="pp-sub"><span class="badge pos-${p.pos}">${p.pos}</span> ${p.nfl || ''} · ${shortName25(p.mainTeam)}</div>
      </div>
      <div class="pp-pts"><b>${fmt(p.tot, 1)}</b><span>season pts</span></div>
    </div>`;
  }

  function ppFiltered() {
    const q = PP.q.toLowerCase();
    return (NG.players || []).filter((p) =>
      (PP.pos === 'ALL' || p.pos === PP.pos) &&
      (!q || p.name.toLowerCase().includes(q)));
  }

  function renderProfiler() {
    const rows = ppFiltered();
    $('#pp-grid').innerHTML = rows.slice(0, PP.limit).map(ppCardHTML).join('') ||
      (NG.players && NG.players.length ? '<div class="card-sub">No players match.</div>' : noLineups());
    $('#pp-more').style.display = rows.length > PP.limit ? 'block' : 'none';
    document.querySelectorAll('.pp-card').forEach((el) =>
      el.addEventListener('click', () => openProfile(+el.dataset.pid)));
  }

  function initProfiler() {
    if (profilerWired) { renderProfiler(); return; }
    profilerWired = true;
    const POSES = ['ALL', 'QB', 'RB', 'WR', 'TE', 'K', 'DST'];
    $('#pp-filters').innerHTML = POSES.map((p) =>
      `<button class="pp-chip${p === PP.pos ? ' on' : ''}" data-pos="${p}">${p}</button>`).join('');
    document.querySelectorAll('.pp-chip').forEach((b) =>
      b.addEventListener('click', () => {
        PP.pos = b.dataset.pos; PP.limit = 20;
        document.querySelectorAll('.pp-chip').forEach((x) => x.classList.toggle('on', x === b));
        renderProfiler();
      }));
    $('#pp-search').addEventListener('input', (e) => { PP.q = e.target.value; PP.limit = 20; renderProfiler(); });
    $('#pp-more').addEventListener('click', () => { PP.limit += 20; renderProfiler(); });
    renderProfiler();
  }

  let sparkChart = null;
  function openProfile(pid) {
    const p = (NG.players || []).find((x) => x.pid === pid);
    if (!p) return;
    const ov = document.createElement('div');
    ov.className = 'pp-overlay';
    const hs = p.hs
      ? `<img class="pp-hs" src="${p.hs}" alt="" onerror="if(this.parentNode)this.outerHTML='<div class=&quot;pp-hs fb&quot;>${p.name.split(' ').map(x=>x[0]).join('').slice(0,2)}</div>'">`
      : `<div class="pp-hs fb">${p.name.split(' ').map(x => x[0]).join('').slice(0, 2)}</div>`;
    const draft = p.draft
      ? (NG.draft.auction
          ? `Auctioned to <strong>${tName25(p.draft.teamId)}</strong> for <strong>$${p.draft.bid}</strong>`
          : `Drafted <strong>${p.draft.round}.${String(p.draft.overall).padStart(2, '0')}</strong> by <strong>${tName25(p.draft.teamId)}</strong>`)
      : '<strong>Undrafted</strong> — a waiver-wire pickup';
    const stat = (v, l) => `<div class="pp-stat"><b>${v}</b><span>${l}</span></div>`;
    ov.innerHTML = `<div class="pp-modal">
      <div class="pp-mhead">
        ${hs}
        <div>
          <h3>${p.name}</h3>
          <div class="pp-sub"><span class="badge pos-${p.pos}">${p.pos}</span> ${p.nfl || 'NFL'} · finished with ${tName25(p.mainTeam)}</div>
        </div>
        <button class="pp-close" aria-label="Close">✕</button>
      </div>
      <div class="pp-stats">
        ${stat(fmt(p.tot, 1), 'season pts')}
        ${stat(fmt(p.ppg, 1), 'ppg started')}
        ${stat(p.starts, 'starts')}
        ${stat(p.cons != null ? Math.round(p.cons * 100) + '%' : '—', 'consistency')}
        ${stat(p.epa != null ? (p.epa >= 0 ? '+' : '') + fmt(p.epa, 1) : '—', 'nfl epa')}
        ${stat(p.wopr != null ? p.wopr.toFixed(2) : '—', 'wopr')}
        ${stat(p.tsh != null ? (p.tsh * 100).toFixed(1) + '%' : '—', 'target share')}
        ${stat(p.cpoe != null ? (p.cpoe >= 0 ? '+' : '') + fmt(p.cpoe, 1) : '—', 'cpoe')}
        ${stat(p.adot != null ? fmt(p.adot, 1) : '—', 'adot')}
        ${stat(p.xtd != null ? fmt(p.xtd, 1) : '—', 'xtd')}
        ${stat(p.tdLuck != null ? (p.tdLuck >= 0 ? '+' : '') + fmt(p.tdLuck, 1) : '—', 'td luck')}
        ${stat(p.fpoe != null ? (p.fpoe >= 0 ? '+' : '') + fmt(p.fpoe, 1) : '—', 'fpoe')}
        ${stat(`${p.boom}<span style="font-size:12px;color:var(--mut)">/</span>${p.bust}`, 'boom / bust wks')}
      </div>
      <div class="pp-spark"><canvas id="pp-spark-canvas"></canvas></div>
      <div class="pp-journey">${draft}. Started ${p.starts} week${p.starts === 1 ? '' : 's'}, producing <strong>${fmt(p.stPts, 1)} pts</strong> in AFFL lineups. <a href="players.html?year=${curYear}&pid=${p.pid}" style="color:var(--blue2);font-weight:700">Full profile →</a></div>
    </div>`;
    document.body.appendChild(ov);
    const close = () => { if (sparkChart) { sparkChart.destroy(); sparkChart = null; } ov.remove(); };
    ov.addEventListener('click', (e) => { if (e.target === ov) close(); });
    ov.querySelector('.pp-close').addEventListener('click', close);

    const weeks = p.wk.map((w) => 'W' + w[0]);
    sparkChart = new Chart(ov.querySelector('#pp-spark-canvas'), {
      type: 'bar',
      data: {
        labels: weeks,
        datasets: [{
          data: p.wk.map((w) => w[1]),
          backgroundColor: p.wk.map((w) => w[2] ? '#2f7bffcc' : '#3a4a6388'),
          borderRadius: 3, maxBarThickness: 22,
        }],
      },
      options: {
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: { callbacks: {
            label: (c) => `${fmt(c.parsed.y, 1)} pts · ${p.wk[c.dataIndex][2] ? 'started' : 'benched'} by ${shortName25(p.wk[c.dataIndex][3])}`,
          } },
        },
        scales: {
          y: { grid: { color: C.grid }, border: { display: false } },
          x: { grid: { display: false }, border: { display: false } },
        },
      },
    });
  }

  /* ================= nfl payroll (Spotrac) ================= */
  function renderCap() {
    const cap = NG.nflCap || {};
    const rows = cap.final || [];
    const money = (n) => '$' + (n / 1e6).toFixed(1) + 'M';
    if (!rows.length) {
      chartNotice('#cap-chart', `No NFL cap data loaded for ${curYear} yet.`);
      $('#cap-tbl tbody').innerHTML =
        `<tr><td colspan="5">${noLineups(`No NFL cap data loaded for ${curYear} yet.`)}</td></tr>`;
      return;
    }
    if (!ensureCanvas('#cap-chart')) return;
    $('#cap-sub').textContent =
      'cap carried by the final-week roster · bench vs starters · via Spotrac';
    mkChart('#cap-chart', {
      type: 'bar',
      data: {
        labels: rows.map((r) => shortName25(r.teamId)),
        datasets: [
          { label: 'Starters', data: rows.map((r) => (r.startersCap || 0) / 1e6),
            backgroundColor: '#ffc400cc', stack: 'c', maxBarThickness: 16 },
          { label: 'Bench', data: rows.map((r) => ((r.totalCap || 0) - (r.startersCap || 0)) / 1e6),
            backgroundColor: '#3a4a63cc', stack: 'c', maxBarThickness: 16 },
        ],
      },
      options: {
        indexAxis: 'y',
        maintainAspectRatio: false,
        plugins: {
          legend: { labels: { boxWidth: 10, boxHeight: 10, usePointStyle: true, pointStyle: 'circle' } },
          tooltip: { callbacks: {
            label: (c) => `${c.dataset.label}: $${c.parsed.x.toFixed(1)}M`,
            afterBody: (items) => {
              const r = rows[items[0].dataIndex];
              return `${r.matched} players · ${money(r.totalCap)} total · priciest ${money(r.maxCap)}`;
            },
          } },
        },
        scales: {
          x: { stacked: true, grid: { color: C.grid }, border: { display: false },
               title: { display: true, text: '$M of NFL cap' } },
          y: { stacked: true, grid: { display: false }, border: { display: false } },
        },
      },
    });
    $('#cap-tbl tbody').innerHTML = (cap.topPlayers || []).map((p) => `
      <tr>
        <td><strong>${p.name}</strong></td>
        <td><span class="badge pos-${p.pos}">${p.pos}</span></td>
        <td class="own">${p.nfl || '—'}</td>
        <td>${shortName25(p.teamId)}<div class="own">${p.weeks} wk${p.weeks === 1 ? '' : 's'} rostered</div></td>
        <td><strong>$${(p.cap / 1e6).toFixed(1)}M</strong></td>
      </tr>`).join('');
  }

  /* ================= fantasy genius ================= */
  function gradeChip(g) {
    return `<span class="grade g${g[0]}">${g}</span>`;
  }

  function renderReport() {
    if (!NG.report.length) {
      $('#report-tbl tbody').innerHTML = `<tr><td colspan="7">${noLineups(
        `Grading needs weekly lineups, which ESPN does not keep for ${curYear}.`)}</td></tr>`;
      return;
    }
    $('#report-tbl tbody').innerHTML = NG.report.map((r, i) => {
      const t = T25[r.teamId];
      return `<tr>
        <td><div class="team-cell">${avatarHTML(t, 'mini')}<div>${t.name}<div class="own">${memberName(t.owner)}</div></div></div></td>
        <td>${gradeChip(r.gDraft)}</td>
        <td>${gradeChip(r.gLineup)}</td>
        <td>${gradeChip(r.gWaiver)}</td>
        <td>${gradeChip(r.gLuck)}</td>
        <td><span class="gpa-badge">${r.gpa.toFixed(2)}</span></td>
        <td class="verdict">${r.verdict}</td>
      </tr>`;
    }).join('');
  }

  function renderWhatIf() {
    if (!NG.whatif.length) {
      $('#whatif-tbl tbody').innerHTML = `<tr><td colspan="5">${noLineups()}</td></tr>`;
      return;
    }
    $('#whatif-tbl tbody').innerHTML = NG.whatif.map((w) => {
      const t = T25[w.teamId];
      const d = w.actRank - w.optRank;
      const fate = d > 0 ? `<span class="fate-up">▲ ${d}</span>`
        : d < 0 ? `<span class="fate-down">▼ ${-d}</span>`
        : '<span class="fate-even">—</span>';
      return `<tr>
        <td><span class="rank-pill${w.optRank === 1 ? ' gold' : ''}">${w.optRank}</span></td>
        <td><div class="team-cell">${avatarHTML(t, 'mini')}<div>${t.name}</div></div></td>
        <td><strong>${w.optW}-${w.optL}</strong></td>
        <td class="own">${w.actW}-${w.actL}</td>
        <td>${fate}</td>
      </tr>`;
    }).join('');
  }

  function renderWaiver() {
    if (!NG.waiver.length) {
      $('#waiver-list').innerHTML = `<li>${noLineups()}</li>`;
      return;
    }
    $('#waiver-list').innerHTML = NG.waiver.map((w, i) => `
      <li>
        <div class="story-ico" style="background:#93d50018">${['🧙','🎩','✨','🪄','🔮','🃏','🎯','⭐'][i] || '⭐'}</div>
        <div class="story-txt">
          <div class="t">${w.name} <span class="badge pos-${w.pos}">${w.pos}</span></div>
          <div class="d">${w.nfl || ''} · scooped by ${shortName25(w.teamId)}</div>
        </div>
        <div class="story-val" style="color:var(--green)">${fmt(w.stPts, 0)} pts started</div>
      </li>`).join('');
  }

  /* ================= orchestrate ================= */
  function sectionLabels() {
    const lineups = NG.hasRosters;
    $('#lab-year').textContent = lineups
      ? `${curYear} · joined to nflverse`
      : `${curYear} · no lineup data stored`;
    $('#profiler-year').textContent = lineups
      ? `${curYear} · every rostered player · nflverse joined`
      : `${curYear} · unavailable`;
    $('#genius-year').textContent = lineups
      ? `${curYear} · manager skill, separated from luck`
      : `${curYear} · unavailable`;
  }

  async function renderSeason() {
    renderPicker();
    await loadYearBundle(curYear);
    renderKPIs();
    renderArea();
    renderSide();
    renderBar();
    renderRace();
    renderStandings();
    renderLuck();
    sectionLabels();
    renderLineupIQ();
    renderDraft();
    renderDNA();
    renderEPA();
    renderSkillRadar();
    renderFPOE();
    renderSpotlight();
    renderCap();
    initProfiler();
    renderReport();
    renderWhatIf();
    renderWaiver();
  }

  await renderSeason();
  renderTimeline();
  renderFranchises();
  renderEra();
  renderH2H();
})();
