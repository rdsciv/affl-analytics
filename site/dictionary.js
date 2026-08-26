/* CHI-53 / AFFL-034 — Data Dictionary. Only metrics this site computes. */
(function () {
  const TERMS = [
    {
      name: "PAR (Points Above Replacement)",
      cat: "draft",
      aliases: ["PAR", "points above replacement", "parByOverall"],
      def: "Season AFFL points minus replacement at that position. From warehouse v_draft_value / parByOverall. A cheap QB is not a steal when replacement QBs already score a lot (replacement QB ~248)."
    },
    {
      name: "PAR/$",
      cat: "draft",
      aliases: ["PAR per dollar", "par per $", "value"],
      def: "PAR divided by auction dollars on that pick (team tables: PAR / scored spend). The value number we actually rank on. Fairer than raw points per dollar."
    },
    {
      name: "PPD (Points Per Dollar)",
      cat: "draft",
      aliases: ["PPD", "points per dollar", "pts/$"],
      def: "Raw points / scored spend. Positionally biased; PAR/$ is the fairer grade."
    },
    {
      name: "Replacement",
      cat: "draft",
      aliases: ["replacement level", "baseline"],
      def: "The position baseline that season. PAR is points above that line."
    },
    {
      name: "Steal",
      cat: "draft",
      aliases: ["steals", "best value"],
      def: "High PAR relative to cost (top of draftValue.steals)."
    },
    {
      name: "Bust / Reach",
      cat: "draft",
      aliases: ["bust", "reach", "busts"],
      def: "Low or negative PAR relative to cost (draftValue.busts)."
    },
    {
      name: "Auction vs Snake",
      cat: "draft",
      aliases: ["auction", "snake", "nomination"],
      def: "Auction years use nomination order: overall pick into rounds of 12. Snake uses stored rounds."
    },
    {
      name: "Draft Hit Rate",
      cat: "draft",
      aliases: ["hit rate", "HIT RATE"],
      def: "Share of drafted players with scored points who cleared 100 AFFL points (pts >= 100). Draft KPI 04. Not PAR > 0."
    },
    {
      name: "Draft Stack",
      cat: "draft",
      aliases: ["stack", "DOUBLE", "TRIPLE", "QUAD"],
      def: "2+ players from the same NFL team on one AFFL roster. Labeled DOUBLE / TRIPLE / QUAD."
    },
    {
      name: "QB Stack",
      cat: "draft",
      aliases: ["qb stack", "connected stack"],
      def: "A stack that includes a QB plus a WR or TE from that NFL team."
    },
    {
      name: "College Stack",
      cat: "draft",
      aliases: ["school stack", "college"],
      def: "2+ players from the same school on one AFFL roster. Missing college is skipped, never invented."
    },
    {
      name: "Homer",
      cat: "draft",
      aliases: ["homers", "franchise concentration"],
      def: "Franchise concentration in one NFL team (2+ picks). Toggle also shows NFL → franchises."
    },
    {
      name: "Handcuff",
      cat: "draft",
      aliases: ["handcuffs", "cuff"],
      def: "2+ players, same AFFL franchise, same NFL team, same position."
    },
    {
      name: "Auction DNA",
      cat: "draft",
      aliases: ["DNA", "Cates", "top6", "l1Distance"],
      def: "How a franchise spends auction dollars: top-6 bids vs the Cates curve $58 / $40 / $24 / $13 / $12 / $9. Table shows warehouse top6Spend, restSpend, top6Share, l1Distance. Cumulative is the average across auction years, not career-stacked. Hidden for snake / pre-2016 and when the year file has no DNA."
    },
    {
      name: "Draft Board",
      cat: "draft",
      aliases: ["board", "round grid"],
      def: "Franchise × round grid. Current franchise names as rows."
    },
    {
      name: "Weekly Custody (draft)",
      cat: "draft",
      aliases: ["custody", "weekly ownership", "waiver", "FA"],
      def: "Drafted / traded in / waiver / FA / $ flipped / points given up. Weekly ownership starts in 2018; no lineups or transaction feed before that."
    },
    {
      name: "Keepers",
      cat: "draft",
      aliases: ["keeper", "keeper league"],
      def: "AFFL does not use keepers."
    },
    {
      name: "All-Play / Power Rankings",
      cat: "league",
      aliases: ["All-Play", "allplay", "power", "power rankings", "PWR", "power_ratio"],
      def: "Each regular-season week you play every other team. A win is outscoring them. Stored as allplay_w / allplay_l. Power rank uses raw allplay_w / (allplay_w + allplay_l) (power_ratio), not the rounded display percent."
    },
    {
      name: "Luck Index",
      cat: "league",
      aliases: ["luck", "lucky win", "unlucky loss", "v_luck", "net"],
      def: "Lucky wins minus unlucky losses (v_luck, FantasyGenius discrete). Lucky win: you won AND finished in the bottom half of that week's scores (W and beat * 2 < field). Unlucky loss: you lost AND finished in the top half (L and beat * 2 >= field). Not the same as Weighted Luck."
    },
    {
      name: "Weighted Luck",
      cat: "league",
      aliases: ["schedule luck", "expected wins", "v_luck_weighted"],
      def: "Actual wins minus expected wins (v_luck_weighted). Shown in the luck-chart tooltip. Different formula from Luck Index. History franchise luck is a sum of per-season t.luck (this weighted path), not Luck Index net."
    },
    {
      name: "Maximum Potential / Optimal Lineup",
      cat: "league",
      aliases: ["Maximum Potential", "optimal lineup", "max points", "lineupIQ"],
      def: "The lineup that would have scored the most points (max points). Gifted Kid award goes to the highest optimal total. From lineupIQ."
    },
    {
      name: "Leftover / Wasted",
      cat: "league",
      aliases: ["leftover", "wasted", "bench points"],
      def: "Optimal minus actual (wasted). Points left on the bench."
    },
    {
      name: "Lineup Efficiency",
      cat: "league",
      aliases: ["efficiency", "actual / optimal", "management"],
      def: "Actual / optimal."
    },
    {
      name: "Title",
      cat: "league",
      aliases: ["championship", "champ", "cup"],
      def: "Championship: finalRank === 1."
    },
    {
      name: "Sacko",
      cat: "league",
      aliases: ["last place", "sacko"],
      def: "Last place: finalRank === n (12-team league)."
    },
    {
      name: "Point Title",
      cat: "league",
      aliases: ["scoreTitles", "points title", "PF champ"],
      def: "Highest regular-season points for in that season (scoreTitles on History). Not the same as the championship."
    },
    {
      name: "Combined Title",
      cat: "league",
      aliases: ["combined", "titles minus sackos", "titles − sackos"],
      def: "Planned combined ranking: titles minus sackos. History does not yet render a live combined column."
    },
    {
      name: "All-League",
      cat: "league",
      aliases: ["all league"],
      def: "Weekly positional top scorers."
    },
    {
      name: "Bush League",
      cat: "league",
      aliases: ["bush"],
      def: "Weekly positional bottoms. You do not want to lead this board."
    },
    {
      name: "FAAB",
      cat: "league",
      aliases: ["faab", "waiver budget", "bids"],
      def: "League is moving to FAAB. Historical waivers are traditional with bid 0. FAAB spend/value charts stay dark until a season has real bids."
    },
    {
      name: "2014–2017 data",
      cat: "league",
      aliases: ["2014", "2015", "2016", "2017", "pre-2018", "snapshots"],
      def: "No transaction log and no weekly benches. End-of-year snapshots exist. Never labeled “NFL not rostered.”"
    },
    {
      name: "Franchise / current name",
      cat: "league",
      aliases: ["franchise", "current name", "Feelers", "Tittsburgh", "owner"],
      def: "Franchise = owner. Site always shows the current name (Feelers, not Tittsburgh). Merges: m01→m07, m03→m08, m20→m10."
    },
    {
      name: "Non-PPR",
      cat: "league",
      aliases: ["PPR", "scoring", "non ppr"],
      def: "AFFL scoring is non-PPR."
    },
    {
      name: "WOPR",
      cat: "players",
      aliases: ["weighted opportunity", "receiving usage"],
      def: "Displayed from the receiving-usage warehouse (receivingUsage[].wopr). We do not recompute it on the page. Persistence plot is year-N WOPR vs year-N+1 AFFL non-PPR FPpG for WR/TE, 2018+."
    },
    {
      name: "Journey",
      cat: "players",
      aliases: ["journey rail", "ownership rail"],
      def: "Wrapping rail of weekly ownership + trades. Home team is the last rostered week, not the first. Pre-2018 uses snapshots only; we do not invent trades."
    },
    {
      name: "Chain of Custody",
      cat: "players",
      aliases: ["custody table", "timeline"],
      def: "Weekly stints table/timeline on the player page."
    },
    {
      name: "Stint",
      cat: "players",
      aliases: ["stints"],
      def: "Consecutive weeks on the same AFFL roster (skips nfl/unrecovered)."
    },
    {
      name: "Playoff stud / dud",
      cat: "players",
      aliases: ["playoff stud", "playoff dud", "yoffstud", "yoffdud"],
      def: "Player-card playoff flags (yoffstud / yoffdud) from AFFL playoff weeks. Need 3 playoff starts to grade."
    },
    {
      name: "Rings",
      cat: "players",
      aliases: ["ring", "AFFL titles"],
      def: "AFFL titles shown on the player card (count plus years in the tooltip)."
    },
    {
      name: "NGS",
      cat: "players",
      aliases: ["Next Gen Stats", "next gen"],
      def: "Next Gen Stats on the player card / game log."
    },
    {
      name: "Start %",
      cat: "players",
      aliases: ["start percent", "starts / rosteredGames", "startPct"],
      def: "Player career strip only: starts / rosteredGames. AFFL starts over weeks rostered — not a cross-league rate and not ideal-start %."
    },
    {
      name: "NGS route share",
      cat: "players",
      aliases: ["route share", "route tree", "yard share"],
      def: "Share of a player's stored AFFL NGS receiving yards on a named route (only keys present in the NGS profile: GO, SLANT, OUT, HITCH, CORNER, SCREEN, and the rest of that player's stored mix). Colored vs the same-position AFFL NGS average: green above 1.15×, yellow near, red below 0.85×. This is yard share, not Reception Perception success rate."
    },
    {
      name: "NGS hole share",
      cat: "players",
      aliases: ["hole share", "hole fan", "rush hole"],
      def: "Share of a player's stored AFFL NGS rushing yards through a named hole (only keys present: MID, LE, LT, LG, RG, RT, RE). Same green / yellow / red vs the same-position AFFL NGS average. Not a man/gap vs zone concept chart."
    },
    {
      name: "Reception Perception (not in AFFL)",
      cat: "players",
      aliases: ["RP", "RP success", "success vs coverage"],
      def: "We do not have Reception Perception charting. No success vs coverage, contested-catch conversion, alignment grades, in-space grades, or film-charted QB accuracy / CPOE-by-route. The player route tree and hole fan are yard-share pictures of stored AFFL NGS mixes only."
    },
    {
      name: "NGS CPOE",
      cat: "players",
      aliases: ["CPOE", "completion over expected"],
      def: "Season CPOE from the NGS passing profile when present on the player card. ngs.json has no throw-location or CPOE-by-route, so we do not draw a field accuracy map."
    }
  ];

  const CATS = ["all", "draft", "league", "players"];
  const CAT_LABEL = { all: "ALL", draft: "DRAFT", league: "LEAGUE", players: "PLAYERS" };

  const $ = (id) => document.getElementById(id);

  function params() {
    const u = new URLSearchParams(location.search);
    let cat = String(u.get("cat") || "all").toLowerCase();
    if (CATS.indexOf(cat) < 0) cat = "all";
    return { cat: cat, q: u.get("q") || "" };
  }

  const init = params();
  let cat = init.cat;
  let q = init.q;

  function hay(t) {
    return [t.name, t.def].concat(t.aliases || []).join(" ").toLowerCase();
  }

  function matches(t) {
    if (cat !== "all" && t.cat !== cat) return false;
    const needle = q.trim().toLowerCase();
    if (!needle) return true;
    return hay(t).indexOf(needle) >= 0;
  }

  function catCount(c) {
    return TERMS.filter((t) => c === "all" || t.cat === c).length;
  }

  function renderChips() {
    const el = $("dict-chips");
    if (!el) return;
    el.innerHTML = CATS.map((c) =>
      `<button type="button" class="season-chip dict-chip${c === cat ? " on" : ""}" data-cat="${c}">${CAT_LABEL[c]} (${catCount(c)})</button>`
    ).join("");
    el.querySelectorAll("[data-cat]").forEach((b) => {
      b.addEventListener("click", () => {
        cat = b.dataset.cat;
        const u = new URL(location.href);
        if (cat === "all") u.searchParams.delete("cat");
        else u.searchParams.set("cat", cat);
        history.replaceState(null, "", u.pathname.split("/").pop() + u.search + u.hash);
        render();
      });
    });
  }

  function renderList(rows) {
    const el = $("dict-list");
    if (!el) return;
    if (!rows.length) {
      el.innerHTML = `<p class="dict-empty">No terms match.</p>`;
      return;
    }
    el.innerHTML = rows.map((t) => `
      <article class="dict-term">
        <div class="dict-term-top">
          <h3>${t.name}</h3>
          <span class="dict-tag">${CAT_LABEL[t.cat]}</span>
        </div>
        <p class="dict-def">${t.def}</p>
      </article>`).join("");
  }

  function render() {
    const rows = TERMS.filter(matches);
    const count = $("dict-count");
    if (count) count.textContent = rows.length + " of " + TERMS.length + " terms";
    renderChips();
    renderList(rows);
  }

  async function boot() {
    if (window.A && typeof A.boot === "function") {
      await A.boot();
      if (typeof A.stampNav === "function") A.stampNav(A.squadFromURL());
    }
    const search = $("dict-search");
    if (search) {
      if (q) search.value = q;
      search.addEventListener("input", () => {
        q = search.value || "";
        const u = new URL(location.href);
        if (q.trim()) u.searchParams.set("q", q);
        else u.searchParams.delete("q");
        history.replaceState(null, "", u.pathname.split("/").pop() + u.search + u.hash);
        render();
      });
    }
    render();
  }

  boot();
})();
