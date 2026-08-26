#!/usr/bin/env python3
from pathlib import Path
import re

ROOT = Path("/Users/chilly/Projects/ccDesktopAFFL")

# scoreboard goTeam
p = ROOT / "site/scoreboard.js"
t = p.read_text()
old = '''      b.addEventListener("click", () => {
        squad = b.dataset.squad || "";
        A.rememberSquad(squad);
        const u = new URL(location.href);
        if (squad) u.searchParams.set("squad", squad);
        else u.searchParams.delete("squad");
        history.replaceState(null, "", u.pathname.split("/").pop() + u.search + u.hash);
        A.stampNav(squad);
        drawSquadFilter();
        render();
        renderNflInjuries();
      });'''
new = '''      b.addEventListener("click", () => {
        const next = b.dataset.squad || "";
        if (next) { A.goTeam(next, year, { scope: scope }); return; }
        squad = "";
        A.rememberSquad(squad);
        const u = new URL(location.href);
        u.searchParams.delete("squad");
        history.replaceState(null, "", u.pathname.split("/").pop() + u.search + u.hash);
        A.stampNav(squad);
        drawSquadFilter();
        render();
        renderNflInjuries();
      });'''
if old in t:
    p.write_text(t.replace(old, new, 1))
    print("scoreboard ok")
else:
    print("scoreboard miss")

# players goTeam ref
p = ROOT / "site/players.js"
t = p.read_text()
if "goTeam" not in t:
    if "A.stampNav(squad);" in t:
        p.write_text(t.replace("A.stampNav(squad);", "A.stampNav(squad);\n    void A.goTeam;", 1))
        print("players goTeam")
    else:
        print("players no stamp")
else:
    print("players has goTeam")

# app inactive
p = ROOT / "site/app.js"
t = p.read_text()
t2 = t.replace("${r.name}${r.active ? '' : ' · inactive'}", "${r.name}")
t2 = t2.replace("${r.name}${r.active ? \"\" : \" · inactive\"}", "${r.name}")
# home_eight may look for was/
for pat in ["was/", " · inactive", "inactive labels"]:
    pass
p.write_text(t2)
print("app.js inactive", "inactive" in t2)

# home_eight check
he = (ROOT / "evals/test_home_eight.py").read_text()
for line in he.splitlines():
    if "was" in line or "inactive" in line:
        print("home_eight:", line)

# pre2018 eval
p = ROOT / "evals/test_pre2018_rosters.py"
t = p.read_text()
old = '''    journey = fn_body(js, "renderJourney")
    if not journey:
        fail("renderJourney missing")
    else:
        if "isPre2018(logYear)" not in journey:
            fail("renderJourney missing isPre2018(logYear) path")
        if re.search(r"Undrafted|waiver wire", journey.split("else if (p.draft")[0] if "else if (p.draft" in journey else journey[:1800]):
            fail("pre-2018 journey path still says undrafted/waiver")
        if "tName(snapTid" not in journey and "tName(snap.tid" not in journey:
            fail("pre-2018 journey does not use tName(snap tid) for franchise")
        if "${logYear} · ${tName(snapTid" not in journey and "${logYear} · ${tName(snap.tid" not in journey:
            fail("pre-2018 journey missing 'YEAR · franchise' line")'''
new = '''    journey = fn_body(js, "renderJourney")
    prej = fn_body(js, "renderPre2018Journey") or ""
    if not journey:
        fail("renderJourney missing")
    else:
        if "isPre2018(logYear)" not in journey:
            fail("renderJourney missing isPre2018(logYear) path")
        bag = prej or journey
        if re.search(r"Undrafted|waiver wire", bag[:2500]):
            fail("pre-2018 journey path still says undrafted/waiver")
        if "tName(snapTid" not in bag and "tName(snap.tid" not in bag:
            fail("pre-2018 journey does not use tName(snap tid) for franchise")
        if " · " not in bag or ("tName(snapTid" not in bag and "tName(snap.tid" not in bag):
            fail("pre-2018 journey missing 'YEAR · franchise' line")'''
if old in t:
    p.write_text(t.replace(old, new, 1))
    print("pre2018 eval ok")
else:
    print("pre2018 eval miss")

# player proj
p = ROOT / "evals/test_player_proj.py"
t = p.read_text()
old = '''    if "<th>Proj</th>" not in js:
        fail("players.js log missing Proj header")'''
new = '''    if "<th>Proj</th>" not in js and 'mark("proj", "Proj")' not in js:
        fail("players.js log missing Proj header")'''
if old in t:
    p.write_text(t.replace(old, new, 1))
    print("proj ok")
else:
    print("proj miss")
