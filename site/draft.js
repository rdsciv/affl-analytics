/* ============ AFFL Draft Room — all seasons ============ */
(async function () {
  const A = window.AFFL;
  const $ = (s) => document.querySelector(s);
  const CATES = [58, 40, 24, 13, 12, 9];
  const CATES_SUM = CATES.reduce((a, b) => a + b, 0);
  let MILES = {};

  function ingestMiles(obj) {
    if (!obj || typeof obj !== "object") return 0;
    let n = 0;
    const take = (pid, rec) => {
      if (!rec || typeof rec !== "object") return;
      const has = ("careerNflTouchesAsOf" in rec) || ("nflTouchesBySeason" in rec);
      if (!has) return;
      MILES[String(pid)] = Object.assign(MILES[String(pid)] || {}, rec);
      n += 1;
    };
    if (Array.isArray(obj)) {
      obj.forEach((rec) => take(rec.pid || rec.id, rec));
      return n;
    }
    Object.keys(obj).forEach((k) => {
      if (k === "careerNflTouchesAsOf" || k === "nflTouchesBySeason") return;
      take(k, obj[k]);
    });
    ["careerNflTouchesAsOf", "nflTouchesBySeason"].forEach((field) => {
      const block = obj[field];
      if (!block || typeof block !== "object" || Array.isArray(block)) return;
      Object.keys(block).forEach((pid) => {
        MILES[String(pid)] = MILES[String(pid)] || {};
        MILES[String(pid)][field] = block[pid];
        n += 1;
      });
    });
    return n;
  }
  async function loadMiles() {
    MILES = {};
    const pull = async (url) => {
      try {
        const r = await fetch(url, { cache: "no-store" });
        if (!r.ok) return null;
        return await r.json();
      } catch (e) { return null; }
    };
    const miles = await pull("miles.json?v=" + Date.now());
    if (miles && ingestMiles(miles) > 0) return;
    const bio = await pull("player_bio.json?v=" + Date.now());
    if (bio) ingestMiles(bio);
  }
  function touchesAsOf(pid, y) {
    if (pid == null || y == null) return null;
    const rec = MILES[String(pid)];
    if (!rec) return null;
    const asof = rec.careerNflTouchesAsOf;
    if (typeof asof === "number" && !Number.isNaN(asof)) return asof;
    if (asof && typeof asof === "object") {
      if (asof[y] != null) return Number(asof[y]);
      if (asof[String(y)] != null) return Number(asof[String(y)]);
    }
    const by = rec.nflTouchesBySeason;
    if (by && typeof by === "object") {
      let sum = 0, any = false;
      Object.keys(by).forEach((k) => {
        if (Number(k) < Number(y)) {
          const v = Number(by[k]);
          if (!Number.isNaN(v)) { sum += v; any = true; }
        }
      });
      if (any) return sum;
    }
    return null;
  }

  await A.boot();
  await A.loadBios();
  await loadMiles();
  A.chartDefaults(Chart);
  const C = A.C, fmt = A.fmt;

  let year = A.seasonFromURL();
  if (year == null) year = A.years()[0];
  let scope = A.seasonFromURL() == null ? "cum" : "season";
  let squad = A.squadFromURL();
  let YD = null, T = {}, chart = null, dnaChart = null, labChart = null, ALL = null;
  let scatterChart = null, contChart = null;
  let HOLDOUT = { pooled: {}, bySeason: {}, scoredAuctionSeasons: [], claim: "", subtitle: "", keepers: { note: "" }, histogramNote: "", grain: "" };
  try {
    HOLDOUT = await A.loadJSON("draft_holdout.json");
  } catch (e) { /* keep empty holdout */ }
  let ovYearChart = null, ovTeamPosChart = null, ovScatterChart = null, recapRoundChart = null, recapPosChart = null;
  const S = { q: '', limit: 60, view: 'table', pos: 'ALL', holdoutScope: 'pooled', mekkoStack: 'half' };
  let heatMode = 'picks';
  let homerMode = 'franchise';
  let boardKey = 'overall';
  let boardDir = 1;
  let fgAgeChart = null;

  function ownerKey(tid) {
    const t = T[tid] || T[String(tid)];
    if (t && t.owner) return A.canon(t.owner);
    return A.canon(tid);
  }
  const tName = (id) => A.franchiseName(ownerKey(id)) || "—";
  const short = (id) => A.shortTeam(ownerKey(id));

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

  function mergeDraft(all) {
    const board = [];
    const steals = [], busts = [];
    const par = {};
    let auction = false;
    for (const { year: y, data } of all) {
      if (data.draft && data.draft.auction) auction = true;
      for (const p of (data.draft && data.draft.board) || []) {
        const oid = A.canon(A.ownerId(y, p.tid) || ("t" + p.tid));
        board.push(Object.assign({}, p, { year: y, tid: oid, auction: !!(data.draft && data.draft.auction) }));
        const dv = data.draftValue && data.draftValue.parByOverall;
        if (dv && dv[String(p.overall)] != null) par[y + ":" + p.overall] = dv[String(p.overall)];
      }
      for (const s of (data.draftValue && data.draftValue.steals) || []) {
        steals.push(Object.assign({}, s, { year: y, tid: A.canon(A.ownerId(y, s.tid) || s.tid) }));
      }
      for (const b of (data.draftValue && data.draftValue.busts) || []) {
        busts.push(Object.assign({}, b, { year: y, tid: A.canon(A.ownerId(y, b.tid) || b.tid) }));
      }
    }
    steals.sort((a, b) => (b.par || 0) - (a.par || 0));
    busts.sort((a, b) => (a.par || 0) - (b.par || 0));
    const baseByYear = {};
    for (const { year: y, data } of all) {
      if (data.draftValue && data.draftValue.baselines) baseByYear[y] = data.draftValue.baselines;
    }
    return {
      draft: { auction, board },
      draftValue: { steals: steals.slice(0, 8), busts: busts.slice(0, 8), parByOverall: par, baselines: [], baseByYear },
      hasRosters: all.some((x) => x.data.hasRosters),
    };
  }



  function teamOf(tid) {
    return A.franchiseTeam(ownerKey(tid));
  }
  function teamHref(tid) {
    const oid = ownerKey(tid);
    return "teams.html?squad=" + encodeURIComponent(oid);
  }
  function teamLink(tid, label) {
    const name = label != null ? label : tName(tid);
    return `<a class="tm-link" href="${teamHref(tid)}">${name}</a>`;
  }
  function teamCell(tid) {
    const t = teamOf(tid);
    return `<div class="team-cell">${A.logoHTML(t, "mini")}<div><strong>${teamLink(tid, t.name)}</strong></div></div>`;
  }

  let ppdKey = "ppd";
  let ppdDir = -1;
  const PPD_KEYS = {
    name: (r) => (teamOf(r.tid).name || "").toLowerCase(),
    spend: (r) => r.spend || 0,
    pts: (r) => r.pts || 0,
    ppd: (r) => r.ppd || 0,
    parpd: (r) => r.parpd || 0,
    ppdQB: (r) => r.ppdQB || 0,
    ppdRB: (r) => r.ppdRB || 0,
    ppdWR: (r) => r.ppdWR || 0,
    ppdTE: (r) => r.ppdTE || 0,
    ppdK: (r) => r.ppdK || 0,
    ppdDST: (r) => r.ppdDST || 0,
  };
  function cmpPPD(a, b) {
    const fn = PPD_KEYS[ppdKey] || PPD_KEYS.ppd;
    const av = fn(a), bv = fn(b);
    if (typeof av === "string") return av.localeCompare(bv) * ppdDir;
    return ((av || 0) - (bv || 0)) * ppdDir;
  }
  function markPPDSort() {
    document.querySelectorAll("#pos-ppd-tbl thead th[data-k]").forEach((th) => {
      const on = th.dataset.k === ppdKey;
      th.classList.toggle("on", on);
      th.classList.toggle("asc", on && ppdDir > 0);
    });
  }
  function bindPPDSort() {
    const tbl = document.querySelector("#pos-ppd-tbl");
    if (!tbl || tbl.dataset.sortBound) return;
    tbl.dataset.sortBound = "1";
    tbl.querySelectorAll("thead th[data-k]").forEach((th) => {
      th.addEventListener("click", () => {
        const k = th.dataset.k;
        if (ppdKey === k) ppdDir *= -1;
        else {
          ppdKey = k;
          ppdDir = k === "name" ? 1 : -1;
        }
        renderPosPPD();
      });
    });
  }

  function renderPosPPD() {
    const POS = ["QB", "RB", "WR", "TE", "K", "DST"];
    const baselines = {};
    (DV().baselines || []).forEach((b) => { baselines[b.position] = b.baseline; });
    const per = {};
    const baseByYear = DV().baseByYear || {};
    YD.draft.board.forEach((p) => {
      const tid = ownerKey(p.tid);
      if (per[tid] == null) {
        per[tid] = { spend: 0, pts: 0, par: 0, scoredSpend: 0, pos: {} };
        POS.forEach((pos) => { per[tid].pos[pos] = { spend: 0, pts: 0 }; });
      }
      const pos = p.pos === "D/ST" ? "DST" : p.pos;
      const bid = p.bid || 0;
      const r = per[tid];
      r.spend += bid;
      if (p.pts != null) {
        r.pts += p.pts;
        r.scoredSpend += bid;
        const yb = {};
        (baseByYear[p.year] || []).forEach((b) => { yb[b.position] = b.baseline; });
        const base = (p.year != null && yb[pos] != null) ? yb[pos] : baselines[pos];
        if (base != null) r.par += p.pts - base;
      }
      if (r.pos[pos]) {
        r.pos[pos].spend += bid;
        if (p.pts != null) r.pos[pos].pts += p.pts;
      }
    });
    const rows = Object.keys(per).map((tid) => {
      const r = per[tid];
      r.tid = tid;
      r.ppd = r.scoredSpend ? r.pts / r.scoredSpend : 0;
      r.parpd = r.scoredSpend ? r.par / r.scoredSpend : 0;
      POS.forEach((pos) => {
        const p = r.pos[pos];
        r["ppd" + pos] = (p && p.spend) ? p.pts / p.spend : 0;
      });
      return r;
    }).filter((r) => r.spend > 0).sort(cmpPPD);
    const tb = document.querySelector("#pos-ppd-tbl tbody");
    if (!tb) return;
    tb.innerHTML = rows.map((r, i) => {
      const t = teamOf(r.tid);
      const rank = i + 1;
      const pill = rank === 1 ? "gold" : rank === 2 ? "slv" : rank === 3 ? "brz" : "";
      const cell = (pos) => {
        const p = r.pos[pos];
        if (!p || !p.spend) return "—";
        return fmt(p.pts / p.spend, 1);
      };
      return `<tr>
        <td><span class="rank-pill ${pill}">${rank}</span></td>
        <td><div class="team-cell">${A.logoHTML(t, "mini")}<div><strong>${teamLink(r.tid, t.name)}</strong></div></div></td>
        <td>$${fmt(r.spend)}</td>
        <td>${fmt(r.pts, 0)}</td>
        <td><strong>${fmt(r.ppd, 2)}</strong></td>
        <td class="${r.parpd >= 0 ? "pos" : "neg"}">${fmt(r.parpd, 2)}</td>
        ${POS.map(cell).map((c) => `<td>${c}</td>`).join("")}
      </tr>`;
    }).join("");
    bindPPDSort();
    markPPDSort();
  }


  let custodyKey = "ptsKept";
  let custodyDir = -1;
  const CUSTODY_KEYS = {
    name: (r) => (teamOf(r.tid).name || "").toLowerCase(),
    ptsDrafted: (r) => r.ptsDrafted || 0,
    ptsTradedIn: (r) => r.ptsTradedIn || 0,
    ptsWaiver: (r) => r.ptsWaiver || 0,
    ptsFa: (r) => r.ptsFa || 0,
    draftSpendTraded: (r) => r.draftSpendTraded || 0,
    ptsTradedAway: (r) => r.ptsTradedAway || 0,
    ptsDroppedAway: (r) => r.ptsDroppedAway || 0,
    ptsKept: (r) => r.ptsKept || 0,
  };
  function emptyCustody(tid) {
    return { tid, ptsDrafted: 0, ptsTradedIn: 0, ptsWaived: 0,
      draftSpendTraded: 0, nDraftedTraded: 0, ptsTradedAway: 0, ptsDroppedAway: 0,
      ptsWaiver: 0, ptsFa: 0, ptsKept: 0 };
  }
  function addCustody(a, b) {
    ["ptsDrafted","ptsTradedIn","ptsWaived","draftSpendTraded","nDraftedTraded",
     "ptsTradedAway","ptsDroppedAway","ptsWaiver","ptsFa","ptsKept"].forEach((k) => {
      a[k] = (a[k] || 0) + (b[k] || 0);
    });
    return a;
  }
  function custodyRows() {
    if (scope === "cum") {
      const by = {};
      (ALL || []).forEach(({ year: y, data }) => {
        const teams = A.teams(y);
        ((data.custody && data.custody.teams) || []).forEach((r) => {
          const t = teams[r.tid] || teams[String(r.tid)] || {};
          const oid = A.canon(t.owner || r.tid);
          by[oid] = addCustody(by[oid] || emptyCustody(oid), r);
          by[oid].tid = oid;
        });
      });
      return Object.values(by);
    }
    return ((YD.custody && YD.custody.teams) || []).map((r) => Object.assign({}, r));
  }
  function bindCustodySort() {
    const tbl = document.querySelector("#custody-tbl");
    if (!tbl || tbl.dataset.sortBound) return;
    tbl.dataset.sortBound = "1";
    tbl.querySelectorAll("thead th[data-k]").forEach((th) => {
      th.addEventListener("click", () => {
        const k = th.dataset.k;
        if (custodyKey === k) custodyDir *= -1;
        else { custodyKey = k; custodyDir = k === "name" ? 1 : -1; }
        renderCustody();
      });
    });
  }
  function renderCustody() {
    const sub = document.getElementById("custody-sub");
    const tb = document.querySelector("#custody-tbl tbody");
    if (!tb) return;
    const rows = custodyRows().filter((r) => r.ptsKept || r.draftSpendTraded || r.ptsTradedAway);
    if (!rows.length) {
      if (sub) sub.textContent = "weekly custody starts in 2018 — no lineups or transaction feed before that";
      tb.innerHTML = `<tr><td colspan="10" class="own">No weekly custody for this view.</td></tr>`;
      return;
    }
    if (sub) {
      sub.textContent = scope === "cum"
        ? "2018–2025 weekly points while on your roster · current franchise name"
        : year + " · points while on your roster, by how the player arrived";
    }
    const fn = CUSTODY_KEYS[custodyKey] || CUSTODY_KEYS.ptsKept;
    rows.sort((a, b) => {
      const av = fn(a), bv = fn(b);
      if (typeof av === "string") return av.localeCompare(bv) * custodyDir;
      return ((av || 0) - (bv || 0)) * custodyDir;
    });
    tb.innerHTML = rows.map((r, i) => {
      const t = teamOf(r.tid);
      const rank = i + 1;
      const pill = rank === 1 ? "gold" : rank === 2 ? "slv" : rank === 3 ? "brz" : "";
      return `<tr>
        <td><span class="rank-pill ${pill}">${rank}</span></td>
        <td><div class="team-cell">${A.logoHTML(t, "mini")}<div><strong>${teamLink(r.tid, t.name)}</strong></div></div></td>
        <td>${fmt(r.ptsDrafted, 0)}</td>
        <td>${fmt(r.ptsTradedIn, 0)}</td>
        <td>${fmt(r.ptsWaiver, 0)}</td>
        <td>${fmt(r.ptsFa, 0)}</td>
        <td>$${fmt(r.draftSpendTraded)}</td>
        <td class="neg">${fmt(r.ptsTradedAway, 0)}</td>
        <td class="neg">${fmt(r.ptsDroppedAway, 0)}</td>
        <td><strong>${fmt(r.ptsKept, 0)}</strong></td>
      </tr>`;
    }).join("");
    bindCustodySort();
    document.querySelectorAll("#custody-tbl thead th[data-k]").forEach((th) => {
      const on = th.dataset.k === custodyKey;
      th.classList.toggle("on", on);
      th.classList.toggle("asc", on && custodyDir > 0);
    });
  }

  function dnaOwner(y, tid) {
    const teams = A.teams(y);
    const t = teams[tid] || teams[String(tid)] || {};
    return A.canon(t.owner || tid);
  }
  function emptyDna(tid) {
    return { tid, top6Spend: 0, restSpend: 0, top6Share: 0, l1Distance: 0, n: 0, slots: [0, 0, 0, 0, 0, 0] };
  }
  function top6List(r) {
    const raw = Array.isArray(r.top6Spend) ? r.top6Spend
      : (Array.isArray(r.top6) ? r.top6 : (Array.isArray(r.slots) ? r.slots : null));
    if (!raw || !raw.length) return null;
    const out = raw.slice(0, 6).map((n) => Number(n) || 0);
    while (out.length < 6) out.push(0);
    return out;
  }
  function slotsFromBoard(r, board, y) {
    if (!board || !board.length) return null;
    const key = y != null ? dnaOwner(y, r.tid) : ownerKey(r.tid);
    const bids = board.filter((p) => {
      const pk = y != null ? dnaOwner(y, p.tid) : ownerKey(p.tid);
      return pk === key;
    }).map((p) => p.bid || 0).sort((a, b) => b - a).slice(0, 6);
    if (!bids.length) return null;
    while (bids.length < 6) bids.push(0);
    return bids;
  }
  function normalizeDna(r, board, y) {
    const slots = top6List(r) || slotsFromBoard(r, board, y);
    const total = slots
      ? slots.reduce((a, b) => a + b, 0)
      : (typeof r.top6Spend === "number" ? r.top6Spend : 0);
    return {
      tid: r.tid,
      top6Spend: total,
      restSpend: r.restSpend || 0,
      top6Share: r.top6Share || 0,
      l1Distance: r.l1Distance || 0,
      slots: slots,
    };
  }
  function auctionDnaRows() {
    if (scope === "cum") {
      const by = {};
      (ALL || []).forEach(({ year: y, data }) => {
        if (!data || !data.draft || !data.draft.auction) return;
        const rows = data.auctionDna;
        if (!rows || !rows.length) return;
        const board = (data.draft && data.draft.board) || [];
        rows.forEach((r) => {
          const oid = dnaOwner(y, r.tid);
          const row = normalizeDna(r, board, y);
          const cur = by[oid] || emptyDna(oid);
          cur.top6Spend += row.top6Spend || 0;
          cur.restSpend += row.restSpend || 0;
          cur.top6Share += row.top6Share || 0;
          cur.l1Distance += row.l1Distance || 0;
          cur.n += 1;
          if (row.slots) {
            for (let i = 0; i < 6; i++) cur.slots[i] += row.slots[i] || 0;
            cur.hasSlots = true;
          }
          cur.tid = oid;
          by[oid] = cur;
        });
      });
      return Object.values(by).map((r) => {
        const n = Math.max(1, r.n);
        return {
          tid: r.tid,
          top6Spend: r.top6Spend / n,
          restSpend: r.restSpend / n,
          top6Share: r.top6Share / n,
          l1Distance: r.l1Distance / n,
          slots: r.hasSlots ? r.slots.map((s) => s / n) : null,
          n: r.n,
        };
      });
    }
    return ((YD && YD.auctionDna) || []).map((r) =>
      normalizeDna(r, (YD.draft && YD.draft.board) || [], year));
  }

  let dnaKey = "l1Distance";
  let dnaDir = 1;
  const DNA_KEYS = {
    name: (r) => (teamOf(r.tid).name || "").toLowerCase(),
    top6Spend: (r) => r.top6Spend || 0,
    restSpend: (r) => r.restSpend || 0,
    l1Distance: (r) => r.l1Distance || 0,
  };
  function bindDnaSort() {
    const tbl = document.querySelector("#dna-tbl");
    if (!tbl || tbl.dataset.sortBound) return;
    tbl.dataset.sortBound = "1";
    tbl.querySelectorAll("thead th[data-k]").forEach((th) => {
      th.addEventListener("click", () => {
        const k = th.dataset.k;
        if (dnaKey === k) dnaDir *= -1;
        else { dnaKey = k; dnaDir = k === "name" || k === "l1Distance" ? 1 : -1; }
        renderAuctionDNA();
      });
    });
  }
  function renderAuctionDNA() {
    const el = document.getElementById("auction-dna-block");
    const wrap = document.getElementById("dna-chart-wrap");
    const empty = document.getElementById("dna-empty");
    const tb = document.querySelector("#dna-tbl tbody");
    const sub = document.getElementById("dna-sub");
    if (!el || !tb) return;
    const snake = scope === "season" && (year < 2016 || !(YD && YD.draft && YD.draft.auction));
    if (snake) {
      el.hidden = true;
      if (dnaChart) { dnaChart.destroy(); dnaChart = null; }
      return;
    }
    el.hidden = false;
    const rows = auctionDnaRows();
    if (sub) {
      sub.textContent = scope === "cum"
        ? "average top-6 vs Cates $58/$40/$24/$13/$12/$9 across auction years · not career-stacked"
        : "top-6 spend vs the Cates championship curve $58 / $40 / $24 / $13 / $12 / $9";
    }
    if (!rows.length) {
      if (wrap) wrap.hidden = true;
      if (empty) { empty.hidden = false; empty.textContent = "Auction DNA is not in this season file yet."; }
      tb.innerHTML = `<tr><td colspan="5" class="own">No auction DNA for this view.</td></tr>`;
      if (dnaChart) { dnaChart.destroy(); dnaChart = null; }
      return;
    }
    if (wrap) wrap.hidden = false;
    if (empty) empty.hidden = true;
    const fn = DNA_KEYS[dnaKey] || DNA_KEYS.l1Distance;
    rows.sort((a, b) => {
      const av = fn(a), bv = fn(b);
      if (typeof av === "string") return av.localeCompare(bv) * dnaDir;
      return ((av || 0) - (bv || 0)) * dnaDir;
    });
    tb.innerHTML = rows.map((r, i) => {
      const rank = i + 1;
      const pill = rank === 1 ? "gold" : rank === 2 ? "slv" : rank === 3 ? "brz" : "";
      return `<tr>
        <td><span class="rank-pill ${pill}">${rank}</span></td>
        <td>${teamCell(r.tid)}</td>
        <td>$${fmt(r.top6Spend)}</td>
        <td>$${fmt(r.restSpend)}</td>
        <td><strong>${fmt(r.l1Distance, 1)}</strong></td>
      </tr>`;
    }).join("");
    bindDnaSort();
    document.querySelectorAll("#dna-tbl thead th[data-k]").forEach((th) => {
      const on = th.dataset.k === dnaKey;
      th.classList.toggle("on", on);
      th.classList.toggle("asc", on && dnaDir > 0);
    });

    const SLOT_COLORS = [C.gold, C.orange, C.fire, C.blue, C.ice, C.steel];
    const hasSlots = rows.some((r) => r.slots && r.slots.length);
    if (dnaChart) dnaChart.destroy();
    const canvas = document.getElementById("dna-chart");
    if (!canvas) return;
    dnaChart = new Chart(canvas, {
      data: {
        labels: rows.map((r) => short(r.tid)),
        datasets: hasSlots
          ? [
              ...CATES.map((_, i) => ({
                type: "bar",
                label: (i + 1) + (i === 0 ? "st" : i === 1 ? "nd" : i === 2 ? "rd" : "th"),
                stack: "top6",
                data: rows.map((r) => (r.slots && r.slots[i]) || 0),
                backgroundColor: SLOT_COLORS[i],
                maxBarThickness: 30,
                order: 2,
              })),
              {
                type: "line",
                label: "Cates $" + CATES_SUM,
                data: rows.map(() => CATES_SUM),
                borderColor: "#ffffff",
                backgroundColor: "#ffffff",
                borderWidth: 2,
                borderDash: [5, 4],
                pointRadius: 0,
                tension: 0,
                order: 1,
              },
            ]
          : [
              {
                type: "bar",
                label: "Top 6 $",
                data: rows.map((r) => r.top6Spend || 0),
                backgroundColor: C.gold,
                maxBarThickness: 30,
                order: 2,
              },
              {
                type: "line",
                label: "Cates $" + CATES_SUM,
                data: rows.map(() => CATES_SUM),
                borderColor: "#ffffff",
                backgroundColor: "#ffffff",
                borderWidth: 2,
                borderDash: [5, 4],
                pointRadius: 0,
                tension: 0,
                order: 1,
              },
            ],
      },
      options: {
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        plugins: {
          legend: { labels: { boxWidth: 10, boxHeight: 10, usePointStyle: true, pointStyle: "circle" } },
          tooltip: { callbacks: { afterBody: (items) => {
            const r = rows[items[0].dataIndex];
            const curve = CATES.map((n) => "$" + n).join(" / ");
            return `Rest $${fmt(r.restSpend)} · L1 ${fmt(r.l1Distance, 1)} · curve ${curve}`;
          } } },
        },
        scales: {
          y: { stacked: !!hasSlots, beginAtZero: true, grid: { color: C.grid }, border: { display: false },
               title: { display: true, text: scope === "cum" ? "avg $ / auction year" : "$ spent" } },
          x: { stacked: !!hasSlots, grid: { display: false }, border: { display: false },
               ticks: { maxRotation: 55, minRotation: 40 } },
        },
      },
    });
  }

  function emptyW1(tid) {
    return { tid, w1Pts: 0, acquiredPts: 0 };
  }
  function w1Rows() {
    if (scope === "cum") {
      const by = {};
      (ALL || []).forEach(({ year: y, data }) => {
        if (y < 2018) return;
        const rows = data && data.w1Acquired;
        if (!rows || !rows.length) return;
        rows.forEach((r) => {
          const oid = dnaOwner(y, r.tid);
          const a = by[oid] || emptyW1(oid);
          a.w1Pts += r.w1Pts || 0;
          a.acquiredPts += r.acquiredPts || 0;
          a.tid = oid;
          by[oid] = a;
        });
      });
      return Object.values(by).map((r) => {
        const tot = (r.w1Pts || 0) + (r.acquiredPts || 0);
        return {
          tid: r.tid,
          w1Pts: r.w1Pts,
          acquiredPts: r.acquiredPts,
          w1Share: tot ? r.w1Pts / tot : 0,
          acquiredShare: tot ? r.acquiredPts / tot : 0,
        };
      });
    }
    return ((YD && YD.w1Acquired) || []).map((r) => Object.assign({}, r));
  }
  function sharePct(x) {
    if (x == null || x === "") return null;
    const n = Number(x);
    if (Number.isNaN(n)) return null;
    return n > 1.5 ? n : n * 100;
  }
  let w1Key = "w1Share";
  let w1Dir = -1;
  const W1_KEYS = {
    name: (r) => (teamOf(r.tid).name || "").toLowerCase(),
    w1Pts: (r) => r.w1Pts || 0,
    acquiredPts: (r) => r.acquiredPts || 0,
    w1Share: (r) => sharePct(r.w1Share) || 0,
    acquiredShare: (r) => sharePct(r.acquiredShare) || 0,
  };
  function bindW1Sort() {
    const tbl = document.querySelector("#w1-tbl");
    if (!tbl || tbl.dataset.sortBound) return;
    tbl.dataset.sortBound = "1";
    tbl.querySelectorAll("thead th[data-k]").forEach((th) => {
      th.addEventListener("click", () => {
        const k = th.dataset.k;
        if (w1Key === k) w1Dir *= -1;
        else { w1Key = k; w1Dir = k === "name" ? 1 : -1; }
        renderW1();
      });
    });
  }
  function renderW1() {
    const el = document.getElementById("w1-block");
    const empty = document.getElementById("w1-empty");
    const tb = document.querySelector("#w1-tbl tbody");
    const sub = document.getElementById("w1-sub");
    const awards = document.getElementById("w1-awards");
    if (!el || !tb) return;
    if (scope === "season" && year < 2018) {
      el.hidden = true;
      return;
    }
    el.hidden = false;
    const rows = w1Rows();
    if (sub) {
      sub.textContent = scope === "cum"
        ? "2018–2025 · Draft Day % from week-1 roster points · Moneyball % from acquired points"
        : year + " · Draft Day % from the week-1 roster · Moneyball % from players acquired after";
    }
    if (!rows.length) {
      if (empty) { empty.hidden = false; empty.textContent = "Week 1 vs acquired is not in this season file yet."; }
      if (awards) awards.innerHTML = "";
      tb.innerHTML = `<tr><td colspan="6" class="own">No week-1 vs acquired for this view.</td></tr>`;
      return;
    }
    if (empty) empty.hidden = true;
    const fn = W1_KEYS[w1Key] || W1_KEYS.w1Share;
    rows.sort((a, b) => {
      const av = fn(a), bv = fn(b);
      if (typeof av === "string") return av.localeCompare(bv) * w1Dir;
      return ((av || 0) - (bv || 0)) * w1Dir;
    });
    let draftDay = null, moneyball = null;
    rows.forEach((r) => {
      if (!draftDay || (sharePct(r.w1Share) || 0) > (sharePct(draftDay.w1Share) || 0)) draftDay = r;
      if (!moneyball || (sharePct(r.acquiredShare) || 0) > (sharePct(moneyball.acquiredShare) || 0)) moneyball = r;
    });
    const card = (k, title, row, which) => {
      const t = row ? teamOf(row.tid) : { name: "—" };
      const pct = row ? sharePct(which === "w1" ? row.w1Share : row.acquiredShare) : null;
      return `<div class="card w1-award">
        <div class="w1-award-kicker">${k}</div>
        <div class="w1-award-copy">
          <div class="w1-award-title">${title}</div>
          <div class="w1-award-name">${t.name}</div>
          <div class="w1-award-pct">${pct != null ? fmt(pct, 1) + "%" : "—"}</div>
        </div>
        ${row ? A.logoHTML(t, "w1-award-logo") : `<div class="w1-award-logo fb">—</div>`}
      </div>`;
    };
    if (awards) {
      awards.innerHTML = [
        card("DRAFT DAY", "Highest week-1 share", draftDay, "w1"),
        card("MONEYBALL", "Highest acquired share", moneyball, "acq"),
      ].join("");
    }
    tb.innerHTML = rows.map((r, i) => {
      const rank = i + 1;
      const pill = rank === 1 ? "gold" : rank === 2 ? "slv" : rank === 3 ? "brz" : "";
      const w1p = sharePct(r.w1Share);
      const acq = sharePct(r.acquiredShare);
      return `<tr>
        <td><span class="rank-pill ${pill}">${rank}</span></td>
        <td>${teamCell(r.tid)}</td>
        <td>${fmt(r.w1Pts, 0)}</td>
        <td>${fmt(r.acquiredPts, 0)}</td>
        <td><strong>${w1p != null ? fmt(w1p, 1) + "%" : "—"}</strong></td>
        <td>${acq != null ? fmt(acq, 1) + "%" : "—"}</td>
      </tr>`;
    }).join("");
    bindW1Sort();
    document.querySelectorAll("#w1-tbl thead th[data-k]").forEach((th) => {
      const on = th.dataset.k === w1Key;
      th.classList.toggle("on", on);
      th.classList.toggle("asc", on && w1Dir > 0);
    });
  }

  function milesRisk(touches, ageYears) {
    if (touches == null && (ageYears == null || ageYears < 29)) return null;
    if ((touches != null && touches > 1500) || (ageYears != null && ageYears >= 29)) {
      return { cls: "hot", label: "decay" };
    }
    if (touches != null && touches >= 1000) return { cls: "warn", label: "miles" };
    if (touches != null) return { cls: "ok", label: "fresh" };
    return null;
  }
  function milesCell(p) {
    const pos = p.pos === "D/ST" ? "DST" : p.pos;
    const skill = pos === "RB" || pos === "WR" || pos === "TE";
    if (!skill) return `<td class="own">—</td>`;
    const y = pickYear(p);
    const touches = touchesAsOf(p.pid, y);
    const bio = A.playerBio(p.pid, y, asOf) || {};
    const seasonAge = bio.birth ? A.ageOn(bio.birth, String(y) + "-09-01") : null;
    const ageYears = seasonAge ? seasonAge.years : null;
    if (touches == null && pos !== "RB" && (ageYears == null || ageYears < 29)) {
      return `<td class="own">—</td>`;
    }
    const risk = milesRisk(touches, ageYears);
    const n = touches == null ? "—" : fmt(touches, 0);
    const lab = risk ? `<span class="draft-risk ${risk.cls}">${risk.label}</span>` : "";
    return `<td class="draft-miles">${n}${lab}</td>`;
  }

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
        desc: `<strong>${A.playerLink(priciest.pid, priciest.name, { year: pickYear(priciest) })}</strong>${priciest.pts != null ? ` · returned ${fmt(priciest.pts, 0)} pts` : ''}` },
      (DV().steals || [])[0] && (() => {
        const s = DV().steals[0];
        return { n: '03 · BEST VALUE', color: C.green, pct: 1,
          label: '+' + fmt(s.par, 0),
          title: 'Steal Of The Draft',
          desc: `<strong>${A.playerLink(s.pid, s.name, { year: pickYear(s) })}</strong> · ${auction ? `$${s.bid || 0} → ` : ''}` +
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
      const tid = ownerKey(p.tid);
      const b = (per[tid] = per[tid] || { pts: 0, spend: 0, byPos: {}, years: {} });
      b.spend += p.bid || 0;
      b.pts += p.pts || 0;
      if (p.year) b.years[p.year] = true;
      const key = POS_COLORS[p.pos] ? p.pos : 'K';
      b.byPos[key] = (b.byPos[key] || 0) + (auction ? (p.bid || 0) : 1);
    });
    const rows = Object.keys(per).map((tid) => ({ tid, ...per[tid] }))
      .filter((r) => r.spend > 0 || Object.values(r.byPos).some(Boolean))
      .sort((a, b) => b.pts - a.pts);
    const anyPts = rows.some((r) => r.pts > 0);
    const nYears = (r) => Math.max(1, Object.keys(r.years || {}).length);
    const avg = auction && scope === "cum";

    $('#spend-sub').textContent = auction
      ? (avg
          ? "average $200 allocation across auction years · line = career points per dollar"
          : "how each team allocated their $200 across positions · line = points returned per dollar")
      : "draft picks by position · line = points those picks returned";

    if (chart) chart.destroy();
    chart = new Chart($('#spend-chart'), {
      data: {
        labels: rows.map((r) => short(r.tid)),
        datasets: [
          ...Object.keys(POS_COLORS).map((pos) => ({
            type: 'bar', label: pos, stack: 'spend', yAxisID: 'y',
            data: rows.map((r) => {
              const raw = r.byPos[pos] || 0;
              return avg ? raw / nYears(r) : raw;
            }),
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
      <td><strong>${A.playerLink(p.pid, p.name, { year: pickYear(p) })}</strong> <span class="badge pos-${p.pos}">${p.pos}</span>
        <div class="own">${p.year ? p.year + ' · ' : ''}${short(p.tid)}</div></td>
      <td>${auction ? '$' + (p.bid || 0) : '#' + p.overall}</td>
      <td><span class="badge ${cls}">${p.par >= 0 ? '+' : ''}${fmt(p.par, 0)}</span>
        <div class="own">${fmt(p.pts, 0)} pts</div></td></tr>`;
    const none = `<tr><td colspan="3" class="own">ESPN stores no weekly scoring for ${year}, so returns can't be graded.</td></tr>`;
    $('#steals-tbl tbody').innerHTML = (steals || []).map((p) => row(p, 'steal')).join('') || none;
    $('#busts-tbl tbody').innerHTML = (busts || []).map((p) => row(p, 'bust')).join('') || '';

    // show the baseline so the number is auditable rather than magic
    const el = $('#baseline-note');
    if (el) {
      const note = DV().computed
        ? ' ESPN kept no lineups this season, so season points are <strong>computed</strong> ' +
          'from NFL stats under this year\'s scoring rules — kickers and D/ST are excluded.'
        : '';
      el.innerHTML = (baselines || []).length
        ? 'Replacement level this season — ' + baselines.map((b) =>
            `<strong>${b.position}</strong> ${fmt(b.baseline, 0)}`).join(' · ') +
          '. Value is points above that line, per dollar.' + note
        : '';
    }
  }


  let asOf = A.today();
  function isoDay(d) {
    const x = d || A.today();
    const m = String(x.getMonth() + 1).padStart(2, "0");
    const day = String(x.getDate()).padStart(2, "0");
    return x.getFullYear() + "-" + m + "-" + day;
  }
  function pickYear(p) { return p.year || year; }
  function withBio(p) {
    const b = A.playerBio(p.pid, pickYear(p), asOf) || {};
    return Object.assign({}, p, {
      age: b.age,
      ageText: b.ageText || "",
      college: b.college || "",
      nfl: p.nfl || b.nfl || "",
    });
  }
  function bindAsOf() {
    const el = document.getElementById("age-asof");
    const sub = document.getElementById("age-sub");
    if (!el) return;
    if (!el.dataset.bound) {
      el.dataset.bound = "1";
      el.addEventListener("change", () => {
        if (el.value) {
          const p = el.value.split("-");
          asOf = new Date(+p[0], +p[1] - 1, +p[2]);
        } else asOf = A.today();
        renderAge();
        renderBoard();
      });
    }
    if (!el.value) el.value = isoDay(asOf);
    if (sub) {
      const same = isoDay(asOf) === isoDay(A.today());
      sub.textContent = same
        ? "ages as of today · updates at midnight"
        : "ages as of " + isoDay(asOf);
    }
  }
  function mean(arr) {
    return arr.length ? arr.reduce((a, b) => a + b, 0) / arr.length : null;
  }

  function renderAge() {
    bindAsOf();
    const POS = ["QB", "RB", "WR", "TE", "K", "DST"];
    const board = (YD.draft.board || []).map(withBio);
    const aged = board.filter((p) => p.age != null);
    const awards = document.getElementById("age-awards");
    const tbl = document.querySelector("#age-tbl tbody");
    if (!awards || !tbl) return;

    const byTeam = {};
    board.forEach((p) => {
      const tid = p.tid;
      if (byTeam[tid] == null) byTeam[tid] = { tid, picks: [], pos: {} };
      byTeam[tid].picks.push(p);
      const pos = p.pos === "D/ST" ? "DST" : p.pos;
      (byTeam[tid].pos[pos] = byTeam[tid].pos[pos] || []).push(p);
    });
    const teams = Object.values(byTeam).map((t) => {
      const ages = t.picks.map((p) => p.age).filter((a) => a != null);
      t.avg = mean(ages);
      t.n = ages.length;
      POS.forEach((pos) => {
        t["avg" + pos] = mean((t.pos[pos] || []).map((p) => p.age).filter((a) => a != null));
      });
      const ranked = t.picks.filter((p) => p.age != null).slice().sort((a, b) => a.age - b.age);
      t.young = ranked[0] || null;
      t.old = ranked.length ? ranked[ranked.length - 1] : null;
      return t;
    }).filter((t) => t.n).sort((a, b) => a.avg - b.avg);

    const youngTeam = teams[0];
    const oldTeam = teams[teams.length - 1];
    const youngPick = aged.slice().sort((a, b) => a.age - b.age)[0];
    const oldPick = aged.slice().sort((a, b) => b.age - a.age)[0];
    const card = (k, title, name, sub, extra) => `
      <div class="card kpi age-award">
        <div class="kpi-num">${k}</div>
        <div class="kpi-title">${title}</div>
        <div class="kpi-desc"><strong>${name || "—"}</strong><div class="own">${sub || ""}</div>${extra || ""}</div>
      </div>`;
    awards.innerHTML = [
      card("YOUNG GUNZ", youngTeam ? fmt(youngTeam.avg, 1) + " avg" : "—",
        youngTeam ? short(youngTeam.tid) : "", youngTeam ? youngTeam.n + " aged picks" : ""),
      card("OLD HEADS", oldTeam ? fmt(oldTeam.avg, 1) + " avg" : "—",
        oldTeam ? short(oldTeam.tid) : "", oldTeam ? oldTeam.n + " aged picks" : ""),
      card("YOUNGEST", youngPick ? fmt(youngPick.age, 1) : "—",
        youngPick ? A.playerLink(youngPick.pid, youngPick.name, { year: pickYear(youngPick) }) : "", youngPick ? (youngPick.pos + " · " + (youngPick.nfl || "")) : "",
        youngPick ? A.nflLogoHTML(youngPick.nfl, "nfl-logo") : ""),
      card("OLDEST", oldPick ? fmt(oldPick.age, 1) : "—",
        oldPick ? A.playerLink(oldPick.pid, oldPick.name, { year: pickYear(oldPick) }) : "", oldPick ? (oldPick.pos + " · " + (oldPick.nfl || "")) : "",
        oldPick ? A.nflLogoHTML(oldPick.nfl, "nfl-logo") : ""),
    ].join("");

    tbl.innerHTML = teams.map((t, i) => {
      const rank = i + 1;
      const pill = rank === 1 ? "gold" : rank === 2 ? "slv" : rank === 3 ? "brz" : "";
      const tm = teamOf(t.tid);
      const pos = (k) => t["avg" + k] != null ? fmt(t["avg" + k], 1) : "—";
      const who = (p) => p ? `${A.nflLogoHTML(p.nfl, "nfl-logo sm")} ${A.playerLink(p.pid, p.name, { year: pickYear(p) })} <span class="own">${fmt(p.age, 1)}</span>` : "—";
      return `<tr>
        <td><span class="rank-pill ${pill}">${rank}</span></td>
        <td><div class="team-cell">${A.logoHTML(tm, "mini")}<strong>${teamLink(t.tid, tm.name || short(t.tid))}</strong></div></td>
        <td><strong>${fmt(t.avg, 1)}</strong></td>
        <td>${pos("QB")}</td><td>${pos("RB")}</td><td>${pos("WR")}</td>
        <td>${pos("TE")}</td><td>${pos("K")}</td><td>${pos("DST")}</td>
        <td>${who(t.young)}</td>
        <td>${who(t.old)}</td>
      </tr>`;
    }).join("");

    const stacks = {};
    const homies = {};
    board.forEach((p) => {
      if (p.nfl) {
        const k = p.tid + "|" + p.nfl;
        (stacks[k] = stacks[k] || { tid: p.tid, nfl: p.nfl, picks: [] }).picks.push(p);
      }
      if (p.college) {
        const k = p.tid + "|" + p.college;
        (homies[k] = homies[k] || { tid: p.tid, college: p.college, picks: [] }).picks.push(p);
      }
    });
    const list = (obj, labelFn) => Object.values(obj)
      .filter((g) => g.picks.length >= 2)
      .sort((a, b) => b.picks.length - a.picks.length)
      .slice(0, 8)
      .map((g) => `<div class="age-chip">${A.nflLogoHTML(g.nfl, "nfl-logo sm")}
        <div><strong>${short(g.tid)}</strong> · ${labelFn(g)}
        <div class="own">${g.picks.map((p) => A.playerLink(p.pid, p.name, { year: pickYear(p) }) + (p.age != null ? " " + fmt(p.age, 1) : "")).join(" · ")}</div></div></div>`)
      .join("") || '<div class="own">Need two+ from the same group.</div>';
    const stacksEl = document.getElementById("age-stacks");
    const homiesEl = document.getElementById("age-homies");
    if (stacksEl) stacksEl.innerHTML = list(stacks, (g) => g.nfl);
    if (homiesEl) homiesEl.innerHTML = list(homies, (g) => g.college);
  }

  function navNormPos(pos) {
    return pos === "D/ST" ? "DST" : (pos || "");
  }
  function navRoundOf(p) {
    const auction = !!(YD && YD.draft && YD.draft.auction) || !!p.auction;
    if (auction) {
      const ov = Number(p.overall) || 0;
      if (ov) return Math.ceil(ov / 12);
    }
    if (p.round != null && p.round !== "") return Number(p.round);
    const ov = Number(p.overall) || 0;
    return ov ? Math.ceil(ov / 12) : 1;
  }
  function navParOf(p) {
    const idx = parIndex();
    if (!idx) return null;
    let v = null;
    if (p.year != null && idx[p.year + ":" + p.overall] != null) v = idx[p.year + ":" + p.overall];
    else if (idx[String(p.overall)] != null) v = idx[String(p.overall)];
    if (v == null || v === "") return null;
    const n = Number(v);
    return Number.isNaN(n) ? null : n;
  }
  function navPass(p) {
    const pos = navNormPos(p.pos);
    if (S.pos && S.pos !== "ALL" && pos !== S.pos) return false;
    const q = (S.q || "").toLowerCase();
    if (!q) return true;
    return (p.name || "").toLowerCase().includes(q) || tName(p.tid).toLowerCase().includes(q)
      || (p.nfl || "").toLowerCase().includes(q);
  }
  function navPicks() {
    return ((YD && YD.draft && YD.draft.board) || []).map((p) => {
      const b = withBio(p);
      return Object.assign({}, b, {
        pos: navNormPos(b.pos),
        oid: ownerKey(b.tid),
        par: navParOf(b),
        rnd: navRoundOf(b),
      });
    });
  }
  function navStackLabel(n) {
    if (n >= 4) return "QUAD";
    if (n === 3) return "TRIPLE";
    if (n === 2) return "DOUBLE";
    return "";
  }
  function bindViewToggle() {
    const el = document.getElementById("board-view-toggle");
    if (!el || el.dataset.bound) return;
    el.dataset.bound = "1";
    el.querySelectorAll("button[data-view]").forEach((b) => {
      b.addEventListener("click", () => {
        S.view = b.dataset.view === "board" ? "board" : "table";
        renderBoard();
      });
    });
  }
  function bindPosChips() {
    const el = document.getElementById("board-pos-chips");
    if (!el || el.dataset.bound) return;
    el.dataset.bound = "1";
    el.querySelectorAll("button[data-pos]").forEach((b) => {
      b.addEventListener("click", () => {
        S.pos = b.dataset.pos || "ALL";
        S.limit = 60;
        renderBoard();
        renderGuide();
      });
    });
  }
  function markViewChips() {
    document.querySelectorAll("#board-view-toggle button[data-view]").forEach((b) => {
      b.classList.toggle("on", b.dataset.view === S.view);
    });
    document.querySelectorAll("#board-pos-chips button[data-pos]").forEach((b) => {
      b.classList.toggle("on", b.dataset.pos === S.pos);
    });
  }
  function navSortVal(td) {
    if (!td) return null;
    const raw = (td.getAttribute("data-sv") || td.textContent || "").replace(/[$,+%]/g, "").trim();
    if (raw === "—" || raw === "") return null;
    const n = Number(String(raw).replace(/,/g, ""));
    if (!Number.isNaN(n) && /^-?[\d.]+$/.test(String(raw).replace(/,/g, ""))) return n;
    return raw.toLowerCase();
  }
  function bindNavTableSort(table) {
    if (!table || table.dataset.navSort) return;
    if (table.dataset.sortBound) return;
    table.dataset.navSort = "1";
    table.querySelectorAll("thead th").forEach((th) => {
      const label = (th.textContent || "").trim();
      if (!label && !th.dataset.k) return;
      th.classList.add("s");
      if (!th.dataset.k) th.dataset.k = "c" + [...th.parentNode.children].indexOf(th);
      th.addEventListener("click", () => {
        const idx = [...th.parentNode.children].indexOf(th);
        const cur = table.dataset.sortCol;
        let dir = -1;
        if (cur === String(idx)) dir = Number(table.dataset.sortDir || -1) * -1;
        else dir = (th.dataset.k === "name" || /team|player|nfl/i.test(label)) ? 1 : -1;
        table.dataset.sortCol = String(idx);
        table.dataset.sortDir = String(dir);
        table.querySelectorAll("thead th").forEach((x) => {
          x.classList.toggle("on", x === th);
          x.classList.toggle("asc", x === th && dir > 0);
        });
        const tb = table.tBodies[0];
        if (!tb) return;
        const rows = [...tb.rows];
        rows.sort((a, b) => {
          const av = navSortVal(a.cells[idx]);
          const bv = navSortVal(b.cells[idx]);
          if (av == null && bv == null) return 0;
          if (av == null) return 1;
          if (bv == null) return -1;
          if (typeof av === "string" || typeof bv === "string")
            return String(av).localeCompare(String(bv)) * dir;
          return (av - bv) * dir;
        });
        rows.forEach((r) => tb.appendChild(r));
      });
    });
  }
  function bindAllDraftSorts() {
    const skip = { "pos-ppd-tbl": 1, "custody-tbl": 1, "dna-tbl": 1, "w1-tbl": 1, "board-tbl": 1 };
    document.querySelectorAll("table.tbl").forEach((tbl) => {
      if (skip[tbl.id]) return;
      bindNavTableSort(tbl);
    });
  }
  function bindBoardSort() {
    const tbl = document.getElementById("board-tbl");
    if (!tbl || tbl.dataset.sortBound) return;
    tbl.dataset.sortBound = "1";
    tbl.querySelectorAll("thead th[data-k]").forEach((th) => {
      th.addEventListener("click", () => {
        const k = th.dataset.k;
        if (boardKey === k) boardDir *= -1;
        else { boardKey = k; boardDir = (k === "name" || k === "team" || k === "nfl" || k === "pos") ? 1 : -1; }
        renderBoard();
      });
    });
  }
  function markBoardSort() {
    document.querySelectorAll("#board-tbl thead th[data-k]").forEach((th) => {
      const on = th.dataset.k === boardKey;
      th.classList.toggle("on", on);
      th.classList.toggle("asc", on && boardDir > 0);
    });
  }
  const BOARD_KEYS = {
    year: (p) => p.year || 0,
    overall: (p) => p.overall || 0,
    name: (p) => (p.name || "").toLowerCase(),
    pos: (p) => navNormPos(p.pos) || "",
    nfl: (p) => (p.nfl || "").toLowerCase(),
    age: (p) => { const b = withBio(p); return b.age == null ? -1 : b.age; },
    miles: (p) => { const t = touchesAsOf(p.pid, pickYear(p)); return t == null ? -1 : t; },
    team: (p) => tName(p.tid).toLowerCase(),
    cost: (p) => p.bid || 0,
    pts: (p) => p.pts == null ? -1 : p.pts,
    par: (p) => { const v = navParOf(p); return v == null ? -9999 : v; },
  };

  function buildNavGrid(picks, yearLabel) {
    const auction = !!(YD && YD.draft && YD.draft.auction);
    const first = {};
    picks.forEach((p) => {
      const tid = p.oid || ownerKey(p.tid);
      const ov = p.overall || 9999;
      if (first[tid] == null || ov < first[tid]) first[tid] = ov;
    });
    const teams = Object.keys(first).sort((a, b) => first[a] - first[b] || tName(a).localeCompare(tName(b)));
    let maxR = 0;
    picks.forEach((p) => { if ((p.rnd || 0) > maxR) maxR = p.rnd; });
    if (!maxR) maxR = 1;
    const by = {};
    picks.forEach((p) => {
      const tid = p.oid || ownerKey(p.tid);
      const k = tid + ":" + p.rnd;
      (by[k] = by[k] || []).push(p);
    });
    const head = [`<div class="nav-board-r">${yearLabel != null ? yearLabel : ""}</div>`];
    for (let r = 1; r <= maxR; r++) head.push(`<div class="nav-board-h">R${r}</div>`);
    const cells = head.slice();
    teams.forEach((tid) => {
      cells.push(`<div class="nav-board-r">${teamLink(tid, short(tid))}</div>`);
      for (let r = 1; r <= maxR; r++) {
        const list = by[tid + ":" + r] || [];
        if (!list.length) {
          cells.push(`<div class="nav-cell empty"></div>`);
          continue;
        }
        const inner = list.map((p) => {
          const pos = navNormPos(p.pos);
          const dim = S.pos && S.pos !== "ALL" && pos !== S.pos;
          return `<div class="nav-cell pos-${pos}${dim ? " dim" : ""}">
            <div class="nav-cell-name">${A.playerLink(p.pid, p.name, { year: pickYear(p) })}</div>
            <div class="nav-cell-meta"><span class="badge pos-${pos}">${pos || "—"}</span>
              <span>${A.nflLogoHTML(p.nfl, "nfl-logo sm")} ${p.nfl || "—"}</span></div>
          </div>`;
        }).join("");
        cells.push(list.length > 1 ? `<div class="nav-cell-stack">${inner}</div>` : inner);
      }
    });
    const style = `--nav-rounds:${maxR}`;
    const sub = (auction ? "auction · nomination order · rounds of 12" : "snake · franchise × round")
      + (yearLabel != null ? " · " + yearLabel : "");
    return `<div class="nav-board-block">
      <div class="card-sub">${sub} · ${teams.length} franchises · ${picks.length} picks</div>
      <div class="nav-board" style="${style}">${cells.join("")}</div>
    </div>`;
  }

  function renderNavBoard(all) {
    const grid = document.getElementById("nav-board");
    const sub = document.getElementById("nav-board-sub");
    if (!grid) return;
    if (!all.length) {
      grid.innerHTML = `<div class="draft-empty">No picks to grid.</div>`;
      return;
    }
    if (scope === "cum") {
      const years = [...new Set(all.map((p) => p.year).filter((y) => y != null))].sort((a, b) => b - a);
      if (!years.length) {
        grid.innerHTML = buildNavGrid(all, null);
      } else {
        grid.innerHTML = years.map((y) => buildNavGrid(all.filter((p) => p.year === y), y)).join("");
      }
      if (sub) sub.textContent = "franchise × round · stacked by year · color by position";
    } else {
      grid.innerHTML = buildNavGrid(all, year);
      if (sub) {
        const auction = !!(YD && YD.draft && YD.draft.auction);
        sub.textContent = auction
          ? year + " · franchise × nomination round (overall into rounds of 12) · color by position"
          : year + " · franchise × round · color by position";
      }
    }
  }

  function renderFgAwards(picks) {
    const el = document.getElementById("fg-awards");
    const body = document.getElementById("fg-awards-body");
    const sub = document.getElementById("fg-awards-sub");
    if (!el || !body) return;
    const aged = picks.filter((p) => p.age != null);
    const byTeam = {};
    aged.forEach((p) => {
      const tid = p.oid;
      (byTeam[tid] = byTeam[tid] || []).push(p.age);
    });
    const teamAvgs = Object.keys(byTeam).map((tid) => ({
      tid, avg: byTeam[tid].reduce((a, b) => a + b, 0) / byTeam[tid].length, n: byTeam[tid].length,
    })).filter((t) => t.n).sort((a, b) => a.avg - b.avg);
    const young = teamAvgs[0];
    const old = teamAvgs.length ? teamAvgs[teamAvgs.length - 1] : null;
    const dv = DV();
    const steal = (dv.steals && dv.steals[0]) || null;
    const bust = (dv.busts && dv.busts[0]) || null;
    const scoredP = picks.filter((p) => p.par != null);
    const best = steal || (scoredP.length ? scoredP.slice().sort((a, b) => b.par - a.par)[0] : null);
    const worst = bust || (scoredP.length ? scoredP.slice().sort((a, b) => a.par - b.par)[0] : null);
    if (!young && !old && !best && !worst) {
      el.hidden = true;
      body.innerHTML = "";
      return;
    }
    el.hidden = false;
    if (sub) {
      sub.textContent = scope === "cum"
        ? "youngest / oldest roster · best value / worst reach from draftValue"
        : year + " · youngest / oldest · best value / worst reach";
    }
    const card = (k, title, name, extra) => `
      <div class="card kpi age-award">
        <div class="kpi-num">${k}</div>
        <div class="kpi-title">${title}</div>
        <div class="kpi-desc"><strong>${name || "—"}</strong><div class="own">${extra || ""}</div></div>
      </div>`;
    const bits = [];
    if (young) bits.push(card("YOUNGEST TEAM", fmt(young.avg, 1) + " avg",
      teamLink(young.tid), young.n + " aged picks"));
    if (old) bits.push(card("OLDEST TEAM", fmt(old.avg, 1) + " avg",
      teamLink(old.tid), old.n + " aged picks"));
    if (best) {
      const par = best.par;
      bits.push(card("BEST VALUE", par != null ? ((par >= 0 ? "+" : "") + fmt(par, 1) + " PAR") : "—",
        A.playerLink(best.pid, best.name, { year: pickYear(best) }),
        (best.pos || "") + " · " + tName(best.tid)));
    }
    if (worst) {
      const par = worst.par;
      bits.push(card("WORST REACH", par != null ? ((par >= 0 ? "+" : "") + fmt(par, 1) + " PAR") : "—",
        A.playerLink(worst.pid, worst.name, { year: pickYear(worst) }),
        (worst.pos || "") + " · " + tName(worst.tid)));
    }
    body.innerHTML = bits.join("");
  }

  function renderFgHeatmap(picks) {
    const el = document.getElementById("fg-heatmap");
    const tbl = document.getElementById("fg-heat-tbl");
    const sub = document.getElementById("fg-heat-sub");
    const tog = document.getElementById("fg-heat-toggle");
    if (!el || !tbl) return;
    const POS = ["QB", "RB", "WR", "TE", "K", "DST"];
    if (!picks.length) { el.hidden = true; return; }
    el.hidden = false;
    const anyAge = picks.some((p) => p.age != null);
    if (tog) {
      tog.hidden = !anyAge;
      tog.querySelectorAll("button[data-heat]").forEach((b) => {
        b.classList.toggle("on", b.dataset.heat === heatMode);
      });
      if (!tog.dataset.bound) {
        tog.dataset.bound = "1";
        tog.querySelectorAll("button[data-heat]").forEach((b) => {
          b.addEventListener("click", () => {
            heatMode = b.dataset.heat === "age" ? "age" : "picks";
            renderFgNav();
          });
        });
      }
    }
    if (!anyAge) heatMode = "picks";
    const by = {};
    picks.forEach((p) => {
      const tid = p.oid;
      const rec = by[tid] || (by[tid] = { tid, n: 0, ages: [], pos: {} });
      rec.n += 1;
      if (p.age != null) rec.ages.push(p.age);
      const pos = POS.includes(p.pos) ? p.pos : null;
      if (!pos) return;
      const cell = rec.pos[pos] || (rec.pos[pos] = { n: 0, ages: [] });
      cell.n += 1;
      if (p.age != null) cell.ages.push(p.age);
    });
    const rows = Object.values(by).sort((a, b) => tName(a.tid).localeCompare(tName(b.tid)));
    const mode = (heatMode === "age" && anyAge) ? "age" : "picks";
    if (sub) sub.textContent = mode === "age"
      ? "mean draft age · team × position · birth dates from player_bio"
      : "pick counts · team × position";
    let max = 0;
    rows.forEach((r) => {
      POS.forEach((pos) => {
        const c = r.pos[pos];
        if (!c) return;
        const v = mode === "age" ? (c.ages.length ? c.ages.reduce((a, b) => a + b, 0) / c.ages.length : 0) : c.n;
        if (v > max) max = v;
      });
    });
    const thead = tbl.tHead || tbl.createTHead();
    thead.innerHTML = `<tr><th></th>
      <th class="s" data-k="name">Team</th>
      ${POS.map((pos) => `<th class="s" data-k="${pos}">${pos}</th>`).join("")}
      <th class="s" data-k="total">${mode === "age" ? "Avg" : "Picks"}</th></tr>`;
    delete tbl.dataset.navSort;
    const tb = tbl.tBodies[0] || tbl.appendChild(document.createElement("tbody"));
    tb.innerHTML = rows.map((r, i) => {
      const tot = mode === "age"
        ? (r.ages.length ? r.ages.reduce((a, b) => a + b, 0) / r.ages.length : null)
        : r.n;
      const cells = POS.map((pos) => {
        const c = r.pos[pos];
        if (!c || !c.n) return `<td class="heat" data-sv="">—</td>`;
        const v = mode === "age"
          ? (c.ages.length ? c.ages.reduce((a, b) => a + b, 0) / c.ages.length : null)
          : c.n;
        const t = (v != null && max) ? Math.min(1, v / max) : 0;
        const bg = mode === "age"
          ? `rgba(255,122,0,${0.10 + t * 0.55})`
          : `rgba(47,123,255,${0.10 + t * 0.55})`;
        const label = v == null ? "—" : (mode === "age" ? fmt(v, 1) : String(c.n));
        return `<td class="heat" data-sv="${v == null ? "" : v}" style="background:${bg}">${label}</td>`;
      }).join("");
      return `<tr>
        <td><span class="rank-pill">${i + 1}</span></td>
        <td>${teamCell(r.tid)}</td>
        ${cells}
        <td data-sv="${tot == null ? "" : tot}"><strong>${tot == null ? "—" : (mode === "age" ? fmt(tot, 1) : tot)}</strong></td>
      </tr>`;
    }).join("");
    bindNavTableSort(tbl);
  }

  function groupStacks(picks, keyFn) {
    const bag = {};
    picks.forEach((p) => {
      const key = keyFn(p);
      if (!key) return;
      (bag[key] = bag[key] || { key, tid: p.oid, picks: [] }).picks.push(p);
    });
    return Object.values(bag).filter((g) => g.picks.length >= 2)
      .sort((a, b) => b.picks.length - a.picks.length || tName(a.tid).localeCompare(tName(b.tid)));
  }
  function stackCard(g, title, extra) {
    const n = g.picks.length;
    const lab = navStackLabel(n);
    return `<div class="fg-stack">
      <div class="fg-stack-top">
        <span class="fg-stack-tag">${lab}</span>
        <strong>${title}</strong>
        ${extra || ""}
      </div>
      <div class="own">${g.picks.map((p) =>
        A.playerLink(p.pid, p.name, { year: pickYear(p) }) + " <span class='badge pos-" + p.pos + "'>" + (p.pos || "") + "</span>"
      ).join(" · ")}</div>
    </div>`;
  }

  function renderFgStacks(picks) {
    const el = document.getElementById("fg-stacks");
    const body = document.getElementById("fg-stacks-body");
    const qbEl = document.getElementById("fg-qb-stacks");
    if (!el || !body) return;
    const groups = groupStacks(picks.filter((p) => p.nfl), (p) => p.oid + "|" + p.nfl);
    if (!groups.length) { el.hidden = true; body.innerHTML = ""; if (qbEl) qbEl.innerHTML = ""; return; }
    el.hidden = false;
    groups.forEach((g) => { g.nfl = g.picks[0].nfl; });
    body.innerHTML = groups.map((g) => stackCard(g,
      teamLink(g.tid) + " · " + (A.nflLogoHTML(g.nfl, "nfl-logo sm") + " " + g.nfl),
      `<span class="own">${g.picks.length} picks</span>`
    )).join("");
    const qb = groups.filter((g) => {
      const poss = new Set(g.picks.map((p) => p.pos));
      return poss.has("QB") && (poss.has("WR") || poss.has("TE"));
    });
    if (qbEl) {
      qbEl.innerHTML = qb.length
        ? `<h3>QB + pass-catcher</h3>` + qb.map((g) => stackCard(g,
            teamLink(g.tid) + " · " + g.nfl + " QB stack",
            `<span class="own">${g.picks.filter((p) => p.pos === "QB" || p.pos === "WR" || p.pos === "TE").length} connected</span>`
          )).join("")
        : "";
    }
  }

  function renderFgCollege(picks) {
    const el = document.getElementById("fg-college");
    const body = document.getElementById("fg-college-body");
    if (!el || !body) return;
    const groups = groupStacks(picks.filter((p) => p.college), (p) => p.oid + "|" + p.college);
    if (!groups.length) { el.hidden = true; body.innerHTML = ""; return; }
    el.hidden = false;
    groups.forEach((g) => { g.college = g.picks[0].college; });
    body.innerHTML = groups.map((g) => stackCard(g,
      teamLink(g.tid) + " · " + g.college,
      `<span class="own">${g.picks.length} from ${g.college}</span>`
    )).join("");
  }

  function renderFgHomers(picks) {
    const el = document.getElementById("fg-homers");
    const body = document.getElementById("fg-homers-body");
    const tog = document.getElementById("fg-homer-toggle");
    const sub = document.getElementById("fg-homers-sub");
    if (!el || !body) return;
    const groups = groupStacks(picks.filter((p) => p.nfl), (p) => p.oid + "|" + p.nfl);
    if (!groups.length) { el.hidden = true; body.innerHTML = ""; return; }
    el.hidden = false;
    groups.forEach((g) => { g.nfl = g.picks[0].nfl; });
    if (tog && !tog.dataset.bound) {
      tog.dataset.bound = "1";
      tog.querySelectorAll("button[data-homer]").forEach((b) => {
        b.addEventListener("click", () => {
          homerMode = b.dataset.homer === "nfl" ? "nfl" : "franchise";
          renderFgNav();
        });
      });
    }
    if (tog) {
      tog.querySelectorAll("button[data-homer]").forEach((b) => {
        b.classList.toggle("on", b.dataset.homer === homerMode);
      });
    }
    if (homerMode === "nfl") {
      if (sub) sub.textContent = "NFL team → AFFL franchises that took 2+";
      const byNfl = {};
      groups.forEach((g) => {
        (byNfl[g.nfl] = byNfl[g.nfl] || []).push(g);
      });
      body.innerHTML = Object.keys(byNfl).sort((a, b) => byNfl[b].length - byNfl[a].length || a.localeCompare(b))
        .map((nfl) => {
          const gs = byNfl[nfl];
          return `<div class="fg-homer-block">
            <h3>${A.nflLogoHTML(nfl, "nfl-logo sm")} ${nfl}</h3>
            ${gs.map((g) => stackCard(g, teamLink(g.tid), `<span class="own">${g.picks.length}</span>`)).join("")}
          </div>`;
        }).join("");
    } else {
      if (sub) sub.textContent = "franchise → NFL team concentrations · 2+ picks";
      const byFr = {};
      groups.forEach((g) => {
        (byFr[g.tid] = byFr[g.tid] || []).push(g);
      });
      body.innerHTML = Object.keys(byFr).sort((a, b) => tName(a).localeCompare(tName(b)))
        .map((tid) => `<div class="fg-homer-block">
          <h3>${teamLink(tid)}</h3>
          ${byFr[tid].map((g) => stackCard(g, A.nflLogoHTML(g.nfl, "nfl-logo sm") + " " + g.nfl,
            `<span class="own">${g.picks.length}</span>`)).join("")}
        </div>`).join("");
    }
  }

  function renderFgCuffs(picks) {
    const el = document.getElementById("fg-cuffs");
    const body = document.getElementById("fg-cuffs-body");
    if (!el || !body) return;
    const groups = groupStacks(
      picks.filter((p) => p.nfl && p.pos),
      (p) => p.oid + "|" + p.nfl + "|" + p.pos
    );
    if (!groups.length) { el.hidden = true; body.innerHTML = ""; return; }
    el.hidden = false;
    body.innerHTML = groups.map((g) => {
      const nfl = g.picks[0].nfl;
      const pos = g.picks[0].pos;
      return stackCard(g,
        teamLink(g.tid) + " · " + (A.nflLogoHTML(nfl, "nfl-logo sm") + " " + nfl) + " " + pos,
        `<span class="own">handcuff · ${g.picks.length}</span>`);
    }).join("");
  }

  function renderFgAgeScatter(picks) {
    const el = document.getElementById("fg-age-scatter");
    const canvas = document.getElementById("fg-age-chart");
    const sub = document.getElementById("fg-age-sub");
    if (!el || !canvas) return;
    const aged = picks.filter((p) => p.age != null);
    if (!aged.length) {
      el.hidden = true;
      if (fgAgeChart) { fgAgeChart.destroy(); fgAgeChart = null; }
      return;
    }
    el.hidden = false;
    if (sub) sub.textContent = "player age vs franchise · color by position · live age from player_bio birth dates";
    const POS = ["QB", "RB", "WR", "TE", "K", "DST"];
    const COLORS = { QB: C.blue, RB: C.green, WR: C.orange, TE: C.gold, K: C.ice, DST: C.steel };
    const teams = [...new Set(aged.map((p) => p.oid))].sort((a, b) => tName(a).localeCompare(tName(b)));
    const xOf = {};
    teams.forEach((tid, i) => { xOf[tid] = i + 1; });
    if (fgAgeChart) { fgAgeChart.destroy(); fgAgeChart = null; }
    fgAgeChart = new Chart(canvas, {
      type: "scatter",
      data: {
        datasets: POS.map((pos) => ({
          label: pos,
          data: aged.filter((p) => p.pos === pos).map((p) => ({
            x: xOf[p.oid], y: p.age, p: p,
          })),
          backgroundColor: COLORS[pos],
          borderColor: COLORS[pos],
          pointRadius: 5,
        })).filter((d) => d.data.length),
      },
      options: {
        maintainAspectRatio: false,
        plugins: {
          tooltip: { callbacks: {
            label: (c) => {
              const p = c.raw.p;
              return tName(p.oid) + " · " + p.name + " · " + p.pos + " · " + fmt(p.age, 1);
            },
          } },
        },
        scales: {
          x: {
            min: 0.5, max: teams.length + 0.5,
            ticks: {
              stepSize: 1,
              callback: (v) => teams[v - 1] ? short(teams[v - 1]) : "",
              maxRotation: 55, minRotation: 40,
            },
            grid: { color: C.grid }, border: { display: false },
            title: { display: true, text: "franchise" },
          },
          y: {
            grid: { color: C.grid }, border: { display: false },
            title: { display: true, text: "age" },
          },
        },
      },
    });
  }

  function renderFgNav() {
    const picks = navPicks();
    renderFgAwards(picks);
    renderFgHeatmap(picks);
    renderFgStacks(picks);
    renderFgCollege(picks);
    renderFgHomers(picks);
    renderFgCuffs(picks);
    renderFgAgeScatter(picks);
  }

  function renderBoard() {
    bindViewToggle();
    bindPosChips();
    bindBoardSort();
    markViewChips();
    const auction = YD.draft.auction;
    const yth = document.getElementById('year-th');
    if (yth) yth.hidden = scope !== 'cum';
    const costTh = document.getElementById('cost-th');
    if (costTh) costTh.textContent = auction ? 'Cost' : 'Pick';
    const all = navPicks();
    const rows = all.filter(navPass);
    const fn = BOARD_KEYS[boardKey] || BOARD_KEYS.overall;
    rows.sort((a, b) => {
      const av = fn(a), bv = fn(b);
      if (typeof av === "string") return av.localeCompare(bv) * boardDir;
      return ((av || 0) - (bv || 0)) * boardDir;
    });
    const withPts = scored();

    $('#board-sub').textContent =
      `${YD.draft.board.length} picks · ${auction ? 'auction' : 'snake'}` +
      (S.pos && S.pos !== "ALL" ? ` · ${S.pos}` : "") +
      (YD.hasRosters ? '' : ' · no scoring data stored for this season');

    const tableWrap = document.getElementById("board-table-wrap");
    const gridWrap = document.getElementById("board-grid-wrap");
    if (tableWrap) tableWrap.hidden = S.view === "board";
    if (gridWrap) gridWrap.hidden = S.view !== "board";

    const pidx = parIndex();
    const tb = document.querySelector('#board-tbl tbody');
    if (tb) {
      tb.innerHTML = rows.slice(0, S.limit).map((p) => {
        let badge = '<td class="own">—</td>';
        const par = p.par != null ? p.par : (p.year != null ? pidx[p.year + ':' + p.overall] : pidx[String(p.overall)]);
        if (par != null) {
          badge = `<td data-sv="${par}"><span class="badge ${par >= 0 ? 'steal' : 'bust'}">` +
                  `${par >= 0 ? '+' : ''}${fmt(par, 0)}</span></td>`;
        }
        const bio = withBio(p);
        return `<tr>
          ${scope === 'cum' ? `<td class="tnum" data-sv="${p.year || ""}">${p.year || ""}</td>` : ''}
          <td data-sv="${p.overall || 0}"><span class="rank-pill${p.overall === 1 ? ' gold' : ''}">${p.overall}</span></td>
          <td data-sv="${(p.name || "").toLowerCase()}"><strong>${A.playerLink(p.pid, p.name, { year: pickYear(p) })}</strong>${p.keeper ? ' <span class="badge">keeper</span>' : ''}</td>
          <td data-sv="${p.pos || ""}"><span class="badge pos-${p.pos}">${p.pos}</span></td>
          <td class="own" data-sv="${p.nfl || ""}">${A.nflLogoHTML(p.nfl, "nfl-logo sm")} ${p.nfl || "—"}</td>
          <td data-sv="${bio.age == null ? "" : bio.age}">${bio.age != null ? fmt(bio.age, 1) : "—"}</td>
          ${milesCell(p)}
          <td data-sv="${tName(p.tid).toLowerCase()}"><div class="team-cell">${A.logoHTML(teamOf(p.tid), 'mini')}<span>${teamLink(p.tid)}</span></div></td>
          <td data-sv="${p.bid || 0}"><strong>${(p.auction != null ? p.auction : auction) ? '$' + (p.bid || 0) : p.round + '.' + String(p.pick).padStart(2, '0')}</strong></td>
          <td data-sv="${p.pts == null ? "" : p.pts}">${p.pts != null ? fmt(p.pts, 1) : '—'}</td>
          ${badge}
        </tr>`;
      }).join('');
    }
    const more = document.getElementById('board-more');
    if (more) more.style.display = rows.length > S.limit ? 'block' : 'none';
    markBoardSort();
    renderNavBoard(all);
  }


  let labPos = "RB";
  let labRound = 1;

  function labNormPos(pos) {
    return pos === "D/ST" ? "DST" : pos;
  }
  function labParOf(p) {
    const idx = parIndex();
    if (!idx) return null;
    let v = null;
    if (p.year != null && idx[p.year + ":" + p.overall] != null) v = idx[p.year + ":" + p.overall];
    else if (idx[String(p.overall)] != null) v = idx[String(p.overall)];
    if (v == null || v === "") return null;
    const n = Number(v);
    return Number.isNaN(n) ? null : n;
  }
  function labHasPar() {
    const idx = parIndex();
    return !!(idx && Object.keys(idx).length);
  }
  function labAuction() {
    return !!(YD && YD.draft && YD.draft.auction);
  }
  function labCost(p) {
    return labAuction() ? ("$" + (p.bid || 0)) : ((p.round || 0) + "." + (p.pick || 0));
  }
  function labPickRows() {
    return ((YD && YD.draft && YD.draft.board) || []).map((p) => ({
      pid: p.pid, tid: p.tid, bid: p.bid || 0,
      round: p.round, pick: p.pick, overall: p.overall,
      name: p.name, pos: labNormPos(p.pos), nfl: p.nfl,
      pts: p.pts, keeper: p.keeper, par: labParOf(p),
    }));
  }
  function labParRows(rows) {
    return (rows || labPickRows()).filter((p) => p.par != null);
  }
  function labLetter(rank, n) {
    const SCALE = ["A+", "A", "A-", "B+", "B", "B-", "C+", "C", "C-", "D", "D-", "F"];
    if (n <= 1) return "A";
    const idx = Math.round((rank - 1) * (SCALE.length - 1) / Math.max(1, n - 1));
    return SCALE[Math.max(0, Math.min(SCALE.length - 1, idx))];
  }
  function labParChip(par) {
    if (par == null) return `<span class="badge">—</span>`;
    return `<span class="badge ${par >= 0 ? "steal" : "bust"}">${par >= 0 ? "+" : ""}${fmt(par, 0)}</span>`;
  }
  function labPlayerRow(p) {
    return `<tr>
      <td><strong>${A.playerLink(p.pid, p.name, { year })}</strong></td>
      <td><span class="badge pos-${p.pos}">${p.pos || "—"}</span></td>
      <td>${teamLink(p.tid)}</td>
      <td>${labCost(p)}</td>
      <td>${labParChip(p.par)}</td>
    </tr>`;
  }
  function labMini(p) {
    if (!p) return `<tr><td class="own" colspan="3">No PAR in this slice.</td></tr>`;
    return `<tr>
      <td><strong>${A.playerLink(p.pid, p.name, { year })}</strong>
        <div class="own">${tName(p.tid)} · ${labCost(p)}</div></td>
      <td><span class="badge pos-${p.pos}">${p.pos || "—"}</span></td>
      <td>${labParChip(p.par)}</td>
    </tr>`;
  }
  function labTeamRows(rows) {
    const by = {};
    labParRows(rows).forEach((p) => {
      const tid = ownerKey(p.tid);
      const r = by[tid] || (by[tid] = { tid, total: 0, picks: [] });
      r.total += p.par;
      r.picks.push(p);
    });
    const list = Object.values(by).sort((a, b) => b.total - a.total);
    list.forEach((r, i) => {
      r.rank = i + 1;
      r.grade = labLetter(r.rank, list.length);
      const ranked = r.picks.slice().sort((a, b) => b.par - a.par);
      r.steal = ranked[0] || null;
      r.reach = ranked.length ? ranked[ranked.length - 1] : null;
    });
    return list;
  }
  function labSlots(rows) {
    let m = 0;
    const tids = {};
    (rows || []).forEach((p) => {
      if ((p.pick || 0) > m) m = p.pick;
      tids[p.tid] = 1;
    });
    return Math.max(m, Object.keys(tids).length) || (year <= 2016 ? 10 : 12);
  }
  function labCol(p, slots, auction) {
    if (auction) return p.pick;
    if ((p.round || 1) % 2 === 1) return p.pick;
    return slots + 1 - p.pick;
  }
  function bindLabTabs(el, items, cur, onPick) {
    if (!el) return;
    el.innerHTML = items.map((it) => {
      const v = typeof it === "object" ? it.v : it;
      const l = typeof it === "object" ? it.l : it;
      return `<button type="button" class="season-chip${String(v) === String(cur) ? " on" : ""}" data-v="${v}">${l}</button>`;
    }).join("");
    el.querySelectorAll("button").forEach((b) => {
      b.addEventListener("click", () => onPick(b.dataset.v));
    });
  }
  function fillMini(sel, list) {
    const tb = document.querySelector(sel);
    if (!tb) return;
    const rows = (list || []).filter(Boolean);
    tb.innerHTML = rows.length ? rows.map(labMini).join("") : labMini(null);
  }

  function renderLab() {
    const empty = document.getElementById("lab-empty");
    const body = document.getElementById("lab-body");
    const sub = document.getElementById("lab-sub");
    if (!empty || !body) return;
    if (scope !== "season") {
      body.hidden = true;
      empty.hidden = false;
      empty.textContent = "Pick a season to open the Draft Lab.";
      if (sub) sub.textContent = "single-season view · pick a season";
      if (labChart) { labChart.destroy(); labChart = null; }
      return;
    }
    if (!labHasPar()) {
      body.hidden = true;
      empty.hidden = false;
      empty.textContent = "This season has no parByOverall — nothing to grade.";
      if (sub) sub.textContent = year + " · no PAR board in the year file";
      if (labChart) { labChart.destroy(); labChart = null; }
      return;
    }
    empty.hidden = true;
    body.hidden = false;
    const auction = labAuction();
    const rows = labPickRows();
    const scored = labParRows(rows);
    if (sub) {
      sub.textContent = year + " · " + (auction ? "auction" : "snake") +
        " · PAR from parByOverall · season points minus replacement at that position";
    }

    const avg = scored.length ? scored.reduce((a, p) => a + p.par, 0) / scored.length : null;
    const hit = scored.length ? scored.filter((p) => p.par > 0).length / scored.length : null;
    const teams = labTeamRows(rows);
    const span = teams.length ? teams[0].total - teams[teams.length - 1].total : null;
    const kpis = document.getElementById("lab-kpis");
    if (kpis) {
      const card = (n, title, desc) =>
        `<div class="card kpi"><div><div class="kpi-num">${n}</div>` +
        `<div class="kpi-title">${title}</div><div class="kpi-desc">${desc}</div></div></div>`;
      kpis.innerHTML = [
        card(avg == null ? "—" : ((avg >= 0 ? "+" : "") + fmt(avg, 1)), "Avg pick PAR",
          `<strong>${scored.length}</strong> graded picks · points above replacement`),
        card(hit == null ? "—" : (Math.round(hit * 100) + "%"), "Positive PAR",
          `<strong>${scored.filter((p) => p.par > 0).length}</strong> of ${scored.length} picks above replacement`),
        card(span == null ? "—" : fmt(span, 0), "Team-value range",
          teams.length
            ? `<strong>${tName(teams[0].tid)}</strong> ${fmt(teams[0].total, 0)} to <strong>${tName(teams[teams.length - 1].tid)}</strong> ${fmt(teams[teams.length - 1].total, 0)}`
            : "no team totals"),
        card(String(teams.length || "—"), "Teams graded",
          "total PAR of players they drafted · even if later traded"),
      ].join("");
    }

    const ranked = scored.slice().sort((a, b) => b.par - a.par);
    const bestTb = document.querySelector("#lab-best-tbl tbody");
    const worstTb = document.querySelector("#lab-worst-tbl tbody");
    if (bestTb) bestTb.innerHTML = ranked.slice(0, 5).map(labPlayerRow).join("") ||
      `<tr><td colspan="5" class="own">No PAR on this board.</td></tr>`;
    if (worstTb) worstTb.innerHTML = ranked.slice(-5).reverse().map(labPlayerRow).join("") ||
      `<tr><td colspan="5" class="own">No PAR on this board.</td></tr>`;

    const POS = ["QB", "RB", "WR", "TE", "K", "DST"];
    if (!POS.includes(labPos)) labPos = "RB";
    bindLabTabs(document.getElementById("lab-pos-tabs"), POS, labPos, (v) => {
      labPos = v; renderLab();
    });
    const posAll = rows.filter((p) => p.pos === labPos);
    const posHit = labParRows(posAll);
    const posMeta = document.getElementById("lab-pos-meta");
    if (posMeta) {
      const avgPar = posHit.length ? posHit.reduce((a, p) => a + p.par, 0) / posHit.length : null;
      const avgCost = posAll.length
        ? (auction
            ? posAll.reduce((a, p) => a + (p.bid || 0), 0) / posAll.length
            : posAll.reduce((a, p) => a + (p.round || 0), 0) / posAll.length)
        : null;
      posMeta.innerHTML = `<strong>${posAll.length}</strong> ${labPos}` +
        ` · avg PAR ${avgPar == null ? "—" : ((avgPar >= 0 ? "+" : "") + fmt(avgPar, 1))}` +
        (auction
          ? ` · avg $ ${avgCost == null ? "—" : fmt(avgCost, 1)}`
          : ` · avg round ${avgCost == null ? "—" : fmt(avgCost, 1)}`);
    }
    const posRank = posHit.slice().sort((a, b) => b.par - a.par);
    fillMini("#lab-pos-top tbody", posRank.slice(0, 3));
    fillMini("#lab-pos-worst tbody", posRank.slice(-3).reverse());

    const rounds = [...new Set(rows.map((p) => p.round).filter((r) => r != null))].sort((a, b) => a - b);
    if (!rounds.includes(Number(labRound))) labRound = rounds[0] || 1;
    labRound = Number(labRound);
    bindLabTabs(document.getElementById("lab-round-tabs"),
      rounds.map((r) => ({ v: r, l: "R" + r })), labRound, (v) => {
        labRound = +v; renderLab();
      });
    const rndAll = rows.filter((p) => p.round === labRound);
    const rndHit = labParRows(rndAll);
    const rndMeta = document.getElementById("lab-round-meta");
    if (rndMeta) {
      const avgPar = rndHit.length ? rndHit.reduce((a, p) => a + p.par, 0) / rndHit.length : null;
      rndMeta.innerHTML = `<strong>Round ${labRound}</strong> · ${rndAll.length} picks` +
        ` · avg PAR ${avgPar == null ? "—" : ((avgPar >= 0 ? "+" : "") + fmt(avgPar, 1))}`;
    }
    const rndRank = rndHit.slice().sort((a, b) => b.par - a.par);
    fillMini("#lab-round-top tbody", rndRank.slice(0, 3));
    fillMini("#lab-round-worst tbody", rndRank.slice(-3).reverse());

    const byRound = {};
    scored.forEach((p) => {
      if (p.round == null) return;
      (byRound[p.round] = byRound[p.round] || []).push(p.par);
    });
    const rLabels = Object.keys(byRound).map(Number).sort((a, b) => a - b);
    const rMeans = rLabels.map((r) => {
      const a = byRound[r];
      return a.reduce((x, y) => x + y, 0) / a.length;
    });
    if (labChart) { labChart.destroy(); labChart = null; }
    const canvas = document.getElementById("lab-round-chart");
    if (canvas && rLabels.length) {
      labChart = new Chart(canvas, {
        type: "bar",
        data: {
          labels: rLabels.map((r) => "R" + r),
          datasets: [{
            label: "Mean PAR by round",
            data: rMeans,
            backgroundColor: rMeans.map((v) => v >= 0 ? C.green : C.fire),
            maxBarThickness: 28,
          }],
        },
        options: {
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
            tooltip: { callbacks: { label: (c) => "Mean PAR " + fmt(c.parsed.y, 1) } },
          },
          scales: {
            y: { grid: { color: C.grid }, border: { display: false },
                 title: { display: true, text: "mean PAR" } },
            x: { grid: { display: false }, border: { display: false } },
          },
        },
      });
    }

    const gtb = document.querySelector("#lab-grades-tbl tbody");
    if (gtb) {
      gtb.innerHTML = teams.map((r) => {
        const pill = r.rank === 1 ? "gold" : r.rank === 2 ? "slv" : r.rank === 3 ? "brz" : "";
        const steal = r.steal
          ? `${A.playerLink(r.steal.pid, r.steal.name, { year })} ${labParChip(r.steal.par)}`
          : "—";
        const reach = r.reach
          ? `${A.playerLink(r.reach.pid, r.reach.name, { year })} ${labParChip(r.reach.par)}`
          : "—";
        return `<tr>
          <td><span class="rank-pill ${pill}">${r.rank}</span></td>
          <td><span class="lab-grade lab-g-${(r.grade || "C")[0]}">${r.grade}</span></td>
          <td>${teamCell(r.tid)}</td>
          <td class="${r.total >= 0 ? "pos" : "neg"}"><strong>${r.total >= 0 ? "+" : ""}${fmt(r.total, 1)}</strong></td>
          <td>${steal}</td>
          <td>${reach}</td>
        </tr>`;
      }).join("") || `<tr><td colspan="6" class="own">No team PAR to grade.</td></tr>`;
    }

    const slots = labSlots(rows);
    const maxRound = rounds.length ? rounds[rounds.length - 1] : 0;
    const boardSub = document.getElementById("lab-board-sub");
    if (boardSub) {
      boardSub.textContent = auction
        ? year + " · auction nomination order · " + maxRound + " rounds × " + slots + " slots"
        : year + " · snake draft slots 1–" + slots + " · " + maxRound + " rounds";
    }
    const grid = document.getElementById("lab-board");
    if (grid) {
      const byKey = {};
      rows.forEach((p) => {
        const col = labCol(p, slots, auction);
        byKey[p.round + ":" + col] = p;
      });
      const headers = [];
      for (let s = 1; s <= slots; s++) {
        if (auction) {
          headers.push(`<div class="lab-board-h">${s}</div>`);
        } else {
          const first = rows.find((p) => p.round === 1 && p.pick === s);
          headers.push(`<div class="lab-board-h">${first ? short(first.tid) : s}</div>`);
        }
      }
      const cells = [`<div class="lab-board-r"></div>`, ...headers];
      for (let r = 1; r <= maxRound; r++) {
        cells.push(`<div class="lab-board-r">R${r}</div>`);
        for (let s = 1; s <= slots; s++) {
          const p = byKey[r + ":" + s];
          if (!p) {
            cells.push(`<div class="lab-board-cell empty"></div>`);
            continue;
          }
          cells.push(`<div class="lab-board-cell pos-${p.pos || ""}">
            <div class="lab-board-name">${A.playerLink(p.pid, p.name, { year })}</div>
            <div class="lab-board-meta">
              <span>${p.pos || "—"} · ${labCost(p)}</span>
              ${labParChip(p.par)}
            </div>
          </div>`);
        }
      }
      grid.style.setProperty("--slots", String(slots));
      grid.style.gridTemplateColumns = `36px repeat(${slots}, minmax(88px, 1fr))`;
      grid.innerHTML = cells.join("");
    }
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

  function holdoutHasPar(block) {
    if (!block) return false;
    const mekko = block.mekko || [];
    const scatter = block.scatter || [];
    return mekko.length > 0 || scatter.length > 0;
  }

  function holdoutEmptyMessage() {
    if (scope === "season" && YD && YD.draft && !YD.draft.auction) {
      return year + " is a snake draft (no auction bids)";
    }
    return "No auction PAR in this slice.";
  }

  function holdoutSliceEmpty(block) {
    if (scope === "season" && YD && YD.draft && !YD.draft.auction) return true;
    if (scope === "season" && !(HOLDOUT.scoredAuctionSeasons || []).includes(year)) return true;
    return !holdoutHasPar(block);
  }

  function hideHoldoutWrap(el, hide) {
    if (!el) return;
    el.hidden = !!hide;
    if (hide) {
      el.style.display = "none";
      el.style.height = "0";
      el.style.minHeight = "0";
      el.style.overflow = "hidden";
    } else {
      el.style.display = "";
      el.style.height = "";
      el.style.minHeight = "";
      el.style.overflow = "";
    }
  }

  function destroyHoldoutCharts() {
    if (scatterChart) { scatterChart.destroy(); scatterChart = null; }
    if (contChart) { contChart.destroy(); contChart = null; }
  }

  function setHoldoutEmpty(empty, msg) {
    destroyHoldoutCharts();
    const emptyEl = $("#holdout-empty");
    if (emptyEl) {
      if (empty) {
        emptyEl.hidden = false;
        emptyEl.style.display = "";
        emptyEl.style.height = "";
        emptyEl.style.minHeight = "";
        emptyEl.innerHTML = A.notice(msg || holdoutEmptyMessage());
      } else {
        emptyEl.hidden = true;
        emptyEl.innerHTML = "";
        emptyEl.style.display = "none";
        emptyEl.style.height = "0";
        emptyEl.style.minHeight = "0";
      }
    }
    hideHoldoutWrap($("#holdout-viz"), empty);
    hideHoldoutWrap($("#holdout-mekko-col"), empty);
    hideHoldoutWrap($("#holdout-early-col"), empty);
    hideHoldoutWrap($("#mekko"), empty);
    hideHoldoutWrap($("#holdout-scatter-wrap"), empty);
    hideHoldoutWrap(document.querySelector(".holdout-continuous"), empty);
    const canvas = $("#holdout-scatter");
    if (canvas) {
      canvas.hidden = !!empty;
      if (empty) {
        canvas.style.display = "none";
        canvas.style.height = "0";
        canvas.style.minHeight = "0";
      } else {
        canvas.style.display = "";
        canvas.style.height = "";
        canvas.style.minHeight = "";
      }
    }
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
      el.innerHTML = "";
      return;
    }
    const W = el.clientWidth || 560, H = el.clientHeight || 340;
    const pad = { t: 10, r: 8, b: 28, l: 32 };
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
      ${[0, 0.5, 1].map((t) => {
        const y = pad.t + innerH * (1 - t);
        const val = Math.round(maxN * t);
        return `<line x1="${pad.l}" x2="${W - pad.r}" y1="${y}" y2="${y}" stroke="${C.grid}"/>
          <text x="${pad.l - 6}" y="${y + 3}" text-anchor="end" fill="${C.mut}" font-size="9">${val}</text>`;
      }).join('')}
      ${rects.map((r, i) => `<rect data-i="${i}" x="${r.x}" y="${r.y}" width="${r.w}" height="${Math.max(1, r.h)}"
        fill="${S.mekkoStack === 'pos' ? (POS_FILL[r.key] || C.steel) : parColor(r.meanPar)}"
        stroke="#05060b" stroke-width="1" opacity="0.92"/>`).join('')}
      ${cols.map((b) => {
        const cx = b.x + b.w / 2;
        const id = `<text x="${cx}" y="${H - 8}" text-anchor="middle" fill="${C.ink}" font-size="10" font-weight="700">${b.id}</text>`;
        const pct = b.w >= 52
          ? `<text x="${cx}" y="${H - 20}" text-anchor="middle" fill="${C.mut}" font-size="9">${fmt((b.spendShare || 0) * 100, 0)}%</text>`
          : "";
        return pct + id;
      }).join('')}
    </svg>`;
    el.querySelectorAll('rect[data-i]').forEach((node) => {
      const r = rects[+node.dataset.i];
      node.addEventListener('mousemove', (ev) => showTip(sliceTip(r.bucket, r.key, r), ev));
      node.addEventListener('mouseleave', hideTip);
    });
  }

  function renderScatter(block) {
    const rows = block.scatter || [];
    if (scatterChart) { scatterChart.destroy(); scatterChart = null; }
    const canvas = $('#holdout-scatter');
    if (!canvas || canvas.hidden || !rows.length) return;
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
    if (!canvas || canvas.hidden || !rows.length) return;
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
    if (!$('#holdout-title') || !HOLDOUT) return;
    const scored = (HOLDOUT.scoredAuctionSeasons || []).includes(year);
    const canSeason = scored && HOLDOUT.bySeason[String(year)];
    if (!canSeason) S.holdoutScope = 'pooled';

    $('#holdout-scope').innerHTML = [
      ['pooled', 'All scored auction years'],
      canSeason ? ['season', String(year)] : null,
    ].filter(Boolean).map(([id, lab]) =>
      `<button class="filter-chip${S.holdoutScope === id ? ' on' : ''}" data-scope="${id}">${lab}</button>`
    ).join('');
    const block = holdoutBlock();
    const showStack = !holdoutSliceEmpty(block);
    $('#holdout-stack').innerHTML = showStack ? [
      ['half', 'Stack: early / late'],
      ['pos', 'Stack: position'],
    ].map(([id, lab]) =>
      `<button class="filter-chip${S.mekkoStack === id ? ' on' : ''}" data-stack="${id}">${lab}</button>`
    ).join('') : '';

    const claim = S.holdoutScope === 'pooled'
      ? HOLDOUT.claim
      : (block.claim ? `${block.claim} (${year} auction, non-keepers).` : HOLDOUT.claim);
    $('#holdout-title').textContent = (claim || '').split(':')[0] || 'Auction holdouts';
    const claimEl = $('#holdout-claim');
    if (claimEl) {
      claimEl.textContent = claim || '';
      hideHoldoutWrap(claimEl, !claim);
    }
    $('#holdout-sub').textContent = S.holdoutScope === 'pooled'
      ? HOLDOUT.subtitle
      : `${year} auction player-seasons · width = share of that draft's spend · stacks = ${S.mekkoStack === 'pos' ? 'position' : 'early/late nomination half'} · color = mean PAR`;

    const notes = [];
    if (scope === "season" && YD && YD.draft && !YD.draft.auction) {
      notes.push(`${year} is a snake draft (no auction bids). Charts stay on 2018–2025 auction seasons.`);
    } else if (scope === "season" && !scored) {
      notes.push(`${year} is auction but ESPN stored no weekly scoring, so PAR is blank. Charts stay on scored auction years.`);
    }
    if (HOLDOUT.keepers && HOLDOUT.keepers.note) notes.push(HOLDOUT.keepers.note);
    if (HOLDOUT.histogramNote) notes.push(HOLDOUT.histogramNote);
    const grain = String(HOLDOUT.grain || "").trim();
    if (grain) notes.push("Grain: " + grain + ".");
    notes.push("Metric is PAR from v_draft_value — not WARP.");
    $('#holdout-note').innerHTML = notes.filter(Boolean).join(" ");

    if (holdoutSliceEmpty(block)) {
      setHoldoutEmpty(true, holdoutEmptyMessage());
      return;
    }
    setHoldoutEmpty(false);
    renderMekko(block);
    renderScatter(block);
    renderContinuous(block);
  }

  async function pick(y) {
    year = y;
    const seasonYear = scope === "cum" ? null : year;
    if (seasonYear != null && squad && !A.franchisePlayedSeason(squad, seasonYear)) {
      squad = "";
      A.stampNav("");
    }
    if (squad) year = A.clampYear(year, squad);
    S.limit = 60;
    const ylist = squad ? A.squadYears(squad) : A.years();
    A.showYearRow(true);
    A.remountTeamSelect(document.getElementById('squad-picker'), squad, (s) => {
      squad = s || "";
      A.stampNav(squad);
      if (squad && scope === "season") {
        const next = A.clampYear(year, squad);
        if (next == null) { scope = "cum"; year = A.years()[0]; }
        else year = next;
      }
      pick(year);
    }, scope === "cum" ? null : year);
    A.stampNav(squad);
    A.seasonSelect($('#year-picker'), scope === "cum" ? null : year, (y) => {
      if (y == null) { scope = "cum"; pick(A.years()[0]); }
      else { scope = "season"; pick(y); }
    }, ylist);
    if (scope === 'cum') {
      ALL = ALL || await A.loadAllYears();
      YD = mergeDraft(ALL);
      T = A.ownerTeams();
      $('#page-sub').textContent = `All · ${YD.draft.board.length} picks`;
    } else {
      YD = await A.loadYear(year);
      T = A.teams(year);
      $('#page-sub').textContent = `${year} · ${YD.draft.auction ? 'auction' : 'snake'} draft · ${YD.draft.board.length} picks`;
    }
    renderKPIs(); renderSpend(); renderValue(); renderLab(); renderOverview(); renderRecap(); renderPosPPD(); renderAuctionDNA(); renderCustody(); renderW1(); renderAge(); renderBoard(); renderFgNav(); renderGuide(); renderHoldout();
  }


  const OV_POS = ["QB", "RB", "WR", "TE", "K", "DST"];
  const OV_POS_COLORS = { QB: C.blue, RB: C.green, WR: C.orange, TE: C.gold, K: C.ice, DST: C.steel };
  let ovPos = "RB";
  let ovScatterPos = "ALL";

  function ovKill(chartRef, setter) {
    if (chartRef) chartRef.destroy();
    setter(null);
  }
  function ovCost(p) {
    return p.auction ? ("$" + (p.bid || 0)) : ((p.round || 0) + "." + String(p.pick || 0).padStart(2, "0"));
  }
  function ovSeasonRank(y, oid) {
    const teams = A.teams(y) || {};
    const list = Object.values(teams);
    for (let i = 0; i < list.length; i++) {
      if (A.canon(list[i].owner) === oid) return list[i].finalRank != null ? list[i].finalRank : null;
    }
    return null;
  }
  function ovCollect() {
    const out = [];
    (ALL || []).forEach(({ year: y, data }) => {
      const board = (data && data.draft && data.draft.board) || [];
      const par = (data && data.draftValue && data.draftValue.parByOverall) || {};
      const auction = !!(data && data.draft && data.draft.auction);
      const teams = A.teams(y) || {};
      board.forEach((p) => {
        const raw = par[String(p.overall)];
        if (raw == null || raw === "") return;
        const n = Number(raw);
        if (Number.isNaN(n)) return;
        const t = teams[p.tid] || teams[String(p.tid)] || {};
        const oid = A.canon(t.owner || A.ownerId(y, p.tid) || ("t" + p.tid));
        out.push({
          year: y, pid: p.pid, name: p.name, pos: labNormPos(p.pos),
          nfl: p.nfl, tid: oid, bid: p.bid || 0, round: p.round,
          pick: p.pick, overall: p.overall, auction: auction, par: n,
          rank: ovSeasonRank(y, oid),
        });
      });
    });
    return out;
  }
  function ovMean(arr) {
    return arr.length ? arr.reduce((a, b) => a + b, 0) / arr.length : null;
  }
  function ovParChip(par) {
    if (par == null) return `<span class="badge">—</span>`;
    return `<span class="badge ${par >= 0 ? "steal" : "bust"}">${par >= 0 ? "+" : ""}${fmt(par, 1)}</span>`;
  }
  function ovPlayerCell(p) {
    return `<strong>${A.playerLink(p.pid, p.name, { year: p.year })}</strong>`;
  }

  function renderOverview() {
    const el = document.getElementById("draft-overview");
    const body = document.getElementById("ov-body");
    const empty = document.getElementById("ov-empty");
    if (!el || !body) return;
    if (scope !== "cum") {
      el.hidden = true;
      if (ovYearChart) { ovYearChart.destroy(); ovYearChart = null; }
      if (ovTeamPosChart) { ovTeamPosChart.destroy(); ovTeamPosChart = null; }
      if (ovScatterChart) { ovScatterChart.destroy(); ovScatterChart = null; }
      return;
    }
    el.hidden = false;
    const picks = ovCollect();
    if (!picks.length) {
      body.hidden = true;
      if (empty) { empty.hidden = false; empty.textContent = "No parByOverall across loaded years."; }
      return;
    }
    body.hidden = false;
    if (empty) empty.hidden = true;

    const years = [...new Set(picks.map((p) => p.year))].sort((a, b) => a - b);
    const teamSeasons = {};
    const seasonTot = {};
    picks.forEach((p) => {
      const k = p.year + ":" + p.tid;
      teamSeasons[k] = (teamSeasons[k] || 0) + p.par;
      seasonTot[p.year] = (seasonTot[p.year] || 0) + p.par;
    });
    const avgPick = ovMean(picks.map((p) => p.par));
    const avgTeamSeason = ovMean(Object.values(teamSeasons));
    const avgSeason = ovMean(Object.values(seasonTot));
    const kpis = document.getElementById("ov-kpis");
    if (kpis) {
      const card = (n, title, desc) =>
        `<div class="card kpi"><div><div class="kpi-num">${n}</div>` +
        `<div class="kpi-title">${title}</div><div class="kpi-desc">${desc}</div></div></div>`;
      kpis.innerHTML = [
        card(avgPick == null ? "—" : ((avgPick >= 0 ? "+" : "") + fmt(avgPick, 1)), "Avg pick PAR",
          `<strong>${picks.length}</strong> graded picks · points above replacement`),
        card(avgTeamSeason == null ? "—" : ((avgTeamSeason >= 0 ? "+" : "") + fmt(avgTeamSeason, 1)), "Avg team-season PAR",
          `<strong>${Object.keys(teamSeasons).length}</strong> franchise-seasons · sum of that team's pick PAR`),
        card(avgSeason == null ? "—" : ((avgSeason >= 0 ? "+" : "") + fmt(avgSeason, 1)), "Avg season total PAR",
          `<strong>${years.length}</strong> seasons · league sum of pick PAR`),
      ].join("");
    }
    const sub = document.getElementById("ov-sub");
    if (sub) sub.textContent = "all-time PAR · " + years[0] + "–" + years[years.length - 1] +
      " · points above replacement · current franchise names";

    const byYearPos = {};
    const byYearPars = {};
    years.forEach((y) => { byYearPos[y] = {}; byYearPars[y] = []; });
    picks.forEach((p) => {
      const pos = OV_POS.includes(p.pos) ? p.pos : null;
      if (pos) byYearPos[p.year][pos] = (byYearPos[p.year][pos] || 0) + p.par;
      byYearPars[p.year].push(p.par);
    });
    if (ovYearChart) { ovYearChart.destroy(); ovYearChart = null; }
    const yCanvas = document.getElementById("ov-year-chart");
    if (yCanvas) {
      ovYearChart = new Chart(yCanvas, {
        data: {
          labels: years.map(String),
          datasets: [
            ...OV_POS.map((pos) => ({
              type: "bar", label: pos, stack: "par", yAxisID: "y",
              data: years.map((y) => byYearPos[y][pos] || 0),
              backgroundColor: OV_POS_COLORS[pos], maxBarThickness: 28, order: 2,
            })),
            {
              type: "line", label: "Mean PAR / pick", yAxisID: "y1",
              data: years.map((y) => ovMean(byYearPars[y])),
              borderColor: C.green, backgroundColor: C.green, borderWidth: 2,
              pointRadius: 3, pointBackgroundColor: C.green, tension: 0.2, order: 1,
            },
          ],
        },
        options: {
          maintainAspectRatio: false,
          interaction: { mode: "index", intersect: false },
          plugins: { legend: { labels: { boxWidth: 10, boxHeight: 10, usePointStyle: true, pointStyle: "circle" } } },
          scales: {
            y: { stacked: true, grid: { color: C.grid }, border: { display: false },
                 title: { display: true, text: "total PAR" } },
            y1: { position: "right", grid: { display: false }, border: { display: false },
                  title: { display: true, text: "mean PAR / pick" } },
            x: { stacked: true, grid: { display: false }, border: { display: false } },
          },
        },
      });
    }

    const ranked = picks.slice().sort((a, b) => b.par - a.par);
    const pickRow = (p) => `<tr>
      <td>${ovPlayerCell(p)}</td>
      <td><span class="badge pos-${p.pos}">${p.pos || "—"}</span></td>
      <td>${p.year}</td>
      <td>${ovCost(p)}</td>
      <td>${teamLink(p.tid)}</td>
      <td>${ovParChip(p.par)}</td>
    </tr>`;
    const topTb = document.querySelector("#ov-top-tbl tbody");
    const worstTb = document.querySelector("#ov-worst-tbl tbody");
    if (topTb) topTb.innerHTML = ranked.slice(0, 8).map(pickRow).join("");
    if (worstTb) worstTb.innerHTML = ranked.slice(-8).reverse().map(pickRow).join("");

    const byFr = {};
    picks.forEach((p) => {
      const r = byFr[p.tid] || (byFr[p.tid] = { tid: p.tid, total: 0, n: 0, pos: {} });
      r.total += p.par;
      r.n += 1;
      const pos = OV_POS.includes(p.pos) ? p.pos : null;
      if (pos) r.pos[pos] = (r.pos[pos] || 0) + p.par;
    });
    const frRows = Object.values(byFr).map((r) => {
      r.mean = r.n ? r.total / r.n : 0;
      return r;
    }).sort((a, b) => b.mean - a.mean);
    const frTb = document.querySelector("#ov-franchise-tbl tbody");
    if (frTb) {
      frTb.innerHTML = frRows.map((r, i) => {
        const rank = i + 1;
        const pill = rank === 1 ? "gold" : rank === 2 ? "slv" : rank === 3 ? "brz" : "";
        return `<tr>
          <td><span class="rank-pill ${pill}">${rank}</span></td>
          <td>${teamCell(r.tid)}</td>
          <td class="${r.mean >= 0 ? "pos" : "neg"}"><strong>${r.mean >= 0 ? "+" : ""}${fmt(r.mean, 1)}</strong></td>
          <td class="${r.total >= 0 ? "pos" : "neg"}">${r.total >= 0 ? "+" : ""}${fmt(r.total, 1)}</td>
          <td>${r.n}</td>
        </tr>`;
      }).join("");
    }

    const posSorted = frRows.slice().sort((a, b) => b.total - a.total);
    if (ovTeamPosChart) { ovTeamPosChart.destroy(); ovTeamPosChart = null; }
    const tpCanvas = document.getElementById("ov-team-pos-chart");
    if (tpCanvas) {
      ovTeamPosChart = new Chart(tpCanvas, {
        type: "bar",
        data: {
          labels: posSorted.map((r) => short(r.tid)),
          datasets: OV_POS.map((pos) => ({
            label: pos, stack: "par",
            data: posSorted.map((r) => r.pos[pos] || 0),
            backgroundColor: OV_POS_COLORS[pos], maxBarThickness: 18,
          })),
        },
        options: {
          indexAxis: "y",
          maintainAspectRatio: false,
          plugins: { legend: { labels: { boxWidth: 10, boxHeight: 10, usePointStyle: true, pointStyle: "circle" } } },
          scales: {
            x: { stacked: true, grid: { color: C.grid }, border: { display: false },
                 title: { display: true, text: "total PAR" } },
            y: { stacked: true, grid: { display: false }, border: { display: false } },
          },
        },
      });
    }
    const tpTb = document.querySelector("#ov-team-pos-tbl tbody");
    if (tpTb) {
      tpTb.innerHTML = posSorted.map((r, i) => {
        const rank = i + 1;
        const pill = rank === 1 ? "gold" : rank === 2 ? "slv" : rank === 3 ? "brz" : "";
        const cell = (pos) => {
          const v = r.pos[pos] || 0;
          return `<td class="${v >= 0 ? "pos" : "neg"}">${v >= 0 ? "+" : ""}${fmt(v, 0)}</td>`;
        };
        return `<tr>
          <td><span class="rank-pill ${pill}">${rank}</span></td>
          <td>${teamCell(r.tid)}</td>
          ${OV_POS.map(cell).join("")}
          <td class="${r.total >= 0 ? "pos" : "neg"}"><strong>${r.total >= 0 ? "+" : ""}${fmt(r.total, 0)}</strong></td>
        </tr>`;
      }).join("");
    }

    const scatterItems = ["ALL"].concat(OV_POS);
    if (!scatterItems.includes(ovScatterPos)) ovScatterPos = "ALL";
    bindLabTabs(document.getElementById("ov-scatter-pos"),
      scatterItems.map((v) => ({ v: v, l: v === "ALL" ? "All" : v })), ovScatterPos, (v) => {
        ovScatterPos = v; renderOverview();
      });
    const scatterPts = [];
    const tsKey = {};
    picks.forEach((p) => {
      if (ovScatterPos !== "ALL" && p.pos !== ovScatterPos) return;
      const k = p.year + ":" + p.tid;
      const rec = tsKey[k] || (tsKey[k] = { year: p.year, tid: p.tid, par: 0, rank: p.rank });
      rec.par += p.par;
      if (rec.rank == null) rec.rank = p.rank;
    });
    Object.values(tsKey).forEach((r) => {
      if (r.rank == null) return;
      scatterPts.push(r);
    });
    if (ovScatterChart) { ovScatterChart.destroy(); ovScatterChart = null; }
    const scCanvas = document.getElementById("ov-scatter");
    if (scCanvas) {
      ovScatterChart = new Chart(scCanvas, {
        type: "scatter",
        data: {
          datasets: [{
            label: ovScatterPos === "ALL" ? "Draft PAR vs final rank" : ovScatterPos + " PAR vs final rank",
            data: scatterPts.map((r) => ({ x: r.par, y: r.rank, r: r })),
            backgroundColor: C.blue + "cc",
            borderColor: C.blue,
            pointRadius: 4,
          }],
        },
        options: {
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
            tooltip: { callbacks: {
              label: (c) => {
                const r = scatterPts[c.dataIndex];
                return tName(r.tid) + " · " + r.year + " · PAR " + fmt(r.par, 1) + " · rank " + r.rank;
              },
            } },
          },
          scales: {
            x: { grid: { color: C.grid }, border: { display: false },
                 title: { display: true, text: ovScatterPos === "ALL" ? "team draft PAR" : ovScatterPos + " draft PAR" } },
            y: { reverse: true, grid: { color: C.grid }, border: { display: false },
                 title: { display: true, text: "final rank (1 at top)" }, ticks: { stepSize: 1 } },
          },
        },
      });
    }

    const byPlayer = {};
    picks.forEach((p) => {
      const id = p.pid != null ? String(p.pid) : ("n:" + p.name);
      const r = byPlayer[id] || (byPlayer[id] = { pid: p.pid, name: p.name, n: 0, par: 0, year: p.year });
      r.n += 1;
      r.par += p.par;
      r.name = p.name;
      r.year = p.year;
    });
    const mostN = Object.values(byPlayer).sort((a, b) => b.n - a.n || b.par - a.par).slice(0, 8);
    const mostPar = Object.values(byPlayer).sort((a, b) => b.par - a.par).slice(0, 8);
    const seenP = {};
    const playerLeaders = [];
    mostN.concat(mostPar).forEach((r) => {
      const k = String(r.pid != null ? r.pid : r.name);
      if (seenP[k]) return;
      seenP[k] = 1;
      playerLeaders.push(r);
    });
    playerLeaders.sort((a, b) => b.n - a.n || b.par - a.par);
    const plTb = document.querySelector("#ov-player-tbl tbody");
    if (plTb) {
      plTb.innerHTML = playerLeaders.slice(0, 10).map((r) => `<tr>
        <td><strong>${A.playerLink(r.pid, r.name, { year: r.year })}</strong></td>
        <td>${r.n}</td>
        <td class="${r.par >= 0 ? "pos" : "neg"}">${r.par >= 0 ? "+" : ""}${fmt(r.par, 1)}</td>
      </tr>`).join("");
    }
    const byNfl = {};
    picks.forEach((p) => {
      if (!p.nfl) return;
      const r = byNfl[p.nfl] || (byNfl[p.nfl] = { nfl: p.nfl, n: 0, par: 0 });
      r.n += 1;
      r.par += p.par;
    });
    const nflN = Object.values(byNfl).sort((a, b) => b.n - a.n || b.par - a.par);
    const nflPar = Object.values(byNfl).sort((a, b) => b.par - a.par);
    const seenN = {};
    const nflLeaders = [];
    nflN.slice(0, 8).concat(nflPar.slice(0, 8)).forEach((r) => {
      if (seenN[r.nfl]) return;
      seenN[r.nfl] = 1;
      nflLeaders.push(r);
    });
    nflLeaders.sort((a, b) => b.n - a.n || b.par - a.par);
    const nflTb = document.querySelector("#ov-nfl-tbl tbody");
    if (nflTb) {
      nflTb.innerHTML = nflLeaders.slice(0, 10).map((r) => `<tr>
        <td>${A.nflLogoHTML(r.nfl, "nfl-logo sm")} ${r.nfl}</td>
        <td>${r.n}</td>
        <td class="${r.par >= 0 ? "pos" : "neg"}">${r.par >= 0 ? "+" : ""}${fmt(r.par, 1)}</td>
      </tr>`).join("");
    }

    if (!OV_POS.includes(ovPos)) ovPos = "RB";
    bindLabTabs(document.getElementById("ov-pos-tabs"), OV_POS, ovPos, (v) => {
      ovPos = v; renderOverview();
    });
    const posPicks = picks.filter((p) => p.pos === ovPos);
    const posMeta = document.getElementById("ov-pos-meta");
    if (posMeta) {
      const avgPar = ovMean(posPicks.map((p) => p.par));
      const auc = posPicks.filter((p) => p.auction);
      const snake = posPicks.filter((p) => !p.auction);
      const avgDol = auc.length ? ovMean(auc.map((p) => p.bid || 0)) : null;
      const avgRnd = snake.length ? ovMean(snake.map((p) => p.round || 0)) : null;
      posMeta.innerHTML = `<strong>${posPicks.length}</strong> ${ovPos}` +
        ` · avg PAR ${avgPar == null ? "—" : ((avgPar >= 0 ? "+" : "") + fmt(avgPar, 1))}` +
        (avgDol == null ? "" : ` · avg $ ${fmt(avgDol, 1)}`) +
        (avgRnd == null ? "" : ` · avg round ${fmt(avgRnd, 1)}`);
    }
    const posRank = posPicks.slice().sort((a, b) => b.par - a.par);
    const ovMini = (p) => {
      if (!p) return `<tr><td class="own" colspan="3">No PAR in this slice.</td></tr>`;
      return `<tr>
        <td>${ovPlayerCell(p)}<div class="own">${p.year} · ${tName(p.tid)} · ${ovCost(p)}</div></td>
        <td><span class="badge pos-${p.pos}">${p.pos || "—"}</span></td>
        <td>${ovParChip(p.par)}</td>
      </tr>`;
    };
    const topP = document.querySelector("#ov-pos-top tbody");
    const worstP = document.querySelector("#ov-pos-worst tbody");
    if (topP) topP.innerHTML = (posRank.slice(0, 3).length ? posRank.slice(0, 3) : [null]).map(ovMini).join("");
    if (worstP) {
      const w = posRank.slice(-3).reverse();
      worstP.innerHTML = (w.length ? w : [null]).map(ovMini).join("");
    }
    const posFr = {};
    posPicks.forEach((p) => {
      const r = posFr[p.tid] || (posFr[p.tid] = { tid: p.tid, total: 0, n: 0 });
      r.total += p.par;
      r.n += 1;
    });
    const posFrRows = Object.values(posFr).map((r) => {
      r.mean = r.n ? r.total / r.n : 0;
      return r;
    }).sort((a, b) => b.mean - a.mean);
    const pfrTb = document.querySelector("#ov-pos-fr-tbl tbody");
    if (pfrTb) {
      pfrTb.innerHTML = posFrRows.map((r, i) => {
        const rank = i + 1;
        const pill = rank === 1 ? "gold" : rank === 2 ? "slv" : rank === 3 ? "brz" : "";
        return `<tr>
          <td><span class="rank-pill ${pill}">${rank}</span></td>
          <td>${teamCell(r.tid)}</td>
          <td class="${r.mean >= 0 ? "pos" : "neg"}"><strong>${r.mean >= 0 ? "+" : ""}${fmt(r.mean, 1)}</strong></td>
          <td class="${r.total >= 0 ? "pos" : "neg"}">${r.total >= 0 ? "+" : ""}${fmt(r.total, 1)}</td>
          <td>${r.n}</td>
        </tr>`;
      }).join("") || `<tr><td colspan="5" class="own">No ${ovPos} PAR.</td></tr>`;
    }
  }

  function recapSquadKey() {
    return squad ? A.canon(squad) : "";
  }
  function renderRecap() {
    const el = document.getElementById("draft-recap");
    if (!el) return;
    const key = recapSquadKey();
    const show = scope === "season" && !!key && labHasPar();
    el.hidden = !show;
    if (!show) {
      if (recapRoundChart) { recapRoundChart.destroy(); recapRoundChart = null; }
      if (recapPosChart) { recapPosChart.destroy(); recapPosChart = null; }
      return;
    }
    const fname = A.franchiseName(key) || tName(key);
    const title = document.getElementById("recap-title");
    if (title) title.textContent = fname + " · " + year + " Draft";
    const sub = document.getElementById("recap-sub");
    if (sub) {
      sub.textContent = year + " · " + (labAuction() ? "auction" : "snake") +
        " · PAR from parByOverall · current franchise name";
    }
    const rows = labPickRows();
    const mine = rows.filter((p) => ownerKey(p.tid) === key);
    const scored = labParRows(mine);
    const teams = labTeamRows(rows);
    const me = teams.find((r) => r.tid === key);
    const total = me ? me.total : scored.reduce((a, p) => a + p.par, 0);
    const rank = me ? me.rank : null;
    const grade = me ? me.grade : (teams.length ? labLetter(teams.length, teams.length) : null);
    const avg = scored.length ? scored.reduce((a, p) => a + p.par, 0) / scored.length : null;
    const hit = scored.length ? scored.filter((p) => p.par > 0).length / scored.length : null;
    const kpis = document.getElementById("recap-kpis");
    if (kpis) {
      const card = (n, title, desc) =>
        `<div class="card kpi"><div><div class="kpi-num">${n}</div>` +
        `<div class="kpi-title">${title}</div><div class="kpi-desc">${desc}</div></div></div>`;
      kpis.innerHTML = [
        card(avg == null ? "—" : ((avg >= 0 ? "+" : "") + fmt(avg, 1)), "Avg pick PAR",
          `<strong>${scored.length}</strong> graded picks · points above replacement`),
        card(hit == null ? "—" : (Math.round(hit * 100) + "%"), "Positive PAR",
          `<strong>${scored.filter((p) => p.par > 0).length}</strong> of ${scored.length} picks above replacement`),
        card(scored.length ? ((total >= 0 ? "+" : "") + fmt(total, 1)) : "—", "Total PAR",
          "sum of this franchise's drafted-player PAR"),
        card(rank == null ? "—" : String(rank), "Draft rank",
          rank == null ? "no team total" : (rank + " of " + teams.length + " · 1 = highest total PAR")),
      ].join("");
    }
    const gradeEl = document.getElementById("recap-grade");
    if (gradeEl) {
      gradeEl.innerHTML = grade
        ? `<span class="lab-grade lab-g-${grade[0]}">${grade}</span>`
        : "";
    }
    const stealEl = document.getElementById("recap-steal");
    if (stealEl) {
      const steal = me && me.steal;
      const reach = me && me.reach;
      const bit = (label, p, cls) => p
        ? `<div><span class="own">${label}</span> <strong>${A.playerLink(p.pid, p.name, { year })}</strong> ${labParChip(p.par)}</div>`
        : `<div class="own">${label} —</div>`;
      stealEl.innerHTML = bit("Best steal", steal, "g") + bit("Worst reach", reach, "r");
    }
    const tb = document.querySelector("#recap-picks-tbl tbody");
    if (tb) {
      const ordered = mine.slice().sort((a, b) => (a.overall || 0) - (b.overall || 0));
      tb.innerHTML = ordered.map((p) => `<tr>
        <td><span class="rank-pill">${p.overall || "—"}</span></td>
        <td><strong>${A.playerLink(p.pid, p.name, { year })}</strong></td>
        <td><span class="badge pos-${p.pos}">${p.pos || "—"}</span></td>
        <td>${labCost(p)}</td>
        <td>${labParChip(p.par)}</td>
      </tr>`).join("") || `<tr><td colspan="5" class="own">No picks for this franchise this season.</td></tr>`;
    }

    const rounds = [...new Set(rows.map((p) => p.round).filter((r) => r != null))].sort((a, b) => a - b);
    const lgR = {}, tmR = {};
    labParRows(rows).forEach((p) => { (lgR[p.round] = lgR[p.round] || []).push(p.par); });
    scored.forEach((p) => { (tmR[p.round] = tmR[p.round] || []).push(p.par); });
    if (recapRoundChart) { recapRoundChart.destroy(); recapRoundChart = null; }
    const rCanvas = document.getElementById("recap-round-chart");
    if (rCanvas && rounds.length) {
      recapRoundChart = new Chart(rCanvas, {
        data: {
          labels: rounds.map((r) => "R" + r),
          datasets: [
            {
              type: "bar", label: fname,
              data: rounds.map((r) => ovMean(tmR[r] || [])),
              backgroundColor: C.blue, maxBarThickness: 22, order: 2,
            },
            {
              type: "line", label: "League avg",
              data: rounds.map((r) => ovMean(lgR[r] || [])),
              borderColor: "#ffffff", backgroundColor: "#ffffff",
              borderWidth: 2, borderDash: [5, 4], pointRadius: 0, tension: 0, order: 1,
            },
          ],
        },
        options: {
          maintainAspectRatio: false,
          plugins: { legend: { labels: { boxWidth: 10, boxHeight: 10 } } },
          scales: {
            y: { grid: { color: C.grid }, border: { display: false }, title: { display: true, text: "mean PAR" } },
            x: { grid: { display: false }, border: { display: false } },
          },
        },
      });
    }
    const lgP = {}, tmP = {};
    labParRows(rows).forEach((p) => {
      if (!OV_POS.includes(p.pos)) return;
      (lgP[p.pos] = lgP[p.pos] || []).push(p.par);
    });
    scored.forEach((p) => {
      if (!OV_POS.includes(p.pos)) return;
      (tmP[p.pos] = tmP[p.pos] || []).push(p.par);
    });
    if (recapPosChart) { recapPosChart.destroy(); recapPosChart = null; }
    const pCanvas = document.getElementById("recap-pos-chart");
    if (pCanvas) {
      recapPosChart = new Chart(pCanvas, {
        data: {
          labels: OV_POS,
          datasets: [
            {
              type: "bar", label: fname,
              data: OV_POS.map((pos) => ovMean(tmP[pos] || [])),
              backgroundColor: OV_POS.map((pos) => OV_POS_COLORS[pos]), maxBarThickness: 26, order: 2,
            },
            {
              type: "line", label: "League avg",
              data: OV_POS.map((pos) => ovMean(lgP[pos] || [])),
              borderColor: "#ffffff", backgroundColor: "#ffffff",
              borderWidth: 2, borderDash: [5, 4], pointRadius: 3, tension: 0, order: 1,
            },
          ],
        },
        options: {
          maintainAspectRatio: false,
          plugins: { legend: { labels: { boxWidth: 10, boxHeight: 10 } } },
          scales: {
            y: { grid: { color: C.grid }, border: { display: false }, title: { display: true, text: "mean PAR" } },
            x: { grid: { display: false }, border: { display: false } },
          },
        },
      });
    }
  }



  /* ---------- Draft Guide (CHI-60): class grid + scout modal, AFFL data only ---------- */
  const GUIDE_SKILL = { QB: 1, RB: 1, WR: 1, TE: 1 };
  let guidePid = null;
  let guideQ = "";
  let guideBound = false;

  function guideSlug(name) {
    return String(name || "").toLowerCase()
      .replace(/['’.]/g, "")
      .replace(/&/g, "and")
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "");
  }
  function guideWriteURL(p) {
    const u = new URL(location.href);
    if (p && p.pid != null && p.pid !== "") {
      u.searchParams.set("pid", String(p.pid));
      const slug = guideSlug(p.name);
      if (slug) u.searchParams.set("player", slug);
      else u.searchParams.delete("player");
    } else {
      u.searchParams.delete("pid");
      u.searchParams.delete("player");
    }
    if (scope === "season" && year) u.searchParams.set("year", String(year));
    if (squad) u.searchParams.set("squad", squad);
    else u.searchParams.delete("squad");
    if (scope === "cum") u.searchParams.set("scope", "cum");
    else u.searchParams.delete("scope");
    history.replaceState(null, "", u.pathname.split("/").pop() + u.search + u.hash);
  }
  function guideYearBoard(y) {
    const yy = Number(y);
    if (scope === "cum" && ALL) {
      const hit = ALL.find((x) => Number(x.year) === yy);
      const board = (hit && hit.data && hit.data.draft && hit.data.draft.board) || [];
      const par = (hit && hit.data && hit.data.draftValue && hit.data.draftValue.parByOverall) || {};
      const auction = !!(hit && hit.data && hit.data.draft && hit.data.draft.auction);
      return board.map((p) => Object.assign({}, p, {
        year: yy,
        auction: auction,
        par: par[String(p.overall)] != null ? Number(par[String(p.overall)]) : null,
      }));
    }
    return ((YD && YD.draft && YD.draft.board) || []).map((p) => Object.assign({}, p, {
      year: pickYear(p),
      auction: p.auction != null ? p.auction : !!(YD && YD.draft && YD.draft.auction),
      par: navParOf(p),
    }));
  }
  function guideClass(pick) {
    const y = pickYear(pick);
    const board = guideYearBoard(y);
    const pos = navNormPos(pick.pos);
    const samePos = board.filter((p) => navNormPos(p.pos) === pos);
    if (samePos.length >= 5) {
      return { rows: samePos, label: y + " " + pos, n: samePos.length, year: y, pos: pos };
    }
    const skill = board.filter((p) => GUIDE_SKILL[navNormPos(p.pos)]);
    return { rows: skill.length ? skill : board, label: y + " skill", n: (skill.length ? skill : board).length, year: y, pos: "SKILL" };
  }
  function guidePct(value, values) {
    const nums = values.filter((v) => v != null && !Number.isNaN(Number(v))).map(Number);
    if (value == null || Number.isNaN(Number(value)) || nums.length < 2) return null;
    const v = Number(value);
    const below = nums.filter((x) => x < v).length;
    const equal = nums.filter((x) => x === v).length;
    return Math.round(100 * (below + 0.5 * (equal - 1)) / (nums.length - 1));
  }
  function guideAgeOf(p) {
    const b = A.playerBio(p.pid, pickYear(p), asOf);
    return b && b.age != null ? b.age : null;
  }
  function guideBioOf(p) {
    return A.playerBio(p.pid, pickYear(p), asOf) || {};
  }
  function guideAuction(p) {
    if (p.auction != null) return !!p.auction;
    return !!(YD && YD.draft && YD.draft.auction);
  }
  function guideCapital(p) {
    const auction = guideAuction(p);
    const bits = [];
    if (auction) bits.push("$" + (p.bid || 0));
    if (p.round != null) bits.push("R" + p.round);
    if (p.overall != null) bits.push("#" + p.overall);
    return bits.length ? bits.join(" · ") : "draft capital missing";
  }
  function guideViewPicks() {
    return ((YD && YD.draft && YD.draft.board) || []).map((p) => Object.assign({}, p, {
      year: pickYear(p),
      pos: navNormPos(p.pos),
      par: navParOf(p),
      auction: p.auction != null ? p.auction : !!(YD && YD.draft && YD.draft.auction),
    }));
  }
  function guideFiltered() {
    const q = (guideQ || "").toLowerCase();
    return guideViewPicks().filter((p) => {
      if (S.pos && S.pos !== "ALL" && navNormPos(p.pos) !== S.pos) return false;
      if (!q) return true;
      const college = (guideBioOf(p).college || "").toLowerCase();
      return (p.name || "").toLowerCase().includes(q)
        || college.includes(q)
        || tName(p.tid).toLowerCase().includes(q)
        || (p.nfl || "").toLowerCase().includes(q)
        || String(p.pid) === q;
    });
  }
  function guideFind(pid) {
    if (pid == null || pid === "") return null;
    const want = String(pid);
    const rows = guideViewPicks();
    return rows.find((p) => String(p.pid) === want) || null;
  }
  function guideComps(pick, klass) {
    const metric = (p) => (p.par != null ? p.par : p.pts);
    const target = metric(pick);
    if (target == null) return [];
    const others = klass.rows.filter((p) => String(p.pid) !== String(pick.pid) && metric(p) != null);
    const samePos = others.filter((p) => navNormPos(p.pos) === navNormPos(pick.pos));
    const pool = samePos.length ? samePos : others;
    return pool.slice().sort((a, b) => Math.abs(metric(a) - target) - Math.abs(metric(b) - target)).slice(0, 3);
  }
  function guideTile(label, valueHtml, pct, missing) {
    if (missing) {
      return `<div class="guide-tile">
        <div class="guide-tile-k">${label}</div>
        <div class="guide-tile-missing">${missing}</div>
      </div>`;
    }
    const pctHtml = pct == null
      ? `<div class="guide-tile-pct">percentile missing · class too small</div>`
      : `<div class="guide-tile-pct">${pct}<span class="guide-th">th</span> vs class</div>`;
    return `<div class="guide-tile">
      <div class="guide-tile-k">${label}</div>
      <div class="guide-tile-v">${valueHtml}</div>
      ${pctHtml}
    </div>`;
  }
  function renderGuide() {
    const grid = document.getElementById("guide-grid");
    const empty = document.getElementById("guide-empty");
    const sub = document.getElementById("guide-sub");
    if (!grid) return;
    const rows = guideFiltered();
    const nAll = guideViewPicks().length;
    if (sub) {
      sub.textContent = (scope === "cum" ? "All" : String(year))
        + " · AFFL class grid · " + nAll + " draftees"
        + (S.pos && S.pos !== "ALL" ? " · " + S.pos : "")
        + " · Board position chips filter this grid";
    }
    if (!rows.length) {
      grid.innerHTML = "";
      if (empty) {
        empty.hidden = false;
        empty.textContent = nAll ? "No drafted player matches that search." : "No drafted players in this Draft view.";
      }
    } else {
      if (empty) empty.hidden = true;
      grid.innerHTML = rows.map((p) => {
        const bio = guideBioOf(p);
        const college = bio.college
          ? A.esc(bio.college)
          : `<span class="guide-miss">college missing</span>`;
        const on = guidePid != null && String(guidePid) === String(p.pid);
        return `<button type="button" class="guide-chip${on ? " on" : ""}" data-pid="${A.esc(p.pid)}" data-year="${A.esc(pickYear(p))}">
          ${A.headshotHTML(p, "guide-hs")}
          <span class="badge pos-${A.esc(p.pos || "")}">${A.esc(p.pos || "")}</span>
          <strong class="guide-chip-name">${A.esc(p.name || "—")}</strong>
          <span class="guide-chip-college">${college}</span>
          <span class="guide-chip-team">${A.esc(tName(p.tid))}</span>
        </button>`;
      }).join("");
      grid.querySelectorAll("button[data-pid]").forEach((b) => {
        b.addEventListener("click", () => guideOpen(b.dataset.pid));
      });
    }
    if (guidePid) {
      const still = guideFind(guidePid);
      if (still) guidePaint(still);
      else if (!document.getElementById("guide-modal").hidden) {
        /* keep modal if deep-linked player is still the open one but filtered out of grid */
        const open = guideViewPicks().find((p) => String(p.pid) === String(guidePid));
        if (open) guidePaint(open);
      }
    }
  }
  function guidePaint(p) {
    const card = document.getElementById("guide-card");
    if (!card || !p) return;
    const bio = guideBioOf(p);
    const klass = guideClass(p);
    const age = guideAgeOf(p);
    const auction = guideAuction(p);
    const ptsVals = klass.rows.map((x) => x.pts).filter((v) => v != null);
    const parVals = klass.rows.map((x) => x.par).filter((v) => v != null);
    const ageVals = klass.rows.map(guideAgeOf).filter((v) => v != null);
    const bidVals = auction ? klass.rows.map((x) => x.bid).filter((v) => v != null) : [];
    const ptsPct = guidePct(p.pts, ptsVals);
    const parPct = guidePct(p.par, parVals);
    const agePct = age == null ? null : guidePct(-age, ageVals.map((v) => -v));
    const bidPct = auction ? guidePct(p.bid, bidVals) : null;
    const collegeHtml = bio.college
      ? `${A.collegeLogoHTML(bio, "guide-ncaa")} <span>${A.esc(bio.college)}</span>`
      : `<span class="guide-miss">college missing</span>`;
    const ageHtml = age != null ? fmt(age, 1) : null;
    const comps = guideComps(p, klass);
    const landing = tName(p.tid);
    card.innerHTML = `
      <div class="guide-ident">
        ${A.headshotHTML(p, "guide-hs-lg")}
        <div class="guide-ident-text">
          <div class="guide-kicker">AFFL Draft Guide · ${A.esc(klass.year)} class</div>
          <h3 id="guide-name">${A.playerLink(p.pid, p.name, { year: pickYear(p) })}</h3>
          <div class="guide-tags">
            <span class="badge pos-${A.esc(p.pos || "")}">${A.esc(p.pos || "")}</span>
            <span class="guide-nfl">${A.nflLogoHTML(p.nfl, "nfl-logo sm")} ${A.esc(p.nfl || "—")}</span>
            <span class="guide-year">${A.esc(pickYear(p))}</span>
          </div>
          <div class="guide-meta-row">${collegeHtml}</div>
          <div class="guide-meta-row"><span class="guide-k">Age</span> ${age != null ? A.esc(bio.ageText || fmt(age, 1)) : '<span class="guide-miss">age missing</span>'}</div>
          <div class="guide-meta-row"><span class="guide-k">Draft capital</span> ${A.esc(guideCapital(p))}</div>
          <div class="guide-meta-row"><span class="guide-k">AFFL landing</span> ${teamLink(p.tid)} · ${A.esc(pickYear(p))}</div>
        </div>
      </div>
      <div class="guide-class-note">Percentiles vs ${A.esc(klass.label)} · n=${klass.n} · season pts and PAR from this year’s draft board. Board pts and PAR only.</div>
      <div class="guide-tiles">
        ${p.pts != null
          ? guideTile("Season pts", fmt(p.pts, 1), ptsPct)
          : guideTile("Season pts", "", null, "pts missing")}
        ${p.par != null
          ? guideTile("PAR", (p.par >= 0 ? "+" : "") + fmt(p.par, 1), parPct)
          : guideTile("PAR", "", null, "PAR missing")}
        ${age != null
          ? guideTile("Age", fmt(age, 1), agePct)
          : guideTile("Age", "", null, "age missing")}
        ${auction
          ? (p.bid != null ? guideTile("Bid / cost", "$" + (p.bid || 0), bidPct) : guideTile("Bid / cost", "", null, "cost missing"))
          : guideTile("Bid / cost", "", null, "not an auction year")}
      </div>
      <div class="guide-comps">
        <h4>Comps</h4>
        ${comps.length
          ? `<ul>${comps.map((c) => {
              const m = c.par != null ? ((c.par >= 0 ? "+" : "") + fmt(c.par, 1) + " PAR") : (c.pts != null ? fmt(c.pts, 1) + " pts" : "—");
              return `<li>${A.playerLink(c.pid, c.name, { year: pickYear(c) })} <span class="badge pos-${A.esc(c.pos || "")}">${A.esc(c.pos || "")}</span> <span class="own">${A.esc(m)}</span> · ${A.esc(tName(c.tid))}</li>`;
            }).join("")}</ul>`
          : `<div class="guide-miss">No nearby comps in this class.</div>`}
      </div>`;
  }
  function guideOpen(pid) {
    const p = guideFind(pid);
    const modal = document.getElementById("guide-modal");
    if (!modal) return;
    if (!p) {
      guidePid = pid;
      guideWriteURL({ pid: pid, name: "" });
      const card = document.getElementById("guide-card");
      if (card) card.innerHTML = `<div class="guide-miss">That player is not in this Draft view.</div>`;
      modal.hidden = false;
      document.body.classList.add("guide-lock");
      return;
    }
    guidePid = p.pid;
    guideWriteURL(p);
    guidePaint(p);
    modal.hidden = false;
    document.body.classList.add("guide-lock");
    renderGuide();
  }
  function guideClose() {
    guidePid = null;
    const modal = document.getElementById("guide-modal");
    if (modal) modal.hidden = true;
    document.body.classList.remove("guide-lock");
    guideWriteURL(null);
    renderGuide();
  }
  function guideStep(dir) {
    const rows = guideFiltered();
    if (!rows.length) return;
    let i = rows.findIndex((p) => String(p.pid) === String(guidePid));
    if (i < 0) i = 0;
    else i = (i + dir + rows.length) % rows.length;
    guideOpen(rows[i].pid);
  }
  function bindGuide() {
    if (guideBound) return;
    guideBound = true;
    const search = document.getElementById("guide-search");
    if (search) {
      search.addEventListener("input", (e) => {
        guideQ = e.target.value || "";
        renderGuide();
      });
    }
    const modal = document.getElementById("guide-modal");
    if (modal) {
      modal.addEventListener("click", (e) => {
        if (e.target.closest("[data-guide-close]")) guideClose();
      });
    }
    const prev = document.getElementById("guide-prev");
    const next = document.getElementById("guide-next");
    if (prev) prev.addEventListener("click", () => guideStep(-1));
    if (next) next.addEventListener("click", () => guideStep(1));
    document.addEventListener("keydown", (e) => {
      const modalEl = document.getElementById("guide-modal");
      if (!modalEl || modalEl.hidden) return;
      if (e.key === "Escape") guideClose();
      if (e.key === "ArrowLeft") guideStep(-1);
      if (e.key === "ArrowRight") guideStep(1);
    });
  }

  const holdoutScopeEl = $('#holdout-scope');
  if (holdoutScopeEl) holdoutScopeEl.addEventListener('click', (e) => {
    const b = e.target.closest('[data-scope]');
    if (!b) return;
    S.holdoutScope = b.dataset.scope;
    renderHoldout();
  });
  const holdoutStackEl = $('#holdout-stack');
  if (holdoutStackEl) holdoutStackEl.addEventListener('click', (e) => {
    const b = e.target.closest('[data-stack]');
    if (!b) return;
    S.mekkoStack = b.dataset.stack;
    renderHoldout();
  });
  window.addEventListener('resize', () => {
    if (!YD) return;
    const block = holdoutBlock();
    if (!holdoutSliceEmpty(block)) renderMekko(block);
  });
  const holdoutCont = document.querySelector('.holdout-continuous');
  if (holdoutCont) holdoutCont.addEventListener('toggle', (e) => {
    if (!e.target.open || !YD) return;
    const block = holdoutBlock();
    if (!holdoutSliceEmpty(block)) renderContinuous(block);
  });

  bindAllDraftSorts();

  $('#board-more').addEventListener('click', () => { S.limit += 60; renderBoard(); });
  $('#draft-search').addEventListener('input', (e) => { S.q = e.target.value; S.limit = 60; renderBoard(); });

  A.onNextMidnight(() => { asOf = A.today(); const el = document.getElementById("age-asof"); if (el) el.value = isoDay(asOf); renderAge(); renderBoard(); });
  const qs = new URLSearchParams(location.search);
  await pick(A.seasonFromURL() || A.years()[0]);
  bindGuide();
  const bootPid = qs.get("pid");
  if (bootPid) guideOpen(bootPid);
})();
