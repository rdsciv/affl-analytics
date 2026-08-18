#!/usr/bin/env python3
"""Fail if site/ has deploy-critical files on disk that are not in git.

Prevents localhost-OK / Pages-broken. No asking Ryan — fix by committing.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"

# Always required if present on disk
CRITICAL_PREFIXES = (
    "site/favicon",
    "site/logos/",
    "site/pillars/",
)
CRITICAL_SUFFIXES = (".html", ".js", ".css", ".json", ".png", ".jpg", ".jpeg", ".svg", ".ico", ".webp")


def tracked():
    out = subprocess.check_output(["git", "ls-files", "site"], cwd=ROOT, text=True)
    return set(out.splitlines())


def main():
    tr = tracked()
    missing = []
    for p in SITE.rglob("*"):
        if not p.is_file():
            continue
        if "/." in str(p):
            continue
        rel = str(p.relative_to(ROOT)).replace("\\", "/")
        if rel in tr:
            continue
        if not rel.endswith(CRITICAL_SUFFIXES):
            continue
        if any(rel.startswith(pref) or pref.rstrip("/") in rel for pref in CRITICAL_PREFIXES) or rel.endswith(
            (".html", ".js", ".css", ".json")
        ):
            # skip huge accidental dumps? pillars are intentional
            missing.append(rel)
    if missing:
        print("FAIL")
        print(f"{len(missing)} site files on disk but NOT in git (would 404 on Pages):")
        for m in sorted(missing)[:80]:
            print(" -", m)
        if len(missing) > 80:
            print(f" ... +{len(missing)-80} more")
        print("Fix: git add -f these paths and push. Do not ask the user.")
        return 1
    print("PASS")
    print(f"site git complete — {len(tr)} tracked files under site/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
