# AFFL Pressers Archive — Scaffold Complete

## Structure Created

```
site/
├── pressers.html          # Main archive index
└── pressers/
    ├── pressers.json      # Data source (31 entries, empty body fields)
    ├── 2020-w01.html      # Individual presser pages...
    ├── 2020-w02.html
    ├── ...
    ├── 2020-w11.html
    ├── 2020-final.html
    ├── 2021-w01.html
    ├── ...
    ├── 2021-w11.html      # (skips week 8)
    ├── 2022-w02.html      # (skips week 1)
    ├── ...
    └── 2022-w10.html      # 31 total pages
```

## What's Ready

✅ **31 HTML pages** generated and committed  
✅ **Archive index** with year-grouped links, gap notes  
✅ **Nav link** added to all 5 existing pages  
✅ **JSON schema** for content (`year`, `week`, `slug`, `title`, `body`)  
✅ **Prev/Next navigation** built into each page  
✅ **Design tokens** match existing site (chrome, color palette)  
✅ **PR opened**: https://github.com/rdsciv/affl-analytics/pull/6

## How to Populate

When you provide the presser texts, I'll:

1. Parse each text into the JSON `body` field
2. The JavaScript on each page will:
   - Detect tier headings (e.g., "TIER 1: Elite") → render as `<h3>`
   - Detect numbered items (e.g., "1. Team Name") → render as `<ol><li>`
   - Preserve paragraphs as `<p>`
3. Commit updated `pressers.json`
4. All 31 pages instantly show the content (no manual HTML editing)

## Example JSON Entry (after population)

```json
{
  "year": 2020,
  "week": 1,
  "slug": "2020-w01",
  "title": "2020 Week 1",
  "body": "TIER 1: Top Dogs\n1. Team Name (6-0) – Dominating performance...\n2. Another Team (5-1) – Close game...\n\nTIER 2: Middle Pack\n3. Team Three..."
}
```

## Testing

All pages are self-contained. To test locally:
```bash
cd site
python3 -m http.server 8000
# Visit http://localhost:8000/pressers.html
```

## Next Step

Ready for the verbatim presser texts. Provide them in any format (plain text, one file per week, or a single document with delimiters) and I'll populate the JSON.
