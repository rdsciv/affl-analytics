#!/usr/bin/env python3
"""CHI-111: THE CHASE next-win logos must be size-capped."""
from pathlib import Path
root = Path(__file__).resolve().parents[1]
css = (root / "site/styles.css").read_text()
app = (root / "site/app.js").read_text()
html = (root / "site/index.html").read_text()
assert 'id="ms-chase"' in html
assert "function renderMsChase" in app
assert "avatarHTML(team, 'mini')" in app
assert "#ms-chase .story-ico img" in css
assert "max-width: 28px" in css
assert "max-height: 28px" in css
assert "img.mini" in css
assert "object-fit: contain" in css
print("ok chase bars")
