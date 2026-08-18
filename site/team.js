/* ============ AFFL team season — started points by lineup slot ============ */
(async function () {
  const A = window.AFFL;
  const $ = (s) => document.querySelector(s);
  await A.boot();
  A.chartDefaults(Chart);
  const C = A.C, fmt = A.fmt;
  const POS = await A.loadJSON('pos_by_week.json');

  const SLOT_COLOR = {
    QB: C.blue, RB: C.green, WR: C.orange, TE: C.gold,
    FLEX: C.fire, K: C.ice, DST: C.steel,
  };
  const SLOT_LABEL = { DST: 'D/ST' };

  let year = A.years()[0];
  let tid = null;
  let chart = null;

  function rec() {
    return ((POS[String(year)] || {}).teams || {})[String(tid)] || null;
  }

  function renderIndex() {
    $('#index-card').hidden = false;
    $('#area-card').hidden = true;
    $('#team-hero').innerHTML = '';
    const teams = Object.values(A.teams(year)).sort((a, b) => (a.finalRank || 99) - (b.finalRank || 99));
    $('#index-sub').textContent = `${year} · ${teams.length} franchises`;
    $('#team-index').innerHTML = teams.map((t) => `
      <a href="${A.teamHref(year, t.id)}">
        ${A.logoHTML(t, 'mini')}
        <div>
          <strong>${t.name}</strong>
          <div class="own">${A.memberName(t.owner)} · ${t.wins}-${t.losses}${t.ties ? '-' + t.ties : ''}
            · ${fmt(t.pf, 1)} PF</div>
        </div>
      </a>`).join('');
    document.title = `${year} teams — AFFL`;
  }

  function renderArea() {
    const T = A.teams(year);
    const t = T[tid];
    if (!t) { renderIndex(); return; }

    $('#index-card').hidden = true;
    $('#area-card').hidden = false;
    document.title = `${t.name} ${year} — AFFL`;
    $('#page-sub').textContent = `${year} · ${t.name}`;
    $('#team-hero').innerHTML = `
      ${A.logoHTML(t, 'logo')}
      <div>
        <h1>${t.name}</h1>
        <div class="rec">${A.memberName(t.owner)} · ${t.wins}-${t.losses}${t.ties ? '-' + t.ties : ''}
          · ${fmt(t.pf, 1)} PF · ${fmt(t.pa, 1)} PA
          · <a class="team-link" href="scoreboard.html?year=${year}">scoreboard</a>
          · <a class="team-link" href="draft.html?year=${year}">draft</a></div>
      </div>`;

    const series = rec();
    const wrap = $('#area-wrap');
    const note = $('#area-note');
    if (chart) { chart.destroy(); chart = null; }

    if (!series || !(series.weeks || []).length) {
      wrap.classList.add('as-notice');
      wrap.innerHTML = A.notice(
        A.yearInfo(year).hasRosters
          ? `No scored weekly lineups stored for this team in ${year}.`
          : `ESPN does not retain weekly lineups for ${year}. Started-by-slot is available from 2018 on.`
      );
      note.textContent = '';
      $('#area-sub').textContent = `${year} · no roster weeks`;
      return;
    }

    wrap.classList.remove('as-notice');
    if (!wrap.querySelector('canvas')) wrap.innerHTML = '<canvas id="pos-area"></canvas>';
    const slots = (POS[String(year)].slots || ['QB', 'RB', 'WR', 'TE', 'FLEX', 'K', 'DST']);
    const weeks = series.weeks;
    const grain = (POS[String(year)].grain || 'started points by lineup slot');
    $('#area-sub').textContent = `${grain} · ${weeks.length} weeks`;
    note.textContent = `Layers are lineup slots (FLEX stays FLEX; D/ST is the DST slot), not the player's listed position. Only weeks this team had a scored roster in ${year}.`;

    chart = new Chart($('#pos-area'), {
      type: 'line',
      data: {
        labels: weeks.map((w) => 'W' + w),
        datasets: slots.map((slot, i) => ({
          label: SLOT_LABEL[slot] || slot,
          data: (series.slots[slot] || []).map((pts, idx) => ({
            x: idx, y: pts, week: weeks[idx], slot, label: SLOT_LABEL[slot] || slot,
          })),
          parsing: { xAxisKey: 'x', yAxisKey: 'y' },
          fill: true,
          tension: 0.2,
          borderColor: SLOT_COLOR[slot] || C.steel,
          backgroundColor: (SLOT_COLOR[slot] || C.steel) + '99',
          borderWidth: 1.5,
          pointRadius: 0,
          pointHoverRadius: 4,
          order: slots.length - i,
        })),
      },
      options: {
        maintainAspectRatio: false,
        interaction: { mode: 'nearest', intersect: false },
        plugins: {
          legend: { labels: { boxWidth: 10, boxHeight: 10, usePointStyle: true, pointStyle: 'circle' } },
          tooltip: {
            callbacks: {
              title: (items) => {
                const p = items[0].raw;
                return `Week ${p.week}`;
              },
              label: (item) => {
                const p = item.raw;
                return `${p.label} ${fmt(p.y, 1)} started pts`;
              },
              footer: (items) => {
                const tot = items.reduce((a, it) => a + (it.raw.y || 0), 0);
                return `lineup ${fmt(tot, 1)}`;
              },
            },
          },
        },
        scales: {
          x: {
            type: 'linear',
            min: 0,
            max: Math.max(0, weeks.length - 1),
            ticks: { callback: (v) => (weeks[v] != null ? 'W' + weeks[v] : '') },
            grid: { color: C.grid }, border: { display: false },
          },
          y: {
            stacked: true, beginAtZero: true,
            title: { display: true, text: 'started points' },
            grid: { color: C.grid }, border: { display: false },
          },
        },
      },
    });
  }

  function go(y, teamId, push) {
    year = y;
    tid = teamId;
    A.yearPicker($('#year-picker'), year, (yy) => go(yy, tid, true), (i) => i.hasRosters ? '' : '*');
    if (tid == null || Number.isNaN(tid)) renderIndex();
    else renderArea();
    if (push) {
      const q = tid != null ? `?year=${year}&tid=${tid}` : `?year=${year}`;
      history.pushState(null, '', q);
    }
  }

  const qs = new URLSearchParams(location.search);
  go(+qs.get('year') || A.years()[0], qs.get('tid') ? +qs.get('tid') : null, false);
  window.addEventListener('popstate', () => {
    const q2 = new URLSearchParams(location.search);
    go(+q2.get('year') || year, q2.get('tid') ? +q2.get('tid') : null, false);
  });
})();
