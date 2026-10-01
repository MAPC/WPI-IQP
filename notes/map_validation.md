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

## Evidence and scope

- `output/reports/map_model_test_results.txt`: management-model and map-rebuild tests.
- `output/reports/map_render_test_results.txt`: marker rendering/configuration tests.
- `output/reports/map_ui_fixture_test_results.txt`: focused browser regressions.
- `output/reports/map_management_headless_results.json`: blocked-network browser pass.
- `output/reports/map_management_test_results.json`: final headed browser pass.
- `output/reports/map_screenshots/`: actual regional, close, hover, selected, evidence, issue, missing-coordinate, transportation, mobile and offline views.
- `output/reports/map_build_manifest.json`: map hash, linked analytical manifest and current validation evidence.
- `output/reports/map_preservation_checks.json`: all 97 protected source/analytical/archive files compared with the pre-redesign hashes.

Historical results are not claimed as newly rerun tests. A full pipeline or clean rebuild is unnecessary for this presentation-only revision; no analytical definition or source processing was changed. Native macOS/Linux launcher execution was not part of this revision's validation; the earlier shell syntax and isolated launcher tests are documented in `notes/project_organization.md`.
