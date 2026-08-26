"""Game log headers must match cells. Journey years must match the AFFL count."""
from pathlib import Path
import re

root = Path("/Users/chilly/Projects/ccDesktopAFFL")
js = (root / "site/players.js").read_text()
html = (root / "site/players.html").read_text()

assert "/* <th>Proj</th> */" not in js, "leftover comment must not create a phantom Proj header"
heads = re.findall(r'mark\("(\w+)", "([^"]+)"\)', js)
# one proj header in renderLog
proj = [h for h in heads if h[0] == "proj"]
assert len(proj) == 1, proj
assert "Fan Pts" in js and "Yds" in js and "TD−xTD" in js
assert "hasProj ? `<td" not in js, "Proj cell must always render so columns cannot slide"
assert "function afflYears" in js
assert "function yearHome" in js
assert "homes[homes.length - 1] === name" in js
assert "players.js?v=" in html
print("PASS")
