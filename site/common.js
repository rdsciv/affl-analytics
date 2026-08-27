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

  /* CHI-121 — ESPN athlete ids that resolved. Never invent more. */
  const HYDRATE_PLAYERS = {
    11289: { name: "Ray Rice", pos: "RB", nfl: "BAL" },
    15358: { name: "Jarrett Boykin", pos: "WR", nfl: "BUF" },
    4685720: { name: "Bryce Young", pos: "QB", nfl: "CAR" },
    14885: { name: "Doug Martin", pos: "RB" },
    11307: { name: "Jamaal Charles", pos: "RB" },
    16040: { name: "C.J. Anderson", pos: "RB" },
    14221: { name: "Doug Baldwin", pos: "WR" },
    9705: { name: "Brandon Marshall", pos: "WR" },
    11270: { name: "Jordy Nelson", pos: "WR" },
    4259308: { name: "Raheem Blackshear", pos: "RB" },
    4430871: { name: "Sean Tucker", pos: "RB" },
    3149687: { name: "Chris Brooks", pos: "RB" },
    4361417: { name: "Zack Kuntz", pos: "TE" },
    4362619: { name: "Chris Rodriguez Jr.", pos: "RB" },
    4373632: { name: "Jaren Hall", pos: "QB" },
    10452: { name: "Adrian Peterson", pos: "RB" },
    13229: { name: "Rob Gronkowski", pos: "TE" },
    14876: { name: "Ryan Tannehill", pos: "QB" },
    4571557: { name: "Spencer Shrader", pos: "K" },
  };
  function hydratePlayer(p) {
    if (!p) return p;
    const rec = HYDRATE_PLAYERS[p.pid] || HYDRATE_PLAYERS[String(p.pid)];
    if (rec && unresolvedPlayerName(p.name)) {
      p.name = rec.name;
      if (!p.pos || p.pos === "?") p.pos = rec.pos;
      if (!p.nfl) p.nfl = rec.nfl;
    } else if (unresolvedPlayerName(p.name)) {
      p.name = "";
    }
    return p;
  }
  function hydrateTree(o) {
    if (!o || typeof o !== "object") return;
    if (o.pid != null && "name" in o) hydratePlayer(o);
    if (Array.isArray(o)) { o.forEach(hydrateTree); return; }
    Object.keys(o).forEach((k) => hydrateTree(o[k]));
  }
  async function loadYear(year) {
    if (yearCache.has(year)) return yearCache.get(year);
    const d = await fetch(`years/${year}.json` + bust(), { cache: 'no-store' }).then((r) => r.json());
    const board = d && d.draft && d.draft.board;
    if (Array.isArray(board)) board.forEach(hydratePlayer);
    hydrateTree(d);
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

  /* Identity: franchise = owner. Display current team name only. */
  const MERGE = { m01: "m07", m03: "m08", m20: "m10" };
  function canon(id) {
    if (id == null || id === "") return id;
    return MERGE[String(id)] || String(id);
  }
  function franchiseRecord(id) {
    const c = canon(id);
    return ((DATA && DATA.franchises) || []).find((f) => canon(f.owner) === c) || null;
  }
  function franchiseName(id) {
    const f = franchiseRecord(id);
    return (f && f.currentName) || "";
  }
  /* Current / replacement marks. Feelers (m18) keep d9388077ba8f.jpg —
     do not point that path at Gabagooners. */
  const FRANCHISE_MARKS = {
    m19: "logos/pounders.png",
    m17: "logos/sanchitos.png",
    m02: "logos/cucks.png",
    m14: "logos/pollywogs.png",
    m22: "logos/gabagooners.png",
    m10: "logos/wake-snakes.png",
  };

  function franchiseLogo(id) {
    const c = canon(id);
    if (FRANCHISE_MARKS[c]) return FRANCHISE_MARKS[c];
    if (FRANCHISE_MARKS[String(id)]) return FRANCHISE_MARKS[String(id)];
    const ys = years();
    for (let i = 0; i < ys.length; i++) {
      const ts = ((DATA.seasons[String(ys[i])] || {}).teams) || [];
      for (let j = 0; j < ts.length; j++) {
        if (canon(ts[j].owner) === c && ts[j].logo) return ts[j].logo;
      }
    }
    return "";
  }
  function franchiseTeam(id) {
    return { owner: canon(id), name: franchiseName(id) || "—", logo: franchiseLogo(id) };
  }
  function shortTeam(id) {
    const n = franchiseName(id);
    const parts = String(n || "").split(/\s+/).filter(Boolean);
    return parts.length ? parts[parts.length - 1] : (n || "?");
  }

  const fmt = (n, d = 0) => (n == null || n === '' || Number.isNaN(Number(n)))
    ? '—'
    : Number(n).toLocaleString('en-US', { maximumFractionDigits: d, minimumFractionDigits: d });

  function initials(name) {
    return (name || '?').split(' ').filter(Boolean).map((x) => x[0]).join('').slice(0, 2).toUpperCase();
  }

  function logoHTML(t, cls) {
    cls = cls || 'sb-logo';
    const ini = initials((t && t.name) || '?');
    const oid = t && (t.owner != null && t.owner !== "" ? t.owner : t.oid);
    const src = (oid ? franchiseLogo(oid) : "") || (t && t.logo) || "";
    if (src && /^(https?:|logos\/)/.test(src)) {
      return `<img class="${cls}" src="${src}" alt="" loading="lazy"
        onerror="if(this.parentNode)this.outerHTML='<div class=&quot;${cls} fb&quot;>${ini}</div>'">`;
    }
    return `<div class="${cls} fb">${ini}</div>`;
  }

  function espnHeadshot(pid) {
    const id = Number(pid);
    if (!id || id <= 0) return "";
    return "https://a.espncdn.com/i/headshots/nfl/players/full/" + id + ".png";
  }

  function isDst(p) {
    const pos = String((p && p.pos) || "").toUpperCase();
    return pos === "DST" || pos === "D/ST" || pos === "DEF";
  }

  function headshotHTML(p, cls) {
    const ini = initials((p && p.name) || "?");
    if (isDst(p) && p.nfl) return nflLogoHTML(p.nfl, cls);
    // ESPN CDN first — nflverse/other hs URLs often 404 and left blank faces.
    const espn = espnHeadshot(p && (p.pid != null ? p.pid : p.id));
    const alt = p && p.hs && p.hs !== espn ? p.hs : "";
    const src = espn || alt;
    if (!src) return `<div class="${cls} fb">${ini}</div>`;
    const next = (espn && alt) ? alt : "";
    return `<img class="${cls}" src="${src}" alt="" loading="lazy" data-fb="${next}"
      onerror="if(this.dataset.fb){this.src=this.dataset.fb;this.dataset.fb='';}else if(this.parentNode)this.outerHTML='<div class=&quot;${cls} fb&quot;>${ini}</div>'">`;
  }

  /** Year chips. onPick(year) is called on click. */
  function yearPicker(el, cur, onPick, decorate, list) {
    el.innerHTML = (list || years()).map((y) => {
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

  function scopeFromURL() {
    return new URLSearchParams(location.search).get("scope") === "cum" ? "cum" : "season";
  }

  function scopePicker(el, scope, onPick) {
    if (!el) return;
    el.innerHTML = [["season", "Season"], ["cum", "Cumulative"]].map(([v, l]) =>
      `<button class="season-chip${v === scope ? " on" : ""}" data-s="${v}">${l}</button>`
    ).join("");
    el.querySelectorAll("button").forEach((b) =>
      b.addEventListener("click", () => onPick(b.dataset.s)));
  }

  function showYearRow(visible) {
    const row = document.getElementById("year-row");
    if (row) row.hidden = !visible;
  }

  async function loadAllYears() {
    const ys = years();
    const bundles = await Promise.all(ys.map((y) => loadYear(y)));
    return ys.map((y, i) => ({ year: y, data: bundles[i] }));
  }

  function ownerId(year, tid) {
    const t = teams(year)[tid];
    return (t && t.owner) || null;
  }

  function ownerTeams() {
    const out = {};
    years().slice().reverse().forEach((y) => {
      Object.values(teams(y)).forEach((t) => {
        if (!t.owner) return;
        const id = canon(t.owner);
        if (!out[id]) out[id] = franchiseTeam(id);
      });
    });
    Object.keys(MERGE).forEach((oldId) => {
      if (out[MERGE[oldId]]) out[oldId] = out[MERGE[oldId]];
    });
    return out;
  }

  function squads() {
    return ((DATA && DATA.franchises) || []).slice().sort((a, b) => {
      if (!!a.active !== !!b.active) return a.active ? -1 : 1;
      return (a.currentName || "").localeCompare(b.currentName || "");
    });
  }

  function squadFromURL() {
    const q = new URLSearchParams(location.search).get("squad");
    if (q) {
      try { localStorage.setItem("affl-squad", q); } catch (e) {}
      return q;
    }
    try { return localStorage.getItem("affl-squad") || ""; } catch (e) { return ""; }
  }

  function rememberSquad(id) {
    try {
      if (id) localStorage.setItem("affl-squad", id);
      else localStorage.removeItem("affl-squad");
    } catch (e) {}
  }

  function squadInfo(id) {
    return squads().find((f) => f.owner === id) || null;
  }

  function squadYears(id) {
    const f = squadInfo(id);
    if (!f || !f.years || !f.years.length) return [];
    return f.years.slice().sort((a, b) => b - a);
  }

  function sameId(a, b) {
    if (a == null || b == null || a === "" || b === "") return false;
    if (a === b) return true;
    const na = Number(a), nb = Number(b);
    return !Number.isNaN(na) && !Number.isNaN(nb) && na === nb;
  }

  function teamIdFor(year, owner) {
    if (!owner) return null;
    const t = ((DATA.seasons[String(year)] || {}).teams || []).find((x) => x.owner === owner);
    return t ? t.id : null;
  }

  function squadPicker(el, squad, onPick) {
    if (!el) return;
    const list = squads();
    el.innerHTML = `<select class="team-select squad-select" aria-label="Squad">
      <option value="">All squads</option>
      ${list.map((f) => `<option value="${f.owner}"${f.owner === squad ? " selected" : ""}>${f.currentName} · ${f.ownerName}${f.active ? "" : " (former)"}</option>`).join("")}
    </select>`;
    el.querySelector("select").addEventListener("change", (e) => {
      rememberSquad(e.target.value);
      const u = new URL(location.href);
      if (e.target.value) u.searchParams.set("squad", e.target.value);
      else u.searchParams.delete("squad");
      history.replaceState(null, "", u.pathname.split("/").pop() + u.search + u.hash);
      onPick(e.target.value);
    });
  }

  function stampNav(squad) {
    document.querySelectorAll(".site-nav a").forEach((a) => {
      const href = a.getAttribute("href") || "";
      if (!href || href.startsWith("http")) return;
      const u = new URL(href, location.href);
      if (squad) u.searchParams.set("squad", squad);
      else u.searchParams.delete("squad");
      a.setAttribute("href", u.pathname.split("/").pop() + u.search + u.hash);
    });
  }

  function franchiseYears(id) {
    const f = franchiseRecord(id);
    if (!f || !f.years || !f.years.length) return [];
    return f.years.slice();
  }

  function franchisePlayedSeason(oid, year) {
    const id = canon(oid);
    if (!id) return false;
    const years = franchiseYears(id);
    if (!years.length) return false;
    const y = +year;
    return years.indexOf(y) >= 0 || years.indexOf(String(y)) >= 0;
  }

  function ownersForSeason(year) {
    const y = +year;
    if (!y) return [];
    return ((DATA && DATA.franchises) || [])
      .filter((f) => franchisePlayedSeason(f.owner, y))
      .map((f) => canon(f.owner));
  }

  function seasonScope(y) {
    if (y == null || y === "" || String(y).toLowerCase() === "all") {
      return { year: null, all: true };
    }
    const n = Number(y);
    if (!Number.isFinite(n) || n < 2014 || n > 2025) return { year: null, all: true };
    return { year: n, all: false };
  }

  function clampYear(year, squad) {
    if (!squad) return year;
    const ys = squadYears(squad);
    if (!ys.length) return null;
    return ys.indexOf(year) >= 0 ? year : null;
  }

  /* Historic teams — Pillars former-teams toggle.
     localStorage affl:show-former, '1' = show. Default hide.
     Chupacabras (m07 / Jason Kafka, merge m01→m07) are current for 2026.
     Gabagooners (m22 / Andy Pietromonaco) are current, empty history.
     2026 departed: Pasco Pounders (m19), Poulsbo Pollywogs (m14). */
  const SHOW_FORMER_KEY = "affl:show-former";
  const HISTORIC_OWNERS = {
    m12: true, // Muck City Mad Dawgs — Garrett Jones — 2014–2020
    m10: true, // Winston-Salem Wake Snakes — Tanner Dunn — 2017–2020
    m04: true, // Charleston Chewbacca — Jake Hibbard — 2015–2018
    m09: true, // Pawtucket Patriots — Scott Ace — 2014
    m16: true, // L.O.B. Thunder — david allardyce — 2014
    m19: true, // Pasco Pounders — Tyler Sanchez — 2021–2025
    m14: true, // Poulsbo Pollywogs — Steven Breitmayer — 2021–2025
  };

  function isHistoric(id) {
    if (id == null || id === "") return false;
    const raw = String(id);
    const c = canon(raw);
    if (c === "m07" || raw === "m07" || raw === "m01") return false;
    if (c === "m22" || raw === "m22") return false;
    return !!(HISTORIC_OWNERS[raw] || HISTORIC_OWNERS[c]);
  }

  function showFormer() {
    try { return localStorage.getItem(SHOW_FORMER_KEY) === "1"; }
    catch (e) { return false; }
  }

  function setShowFormer(on) {
    try { localStorage.setItem(SHOW_FORMER_KEY, on ? "1" : "0"); }
    catch (e) {}
    document.documentElement.classList.toggle("show-former", !!on);
    const input = document.querySelector("#historic-toggle input");
    if (input) input.checked = !!on;
    document.dispatchEvent(new CustomEvent("affl:show-former", { detail: { show: !!on } }));
  }

  function visibleFranchises(list) {
    const rows = list || [];
    if (showFormer()) return rows.slice();
    return rows.filter((x) => !isHistoric(x && (x.owner != null ? x.owner : x.id)));
  }

  function historicCount() {
    return Object.keys(HISTORIC_OWNERS).length;
  }

  function ensureHeaderRail() {
    const header = document.querySelector(".topbar") || document.querySelector("header");
    if (!header) return null;
    let rail = document.getElementById("header-rail");
    if (rail) return rail;
    rail = document.createElement("div");
    rail.id = "header-rail";
    rail.className = "topbar-row header-rail";
    /* Insert after first brand row, before nav / meta */
    const brandRow = header.querySelector(".topbar-row");
    const nav = header.querySelector(".site-nav");
    if (brandRow && brandRow.parentNode === header) {
      brandRow.insertAdjacentElement("afterend", rail);
    } else if (nav && nav.parentNode) {
      nav.parentNode.insertBefore(rail, nav);
    } else {
      header.appendChild(rail);
    }
    /* Force nav onto its own full-width row under the rail */
    if (nav) {
      let navRow = nav.closest(".topbar-nav-row");
      if (!navRow) {
        if (nav.parentElement && nav.parentElement.classList.contains("topbar-row")
            && nav.parentElement.querySelector(".brand")) {
          /* nav shares brand row — pull it out */
          navRow = document.createElement("div");
          navRow.className = "topbar-row topbar-nav-row";
          rail.insertAdjacentElement("afterend", navRow);
          navRow.appendChild(nav);
        } else {
          nav.classList.add("site-nav-bar");
          if (!nav.parentElement.classList.contains("topbar-nav-row")) {
            navRow = document.createElement("div");
            navRow.className = "topbar-row topbar-nav-row";
            if (nav.parentNode === header) {
              rail.insertAdjacentElement("afterend", navRow);
              navRow.appendChild(nav);
            } else {
              nav.parentNode.insertBefore(navRow, nav);
              navRow.appendChild(nav);
            }
          }
        }
      }
    }
    return rail;
  }

  function mountHistoricToggle() {
    if (document.getElementById("historic-toggle")) return;
    const rail = ensureHeaderRail();
    if (!rail) return;
    const on = showFormer();
    const n = historicCount();
    const label = document.createElement("label");
    label.className = "former-toggle";
    label.id = "historic-toggle";
    label.title = n + " franchises no longer in the league";
    label.innerHTML = "<input type=\"checkbox\"" + (on ? " checked" : "") + ">"
      + "<span>Historic teams</span>"
      + "<span class=\"former-toggle-count\">" + n + "</span>";
    rail.appendChild(label);
    label.querySelector("input").addEventListener("change", function (e) {
      setShowFormer(e.target.checked);
    });
    document.documentElement.classList.toggle("show-former", on);
  }

  /* 2026 current 12 — ESPN league 51418.
     2025 twelve minus Pounders (m19) minus Pollywogs (m14),
     plus Chupacabras (m07) plus Gabagooners (m22).
     Historic 7 stay behind the Historic teams toggle — not in this rail. */
  const CURRENT_2026 = [
    { owner: "m11", name: "Squaw Valley Skinners", logo: "logos/f646d3458763.jpg" },
    { owner: "m06", name: "Fairview Fat Cats", logo: "logos/06042c09ba0f.png" },
    { owner: "m08", name: "Goleta Gringos", logo: "logos/bca2e02e50d7.png" },
    { owner: "m05", name: "San Diego Shadowcöcks", logo: "logos/4fd947dd128a.jpg" },
    { owner: "m02", name: "DC Mighty Cucks", logo: "logos/cucks.png" },
    { owner: "m18", name: "Grand Teeton Feelers", logo: "logos/d9388077ba8f.jpg" },
    { owner: "m15", name: "Westeros Warlords", logo: "logos/5ed986bfece0.png" },
    { owner: "m17", name: "Tijuana Sanchitos", logo: "logos/sanchitos.png" },
    { owner: "m21", name: "Patagonia Pipers", logo: "logos/2e427c7e3ab0.png" },
    { owner: "m13", name: "Honolulu Horndogs", logo: "logos/3f384b75a09a.png" },
    { owner: "m22", name: "Central Oregon Gabagooners", logo: "logos/gabagooners.png" },
    { owner: "m07", name: "Chula Vista Chupacabras", logo: "logos/1f345cc38124.jpg" },
  ];

  function mountBrandStrip() {
    if (document.getElementById("brand-strip")) return;
    const rail = ensureHeaderRail();
    if (!rail) return;
    const active = new URLSearchParams(location.search).get("squad") || "";
    const strip = document.createElement("nav");
    strip.id = "brand-strip";
    strip.className = "brand-strip";
    strip.setAttribute("aria-label", "2026 teams");
    strip.innerHTML = CURRENT_2026.map((t) => {
      const href = "teams.html?squad=" + encodeURIComponent(t.owner);
      const alt = esc(t.name);
      const on = active && active === t.owner;
      const inner = t.logo
        ? `<img src="${t.logo}" alt="${alt}" loading="lazy">`
        : `<span class="brand-team-fb">${initials(t.name)}</span>`;
      return `<a class="brand-team${on ? " is-active" : ""}" href="${href}" title="${alt}" data-name="${alt}" data-owner="${t.owner}">${inner}</a>`;
    }).join("");
    rail.appendChild(strip);
  }

  /* Excel-style sheet menu: left rail, rounded items, hyperlinks between pages.
     Colors stay AFFL tokens. Header rail (48px logos) stays above. */
  function ensureSideMenu() {
  if (document.getElementById("side-menu")) return;
  const frame = document.querySelector(".frame");
  const nav = document.querySelector(".site-nav");
  if (!frame || !nav) return;
  const header = frame.querySelector(".topbar") || frame.querySelector("header");
  const aside = document.createElement("aside");
  aside.id = "side-menu";
  aside.className = "side-menu";
  aside.setAttribute("aria-label", "Sheets");
  const navRow = nav.closest(".topbar-nav-row");
  aside.appendChild(nav);
  if (navRow && !navRow.children.length) navRow.remove();
  nav.querySelectorAll("a").forEach((a) => {
    const label = (a.textContent || "").trim();
    a.setAttribute("data-sheet", label.toLowerCase());
    if (!a.getAttribute("data-ico")) a.setAttribute("data-ico", (label[0] || "").toUpperCase());
  });
  const main = document.createElement("div");
  main.className = "sheet-main";
  const sheet = document.createElement("div");
  sheet.className = "sheet";
  Array.from(frame.children).forEach((el) => {
    if (el === header) return;
    main.appendChild(el);
  });
  sheet.appendChild(aside);
  sheet.appendChild(main);
  frame.appendChild(sheet);
  }

  if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", function () {
    mountHistoricToggle();
    mountBrandStrip();
    ensureSideMenu();
  });
  } else {
  mountHistoricToggle();
  mountBrandStrip();
  ensureSideMenu();
  }


  const NFL_SLUG = { LA: "lar", LAR: "lar", WAS: "wsh", WSH: "wsh", JAC: "jax", JAX: "jax" };
  function nflSlug(abbr) {
    if (!abbr) return "";
    return (NFL_SLUG[abbr] || String(abbr)).toLowerCase();
  }
  function nflLogoHTML(abbr, cls) {
    cls = cls || "nfl-logo";
    const slug = nflSlug(abbr);
    if (!slug) return "";
    const label = String(abbr || "").toUpperCase();
    return `<img class="${cls}" src="logos/nfl/${slug}.png" alt="${label}" title="${label}" loading="lazy"
      onerror="this.outerHTML='<span class=&quot;${cls} fb&quot;>${label}</span>'">`;
  }

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"]/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;",
    }[c]));
  }

  function collegeSlug(name) {
    return String(name || "").toLowerCase()
      .replace(/&/g, "and")
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "");
  }

  function collegeLogoHTML(bio, cls) {
    cls = cls || "ncaa-logo";
    const rec = bio || {};
    const college = rec.college || "";
    let src = rec.collegeLogo || "";
    if (!src && college) src = "logos/ncaa/" + collegeSlug(college) + ".png";
    if (!src) return "";
    const alt = esc(college);
    return `<img class="${cls}" src="${esc(src)}" alt="${alt}" title="${alt}" loading="lazy"
      onerror="this.remove()">`;
  }

  function playerHref(pid, extra) {
    extra = extra || {};
    if (pid == null || pid === "") return "";
    const u = new URL("players.html", "https://affl.local/");
    u.searchParams.set("pid", String(pid));
    if (extra.year) u.searchParams.set("year", String(extra.year));
    if (extra.log != null && extra.log !== "") u.searchParams.set("log", String(extra.log));
    if (extra.squad) u.searchParams.set("squad", extra.squad);
    return "players.html" + u.search;
  }

  /** CHI-121 — never paint `Player {espnId}`. Missing hydrate is unavailable. */
  function unresolvedPlayerName(name) {
    return name == null || name === "" || /^Player \d+$/.test(String(name).trim());
  }
  function displayPlayerName(name) {
    return unresolvedPlayerName(name) ? "unavailable" : name;
  }
  function playerLink(pid, name, extra) {
    extra = extra || {};
    const cls = extra.cls || "pl-link";
    if (unresolvedPlayerName(name)) {
      return `<span class="${cls} is-unavailable">unavailable</span>`;
    }
    const label = esc(name || "—");
    const href = playerHref(pid, extra);
    if (!href) return `<span class="${cls}">${label}</span>`;
    return `<a class="${cls}" href="${href}" data-pid="${esc(pid)}">${label}</a>`;
  }

  let BIOS = null;
  async function loadBios() {
    if (BIOS) return BIOS;
    BIOS = await fetch("player_bio.json" + bust(), { cache: "no-store" }).then((r) => r.json());
    return BIOS;
  }
  function parseDay(value) {
    if (!value) return null;
    if (value instanceof Date && !Number.isNaN(value.getTime())) {
      return new Date(value.getFullYear(), value.getMonth(), value.getDate());
    }
    const s = String(value).slice(0, 10);
    const p = s.split("-");
    if (p.length < 3) return null;
    const d = new Date(+p[0], +p[1] - 1, +p[2]);
    return Number.isNaN(d.getTime()) ? null : d;
  }
  function today() {
    const n = new Date();
    return new Date(n.getFullYear(), n.getMonth(), n.getDate());
  }
  /** Live age from a birth date. asOf defaults to today. Recalculates every call. */
  function ageOn(birth, asOf) {
    const b = parseDay(birth);
    const a = parseDay(asOf) || today();
    if (!b || a < b) return null;
    let years = a.getFullYear() - b.getFullYear();
    let months = a.getMonth() - b.getMonth();
    let days = a.getDate() - b.getDate();
    if (days < 0) {
      const prev = new Date(a.getFullYear(), a.getMonth(), 0).getDate();
      days += prev;
      months -= 1;
    }
    if (months < 0) { years -= 1; months += 12; }
    const decimal = Math.round(((a - b) / (365.2425 * 24 * 3600 * 1000)) * 10) / 10;
    return {
      years: years,
      months: months,
      days: days,
      decimal: decimal,
      text: years + "y " + months + "m",
    };
  }
  function playerBio(pid, year, asOf) {
    const rec = (BIOS || {})[String(pid)];
    if (!rec) return null;
    const y = year != null ? String(year) : "";
    const age = ageOn(rec.birth, asOf);
    return {
      birth: rec.birth || "",
      college: rec.college || "",
      collegeLogo: rec.collegeLogo || "",
      draftYear: rec.draftYear != null ? rec.draftYear : null,
      draftRound: rec.draftRound != null ? rec.draftRound : null,
      draftPick: rec.draftPick != null ? rec.draftPick : null,
      draftTeam: rec.draftTeam || "",
      breakoutAge: rec.breakoutAge != null ? rec.breakoutAge : null,
      dominator: rec.dominator != null ? rec.dominator : null,
      earlyDeclare: rec.earlyDeclare != null ? rec.earlyDeclare : null,
      combine: rec.combine != null ? rec.combine : null,
      nflDraft: rec.nflDraft != null ? rec.nflDraft : null,
      nfl: (y && rec.nflByYear && rec.nflByYear[y]) || "",
      age: age ? age.decimal : null,
      ageText: age ? age.text : "",
      ageParts: age,
    };
  }
  function onNextMidnight(fn) {
    const n = new Date();
    const next = new Date(n.getFullYear(), n.getMonth(), n.getDate() + 1, 0, 0, 5);
    setTimeout(function tick() {
      fn();
      setTimeout(tick, 86400000);
    }, Math.max(1000, next - n));
  }

  /* CHI-66 — week walk + published PAR baseline (same scale as draft). */
  function weekLog(player) {
    return ((player && player.wk) || []).map((row) => ({
      week: row[0],
      pts: +(row[1] || 0),
      started: +row[2] || 0,
      tid: row[3],
      slot: row[4] || "",
    }));
  }

  function posBaseline(yd, pos) {
    const rows = (yd && yd.draftValue && yd.draftValue.baselines) || [];
    for (let i = 0; i < rows.length; i++) {
      if (rows[i] && rows[i].position === pos && rows[i].baseline != null) return rows[i].baseline;
    }
    return null;
  }

  function afterStart(player, tid, afterWk) {
    let pts = 0, starts = 0;
    weekLog(player).forEach((w) => {
      if (w.week > afterWk && sameId(w.tid, tid) && w.started) {
        pts += w.pts;
        starts += 1;
      }
    });
    return { pts: pts, starts: starts };
  }

  function goTeam(owner, year, extra) {
    const u = new URL("teams.html", location.href);
    if (owner) u.searchParams.set("squad", owner);
    if (year) u.searchParams.set("year", String(year));
    if (extra && extra.scope) u.searchParams.set("scope", extra.scope);
    location.href = u.pathname.split("/").pop() + u.search + u.hash;
  }

  return { C, boot, loadYear, loadAllYears, years, yearInfo, teams, memberName, ownerId, ownerTeams,
           MERGE, canon, franchiseName, franchiseTeam, shortTeam, franchiseLogo,
           squads, squadFromURL, squadInfo, squadYears, franchiseYears, franchisePlayedSeason, ownersForSeason, seasonScope, teamIdFor, sameId, squadPicker, stampNav, clampYear, rememberSquad,
           isHistoric, showFormer, setShowFormer, visibleFranchises, mountHistoricToggle, SHOW_FORMER_KEY,
           CURRENT_2026, mountBrandStrip, FRANCHISE_MARKS,
           goTeam, weekLog, posBaseline, afterStart,
           fmt, initials, logoHTML, headshotHTML, nflLogoHTML, nflSlug, esc, collegeSlug, collegeLogoHTML,
           playerHref, playerLink, unresolvedPlayerName, displayPlayerName, HYDRATE_PLAYERS,
           loadBios, playerBio, ageOn, today, onNextMidnight, yearPicker, scopePicker, scopeFromURL, showYearRow,
           chartDefaults, dateStr, notice,
           get data() { return DATA; } };
})();
