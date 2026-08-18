# AFFL design system

Steal structure, not pixels. The mark is loud. The body is a quiet archive dashboard.

## What we studied

Confirmed from live pages and the products they stand in for.

| Source | What we took | What we left |
| --- | --- | --- |
| AFFL Leeger (`rdsciv.github.io/AFFLleeger/`) | Cleanest AFFL property. Four working KPI tiles (seasons / owners / matchups / range), one-line provenance, year chips as the drill. That is the home header rhythm. | leeger’s binning UI and a second analytics stack. |
| Live Analytics (`rdsciv.github.io/affl-analytics/`) | A hard don’t: first screen ships REG-SEASON POINTS and GAMES as em-dashes, charts blank. Local index must not repeat that. Hero-stats get real `data.json` fallbacks. `#kpi-row` and `#season-picker` get static HTML that JS replaces when fetch works. | The broken first screen. |
| FantasyGenius demo | First screen is “who won / what happened”: league identity, champ/clown cards, week strip, feed, rivalry rail. Recap voice in a side card. Standings is a drill with ALL/REG/PLAYOFFS — we keep standings on home because this site is archive-first, not a live weekly product. | Cloning their demo nav or putting standings on a second page. |
| FantasyPros My Playbook | Other pages are jobs, not chart types: Scoreboard (matchup), Players (one player), Draft (board), Trades (front office). Home is not those tools. | Start/sit, waivers, and trade widgets on the dashboard. |
| AFFL_Wrapped | Editorial magazine energy. Keep it in the footer mark only. | Magazine layout on the dashboard. |
| Stripe / Linear / Vercel (2026 dashboard craft) | First screen answers one question. Four KPI cards max. Monochrome body, one accent. Density in tables, not borders. Progressive disclosure. Calm density, no card-stack monotony. | Marketing chrome and rainbow illustration. |
| League Legacy | Record book, franchise career, H2H ledger, gamecenter (optimal / luck / position battle). All-time is a destination. | Eight career charts on the home fold. |
| Sleeper / sports UX | Matchup-centric when the league is live. Scoreboard page = matchup. | Live-week home. This site is archive-first. |

AFFL wedge: a 12-year evidence-gated warehouse. Verified vs reconstructed vs unavailable is a quiet status chip, not a banner. Custody PAR (when it exists) is the GM grade, not starter points.

## North-star screen

Home answers one question: **who won this season, and how.**

Above the fold, in this order:

1. Mark + nav
2. Leeger header strip: four working tiles (or the season donuts once JS hydrates) + one-line provenance + year chips
3. Final standings (left) and champion / Season Story (right)

Hero-stats (`#hs-total`, `#hs-games`) always show real numbers from `data.json` (2025 fallback: 15,723 points, 84 games). JS overwrites them per season. They are never em-dashes.

`#kpi-row` ships four static league tiles (12 seasons / 12 owners / 927 matchups / 2014–2025). When `app.js` loads `data.json`, it replaces that row with the four season donuts. Either way the first screen has four working numbers.

Everything else is later: weekly scoring, the race, luck, lab, profiler, genius, all-time.

## Information architecture

| Surface | Job | Not the job |
| --- | --- | --- |
| Home (`index.html`) | Season result. Who won, how, standings, story. Then scoring / race / luck. Lab and all-time after a scroll. | Start/sit, waivers, live matchup, draft board, trade desk. |
| Scoreboard | Matchup. Every lineup, every week. Gamecenter when we have optimal / luck / position battle. | Season recap. |
| Players | One player. Game log, usage, AFFL journey. | League standings. |
| Draft | Auction / snake board, steals, busts, ROI. | Manager GPA. |
| Trades | Front office. Trades and transaction log. | Weekly scoring. |

All-time (timeline, franchise records, H2H) lives on home but below the season. It is a destination, not the first screen.

Nav labels are jobs (Dashboard / Scoreboard / Players / Draft / Trades), not chart types.

## Visual tokens

Pulled from the mark (`site/logos/affl-mark.png`, `site/logos/affl-banner.png`). Do not invent a second palette.

