# AFFL factory

One product. One repo. One branch. Tickets in Linear. Data visible as files.

## Product

League Legacy + FantasyGenius + custom AFFL metrics, plus leeg/historical coverage.
Evidence rules stay: reconstructed can be explored, verified is for awards, missing stays missing.

## Working tree

- Repo: `rdsciv/affl-analytics`
- Local: `~/Projects/ccDesktopAFFL`
- Branch: `verify/full-audit` only. No PR theater. No extra worktrees.
- Live site (`main`) updates only when this branch is ready to ship.

Other copies (AFFLleeger, Auction Lab, Wrapped, Sourcebook site) are **inputs**, not places to keep building.

## How a change happens

1. You drop a ticket in [AFFL Sourcebook v1](https://linear.app/childressllc/project/affl-sourcebook-v1-88ad883cc233) or tell me in chat.
2. I pick it up, implement on `verify/full-audit`, show the data in `preview/`.
3. You look at `preview/SUMMARY.md` (or the CSVs). Not the website first.
4. When a slice is actually good, we merge `verify/full-audit` → `main` and the site updates.

Linear statuses I honor:
- In Spec / Ready → I start it.
- Backlog → I do not start it unless you say so.
- In Dev → I am building it on the local tree.
- In QA → it is on the local site, waiting for Ryan to review.
- In Deploy → reviewed, waiting to ship to `main`.
- Done → Ryan reviewed it AND it is live on production. Warehouse evals, preview files, and the local working tree are never Done.

Contracts: `CONTRACTS.md` (CHI-21, CHI-23).

## See the data

```
python3 build_db.py
python3 compute_xtd.py
python3 inspect_data.py --season 2025
```

Opens `preview/SUMMARY.md`. Warehouse is `affl.db`. Site JSON is a build artifact, not the source of truth.

