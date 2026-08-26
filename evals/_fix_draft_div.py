from pathlib import Path
p = Path("/Users/chilly/Projects/ccDesktopAFFL/site/index.html")
t = p.read_text()
old = """      <div class=\"draft-note\" id=\"draft-note\"></div>
    </div>
  </section>"""
new = """      <div class=\"draft-note\" id=\"draft-note\"></div>
  </section>"""
if old not in t:
    raise SystemExit("draft close not found")
p.write_text(t.replace(old, new, 1))
print("removed extra div")
