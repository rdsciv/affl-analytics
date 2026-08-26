/* ============ AFFL Analytics ============ */
(async function () {
  const DATA = await (await fetch('data.json?v=' + Date.now(), {cache: 'no-store'})).json();
  const $ = (s) => document.querySelector(s);

  const C = {
    blue: '#00a2ff', blue2: '#47d4ff', ice: '#9fd8ff', steel: '#3a4a63',
    orange: '#ff6a00', fire: '#ff5a1e', gold: '#ffc400', gold2: '#ffcc33',
    green: '#c8ff00', red: '#ff2d1a',
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

  const MERGE = { m01: "m07", m03: "m08", m20: "m10" };
  const canon = (id) => MERGE[id] || id;
  const FRANCHISE = {};
  (DATA.franchises || []).forEach((f) => { FRANCHISE[canon(f.owner)] = f; });
  const FRANCHISE_LOGO = {};
  Object.keys(DATA.seasons || {}).sort().forEach((y) => {
    (DATA.seasons[y].teams || []).forEach((t) => {
      if (t.owner && t.logo) FRANCHISE_LOGO[canon(t.owner)] = t.logo;
    });
  });
  const franchiseName = (id) => {
    const f = FRANCHISE[canon(id)];
    return (f && f.currentName) || memberName(id);
  };
  const shortTeam = (id) => {
    const parts = String(franchiseName(id) || "").split(/\s+/).filter(Boolean);
    return parts.length ? parts[parts.length - 1] : franchiseName(id);
  };
  const franchiseTeam = (id) => ({ name: franchiseName(id), logo: FRANCHISE_LOGO[canon(id)] || "" });

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
  let curYear = years.includes(qsYear) ? qsYear : null;
  let spotlightId = null;
  let NG = null;

  const S = () => DATA.seasons[String(curYear)] || { teams: [] };
  const teamById = (id) => (S().teams || []).find((t) => t.id === id);

  function warehouseMaps() {
    const power = {}, luck = {}, luckW = {};
    ((NG && NG.power) || []).forEach((p) => { power[p.teamId] = p; });
    ((NG && NG.luckFG) || []).forEach((p) => { luck[p.teamId] = p; });
    ((NG && NG.luckWeighted) || []).forEach((p) => { luckW[p.teamId] = p; });
    return { power, luck, luckW };
  }

  const NOTABLE_ORDER = ['min_win', 'max_loss', 'slugfest', 'pillow_fight', 'blowout', 'nail_biter'];
  const NOTABLE_META = {
    min_win: { t: 'Lowest win' },
    max_loss: { t: 'Highest loss' },
    slugfest: { t: 'Slugfest' },
    pillow_fight: { t: 'Pillow fight' },
    blowout: { t: 'Blowout' },
    nail_biter: { t: 'Nail-biter' },
  };
  const nick = (id) => {
    const n = (teamById(id) || { name: '?' }).name;
    const parts = n.split(' ');
    return parts[parts.length - 1];
  };

  /* ================= season picker ================= */
  function isCum() { return curYear == null; }

  function leagueTotals() {
    let pts = 0, games = 0;
    years.forEach((y) => {
      const s = DATA.seasons[String(y)];
      if (!s) return;
      pts += Number(s.totalPts) || 0;
      games += (s.teams || []).reduce((a, t) => a + (t.wins || 0) + (t.losses || 0) + (t.ties || 0), 0) / 2;
    });
    return { pts: pts, games: games };
  }

  function setPanes() {
    const season = document.getElementById('season-pane');
    const cum = document.getElementById('cum-pane');
    if (season) season.hidden = isCum();
    if (cum) cum.hidden = !isCum();
  }

  function renderCumHome() {
    const tot = leagueTotals();
    const latest = DATA.seasons[String(DATA.latest)] || {};
    const nTeams = (latest.teams || []).length || (DATA.activeOwners || []).length;
    const nOwners = (DATA.activeOwners || []).length;
    const lo = years[0], hi = years[years.length - 1];
    const hdr = document.getElementById('hdr-sub');
    if (hdr) hdr.textContent = nTeams + '-team league · all-time · est. 2014';
    const hsT = document.getElementById('hs-total');
    const hsG = document.getElementById('hs-games');
    if (hsT) hsT.textContent = fmt(tot.pts, 1);
    if (hsG) hsG.textContent = fmt(tot.games);
    const kpi = document.getElementById('kpi-row');
    if (kpi) {
      kpi.innerHTML = `
        <div class="card kpi kpi-static"><div class="kpi-title">${years.length}</div><div class="kpi-desc">seasons</div></div>
        <div class="card kpi kpi-static"><div class="kpi-title">${nOwners}</div><div class="kpi-desc">active owners</div></div>
        <div class="card kpi kpi-static"><div class="kpi-title">${fmt(tot.games)}</div><div class="kpi-desc">matchups</div></div>
        <div class="card kpi kpi-static"><div class="kpi-title">${lo}–${hi}</div><div class="kpi-desc">range</div></div>`;
    }
  }

  function renderPicker() {
    const chips = [`<button class="season-chip${curYear == null ? ' on' : ''}" data-y="cum">Cumulative</button>`]
      .concat(years.map((y) => `<button class="season-chip${y === curYear ? ' on' : ''}" data-y="${y}">${y}</button>`));
    $('#season-picker').innerHTML = chips.join('');
    document.querySelectorAll('.season-chip').forEach((b) =>
      b.addEventListener('click', () => {
        const raw = b.dataset.y;
        curYear = (raw === '' || raw === 'cum' || raw == null) ? null : +raw;
        if (curYear != null && !years.includes(curYear)) curYear = null;
        history.replaceState(null, '', curYear == null ? 'index.html' : ('?year=' + curYear));
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
    const { power } = warehouseMaps();
    const powerTop = (NG.power || [])[0];
    const powerTeam = powerTop ? teamById(powerTop.teamId) : null;
    const luckTop = [...(NG.luckFG || [])].sort((a, b) => b.net - a.net)[0];
    const luckTeam = luckTop ? teamById(luckTop.teamId) : null;
    const apPct = (t) => {
      const p = power[t.id];
      const w = p ? p.w : t.allplayW;
      const l = p ? p.l : t.allplayL;
      return w / Math.max(1, w + l);
    };

    const cards = [
      champ && {
        n: '01 · CROWN', color: C.gold, title: 'The Champion',
        pct: champ.wins / Math.max(1, champ.wins + champ.losses),
        label: Math.round((champ.wins / Math.max(1, champ.wins + champ.losses)) * 100) + '%',
        desc: `<strong>${champ.name}</strong> · ${champ.wins}-${champ.losses} · ${firstName(champ.owner)} · ${fmt(champ.pf, 2)} PF`,
      },
      {
        n: '02 · POINTS', color: C.blue, title: 'Points Leader',
        pct: apPct(ptsLeader), label: fmt(ptsLeader.pf, 0),
        desc: `<strong>${ptsLeader.name}</strong> · ${fmt(ptsLeader.pf, 2)} PF · ${fmt(ptsLeader.avgPts, 1)} / week`,
      },
      powerTeam && {
        n: '03 · POWER', color: C.blue, title: 'All-Play',
        pct: powerTop.w / Math.max(1, powerTop.w + powerTop.l),
        label: (powerTop.pwrPct != null ? Number(powerTop.pwrPct).toFixed(1) : (apPct(powerTeam) * 100).toFixed(1)) + '%',
        desc: `<strong>${powerTeam.name}</strong> · ${powerTop.w}–${powerTop.l} raw all-play`,
      },
      luckTeam && {
        n: '04 · LUCK', color: luckTop.net >= 0 ? C.green : C.mut, title: 'Luck Index',
        pct: Math.min(1, (Math.abs(luckTop.net) + 2) / 8),
        label: (luckTop.net >= 0 ? '+' : '') + luckTop.net,
        desc: `<strong>${luckTeam.name}</strong> · ${luckTop.lucky} lucky / ${luckTop.unlucky} unlucky`,
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
    const { power, luck } = warehouseMaps();
    const p = champ ? power[champ.id] : null;
    const lk = champ ? luck[champ.id] : null;
    const how = [];
    if (champ) how.push(`${champ.wins}-${champ.losses}`);
    if (champ) how.push(`${fmt(champ.pf, 2)} PF`);
    if (p) how.push(`Power ${p.rank} · ${p.w}–${p.l}`);
    if (lk && lk.net != null) how.push(`Luck Index ${lk.net >= 0 ? '+' : ''}${lk.net}`);

    $('#champ-spot').innerHTML = champ ? `
      ${avatarHTML(champ)}
      <div>
        <div class="tag">League Champion</div>
        <div class="nm">${champ.name}</div>
        <div class="rec">${memberName(champ.owner)} · ${how.join(' · ')}</div>
      </div>` : '<div class="rec">Season in progress</div>';

    const notables = [...(NG.notables || [])].sort(
      (a, b) => NOTABLE_ORDER.indexOf(a.kind) - NOTABLE_ORDER.indexOf(b.kind));
    $('#story-list').innerHTML = notables.map((n) => {
      const meta = NOTABLE_META[n.kind] || { t: n.kind };
      return `<li>
        <div class="story-ico">${n.week}</div>
        <div class="story-txt"><div class="t">${meta.t}</div>
          <div class="d">${nick(n.winnerId)} ${fmt(n.winnerPts, 1)} over ${nick(n.loserId)} ${fmt(n.loserPts, 1)}</div>
        </div>
        <div class="story-val">${fmt(n.winnerPts, 1)}–${fmt(n.loserPts, 1)}</div>
      </li>`;
    }).join('');

    const ss = NG.scoreSeason;
    const storySub = $('#story-sub');
    if (storySub) {
      storySub.textContent = ss && ss.n
        ? `${ss.n} regular sides · min ${fmt(ss.minPts, 1)} · median ${fmt(ss.medianPts, 1)} · max ${fmt(ss.maxPts, 1)}`
        : 'warehouse notables · both scores';
    }

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
    const colors = [C.blue, C.gold, C.blue2, C.ice];
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
    const { power, luck } = warehouseMaps();
    const rows = [...s.teams].sort((a, b) => (a.finalRank || 99) - (b.finalRank || 99));
    const pillCls = (r) => r === 1 ? 'gold' : r === 2 ? 'slv' : r === 3 ? 'brz' : '';
    const sub = $('#standings-sub');
    if (sub) sub.innerHTML = 'ESPN W-L-T · warehouse Power · <span class="chip-verified">verified</span>';
    $('#standings-tbl tbody').innerHTML = rows.map((t) => {
      const p = power[t.id];
      const lk = luck[t.id];
      const ap = p ? `${p.w}–${p.l}` : `${t.allplayW}–${t.allplayL}`;
      const pwr = p && p.pwrPct != null ? Number(p.pwrPct).toFixed(1) + '%' : '';
      const luckTxt = lk && lk.net != null ? `${lk.net > 0 ? '+' : ''}${lk.net}` : '';
      const luckCls = lk && lk.net > 0 ? 'pos' : (lk && lk.net < 0 ? 'neg' : '');
      return `
      <tr>
        <td><span class="rank-pill ${pillCls(t.finalRank)}">${t.finalRank || '–'}</span></td>
        <td><div class="team-cell">${avatarHTML(t, 'mini')}<div>${t.name}<div class="own">${memberName(t.owner)}</div></div></div></td>
        <td><strong>${t.wins}-${t.losses}${t.ties ? '-' + t.ties : ''}</strong></td>
        <td>${fmt(t.pf, 2)}</td>
        <td>${fmt(t.pa, 2)}</td>
        <td>${ap}</td>
        <td>${pwr}</td>
        <td class="${luckCls}">${luckTxt}</td>
      </tr>`;
    }).join('');
  }

  /* ================= luck chart ================= */
  function renderLuck() {
    const s = S();
    const { luck, luckW } = warehouseMaps();
    const rows = [...s.teams].map((t) => {
      const lk = luck[t.id];
      const w = luckW[t.id];
      return {
        t,
        net: lk ? lk.net : null,
        lucky: lk ? lk.lucky : null,
        unlucky: lk ? lk.unlucky : null,
        weighted: w ? w.weighted : t.luck,
      };
    }).filter((r) => r.net != null).sort((a, b) => b.net - a.net);
    const sub = document.querySelector('#luck-chart') &&
      document.querySelector('#luck-chart').closest('.card') &&
      document.querySelector('#luck-chart').closest('.card').querySelector('.card-sub');
    if (sub) sub.textContent = 'lucky wins minus unlucky losses · weighted luck in the tooltip';
    mkChart('#luck-chart', {
      type: 'bar',
      data: {
        labels: rows.map((r) => r.t.name.length > 18 ? r.t.name.slice(0, 17) + '…' : r.t.name),
        datasets: [{
          data: rows.map((r) => r.net),
          backgroundColor: rows.map((r) => r.net >= 0 ? '#c8ff00cc' : '#3a4a63cc'),
          borderRadius: 5, maxBarThickness: 16,
        }],
      },
      options: {
        indexAxis: 'y',
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: { callbacks: { label: (c) => {
            const r = rows[c.dataIndex];
            const idx = `${r.net >= 0 ? '+' : ''}${r.net} Luck Index (${r.lucky} lucky / ${r.unlucky} unlucky)`;
            const w = r.weighted == null ? '' : ` · weighted ${r.weighted >= 0 ? '+' : ''}${fmt(r.weighted, 2)}`;
            return idx + w;
          } } },
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
        <div class="tl-own">${t.record}</div>
      </div>`).join('');
  }

  function renderFranchises() {
    const src = (window.AFFL && window.AFFL.visibleFranchises)
      ? window.AFFL.visibleFranchises(DATA.franchises || [])
      : (DATA.franchises || []);
    const rows = src.slice().sort((a, b) => (b.titles - a.titles) || (b.winPct - a.winPct) || (b.pf - a.pf));
    $('#franchise-tbl tbody').innerHTML = rows.map((f, i) => {
      const rank = i + 1;
      const pill = rank === 1 ? "gold" : rank === 2 ? "slv" : rank === 3 ? "brz" : "";
      const t = franchiseTeam(f.owner);
      const href = "teams.html?squad=" + encodeURIComponent(f.owner);
      return `
      <tr>
        <td><span class="rank-pill ${pill}">${rank}</span></td>
        <td><div class="team-cell">${avatarHTML(t, "mini")}<div><a class="hist-name" href="${href}">${t.name}</a></div></div></td>
        <td>${f.seasons}</td>
        <td>${f.wins}-${f.losses}${f.ties ? '-' + f.ties : ''}</td>
        <td class="${f.winPct >= 0.5 ? 'pos' : 'neg'}"><strong>${(f.winPct * 100).toFixed(1)}%</strong></td>
        <td>${f.titles || 0}</td>
        <td>${fmt(f.pf)}</td>
      </tr>`;
    }).join('');
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
          label: shortTeam(f.owner),
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
    const head = '<tr><th></th>' + owners.map((o) => `<th>${shortTeam(o)}</th>`).join('') + '</tr>';
    const body = owners.map((row) => {
      const cells = owners.map((col) => {
        if (row === col) return '<td class="h2h-x">—</td>';
        const r = rec[row + '|' + col];
        if (!r) return '<td class="h2h-x">·</td>';
        const cls = r[0] > r[1] ? 'h2h-w' : r[0] < r[1] ? 'h2h-l' : 'h2h-e';
        return `<td><span class="h2h-cell ${cls}">${r[0]}–${r[1]}</span></td>`;
      }).join('');
      return `<tr><td>${shortTeam(row)}</td>${cells}</tr>`;
    }).join('');
    $('#h2h-tbl').innerHTML = head + body;
  }

  /* ================= next gen lab (per season) =================
     NG and T25 are reassigned every time the season changes; every renderer
     below reads them, so all lower sections follow the picker. */
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

  function renderMaxPotential() {
    const award = $("#maxpot-award");
    const bars = $("#maxpot-bars");
    if (!award || !bars) return;
    const raw = (NG && NG.lineupIQ) || [];
    if (!NG.hasRosters || !raw.length) {
      award.innerHTML = noLineups();
      bars.innerHTML = "";
      return;
    }
    const rows = raw.map((r) => {
      const t = T25[r.teamId] || { name: "?", id: r.teamId };
      const opt = Number(r.optimal) || 0;
      const act = Number(r.actual) || 0;
      const left = Number(r.wasted != null ? r.wasted : Math.max(0, opt - act));
      const pct = opt ? act / opt : 0;
      return { t, act, opt, left, pct, perfect: r.perfect || 0 };
    }).sort((a, b) => b.opt - a.opt || b.act - a.act);
    const top = rows[0];
    award.innerHTML = `
      <div class="maxpot-award">
        ${avatarHTML(top.t)}
        <div>
          <div class="maxpot-kicker">Gifted Kid Maximum Potential Award</div>
          <div class="maxpot-name">${top.t.name}</div>
        </div>
        <div class="maxpot-score">
          <div class="maxpot-opt">${fmt(top.opt, 0)}</div>
          <div class="maxpot-pct">${Math.round(top.pct * 100)}% of ideal points</div>
        </div>
      </div>`;
    const max = Math.max(...rows.map((r) => r.opt), 1);
    bars.innerHTML = rows.map((r) => {
      const actW = Math.max(0, (r.act / max) * 100);
      const leftW = Math.max(0, (r.left / max) * 100);
      return `<div class="maxpot-row">
        ${avatarHTML(r.t, "mini")}
        <div class="maxpot-team">${r.t.name}</div>
        <div class="maxpot-track">
          <div class="maxpot-act" style="width:${actW.toFixed(2)}%"><span>${fmt(r.act, 0)}</span></div>
          <div class="maxpot-left" style="width:${leftW.toFixed(2)}%"><span>${fmt(r.left, 0)}</span></div>
        </div>
      </div>`;
    }).join("");
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
            label: (c) => `${fmt(c.parsed.x, 1)} EPA`,
          } },
        },
        scales: {
          x: { grid: { color: C.grid }, border: { display: false } },
          y: { grid: { display: false }, border: { display: false } },
        },
      },
    });
  }

  /* Home eight: opportunity / trophies / luckCard. Missing keys => empty, no crash. */
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"]/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;",
    }[c]));
  }
  function sameTid(a, b) {
    if (a == null || b == null || a === "" || b === "") return false;
    if (a === b) return true;
    const na = Number(a), nb = Number(b);
    return !Number.isNaN(na) && !Number.isNaN(nb) && na === nb;
  }
  function ownerForTid(tid) {
    const t = ((S() && S().teams) || []).find((x) => sameTid(x.id, tid));
    return t ? t.owner : null;
  }
  function currentFranchise(tid) {
    const owner = ownerForTid(tid);
    const name = franchiseName(owner);
    const logo = (owner && FRANCHISE_LOGO[canon(owner)]) || "";
    return { owner, name: name || "—", logo };
  }
  function teamCellHTML(tid) {
    const f = currentFranchise(tid);
    const href = f.owner ? "teams.html?squad=" + encodeURIComponent(f.owner) : "";
    const name = href
      ? `<a class="hist-name" href="${href}">${esc(f.name)}</a>`
      : esc(f.name);
    return `<div class="team-cell">${avatarHTML({ name: f.name, logo: f.logo }, "mini")}<div>${name}</div></div>`;
  }
  function opportunityRows(bundle) {
    if (!bundle) return [];
    const opp = bundle.opportunity;
    if (Array.isArray(opp)) return opp;
    if (opp && Array.isArray(opp.receivingUsage)) return opp.receivingUsage;
    if (Array.isArray(bundle.receivingUsage)) return bundle.receivingUsage;
    return [];
  }
  function shareTxt(v) {
    if (v == null || v === "" || Number.isNaN(Number(v))) return "—";
    const n = Number(v);
    return (n <= 1.5 ? n * 100 : n).toFixed(1) + "%";
  }
  function numTxt(n, d) {
    if (n == null || n === "" || Number.isNaN(Number(n))) return "—";
    return fmt(Number(n), d);
  }
  function signedTxt(n, d) {
    if (n == null || n === "" || Number.isNaN(Number(n))) return "—";
    const v = Number(n);
    return (v > 0 ? "+" : "") + fmt(v, d);
  }

  let oppSort = { k: "wopr", dir: -1 };
  let luckSort = { k: "actualW", dir: -1 };
  let eightWired = false;

  function renderSpotlight() {
    const tb = document.querySelector("#spotlight-tbl tbody");
    if (!tb) return;
    const raw = opportunityRows(NG);
    const rows = raw.map((p) => {
      const fp = p.fp != null ? p.fp : p.pts;
      const xfp = p.xfp;
      const resid = (fp != null && xfp != null) ? Number(fp) - Number(xfp) : null;
      const tgt = p.tgtShare != null ? p.tgtShare : p.tsh;
      return Object.assign({}, p, { fp, resid, tgtShare: tgt });
    });
    const sub = document.getElementById("opp-sub");
    if (!rows.length) {
      tb.innerHTML = `<tr><td colspan="8"><div class="notice">Opportunity board is not in the ${curYear} file yet.</div></td></tr>`;
      if (sub) sub.textContent = curYear + " · unavailable";
      return;
    }
    if (sub) sub.textContent = curYear + " · tgt share, WOPR, aDOT, xFP, FP−xFP";
    const k = oppSort.k, dir = oppSort.dir;
    rows.sort((a, b) => {
      if (k === "name" || k === "pos") return String(a[k] || "").localeCompare(String(b[k] || "")) * dir;
      const an = a[k] == null ? -Infinity * dir : Number(a[k]);
      const bn = b[k] == null ? -Infinity * dir : Number(b[k]);
      return (an - bn) * dir;
    });
    tb.innerHTML = rows.map((p) => {
      const href = (p.pid != null && p.pid !== "")
        ? `players.html?year=${curYear}&pid=${p.pid}`
        : "";
      const name = href
        ? `<a class="hist-name" href="${href}">${esc(p.name || "—")}</a>`
        : `<strong>${esc(p.name || "—")}</strong>`;
      const residCls = p.resid == null ? "" : (p.resid > 0 ? "pos" : p.resid < 0 ? "neg" : "");
      return `<tr>
        <td>${name}</td>
        <td><span class="badge pos-${esc(p.pos || "")}">${esc(p.pos || "—")}</span></td>
        <td>${shareTxt(p.tgtShare)}</td>
        <td>${p.wopr == null ? "—" : Number(p.wopr).toFixed(2)}</td>
        <td>${numTxt(p.adot, 1)}</td>
        <td>${numTxt(p.xfp, 1)}</td>
        <td><strong>${numTxt(p.fp, 1)}</strong></td>
        <td class="${residCls}">${signedTxt(p.resid, 1)}</td>
      </tr>`;
    }).join("");
    const tbl = document.getElementById("spotlight-tbl");
    if (tbl) {
      tbl.querySelectorAll("thead th.s").forEach((th) => {
        th.classList.toggle("on", th.dataset.k === oppSort.k);
        th.classList.toggle("asc", th.dataset.k === oppSort.k && oppSort.dir > 0);
      });
    }
  }

  function trophySlot(tag, tid, rec) {
    if (tid == null || tid === "") {
      return `<div class="trophy-slot empty">
        <div>
          <div class="tag">${esc(tag)}</div>
          <div class="nm">—</div>
          <div class="rec">unavailable</div>
        </div>
      </div>`;
    }
    const f = currentFranchise(tid);
    return `<div class="trophy-slot">
      ${avatarHTML({ name: f.name, logo: f.logo })}
      <div>
        <div class="tag">${esc(tag)}</div>
        <div class="nm">${esc(f.name)}</div>
        <div class="rec">${esc(rec)}</div>
      </div>
    </div>`;
  }

  function renderTrophies() {
    const grid = document.getElementById("trophy-grid");
    const sub = document.getElementById("trophy-sub");
    if (!grid) return;
    const t = (NG && NG.trophies) || null;
    const hasH2H = t && t.h2hChampionTid != null && t.h2hChampionTid !== "";
    const hasMed = t && t.medianChampionTid != null && t.medianChampionTid !== "";
    const hasAP = t && t.allPlayChampionTid != null && t.allPlayChampionTid !== "";
    const hasRoto = t && t.rotoChampionTid != null && t.rotoChampionTid !== "";
    const awardsLink = ' · <a class="hist-name" href="awards.html">All-League →</a>';
    if (!t || (!hasH2H && !hasMed && !hasAP && !hasRoto)) {
      grid.innerHTML = `<div class="notice">Trophy board is not in the ${curYear} file yet.</div>`;
      if (sub) sub.innerHTML = curYear + ' · unavailable' + awardsLink;
      return;
    }
    if (sub) sub.innerHTML = curYear + ' · Cup · Board · Roto · current names' + awardsLink;
    const parts = [];
    /* 2014 trophies still render H2H if present, even when Board/Roto are missing. */
    parts.push(trophySlot("Cup", hasH2H ? t.h2hChampionTid : null, "H2H champion"));
    if (hasMed && hasAP && !sameTid(t.medianChampionTid, t.allPlayChampionTid)) {
      parts.push(trophySlot("Board", t.medianChampionTid, "median champion"));
      parts.push(trophySlot("Board", t.allPlayChampionTid, "all-play champion"));
    } else if (hasMed || hasAP) {
      const tid = hasMed ? t.medianChampionTid : t.allPlayChampionTid;
      const rec = (hasMed && hasAP) ? "median / all-play" : (hasMed ? "median champion" : "all-play champion");
      parts.push(trophySlot("Board", tid, rec));
    } else {
      parts.push(trophySlot("Board", null, "unavailable"));
    }
    parts.push(trophySlot("Roto", hasRoto ? t.rotoChampionTid : null, "roto champion"));
    grid.innerHTML = parts.join("");
  }

  function luckRows() {
    const list = (NG && Array.isArray(NG.luckCard)) ? NG.luckCard : [];
    return list.map((r) => {
      const f = currentFranchise(r.tid);
      const tdRes = (r.tdFor != null && r.xtdFor != null)
        ? Number(r.tdFor) - Number(r.xtdFor)
        : null;
      return Object.assign({}, r, { name: f.name, tdRes });
    });
  }

  function renderLuckCard() {
    const tb = document.querySelector("#luck-card-tbl tbody");
    if (!tb) return;
    const rows = luckRows();
    const sub = document.getElementById("luck-card-sub");
    if (!rows.length) {
      tb.innerHTML = `<tr><td colspan="7"><div class="notice">Schedule vs roster luck is not in the ${curYear} file yet.</div></td></tr>`;
      if (sub) sub.textContent = curYear + " · unavailable";
      return;
    }
    if (sub) sub.textContent = curYear + " · actual · all-play · median · expected wins · schedule luck · TD−xTD";
    const k = luckSort.k, dir = luckSort.dir;
    rows.sort((a, b) => {
      if (k === "name") return String(a.name || "").localeCompare(String(b.name || "")) * dir;
      const an = a[k] == null ? -Infinity * dir : Number(a[k]);
      const bn = b[k] == null ? -Infinity * dir : Number(b[k]);
      return (an - bn) * dir;
    });
    const rec = (w, l) => (w == null || l == null) ? "—" : `${w}-${l}`;
    tb.innerHTML = rows.map((r) => {
      const luckCls = r.scheduleLuckWins == null ? "" : (r.scheduleLuckWins > 0 ? "pos" : r.scheduleLuckWins < 0 ? "neg" : "");
      const tdCls = r.tdRes == null ? "" : (r.tdRes > 0 ? "pos" : r.tdRes < 0 ? "neg" : "");
      const apPct = r.allPlayPct == null ? ""
        : `<div class="own">${shareTxt(r.allPlayPct)}</div>`;
      return `<tr>
        <td>${teamCellHTML(r.tid)}</td>
        <td><strong>${rec(r.actualW, r.actualL)}</strong></td>
        <td>${rec(r.allPlayW, r.allPlayL)}${apPct}</td>
        <td>${rec(r.medianW, r.medianL)}</td>
        <td>${numTxt(r.expectedWins, 2)}</td>
        <td class="${luckCls}">${signedTxt(r.scheduleLuckWins, 2)}</td>
        <td class="${tdCls}">${signedTxt(r.tdRes, 2)}</td>
      </tr>`;
    }).join("");
    const tbl = document.getElementById("luck-card-tbl");
    if (tbl) {
      tbl.querySelectorAll("thead th.s").forEach((th) => {
        th.classList.toggle("on", th.dataset.k === luckSort.k);
        th.classList.toggle("asc", th.dataset.k === luckSort.k && luckSort.dir > 0);
      });
    }
  }

  function wireEightSorts() {
    if (eightWired) return;
    eightWired = true;
    const bind = (tableId, get, set, render) => {
      const el = document.getElementById(tableId);
      if (!el) return;
      el.querySelectorAll("thead th.s").forEach((th) => {
        th.addEventListener("click", () => {
          const st = get();
          if (st.k === th.dataset.k) st.dir *= -1;
          else {
            st.k = th.dataset.k;
            st.dir = (th.dataset.k === "name" || th.dataset.k === "pos") ? 1 : -1;
          }
          set(st);
          render();
        });
      });
    };
    bind("spotlight-tbl", () => oppSort, (s) => { oppSort = s; }, renderSpotlight);
    bind("luck-card-tbl", () => luckSort, (s) => { luckSort = s; }, renderLuckCard);
  }

  /* ================= player profiler ================= */
  const PP = { q: '', pos: 'ALL', limit: 20 };
  let profilerWired = false;


  function playerFace(p, cls) {
    cls = cls || "pp-hs";
    const ini = (p.name || "?").split(" ").filter(Boolean).map((x) => x[0]).join("").slice(0, 2).toUpperCase();
    const pos = String(p.pos || "").toUpperCase();
    if (pos === "DST" || pos === "D/ST" || pos === "DEF") {
      const map = { LA: "lar", LAR: "lar", WAS: "wsh", WSH: "wsh", JAC: "jax", JAX: "jax" };
      const slug = (map[p.nfl] || String(p.nfl || "")).toLowerCase();
      if (slug) {
        return `<img class="${cls}" src="logos/nfl/${slug}.png" alt="" loading="lazy"
          onerror="if(this.parentNode)this.outerHTML='<div class=&quot;${cls} fb&quot;>${ini}</div>'">`;
      }
    }
    const espn = Number(p.pid) > 0
      ? ("https://a.espncdn.com/i/headshots/nfl/players/full/" + Number(p.pid) + ".png") : "";
    const src = p.hs || espn;
    if (!src) return `<div class="${cls} fb">${ini}</div>`;
    const next = (p.hs && espn && p.hs !== espn) ? espn : "";
    return `<img class="${cls}" src="${src}" alt="" loading="lazy" data-fb="${next}"
      onerror="if(this.dataset.fb){this.src=this.dataset.fb;this.dataset.fb='';}else if(this.parentNode)this.outerHTML='<div class=&quot;${cls} fb&quot;>${ini}</div>'">`;
  }

  function ppCardHTML(p, i) {
    const hs = playerFace(p, "pp-hs");
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
    const hs = playerFace(p, "pp-hs");
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
    setPanes();
    if (curYear == null) {
      renderCumHome();
      return;
    }
    await loadYearBundle(curYear);
    renderKPIs();
    renderArea();
    renderSide();
    renderBar();
    renderRace();
    renderStandings();
    renderLuck();
    sectionLabels();
    if (document.getElementById('max-potential')) renderMaxPotential();
    renderDraft();
    renderDNA();
    renderEPA();
    try { renderSpotlight(); } catch (e) { console.warn(e); }
    try { renderTrophies(); } catch (e) { console.warn(e); }
    try { renderLuckCard(); } catch (e) { console.warn(e); }
    wireEightSorts();
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
  document.addEventListener("affl:show-former", renderFranchises);
  /* ================= CHI-89 Elo + Milestones (all-time / cum pane) ================= */
  let ELO = null;
  let MS = null;
  let eloFilter = 'active';
  let msBoardId = null;

  async function loadEloMs() {
    if (ELO && MS) return;
    const [e, m] = await Promise.all([
      fetch('elo.json?v=' + Date.now(), { cache: 'no-store' }).then((r) => r.json()),
      fetch('milestones.json?v=' + Date.now(), { cache: 'no-store' }).then((r) => r.json()),
    ]);
    ELO = e;
    MS = m;
  }

  function eloRows() {
    const rows = (ELO && ELO.table) || [];
    if (eloFilter === 'active') return rows.filter((r) => r.active);
    return rows.slice();
  }

  function renderEloTable() {
    const tbody = $('#elo-tbl tbody');
    if (!tbody) return;
    const rows = eloRows();
    tbody.innerHTML = rows.map((r, i) => {
      const team = franchiseTeam(r.owner);
      const peakAt = r.peakAt
        ? `${r.peakAt.season} wk ${r.peakAt.week}`
        : '—';
      return `<tr>
        <td><span class="rank-pill${i === 0 ? ' gold' : ''}">${i + 1}</span></td>
        <td><div class="team-cell">${avatarHTML(team, 'mini')}<div>
          <div>${team.name}</div>
          <div class="card-sub" style="margin:0">${r.name}</div>
        </div></div></td>
        <td class="s"><strong>${fmt(r.rating, 0)}</strong></td>
        <td class="s" title="${peakAt}">${fmt(r.peak, 0)}</td>
        <td class="s">${fmt(r.low, 0)}</td>
        <td class="s">${r.games}</td>
      </tr>`;
    }).join('') || `<tr><td colspan="6">No rated managers</td></tr>`;
  }

  function renderEloChart() {
    const canvas = $('#elo-chart');
    if (!canvas || !ELO) return;
    const rows = eloRows().slice(0, 8);
    const seasons = (ELO.seasons || []).slice();
    const colors = [C.blue, C.gold, C.green, C.orange, C.blue2, C.red, C.ice, C.steel];
    const datasets = rows.map((r, i) => {
      const ser = ((ELO.series || {})[r.owner] || []);
      const by = {};
      ser.forEach((p) => { by[p.season] = p.elo; });
      return {
        label: shortTeam(r.owner),
        data: seasons.map((s) => by[s] != null ? by[s] : null),
        borderColor: colors[i % colors.length],
        backgroundColor: 'transparent',
        tension: 0.25,
        spanGaps: true,
        pointRadius: 2,
        borderWidth: 2,
      };
    });
    mkChart('#elo-chart', {
      type: 'line',
      data: { labels: seasons.map(String), datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { position: 'bottom', labels: { boxWidth: 10, color: C.mut } },
          tooltip: { mode: 'index', intersect: false },
        },
        scales: {
          x: { grid: { color: C.grid }, ticks: { color: C.mut } },
          y: {
            grid: { color: C.grid },
            ticks: { color: C.mut },
            suggestedMin: 1300,
            suggestedMax: 1800,
          },
        },
      },
    });
  }

  function renderMsBoard() {
    const boardEl = $('#ms-board');
    const tabs = $('#ms-board-tabs');
    if (!boardEl || !tabs || !MS) return;
    const boards = MS.boards || [];
    if (!msBoardId && boards[0]) msBoardId = boards[0].id;
    tabs.innerHTML = boards.map((b) =>
      `<button type="button" class="chip${b.id === msBoardId ? ' on' : ''}" data-ms-board="${b.id}">${b.title.replace('Fastest to ', '')}</button>`
    ).join('');
    const board = boards.find((b) => b.id === msBoardId) || boards[0];
    if (!board) {
      boardEl.innerHTML = '<p class="card-sub">No milestone boards</p>';
      return;
    }
    const rows = board.rows || [];
    boardEl.innerHTML = `
      <h3 class="ms-board-title">${board.title}</h3>
      <ol class="ms-list">
        ${rows.map((r) => {
          const team = franchiseTeam(r.owner);
          const when = r.week != null
            ? `${r.season} · wk ${r.week}`
            : `${r.season}`;
          return `<li class="ms-row">
            <span class="ms-rank">${r.rank}</span>
            <div class="ms-who">${avatarHTML(team, 'mini')}
              <div>
                <div class="ms-name">${team.name}</div>
                <div class="ms-meta">${r.name} · ${when}${r.detail ? ' · ' + r.detail : ''}${r.record ? ' · ' + r.record : ''}</div>
              </div>
            </div>
            <div class="ms-games"><strong>${r.games}</strong><span>games</span></div>
          </li>`;
        }).join('') || '<li class="ms-row"><div class="ms-meta">Nobody has hit this bar yet.</div></li>'}
      </ol>`;
    tabs.querySelectorAll('[data-ms-board]').forEach((btn) => {
      btn.onclick = () => {
        msBoardId = btn.getAttribute('data-ms-board');
        renderMsBoard();
      };
    });
  }

  function renderMsChase() {
    const ul = $('#ms-chase');
    if (!ul || !MS) return;
    const rows = (MS.chase || []).filter((c) => c.active !== false).slice(0, 8);
    ul.innerHTML = rows.map((c) => {
      const team = franchiseTeam(c.owner);
      return `<li>
        <div class="story-ico">${avatarHTML(team, 'mini')}</div>
        <div class="story-txt">
          <div class="t">${team.name}</div>
          <div class="d">${c.wins} wins in ${c.games} games · bar ${c.bar}</div>
        </div>
        <div class="story-val">${c.need} win${c.need === 1 ? '' : 's'} away</div>
      </li>`;
    }).join('') || '<li><div class="story-txt"><div class="d">No active chase</div></div></li>';
  }

  async function renderEloAndMilestones() {
    if (!$('#elo-card') && !$('#milestones-card')) return;
    await loadEloMs();
    const sub = $('#elo-sub');
    if (sub && ELO) {
      const s0 = (ELO.seasons || [])[0];
      const s1 = (ELO.seasons || []).slice(-1)[0];
      sub.textContent = `Elo · ${ELO.ratedGames} rated games · seasons ${s0}–${s1} · 1500 = average`;
    }
    const note = $('#elo-note');
    if (note && ELO) note.textContent = ELO.note || '';
    const msNote = $('#ms-note');
    if (msNote && MS) msNote.textContent = MS.note || '';
    const msSub = $('#ms-sub');
    if (msSub && MS) {
      const s0 = (MS.seasons || [])[0];
      const s1 = (MS.seasons || []).slice(-1)[0];
      msSub.textContent = `Fewest career games to each bar · ${s0}–${s1} · verified matchups`;
    }
    document.querySelectorAll('#elo-filters [data-elo-filter]').forEach((btn) => {
      btn.onclick = () => {
        eloFilter = btn.getAttribute('data-elo-filter') || 'active';
        document.querySelectorAll('#elo-filters .chip').forEach((b) => b.classList.toggle('on', b === btn));
        renderEloTable();
        renderEloChart();
      };
    });
    renderEloTable();
    renderEloChart();
    renderMsBoard();
    renderMsChase();
  }
  try { await renderEloAndMilestones(); } catch (e) { console.warn("elo/milestones", e); }
})();