| Token | Hex | Role |
| --- | --- | --- |
| `--bg0` / field | `#050508` → `#000` | Page and logo field. Near-black so the PNG black blends. |
| `--card` | `#0e1119` | Surfaces. |
| `--line` | `#1c2536` | 1px borders. No second border color. |
| `--blue` | `#00a2ff` | The one accent. Nav on-state, season chip on-state, focus, verified chip. |
| `--blue2` | `#47d4ff` | Lighter ice of the same glow. |
| `--orange` | `#ff6a00` | Title second-word and heat only. |
| `--green` | `#c8ff00` | Lime est. 2014 / positive deltas only. |
| `--yellow` | `#ffc400` | Burst interior, sparse hero numbers, reconstructed chip. |
| `--ink` | `#eef4ff` | Body and card headings. |
| `--mut` | `#7d8aa0` | Captions, data-source lines. |

Orange is not a second brand color on the page. Lime is not a chart series. Neon lives in the PNG, not in card shadows.

## Rules

**Brand loud, body quiet.** The mark is chrome, italic, ultra-heavy, electric outline, sunset metal, lime chip. Site titles echo that: italic 900, uppercase, orange second word, lime subline. Body type is roman. Card `h2` is `#eef4ff`, 13px, 700, uppercase — not a chrome text-clip. Section-break `h2` can stay a step louder.

**No chrome-clip on every heading.** `.chrome` and section breaks may use the steel gradient. Cards, tables, and tool chrome may not.

**Tables first.** Tabular numerals. Numeric columns right-aligned. Team / player / manager names left. Row height ~36px. Density from type and alignment, not from extra rules, glows, or zebra noise.

**Evidence chips, not banners.** Warehouse rows are verified, reconstructed, or unavailable. Use `.chip-verified` / `.chip-recon` / `.chip-na`. Tiny pills. Custody PAR is the GM grade when it exists.

**Four KPIs.** Number + short label. Donut rings stay once JS hydrates, 56px, no italic screaming. Static fallback tiles have no rings.

**Progressive disclosure.** Standings + story, then scoring / race / luck, then lab / profiler / genius / all-time.

**Cards.** 1px `#1c2536`, 10px radius, light shadow. No neon stack. No clipped-heading glow. Avoid a stack of identical cards; vary table vs chart vs story.

**Never ship a blank number.** If a figure waits on `fetch('data.json')`, give it a real fallback from that file or hide the node. Em-dashes on the first screen are a bug. `file://` and a failed GitHub Pages fetch are expected failure modes.

## Header and footer PNGs

Already implemented. Do not rebuild the mark in CSS or SVG text.

Header, every page:

```
<img class="brand-logo" src="logos/affl-mark.png" alt="AFFL">
AFFL Analytics   (or Scoreboard / PlayerProfiler / Draft Room / Front Office)
```

- `.brand-logo` is 64px tall, width auto. No rounded letter-box, border, or text-clip. Black field so the PNG vanishes into the page.
- Tight 8px gap to the title.
- Italic title + orange second word + lime subline (`est. 2014` or the page tag).
- Favicon is the same mark.
- Home header is two rows: brand + nav, then quieter hero-stats (real fallbacks, never dashes) + provenance + full-width season picker. Do not delete those IDs. Year chips are the drill, as on Leeger.

Footer, every page. Wrapped-magazine energy lives here, not on the dashboard:

```
<footer class="foot">
  <img class="foot-banner" src="logos/affl-banner.png" alt="AFFL">
  <p class="foot-caption">…data source line…</p>
</footer>
```

- `.foot` and `.foot-banner` sit on `#000`.
- Banner is `width: 100%`, `height: auto`, `object-fit: contain`, `max-height: 160px`. The asset is square; leftover width stays black.
- Caption is muted, small, centered.

Team logos in `site/logos/` are franchise art. Do not chrome them. Do not replace them with the AFFL mark. The old letter tiles (A / S / P / D / T) stay retired.

## What not to do

- Do not ship blank KPIs, em-dash hero-stats, or an empty year strip. That is the live Analytics failure mode.
- Do not turn home into a feature warehouse. Lab, profiler, genius, and all-time are later sections, not the first viewport.
- Do not draw rainbow charts. One accent. Orange for heat, lime for positive / est. 2014.
- Do not invent consensus numbers, fake ranks, or unverified “expert” grades. If the warehouse cannot support a figure, chip it unavailable or omit it.
- Do not put start/sit, waivers, or trade tools on home. Those pages already exist (FP decision IA).
- Do not treat all-time as eight charts above the fold.
- Do not rebuild AFFL in CSS, SVG text, or a boxed initial. Use the PNG.
- Do not banner the evidence model. Chips only.
- Do not grade GMs on starter points when custody PAR exists.
- Do not spread AFFL_Wrapped magazine layout across the dashboard. Footer mark only.
- Do not stack identical glowing cards. Calm density.
