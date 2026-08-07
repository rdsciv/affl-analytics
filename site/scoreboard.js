/* ============ AFFL Scoreboard — joined to PlayerProfiler ============ */
(async function () {
  const [DATA, SB] = await Promise.all([
    fetch('data.json?v=' + Date.now(), { cache: 'no-store' }).then((r) => r.json()),
    fetch('scoreboard.json?v=' + Date.now(), { cache: 'no-store' }).then((r) => r.json()),
  ]);
  const $ = (s) => document.querySelector(s);

  const T25 = {};
  DATA.seasons['2025'].teams.forEach((t) => { T25[t.id] = t; });
  const profiled = new Set((DATA.nextgen.players || []).map((p) => p.pid));

  const weeks = Object.keys(SB.weeks).map(Number).sort((a, b) => a - b);
  let curWeek = weeks[0];

  const TIER_LABEL = {
    WINNERS_BRACKET: 'Playoffs', LOSERS_CONSOLATION_LADDER: 'Consolation',
    WINNERS_CONSOLATION_LADDER: 'Consolation', NONE: '',
  };
  const SLOT_ORDER = { QB: 0, RB: 1, WR: 2, TE: 3, FLEX: 4, 'RB/WR': 4, 'WR/TE': 4, OP: 4, 'D/ST': 5, K: 6 };

  function logoHTML(t) {
    const initial = (t.name || '?').replace(/[^A-Za-z0-9]/g, '').charAt(0).toUpperCase() || '?';
    if (t.logo && /^(https?:|logos\/)/.test(t.logo)) {
      return `<img class="sb-logo" src="${t.logo}" alt="" loading="lazy"
        onerror="this.outerHTML='<div class=&quot;sb-logo fb&quot;>${initial}</div>'">`;
    }
    return `<div class="sb-logo fb">${initial}</div>`;
  }

  function playerLink(pid, extra) {
    const p = SB.players[String(pid)];
    if (!p) return '<span class="sb-name">—</span>';
    const cls = profiled.has(pid) ? 'sb-name link' : 'sb-name';
    const href = profiled.has(pid) ? ` href="players.html?pid=${pid}"` : '';
    const tag = profiled.has(pid) ? 'a' : 'span';
    return `<${tag} class="${cls}"${href}>${p[0]}${extra || ''}</${tag}>`;
  }

  function rosterHTML(side) {
    const starters = side.roster.filter((r) => r[1] !== 'BN' && r[1] !== 'IR')
      .sort((a, b) => (SLOT_ORDER[a[1]] ?? 9) - (SLOT_ORDER[b[1]] ?? 9));
    const bench = side.roster.filter((r) => r[1] === 'BN' || r[1] === 'IR')
      .sort((a, b) => b[2] - a[2]);
    const row = (r) => {
      const p = SB.players[String(r[0])] || ['—', '', ''];
      return `<div class="sb-row">
        <span class="sb-slot">${r[1]}</span>
        ${playerLink(r[0])}
        <span class="sb-nfl">${p[2] || ''}</span>
        <span class="sb-pts">${r[2].toFixed(1)}</span>
      </div>`;
    };
    return `${starters.map(row).join('')}
      <details class="sb-bench"><summary>Bench · ${bench.reduce((a, r) => a + r[2], 0).toFixed(1)} pts unused</summary>
        ${bench.map(row).join('')}
      </details>`;
  }

  function render() {
    $('#week-picker').innerHTML = weeks.map((w) => {
      const tier = SB.weeks[w].some((g) => g.tier === 'WINNERS_BRACKET');
      return `<button class="season-chip${w === curWeek ? ' on' : ''}" data-w="${w}">W${w}${w > 14 ? ' 🏆' : ''}</button>`;
    }).join('');
    document.querySelectorAll('#week-picker .season-chip').forEach((b) =>
      b.addEventListener('click', () => { curWeek = +b.dataset.w; render(); window.scrollTo(0, 0); }));

    const games = [...SB.weeks[curWeek]].sort((a, b) =>
      (a.tier === 'WINNERS_BRACKET' ? 0 : 1) - (b.tier === 'WINNERS_BRACKET' ? 0 : 1));

    $('#sb-grid').innerHTML = games.map((g) => {
      const hWin = g.home.pts > g.away.pts;
      const side = (s, win) => {
        const t = T25[s.tid] || { name: 'Team ' + s.tid };
        return `<div class="sb-team${win ? ' win' : ''}">
          <div class="sb-team-head">
            ${logoHTML(t)}
            <div class="sb-team-name">${t.name}<span>${DATA.members[t.owner] || ''}</span></div>
            <div class="sb-total${win ? ' w' : ''}">${s.pts.toFixed(1)}</div>
          </div>
          ${rosterHTML(s)}
        </div>`;
      };
      const tier = TIER_LABEL[g.tier] || '';
      return `<div class="card sb-card">
        ${tier ? `<div class="sb-tier">${tier}</div>` : ''}
        <div class="sb-match">
          ${side(g.away, !hWin)}
          <div class="sb-vs">VS</div>
          ${side(g.home, hWin)}
        </div>
      </div>`;
    }).join('');
  }

  render();
})();
