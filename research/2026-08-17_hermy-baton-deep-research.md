# AFFL Hermy Baton — deep research memo

**Date:** 2026-08-17  
**Branch:** `AFFL_Hermy_Baton` @ `58176a9` (+ heavy local WIP, preserved)  
**Repo:** `/Users/chilly/Projects/ccDesktopAFFL` (`rdsciv/affl-analytics`)  
**Worktree:** same directory as `verify/full-audit` (no new worktree)  
**Linear:** [AFFL Sourcebook v1](https://linear.app/childressllc/project/affl-sourcebook-v1-88ad883cc233) — **live API unavailable this session** (`LINEAR_API_KEY` unset; Composio Linear connection failed). Statuses below are reconstructed from `START-HERE.md`, eval headers, and Grok Bot session blobs — re-query Linear before flipping any card.

---

## 1. What “where it needs to be” means

The product is not another app. It is:

1. **A correct warehouse** (`affl.db`) for AFFL ESPN league `51418`, seasons **2014–2025 only**.
2. **A static archive site** under `site/` that never invents missing grains.
3. **Evidence-gated UX** — verified / reconstructed / unavailable chips, no fake zeros.
4. **Ryan’s review loop** — localhost `:8765` → Chrome → In QA → his OK → In Deploy → `main` Pages → Done.

“Done” is **not** eval pass, not Grok Bot saying QA, not a screenshot.

North star (from `design.md` + `FACTORY.md`): loud mark, quiet archive body, tables first, home answers **who won and how**.

---

## 2. Verified live warehouse (read-only, this session)

| Fact | Value |
| --- | --- |
| `PRAGMA integrity_check` | `ok` |
| `dim_season` | 12 rows: 2014–2025 (**no 2026**) |
| `dim_team` season 2026 | **0** |
| `dim_player` | 5,107 |
| `fact_roster_week` | 24,762 (2018–2025) |
| `fact_matchup` | 2,220 |
| `fact_draft_pick` | 2,124 |
| `fact_transaction` | 15,815 |
| `fact_trade` | **392** (STATUS.md “181” is stale) |
| `fact_nfl_week` | 208,168 |
| `fact_contract` / `fact_cap_hit` | 31,893 / 30,611 |
| Sidecar tables in DB | **all missing**: `fact_ngs`, `dim_player_bio`, `fact_injury`, `fact_depthchart`, `fact_college`, `fact_player_overview` |
| Sidecar JSON under `site/` | present (local-only state; export is dangerous) |

**Binding correction (CHI-75):** There is no AFFL 2026 season before the draft. Membership is navigation only. NFL 2026 roster rows in `player_season` are **not** an AFFL season.

**Eval conflict found this session:**

```text
python3 evals/test_handoff.py          → PASS
python3 evals/test_warehouse_2026.py   → FAIL
  - expects dim_season 2026 + 12 teams (CHI-72 Phase A stub)
  - current DB correctly has 0 (CHI-75)
```

That single conflict is the cleanest proof the gauntlet must **reconcile tickets before shipping UI**.

---

## 3. Site surface inventory (local, ahead of production)

**Server already correct:** PID serves `/Users/chilly/Projects/ccDesktopAFFL/site` on **8765**.  
Checked: `http://127.0.0.1:8765/` → HTTP 200, AFFL chrome present.

| Page | Job | Notes |
| --- | --- | --- |
| `index.html` | Season / cumulative dashboard | CHI-46 cumulative default |
| `scoreboard.html` | Matchups + squad filter | CHI-62; notables redesign = CHI-80 backlog |
| `players.html` | Player OS | charts CHI-51; FPpG bug CHI-54; NGS tree CHI-59/84 |
| `draft.html` | Auction board + guide | CHI-60 |
| `trades.html` | Front office | CHI-45 join; grades CHI-66 |
| `roto.html` | Roto standings | warehouse-backed |
| `teams.html` | Franchise lab | NGS scheme CHI-84 |
| `history.html` | Titles / record book / custody | CHI-50/55/39 |
| `awards.html` | All-League / Bush / W1 | CHI-57/83; **CHI-81 backlog redesign** |
| `dictionary.html` | Metric dictionary | CHI-53 |
| `wrapped.html` | Season wrapped | CHI-66 |

Production Pages (`main`) is **behind** this tree. Do not treat live as truth for current WIP.

---

## 4. Linear / ticket map (from repo + Grok Bot)

### 4.1 Handoff queue (`START-HERE.md` — re-query before acting)

| ID | Subject | Handoff status | Gauntlet stance |
| --- | --- | --- | --- |
| **CHI-72** | Warehouse foundation / sidecars | In Dev | **Core.** Phase A stub eval is now wrong vs CHI-75. Phase B sidecars **not** in DB. |
| **CHI-75** | Remove premature 2026 AFFL season | DB corrected; build path may still stub | **Close the loop:** strip `load_2026_stub`, rewrite evals, planning membership only. |
| **CHI-76** | Visualization tooling plan | Planning | **Plan only.** No new chart library until approved. Chart.js stays. |
| **CHI-80** | Scoreboard Notables redesign | Backlog | **Do not start.** |
| **CHI-81** | Awards broken / redesign | Backlog | **Do not start** without approved system. Small mechanical fixes only if ticketed. |
| **CHI-82** | Handoff / START-HERE | Ready for In QA after eval | **`test_handoff.py` PASS this session.** |

### 4.2 Warehouse / contract tickets with evals (mostly built, need truth gate)

| ID | Eval / artifact | Grain |
| --- | --- | --- |
| CHI-21/23 | `CONTRACTS.md` | Identity + phase |
| CHI-24 | `test_matchup_import_2025.py` | Matchup box import |
| CHI-25 | `test_scoring_notables_2025.py` | Scoring / notables |
| CHI-26 | `test_standings_power_luck_2025.py` | Standings / power / luck |
| CHI-27 | `test_starter_nfl_2025.py` | Starter NFL lines |
| CHI-29 | `test_nav_gates.py` | Nav evidence gates |
| CHI-30–36 | auction, draft value, rosters, lineup IQ, tx, trades, history gates | 2018+ verified where claimed |
| CHI-37 | entity / rivalry history | warehouse only |
| CHI-39 | custody PAR on History | GM grade ≠ starter pts |

### 4.3 Product surface tickets Grok Bot looped (claims ≠ Ryan Done)

From Grok Bot sand blobs (Ork / ScraprBot / AFFLbot, ~2026-08-17):

| ID | Theme | Bot claim | Risk |
| --- | --- | --- | --- |
| CHI-45 | Trade builder join | “fixed; 37→40 deals 2025” | Warehouse may lag site JSON |
| CHI-48 | Max Potential | “In QA” | Verify eval + year-only display |
| CHI-50/55 | Titles + record book | “on History” | Need eval + Chrome |
| CHI-51 | Player year + career charts | “canvas height fix” | Regression-prone |
| CHI-53 | Dictionary | “In QA, 41 terms” | OK candidate |
| CHI-54 | FPpG divide by starts vs NFL games | “fixed Tucker 6.16” | **Correctness critical** — re-verify |
| CHI-57/83 | Awards position pills / W1 cards | iterative UX thrash | CHI-81 still backlog |
| CHI-59/84 | NGS route tree / O-line gaps | “In QA” | Must use stored AFFL NGS only; no invented film |
| CHI-60/61 | Draft guide / tables | “In QA” | Season filter |
| CHI-66 | Wrapped + trade grades | partial | No pre-2018 fiction |
| CHI-67/69 | Logo home / 2026 header rail | marks only | Rail ≠ AFFL season |
| CHI-88 | Marimekko draft + team area | started mid-loop | **Defer** until CHI-76 + core gates |

### 4.4 Explicit backlog / research (do not steal the gauntlet)

- CHI-40–43 ESPN sports API context (cache only; never browser ESPN)
- CHI-44 player journey, CHI-47 team comp
- CHI-78/85/87 SumerSports / nfelo / third-party MCP — **out of AFFL factory path**
- `research/running-ml-brief.md` — running models side research, not this site loop

---

## 5. Grok Bot session autopsy (why the loop failed)

Primary sources: `~/Library/Application Support/Grok Bot/sand-client-persistence/*.blob` (Ork, ScraprBot, AFFLbot, Analyst).

### What worked
- Filed Linear tickets and sometimes hit real bugs (FPpG label vs season total).
- Local site on 8765 used for review URLs.
- Some mechanical UI landed (dictionary, history titles, trade join site files).

### Failure modes (binding anti-patterns for Hermy Baton)

1. **Roadmap theater.** User: “loop through and fix everything NOW.” Bot: 90-day nfelo/OSF plan, Supabase hosted tap-in, yFiles debate.  
2. **Project drift.** Left `ccDesktopAFFL` for SumerSports Supabase rename drama (`AFFL_ss`). Wrong product.  
3. **User-as-ops.** Asked Ryan to sign in on the box. Ryan reaction: don’t ask me to do shit.  
4. **Status inflation.** “In QA” without Ryan Chrome review; never production Done.  
5. **Contract blindness.** CHI-72 Phase A still wants 2026 stub while CHI-75 deleted it; bot didn’t reconcile.  
6. **Evidence theater.** Reception Perception / route trees without film rates → risk of invented metrics. Bot sometimes refused correctly; sometimes shipped decorative NGS.  
7. **No ledger.** Parallel cursor agents, no persistent task ledger → thrash and partial claims.  
8. **export / rebuild risk.** Talk of full warehouse rebuild while sidecars only live in `site/*.json`.

### Design implication
The gauntlet must be **ticket-narrow, eval-gated, same-repo, no roadmap, no “please sign in,” no Done without Ryan + Pages.**

---

## 6. Subject research (product domains)

### 6.1 Identity (CONTRACTS.md)
- Owner ≠ franchise slot ≠ team-season ≠ alias.
- Kafka/Chupacabras: **`m01 → m07` only** (never reverse).
- Sliger `m03 → m08`, Dunn `m20 → m10`.
- Gabagooners `m22` new; Pounders `m19` / Pollywogs `m14` historic.
- Career math groups by owner, not team name / `team_id`.

### 6.2 Evidence
| Status | Allowed surfaces |
| --- | --- |
| Verified | Awards, standings, career, primary nav |
| Reconstructed | Explore, labeled (pre-2018 totals, trade ledger) |
| Unavailable | Omitted — never 0-fill benches/tx 2014–17 |

### 6.3 Phase
- Championship = regular + `WINNERS_BRACKET` only.
- Consolation stored, never folded into title W/L.
- League size 10 (2014–16) then 12.

### 6.4 Scoring
- AFFL rules; yardage BUCKET ≤2018, FRACTIONAL ≥2019.
- 50-yard FG = 3 (documented quirk).
- Never trust vendor FPTS column; recompute under `dim_scoring`.

### 6.5 GM metrics (METRICS.md / CONTRACTS)
- **Custody PAR** = rostered weeks PAR (not starter-only).
- **Lineup IQ** = actual ÷ optimal (start/sit).
- **Trade Alpha** = ROS delta at trade time — separate from Custody PAR; needs dated ROS (mostly unavailable historically).

### 6.6 Draft market
- PAR/$ and position×price tiers already the league’s edge story.
- Mid-tier RBs historically overpaid; $10–24 QBs strong (STATUS findings).
- CHI-88 Marimekko/connected-scatter is **analysis presentation**, not foundation.

### 6.7 Sidecars / ESPN sports API
- Schema defines NGS/bio/injury/depth/college/overview; **DB lacks tables**.
- Site JSON caches exist → `export_site.py` can **wipe** local-only state.
- CHI-72 complete only when tables exist **and** load path is non-destructive **or** export is gated.

### 6.8 Visualization (CHI-76)
- Current: Chart.js in `site/`.
- ROADMAP candidates: TanStack Charts, flint — **plan first**.
- HermesAFFL skill prefers OpenChart for *that* monorepo; **this factory stays static Chart.js until CHI-76 approved**. Do not install a second stack here.

### 6.9 Parallel universe: HermesAFFL
- Canonical brain for Next/DuckDB golden Excel lives at `~/Projects/HermesAFFL`.
- **This gauntlet does not migrate there.** User locked work to `ccDesktopAFFL`. Harvest only if a ticket says so.

---

## 7. Gaps ranked by harm

| Rank | Gap | Why it hurts | Ticket / wave |
| --- | --- | --- | --- |
| 1 | CHI-72 vs CHI-75 eval/build contradiction | Agents will re-insert fake 2026 | 72/75 · Wave A |
| 2 | Sidecars schema-only; JSON local | Blind export destroys work | 72 · Wave A |
| 3 | Wrong player numbers (FPpG etc.) | Trust death | 54 · Wave B |
| 4 | Trade warehouse vs site drift | Front office lies | 45/35 · Wave B |
| 5 | No team-season move timing / value-added view | Can't see churn vs skill on Teams | Phase 9 · **Wave T** |
| 6 | Awards UX thrash without system | CHI-81 still open | 81 backlog |
| 7 | Stale STATUS/preview docs | Agent mis-navigation | docs hygiene |
| 8 | Production lag | Public site wrong vs local | deploy wave only after Ryan |
| 9 | Chart library FOMO | Scope explosion | 76 plan only · Wave D |

---

## 8. Recommended destination state (definition of “there”)

**Warehouse**
- Contracts enforced in code + evals.
- No 2026 `dim_season`/`dim_team` pre-draft.
- Sidecars either loaded with provenance **or** explicitly documented incomplete (never half-claimed).
- `build_db.py --check` green; no silent stub loaders.

**Site**
- Every primary nav page: real numbers or honest empty; no em-dash hero bugs.
- Evidence chips on reconstructed surfaces.
- 2026 header rail = planning membership art only.
- Awards/Notables redesigns only after CHI-80/81 approval.

**Process**
- One Linear ticket at a time (or one wave of independent verify-only tasks).
- Eval + checked `http://127.0.0.1:8765/<page>` before In QA.
- Ryan Chrome review before In Deploy.
- Pages live before Done.
- No commit/push/PR unless Ryan asks.

---

## 9. Sources used

- `START-HERE.md`, `STATUS.md`, `CONTRACTS.md`, `FACTORY.md`, `ROADMAP.md`, `design.md`, `METRICS.md`, `schema.sql`
- Live `affl.db` read-only queries (this session)
- `evals/test_*.py` inventory (80+ scripts)
- Grok Bot sand-client-persistence transcripts (2026-08-17 loops)
- Hermes sessions: HermesAFFL platform history (context only; not this tree)
- Local server probe: port 8765 → this `site/`

**Not used as truth:** stale `preview/SUMMARY.md` / `preview/WAREHOUSE.md` counts; Linear live (unavailable); production Pages.
