#!/usr/bin/env python3
from pathlib import Path

ROOT = Path("/Users/chilly/Projects/ccDesktopAFFL")
js_path = ROOT / "site/draft.js"
html_path = ROOT / "site/draft.html"
css_path = ROOT / "site/styles.css"
eval_path = ROOT / "evals/test_w1_awards.py"

js = js_path.read_text()
old_card = '''    const card = (k, title, row, which) => {
      const t = row ? teamOf(row.tid) : { name: "—" };
      const pct = row ? sharePct(which === "w1" ? row.w1Share : row.acquiredShare) : null;
      return `<div class="card kpi age-award">
        <div class="kpi-num">${k}</div>
        <div class="kpi-title">${title}</div>
        <div class="kpi-desc"><strong>${t.name}</strong>
          <div class="own">${pct != null ? fmt(pct, 1) + "%" : "—"}</div>
          ${row ? A.logoHTML(t, "mini") : ""}</div>
      </div>`;
    };'''
new_card = '''    const card = (k, title, row, which) => {
      const t = row ? teamOf(row.tid) : { name: "—" };
      const pct = row ? sharePct(which === "w1" ? row.w1Share : row.acquiredShare) : null;
      return `<div class="card w1-award">
        <div class="w1-award-kicker">${k}</div>
        <div class="w1-award-copy">
          <div class="w1-award-title">${title}</div>
          <div class="w1-award-name">${t.name}</div>
          <div class="w1-award-pct">${pct != null ? fmt(pct, 1) + "%" : "—"}</div>
        </div>
        ${row ? A.logoHTML(t, "w1-award-logo") : `<div class="w1-award-logo fb">—</div>`}
      </div>`;
    };'''
if old_card not in js:
    raise SystemExit("draft.js card() block not found exactly — abort")
js_path.write_text(js.replace(old_card, new_card, 1))

html = html_path.read_text()
old_html = '<div class="kpi-row" id="w1-awards"></div>'
new_html = '<div class="w1-awards-row" id="w1-awards"></div>'
if old_html not in html:
    raise SystemExit("draft.html #w1-awards row not found exactly — abort")
html_path.write_text(html.replace(old_html, new_html, 1))

css = css_path.read_text()
if ".w1-award-logo" not in css:
    css += """

/* CHI-83: Week 1 vs Acquired award cards — 2-up, capped logos */
#w1-awards,
.w1-awards-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 16px;
}
.w1-award {
  display: grid;
  grid-template-columns: 92px minmax(0, 1fr) 64px;
  align-items: center;
  gap: 16px;
  min-height: 120px;
  padding: 18px 20px;
}
.w1-award-kicker {
  font-size: 11px;
  letter-spacing: .14em;
  font-weight: 700;
  text-transform: uppercase;
  color: var(--mut);
  line-height: 1.25;
}
.w1-award-title {
  font-size: 11px;
  color: var(--mut);
  text-transform: uppercase;
  letter-spacing: .04em;
}
.w1-award-name {
  font-size: 16px;
  font-weight: 700;
  color: var(--ink);
  margin: 4px 0 2px;
  line-height: 1.25;
}
.w1-award-pct {
  font-size: 28px;
  font-weight: 800;
  font-variant-numeric: tabular-nums;
  color: var(--ink);
}
img.w1-award-logo,
.w1-award-logo,
.w1-award .w1-award-logo.fb {
  width: 64px;
  height: 64px;
  max-width: 64px;
  max-height: 64px;
  object-fit: contain;
  background: transparent;
  border-radius: 8px;
  display: grid;
  place-items: center;
  flex: 0 0 64px;
}
@media (max-width: 800px) {
  #w1-awards, .w1-awards-row { grid-template-columns: 1fr; }
}
"""
    css_path.write_text(css)

eval_path.write_text('''#!/usr/bin/env python3
"""CHI-83: Draft Week 1 vs Acquired cards stay 2-up with capped logos."""
import re
import sys
from pathlib import Path

SITE = Path(__file__).resolve().parents[1] / "site"
fails = []


def fail(msg):
    fails.append(msg)


html = (SITE / "draft.html").read_text()
js = (SITE / "draft.js").read_text()
css = (SITE / "styles.css").read_text()

m = re.search(r'<div class="([^"]*)" id="w1-awards">', html)
if not m:
    fail("draft.html missing #w1-awards")
elif "kpi-row" in m.group(1).split():
    fail("#w1-awards still uses 4-column kpi-row")

if "class=\\"card w1-award\\"" not in js and 'class="card w1-award"' not in js:
    fail("draft.js card() is not the w1-award markup")
if "age-award" in js[js.find("function renderW1"): js.find("function milesRisk")]:
    fail("renderW1 still emits age-award / unconstrained mini logos")
if 'logoHTML(t, "mini")' in js[js.find("function renderW1"): js.find("function milesRisk")]:
    fail("renderW1 still drops A.logoHTML mini with no size cap")
if 'logoHTML(t, "w1-award-logo")' not in js:
    fail("renderW1 does not use w1-award-logo")

if ".w1-award-logo" not in css:
    fail("styles.css missing .w1-award-logo cap")
block = css[css.find(".w1-award-logo"): css.find(".w1-award-logo") + 400]
if "64px" not in block and "72px" not in block:
    fail("w1-award-logo is not capped to 64/72px")
if "1fr 1fr" not in css[css.find("#w1-awards"): css.find("#w1-awards") + 220]:
    fail("#w1-awards is not a 2-column grid")
if "card(\\"DRAFT DAY\\"" not in js and "card(\"DRAFT DAY\"" not in js:
    fail("Draft Day card missing")
if "card(\\"MONEYBALL\\"" not in js and "card(\"MONEYBALL\"" not in js:
    fail("Moneyball card missing")

print("FAIL" if fails else "PASS")
for f in fails:
    print(" -", f)
sys.exit(1 if fails else 0)
''')

print("patched draft.js, draft.html, styles.css, evals/test_w1_awards.py")
