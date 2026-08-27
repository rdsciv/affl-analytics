#!/usr/bin/env python3
"""Load every source into affl.db.

Reads the same cached inputs fetch.py produces (data/*.json, data/*.csv) and
lands them in the relational schema, which then becomes the single source of
truth for metrics. Idempotent: safe to re-run, rebuilds from scratch.

    python3 build_db.py                   # rebuild everything
    python3 build_db.py --check           # run verification queries only
    python3 build_db.py --import-matchups 2025   # CHI-24: one season, keep checksum
    python3 build_db.py --sidecars        # CHI-72 Phase B: NGS/bio/injury/college/overview
"""
import csv
import gzip
import json
import os
import re
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime, timezone
import adapters.espn_box_v1 as espn_box
from process_seasons import resolve_accept_items

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, 'data')
# AFFL_DB lets a rebuild be rehearsed against a copy. This script starts by
# deleting most of the warehouse, so being able to prove a run is non-destructive
# before pointing it at the real file is the difference between a test and a bet.
DB = os.environ.get('AFFL_DB') or os.path.join(HERE, 'affl.db')
SITE = os.path.join(HERE, 'site')

SLOT = {0: 'QB', 2: 'RB', 3: 'RB/WR', 4: 'WR', 5: 'WR/TE', 6: 'TE', 7: 'OP',
        16: 'D/ST', 17: 'K', 20: 'BN', 21: 'IR', 23: 'FLEX'}
BENCH = {'BN', 'IR'}

def load(path):
    if not os.path.exists(path):
        return None
    d = json.load(open(path))
    return d[0] if isinstance(d, list) else d

def fnum(row, key):
    try:
        return float(row.get(key) or 0)
    except (ValueError, TypeError):
        return 0.0

# --------------------------------------------------------------------- schema
def init(con):
    con.executescript(open(os.path.join(HERE, 'schema.sql')).read())
    cols = {r[1] for r in con.execute('PRAGMA table_info(dim_member)')}
    if 'owner_id' not in cols:
        con.execute('ALTER TABLE dim_member ADD COLUMN owner_id TEXT')

def wipe(con):
    for t in ('fact_trade_item', 'fact_trade', 'fact_transaction', 'fact_draft_pick',
              'fact_matchup', 'fact_roster_week', 'fact_roster_snapshot_pre2018',
              'fact_nfl_week', 'fact_contract',
              'fact_cap_hit', 'fact_player_season_points', 'player_season',
              'fact_player_week_par', 'fact_player_season_par_reconstructed',
              'fact_xtd_player_week', 'fact_projection_week', 'fact_roto_team_season',
              'fact_roto_team_week',
              'fact_ngs', 'dim_player_bio', 'fact_injury', 'fact_depthchart',
              'fact_college', 'fact_player_overview',
              'dim_player', 'dim_team',
              'dim_member', 'dim_owner', 'dim_scoring', 'dim_season'):
        con.execute(f'DELETE FROM {t}')

# ------------------------------------------------------------------ load core
def load_seasons_and_teams(con, site):
    """dim_season / dim_member / dim_team come from the already-anonymised
    site/data.json, so no ESPN SWID ever reaches the database."""
    for mid, name in site['members'].items():
        con.execute("""INSERT INTO dim_member(member_id, display_name, is_active)
                       VALUES (?,?,0)
                       ON CONFLICT(member_id) DO UPDATE SET
                         display_name=excluded.display_name, is_active=0""",
                    (mid, name))
    active = set(site.get('activeOwners') or [])
    con.executemany('UPDATE dim_member SET is_active = 1 WHERE member_id = ?',
                    [(a,) for a in active])

    for yr_s, s in site['seasons'].items():
        year = int(yr_s)
        bundle = load(os.path.join(SITE, 'years', f'{year}.json')) or {}
        slots = bundle.get('slots') or {}
        yardage = 'BUCKET' if year <= 2018 else 'FRACTIONAL'
        con.execute("""INSERT OR REPLACE INTO dim_season
            (season, reg_weeks, playoff_teams, team_count, auction_draft,
             has_rosters, has_tx, uses_faab,
             slot_qb, slot_rb, slot_wr, slot_te, slot_flex, slot_dst, slot_k,
             yardage_mode)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (year, max(s['regWeeks']) if s.get('regWeeks') else 13,
             s.get('playoffTeams'), len(s['teams']),
             int(bool(bundle.get('auctionDraft'))), int(bool(bundle.get('hasRosters'))),
             int(bool(bundle.get('hasTx'))), int(bool(bundle.get('usesFaab'))),
             slots.get('QB'), slots.get('RB'), slots.get('WR'), slots.get('TE'),
             slots.get('FLEX'), slots.get('DST'), slots.get('K'), yardage))

        con.executemany("""INSERT OR REPLACE INTO dim_team
            (season, team_id, member_id, name, abbrev, logo, wins, losses, ties,
             points_for, points_against, playoff_seed, final_rank)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            [(year, t['id'], t.get('owner'), t['name'], t.get('abbrev'), t.get('logo'),
              t.get('wins'), t.get('losses'), t.get('ties'), t.get('pf'), t.get('pa'),
              t.get('playoffSeed'), t.get('finalRank')) for t in s['teams']])

def parse_current_2026():
    """Site header rail only — planning/navigation membership, not warehouse season.

    CHI-75: CURRENT_2026 must never be written into dim_season / dim_team
    before the AFFL draft. Callers may read this for UI checks; do not load.
    """
    path = os.path.join(SITE, 'common.js')
    js = open(path).read()
    block = re.search(r'const CURRENT_2026 = \[(.*?)\];', js, re.S)
    if not block:
        raise RuntimeError('CURRENT_2026 missing from site/common.js')
    rows = re.findall(
        r'owner:\s*"([^"]+)"\s*,\s*name:\s*"([^"]+)"\s*,\s*logo:\s*"([^"]*)"',
        block.group(1))
    return rows


def refuse_affl_2026_season(con):
    """CHI-75: there is no AFFL 2026 season before the draft.

    Strip any leftover dim_season/dim_team 2026 rows. NFL roster identity in
    player_season for calendar 2026 is a different grain and is left alone.
    """
    n_team = con.execute("SELECT COUNT(*) FROM dim_team WHERE season=2026").fetchone()[0]
    n_season = con.execute("SELECT COUNT(*) FROM dim_season WHERE season=2026").fetchone()[0]
    if n_team or n_season:
        con.execute("DELETE FROM dim_team WHERE season=2026")
        con.execute("DELETE FROM dim_season WHERE season=2026")
    return n_team + n_season


