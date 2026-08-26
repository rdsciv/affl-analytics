/* AFFL History Book — archive, records, franchises. Stats come from
   history.json + split parts (MCP payload limit). Missing 2014–17 benches/tx stay missing. */
(function () {
  const FIRST = 2014;
  const LAST = 2025;
  const $ = (s, r) => (r || document).querySelector(s);
  const $$ = (s, r) => [...(r || document).querySelectorAll(s)];

  let H = null;
  let DATA = null;

  const NAV = [
    ['archive.html', 'Archive'],
    ['records.html', 'Records'],
    ['teams.html', 'Teams'],
    ['awards.html', 'Awards'],
    ['draft.html', 'Draft'],
    ['scoreboard.html', 'Scoreboard'],
  ];

  function bust(url) { return url + (url.includes('?') ? '&' : '?') + 'v=hist3'; }

  async function jsonOrEmpty(url) {
    const r = await fetch(bust(url), { cache: 'no-store' });
    if (!r.ok) return {};
    return r.json();
  }

  async function boot() {
    if (H && DATA) return { H, DATA };
    const [h, extraF, extraL, d] = await Promise.all([
      fetch(bust('history.json'), { cache: 'no-store' }).then((r) => r.json()),
      jsonOrEmpty('history-franchises.json'),
      jsonOrEmpty('history-ledger.json'),
      fetch(bust('data.json'), { cache: 'no-store' }).then((r) => r.json()),
    ]);
    H = Object.assign({}, h, extraF, extraL);
    DATA = d;
    return { H, DATA };
  }

  function years() {
    return H.years.map((y) => y.year).filter((y) => y >= FIRST && y <= LAST);
  }

  function yearCard(y) {
    return H.years.find((row) => row.year === y);
  }

  function franchise(owner) {
    return H.franchises.find((f) => f.owner === owner);
  }

  function qs(name, fallback) {
    const v = new URLSearchParams(location.search).get(name);
    return v == null || v === '' ? fallback : v;
  }

  function fmt(n, d) {
    if (n == null || n === '' || Number.isNaN(Number(n))) return '—';
    return Number(n).toLocaleString('en-US', {
      maximumFractionDigits: d == null ? 1 : d,
      minimumFractionDigits: d == null ? 0 : d,
    });
  }

  function initials(name) {
    return (name || '?').split(/\s+/).filter(Boolean).map((x) => x[0]).join('').slice(0, 2).toUpperCase();
  }

  function mark(logo, name) {
    const ini = initials(name);
    if (logo && /^(https?:|logos\/)/.test(logo)) {
      return `<img class="archive-mark" src="${logo}" alt="" width="28" height="28" loading="lazy"
        onerror="if(this.parentNode)this.outerHTML='<div class=&quot;archive-mark fb&quot;>${ini}</div>'">`;
    }
    return `<div class="archive-mark fb">${ini}</div>`;
  }

  function franLink(owner, label) {
    if (!owner || owner.startsWith('new-')) return label;
    return `<a class="fran-link" href="franchise.html?id=${encodeURIComponent(owner)}">${label}</a>`;
  }

  function chrome(opts) {
    const page = opts.page;
    const title = opts.title;
    const accent = opts.accent || 'History';
    const sub = opts.sub || 'ESPN 51418 · non-PPR · 2014–2025';
    const nav = NAV.map(([href, label]) => {
      const on = href === page ? ' on' : '';
      return `<a href="${href}" class="${on.trim()}">${label}</a>`;
    }).join('');
    const host = $('#site-chrome');
    if (!host) return;
    host.innerHTML = `
      <header class="topbar">
        <a class="brand brand-link" href="archive.html">
          <div class="brand-mark" aria-hidden="true"></div>
          <div>
            <h1>AFFL <span>${accent}</span></h1>
            <div class="sub">${sub}</div>
          </div>
        </a>
        <nav class="site-nav">${nav}</nav>
      </header>`;
    const foot = $('#site-foot');
    if (foot) {
      foot.innerHTML = `
        <img class="foot-banner" src="logos/affl-chrome.jpg" alt="AFFL">
        <div>AFFL History Book · ESPN league 51418 · non-PPR · seasons 2014–2025 · no 2026 season until the draft</div>`;
    }
    document.title = title || `AFFL ${accent}`;
  }

  function yearChips(el, cur, onPick) {
    const list = years();
    el.innerHTML = list.map((y) =>
      `<button class="season-chip${y === cur ? ' on' : ''}" data-y="${y}" type="button">${y}</button>`
    ).join('');
    el.querySelectorAll('.season-chip').forEach((b) => {
      b.addEventListener('click', () => onPick(+b.dataset.y));
    });
  }

  function sortTable(table) {
    const tbody = table.tBodies[0];
    if (!tbody) return;
    $$('th[data-sort]', table).forEach((th) => {
      th.classList.add('sortable');
      th.addEventListener('click', () => {
        const key = th.dataset.sort;
        const type = th.dataset.type || 'num';
        const dir = th.dataset.dir === 'asc' ? 'desc' : 'asc';
        $$('th[data-sort]', table).forEach((h) => { h.dataset.dir = ''; h.classList.remove('sorted-asc', 'sorted-desc'); });
        th.dataset.dir = dir;
        th.classList.add(dir === 'asc' ? 'sorted-asc' : 'sorted-desc');
        const rows = [...tbody.rows];
        rows.sort((a, b) => {
          const av = a.dataset[key] ?? a.getAttribute('data-' + key) ?? '';
          const bv = b.dataset[key] ?? b.getAttribute('data-' + key) ?? '';
          let cmp;
          if (type === 'num') cmp = Number(av) - Number(bv);
          else cmp = String(av).localeCompare(String(bv), undefined, { sensitivity: 'base' });
          return dir === 'asc' ? cmp : -cmp;
        });
        rows.forEach((r) => tbody.appendChild(r));
      });
    });
  }

  function honorLine(label, h, cls) {
    return `<div class="honor ${cls || ''}">
      <span class="honor-k">${label}</span>
      <span class="honor-v">${mark(h.logo, h.currentName)} ${franLink(h.owner, h.currentName)}</span>
      <span class="honor-s">${h.record} · ${fmt(h.pf, 1)} PF</span>
    </div>`;
  }

  function renderYearWall() {
    const wall = $('#year-wall');
    wall.innerHTML = H.years.map((y) => `
      <a class="year-card" href="year.html?y=${y.year}" data-year="${y.year}">
        <div class="yc-year">${y.year}</div>
        <div class="yc-row champ">${mark(y.champion.logo, y.champion.currentName)}
          <div><div class="yc-k">Champion</div><div class="yc-n">${y.champion.currentName}</div>
          <div class="yc-s">${y.champion.record} · ${fmt(y.champion.pf, 1)} PF</div></div>
        </div>
        <div class="yc-row">${mark(y.runnerUp.logo, y.runnerUp.currentName)}
          <div><div class="yc-k">Runner-up</div><div class="yc-n">${y.runnerUp.currentName}</div>
          <div class="yc-s">${y.runnerUp.record} · ${fmt(y.runnerUp.pf, 1)} PF</div></div>
        </div>
        <div class="yc-row">${mark(y.third.logo, y.third.currentName)}
          <div><div class="yc-k">Third</div><div class="yc-n">${y.third.currentName}</div>
          <div class="yc-s">${y.third.record} · ${fmt(y.third.pf, 1)} PF</div></div>
        </div>
        <div class="yc-row sacko">${mark(y.sacko.logo, y.sacko.currentName)}
          <div><div class="yc-k">Sacko</div><div class="yc-n">${y.sacko.currentName}</div>
          <div class="yc-s">${y.sacko.record} · ${fmt(y.sacko.pf, 1)} PF</div></div>
        </div>
        <div class="yc-row pt">${mark(y.pointTitle.logo, y.pointTitle.currentName)}
          <div><div class="yc-k">Point title</div><div class="yc-n">${y.pointTitle.currentName}</div>
          <div class="yc-s">${y.pointTitle.record} · ${fmt(y.pointTitle.pf, 1)} PF</div></div>
        </div>
      </a>`).join('');
  }

  function renderYearPage() {
    const y = +qs('y', qs('year', LAST));
    const card = yearCard(y);
    if (!card || y < FIRST || y > LAST) {
      $('#year-body').innerHTML = '<div class="notice">No AFFL season for that year. Archive is 2014–2025 only.</div>';
      return;
    }
    chrome({
      page: 'year.html',
      title: `${y} · AFFL History`,
      accent: String(y),
      sub: `${card.teamCount} teams · current franchise names`,
    });
    yearChips($('#year-chips'), y, (next) => { location.href = `year.html?y=${next}`; });

    const season = DATA.seasons[String(y)];
    const teams = [...season.teams].sort((a, b) => a.finalRank - b.finalRank);
    const info = (window.AFFL && window.AFFL.yearInfo) ? window.AFFL.yearInfo(y) : {};
    const missing = [];
    if (y <= 2017) {
      missing.push('Weekly benches and transactions are not in the ESPN extract for 2014–17. Missing stays missing — not zero, not “not rostered.”');
    }

    $('#year-honors').innerHTML =
      honorLine('Champion', card.champion, 'gold') +
      honorLine('Runner-up', card.runnerUp, 'slv') +
      honorLine('Third', card.third, 'brz') +
      honorLine('Sacko', card.sacko, 'sacko') +
      honorLine('Point title', card.pointTitle, 'pt');

    $('#year-links').innerHTML = `
      <a class="page-link" href="draft.html?year=${y}">Draft</a>
      <a class="page-link" href="awards.html?y=${y}">Awards</a>
      <a class="page-link" href="teams.html">Teams</a>
      <a class="page-link" href="scoreboard.html?year=${y}">Scoreboard</a>
      <a class="page-link" href="records.html">Records</a>`;

    $('#year-note').innerHTML = missing.length
      ? `<div class="notice">${missing.join(' ')}</div>`
      : '';

    const body = teams.map((t) => {
      const owner = _canon(t.owner);
      const fr = franchise(owner);
      const name = fr ? fr.currentName : t.name;
      const ownerName = fr ? fr.ownerName : (DATA.members[t.owner] || '');
      const rec = t.ties ? `${t.wins}-${t.losses}-${t.ties}` : `${t.wins}-${t.losses}`;
      const pill = t.finalRank === 1 ? ' gold' : t.finalRank === 2 ? ' slv' : t.finalRank === 3 ? ' brz' : '';
      return `<tr data-rank="${t.finalRank}" data-name="${name}" data-pf="${t.pf}" data-wins="${t.wins}">
        <td><span class="rank-pill${pill}">${t.finalRank}</span></td>
        <td><div class="team-cell">${mark(t.logo, name)} <span>${franLink(owner, name)}<span class="own"> ${ownerName}</span></span></div></td>
        <td>${rec}</td>
        <td>${fmt(t.pf, 1)}</td>
        <td>${fmt(t.pa, 1)}</td>
        <td>${fmt(t.avgPts, 1)}</td>
        <td>${t.allplayW}–${t.allplayL}</td>
      </tr>`;
    }).join('');
    $('#standings-tbl tbody').innerHTML = body;
    sortTable($('#standings-tbl'));
    void info;
  }

  function _canon(oid) {
    const map = { m01: 'm07', m03: 'm08', m20: 'm10' };
    return map[oid] || oid;
  }

  function renderFranchise() {
    const id = qs('id', '');
    const fr = franchise(id);
    if (!fr) {
      $('#franchise-body').innerHTML = '<div class="notice">Unknown franchise. <a href="teams.html">Back to teams</a>.</div>';
      return;
    }
    chrome({
      page: 'teams.html',
      title: `${fr.currentName} · AFFL History`,
      accent: 'Franchise',
      sub: `${fr.ownerName} · ${fr.seasons} seasons · ${fr.status}`,
    });
    yearChips($('#year-chips'), null, (y) => { location.href = `year.html?y=${y}`; });

    $('#fran-hero').innerHTML = `
      <div class="fran-ident">${mark(fr.logo, fr.currentName)}
        <div>
          <h2 class="fran-name">${fr.currentName}</h2>
          <div class="card-sub">${fr.ownerName} · ${fr.status} · ${fr.years[0]}–${fr.years[fr.years.length - 1]}</div>
        </div>
      </div>
      <div class="kpi-row fran-kpis">
        <div class="card kpi-mini"><div class="hs-value">${fr.wins}-${fr.losses}</div><div class="hs-label">career W-L</div></div>
        <div class="card kpi-mini"><div class="hs-value">${fmt(fr.winPct * 100, 1)}%</div><div class="hs-label">win %</div></div>
        <div class="card kpi-mini"><div class="hs-value">${fr.championships}</div><div class="hs-label">titles</div></div>
        <div class="card kpi-mini"><div class="hs-value">${fr.combinedTitles}</div><div class="hs-label">combined titles</div></div>
      </div>`;

    const rows = fr.years.map((year) => {
      const season = DATA.seasons[String(year)];
      const team = season.teams.find((t) => _canon(t.owner) === fr.owner);
      if (!team) return '';
      const rec = team.ties ? `${team.wins}-${team.losses}-${team.ties}` : `${team.wins}-${team.losses}`;
      const pill = team.finalRank === 1 ? ' gold' : team.finalRank === 2 ? ' slv' : team.finalRank === 3 ? ' brz' : '';
      return `<tr data-year="${year}" data-rank="${team.finalRank}" data-pf="${team.pf}" data-wins="${team.wins}">
        <td><a class="fran-link" href="year.html?y=${year}">${year}</a></td>
        <td>${team.name}</td>
        <td><span class="rank-pill${pill}">${team.finalRank}</span></td>
        <td>${rec}</td>
        <td>${fmt(team.pf, 1)}</td>
        <td>${fmt(team.pa, 1)}</td>
      </tr>`;
    }).join('');
    $('#fran-seasons tbody').innerHTML = rows;
    sortTable($('#fran-seasons'));

    $('#fran-honors').innerHTML = `
      <li>Championships: <strong>${fr.championships}</strong></li>
      <li>Seconds: <strong>${fr.seconds}</strong></li>
      <li>Thirds: <strong>${fr.thirds}</strong></li>
      <li>Point titles: <strong>${fr.pointTitles}</strong></li>
      <li>Sackos: <strong>${fr.sackos}</strong></li>
      <li>Combined titles (C+2nd+3rd+PT−sacko): <strong>${fr.combinedTitles}</strong></li>`;
  }

  function renderRecords() {
    chrome({
      page: 'records.html',
      title: 'Records · AFFL History',
      accent: 'Records',
      sub: 'Career, combined titles, heatmap, trophy case, H2H, single-season',
    });
    yearChips($('#year-chips'), null, (y) => { location.href = `year.html?y=${y}`; });

    $('#franchise-tbl tbody').innerHTML = H.franchises.map((f) => {
      const rec = f.ties ? `${f.wins}-${f.losses}-${f.ties}` : `${f.wins}-${f.losses}`;
      return `<tr data-name="${f.currentName}" data-years="${f.seasons}" data-winpct="${f.winPct}" data-titles="${f.titles}" data-pf="${f.pf}" data-combined="${f.combinedTitles}">
        <td>${f.ownerName}</td>
        <td><div class="team-cell">${mark(f.logo, f.currentName)} ${franLink(f.owner, f.currentName)}</div></td>
        <td>${f.seasons}</td>
        <td>${rec}</td>
        <td>${fmt(f.winPct * 100, 1)}%</td>
        <td>${f.titles}</td>
        <td>${fmt(f.pf, 1)}</td>
      </tr>`;
    }).join('');
    sortTable($('#franchise-tbl'));

    $('#combined-tbl tbody').innerHTML = H.franchises.map((f) => `
      <tr data-name="${f.currentName}" data-combined="${f.combinedTitles}" data-c="${f.championships}" data-s="${f.seconds}" data-t="${f.thirds}" data-pt="${f.pointTitles}" data-sk="${f.sackos}">
        <td><div class="team-cell">${mark(f.logo, f.currentName)} ${franLink(f.owner, f.currentName)}</div></td>
        <td>${f.championships}</td>
        <td>${f.seconds}</td>
        <td>${f.thirds}</td>
        <td>${f.pointTitles}</td>
        <td>${f.sackos}</td>
        <td><strong>${f.combinedTitles}</strong></td>
      </tr>`).join('');
    sortTable($('#combined-tbl'));

    const yrs = years();
    const head = `<tr><th>Franchise</th>${yrs.map((y) => `<th>${y}</th>`).join('')}</tr>`;
    const heatBody = H.franchises.filter((f) => f.seasons).map((f) => {
      const cells = yrs.map((y) => {
        const fin = f.finishes[String(y)];
        if (fin == null) return '<td class="heat-empty">·</td>';
        let cls = 'heat-mid';
        if (fin === 1) cls = 'heat-1';
        else if (fin === 2) cls = 'heat-2';
        else if (fin === 3) cls = 'heat-3';
        else if (fin >= 10) cls = 'heat-last';
        return `<td class="${cls}"><a href="year.html?y=${y}">${fin}</a></td>`;
      }).join('');
      return `<tr><td><div class="team-cell">${mark(f.logo, f.currentName)} ${franLink(f.owner, f.currentName)}</div></td>${cells}</tr>`;
    }).join('');
    $('#heatmap-tbl').innerHTML = head + heatBody;

    $('#timeline').innerHTML = H.timeline.map((t) => `
      <a class="tl-card" href="year.html?y=${t.year}">
        <div class="tl-year">${t.year}</div>
        <div class="tl-team">${mark(t.logo, t.currentName)} ${t.currentName}</div>
        <div class="tl-own">${t.ownerName} · ${t.record}</div>
      </a>`).join('');

    $('#trophy-case').innerHTML = H.franchises.filter((f) => f.championships).map((f) => {
      const yrs = H.years.filter((y) => y.champion.owner === f.owner).map((y) => y.year);
      return `<div class="trophy">
        ${mark(f.logo, f.currentName)}
        <div><div class="yc-n">${franLink(f.owner, f.currentName)}</div>
        <div class="yc-s">${f.championships} title${f.championships === 1 ? '' : 's'} · ${yrs.join(', ')}</div></div>
      </div>`;
    }).join('');

    renderH2H();
    renderSeasonLists();
  }

  function renderH2H() {
    const active = H.franchises.filter((f) => f.status === 'current');
    const ids = active.map((f) => f.owner);
    const map = {};
    H.h2h.forEach((r) => {
      const a = _canon(r.a);
      const b = _canon(r.b);
      map[a + ':' + b] = [r.aW, r.bW];
      map[b + ':' + a] = [r.bW, r.aW];
    });
    const name = (id) => (franchise(id) || {}).currentName || id;
    const head = `<tr><th></th>${ids.map((id) => `<th title="${name(id)}">${mark((franchise(id) || {}).logo, name(id))}</th>`).join('')}</tr>`;
    const body = ids.map((row) => {
      const cells = ids.map((col) => {
        if (row === col) return '<td class="h2h-x">—</td>';
        const r = map[row + ':' + col];
        if (!r) return '<td class="h2h-x">·</td>';
        const cls = r[0] > r[1] ? 'h2h-w' : r[0] < r[1] ? 'h2h-l' : 'h2h-e';
        return `<td><span class="h2h-cell ${cls}">${r[0]}–${r[1]}</span></td>`;
      }).join('');
      return `<tr><td><div class="team-cell">${mark((franchise(row) || {}).logo, name(row))} ${franLink(row, name(row))}</div></td>${cells}</tr>`;
    }).join('');
    $('#h2h-tbl').innerHTML = head + body;
  }

  function seasonRows(list) {
    return list.map((r) => `
      <tr>
        <td><a class="fran-link" href="year.html?y=${r.year}">${r.year}</a></td>
        <td><div class="team-cell">${mark(r.logo, r.currentName)} ${franLink(r.owner, r.currentName)}</div></td>
        <td>${r.record}</td>
        <td>${fmt(r.pf, 1)}</td>
        <td>${fmt(r.avgPts, 1)}</td>
        <td>${r.finalRank}</td>
      </tr>`).join('');
  }

  function renderSeasonLists() {
    const R = H.records;
    $('#ss-pf tbody').innerHTML = seasonRows(R.highestPf);
    $('#ss-wins tbody').innerHTML = seasonRows(R.mostWins);
    $('#ss-low tbody').innerHTML = seasonRows(R.lowestPf);
    $('#ss-loss tbody').innerHTML = seasonRows(R.mostLosses);
  }

  function renderAwards() {
    const y = +qs('y', 0);
    chrome({
      page: 'awards.html',
      title: 'Awards · AFFL History',
      accent: 'Awards',
      sub: 'Champions, seconds, thirds, point titles, sackos',
    });
    yearChips($('#year-chips'), y || null, (next) => { location.href = `awards.html?y=${next}`; });

    const rows = (y ? H.years.filter((row) => row.year === y) : H.years);
    $('#awards-tbl tbody').innerHTML = rows.map((row) => `
      <tr>
        <td><a class="fran-link" href="year.html?y=${row.year}">${row.year}</a></td>
        <td><div class="team-cell">${mark(row.champion.logo, row.champion.currentName)} ${franLink(row.champion.owner, row.champion.currentName)}</div></td>
        <td><div class="team-cell">${mark(row.runnerUp.logo, row.runnerUp.currentName)} ${franLink(row.runnerUp.owner, row.runnerUp.currentName)}</div></td>
        <td><div class="team-cell">${mark(row.third.logo, row.third.currentName)} ${franLink(row.third.owner, row.third.currentName)}</div></td>
        <td><div class="team-cell">${mark(row.sacko.logo, row.sacko.currentName)} ${franLink(row.sacko.owner, row.sacko.currentName)}</div></td>
        <td><div class="team-cell">${mark(row.pointTitle.logo, row.pointTitle.currentName)} ${franLink(row.pointTitle.owner, row.pointTitle.currentName)}</div></td>
      </tr>`).join('');

    $('#trophy-case').innerHTML = H.franchises.filter((f) => f.championships).map((f) => {
      const yrs = H.years.filter((row) => row.champion.owner === f.owner).map((row) => row.year);
      return `<div class="trophy">
        ${mark(f.logo, f.currentName)}
        <div><div class="yc-n">${franLink(f.owner, f.currentName)}</div>
        <div class="yc-s">${yrs.join(' · ')}</div></div>
      </div>`;
    }).join('');
  }

  function renderTeams() {
    chrome({
      page: 'teams.html',
      title: 'Teams · AFFL History',
      accent: 'Teams',
      sub: 'Current names · Pounders & Pollywogs historic · Chupacabras current · Gabagooners new',
    });
    yearChips($('#year-chips'), null, (y) => { location.href = `year.html?y=${y}`; });

    const groups = [
      ['Current franchises', H.franchises.filter((f) => f.status === 'current')],
      ['Historic franchises', H.franchises.filter((f) => f.status === 'historic')],
    ];
    $('#teams-grid').innerHTML = groups.map(([label, list]) => `
      <section class="card">
        <div class="card-head"><h2>${label}</h2></div>
        <div class="team-dir">
          ${list.map((f) => `
            <a class="team-tile" href="franchise.html?id=${encodeURIComponent(f.owner)}">
              ${mark(f.logo, f.currentName)}
              <div>
                <div class="yc-n">${f.currentName}</div>
                <div class="yc-s">${f.ownerName} · ${f.seasons} szn · ${f.wins}-${f.losses}</div>
              </div>
            </a>`).join('')}
        </div>
      </section>`).join('');

    $('#new-franchises').innerHTML = H.newFranchises.map((n) => `
      <div class="team-tile new">
        <div class="archive-mark fb">${initials(n.name)}</div>
        <div>
          <div class="yc-n">${n.name}</div>
          <div class="yc-s">${n.note}</div>
        </div>
      </div>`).join('');
  }

  async function start(page) {
    await boot();
    if (window.AFFL && AFFL.boot) await AFFL.boot();
    if (page === 'archive') {
      chrome({ page: 'archive.html', title: 'AFFL History', accent: 'History', sub: 'The archive · 2014–2025 · current franchise names' });
      yearChips($('#year-chips'), null, (y) => { location.href = `year.html?y=${y}`; });
      renderYearWall();
    } else if (page === 'year') renderYearPage();
    else if (page === 'franchise') renderFranchise();
    else if (page === 'records') renderRecords();
    else if (page === 'awards') renderAwards();
    else if (page === 'teams') renderTeams();
    else {
      const _never = page;
      void _never;
    }
  }

  window.AFFLHistory = {
    boot, start, years, yearCard, franchise, mark, fmt, chrome, yearChips,
    _canon,
  };
})();
