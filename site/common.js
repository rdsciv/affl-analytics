/* ============ shared across all AFFL pages ============ */
window.AFFL = (function () {
  const C = {
    blue: '#2f7bff', blue2: '#47a8ff', ice: '#9fd8ff', steel: '#3a4a63',
    orange: '#ff7a00', fire: '#ff5a1e', gold: '#ffc400', gold2: '#ffcc33',
    green: '#93d500', red: '#ff2d1a',
    mut: '#7d8aa0', ink: '#eef4ff', grid: '#1b243366',
  };

  const bust = () => '?v=' + Date.now();
  let DATA = null;
  let MANIFEST = null;
  const yearCache = new Map();

  async function boot() {
    if (DATA) return { DATA, MANIFEST };
    [DATA, MANIFEST] = await Promise.all([
      fetch('data.json' + bust(), { cache: 'no-store' }).then((r) => r.json()),
      fetch('index_years.json' + bust(), { cache: 'no-store' }).then((r) => r.json()),
    ]);
    return { DATA, MANIFEST };
  }

  async function loadYear(year) {
    if (yearCache.has(year)) return yearCache.get(year);
    const d = await fetch(`years/${year}.json` + bust(), { cache: 'no-store' }).then((r) => r.json());
    yearCache.set(year, d);
    return d;
  }

  const years = () => MANIFEST.years.map((y) => y.year).sort((a, b) => b - a);
  const yearInfo = (y) => MANIFEST.years.find((m) => m.year === y) || {};

  function teams(year) {
    const out = {};
    (DATA.seasons[String(year)] || { teams: [] }).teams.forEach((t) => { out[t.id] = t; });
    return out;
  }
  const memberName = (id) => (DATA.members || {})[id] || '';

  const fmt = (n, d = 0) => (n == null || n === '' || Number.isNaN(Number(n)))
    ? '—'
    : Number(n).toLocaleString('en-US', { maximumFractionDigits: d, minimumFractionDigits: d });

  function initials(name) {
    return (name || '?').split(' ').filter(Boolean).map((x) => x[0]).join('').slice(0, 2).toUpperCase();
  }

  function logoHTML(t, cls) {
    cls = cls || 'sb-logo';
    const ini = initials((t && t.name) || '?');
    if (t && t.logo && /^(https?:|logos\/)/.test(t.logo)) {
      return `<img class="${cls}" src="${t.logo}" alt="" loading="lazy"
        onerror="if(this.parentNode)this.outerHTML='<div class=&quot;${cls} fb&quot;>${ini}</div>'">`;
    }
    return `<div class="${cls} fb">${ini}</div>`;
  }

  function headshotHTML(p, cls) {
    const ini = initials(p.name);
    if (p.hs) {
      return `<img class="${cls}" src="${p.hs}" alt="" loading="lazy"
        onerror="if(this.parentNode)this.outerHTML='<div class=&quot;${cls} fb&quot;>${ini}</div>'">`;
    }
    return `<div class="${cls} fb">${ini}</div>`;
  }

  /** Year chips. onPick(year) is called on click. */
  function yearPicker(el, cur, onPick, decorate) {
    el.innerHTML = years().map((y) => {
      const info = yearInfo(y);
      const extra = decorate ? decorate(info) : '';
      return `<button class="season-chip${y === cur ? ' on' : ''}" data-y="${y}">${y}${extra}</button>`;
    }).join('');
    el.querySelectorAll('.season-chip').forEach((b) =>
      b.addEventListener('click', () => onPick(+b.dataset.y)));
  }

  function chartDefaults(Chart) {
    Chart.defaults.color = C.mut;
    Chart.defaults.font.family = '"Avenir Next","Segoe UI",-apple-system,sans-serif';
    Chart.defaults.font.size = 11;
    Chart.defaults.borderColor = C.grid;
    Chart.defaults.plugins.tooltip.backgroundColor = '#05060bf2';
    Chart.defaults.plugins.tooltip.borderColor = '#1c2536';
    Chart.defaults.plugins.tooltip.borderWidth = 1;
    Chart.defaults.plugins.tooltip.padding = 10;
    Chart.defaults.plugins.tooltip.titleColor = C.ink;
  }

  const dateStr = (ms) => {
    if (!ms) return '';
    const d = new Date(ms);
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  };

  function notice(msg) {
    return `<div class="notice">${msg}</div>`;
  }

  return { C, boot, loadYear, years, yearInfo, teams, memberName, fmt,
           initials, logoHTML, headshotHTML, yearPicker, chartDefaults, dateStr, notice,
           get data() { return DATA; } };
})();
