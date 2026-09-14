#!/usr/bin/env python3
"""CHI-83: Draft Week 1 vs Acquired cards stay 2-up with capped logos.

Moneyball (m04 / Chewbacca) must use a locally baked CC badge — same-origin
relative logos/* path, never kathleenhalme.com or another remote host.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
fails = []

REMOTE_HOSTS = (
    "kathleenhalme.com",
    "hamous.org",
    "geekshak.com",
)


def fail(msg):
    fails.append(msg)


html = (SITE / "draft.html").read_text()
js = (SITE / "draft.js").read_text()
css = (SITE / "styles.css").read_text()
common = (SITE / "common.js").read_text()
data = json.loads((SITE / "data.json").read_text())

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

# --- CHI-83 remaining: Moneyball / m04 local-only mark ---
marks_block = re.search(r"const FRANCHISE_MARKS = \{([\s\S]*?)\n  \};", common)
if not marks_block:
    fail("common.js missing FRANCHISE_MARKS")
    marks = {}
else:
    marks = dict(re.findall(r'(m\d+):\s*"(logos/[^"]+)"', marks_block.group(1)))

m04_src = marks.get("m04") or ""
if not m04_src:
    fail("FRANCHISE_MARKS does not bind m04 to a local logos/ asset")
elif not m04_src.startswith("logos/"):
    fail(f"m04 mark is not a relative logos/ path: {m04_src!r}")
elif re.search(r"https?://", m04_src) or m04_src.startswith("//"):
    fail(f"m04 mark is a remote URL: {m04_src!r}")
else:
    disk = SITE / m04_src
    if not disk.is_file() or disk.stat().st_size < 200:
        fail(f"m04 local badge missing or empty: {m04_src}")
    else:
        print(f"m04 local badge {m04_src} {disk.stat().st_size} bytes")

strip = re.search(r'owner:\s*"m04"[^}]+\}', common)
if strip:
    logo = re.search(r'logo:\s*"([^"]*)"', strip.group(0))
    src = logo.group(1) if logo else ""
    if src and (src.startswith("http") or src.startswith("//") or "://" in src):
        fail(f"HISTORIC_STRIP m04 still has a remote logo: {src!r}")
    if src and not src.startswith("logos/"):
        fail(f"HISTORIC_STRIP m04 logo is not same-origin: {src!r}")

# logoHTML must not emit http(s) franchise marks (CHI-169 + CHI-83)
logo_fn = re.search(r"function logoHTML\([\s\S]*?\n  \}", common)
if not logo_fn:
    fail("could not isolate logoHTML")
else:
    body = logo_fn.group(0)
    if re.search(r"https?:", body):
        fail("logoHTML still references an http(s) scheme")
    if "isLocalLogo(src)" not in body:
        fail("logoHTML does not gate img src on isLocalLogo")
    if re.search(r"\^\(https\?:", body):
        fail("logoHTML still allows remote http(s) src")

if "w1-award-logo" not in re.search(
    r"function logoMarkSize\([\s\S]*?\n  \}", common
).group(0):
    fail("logoMarkSize does not treat w1-award-logo as a 64px cap")
else:
    size_fn = re.search(r"function logoMarkSize\([\s\S]*?\n  \}", common).group(0)
    if "return 64" not in size_fn:
        fail("logoMarkSize has no 64px return for award logos")

# Moneyball card src resolves through franchiseTeam → franchiseLogo(m04)
if "A.logoHTML(t, \"w1-award-logo\")" not in chunk:
    fail("Moneyball card does not call logoHTML for the award mark")

# No leftover remote Chewbacca hosts in the award path or warehouse payloads
scan_files = [
    SITE / "common.js",
    SITE / "draft.js",
    SITE / "app.js",
    SITE / "data.json",
    SITE / "history-franchises.json",
    SITE / "history.json",
    SITE / "team_activity.json",
]
for path in scan_files:
    text = path.read_text()
    for host in REMOTE_HOSTS:
        if host in text:
            fail(f"{path.name} still references remote host {host}")

for season in (data.get("seasons") or {}).values():
    for team in season.get("teams") or []:
        if team.get("owner") != "m04":
            continue
        logo = team.get("logo") or ""
        if re.search(r"https?://", str(logo)) or any(h in str(logo) for h in REMOTE_HOSTS):
            fail(f"data.json m04 season logo is remote: {logo!r}")

# Simulated Moneyball <img src> — same-origin relative, never a remote host
moneyball_src = m04_src
if moneyball_src:
    if moneyball_src.startswith("http://") or moneyball_src.startswith("https://"):
        fail(f"Moneyball img src is remote: {moneyball_src!r}")
    if "://" in moneyball_src or moneyball_src.startswith("//"):
        fail(f"Moneyball img src is not same-origin: {moneyball_src!r}")
    if not moneyball_src.startswith("logos/"):
        fail(f"Moneyball img src is not a relative logos/ path: {moneyball_src!r}")
    print(f"Moneyball img src {moneyball_src}")

if 'common.js?v=40' not in html:
    fail("draft.html common.js is not cache-busted to v=40")
if 'draft.js?v=27' not in html:
    fail("draft.html draft.js is not cache-busted to v=27")

print("FAIL" if fails else "PASS")
for item in fails:
    print(" -", item)
sys.exit(1 if fails else 0)
