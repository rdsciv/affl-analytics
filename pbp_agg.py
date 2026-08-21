#!/usr/bin/env python3
"""Roll nflverse / nflfastR play-by-play down to player-week facts.

Savant's UI is a Cloudflare front-end over the same public PBP. We read the
nflverse release files (csv.gz) and never keep play grain in the warehouse.

xTD is opportunity-based: P(TD | yardline bucket, play_type) fit on that
season's regular-season pass/run plays, then summed onto the passer / rusher /
receiver. Receptions are counted as volume only — AFFL is non-PPR.
"""
import csv
import gzip
import os
from collections import defaultdict

PBP_COLS = (
    'season', 'week', 'season_type', 'play_type', 'two_point_attempt',
    'passer_player_id', 'rusher_player_id', 'receiver_player_id',
    'complete_pass', 'pass_attempt', 'rush_attempt', 'sack',
    'air_yards', 'epa', 'success', 'cpoe',
    'yardline_100', 'touchdown', 'pass_touchdown', 'rush_touchdown',
    'xyac_mean_yardage',
)

# Laplace-smoothed seasonal TD rates stay stable in sparse red-zone cells.
XTD_PRIOR = 0.5
XTD_STRENGTH = 1.0


def fnum(v):
    if v in (None, '', 'NA', 'na', 'nan', 'NaN', 'None'):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def fnum0(v):
    n = fnum(v)
    return 0.0 if n is None else n


def truthy(v):
    if v in (None, '', 'NA', 'na', 'nan', 'NaN', 'None', '0', '0.0', 'FALSE',
             'False', 'false'):
        return False
    if v in (1, 1.0, True, '1', '1.0', 'TRUE', 'True', 'true'):
        return True
    try:
        return float(v) != 0.0
    except (TypeError, ValueError):
        return False


def yardline_bucket(yl):
    if yl is None:
        return None
    yl = float(yl)
    if yl <= 2:
        return '1-2'
    if yl <= 5:
        return '3-5'
    if yl <= 10:
        return '6-10'
    if yl <= 20:
        return '11-20'
    if yl <= 30:
        return '21-30'
    if yl <= 50:
        return '31-50'
    return '51+'


def ptd(counts, key):
    plays, tds = counts.get(key, (0, 0))
    return (tds + XTD_PRIOR) / (plays + XTD_STRENGTH)


def _open_pbp(path):
    if path.endswith('.gz'):
        return gzip.open(path, 'rt', encoding='utf-8', newline='')
    return open(path, 'rt', encoding='utf-8', newline='')


def _keep_play(row):
    if (row.get('season_type') or 'REG') != 'REG':
        return False
    if truthy(row.get('two_point_attempt')):
        return False
    return row.get('play_type') in ('pass', 'run')


def _iter_pbp(path):
    with _open_pbp(path) as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            if _keep_play(row):
                yield row


def fit_xtd_rates(path):
    """P(TD | season, play_type, yardline_bucket) from one season's PBP file."""
    counts = defaultdict(lambda: [0, 0])
    season = None
    for row in _iter_pbp(path):
        if season is None:
            try:
                season = int(float(row['season']))
            except (KeyError, TypeError, ValueError):
                continue
        ptype = row.get('play_type')
        bucket = yardline_bucket(fnum(row.get('yardline_100')))
        if bucket is None:
            continue
        scored = truthy(row.get('pass_touchdown') if ptype == 'pass'
                        else row.get('rush_touchdown'))
        if not scored:
            scored = truthy(row.get('touchdown')) and ptype in ('pass', 'run')
        key = (season, ptype, bucket)
        counts[key][0] += 1
        counts[key][1] += int(scored)
    return {k: ptd(counts, k) for k in counts}


def _blank_agg():
    return {
        'dropbacks': 0.0, 'pass_attempts': 0.0, 'completions': 0.0,
        'pass_epa': 0.0, 'cpoe_sum': 0.0, 'cpoe_n': 0.0,
        'pass_air_yards': 0.0, 'pass_success': 0.0, 'pass_success_n': 0.0,
        'pass_td': 0.0, 'pass_xtd': 0.0, 'rz_pass': 0.0, 'gl_pass': 0.0,
        'rush_att': 0.0, 'rush_epa': 0.0, 'rush_success': 0.0, 'rush_success_n': 0.0,
        'rush_td': 0.0, 'rush_xtd': 0.0, 'rz_rush': 0.0, 'gl_rush': 0.0,
        'targets': 0.0, 'receptions': 0.0, 'rec_epa': 0.0,
        'rec_air_yards': 0.0, 'rec_success': 0.0, 'rec_success_n': 0.0,
        'rec_td': 0.0, 'rec_xtd': 0.0, 'rz_tgt': 0.0, 'gl_tgt': 0.0,
        'xyac_sum': 0.0, 'xyac_n': 0.0,
    }


def _add_pass(agg, row, xtd):
    agg['dropbacks'] += 1
    if truthy(row.get('pass_attempt')) and not truthy(row.get('sack')):
        agg['pass_attempts'] += 1
    if truthy(row.get('complete_pass')):
        agg['completions'] += 1
    agg['pass_epa'] += fnum0(row.get('epa'))
    cpoe = fnum(row.get('cpoe'))
    if cpoe is not None:
        agg['cpoe_sum'] += cpoe
        agg['cpoe_n'] += 1
    air = fnum(row.get('air_yards'))
    if air is not None:
        agg['pass_air_yards'] += air
    if row.get('success') not in (None, '', 'NA'):
        agg['pass_success'] += float(truthy(row.get('success')))
        agg['pass_success_n'] += 1
    if truthy(row.get('pass_touchdown')) or (
            truthy(row.get('touchdown')) and truthy(row.get('complete_pass'))):
        agg['pass_td'] += 1
    agg['pass_xtd'] += xtd
    yl = fnum(row.get('yardline_100'))
    if yl is not None and yl <= 20:
        agg['rz_pass'] += 1
    if yl is not None and yl <= 2:
        agg['gl_pass'] += 1


