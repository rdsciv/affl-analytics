#!/usr/bin/env python3
"""Teams draft table: Cost and Season Pts are click-sortable."""
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
js = (ROOT / "site/teams.js").read_text()
html = (ROOT / "site/teams.html").read_text()
assert "sortDraftPicks" in js
assert "draftSortKey" in js
assert "mark(\"cost\")" in js or "data-k=\"cost\"" in js
assert "mark(\"pts\")" in js or "data-k=\"pts\"" in js
assert "team-draft-tbl" in js
import re
m = re.search(r"teams\.js\?v=(\d+)", html)
assert m and int(m.group(1)) >= 6, html[:200]
print("ok")
