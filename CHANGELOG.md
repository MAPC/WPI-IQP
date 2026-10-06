# Changelog

## 1.2.0 — 2026-10-06

- Accessibility-tag circle sizing by default; optional all-attribute sizing with independent color and filter state.
- Clear recorded-tag versus assessed/calculated labels, explicit inventory subsets and plain municipality warnings.
- Separate designated parking from aisle conditions; exclude explicit remote-location restroom evidence from local assessments.
- Keep valid locations outside advisory study bounds mapped; gate GIS/transit evidence independently by configured coverage.
- Preserve all-mode cached MBTA calculation while keeping transit-policy scope an explicit open decision.
- 151 tests, 12 visible-browser QA groups, 10 reviewed screenshots; source and current spatial results preserved.


## 1.1.0 — 2026-10-01

Simplified the product to one interactive management map and a shared Windows/macOS launch workflow. Required parsing, source reconciliation, full-line GIS distance, half-mile transit and site/management calculations now pass their results in memory to the HTML renderer. The launcher manages Python dependencies, generates the map, starts a localhost server and opens the browser. Reporting, chart, workbook, static-map and release generators are removed from the application.

Review/search filters hide nonmatches; the missing-coordinate metric is display-only; Snapshot and CSV export controls are removed. Scrollable hover cards support marker-to-card crossing, close promptly, and require deliberate re-entry after dismissal. Development tests remain separate from application startup.

## 1.0.0 — 2026-09-30

Initial reproducible pipeline: immutable root inventory and copy-based bootstrap; alias-aware schema contract; traceable asset/attribute/activity/coordinate parsing; conservative three-state evidence reconciliation; verified MAPC GIS domains and full-line indexed proximity; official MBTA snapshot caching and exact half-mile calculation; separate asset/site descriptive analysis; Excel workbooks and field dictionary; local interactive map, static map and publication charts; tests, browser checks, QC, provenance and release packaging.

New-data runs retain the same software version. Methodology or code changes require an entry and appropriate version increment in src/__init__.py and pyproject.toml.
