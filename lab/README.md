# AFFL Lab

TanStack Charts proof-of-concept demonstrating the AFFL ⋈ NFL join.

## What It Does

Displays **started fantasy points vs NFL EPA** (2018–2025) in both:
- A D3 scatter chart (filterable by season, position, minimum points)
- A TanStack Table (sortable, shows full stats including cap hit)

Each row joins AFFL roster data to NFL data via `dim_player.gsis_id`:
- AFFL: who started, fantasy points scored
- NFL: EPA, passing/rushing/receiving stats
- Spotrac: NFL cap hit

Query: `v_started_vs_nfl` view across both databases.

## Build

```bash
# Export data from the warehouse (requires affl.db + nfl.db built)
python3 ../export_lab.py

# Install dependencies
npm install

# Dev server
npm run dev

# Build static site to ../site/lab/
npm run build
```

The built output goes directly into `site/lab/` where GitHub Pages will serve it.

## Stack

- Vite (static build, no server runtime)
- D3 for scatter chart
- TanStack Table Core for sortable table (vanilla JS, no React)
- Vanilla JS (no framework)

This pattern is the charting path forward, proven in [dienasty-history](https://github.com/rdsciv/dienasty-history). The existing five site pages stay Chart.js; migration is not in this PR's scope.