def load_2026_stub(con, site=None):
    """Removed (CHI-75). Kept only so old docs/scripts fail loudly."""
    raise RuntimeError(
        "CHI-75: load_2026_stub is retired. There is no AFFL 2026 season "
        "before the draft. Do not insert dim_season/dim_team 2026. "
        "Planning membership lives in site/common.js CURRENT_2026 only."
    )


def iter_roster_by_espn(year):
    """Latest nflverse roster row per espn_id. D/ST have no espn_id here."""
    path = os.path.join(DATA, f'roster_{year}.csv')
    if not os.path.exists(path):
        return
    by_eid = {}
    for row in csv.DictReader(open(path)):
        eid = row.get('espn_id')
        if not eid:
            continue
        try:
            eid = int(eid)
        except ValueError:
            continue
        try:
            wk = int(row.get('week') or 0)
        except ValueError:
            wk = 0
        prev = by_eid.get(eid)
        if prev is None or wk >= prev[0]:
            by_eid[eid] = (wk, row)
    for eid, (_wk, row) in by_eid.items():
        yield eid, row


def upsert_roster_players(con, year):
    """Load nflverse roster_YEAR into dim_player / player_season. espn→gsis."""
    existing = {r[0]: r[1] for r in con.execute(
        'SELECT player_id, gsis_id FROM dim_player')}
    new_players = 0
    seasons = []
    for eid, row in iter_roster_by_espn(year):
        name = (row.get('full_name') or '').strip()
        pos = (row.get('position') or '').strip()
        gsis = (row.get('gsis_id') or '').strip() or None
        hs = row.get('headshot_url') or ''
        if hs:
            hs = hs.replace('f_auto,q_auto',
                            'c_fill,g_face,h_200,w_200,f_auto,q_auto')
        else:
            hs = None
        nfl = (row.get('team') or '').strip() or None
        if eid not in existing:
            if not name:
                continue
            con.execute("""INSERT INTO dim_player
                (player_id, name, position, gsis_id, otc_id, headshot_url)
                VALUES (?,?,?,?,NULL,?)""", (eid, name, pos, gsis, hs))
            existing[eid] = gsis
            new_players += 1
        elif gsis and not existing[eid]:
            con.execute("""UPDATE dim_player SET gsis_id=?
                            WHERE player_id=? AND (gsis_id IS NULL OR gsis_id='')""",
                        (gsis, eid))
            existing[eid] = gsis
        seasons.append((year, eid, nfl))
    con.executemany(
        'INSERT OR REPLACE INTO player_season(season, player_id, nfl_team) VALUES (?,?,?)',
        seasons)
    return new_players, len(seasons)


def fix_huntley_gsis(con):
    """Caleb Huntley: nflverse has gsis but often no espn_id. Name backfill only."""
    row = con.execute(
        "SELECT player_id, gsis_id FROM dim_player WHERE name='Caleb Huntley'"
    ).fetchone()
    if not row or row[1]:
        return 0
    gsis = None
    for year in range(2014, 2027):
        path = os.path.join(DATA, f'roster_{year}.csv')
        if not os.path.exists(path):
            continue
        for r in csv.DictReader(open(path)):
            if (r.get('full_name') or '').strip() == 'Caleb Huntley' and r.get('gsis_id'):
                gsis = r['gsis_id'].strip()
    if not gsis:
        return 0
    con.execute("""UPDATE dim_player SET gsis_id=?
                    WHERE player_id=? AND (gsis_id IS NULL OR gsis_id='')""",
                (gsis, row[0]))
    return 1


def backfill_pool_players(con):
    """Name pre-2018 players that exist only in ESPN's own season player pool.

    A player who was rostered or drafted before 2018 but never reached a boxscore
    and has no nflverse espn_id gets no dim_player row, so fact_roster_week ends up
    pointing at an unknown player. The pool ESPN shipped with that season's draft
    has every one of them. Runs after the pre-2018 lineup load, since that is what
    introduces the references.
    """
    import json as _json
    POS = {1: 'QB', 2: 'RB', 3: 'WR', 4: 'TE', 5: 'K', 16: 'D/ST'}
    missing = {pid for (pid,) in con.execute("""
        SELECT DISTINCT player_id FROM fact_roster_week r
         WHERE NOT EXISTS (SELECT 1 FROM dim_player p WHERE p.player_id = r.player_id)
        UNION
        SELECT DISTINCT player_id FROM fact_draft_pick d
         WHERE player_id IS NOT NULL
           AND NOT EXISTS (SELECT 1 FROM dim_player p WHERE p.player_id = d.player_id)""")}
    if not missing:
        return 0
    rows = []
    for year in range(2014, 2018):
        path = f'{DATA}/player_pool_{year}.json'
        if not os.path.exists(path):
            continue
        for p in _json.load(open(path)):
            pid = p.get('id')
            if pid not in missing:
                continue
            name = (p.get('fullName') or '').strip()
            if not name:
                continue
            rows.append((pid, name, POS.get(p.get('defaultPositionId')), None, None, None))
            missing.discard(pid)
    con.executemany("""INSERT OR IGNORE INTO dim_player
        (player_id, name, position, gsis_id, otc_id, headshot_url) VALUES (?,?,?,?,?,?)""", rows)
    return len(rows)


