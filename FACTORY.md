# AFFL factory

One product. One repo. One branch. Tickets in Notion. Data visible as files.

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

1. You drop a ticket in [AFFL Linear Handoff Queue](https://app.notion.com/p/937f0e507b63413fa4a02fe926628892) or tell me in chat.
2. I pick it up, implement on `verify/full-audit`, show the data in `preview/`.
3. You look at `preview/SUMMARY.md` (or the CSVs). Not the website first.
4. When a slice is actually good, we merge `verify/full-audit` → `main` and the site updates.

## See the data

```
python3 build_db.py --check
python3 inspect_data.py --season 2025
```

Opens `preview/SUMMARY.md`. Warehouse is `affl.db`. Site JSON is a build artifact, not the source of truth.

## Ticket statuses I honor

- Ready → I start it
- Backlog → I do not start it unless you say so
- Done → I wrote what changed on the ticket