def _add_rush(agg, row, xtd):
    agg['rush_att'] += 1
    agg['rush_epa'] += fnum0(row.get('epa'))
    if row.get('success') not in (None, '', 'NA'):
        agg['rush_success'] += float(truthy(row.get('success')))
        agg['rush_success_n'] += 1
    if truthy(row.get('rush_touchdown')) or truthy(row.get('touchdown')):
        agg['rush_td'] += 1
    agg['rush_xtd'] += xtd
    yl = fnum(row.get('yardline_100'))
    if yl is not None and yl <= 20:
        agg['rz_rush'] += 1
    if yl is not None and yl <= 2:
        agg['gl_rush'] += 1


def _add_rec(agg, row, xtd):
    agg['targets'] += 1
    if truthy(row.get('complete_pass')):
        agg['receptions'] += 1
    agg['rec_epa'] += fnum0(row.get('epa'))
    air = fnum(row.get('air_yards'))
    if air is not None:
        agg['rec_air_yards'] += air
    if row.get('success') not in (None, '', 'NA'):
        agg['rec_success'] += float(truthy(row.get('success')))
        agg['rec_success_n'] += 1
    if truthy(row.get('pass_touchdown')) or (
            truthy(row.get('touchdown')) and truthy(row.get('complete_pass'))):
        agg['rec_td'] += 1
    agg['rec_xtd'] += xtd
    yl = fnum(row.get('yardline_100'))
    if yl is not None and yl <= 20:
        agg['rz_tgt'] += 1
    if yl is not None and yl <= 2:
        agg['gl_tgt'] += 1
    xyac = fnum(row.get('xyac_mean_yardage'))
    if xyac is not None:
        agg['xyac_sum'] += xyac
        agg['xyac_n'] += 1


def aggregate_pbp(path, rates=None):
    """Return player-week dicts ready for fact_pbp_agg.

    Receptions are a counting stat (volume). This never awards PPR points.
    """
    if rates is None:
        rates = fit_xtd_rates(path)
    out = {}
    for row in _iter_pbp(path):
        try:
            season = int(float(row['season']))
            week = int(float(row['week']))
        except (KeyError, TypeError, ValueError):
            continue
        ptype = row.get('play_type')
        bucket = yardline_bucket(fnum(row.get('yardline_100')))
        xtd = rates.get((season, ptype, bucket), 0.0) if bucket else 0.0

        if ptype == 'pass':
            passer = (row.get('passer_player_id') or '').strip()
            recv = (row.get('receiver_player_id') or '').strip()
            if passer:
                key = (season, week, passer)
                agg = out.setdefault(key, _blank_agg())
                _add_pass(agg, row, xtd)
            if recv:
                key = (season, week, recv)
                agg = out.setdefault(key, _blank_agg())
                _add_rec(agg, row, xtd)
        elif ptype == 'run':
            rusher = (row.get('rusher_player_id') or '').strip()
            if rusher:
                key = (season, week, rusher)
                agg = out.setdefault(key, _blank_agg())
                _add_rush(agg, row, xtd)

    rows = []
    for (season, week, gsis), a in out.items():
        cpoe = (a['cpoe_sum'] / a['cpoe_n']) if a['cpoe_n'] else None
        xyac = (a['xyac_sum'] / a['xyac_n']) if a['xyac_n'] else None
        rows.append({
            'season': season, 'week': week, 'gsis_id': gsis,
            'dropbacks': a['dropbacks'],
            'pass_attempts': a['pass_attempts'],
            'completions': a['completions'],
            'pass_epa': a['pass_epa'],
            'cpoe': cpoe,
            'cpoe_n': a['cpoe_n'],
            'pass_air_yards': a['pass_air_yards'],
            'pass_success': a['pass_success'],
            'pass_success_n': a['pass_success_n'],
            'pass_td': a['pass_td'],
            'pass_xtd': a['pass_xtd'],
            'rz_pass': a['rz_pass'],
            'gl_pass': a['gl_pass'],
            'rush_att': a['rush_att'],
            'rush_epa': a['rush_epa'],
            'rush_success': a['rush_success'],
            'rush_success_n': a['rush_success_n'],
            'rush_td': a['rush_td'],
            'rush_xtd': a['rush_xtd'],
            'rz_rush': a['rz_rush'],
            'gl_rush': a['gl_rush'],
            'targets': a['targets'],
            'receptions': a['receptions'],
            'rec_epa': a['rec_epa'],
            'rec_air_yards': a['rec_air_yards'],
            'rec_success': a['rec_success'],
            'rec_success_n': a['rec_success_n'],
            'rec_td': a['rec_td'],
            'rec_xtd': a['rec_xtd'],
            'rz_tgt': a['rz_tgt'],
            'gl_tgt': a['gl_tgt'],
            'xyac': xyac,
            'xyac_n': a['xyac_n'],
        })
    return rows


def pbp_path(data_dir, year):
    gz = os.path.join(data_dir, f'play_by_play_{year}.csv.gz')
    raw = os.path.join(data_dir, f'play_by_play_{year}.csv')
    if os.path.exists(gz):
        return gz
    if os.path.exists(raw):
        return raw
    return None
