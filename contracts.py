#!/usr/bin/env python3
"""Identity map, custody PAR, reconstructed draft PAR.

Called from build_db.py after the core facts are loaded. Safe to re-run
on an already-built warehouse:

    python3 -c "import sqlite3, contracts; c=sqlite3.connect('affl.db'); print(contracts.apply_all(c)); c.commit()"
"""
from collections import defaultdict

# ESPN member_id is not the person. Kafka used two slots; Sliger m03 and
# Dunn m20 are orphans with no team-seasons. Map onto dim_owner. Do not
# delete the member rows. Canonical Kafka id is m07 (site merge m01→m07).
OWNER_OF = {
    "m01": "m07",  # Jason Kafka 2017–23 → Chupacabras / 2026 current
    "m03": "m08",  # Kevin Sliger orphan
    "m20": "m10",  # Tanner Dunn orphan
}


def apply_owners(con):
    members = list(con.execute(
        "SELECT member_id, display_name, is_active FROM dim_member"))
    by_id = {mid: (name, active) for mid, name, active in members}
    owner_of = {mid: OWNER_OF.get(mid, mid) for mid, _, _ in members}
    owners = {}
    for mid, oid in owner_of.items():
        if oid not in owners:
            owners[oid] = list(by_id[oid] if oid in by_id else by_id[mid])
        else:
            owners[oid][1] = max(owners[oid][1], by_id[mid][1])
    # Rebuild so a flipped merge (m07→m01 becoming m01→m07) does not leave
    # the old canonical row sitting around.
    con.execute("DELETE FROM dim_owner")
    con.executemany(
        "INSERT INTO dim_owner(owner_id, display_name, is_active) VALUES (?,?,?)",
        [(oid, n, a) for oid, (n, a) in owners.items()])
    con.executemany(
        "UPDATE dim_member SET owner_id = ? WHERE member_id = ?",
        [(oid, mid) for mid, oid in owner_of.items()])
    return len(owners)


def _classify_factory(con):
    """Most recent acquisition event at or before the roster week.

    Four buckets only: Drafted, Traded in, Waiver, FA.
    A recorded ADD (waiver vs FA) or trade-in wins. Drafted only on the
    team that bought them. Drafted → dropped → added is FA or Waiver
    when the ADD exists — never a trade just because someone else drafted them.
    No event on this team: roster jump from another team, or a post-draft
    pre-week-1 move (drafted by someone who never rostered them) → Traded in.
    Otherwise FA.
    """
    events = defaultdict(list)
    drafted_by = {}
    for s, tid, pid in con.execute(
            "SELECT season, team_id, player_id FROM fact_draft_pick "
            "WHERE player_id IS NOT NULL"):
        events[(s, tid, pid)].append((0, "Drafted", 1))
        drafted_by[(s, pid)] = tid
    for s, tid, pid, wk in con.execute(
            "SELECT t.season, i.to_team_id, i.player_id, t.week "
            "FROM fact_trade_item i "
            "JOIN fact_trade t ON t.trade_id = i.trade_id"):
        events[(s, tid, pid)].append((wk, "Traded in", 3))
    for s, tid, pid, wk, tx in con.execute(
            "SELECT season, team_id, player_id, week, tx_type "
            "FROM fact_transaction WHERE direction = 'ADD'"):
        label = "Waiver" if tx == "WAIVER" else "FA"
        events[(s, tid, pid)].append((wk if wk is not None else 1, label, 2))

    prior = defaultdict(list)
    for s, pid, tid, wk in con.execute(
            "SELECT season, player_id, team_id, week FROM fact_roster_week"):
        prior[(s, pid)].append((wk, tid))

    def classify(season, team_id, player_id, week):
        cands = [e for e in events.get((season, team_id, player_id), [])
                 if e[0] <= week]
        if cands:
            return max(cands, key=lambda e: (e[0], e[2]))[1]
        for wk, tid in prior.get((season, player_id), []):
            if wk < week and tid != team_id:
                return "Traded in"
        other = drafted_by.get((season, player_id))
        if other and other != team_id:
            return "Traded in"
        return "FA"
    return classify


def load_player_week_par(con):
    """Weekly custody PAR for seasons that have lineups (2018-2025).

    replacement(pos, season) is the Nth-best season total at the position
    (v_replacement_level). Weekly PAR subtracts that number divided by the
    number of distinct roster weeks that season, so a full-season hold of
    the replacement player nets ~0. Started and benched both count.
    """
    con.execute("DELETE FROM fact_player_week_par")
    repl = {(s, pos): pts for s, pos, pts in con.execute(
        "SELECT season, position, replacement_points FROM v_replacement_level")}
    nweeks = dict(con.execute(
        "SELECT season, COUNT(DISTINCT week) FROM fact_roster_week GROUP BY season"))
    classify = _classify_factory(con)
    rows = []
    for s, wk, tid, pid, pts, started, pos in con.execute(
            "SELECT r.season, r.week, r.team_id, r.player_id, r.points, r.started, "
            "CASE "
            "  WHEN p.position IN ('QB','RB','WR','TE','K','DST') THEN p.position "
            "  WHEN p.position = 'FB' THEN 'RB' "
            "  WHEN r.slot IN ('QB','RB','WR','TE','K') THEN r.slot "
            "  WHEN r.slot IN ('D/ST','DST') THEN 'DST' "
            "  ELSE NULL END "
            "FROM fact_roster_week r "
            "JOIN dim_player p ON p.player_id = r.player_id"):
        nw = nweeks.get(s) or 0
        rp = repl.get((s, pos)) if pos else None
        weekly = (rp / nw) if (rp is not None and nw) else None
        par = (pts - weekly) if weekly is not None else None
        rows.append((s, wk, pid, tid, pts, par, started,
                     classify(s, tid, pid, wk), pos))
    con.executemany(
        "INSERT OR REPLACE INTO fact_player_week_par "
        "(season, week, player_id, team_id, points, par, started, acquisition, position) "
        "VALUES (?,?,?,?,?,?,?,?,?)", rows)
    return len(rows)


def load_reconstructed_par(con):
    """2014-2017 season draft PAR. Weekly custody PAR is unavailable."""
    con.execute("DELETE FROM fact_player_season_par_reconstructed")
    rows = list(con.execute(
        "SELECT dp.season, dp.team_id, dp.player_id, p.position, "
        "ps.total_points, ps.total_points - rl.replacement_points, 'Drafted' "
        "FROM fact_draft_pick dp "
        "JOIN dim_player p ON p.player_id = dp.player_id "
        "JOIN fact_player_season_points ps "
        "  ON ps.season = dp.season AND ps.player_id = dp.player_id "
        "JOIN v_replacement_level rl "
        "  ON rl.season = dp.season AND rl.position = p.position "
        "WHERE dp.season <= 2017 AND rl.replacement_points IS NOT NULL"))
    con.executemany(
        "INSERT OR REPLACE INTO fact_player_season_par_reconstructed "
        "(season, team_id, player_id, position, points, par, acquisition) "
        "VALUES (?,?,?,?,?,?,?)", rows)
    return len(rows)


def apply_all(con):
    n_own = apply_owners(con)
    n_par = load_player_week_par(con)
    n_rec = load_reconstructed_par(con)
    return n_own, n_par, n_rec