def load_players_and_rosters(con):
    players, pseason, rws = {}, [], []
    for year in range(2014, 2026):
        box = load(f'{DATA}/box_{year}.json')
        if not box:
            continue
        for pid_s, v in box.get('players', {}).items():
            pid = int(pid_s)
            name, pos, nfl = v[0], v[1], (v[2] if len(v) > 2 else '')
            players.setdefault(pid, {'name': name, 'position': pos})
            pseason.append((year, pid, nfl))
        for wk_s, games in box.get('weeks', {}).items():
            wk = int(wk_s)
            for g in games:
                for side in ('home', 'away'):
                    s = g[side]
                    for pid, slot, pts in s['roster']:
                        rws.append((year, wk, s['tid'], pid, slot, pts,
                                    0 if slot in BENCH else 1))

    # nflverse ids + headshots, so contracts and box stats can join
    gsis, shots = {}, {}
    for year in range(2014, 2027):
        p = f'{DATA}/roster_{year}.csv'
        if not os.path.exists(p):
            continue
        for row in csv.DictReader(open(p)):
            eid = row.get('espn_id')
            if not eid:
                continue
            try:
                eid = int(eid)
            except ValueError:
                continue
            if row.get('gsis_id'):
                gsis[eid] = row['gsis_id']
            hs = row.get('headshot_url') or ''
            if hs and eid not in shots:
                shots[eid] = hs.replace('f_auto,q_auto',
                                        'c_fill,g_face,h_200,w_200,f_auto,q_auto')
            if eid not in players and (row.get('full_name') or '').strip():
                players[eid] = {'name': row['full_name'].strip(),
                                'position': (row.get('position') or '').strip()}

    otc = {}
    p = f'{DATA}/otc_players.csv'
    if os.path.exists(p):
        by_gsis = {r['gsis_id']: r['otc_id'] for r in csv.DictReader(open(p)) if r.get('gsis_id')}
        for eid, g in gsis.items():
            if g in by_gsis:
                otc[eid] = by_gsis[g]

    con.executemany("""INSERT OR REPLACE INTO dim_player
        (player_id, name, position, gsis_id, otc_id, headshot_url) VALUES (?,?,?,?,?,?)""",
        [(pid, v['name'], v['position'], gsis.get(pid), otc.get(pid), shots.get(pid))
         for pid, v in players.items()])
    con.executemany('INSERT OR REPLACE INTO player_season(season, player_id, nfl_team) VALUES (?,?,?)',
                    pseason)
    # a player can appear twice in a week if ESPN reports a mid-week move; keep the last
    con.executemany("""INSERT OR REPLACE INTO fact_roster_week
        (season, week, team_id, player_id, slot, points, started) VALUES (?,?,?,?,?,?,?)""", rws)
    # 2026 NFL rosters: no AFFL box yet. espn→gsis same as other years; D/ST stay without gsis.
    upsert_roster_players(con, 2026)
    fix_huntley_gsis(con)
    return len(players), len(rws)

