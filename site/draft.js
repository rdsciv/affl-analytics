/* ============ AFFL Draft Room — all seasons ============ */
(async function () {
  const A = window.AFFL;
  const $ = (s) => document.querySelector(s);
  await A.boot();
  A.chartDefaults(Chart);
  const C = A.C, fmt = A.fmt;

  let year = A.years()[0];
  let YD = null, T = {}, chart = null, scatterChart = null, contChart = null;
  const S = { q: '', limit: 60, holdoutScope: 'pooled', mekkoStack: 'half' };
  const HOLDOUT = await A.loadJSON('draft_holdout.json');

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

  /** Draft value is points ABOVE REPLACEMENT per dollar, computed in SQL
      (v_draft_value). Raw points/$ is positionally biased: a replacement QB
      already scores ~248, so any cheap QB looked like an infinite steal while
      genuinely scarce stud RBs graded as mediocre. */
  const scored = () => YD.draft.board.filter((p) => p.pts != null);
  const DV = () => YD.draftValue || { steals: [], busts: [], teamEff: [], baselines: [] };
  const parIndex = () => DV().parByOverall || {};

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
      (DV().steals || [])[0] && (() => {
        const s = DV().steals[0];
        return { n: '03 · BEST VALUE', color: C.green, pct: 1,
          label: '+' + fmt(s.par, 0),
          title: 'Steal Of The Draft',
          desc: `<strong>${s.name}</strong> · ${auction ? `$${s.bid || 0} → ` : ''}` +
                `${fmt(s.par, 0)} pts above replacement (${fmt(s.parPerDollar, 1)}/$)` };
      })(),
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
    const { steals, busts, baselines } = DV();
    const row = (p, cls) => `<tr>
      <td><strong>${p.name}</strong> <span class="badge pos-${p.pos}">${p.pos}</span>
        <div class="own">${short(p.tid)}</div></td>
      <td>${auction ? '$' + (p.bid || 0) : '#' + p.overall}</td>
      <td><span class="badge ${cls}">${p.par >= 0 ? '+' : ''}${fmt(p.par, 0)}</span>
        <div class="own">${fmt(p.pts, 0)} pts</div></td></tr>`;
    const none = `<tr><td colspan="3" class="own">ESPN stores no weekly scoring for ${year}, so returns can't be graded.</td></tr>`;
    $('#steals-tbl tbody').innerHTML = (steals || []).map((p) => row(p, 'steal')).join('') || none;
    $('#busts-tbl tbody').innerHTML = (busts || []).map((p) => row(p, 'bust')).join('') || '';

    // show the baseline so the number is auditable rather than magic
    const el = $('#baseline-note');
    if (el) {
      el.innerHTML = (baselines || []).length
        ? 'Replacement level this season — ' + baselines.map((b) =>
            `<strong>${b.position}</strong> ${fmt(b.baseline, 0)}`).join(' · ') +
          '. Value is points above that line, per dollar.'
        : '';
    }
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

    const pidx = parIndex();
    $('#board-tbl tbody').innerHTML = rows.slice(0, S.limit).map((p) => {
      let badge = '<td class="own">—</td>';
      const par = pidx[String(p.overall)];
      if (par != null) {
        badge = `<td><span class="badge ${par >= 0 ? 'steal' : 'bust'}">` +
                `${par >= 0 ? '+' : ''}${fmt(par, 0)}</span></td>`;
      }
      return `<tr>
        <td><span class="rank-pill${p.overall === 1 ? ' gold' : ''}">${p.overall}</span></td>
        <td><strong>${p.name}</strong>${p.keeper ? ' <span class="badge">keeper</span>' : ''}</td>
        <td><span class="badge pos-${p.pos}">${p.pos}</span></td>
        <td class="own">${p.nfl || '—'}</td>
        <td><a class="team-link" href="${A.teamHref(year, p.tid)}"><div class="team-cell">${A.logoHTML(T[p.tid], 'mini')}<span>${short(p.tid)}</span></div></a></td>
        <td><strong>${auction ? '$' + (p.bid || 0) : p.round + '.' + String(p.pick).padStart(2, '0')}</strong></td>
        <td>${p.pts != null ? fmt(p.pts, 1) : '—'}</td>
        ${badge}
      </tr>`;
    }).join('');
    $('#board-more').style.display = rows.length > S.limit ? 'block' : 'none';
  }

  const BUCKET_COLOR = {
    '$1': C.ice, '$2': C.blue, '$3–5': C.green, '$6–10': C.gold,
    '$11–20': C.orange, '$21–40': C.fire, '$41–70': C.red, '$71+': '#eef4ff',
  };
  const POS_FILL = { QB: C.blue, RB: C.green, WR: C.orange, TE: C.gold, K: C.ice, DST: C.steel };

  function parColor(par) {
    if (par == null) return C.steel;
    const t = Math.max(-1, Math.min(1, par / 80));
    const mix = (a, b, u) => {
      const h = (hex) => [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16));
      const A = h(a), B = h(b);
      const c = A.map((v, i) => Math.round(v + (B[i] - v) * u));
      return `rgb(${c[0]},${c[1]},${c[2]})`;
    };
    return t >= 0 ? mix('#3a4a63', '#93d500', t) : mix('#3a4a63', '#ff2d1a', -t);
  }

  function holdoutBlock() {
    const scored = (HOLDOUT.scoredAuctionSeasons || []).includes(year);
    if (S.holdoutScope === 'season' && scored && HOLDOUT.bySeason[String(year)]) {
      return HOLDOUT.bySeason[String(year)];
    }
    return HOLDOUT.pooled;
  }

  function signed(n) {
    if (n == null) return '—';
    return (n > 0 ? '+' : '') + fmt(n, 1);
  }

  function showTip(html, ev) {
    let tip = document.getElementById('viz-tip');
    if (!tip) {
      tip = document.createElement('div');
      tip.id = 'viz-tip';
      tip.className = 'mekko-tip';
      document.body.appendChild(tip);
    }
    tip.innerHTML = html;
    tip.style.display = 'block';
    const x = Math.min(ev.clientX + 14, window.innerWidth - 300);
    const y = Math.min(ev.clientY + 14, window.innerHeight - 160);
    tip.style.left = x + 'px';
    tip.style.top = y + 'px';
  }
  function hideTip() {
    const tip = document.getElementById('viz-tip');
    if (tip) tip.style.display = 'none';
  }

  function sliceTip(bucket, sliceKey, sl) {
    const examples = (sl.examples || []).map((e) =>
      `${e.year} ${e.name} ${signed(e.par)}`).join(' · ');
    return `<strong>${bucket} · ${sliceKey}</strong>
      n = ${sl.n}${sl.nNominated && sl.nNominated !== sl.n ? ` of ${sl.nNominated} nominated` : ''}
      · $${fmt(sl.spend)} spend<br>
      mean PAR ${signed(sl.meanPar)}
      ${examples ? `<div class="ex">${examples}</div>` : ''}`;
  }

  function renderMekko(block) {
    const el = $('#mekko');
    const buckets = block.mekko || [];
    if (!buckets.length) {
      el.innerHTML = A.notice('No auction PAR in this slice.');
      return;
    }
    const W = el.clientWidth || 560, H = el.clientHeight || 340;
    const pad = { t: 12, r: 10, b: 42, l: 36 };
    const innerW = W - pad.l - pad.r, innerH = H - pad.t - pad.b;
    const gap = 5;
    const totalShare = buckets.reduce((a, b) => a + (b.spendShare || 0), 0) || 1;
    let x = pad.l;
    const cols = buckets.map((b) => {
      const w = Math.max(18, (b.spendShare / totalShare) * (innerW - gap * (buckets.length - 1)));
      const col = { ...b, x, w };
      x += w + gap;
      return col;
    });

    const stacks = S.mekkoStack === 'pos'
      ? cols.map((b) => (b.byPos || []).map((s) => ({ key: s.pos, ...s })))
      : cols.map((b) => ['early', 'late'].map((k) => ({ key: k, ...(b.slices[k] || { n: 0, spend: 0, meanPar: null }) })));

    const maxN = Math.max(1, ...stacks.map((st) => st.reduce((a, s) => a + (s.n || 0), 0)));
    const rects = [];
    cols.forEach((b, i) => {
      const st = stacks[i].filter((s) => s.n > 0);
      const tot = st.reduce((a, s) => a + s.n, 0) || 1;
      let y = pad.t + innerH * (1 - tot / maxN);
      st.forEach((s) => {
        const h = innerH * (s.n / maxN);
        rects.push({ ...s, bucket: b.id, x: b.x, w: b.w, y, h, spendShare: b.spendShare });
        y += h;
      });
    });

    el.innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Marimekko of auction cost buckets">
      ${[0, 0.25, 0.5, 0.75, 1].map((t) => {
        const y = pad.t + innerH * (1 - t);
        return `<line x1="${pad.l}" x2="${W - pad.r}" y1="${y}" y2="${y}" stroke="${C.grid}"/>`;
      }).join('')}
      ${rects.map((r, i) => `<rect data-i="${i}" x="${r.x}" y="${r.y}" width="${r.w}" height="${Math.max(1, r.h)}"
        fill="${S.mekkoStack === 'pos' ? (POS_FILL[r.key] || C.steel) : parColor(r.meanPar)}"
        stroke="#05060b" stroke-width="1" opacity="0.92"/>`).join('')}
      ${cols.map((b) => `<text x="${b.x + b.w / 2}" y="${H - 22}" text-anchor="middle"
        fill="${C.ink}" font-size="11" font-weight="700">${b.id}</text>
        <text x="${b.x + b.w / 2}" y="${H - 8}" text-anchor="middle"
        fill="${C.mut}" font-size="10">${fmt((b.spendShare || 0) * 100, 1)}% spend</text>`).join('')}
      <text x="6" y="${pad.t + 8}" fill="${C.mut}" font-size="10">n</text>
    </svg>`;
    el.querySelectorAll('rect[data-i]').forEach((node) => {
      const r = rects[+node.dataset.i];
      node.addEventListener('mousemove', (ev) => showTip(sliceTip(r.bucket, r.key, r), ev));
      node.addEventListener('mouseleave', hideTip);
    });
  }

  function renderScatter(block) {
    const rows = block.scatter || [];
    if (scatterChart) scatterChart.destroy();
    const canvas = $('#holdout-scatter');
    if (!rows.length) {
      scatterChart = null;
      return;
    }
    scatterChart = new Chart(canvas, {
      type: 'scatter',
      data: {
        datasets: rows.map((b) => ({
          label: b.id,
          data: [
            { x: 0, y: b.early.meanPar, slice: 'early', bucket: b.id, meta: b.early },
            { x: 1, y: b.late.meanPar, slice: 'late', bucket: b.id, meta: b.late },
          ],
          showLine: true,
          borderColor: BUCKET_COLOR[b.id] || C.ice,
          backgroundColor: BUCKET_COLOR[b.id] || C.ice,
          borderWidth: 2,
          pointRadius: 5,
          pointHoverRadius: 7,
        })),
      },
      options: {
        maintainAspectRatio: false,
        plugins: {
          legend: { labels: { boxWidth: 10, boxHeight: 10, usePointStyle: true, pointStyle: 'circle' } },
          tooltip: {
            callbacks: {
              title: (items) => {
                const p = items[0].raw;
                return `${p.bucket} · ${p.slice}`;
              },
              label: (item) => {
                const m = item.raw.meta || {};
                const bits = [`mean PAR ${signed(item.raw.y)}`, `n=${m.n}`, `$${fmt(m.spend)} spend`];
                if (m.examples && m.examples.length) {
                  bits.push(m.examples.map((e) => `${e.year} ${e.name} ${signed(e.par)}`).join(' · '));
                }
                return bits;
              },
            },
          },
        },
        scales: {
          x: {
            min: -0.15, max: 1.15,
            ticks: { callback: (v) => (v === 0 ? 'Early' : v === 1 ? 'Late' : '') },
            grid: { color: C.grid }, border: { display: false },
          },
          y: {
            title: { display: true, text: 'mean PAR' },
            grid: { color: C.grid }, border: { display: false },
          },
        },
      },
    });
  }

  function renderContinuous(block) {
    const rows = block.continuous || [];
    if (contChart) { contChart.destroy(); contChart = null; }
    const canvas = $('#holdout-continuous');
    if (!canvas || !rows.length) return;
    contChart = new Chart(canvas, {
      type: 'scatter',
      data: {
        datasets: rows.map((b) => ({
          label: b.id,
          data: (b.points || []).map((p) => ({
            x: p.meanOverall, y: p.meanPar, n: p.n, q: p.q, bucket: b.id,
          })),
          showLine: true,
          borderColor: BUCKET_COLOR[b.id] || C.ice,
          backgroundColor: BUCKET_COLOR[b.id] || C.ice,
          borderWidth: 2,
          pointRadius: 4,
        })),
      },
      options: {
        maintainAspectRatio: false,
        plugins: {
          legend: { labels: { boxWidth: 10, boxHeight: 10, usePointStyle: true, pointStyle: 'circle' } },
          tooltip: {
            callbacks: {
              title: (items) => `${items[0].raw.bucket} · quintile ${items[0].raw.q}`,
              label: (item) => `mean PAR ${signed(item.raw.y)} · mean overall ${fmt(item.raw.x, 0)} · n=${item.raw.n}`,
            },
          },
        },
        scales: {
          x: { title: { display: true, text: 'mean overall pick' }, grid: { color: C.grid }, border: { display: false } },
          y: { title: { display: true, text: 'mean PAR' }, grid: { color: C.grid }, border: { display: false } },
        },
      },
    });
  }

  function renderHoldout() {
    const scored = (HOLDOUT.scoredAuctionSeasons || []).includes(year);
    const canSeason = scored && HOLDOUT.bySeason[String(year)];
    if (!canSeason) S.holdoutScope = 'pooled';

    $('#holdout-scope').innerHTML = [
      ['pooled', 'All scored auction years'],
      canSeason ? ['season', String(year)] : null,
    ].filter(Boolean).map(([id, lab]) =>
      `<button class="filter-chip${S.holdoutScope === id ? ' on' : ''}" data-scope="${id}">${lab}</button>`
    ).join('');
    $('#holdout-stack').innerHTML = [
      ['half', 'Stack: early / late'],
      ['pos', 'Stack: position'],
    ].map(([id, lab]) =>
      `<button class="filter-chip${S.mekkoStack === id ? ' on' : ''}" data-stack="${id}">${lab}</button>`
    ).join('');

    const block = holdoutBlock();
    const claim = S.holdoutScope === 'pooled'
      ? HOLDOUT.claim
      : (block.claim ? `${block.claim} (${year} auction, non-keepers).` : HOLDOUT.claim);
    $('#holdout-title').textContent = (claim || '').split(':')[0] || 'Auction holdouts';
    $('#holdout-claim').textContent = claim || '';
    $('#holdout-sub').textContent = S.holdoutScope === 'pooled'
      ? HOLDOUT.subtitle
      : `${year} auction player-seasons · width = share of that draft's spend · stacks = ${S.mekkoStack === 'pos' ? 'position' : 'early/late nomination half'} · color = mean PAR`;

    const notes = [];
    if (!YD.draft.auction) {
      notes.push(`${year} is a snake draft (no auction bids). Charts stay on 2018–2025 auction seasons.`);
    } else if (!scored) {
      notes.push(`${year} is auction but ESPN stored no weekly scoring, so PAR is blank. Charts stay on scored auction years.`);
    }
    notes.push(HOLDOUT.keepers.note);
    notes.push(HOLDOUT.histogramNote);
    notes.push('Grain: ' + HOLDOUT.grain + '. Metric is PAR from v_draft_value — not WARP.');
    $('#holdout-note').innerHTML = notes.join(' ');

    renderMekko(block);
    renderScatter(block);
    renderContinuous(block);
  }

  async function pick(y) {
    year = y;
    S.limit = 60;
    YD = await A.loadYear(y);
    T = A.teams(y);
    A.yearPicker($('#year-picker'), year, pick);
    $('#page-sub').textContent = `${year} · ${YD.draft.auction ? 'auction' : 'snake'} draft · ${YD.draft.board.length} picks`;
    renderKPIs(); renderSpend(); renderValue(); renderBoard(); renderHoldout();
  }

  $('#holdout-scope').addEventListener('click', (e) => {
    const b = e.target.closest('[data-scope]');
    if (!b) return;
    S.holdoutScope = b.dataset.scope;
    renderHoldout();
  });
  $('#holdout-stack').addEventListener('click', (e) => {
    const b = e.target.closest('[data-stack]');
    if (!b) return;
    S.mekkoStack = b.dataset.stack;
    renderHoldout();
  });
  window.addEventListener('resize', () => { if (YD) renderMekko(holdoutBlock()); });
  document.querySelector('.holdout-continuous').addEventListener('toggle', (e) => {
    if (e.target.open && YD) renderContinuous(holdoutBlock());
  });

  $('#board-more').addEventListener('click', () => { S.limit += 60; renderBoard(); });
  $('#draft-search').addEventListener('input', (e) => { S.q = e.target.value; S.limit = 60; renderBoard(); });

  const qs = new URLSearchParams(location.search);
  await pick(+qs.get('year') || A.years()[0]);
})();
