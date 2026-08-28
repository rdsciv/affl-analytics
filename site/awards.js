/* AFFL Awards — All-League + Bush League. Current franchise names only. */
(async function () {
  const A = window.AFFL;
  await A.boot();
  const $ = (id) => document.getElementById(id);

  const POS_ORDER = ["QB", "RB", "WR", "TE", "K", "DST"];
  const POS_FILL = {
    QB: "var(--blue)", RB: "var(--green)", WR: "var(--orange)",
    TE: "var(--yellow)", K: "var(--ice)", DST: "var(--steel)",
  };

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"]/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;",
    }[c]));
  }

  function normPos(p) {
    const u = String(p == null ? "" : p).toUpperCase().replace(/\s+/g, "");
    if (u === "DST" || u === "D/ST" || u === "DEF") return "DST";
    return u;
  }

  function filterStarts(starts, want) {
    const list = starts || [];
    if (!want || want === "ALL") return list.slice();
    return list.filter((s) => normPos(s.pos) === want);
  }

  function applyPos(rows, want) {
    return rows.map((r) => {
      const starts = filterStarts(r.starts, want);
      let topPlayer = "—", topPlayerPid = null, topPlayerPts = null;
      starts.forEach((s) => {
        const pts = s.pts == null ? null : Number(s.pts);
        if (pts != null && (topPlayerPts == null || pts > topPlayerPts)) {
          topPlayer = s.name || "—";
          topPlayerPid = s.pid;
          topPlayerPts = pts;
        }
      });
      return Object.assign({}, r, {
        starts: starts,
        count: starts.length,
        topPlayer: topPlayer,
        topPlayerPid: topPlayerPid,
        topPlayerPts: topPlayerPts,
      });
    }).filter((r) => want === "ALL" || r.count > 0);
  }

  function ownerByTid(year) {
    const out = {};
    Object.values(A.teams(year) || {}).forEach((t) => {
      if (t && t.owner != null) {
        out[t.id] = A.canon(t.owner);
        out[String(t.id)] = A.canon(t.owner);
      }
    });
    return out;
  }

  function awardList(bundle, kind) {
    const awards = bundle && bundle.awards;
    if (!awards || typeof awards !== "object") return [];
    const list = awards[kind];
    return Array.isArray(list) ? list : [];
  }

  function startsOf(r, year) {
    return (r.starts || []).map((s) => Object.assign({}, s, { year: s.year || year }));
  }

  function rowsFor(kind, bundle, year) {
    const owners = ownerByTid(year);
    return awardList(bundle, kind).map((r) => {
      const oid = owners[r.tid] || owners[Number(r.tid)] || owners[String(r.tid)] || null;
      const name = oid ? (A.franchiseName(oid) || "—") : "—";
      const logo = oid ? (A.franchiseLogo(oid) || "") : "";
      return {
        tid: r.tid,
        owner: oid,
        name: name,
        logo: logo,
        count: r.count == null ? 0 : Number(r.count),
        topPlayer: r.topPlayer || "—",
        topPlayerPid: r.topPlayerPid,
        topPlayerPts: r.topPlayerPts,
        starts: startsOf(r, year),
      };
    });
  }

  function seedFranchises() {
    const by = {};
    Object.keys(A.ownerTeams() || {}).forEach((id) => {
      const oid = A.canon(id);
      if (by[oid]) return;
      by[oid] = {
        owner: oid,
        name: A.franchiseName(oid) || "—",
        logo: A.franchiseLogo(oid) || "",
        count: 0,
        topPlayer: "—",
        topPlayerPid: null,
        topPlayerPts: null,
        starts: [],
      };
    });
    return by;
  }

  function cumRows(kind, all) {
    const by = seedFranchises();
    (all || []).forEach(({ year, data }) => {
      rowsFor(kind, data, year).forEach((r) => {
        if (!r.owner) return;
        if (!by[r.owner]) {
          by[r.owner] = {
            owner: r.owner, name: r.name, logo: r.logo,
            count: 0, topPlayer: "—", topPlayerPid: null, topPlayerPts: null, starts: [],
          };
        }
        const row = by[r.owner];
        row.count += r.count || 0;
        row.starts = row.starts.concat(r.starts || []);
        if (r.topPlayerPts != null && (row.topPlayerPts == null || r.topPlayerPts > row.topPlayerPts)) {
          row.topPlayer = r.topPlayer;
          row.topPlayerPid = r.topPlayerPid;
          row.topPlayerPts = r.topPlayerPts;
        }
      });
    });
    return Object.values(by);
  }

  function teamCell(r) {
    const href = r.owner ? ("teams.html?squad=" + encodeURIComponent(r.owner)) : "";
    const name = href
      ? `<a class="hist-name" href="${href}">${esc(r.name)}</a>`
      : esc(r.name);
    return `<div class="team-cell">${A.logoHTML({ name: r.name, logo: r.logo }, "mini")}<div>${name}</div></div>`;
  }

  function pill(i) {
    const rank = i + 1;
    const cls = rank === 1 ? "gold" : rank === 2 ? "slv" : rank === 3 ? "brz" : "";
    return `<span class="rank-pill ${cls}">${rank}</span>`;
  }

  function emptyNotice(msg) {
    return `<div class="notice">${esc(msg)}</div>`;
  }

  function playerCell(r) {
    const pts = r.topPlayerPts == null ? "" : `<div class="own">${A.fmt(r.topPlayerPts, 1)} pts</div>`;
    return `${A.playerLink(r.topPlayerPid, r.topPlayer, { year: scope === "cum" ? null : year, cls: "pl-link award-pl" })}${pts}`;
  }

  function startLine(s) {
    const y = s.year != null ? s.year + " " : "";
    return `<div class="award-hit">
      <span class="own">${y}W${s.wk} ${esc(s.pos || "")}</span>
      ${A.playerLink(s.pid, s.name, { year: s.year || year, cls: "pl-link award-pl" })}
      <span class="own">${A.fmt(s.pts, 1)}</span>
    </div>`;
  }

  function posMix(starts) {
    const list = starts || [];
    const n = list.length;
    const counts = {};
    list.forEach((s) => {
      const p = normPos(s.pos) || "?";
      counts[p] = (counts[p] || 0) + 1;
    });
    const keys = POS_ORDER.filter((p) => counts[p])
      .concat(Object.keys(counts).filter((p) => POS_ORDER.indexOf(p) < 0).sort());
    return keys.map((p) => ({
      pos: p,
      n: counts[p],
      pct: n ? Math.round((100 * counts[p]) / n) : 0,
    }));
  }

  function chipTint(kind) {
    return kind === "bushLeague" ? "bush" : "al";
  }

  function posChip(item, kind) {
    return `<span class="ngs-chip ${chipTint(kind)}" data-pos="${esc(item.pos)}" role="button" tabindex="0"><b>${esc(item.pos)}</b> ${item.n} · ${item.pct}%</span>`;
  }

  function chipsHTML(starts, kind) {
    const mix = posMix(starts);
    if (!mix.length) return "";
    return `<div class="ngs-chips">${mix.map((x) => posChip(x, kind)).join("")}</div>`;
  }

  function countOf(starts, pred) {
    return (starts || []).filter((s) => pred(normPos(s.pos))).length;
  }

  function pctOf(n, d) {
    return d ? Math.round((100 * n) / d) : 0;
  }

  function topMix(mix) {
    return mix.slice().sort((a, b) =>
      (b.n - a.n) || (POS_ORDER.indexOf(a.pos) - POS_ORDER.indexOf(b.pos)))[0] || null;
  }

  function shareBoxes(starts) {
    const list = starts || [];
    const n = list.length;
    if (!n) return "";
    const mix = posMix(list);
    const top = topMix(mix);
    const qb = countOf(list, (p) => p === "QB");
    const skill = countOf(list, (p) => p === "WR" || p === "TE" || p === "RB");
    const st = countOf(list, (p) => p === "DST" || p === "K");
    const tiles = [
      [top ? (top.pct + "%") : "—", top ? ("top " + top.pos) : "top pos"],
      [pctOf(qb, n) + "%", "QB share"],
      [pctOf(skill, n) + "%", "skill WR+TE+RB"],
      [pctOf(st, n) + "%", "DST+K"],
    ];
    return `<div class="ngs-mix">${tiles.map(([v, l]) =>
      `<div class="pp-stat"><b>${esc(v)}</b><span>${esc(l)}</span></div>`).join("")}</div>`;
  }

  function mixFan(starts) {
    const mix = posMix(starts);
    const total = mix.reduce((s, x) => s + x.n, 0);
    if (!total) return "";
    const cx = 36, cy = 36, r = 32;
    let a0 = -Math.PI / 2;
    const slices = mix.map((x) => {
      const sweep = (x.n / total) * Math.PI * 2;
      const a1 = a0 + sweep;
      const large = sweep > Math.PI ? 1 : 0;
      const x0 = cx + r * Math.cos(a0);
      const y0 = cy + r * Math.sin(a0);
      const x1 = cx + r * Math.cos(a1);
      const y1 = cy + r * Math.sin(a1);
      const d = sweep >= Math.PI * 2 - 1e-6
        ? `M ${cx} ${cy - r} A ${r} ${r} 0 1 1 ${cx - 0.01} ${cy - r} A ${r} ${r} 0 1 1 ${cx} ${cy - r} Z`
        : `M ${cx} ${cy} L ${x0.toFixed(2)} ${y0.toFixed(2)} A ${r} ${r} 0 ${large} 1 ${x1.toFixed(2)} ${y1.toFixed(2)} Z`;
      a0 = a1;
      return `<path d="${d}" fill="${POS_FILL[x.pos] || "var(--mut)"}"><title>${esc(x.pos)} ${x.n} · ${x.pct}%</title></path>`;
    }).join("");
    return `<svg width="72" height="72" viewBox="0 0 72 72" aria-hidden="true">${slices}</svg>`;
  }

  function mixBlock(starts, kind) {
    const chips = chipsHTML(starts, kind);
    if (!chips) return "";
    const mix = posMix(starts);
    const top = topMix(mix);
    const sub = top ? `Top ${esc(top.pos)} · ${top.pct}%` : "position mix";
    return `<div class="ngs-mix">
      <div>
        <div class="card-sub">${sub}</div>
        ${mixFan(starts)}
        ${chips}
      </div>
      <div>
        <div class="card-sub">start shares from the same starts</div>
        ${shareBoxes(starts)}
      </div>
    </div>`;
  }

  function countCell(kind, r) {
    const key = r.owner || String(r.tid);
    const open = expanded[kind] === key;
    const n = A.fmt(r.count);
    if (!r.starts || !r.starts.length) return `<strong>${n}</strong>`;
    return `<div>
      <button type="button" class="award-count${open ? " on" : ""}" data-kind="${kind}" data-key="${esc(key)}">${n}<span class="own"> starts</span></button>
      ${chipsHTML(r.starts, kind)}
    </div>`;
  }

  function startsRow(kind, r, colspan) {
    const key = r.owner || String(r.tid);
    if (expanded[kind] !== key || !r.starts || !r.starts.length) return "";
    const hits = r.starts.slice().sort((a, b) =>
      ((a.year || 0) - (b.year || 0)) || (a.wk - b.wk) || String(a.pos || "").localeCompare(String(b.pos || "")));
    const head = mixBlock(hits, kind);
    return `<tr class="award-starts-row"><td colspan="${colspan}"><div class="award-starts award-starts-grouped">${head}<div class="award-starts">${hits.map(startLine).join("")}</div></div></td></tr>`;
  }

  function scopeLabel() {
    return scope === "cum" ? "career" : String(year);
  }

  function leaderHTML(kind, rows, title, empty) {
    if (!rows.length) {
      return `<div class="card-head"><div><h2>${esc(title)}</h2><div class="card-sub">${esc(empty)}</div></div></div>`;
    }
    const top = rows[0];
    const pts = top.topPlayerPts == null ? "" : (" · " + A.fmt(top.topPlayerPts, 1) + " pts");
    return `<div class="card-head">
        <div>
          <h2>${esc(title)}</h2>
          <div class="card-sub">${esc(top.name)} · ${A.fmt(top.count)} starts · ${esc(scopeLabel())}</div>
        </div>
      </div>
      <div class="champ-spot">
        ${A.logoHTML({ name: top.name, logo: top.logo }, "avatar")}
        <div>
          <div class="tag">${esc(title)} leader</div>
          <div class="nm">${esc(top.name)}</div>
          <div class="rec">${A.fmt(top.count)} starts · ${A.playerLink(top.topPlayerPid, top.topPlayer, { year: scope === "cum" ? null : year, cls: "pl-link award-pl" })}${pts}</div>
        </div>
      </div>
      ${mixBlock(top.starts, kind)}`;
  }

  function tableHTML(kind, rows, empty) {
    if (!rows.length) return `<tr><td colspan="4">${emptyNotice(empty)}</td></tr>`;
    return rows.map((r, i) => {
      return `<tr>
        <td>${pill(i)}</td>
        <td>${teamCell(r)}</td>
        <td>${countCell(kind, r)}</td>
        <td>${playerCell(r)}</td>
      </tr>${startsRow(kind, r, 4)}`;
    }).join("");
  }

  let year = A.years()[0];
  let scope = "cum";
  let squad = A.squadFromURL();
  let pos = "ALL";
  let ALL = null;
  let YD = null;
  const sort = {
    allLeague: { k: "count", dir: -1 },
    bushLeague: { k: "count", dir: -1 },
  };
  const expanded = { allLeague: null, bushLeague: null };

  function sortRows(kind, rows) {
    const st = sort[kind];
    const k = st.k, dir = st.dir;
    return rows.slice().sort((a, b) => {
      const av = a[k], bv = b[k];
      if (k === "name" || k === "topPlayer") return String(av || "").localeCompare(String(bv || "")) * dir;
      const an = av == null ? -Infinity * dir : Number(av);
      const bn = bv == null ? -Infinity * dir : Number(bv);
      if (an !== bn) return (an - bn) * dir;
      return String(a.name || "").localeCompare(String(b.name || ""));
    });
  }

  function board(kind) {
    const raw = scope === "cum" ? cumRows(kind, ALL || []) : rowsFor(kind, YD, year);
    const rows = sortRows(kind, applyPos(raw, pos));
    if (!squad) return rows;
    return rows.filter((r) => r.owner && A.canon(r.owner) === A.canon(squad));
  }

  function render() {
    const all = board("allLeague");
    const bush = board("bushLeague");
    const emptyAll = scope === "cum"
      ? "All-League counts start in 2018."
      : "All-League is not in the " + year + " file yet.";
    const emptyBush = scope === "cum"
      ? "Bush League counts start in 2018."
      : "Bush League is not in the " + year + " file yet.";

    $("all-league-lead").innerHTML = leaderHTML("allLeague", all, "All-League", emptyAll);
    $("bush-league-lead").innerHTML = leaderHTML("bushLeague", bush, "Bush League", emptyBush);
    document.querySelector("#all-tbl tbody").innerHTML = tableHTML("allLeague", all, emptyAll);
    document.querySelector("#bush-tbl tbody").innerHTML = tableHTML("bushLeague", bush, emptyBush);

    $("all-sub").textContent = scope === "cum"
      ? "career weekly positional top starts · click a count · current names"
      : year + " · weekly positional top starts · click a count · current names";
    $("bush-sub").textContent = scope === "cum"
      ? "career weekly positional bottom starts · you do not want to lead this board"
      : year + " · weekly positional bottoms · click a count";
    $("page-sub").textContent = scope === "cum"
      ? "All-League · Bush League · career starts · current franchise names"
      : "All-League · Bush League · " + year + " · current franchise names";

    [["#all-tbl", "allLeague"], ["#bush-tbl", "bushLeague"]].forEach(([sel, kind]) => {
      const st = sort[kind];
      document.querySelectorAll(sel + " thead th.s").forEach((th) => {
        th.classList.toggle("on", th.dataset.k === st.k);
        th.classList.toggle("asc", th.dataset.k === st.k && st.dir > 0);
      });
    });
    const leads = $("award-leaders");
    if (leads) leads.hidden = false;
  }

  function bindSort(sel, kind) {
    document.querySelectorAll(sel + " thead th.s").forEach((th) => {
      th.addEventListener("click", () => {
        const st = sort[kind];
        if (st.k === th.dataset.k) st.dir *= -1;
        else {
          st.k = th.dataset.k;
          st.dir = (th.dataset.k === "name" || th.dataset.k === "topPlayer") ? 1 : -1;
        }
        render();
      });
    });
  }

  function bindExpand() {
    document.addEventListener("click", (e) => {
      const btn = e.target.closest("button.award-count");
      if (!btn) return;
      const kind = btn.dataset.kind;
      const key = btn.dataset.key;
      expanded[kind] = expanded[kind] === key ? null : key;
      render();
    });
  }

  function setScopeURL(nextScope, nextYear) {
    const u = new URL(location.href);
    u.searchParams.delete("scope");
    if (nextScope === "cum") {
      u.searchParams.delete("year");
    } else {
      if (nextYear) u.searchParams.set("year", String(nextYear));
    }
    history.replaceState(null, "", u.pathname.split("/").pop() + u.search + u.hash);
  }

  function renderYearChips() {
    const el = $("year-picker");
    if (!el) return;
    const ylist = squad ? A.squadYears(squad) : A.years();
    A.seasonPicker(el, scope === "cum" ? null : year, async (raw) => {
      if (raw == null) {
        scope = "cum";
        setScopeURL("cum");
      } else {
        scope = "season";
        year = +raw;
        setScopeURL("season", year);
      }
      await pick(year);
    }, ylist);
    A.squadPicker($("squad-picker"), squad, (s) => {
      squad = s || "";
      A.stampNav(squad);
      if (squad && scope === "season") {
        const next = A.clampYear(year, squad);
        if (next == null) { scope = "cum"; setScopeURL("cum"); }
        else { year = next; setScopeURL("season", year); }
      }
      pick(year);
    });
  }

  function setPos(next) {
    pos = next || "ALL";
    const el = $("pos-picker");
    if (el) {
      el.querySelectorAll(".season-chip").forEach((x) => x.classList.toggle("on", x.dataset.pos === pos));
    }
    render();
  }

  function bindPos() {
    const el = $("pos-picker");
    if (el) {
      el.querySelectorAll(".season-chip").forEach((b) => {
        b.addEventListener("click", () => setPos(b.dataset.pos || "ALL"));
      });
    }
    document.addEventListener("click", (e) => {
      const chip = e.target.closest(".ngs-chip[data-pos]");
      if (!chip) return;
      e.preventDefault();
      setPos(chip.dataset.pos || "ALL");
    });
  }

  async function pick(y) {
    year = y;
    if (scope === "cum") {
      ALL = ALL || await A.loadAllYears();
      YD = (ALL.find((x) => x.year === year) || ALL[0] || {}).data || {};
    } else {
      try { YD = await A.loadYear(y); }
      catch (e) { YD = {}; }
    }
    renderYearChips();
    render();
  }

  bindSort("#all-tbl", "allLeague");
  bindSort("#bush-tbl", "bushLeague");
  bindExpand();
  bindPos();
  const qs = new URLSearchParams(location.search);
  const yearQ = qs.get("year");
  if (yearQ) {
    scope = "season";
    await pick(+yearQ);
  } else {
    scope = "cum";
    await pick(year);
  }
})();