def pairing_diagnostics(con, season):
    """Row / team / week / pairing gates. Week 15 with 10 teams is a bye, not a hole."""
    dim = con.execute(
        "SELECT team_count, reg_weeks, playoff_teams FROM dim_season WHERE season=?",
        (season,)).fetchone()
    team_count, reg_weeks, playoff_teams = dim if dim else (None, None, None)
    sides = con.execute("SELECT COUNT(*) FROM fact_matchup WHERE season=?", (season,)).fetchone()[0]
    team_ids = [r[0] for r in con.execute(
        "SELECT DISTINCT team_id FROM fact_matchup WHERE season=? ORDER BY 1", (season,))]
    weeks = [r[0] for r in con.execute(
        "SELECT DISTINCT week FROM fact_matchup WHERE season=? ORDER BY 1", (season,))]
    mirrors = con.execute("""
        SELECT COUNT(*) FROM fact_matchup a LEFT JOIN fact_matchup b
          ON b.season=a.season AND b.week=a.week AND b.team_id=a.opponent_id
         WHERE a.season=? AND b.team_id IS NULL""", (season,)).fetchone()[0]
    self_play = con.execute(
        "SELECT COUNT(*) FROM fact_matchup WHERE season=? AND team_id=opponent_id",
        (season,)).fetchone()[0]
    holes = []
    by_week = []
    for wk, n_sides, n_teams in con.execute("""
            SELECT week, COUNT(*), COUNT(DISTINCT team_id)
              FROM fact_matchup WHERE season=? GROUP BY week ORDER BY week""", (season,)):
        expected = team_count
        bye_week = (reg_weeks is not None and wk == reg_weeks + 1
                    and playoff_teams == 6 and team_count == 12)
        if bye_week:
            expected = 10
        by_week.append({"week": wk, "sides": n_sides, "teams": n_teams,
                        "games": n_sides // 2, "expected_teams": expected})
        if expected is not None and (n_teams != expected or n_sides != expected):
            holes.append({"week": wk, "sides": n_sides, "teams": n_teams,
                          "expected_teams": expected})
    if mirrors:
        holes.append({"kind": "missing_mirrors", "count": mirrors})
    if self_play:
        holes.append({"kind": "self_play", "count": self_play})
    bye_ids = []
    week15_note = None
    if reg_weeks is not None:
        w15 = {r[0] for r in con.execute(
            "SELECT DISTINCT team_id FROM fact_matchup WHERE season=? AND week=?",
            (season, reg_weeks + 1))}
        if team_ids and w15:
            bye_ids = [t for t in team_ids if t not in w15]
            if bye_ids:
                names = []
                for tid in bye_ids:
                    row = con.execute(
                        "SELECT name, final_rank FROM dim_team WHERE season=? AND team_id=?",
                        (season, tid)).fetchone()
                    if row:
                        names.append(f"#{row[1]} {row[0]}" if row[1] is not None else row[0])
                    else:
                        names.append(str(tid))
                week15_note = (
                    f"week {reg_weeks + 1} has {len(w15)} teams — first-round byes for "
                    + " and ".join(names) + ". Not a pairing hole."
                )
    return {
        "season": season,
        "sides": sides,
        "teams": len(team_ids),
        "team_ids": team_ids,
        "weeks": weeks,
        "week_min": weeks[0] if weeks else None,
        "week_max": weeks[-1] if weeks else None,
        "mirrors_missing": mirrors,
        "self_play": self_play,
        "bye_team_ids": bye_ids,
        "week15_note": week15_note,
        "holes": holes,
        "by_week": by_week,
    }


def import_matchups_season(con, season, data_dir=None):
    """Replace one season of fact_matchup from the versioned adapter. Idempotent."""
    data_dir = data_dir or DATA
    started = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    dim = con.execute("SELECT reg_weeks FROM dim_season WHERE season=?", (season,)).fetchone()
    payload = espn_box.extract(data_dir, season, reg_weeks=dim[0] if dim else None)
    rows = payload["rows"]
    if not rows:
        finished = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        diag = {"error": "no matchup rows extracted", "primary": payload.get("primary")}
        con.execute("""INSERT INTO meta_import_run
            (adapter, adapter_version, dataset, season, started_at, finished_at,
             status, row_count, diagnostics)
            VALUES (?,?,?,?,?,?,?,?,?)""",
            (payload["adapter"], payload["adapter_version"], "matchup", season,
             started, finished, "fail", 0, json.dumps(diag, sort_keys=True)))
        run_id = con.execute("SELECT last_insert_rowid()").fetchone()[0]
        for s in payload["sources"]:
            con.execute("""INSERT INTO meta_import_source (run_id, path, sha256, bytes)
                VALUES (?,?,?,?)""", (run_id, s["path"], s["sha256"], s["bytes"]))
        return 0
    con.execute("DELETE FROM fact_matchup WHERE season=?", (season,))
    con.executemany("""INSERT INTO fact_matchup
        (season, week, team_id, opponent_id, points, opponent_points, is_home, tier, is_playoff)
        VALUES (?,?,?,?,?,?,?,?,?)""", rows)
    diag = pairing_diagnostics(con, season)
    status = "ok" if not diag.get("holes") else "fail"
    finished = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    con.execute("""INSERT INTO meta_import_run
        (adapter, adapter_version, dataset, season, started_at, finished_at,
         status, row_count, diagnostics)
        VALUES (?,?,?,?,?,?,?,?,?)""",
        (payload["adapter"], payload["adapter_version"], "matchup", season,
         started, finished, status, len(rows), json.dumps(diag, sort_keys=True)))
    run_id = con.execute("SELECT last_insert_rowid()").fetchone()[0]
    for s in payload["sources"]:
        con.execute("""INSERT INTO meta_import_source (run_id, path, sha256, bytes)
            VALUES (?,?,?,?)""", (run_id, s["path"], s["sha256"], s["bytes"]))
    return len(rows)


def load_matchups(con):
    total = 0
    for year in range(2014, 2026):
        total += import_matchups_season(con, year)
    return total

def load_drafts(con):
    rows = []
    for year in range(2014, 2026):
        d = load(f'{DATA}/draft_{year}.json')
        if not d:
            continue
        for p in d['picks']:
            if p.get('overall') is None:
                continue
            rows.append((year, p['overall'], p.get('round'), p.get('pick'),
                         p['tid'], p.get('pid'), p.get('bid') or 0, int(bool(p.get('keeper')))))
    con.executemany("""INSERT OR REPLACE INTO fact_draft_pick
        (season, overall, round, pick_in_round, team_id, player_id, bid, is_keeper)
        VALUES (?,?,?,?,?,?,?,?)""", rows)
    return len(rows)

def load_transactions(con):
    """Only waiver/free-agent moves, attributed by the transaction ITEM (the team
    that actually gained or lost the player) rather than the executing team."""
    rows = []
    for year in range(2014, 2026):
        d = load(f'{DATA}/tx_{year}.json')
        if not d:
            continue
        for t in d['tx']:
            if t['type'] not in ('WAIVER', 'FREEAGENT'):
                continue
            for i in t.get('items') or []:
                pid = i.get('pid')
                if pid is None:
                    continue
                if i.get('to'):
                    rows.append((year, t['wk'], t.get('date'), t['type'], i['to'], pid, 'ADD', t.get('bid') or 0))
                if i.get('from'):
                    rows.append((year, t['wk'], t.get('date'), t['type'], i['from'], pid, 'DROP', 0))
    con.executemany("""INSERT INTO fact_transaction
        (season, week, ts, tx_type, team_id, player_id, direction, bid)
        VALUES (?,?,?,?,?,?,?,?)""", rows)
    return len(rows)

def load_trades(con):
    """TRADE_ACCEPT joined to TRADE_PROPOSAL via rel (from/to on the item,
    never executing team). One-sided ESPN rows are filled from the proposal or
    the paired item. 2014–17 have no tx log and are skipped. Empty ACCEPTs and
    the rest come from process_seasons reconstruction."""
    n_tr = n_it = 0
    seen = set()  # (year, pid, from, to, week) to avoid ACCEPT + recon dupes

    def add_trade(year, wk, ts, items):
        nonlocal n_tr, n_it
        rows = []
        for pid, frm, to in items:
            if pid is None or not frm or not to or frm == to:
                continue
            key = (year, pid, frm, to, wk)
            if key in seen:
                continue
            seen.add(key)
            rows.append((pid, frm, to))
        if not rows:
            return
        cur = con.execute('INSERT INTO fact_trade(season, week, ts) VALUES (?,?,?)',
                          (year, wk, ts))
        tid = cur.lastrowid
        n_tr += 1
        for pid, frm, to in rows:
            con.execute("""INSERT INTO fact_trade_item
                (trade_id, player_id, from_team_id, to_team_id) VALUES (?,?,?,?)""",
                (tid, pid, frm, to))
            n_it += 1

    for year in range(2018, 2026):
        d = load(f'{DATA}/tx_{year}.json')
        if not d:
            continue
        by_id = {t['id']: t for t in d.get('tx', []) if t.get('id')}
        seen_sets = set()
        for t in d.get('tx', []):
            if t.get('type') != 'TRADE_ACCEPT':
                continue
            wk = t.get('wk') or 1
            items = [(i.get('pid'), i.get('from'), i.get('to'))
                     for i in resolve_accept_items(t, by_id)]
            if not items:
                continue
            key = frozenset(items)
            if key in seen_sets:
                continue
            seen_sets.add(key)
            add_trade(year, wk, t.get('date'), items)

    for year in range(2018, 2026):
        bundle = load(os.path.join(SITE, 'years', f'{year}.json'))
        if not bundle:
            continue
        for tr in bundle.get('trades', []):
            items = []
            sides = tr.get('sides') or []
            other = {s['tid'] for s in sides}
            for s in sides:
                to_team = s['tid']
                for g in s.get('got') or []:
                    pid = g.get('pid')
                    frm = g.get('from')
                    if frm is None:
                        frm = next((o for o in other if o != to_team), None)
                    items.append((pid, frm, to_team))
            add_trade(year, tr['wk'], tr.get('date'), items)
    return n_tr, n_it

def load_nfl_weeks(con):
    rows = []
    for year in range(2014, 2026):
        p = f'{DATA}/stats_player_week_{year}.csv'
        if not os.path.exists(p):
            continue
        for r in csv.DictReader(open(p)):
            if r.get('season_type') != 'REG':
                continue
            try:
                wk = int(r['week'])
            except (ValueError, KeyError):
                continue
            rows.append((year, wk, r['player_id'], r.get('opponent_team'),
                         fnum(r, 'passing_yards'), fnum(r, 'passing_tds'),
                         fnum(r, 'completions'), fnum(r, 'attempts'),
                         fnum(r, 'rushing_yards'), fnum(r, 'rushing_tds'), fnum(r, 'carries'),
                         fnum(r, 'receiving_yards'), fnum(r, 'receiving_tds'),
                         fnum(r, 'receptions'), fnum(r, 'targets'),
                         fnum(r, 'receiving_air_yards'), fnum(r, 'target_share'), fnum(r, 'wopr'),
                         fnum(r, 'passing_epa') + fnum(r, 'rushing_epa') + fnum(r, 'receiving_epa'),
                         fnum(r, 'passing_interceptions'),
                         fnum(r, 'sack_fumbles_lost') + fnum(r, 'rushing_fumbles_lost')
                           + fnum(r, 'receiving_fumbles_lost'),
                         fnum(r, 'passing_2pt_conversions') + fnum(r, 'rushing_2pt_conversions')
                           + fnum(r, 'receiving_2pt_conversions'),
                         fnum(r, 'sacks_suffered'), fnum(r, 'air_yards_share'),
                         fnum(r, 'racr'), fnum(r, 'pacr')))
    con.executemany("""INSERT OR REPLACE INTO fact_nfl_week
        (season, week, gsis_id, opponent, pass_yards, pass_tds, completions, attempts,
         rush_yards, rush_tds, carries, rec_yards, rec_tds, receptions, targets,
         air_yards, target_share, wopr, epa,
         interceptions, fumbles_lost, two_pt, sacks_suffered, air_yards_share, racr, pacr)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", rows)
    return len(rows)

def load_contracts(con):
    p = f'{DATA}/historical_contracts.csv'
    if not os.path.exists(p):
        return 0
    otc_to_gsis = {}
    op = f'{DATA}/otc_players.csv'
    if os.path.exists(op):
        otc_to_gsis = {r['otc_id']: r['gsis_id'] for r in csv.DictReader(open(op)) if r.get('gsis_id')}
    rows = []
    for r in csv.DictReader(open(p)):
        def num(k):
            try:
                return float(r[k]) if r.get(k) not in (None, '', 'NA') else None
            except ValueError:
                return None
        rows.append((r.get('otc_id'), otc_to_gsis.get(r.get('otc_id')),
                     r['player'], r.get('position'), r.get('team'),
                     int(r['year_signed']) if (r.get('year_signed') or '').isdigit() else None,
                     int(r['years']) if (r.get('years') or '').isdigit() else None,
                     num('value'), num('apy'), num('guaranteed'), num('apy_cap_pct'),
                     1 if r.get('is_active') == 'TRUE' else 0))
    con.executemany("""INSERT INTO fact_contract
        (otc_id, gsis_id, player_name, position, nfl_team, year_signed, years,
         value, apy, guaranteed, apy_cap_pct, is_active)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""", rows)
    return len(rows)

def load_cap_hits(con):
    """Spotrac cap tables. Resolve each row to an ESPN player_id by name within
    the same NFL team + season, which is how the AFFL roster join happens."""
    import glob, re

    def norm(n):
        n = (n or '').lower()
        n = re.sub(r"[.'`\u2019]", '', n)
        n = re.sub(r'\s+(jr|sr|ii|iii|iv|v)$', '', n)
        return re.sub(r'\s+', ' ', n).strip()

    total = matched = 0
    for path in sorted(glob.glob(f'{DATA}/cap_*.json')):
        season = int(os.path.basename(path).split('_')[1].split('.')[0])
        # espn players active that season, indexed by (nfl_team, normalised name)
        idx, by_name = {}, defaultdict(list)
        for pid, name, team in con.execute("""
                SELECT p.player_id, p.name, ps.nfl_team
                  FROM dim_player p JOIN player_season ps
                    ON ps.player_id = p.player_id AND ps.season = ?""", (season,)):
            idx[(team or '', norm(name))] = pid
            by_name[norm(name)].append(pid)

        rows = []
        for r in json.load(open(path)):
            key = (r['nfl_team'], norm(r['player_name']))
            pid = idx.get(key)
            if pid is None:
                # fall back to a league-wide unique name (handles mid-season trades)
                cands = by_name.get(norm(r['player_name']) or '', [])
                pid = cands[0] if len(cands) == 1 else None
            if pid is not None:
                matched += 1
            rows.append((season, r['nfl_team'], r['player_name'], pid, r.get('position'),
                         r.get('cap_hit'), r.get('base_salary'), r.get('signing_bonus'),
                         r.get('dead_cap'), r.get('cap_pct')))
        total += len(rows)
        con.executemany("""INSERT OR REPLACE INTO fact_cap_hit
            (season, nfl_team, player_name, player_id, position, cap_hit,
             base_salary, signing_bonus, dead_cap, cap_pct)
            VALUES (?,?,?,?,?,?,?,?,?,?)""", rows)
    return total, matched

STAT_NAMES = {
    0: 'passAtt', 1: 'passComp', 3: 'passYds', 4: 'passTD', 19: 'pass2pt', 20: 'passInt',
    23: 'rushAtt', 24: 'rushYds', 25: 'rushTD', 26: 'rush2pt',
    41: 'recTgt', 42: 'recYds', 43: 'recTD', 44: 'rec2pt', 53: 'rec',
    63: 'fumRecTD', 72: 'fumLost',
    74: 'fg0_39', 77: 'fg40_49', 80: 'fg50', 85: 'fgMiss', 86: 'xp', 88: 'xpMiss',
    89: 'ptsAllowed0', 90: 'ptsAllowed1_6', 91: 'ptsAllowed7_13', 92: 'ptsAllowed14_17',
    93: 'defTD', 95: 'defInt', 96: 'defFumRec', 97: 'defBlk', 98: 'defSaf', 99: 'defSack',
    101: 'krTD', 102: 'prTD', 103: 'fumRetTD', 104: 'intRetTD',
    120: 'ptsAllowed28_34', 121: 'ptsAllowed35_45', 122: 'ptsAllowed46plus',
    123: 'ptsAllowed18_21', 124: 'ptsAllowed22_27',
    198: 'yardsAllowedBucket', 201: 'defTD2', 206: 'misc206', 209: 'misc209',
}

def load_scoring(con):
    """Scoring changes between seasons, so this is keyed by season and is the
    basis for recomputing points from raw stats (needed for pre-2018)."""
    rows = []
    for year in range(2014, 2026):
        d = load(f'{DATA}/settings_{year}.json')
        if not d:
            continue
        sc = ((d.get('settings') or {}).get('scoringSettings') or {})
        for it in sc.get('scoringItems', []):
            pts = it.get('points') or 0
            if pts:
                rows.append((year, it['statId'], STAT_NAMES.get(it['statId']), pts))
    con.executemany("""INSERT OR REPLACE INTO dim_scoring
        (season, stat_id, stat_name, points) VALUES (?,?,?,?)""", rows)

    # ESPN's stored 2018 settings omit the yardage rules (statIds 3/24/42) even
    # though the league clearly used them -- recomputed points come out ~6-19
    # short without them. Backfill from the nearest season that has them; the
    # validation script proves the assumption (2018 goes 0.6% -> 99%+ exact).
    have = {(s, sid) for s, sid in con.execute('SELECT season, stat_id FROM dim_scoring')}
    seasons = [r[0] for r in con.execute('SELECT season FROM dim_season ORDER BY season')]
    scored = {s for s, _ in have}
    filled = 0
    for season in seasons:
        if season not in scored and not os.path.exists(os.path.join(DATA, f'settings_{season}.json')):
            continue
        for sid in (3, 24, 42):
            if (season, sid) in have:
                continue
            donor = min((s for s in seasons if (s, sid) in have),
                        key=lambda s: (abs(s - season), s), default=None)
            if donor is None:
                continue
            pts, name = con.execute(
                'SELECT points, stat_name FROM dim_scoring WHERE season=? AND stat_id=?',
                (donor, sid)).fetchone()
            con.execute("""INSERT OR REPLACE INTO dim_scoring
                (season, stat_id, stat_name, points) VALUES (?,?,?,?)""",
                (season, sid, name, pts))
            filled += 1
    if filled:
        print(f'    backfilled {filled} missing yardage rules from neighbouring seasons')

    # 2018 and earlier floor yardage to whole points; 2019+ is fractional.
    # Proven empirically -- see validate_scoring.py (2018: 96.2% exact bucketed
    # vs 6.6% fractional; 2019: the reverse).
    con.execute("UPDATE dim_season SET yardage_mode = 'BUCKET'     WHERE season <= 2018")
    con.execute("UPDATE dim_season SET yardage_mode = 'FRACTIONAL' WHERE season >= 2019")
    return len(rows) + filled

def load_player_season_points(con):
    """Season fantasy totals per player: ESPN's own where lineups exist, computed
    from nflverse under dim_scoring where they don't (pre-2018).

    Materialised because the equivalent view -- correlated subqueries over 208k
    player-weeks -- made the site export take minutes.
    """
    modes = dict(con.execute('SELECT season, yardage_mode FROM dim_season'))
    rules = defaultdict(dict)
    for season, sid, pts in con.execute('SELECT season, stat_id, points FROM dim_scoring'):
        rules[season][sid] = pts

    # 1) actual, from ESPN's own weekly points.
    #
    # Only for seasons with FULL rosters. 2014-2017 hold recovered STARTERS, so
    # summing them gives what a player scored in the weeks he was started, not what
    # he scored that season - Jamaal Charles 2014 came out at 197.0 over 13 starts
    # and displaced his real nflverse total. Because a row here suppresses the
    # computed one below, that silently turned every pre-2018 season total into a
    # partial and corrupted the draft PAR built on top of it. has_rosters is exactly
    # the "full rosters incl. bench" flag, so gate on it. See CONTRACTS.md.
    actual = {}
    for season, pid, tot in con.execute("""
            SELECT r.season, r.player_id, ROUND(SUM(r.points), 1)
              FROM fact_roster_week r
              JOIN dim_season s ON s.season = r.season AND s.has_rosters = 1
             GROUP BY r.season, r.player_id"""):
        actual[(season, pid)] = tot

    # 2) computed, for skill players in seasons with no lineups
    gsis_to_pid = {}
    for pid, g, pos in con.execute(
            "SELECT player_id, gsis_id, position FROM dim_player WHERE gsis_id IS NOT NULL"):
        if pos in ('QB', 'RB', 'WR', 'TE'):
            gsis_to_pid[g] = pid

    computed = defaultdict(float)
    for row in con.execute("""
            SELECT season, gsis_id, pass_yards, pass_tds, interceptions, rush_yards,
                   rush_tds, rec_yards, rec_tds, receptions, fumbles_lost, two_pt
              FROM fact_nfl_week"""):
        season, g = row[0], row[1]
        pid = gsis_to_pid.get(g)
        if pid is None:
            continue
        k = rules.get(season, {})
        py, pt, i, ry, rt, cy, ct, rc, fl, tp = row[2:]
        if modes.get(season) == 'BUCKET':
            yards = int(py // 25) + int(ry // 10) + int(cy // 10)
        else:
            yards = py * k.get(3, 0) + ry * k.get(24, 0) + cy * k.get(42, 0)
        computed[(season, pid)] += (yards + pt * k.get(4, 0) + i * k.get(20, 0)
                                   + rt * k.get(25, 0) + ct * k.get(43, 0)
                                   + rc * k.get(53, 0) + fl * k.get(72, 0)
                                   + tp * k.get(26, 0))

    rows = [(s, p, t, 0) for (s, p), t in actual.items()]
    rows += [(s, p, round(t, 1), 1) for (s, p), t in computed.items()
             if (s, p) not in actual]
    con.executemany("""INSERT OR REPLACE INTO fact_player_season_points
        (season, player_id, total_points, is_computed) VALUES (?,?,?,?)""", rows)
    return sum(1 for r in rows if not r[3]), sum(1 for r in rows if r[3])

# ---------------------------------------------------------------- verification
CHECKS = [
    ("seasons", "SELECT COUNT(*) FROM dim_season"),
    ("members", "SELECT COUNT(*) FROM dim_member"),
    ("franchise-seasons", "SELECT COUNT(*) FROM dim_team"),
    ("players", "SELECT COUNT(*) FROM dim_player"),
    ("players w/ gsis", "SELECT COUNT(*) FROM dim_player WHERE gsis_id IS NOT NULL"),
    ("roster-weeks", "SELECT COUNT(*) FROM fact_roster_week"),
    ("matchup sides", "SELECT COUNT(*) FROM fact_matchup"),
    ("draft picks", "SELECT COUNT(*) FROM fact_draft_pick"),
    ("transactions", "SELECT COUNT(*) FROM fact_transaction"),
    ("trades", "SELECT COUNT(*) FROM fact_trade"),
    ("nfl player-weeks", "SELECT COUNT(*) FROM fact_nfl_week"),
    ("contracts", "SELECT COUNT(*) FROM fact_contract"),
    ("scoring rules", "SELECT COUNT(*) FROM dim_scoring"),
    ("player-seasons", "SELECT COUNT(*) FROM fact_player_season_points"),
    ("cap hits", "SELECT COUNT(*) FROM fact_cap_hit"),
    ("owners", "SELECT COUNT(*) FROM dim_owner"),
    ("player-week PAR", "SELECT COUNT(*) FROM fact_player_week_par"),
    ("reconstructed PAR", "SELECT COUNT(*) FROM fact_player_season_par_reconstructed"),
    ("xTD player-weeks", "SELECT COUNT(*) FROM fact_xtd_player_week"),
    ("projections", "SELECT COUNT(*) FROM fact_projection_week"),
    ("import runs", "SELECT COUNT(*) FROM meta_import_run"),
    ("ngs", "SELECT COUNT(*) FROM fact_ngs"),
    ("player bio", "SELECT COUNT(*) FROM dim_player_bio"),
    ("injuries", "SELECT COUNT(*) FROM fact_injury"),
    ("depth charts", "SELECT COUNT(*) FROM fact_depthchart"),
    ("college", "SELECT COUNT(*) FROM fact_college"),
    ("player overview", "SELECT COUNT(*) FROM fact_player_overview"),
]


INTEGRITY = [
    ("every matchup side has a mirror",
     """SELECT COUNT(*) FROM fact_matchup a LEFT JOIN fact_matchup b
          ON b.season=a.season AND b.week=a.week AND b.team_id=a.opponent_id
        WHERE b.team_id IS NULL"""),
    ("no roster row points to an unknown team",
     """SELECT COUNT(*) FROM fact_roster_week r LEFT JOIN dim_team t
          ON t.season=r.season AND t.team_id=r.team_id WHERE t.team_id IS NULL"""),
    ("no roster row points to an unknown player",
     """SELECT COUNT(*) FROM fact_roster_week r LEFT JOIN dim_player p
          ON p.player_id=r.player_id WHERE p.player_id IS NULL"""),
    # The pre-2018 recovery is irreplaceable: ESPN no longer serves these lineups
    # anywhere else, and wipe() clears the table every run. If a rebuild ever drops
    # below the recovered count, it has destroyed data — fail the build, loudly.
    # The snapshot is the only pre-2018 bench that exists anywhere. Same reasoning
    # as the starter floor below: silence is not proof it survived a rebuild.
    ("2014-2017 roster snapshots recovered (>= 659)",
     """SELECT CASE WHEN COUNT(*) >= 659 THEN 0 ELSE 659 - COUNT(*) END
          FROM fact_roster_snapshot_pre2018"""),
    # Dating proves recovered-starters ⊆ snapshot non-bench, not equality: two 2015
    # team-weeks are placed by containment because ESPN truncated their lineups
    # (lineup_complete = 0), leaving the snapshot holding starters the week lost.
    # Asserting equality would fail those two for being MORE complete.
    ("every recovered starter appears in its dated snapshot",
     """SELECT COUNT(*) FROM fact_roster_week r
           JOIN (SELECT DISTINCT season, team_id, dated_week
                   FROM fact_roster_snapshot_pre2018
                  WHERE dated_week IS NOT NULL) d
             ON d.season = r.season AND d.team_id = r.team_id
            AND d.dated_week = r.week
          WHERE r.started = 1
            AND NOT EXISTS (SELECT 1 FROM fact_roster_snapshot_pre2018 s
                             WHERE s.season = r.season AND s.team_id = r.team_id
                               AND s.player_id = r.player_id
                               AND s.started = 1)"""),
    ("2014-2017 starters recovered (>= 4888)",
     """SELECT CASE WHEN COUNT(*) >= 4888 THEN 0 ELSE 4888 - COUNT(*) END
          FROM fact_roster_week WHERE season BETWEEN 2014 AND 2017"""),
    ("every complete pre-2018 lineup still sums to ESPN's score",
     """SELECT COUNT(*) FROM (
          SELECT r.season, r.week, r.team_id
            FROM fact_roster_week r
            JOIN fact_matchup m ON m.season=r.season AND m.week=r.week
                               AND m.team_id=r.team_id
           WHERE r.season BETWEEN 2014 AND 2017 AND r.lineup_complete = 1
           GROUP BY r.season, r.week, r.team_id
          HAVING ABS(SUM(r.points) - m.points) > 0.01)"""),
    ("no ESPN SWID leaked into member ids",
     "SELECT COUNT(*) FROM dim_member WHERE member_id LIKE '{%'"),
    ("every member maps to an owner",
     "SELECT COUNT(*) FROM dim_member WHERE owner_id IS NULL"),
    ("every team-season has an owner",
     """SELECT COUNT(*) FROM dim_team t LEFT JOIN dim_member m
          ON m.member_id = t.member_id
        WHERE m.owner_id IS NULL"""),
    ("2025 regular matchup weeks are complete pairings",
     """SELECT COUNT(*) FROM (
          SELECT m.week FROM fact_matchup m
          JOIN dim_season s ON s.season = m.season
         WHERE m.season = 2025 AND m.is_playoff = 0
         GROUP BY m.week, s.team_count
        HAVING COUNT(DISTINCT m.team_id) != s.team_count
            OR COUNT(*) != s.team_count
        )"""),
]

def check(con):
    print('== row counts ==')
    for label, q in CHECKS:
        print(f'  {label:20} {con.execute(q).fetchone()[0]:>9,}')
    print('== integrity (all must be 0) ==')
    ok = True
    for label, q in INTEGRITY:
        n = con.execute(q).fetchone()[0]
        flag = 'ok' if n == 0 else 'FAIL'
        if n:
            ok = False
        print(f'  [{flag}] {label:44} {n}')
    return ok

def _try_xtd(con):
    """Use pbp already on disk. Downloads happen in compute_xtd.py, not here."""
    pbp_dir = os.path.join(DATA, 'pbp')
    have = os.path.isdir(pbp_dir) and any(
        n.startswith('play_by_play_') and n.endswith('.csv.gz')
        for n in os.listdir(pbp_dir))
    if not have:
        return 0, 'no pbp on disk — run python3 compute_xtd.py'
    import compute_xtd
    n = 0
    for y in range(2014, 2026):
        path, status = compute_xtd.ensure_pbp(y, download=False)
        if path is None:
            continue
        rows, _plays = compute_xtd.fit_and_score(path)
        if rows:
            n += compute_xtd.persist(con, rows)
    return n, 'ok'


def main():
    if '--check' in sys.argv:
        con = sqlite3.connect(DB)
        sys.exit(0 if check(con) else 1)

    if '--import-matchups' in sys.argv:
        i = sys.argv.index('--import-matchups')
        season = 2025
        if i + 1 < len(sys.argv) and not sys.argv[i + 1].startswith('-'):
            season = int(sys.argv[i + 1])
        con = sqlite3.connect(DB)
        init(con)
        n = import_matchups_season(con, season)
        con.commit()
        run = con.execute("""
            SELECT adapter, adapter_version, status, diagnostics
              FROM meta_import_run
             WHERE dataset='matchup' AND season=?
             ORDER BY run_id DESC LIMIT 1""", (season,)).fetchone()
        srcs = con.execute("""
            SELECT path, sha256, bytes FROM meta_import_source
             WHERE run_id = (SELECT MAX(run_id) FROM meta_import_run
                              WHERE dataset='matchup' AND season=?)""", (season,)).fetchall()
        print(f'matchup import {season}: {n} sides')
        if run:
            print(f'  adapter {run[0]} {run[1]}  status={run[2]}')
            for path, sha, b in srcs:
                print(f'  source {path} sha256={sha} bytes={b}')
            diag = json.loads(run[3] or '{}')
            print(f'  teams {diag.get("teams")} weeks {diag.get("week_min")}-{diag.get("week_max")} holes {len(diag.get("holes") or [])}')
            if diag.get("week15_note"):
                print(f'  {diag["week15_note"]}')
        sys.exit(0 if run and run[2] == 'ok' else 1)

    site = json.load(open(os.path.join(SITE, 'data.json')))
    fresh = not os.path.exists(DB)
    con = sqlite3.connect(DB)
    init(con)
    wipe(con)

    load_seasons_and_teams(con, site)
    # CHI-75: never load a fake AFFL 2026 season. Site CURRENT_2026 is nav only.
    stripped = refuse_affl_2026_season(con)
    print(f'  AFFL 2026 season rows stripped (CHI-75): {stripped}')
    import contracts
    print(f'  owners {contracts.apply_owners(con):,}')
    print(f'  scoring rules {load_scoring(con):,}')
    npl, nrw = load_players_and_rosters(con)
    print(f'  players {npl:,} · roster-weeks {nrw:,}')
    print(f'  matchup sides {load_matchups(con):,}')
    print(f'  draft picks {load_drafts(con):,}')
    print(f'  transactions {load_transactions(con):,}')
    # wipe() clears fact_roster_week, and ESPN's pre-2018 starters do not come from
    # the box files the loader above reads — they are recovered from data/box_raw.
    # Without this call a rebuild silently destroys 2014-2017. Runs after matchups
    # and drafts because it reconciles against both.
    # Two additive tables ESPN kept but nothing used to read, both out of
    # league_YYYY.json. They must load BEFORE the pre-2018 recovery:
    # load_pre2018_lineups reads fact_team_scoring_period to know which matchup
    # periods span two NFL weeks, and without it the recovery cannot run at all.
    # Neither table was in schema.sql or this script until now - they survived only
    # because nothing wiped them, so a clean checkout could not rebuild 2014-2017.
    import load_scoring_periods, load_transaction_counts
    print(f'  team scoring periods {load_scoring_periods.load(con, write=True):,}')
    print(f'  acquisition counts {load_transaction_counts.load(con, write=True):,}')
    import load_pre2018_lineups
    print(f'  pre-2018 starters {load_pre2018_lineups.load(con, write=True):,}')
    # The same payloads carry a full late-season roster per team, bench included,
    # in a different block. It is one snapshot rather than a weekly series, so it
    # gets its own table - merging it into fact_roster_week would make 282 bench
    # rows look like weeks ESPN never returned. Runs after the starter load, which
    # is what dates it.
    import load_pre2018_bench
    print(f'  pre-2018 roster snapshots {load_pre2018_bench.load(con, write=True):,}')
    print(f'  pool-only players named {backfill_pool_players(con):,}')
    tr, it = load_trades(con)
    print(f'  trades {tr:,} ({it:,} items)')
    print(f'  nfl player-weeks {load_nfl_weeks(con):,}')
    print(f'  contracts {load_contracts(con):,}')
    na, nc = load_player_season_points(con)
    print(f'  player-seasons {na + nc:,} ({nc:,} computed from NFL stats)')
    ncap, nmatch = load_cap_hits(con)
    print(f'  cap hits {ncap:,} ({nmatch:,} resolved to an AFFL-known player)')
    import contracts
    print(f'  player-week PAR {contracts.load_player_week_par(con):,}')
    print(f'  reconstructed draft PAR {contracts.load_reconstructed_par(con):,}')
    import fetch_projections
    n_espn, n_fp = fetch_projections.load_into(con)
    print(f'  projections espn={n_espn:,} fantasypros={n_fp:,}')
    nx, xmsg = _try_xtd(con)
    print(f'  xTD player-weeks {nx:,} ({xmsg})')
    import compute_roto
    print(f'  roto team-seasons {compute_roto.compute_all(con):,}')
    con.commit()
    con.execute('ANALYZE')
    con.commit()
    print(f'\naffl.db {"created" if fresh else "rebuilt"} — {os.path.getsize(DB)/1048576:.1f} MB')
    check(con)

if __name__ == '__main__':
    main()
