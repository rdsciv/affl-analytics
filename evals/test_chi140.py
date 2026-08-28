#!/usr/bin/env python3
"""CHI-140: Savant landing is the plot, identity marks, one control row.

Fails if landing default color is franchise, or if more than one control
row is the first screen. Franchise color is a toggle, off on arrival.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
fails: list[str] = []


def fail(msg: str) -> None:
    fails.append(msg)

def _css_block(html: str, selector: str) -> str:
    pat = re.escape(selector) + r"\s*\{([^}]+)\}"
    m = re.search(pat, html)
    return m.group(1) if m else ""


def _px(css: str, prop: str, default: int = 0) -> int:
    m = re.search(rf"{re.escape(prop)}:\s*(\d+)px", css)
    return int(m.group(1)) if m else default


def _nowrap_clips_axis_labels(html: str) -> bool:
    """True when a nowrap control bar would clip Y AXIS / MIN OPP.

    Picasso fail: nowrap on a too-narrow rigid bar without overflow:visible
    or wrap — visible text becomes "Y AXI".
    """
    row = _css_block(html, ".sv-control-row")
    field = _css_block(html, ".sv-control-row .sv-field")
    wide = _css_block(html, ".sv-control-row .sv-field.wide")
    lab = _css_block(html, ".sv-field label")
    if not row:
        return True

    wraps = bool(re.search(r"flex-wrap:\s*wrap(?!\s*-)", row)) and "nowrap" not in row
    if wraps:
        return False

    nowrap = "nowrap" in row
    if not nowrap:
        return False

    overflow_visible = bool(re.search(r"overflow(?:-x)?:\s*visible", row + lab))
    shrinks = (
        bool(re.search(r"min-width:\s*0\b", field))
        or bool(re.search(r"flex:\s*[^;]*[1-9]\s+", field))
    )
    lab_hidden = bool(re.search(r"overflow:\s*hidden", lab))
    if lab_hidden:
        return True

    n_reg = len(re.findall(r'class="sv-field"', html))
    n_wide = len(re.findall(r'class="sv-field wide"', html))
    gap = _px(row, "gap", 10)
    min_reg = _px(field, "min-width", 0)
    min_wide = _px(wide, "min-width", min_reg)
    # flex-basis like 72px counts as the reserved slot when min-width is 0
    if min_reg == 0:
        m = re.search(r"flex:\s*[\d.]+\s+[\d.]+\s+(\d+)px", field)
        min_reg = int(m.group(1)) if m else 0
    if min_wide == 0:
        m = re.search(r"flex:\s*[\d.]+\s+[\d.]+\s+(\d+)px", wide)
        min_wide = int(m.group(1)) if m else min_reg
    total = n_reg * min_reg + n_wide * min_wide + gap * max(n_reg + n_wide - 1, 0)
    # ~1000px is sheet-main at a 1280 Picasso viewport beside the 188px rail.
    too_narrow = total > 900 and not shrinks
    if too_narrow and not overflow_visible:
        return True
    # overflow:auto/hidden/scroll is a clipping scrollport — "Y AXI" still paints.
    row_clips = bool(re.search(r"overflow(?:-x)?:\s*(hidden|auto|scroll)", row))
    rigid = bool(re.search(r"flex:\s*0\s+0", field))
    if row_clips and rigid and not overflow_visible:
        return True
    return False




def main() -> int:
    html = (SITE / "savant.html").read_text()
    js = (SITE / "savant.js").read_text()

    if re.search(r"plotly|cdn\.plot\.ly|d3\.min\.js|from ['\"]d3['\"]", html + js, re.I):
        fail("Plotly/D3 leaked in; CHI-146 is out of this landing")

    state = re.search(r"const state = \{([\s\S]*?)\n  \};", js)
    if not state:
        fail("savant.js missing const state")
    else:
        body = state.group(1)
        if 'color: "franchise"' in body:
            fail("landing default color is franchise")
        if 'color: "identity"' not in body:
            fail("landing default color is not identity")
        if re.search(r'season:\s*ALL', body) is None and 'season: "all"' not in body:
            fail("Season default is not All")
        if re.search(r'franchise:\s*""', body) is None:
            fail("Team default is not All")

    if '["cum", "Cumulative"]' in js or '["season", "Season"]' in js:
        fail("Cumulative|Season toggle still ships")
    if 'id="scope-picker"' in html:
        fail("Cumulative|Season scope-picker still on the page")

    if html.count('id="sv-control-row"') != 1:
        fail("need exactly one #sv-control-row")
    if 'flex-wrap: nowrap' not in html and "flex-wrap:nowrap" not in html:
        fail("control row is not locked to one row")

    tuck = re.search(r'<details\b[^>]*id="sv-tuck"[^>]*>', html)
    if not tuck:
        fail("team/pool/historic chips are not tucked in #sv-tuck")
    elif "open" in tuck.group(0):
        fail("#sv-tuck is open on arrival — chips are the first screen")

    plot = html.find('class="sv-plot"')
    if plot < 0:
        fail("landing has no .sv-plot")
    else:
        head = html[:plot]
        visible_rows = 0
        if 'id="sv-control-row"' in head:
            visible_rows += 1
        # picker-rows that are not inside the closed tuck
        tuck_i = head.find('id="sv-tuck"')
        before_tuck = head if tuck_i < 0 else head[:tuck_i]
        visible_rows += len(re.findall(r'class="[^"]*picker-row', before_tuck))
        visible_rows += len(re.findall(r'class="[^"]*sv-controls', before_tuck))
        if visible_rows > 1:
            fail(f">{1} control row is the first screen ({visible_rows})")

    if "All squads" in html or "All squads" in js:
        fail("landing still says All squads; word is team")
    if re.search(r">Squad<", html):
        fail("landing chrome says Squad")
    if 'for="team-picker">Team</label>' not in html:
        fail("CHI-142 Team control missing")
    if 'for="season-picker">Season</label>' not in html:
        fail("CHI-142 Season control missing")

    if "function markHTML" not in js or "function identityKind" not in js:
        fail("identity mark helpers missing")
    if "sv-mark-face" not in html or "sv-mark-abbr" not in html:
        fail("face/abbrev mark classes missing from landing CSS")
    if "28px" not in html:
        fail("face mark not capped at 28px")
    if "16px" not in html:
        fail("abbrev mark not capped at 16px")
    if "object-fit: contain" not in html and "object-fit:contain" not in html:
        fail("marks missing object-fit contain")
    if "background: transparent" not in html and "background:transparent" not in html:
        fail("marks missing transparent background")
    if "nflLogoHTML" in js or "logos/nfl/" in js:
        fail("unconstrained NFL logos on savant marks")

    if "function hoverStartedLine" not in js or "r.frStarts" not in js:
        fail("CHI-139 hoverStartedLine / frStarts dropped")
    if "Central Oregon Gabagooners" not in js:
        fail("Gabagooners dropped from the team list")
    if 'Green Bay Glory Holes": "Chula Vista Chupacabras"' not in js:
        fail("Glory Holes are not folded into Chupacabras")
    if "non-PPR" not in js:
        fail("non-PPR lock dropped")
    if "League Legacy" in js or "League Legacy" in html:
        fail("Savant mentions League Legacy")

    bust = re.search(r"savant\.js\?v=(\d+)", html)
    if not bust:
        fail("savant.js not cache-busted")
    elif int(bust.group(1)) < 10:
        fail(f"savant.js cache still v={bust.group(1)}")

    if _nowrap_clips_axis_labels(html):
        fail("control row CSS nowrap would clip axis labels (Y AXIS / MIN OPP)")
    for needle in ("Season", "Team", "Y axis", "Min opp", "X axis"):
        if f">{needle}<" not in html:
            fail(f"control label {needle!r} missing")

    if fails:
        print("FAIL CHI-140")
        for item in fails:
            print(" -", item)
        return 1
    print("PASS")
    print("CHI-140: landing identity marks; one control row; franchise color off")
    return 0


if __name__ == "__main__":
    sys.exit(main())
