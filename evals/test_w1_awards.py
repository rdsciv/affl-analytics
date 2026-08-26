#!/usr/bin/env python3
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

if "card w1-award" not in js:
    fail("draft.js card() is not the w1-award markup")

start = js.find("function renderW1")
end = js.find("function milesRisk")
chunk = js[start:end] if start != -1 and end != -1 else ""
if not chunk:
    fail("could not isolate renderW1")
if "age-award" in chunk:
    fail("renderW1 still emits age-award")
if 'logoHTML(t, "mini")' in chunk:
    fail("renderW1 still drops unconstrained mini logos")
if 'logoHTML(t, "w1-award-logo")' not in chunk:
    fail("renderW1 does not use w1-award-logo")
if "DRAFT DAY" not in chunk:
    fail("Draft Day card missing")
if "MONEYBALL" not in chunk:
    fail("Moneyball card missing")

if ".w1-award-logo" not in css:
    fail("styles.css missing .w1-award-logo cap")
logo_at = css.find(".w1-award-logo")
if "64px" not in css[logo_at: logo_at + 400]:
    fail("w1-award-logo is not capped to 64px")
row_at = css.find("#w1-awards")
if row_at == -1 or "1fr 1fr" not in css[row_at: row_at + 220]:
    fail("#w1-awards is not a 2-column grid")

print("FAIL" if fails else "PASS")
for item in fails:
    print(" -", item)
sys.exit(1 if fails else 0)
