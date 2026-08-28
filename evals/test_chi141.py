#!/usr/bin/env python3
"""CHI-141: Draft Marimekko labels do not pile up or leave a stray n."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
js = (ROOT / "site/draft.js").read_text()
html = (ROOT / "site/draft.html").read_text()
fails = []


def fail(m):
    fails.append(m)


if ">n</text>" in js:
    fail("stray n label still in mekko")
if "}% spend</text>" in js:
    fail("% spend still always painted on every column")
if "b.w >= 52" not in js:
    fail("narrow columns still get percent labels")
if "Connected scatter" in html:
    fail("Connected scatter title still clips")
import re as _re
_m = _re.search(r"draft\.js\?v=(\d+)", html)
if not _m or int(_m.group(1)) < 18:
    fail("draft.js pin not v>=18")

if fails:
    print("FAIL")
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("PASS")
print("CHI-141: no stray n; percent only on wide columns; scatter title shortened")
