# Management map validation

The management-map revision reuses the successful analytical run of 2026-09-30T14:04:38.865719+00:00. Its source, GIS, transit, workbooks, charts, canonical CSVs and release archives are not rebuilt for UI checks. The older analytical manifest and QC report remain historical evidence; current UI evidence is recorded separately.

## Repeatable targeted checks

From the repository root, using the project Python environment:

```text
python -m pytest -q tests/test_map_management.py tests/test_map_rebuild.py
python -m pytest -q tests/test_map.py tests/test_pipeline.py::test_project_config_enforces_exact_half_mile
python -m pytest -q tests/test_map_ui.py
python -m src.rebuild_map
python -m src.map_smoke_test
python -m src.map_smoke_test --headed
```

The first three commands are focused tests, not the full project suite. `rebuild_map` verifies checksums before rendering and checks analytical output hashes afterward. It does not invoke the source parser, spatial processing, transit acquisition, workbook generation, charts or release packaging.

The default browser check blocks all public tile traffic. The headed check opens an ordinary browser view for online QA, retains normal browser caching, and verifies only the displayed views. It does not download a tile archive. Direct `file://` opening uses embedded local data; use `python -m src.serve_map` for the HTTP Referer required by the online provider.

## Browser contract

The UI has a management drawer and custom controls. Browser tests click actual controls under `#layer-options`, open records through marker clicks and queue buttons, and check `#details-drawer`. The old Leaflet popup and built-in layers-control selectors are intentionally absent.

The check covers initialization, 171 mapped records and validation defaults; full viewport/no banner; dynamic counts against saved assets and all site counts; omissions; source/final values; all GIS/transit layer controls; both view modes; issue queues; CSV export; selected-record details; About/snapshot dialogs; mobile layout; no source mutation; no Apple resource requests; offline file opening; and JavaScript errors. Production counts are derived from saved data, not implementation constants.

Fractional zoom is checked at both 10.1 with a 0.1 increment and 10.25 with a 0.25 increment. The production increment is 0.25. Home restores the asset-based extent, allowing one pixel for Leaflet origin rounding. Legend measurements allow only 0.01 CSS pixel for browser display-scaling arithmetic; radii remain exactly 5, 8, 12, 17 and 23 in the configuration.

Regression fixtures cover overlapping validation/temporary reveal layers, source physical-line labels, MBTA retrieval dates, offline file safeguards, usable hover content and unobscured mobile controls. They use a tiny local dataset and no public tile requests.

## Final results — 2026-09-30 evening, America/New_York

The final resumption retained the completed hover/mobile fixes and finished their regression verification. The UI fixture now starts a fresh document when resizing, passes the browser wait argument by keyword, and waits for the zoom animation before the opposite click. These changes repair test setup/timing without weakening the interaction assertions.

| Evidence | Result and scope |
|---|---|
| Management-model and map-rebuild tests | 26 passed in 1.49 s; retained earlier result from this redesign |
| Map rendering and exact half-mile configuration | 5 passed in 0.37 s; retained earlier result from this redesign |
| Final `tests/test_map_ui.py` run | 7 passed in 5.50 s |
| Final `python -m src.rebuild_map` | Successful; all 61 protected analytical outputs unchanged |
| Final `python -m src.map_smoke_test --headed` | 14 checks passed in Edge; 24 initial online tiles, zero tile errors, no fatal JavaScript errors; offline and mobile checks included |
| Final baseline preservation audit | 97 of 97 files unchanged; zero discrepancies |

The hover regression uses actual pointer movement from a marker into its card, waits beyond the close delay, scrolls to the last of 40 activities, and confirms the map zoom stays unchanged. Mobile regressions at 390 × 844 and 360 × 640 expand the management panel and summary, verify neither zoom control is covered, then click both controls. The final production-map browser pass followed these tests and the final rendering.

All 13 final screenshots in `output/reports/map_screenshots/` were visually reviewed. The hover card has a usable scroll region; the expanded mobile panel ends above the zoom controls; source/audited conflict evidence remains distinct; queue and drawer content is legible; missing coordinates are explicit; online attribution and offline local content remain visible. No remaining visual issue was identified. The screenshot review is an additional visual check, not a substitute for the pointer and click regressions.

## Evidence and scope

- `output/reports/map_model_test_results.txt`: management-model and map-rebuild tests.
- `output/reports/map_render_test_results.txt`: marker rendering/configuration tests.
- `output/reports/map_ui_fixture_test_results.txt`: focused browser regressions.
- `output/reports/map_management_headless_results.json`: earlier blocked-network browser pass, before the last hover/mobile fixes. The final headed pass also checks offline operation on the final HTML.
- `output/reports/map_management_test_results.json`: final headed browser pass.
- `output/reports/map_screenshots/`: actual regional, close, hover, selected, evidence, issue, missing-coordinate, transportation, mobile and offline views.
- `output/reports/map_build_manifest.json`: map hash, linked analytical manifest and current validation evidence.
- `output/reports/map_preservation_checks.json`: all 97 protected source/analytical/archive files compared with the pre-redesign hashes.

Historical results are not claimed as newly rerun tests. A full pipeline or clean rebuild is unnecessary for this presentation-only revision; no analytical definition or source processing was changed. Native macOS/Linux launcher execution was not part of this revision's validation; the earlier shell syntax and isolated launcher tests are documented in `notes/project_organization.md`.
