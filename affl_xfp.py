#!/usr/bin/env python3
"""AFFL fantasy points and expected points (XFP / FPOE).

Savant /fantasy has a std (non-PPR) toggle. That page is a comparison UI.
AFFL scoring is not generic standard: rec = 0, yardage is bucketed through
2018 and fractional from 2019, and a 50-yard FG scores 3 (kickers only).
XFP here is recomputed from fact_nfl_week + fact_pbp_agg under dim_scoring.
Receptions are volume; they never add points.
"""
import math

# SPEC.md §1 — skill-player rules. Used to seed dim_scoring when ESPN
# settings dumps are absent, and as the fallback in score_box.
# stat_id 53 (rec) is explicitly 0 so a missing row cannot become PPR.
AFFL_SKILL_RULES = {
    3: ('passYds', 0.04),
    4: ('passTD', 4.0),
    19: ('pass2pt', 2.0),
    20: ('passInt', -2.0),
    24: ('rushYds', 0.10),
    25: ('rushTD', 6.0),
    26: ('rush2pt', 2.0),
    42: ('recYds', 0.10),
    43: ('recTD', 6.0),
    44: ('rec2pt', 2.0),
    53: ('rec', 0.0),
    72: ('fumLost', -2.0),
}

SAVANT_FANTASY_NOTE = (
    "Savant /fantasy std is a comparison UI, not the AFFL scoring source. "
    "FP / XFP / FPOE here use dim_scoring (non-PPR, rec = 0; yardage "
    "bucketed through 2018, fractional from 2019)."
)


def _n(v):
    try:
        return 0.0 if v is None else float(v)
    except (TypeError, ValueError):
        return 0.0


def score_box(box, rules, mode):
    """Recompute one week of AFFL points from a box-score dict.

    `rules` is stat_id → points. Receptions use stat 53, which is 0 in AFFL.
    """
    py, pt = _n(box.get('pass_yards')), _n(box.get('pass_tds'))
    i = _n(box.get('interceptions'))
    ry, rt = _n(box.get('rush_yards')), _n(box.get('rush_tds'))
    cy, ct = _n(box.get('rec_yards')), _n(box.get('rec_tds'))
    rc = _n(box.get('receptions'))
    fl, tp = _n(box.get('fumbles_lost')), _n(box.get('two_pt'))
    rec_pts = rules.get(53, 0.0)
    if mode == 'BUCKET':
        yards = math.floor(py / 25) + math.floor(ry / 10) + math.floor(cy / 10)
    else:
        yards = (py * rules.get(3, 0.0) + ry * rules.get(24, 0.0)
                 + cy * rules.get(42, 0.0))
    return (yards
            + pt * rules.get(4, 0.0) + i * rules.get(20, 0.0)
            + rt * rules.get(25, 0.0) + ct * rules.get(43, 0.0)
            + rc * rec_pts
            + fl * rules.get(72, 0.0)
            + tp * rules.get(26, 0.0))


def expected_box(box, pbp, ngs=None):
    """Opportunity box for XFP: xTD in, receiving yards = air + xYAC.

    Passing/rushing yards stay actual unless NGS RYOE is present (rush only).
    Interceptions, fumbles, and 2-pt conversions stay actual — we do not
    invent expected turnovers. Receptions stay on the box as volume.
    """
    out = dict(box)
    if not pbp:
        return out
    out['pass_tds'] = _n(pbp.get('pass_xtd'))
    out['rush_tds'] = _n(pbp.get('rush_xtd'))
    out['rec_tds'] = _n(pbp.get('rec_xtd'))
    air = pbp.get('rec_air_yards')
    xyac = pbp.get('xyac')
    xyac_n = _n(pbp.get('xyac_n'))
    if air is not None:
        xrec = _n(air)
        if xyac is not None and xyac_n:
            xrec += _n(xyac) * xyac_n
        out['rec_yards'] = xrec
    if ngs is not None and ngs.get('rush_yards_over_expected') is not None:
        out['rush_yards'] = _n(box.get('rush_yards')) - _n(ngs['rush_yards_over_expected'])
    return out


def week_xfp(box, pbp, rules, mode, ngs=None):
    fp = score_box(box, rules, mode)
    xfp = score_box(expected_box(box, pbp, ngs), rules, mode)
    return fp, xfp, fp - xfp


def rules_from_rows(rows, fallback=True):
    """Build stat_id → points from dim_scoring rows for one season."""
    out = {}
    for sid, pts in rows:
        out[int(sid)] = float(pts)
    if fallback:
        for sid, (_name, pts) in AFFL_SKILL_RULES.items():
            out.setdefault(sid, pts)
    out[53] = 0.0
    return out
