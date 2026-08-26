/* CHI-66 / AFFL-043 — Season Wrapped: that year only, PAR adds, trade grades. */
(async function () {
  const A = window.AFFL;
  await A.boot();
  const $ = (id) => document.getElementById(id);
  const esc = A.esc;
  const fmt = A.fmt;

  let year = +new URLSearchParams(location.search).get("year") || A.years()[0] || 2025;
  let YD = null;
  const squad = A.squadFromURL();
  A.stampNav(squad);

  function seasonOf(y) {
    return (A.data.seasons && A.data.seasons[String(y)]) || {};
  }

  function teamsOf(y) {
    return (seasonOf(y).teams || []).slice();
  }

  function ownerByTid(y) {
    const out = {};
    Object.values(A.teams(y) || {}).forEach((t) => {
      if (t && t.owner != null) {
        const oid = A.canon(t.owner);
        out[t.id] = oid;
        out[String(t.id)] = oid;
      }
    });
    return out;
  }

  function fran(y, tid) {
    const owners = ownerByTid(y);
    const oid = owners[tid] || owners[Number(tid)] || owners[String(tid)] || null;
    if (!oid) return { owner: "", name: "—", logo: "" };
    return {
      owner: oid,
      name: A.franchiseName(oid) || "—",
      logo: A.franchiseLogo(oid) || "",
    };
  }

  function ident(f) {
    const logo = A.logoHTML({ name: f.name, logo: f.logo }, "wrap-logo");
    return `<div class="wrap-ident">${logo}<div class="wrap-name">${esc(f.name)}</div></div>`;
  }

  function metricYears() {
    return A.years().filter((y) => {
      const s = seasonOf(y);
      const teams = s.teams || [];
      if (s.champion != null) return true;
      if (teams.some((t) => t.finalRank === 1)) return true;
      return false;
    });
  }

  function setYearURL(y) {
    const u = new URL(location.href);
    u.searchParams.set("year", String(y));
    if (squad) u.searchParams.set("squad", squad);
    history.replaceState(null, "", u.pathname.split("/").pop() + u.search + u.hash);
  }

  function card(title, body, extraCls) {
    return `<article class="card wrap-card${extraCls ? " " + extraCls : ""}">
      <div class="wrap-kicker">${esc(title)}</div>
      ${body}
    </article>`;
  }

  function playerMap(yd) {
    const out = {};
    ((yd && yd.players) || []).forEach((p) => {
      if (p && p.pid != null) out[p.pid] = p;
    });
    return out;
  }

  function namesOf(arr) {
    return (arr || []).map((x) => x.name).filter(Boolean);
  }

  function nameList(arr) {
    const n = namesOf(arr);
    if (!n.length) return "—";
    if (n.length === 1) return n[0];
    if (n.length === 2) return n[0] + " + " + n[1];
    return n.slice(0, -1).join(", ") + " + " + n[n.length - 1];
  }

  function letterGrade(netPts) {
    if (netPts >= 80) return "A";
    if (netPts >= 30) return "B";
    if (netPts >= -30) return "C";
    if (netPts >= -80) return "D";
    return "F";
  }

  function gradeTrades(yd, y) {
    if (y < 2018) return [];
    const players = playerMap(yd);
    const trades = (yd && yd.trades) || [];
    const out = [];
    trades.forEach((tr, i) => {
      const wk = tr.wk;
      const sides = (tr.sides || []).map((s) => {
        const got = [];
        let pts = 0, par = 0;
        (s.got || []).forEach((g) => {
          const p = players[g.pid] || players[Number(g.pid)];
          const rec = A.afterStart(p, s.tid, wk);
          const base = p ? A.posBaseline(yd, p.pos) : null;
          const weekly = base != null ? base / 17 : 0;
          const gpar = rec.starts ? rec.pts - weekly * rec.starts : 0;
          pts += rec.pts;
          par += gpar;
          got.push({
            pid: g.pid,
            name: (p && p.name) || g.name,
            pos: (p && p.pos) || g.pos,
            pts: rec.pts,
            par: gpar,
            from: g.from,
          });
        });
        return { tid: s.tid, got: got, pts: pts, par: par };
      });
      if (sides.length < 2) return;
      const totalPts = sides.reduce((a, s) => a + s.pts, 0);
      const totalPar = sides.reduce((a, s) => a + s.par, 0);
      sides.forEach((s) => {
        s.netPts = s.pts - (totalPts - s.pts);
        s.netPar = s.par - (totalPar - s.par);
        s.grade = letterGrade(s.netPts);
        s.sent = [];
        sides.forEach((o) => { if (o !== s) s.sent = s.sent.concat(o.got); });
      });
      const ranked = sides.slice().sort((a, b) => a.netPts - b.netPts);
      out.push({
        i: i, wk: wk, date: tr.date, sides: sides,
        worst: ranked[0], best: ranked[ranked.length - 1],
      });
    });
    return out;
  }

  function gradeAdds(yd) {
    const players = playerMap(yd);
    const drafted = {};
    Object.values(players).forEach((p) => {
      if (p.draft && p.draft.teamId != null) drafted[p.pid] = true;
    });
    const first = {};
    ((yd && yd.moves) || []).forEach((m) => {
      if (m.type !== "WAIVER" && m.type !== "FREEAGENT") return;
      (m.add || []).forEach((g) => {
        if (g.pid == null || m.wk == null) return;
        const k = String(g.pid) + ":" + String(m.tid);
        if (!first[k] || m.wk < first[k].wk) {
          first[k] = { pid: g.pid, tid: m.tid, wk: m.wk, type: m.type };
        }
      });
    });
    Object.values(players).forEach((p) => {
      if (drafted[p.pid] || p.mainTeam == null) return;
      const k = String(p.pid) + ":" + String(p.mainTeam);
      if (!first[k]) first[k] = { pid: p.pid, tid: p.mainTeam, wk: 0, type: "UNDRAFTED" };
    });
    const rows = [];
    Object.values(first).forEach((a) => {
      const p = players[a.pid] || players[Number(a.pid)];
      if (!p) return;
      const rec = A.afterStart(p, a.tid, a.wk);
      const base = A.posBaseline(yd, p.pos);
      if (base == null) return;
      rows.push({
        pid: p.pid, name: p.name, pos: p.pos, tid: a.tid, wk: a.wk,
        stPts: rec.pts, starts: rec.starts, par: rec.pts - base, base: base, type: a.type,
      });
    });
    rows.sort((a, b) => (b.par - a.par) || (b.stPts - a.stPts));
    return rows;
  }

  function keptBusts(yd) {
    const busts = ((yd && yd.draftValue && yd.draftValue.busts) || []).slice();
    const traded = {};
    ((yd && yd.trades) || []).forEach((tr) => {
      (tr.sides || []).forEach((s) => {
        (s.got || []).forEach((g) => {
          if (g.pid != null && g.from != null) traded[String(g.pid) + ":" + String(g.from)] = true;
        });
      });
    });
    return busts.filter((b) => {
      const tid = b.tid != null ? b.tid : b.teamId;
      return !traded[String(b.pid) + ":" + String(tid)];
    });
  }

  function signed(n, d) {
    const v = fmt(n, d);
    if (n > 0) return "+" + v;
    return v;
  }

  function buildCards() {
    const cards = [];
    const season = seasonOf(year);
    const teams = teamsOf(year);
    const n = teams.length;

    const champ = teams.find((t) => t.finalRank === 1)
      || teams.find((t) => t.id === season.champion);
    if (champ) {
      const f = fran(year, champ.id);
      const rec = [champ.wins, champ.losses].every((x) => x != null)
        ? `${champ.wins}-${champ.losses}` : "";
      const pf = champ.pf != null ? `${fmt(champ.pf, 2)} PF` : "";
      const line = [rec, pf].filter(Boolean).join(" · ");
      cards.push(card("Champion", `${ident(f)}${line ? `<div class="wrap-stat">${esc(line)}</div>` : ""}`, "wrap-champ"));
    }

    const sack = n ? teams.find((t) => t.finalRank === n) : null;
    if (sack) {
      const f = fran(year, sack.id);
      const rec = [sack.wins, sack.losses].every((x) => x != null)
        ? `${sack.wins}-${sack.losses}` : "";
      const pf = sack.pf != null ? `${fmt(sack.pf, 2)} PF` : "";
      const line = [rec, pf].filter(Boolean).join(" · ");
      cards.push(card("Sacko", `${ident(f)}${line ? `<div class="wrap-stat">${esc(line)}</div>` : ""}`, "wrap-sacko"));
    }

    const pfKing = teams.filter((t) => t.pf != null).slice().sort((a, b) => b.pf - a.pf)[0];
    if (pfKing) {
      const f = fran(year, pfKing.id);
      cards.push(card("PF King", `${ident(f)}<div class="wrap-stat">${fmt(pfKing.pf, 2)} PF</div>`));
    }

    const luckRows = (YD && YD.luckFG) || [];
    if (luckRows.length) {
      const top = luckRows.slice().sort((a, b) => (b.net || 0) - (a.net || 0))[0];
      if (top && top.net != null) {
        const f = fran(year, top.teamId);
        const net = top.net > 0 ? "+" + top.net : String(top.net);
        cards.push(card("Luck", `${ident(f)}<div class="wrap-stat">${esc(net)}</div><div class="wrap-sub">Luck Index · lucky − unlucky</div>`));
      }
    }

    const adds = gradeAdds(YD);
    if (adds.length && adds[0].name && adds[0].par != null) {
      const a = adds[0];
      const f = fran(year, a.tid);
      const pl = A.playerLink(a.pid, a.name, { year: year, squad: squad, cls: "wrap-player" });
      cards.push(card("Best Add", `<div class="wrap-ident">${pl}</div><div class="wrap-stat">${esc(signed(a.par, 1))} PAR</div><div class="wrap-sub">${esc(a.pos || "")}${f.name !== "—" ? " · " + esc(f.name) : ""} · ${esc(fmt(a.stPts, 1))} starter pts after add</div>`));
    }

    const grades = gradeTrades(YD, year);
    const worstDeal = grades.length ? grades.slice().sort((a, b) => a.worst.netPts - b.worst.netPts)[0] : null;
    const bestDeal = grades.length ? grades.slice().sort((a, b) => b.best.netPts - a.best.netPts)[0] : null;

    const busts = keptBusts(YD);
    if (busts.length && busts[0].name && busts[0].par != null) {
      const b = busts[0];
      const f = fran(year, b.tid != null ? b.tid : b.teamId);
      const pl = A.playerLink(b.pid, b.name, { year: year, squad: squad, cls: "wrap-player" });
      const par = fmt(b.par, 1);
      cards.push(card("Worst Draft", `<div class="wrap-ident">${pl}</div><div class="wrap-stat">${esc(par)} PAR</div><div class="wrap-sub">$${esc(b.bid != null ? b.bid : "—")}${f.name !== "—" ? " · " + esc(f.name) : ""} · kept</div>`));
    } else if (worstDeal && worstDeal.worst && worstDeal.worst.netPts < 0) {
      /* traded-away star is not a draft leftover — the trade card carries it */
    }

    if (worstDeal && worstDeal.worst && worstDeal.worst.netPts < 0) {
      const w = worstDeal.worst;
      const f = fran(year, w.tid);
      const swap = `sent ${nameList(w.sent)} for ${nameList(w.got)}`;
      cards.push(card("Worst Trade", `${ident(f)}<div class="wrap-swap">${esc(swap)}</div><div class="wrap-stat">${esc(signed(w.netPts, 1))} starter pts</div><div class="wrap-sub">after Wk ${esc(String(worstDeal.wk))} · ${esc(signed(w.netPar, 1))} PAR · grade ${esc(w.grade)}</div>`, "wrap-trade-bad"));
    }
    if (bestDeal && bestDeal.best && bestDeal.best.netPts > 0) {
      const b = bestDeal.best;
      const f = fran(year, b.tid);
      const swap = `got ${nameList(b.got)} for ${nameList(b.sent)}`;
      cards.push(card("Best Trade", `${ident(f)}<div class="wrap-swap">${esc(swap)}</div><div class="wrap-stat">${esc(signed(b.netPts, 1))} starter pts</div><div class="wrap-sub">after Wk ${esc(String(bestDeal.wk))} · ${esc(signed(b.netPar, 1))} PAR · grade ${esc(b.grade)}</div>`, "wrap-trade-good"));
    }

    window.__afflWrapped = {
      year: year,
      adds: adds.slice(0, 12),
      bestAdd: adds[0] || null,
      keptBusts: busts,
      grades: grades,
      worstTrade: worstDeal,
      bestTrade: bestDeal,
    };

    return cards;
  }

  function fillTable(tbl, rows) {
    const tb = tbl && tbl.querySelector("tbody");
    if (!tb) return;
    tb.innerHTML = rows.join("");
  }

  function renderTables() {
    const power = (YD && YD.power) || [];
    const powerCard = $("wrap-power-card");
    if (powerCard) {
      if (!power.length) powerCard.hidden = true;
      else {
        powerCard.hidden = false;
        fillTable($("wrap-power-tbl"), power.map((r) => {
          const f = fran(year, r.teamId);
          const rec = (r.w != null && r.l != null) ? `${r.w}-${r.l}` : "—";
          return `<tr><td class="wrap-rank">${esc(r.rank != null ? r.rank : "")}</td><td>${ident(f)}</td><td>${esc(rec)}</td></tr>`;
        }));
      }
    }

    const luck = (YD && YD.luckFG) || [];
    const luckCard = $("wrap-luck-card");
    if (luckCard) {
      if (!luck.length) luckCard.hidden = true;
      else {
        luckCard.hidden = false;
        const rows = luck.slice().sort((a, b) => (b.net || 0) - (a.net || 0));
        fillTable($("wrap-luck-tbl"), rows.map((r) => {
          const f = fran(year, r.teamId);
          const net = r.net > 0 ? "+" + r.net : String(r.net);
          return `<tr><td></td><td>${ident(f)}</td><td>${esc(net)}</td></tr>`;
        }));
      }
    }

    const notes = (YD && YD.notables) || [];
    const notesCard = $("wrap-notes-card");
    if (notesCard) {
      if (!notes.length) notesCard.hidden = true;
      else {
        notesCard.hidden = false;
        fillTable($("wrap-notes-tbl"), notes.map((r) => {
          const w = fran(year, r.winnerId);
          const l = fran(year, r.loserId);
          return `<tr>
            <td>${esc(r.kind || "")}</td>
            <td>${esc(r.week != null ? r.week : "")}</td>
            <td>${esc(w.name)}</td>
            <td>${esc(r.winnerPts != null ? r.winnerPts : "")}</td>
            <td>${esc(r.loserPts != null ? r.loserPts : "")}</td>
            <td>${esc(l.name)}</td>
          </tr>`;
        }));
      }
    }

    const grades = (window.__afflWrapped && window.__afflWrapped.grades) || [];
    const tradeCard = $("wrap-trades-card");
    if (tradeCard) {
      if (year < 2018 || !grades.length) tradeCard.hidden = true;
      else {
        tradeCard.hidden = false;
        const rows = grades.slice().sort((a, b) => a.worst.netPts - b.worst.netPts);
        fillTable($("wrap-trades-tbl"), rows.map((g) => {
          const w = g.worst;
          const b = g.best;
          const wf = fran(year, w.tid);
          const bf = fran(year, b.tid);
          const deal = `${wf.name} sent ${nameList(w.sent)} for ${nameList(w.got)}`;
          return `<tr>
            <td class="wrap-rank">${esc(String(g.wk))}</td>
            <td><div class="wrap-deal">${esc(deal)}</div><div class="wrap-deal-sub">${esc(bf.name)} got ${esc(nameList(b.got))}</div></td>
            <td class="${w.netPts < 0 ? "wrap-neg" : "wrap-pos"}">${esc(signed(w.netPts, 1))}</td>
            <td class="${w.netPar < 0 ? "wrap-neg" : "wrap-pos"}">${esc(signed(w.netPar, 1))}</td>
            <td><span class="wrap-grade wrap-grade-${esc(w.grade)}">${esc(w.grade)}</span></td>
          </tr>`;
        }));
      }
    }
  }

  function render() {
    const host = $("wrap-cards");
    const cards = buildCards();
    host.innerHTML = cards.length ? cards.join("") : `<div class="notice">No released Wrapped metrics for ${year}.</div>`;
    const sub = $("page-sub");
    if (sub) sub.textContent = `${year} season · that year's events only · current franchise names`;
    const lede = $("wrap-lede");
    if (lede) {
      lede.textContent = year < 2018
        ? `${year} recap from numbers this site already computes. ESPN has no trade log before 2018 — no invented deals. Adds ranked by PAR, not raw points.`
        : `${year} recap from numbers this site already computes. Season events only. Adds ranked by PAR (points minus replacement). Trades graded on starter points after the deal week.`;
    }
    renderTables();
  }

  function renderYearChips() {
    const el = $("year-picker");
    if (!el) return;
    const ys = metricYears();
    const cur = ys.indexOf(year) >= 0 ? year : (ys[0] || year);
    year = cur;
    A.yearPicker(el, year, (y) => { pick(y); }, null, ys);
  }

  async function pick(y) {
    year = y;
    setYearURL(y);
    try { YD = await A.loadYear(y); }
    catch (e) { YD = {}; }
    renderYearChips();
    render();
  }

  const ys = metricYears();
  if (ys.indexOf(year) < 0) year = ys[0] || year;
  await pick(year);
})();
