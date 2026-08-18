#!/usr/bin/env python3
"""Starter EPA chart tooltip is EPA only."""
import sys
from pathlib import Path
js = (Path(__file__).resolve().parents[1] / "site" / "app.js").read_text()
fn = js.split("function renderEPA", 1)
if len(fn) < 2:
    print("FAIL\n - renderEPA missing")
    sys.exit(1)
body = fn[1].split("function ", 1)[0]
fails = []
if "air yards" in body or "WOPR" in body or "wopr" in body:
    fails.append("EPA tooltip still mentions air yards or WOPR")
if "afterBody" in body:
    fails.append("EPA tooltip still has afterBody extras")
if "EPA" not in body:
    fails.append("EPA label gone")
if fails:
    print("FAIL")
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("PASS")
print("Starter EPA tooltip is EPA only")
