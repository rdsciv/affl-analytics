/* ============ AFFL Scoreboard — all seasons ============ */
(async function () {
  const A = window.AFFL;
  const $ = (s) => document.querySelector(s);
  await A.boot();

  const TIER = { WINNERS_BRACKET: 'Playoffs', LOSERS_CONSOLATION_LADDER: 'Consolation',
                 WINNERS_CONSOLATION_LADDER: 'Consolation', NONE: '' };
  const SLOT_ORDER = { QB: 0, RB: 1, WR: 2, TE: 3, FLEX: 4, 'RB/WR': 4, 'WR/TE': 4, OP: 4, 'D/ST': 5, K: 6 };

  let year = A.years()[0];
  let week = null;
  let YD = null, T = {};

  function playerCell(pid) {
    const m = YD.pmeta[String(pid)];
    if (!m) return '<span class="sb-name">—</span>';
    const [name, pos, nfl] = m;
    const known = YD.players.some((p) => p.pid === pid);
    if (known) {
      return `<a class="sb-name link" href="players.html?year=${year}&pid=${pid}">${name}</a>`;
    }
    return `<span class="sb-name">${name}</span>`;
  }

  function rosterHTML(side) {
    if (!side.roster.length) return '';
    const starters = side.roster.filter((r) => r[1] !== 'BN' && r[1] !== 'IR')
      .sort((a, b) => (SLOT_ORDER[a[1]] ?? 9) - (SLOT_ORDER[b[1]] ?? 9));
    const bench = side.roster.filter((r) => r[1] === 'BN' || r[1] === 'IR')
      .sort((a, b) => b[2] - a[2]);
    const row = (r) => {
      const m = YD.pmeta[String(r[0])] || ['—', '', ''];
      return `<div class="sb-row">
        <span class="sb-slot">${r[1]}</span>
        ${playerCell(r[0])}
        <span class="sb-nfl">${m[2] || ''}</span>
        <span class="sb-pts">${r[2].toFixed(1)}</span>
      </div>`;
    };
    const benchPts = bench.reduce((a, r) => a + r[2], 0);
    return `${starters.map(row).join('')}
      ${bench.length ? `<details class="sb-bench"><summary>Bench · ${benchPts.toFixed(1)} pts unused</summary>${bench.map(row).join('')}</details>` : ''}`;
  }

  function render() {
    const weeks = Object.keys(YD.weeks).map(Number).sort((a, b) => a - b);
    if (!weeks.length) {
      $('#week-picker').innerHTML = '';
      $('#sb-grid').innerHTML = A.notice(
        `ESPN has no matchup data stored for ${year}.`);
      return;
    }
    if (!weeks.includes(week)) week = weeks[0];

    $('#week-picker').innerHTML = weeks.map((w) =>
      `<button class="season-chip${w === week ? ' on' : ''}" data-w="${w}">W${w}${w > YD.regWeeks ? ' 🏆' : ''}</button>`).join('');
    $('#week-picker').querySelectorAll('.season-chip').forEach((b) =>
      b.addEventListener('click', () => { week = +b.dataset.w; render(); }));

    const games = [...YD.weeks[String(week)]].sort((a, b) =>
      (a.tier === 'WINNERS_BRACKET' ? 0 : 1) - (b.tier === 'WINNERS_BRACKET' ? 0 : 1));

    const banner = YD.hasRosters ? '' : A.notice(
      `ESPN does not retain weekly lineups for ${year} — final scores only. ` +
      `Full rosters are available from 2018 on.`);

    $('#sb-grid').innerHTML = banner + games.map((g) => {
      const hWin = g.home.pts > g.away.pts;
      const side = (s, win) => {
        const t = T[s.tid] || { name: 'Team ' + s.tid };
        return `<div class="sb-team${win ? ' win' : ''}">
          <div class="sb-team-head">
            ${A.logoHTML(t)}
            <div class="sb-team-name">${t.name}<span>${A.memberName(t.owner)}</span></div>
            <div class="sb-total${win ? ' w' : ''}">${s.pts.toFixed(1)}</div>
          </div>
          ${rosterHTML(s)}
        </div>`;
      };
      const tier = TIER[g.tier] || '';
      return `<div class="card sb-card">
        ${tier ? `<div class="sb-tier">${tier}</div>` : ''}
        <div class="sb-match">
          ${side(g.away, !hWin)}<div class="sb-vs">VS</div>${side(g.home, hWin)}
        </div>
      </div>`;
    }).join('');
  }

  async function pick(y) {
    year = y;
    week = null;
    $('#sb-grid').innerHTML = '<div class="loading">Loading ' + y + '…</div>';
    YD = await A.loadYear(y);
    T = A.teams(y);
    draw();
    render();
  }

  function draw() {
    A.yearPicker($('#year-picker'), year, pick, (i) => i.hasRosters ? '' : '*');
    $('#sb-sub').textContent =
      `${year} · ${YD.hasRosters ? 'full lineups' : 'scores only'}`;
  }

  const qs = new URLSearchParams(location.search);
  await pick(+qs.get('year') || A.years()[0]);
  if (qs.get('week')) { week = +qs.get('week'); render(); }
})();
