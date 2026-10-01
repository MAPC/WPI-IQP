# MAPC work progress

Updated: 2026-09-30 evening, America/New_York (2026-10-01 UTC). The current completion checkpoint below supersedes earlier next-step instructions. Older sections are retained as historical evidence.

## Inventory management map update — complete

Active root: `C:/Users/Jaeyun/Desktop/MAPC Ultimate Deliverables`. Branch `main`, latest commit `c014411` at resumption. The working tree already contained the completed cleanup, management model, launcher, redesigned map, integration, and most browser validation. The last two visual fixes and their regression fixtures had also survived on disk. No source was reset or reverted, and no edits attributable to the mistaken macOS debugging direction needed undoing.

The remaining work was to finish verification of hover scrolling and mobile control spacing, run the final map/browser pass, review screenshots, and close the documentation. That work is complete:

- Hover cards accept the pointer, stay open while it is inside, and scroll the complete lists without zooming the map. The regression reaches the last of 40 fixture activities.
- The expanded mobile management panel reserves room for both zoom buttons. Regression checks at 390 × 844 and 360 × 640 verify geometry, pointer hit targets, and working zoom-in/out clicks.
- The saved regression fixture needed a fresh document to avoid redeclaring JavaScript constants, the correct keyword argument for the browser wait, and completion of the zoom animation before the opposite click. Those test defects are repaired.
- The map was rendered once from existing saved outputs after those fixes. Its 61 analytical output checksums remained unchanged.
- Final visible Edge browser QA passed all 14 checks, including online tiles and offline/mobile operation; 24 initial street tiles loaded with zero tile errors, and no fatal JavaScript errors occurred. Both 0.1 and 0.25 fractional zoom increments were verified.
- All 13 final screenshots were visually reviewed, including the usable hover, expanded mobile panel, conflict evidence, missing-coordinate queue, mobile drawer and offline map. No remaining visual defect was identified.

### Files and modules delivered

The completed redesign is in `src/map_ui.html`, `src/map_management.py`, `src/make_map.py`, `src/rebuild_map.py`, `src/serve_map.py`, and `src/map_smoke_test.py`, with map configuration, pipeline snapshot integration, package-data inclusion, acceptance wording and related tests. Cleanup/launcher work is recorded in `notes/project_organization.md` and `bootstrap/root_cleanup_report.*`. The final resumption changed `tests/test_map_ui.py`, README, this progress note, `notes/map_validation.md`, and added `notes/MAP_HANDOFF.md`; generated HTML, screenshots and UI-specific QA/provenance reports were refreshed.

### Verification and preserved state

| Check | Actual result |
|---|---|
| Management model + map-only rebuild tests, already completed during this redesign | 26 passed |
| Rendering + exact half-mile configuration tests, already completed during this redesign | 5 passed |
| Final focused UI regression run | 7 passed in 5.50 s |
| Final headed Edge browser pass after map-only rebuild | 14 checks passed; no reported errors or limitations |
| Final preservation comparison against `notes/map_redesign_baseline.json` | 97 of 97 protected files unchanged; zero missing/changed |

Current pipeline stage: management-map implementation, integration, targeted validation and handoff complete. No required implementation remains for this revision. The parser, GIS/transit analysis, workbooks, charts, static maps, historical full-suite run and clean-rebuild acceptance were retained; none was rerun to finish the UI. Current evidence is separate from the historical analytical manifest and QC report.

Current counts: 213 source rows, 211 accepted assets, 2 blank quarantine rows, 131 sites, 101 field validated, 27 staff reviewed, 171 mapped (101 validated + 70 unfinished), and 40 accepted records without coordinates. Management counts: 110 awaiting field completion, 184 awaiting staff review, 4 records/4 fields with unresolved access evidence, 2 source warnings, 24 records with no known management issues, and 113 with multiple categories. Site counts: 68 fully field validated, 0 partial, 63 with none recorded; 112 need staff review and 16 have no known management issues. Counts overlap where categories do.

External data successfully acquired earlier remain intact: four supplied MAPC GIS networks (83,749 source features), verified official MAPC metadata/code definitions, and frozen official MBTA feed SHA-256 `da552d2330c9b85c2ad7ddb5d71012bb9539b2ba5b822d7000d7a3606ec79296` (7,877 stops/stations and 1,163 shapes). No source data or transit feed was reacquired.

Known limitations: 40 missing coordinates, two retained Municipality values `02176`, four unresolved access conflicts, and fallback identities remain source-review items. No previous-input comparison is loaded, so change review is disabled with an explanation. Street tiles require the local HTTP viewer and internet; direct-file/offline use retains local inventory and overlays. Native macOS/Linux execution is not verified; no macOS debugging was undertaken. See the handoff for exact scope.

Final map: `output/maps/MAPC_access_map.html`. Open the street-map viewer with `.venv\Scripts\python -m src.serve_map` on Windows, or `python -m src.serve_map` in the activated environment. The exact next recommended step is to use the completed read-only map and review the existing source issues; no pipeline run is needed to view it. For a future presentation change, use `python -m src.rebuild_map`; a future input update follows README's full-build workflow.

The unchanged analytical release is `releases/MAPC_Recreation_Analysis_2026-09-30_1.0.0_140509809545.zip`. It predates this redesign and does not contain the current UI. No new release archive or full clean rebuild was created for this presentation-only completion. Current map provenance and validation hashes are in `output/reports/map_build_manifest.json`. Full final handoff: `notes/MAP_HANDOFF.md`.

## Previously completed analytical state (historical checkpoint)

The project is **complete**. The complete software/data build and required clean-rebuild acceptance passed. Current run manifest status is **success**, with no errors. Release packaging and archived-file checksum/ZIP integrity verification also passed. The release is `releases/MAPC_Recreation_Analysis_2026-09-30_1.0.0.zip`; its final byte size and checksum are in `releases/release_index.json`. Earlier failures below have been repaired, their outputs archived, and they do not describe the current deliverables.

## Final verified results

- All 13 original files and their organized copies match initial checksums. No original input/reference was overwritten or deleted.
- Current data: 213 source rows retained, 211 accepted assets, 2 blank quarantine records, 131 sites. Primary analysis: 101 validated assets at 68 sites; 27 staff-reviewed assets. Vocabulary: 15 attributes and 40 activities.
- Map: 171 markers, comprising 101 validated on by default and 70 unvalidated off by default. Forty accepted assets lack coordinates and remain in the data and explicit map-omission report.
- GIS: all 83,749 source features preserved. Current/public eligibility: 9,707 bicycle, 4,665 shared-use, 54,089 walking and 2,723 landline features. All source CRS verified as EPSG:26986; full lines support analytical distance and simplified WGS84 lines support display.
- Official cached MBTA snapshot unchanged: 7,877 served stops/stations and 1,163 shapes. Transit among accepted assets: 96 YES, 75 NO, 40 UNKNOWN without coordinates. Zero comparable recorded-YES vs calculated-NO discrepancies.
- Four complete Excel workbooks, 13 computed findings, eight PNG/SVG chart pairs, data dictionary/methodology, interactive map and static PNG/SVG are saved.
- All 92 unit/integration tests passed. Real browser checks passed initialization, expected markers/defaults, complete tooltips/popups, every GIS/transit/validation layer toggle and offline reload. No fatal JavaScript errors; 42 online basemap tiles loaded with zero errors.
- All 18 workbook sheet opening regions rendered and reviewed, along with all eight charts. Native Microsoft Excel application was not automated; OOXML files, numeric types, table dimensions and Excel-error checks passed.
- Clean rebuild preserved baseline at cache/rebuilds/20260930T133754669718Z/output. Every one of 32 canonical data/analysis CSVs has identical SHA-256 after regeneration. All 42 artifact acceptance checks passed.
- Windows PowerShell launcher dependency checking and argument forwarding succeeded. The optional authoring QA renderer is not a normal pipeline dependency.

Known review items: missing source stable IDs require documented fallback keys; 40 assets lack coordinates; two Municipality cells contain postal code 02176 and are retained/flagged; four access conflicts remain (three accessible-parking and one restroom availability). Unknown GIS status/type and nonpublic/proposed/gap features are explicitly excluded, not silently dropped. Proximity does not establish an accessible route. Findings remain descriptive and account for site clustering.

No required implementation or testing remains. Exact next recommended step for the next student: read README.md, replace the full CSV in input/assets when an updated export is available, double-click run_pipeline.bat, and review output/reports/QC_report.html. No Python source editing is required. The release excludes original raw/reference data and the GTFS ZIP; preserve input/, reference/ and cache/transit/ in the institutional archive for exact reproduction. Source-data review items above remain visible and are not treated as software failures.

## Historical checkpoint log

## Completed work confirmed by disk inventory

- All 13 original root files remain present. Initial bootstrap/root_inventory.csv and bootstrap/bootstrap_report.html exist, with copied inputs/references in the professional folder structure. Checksums will be reverified before processing.
- Python .venv and pinned requirements.txt exist, together with README.md, CHANGELOG.md, pyproject.toml, Windows launchers and .gitignore.
- Five configuration files exist: config.yaml, schema.yaml, column_aliases.yaml, attribute_taxonomy.yaml and mapc_gis_codes.yaml.
- Source modules exist for bootstrap, configuration, schema validation, asset/attribute/activity/coordinate parsing, reconciliation, site aggregation, version comparison, GIS decoding/loading, spatial analysis, bike proximity, GTFS acquisition, transit calculation, analysis, charts, workbooks, documentation, interactive/static maps, browser checks, QC, provenance, release packaging and pipeline orchestration. Vendored Leaflet JS/CSS/license exist.
- Tests exist for schema, assets, attributes, activities, coordinates, access profiles, validation, site aggregation, version comparison, GIS, spatial distance, transit, map and pipeline. Some tests ran before interruption, but no authoritative full-suite result has been saved.
- Methodology notes exist for asset parsing and analysis. Official GIS metadata and MAPC source-code evidence were cached under reference/gis_metadata/.
- The only generated data outputs currently present are output/gis/mbta_stops.csv, mbta_stops_web.geojson and mbta_routes_web.geojson.

## Current data counts (last observed, to reverify)

- Asset source: 213 records including 2 blank records; 211 identifiable assets.
- Explicit finished/validated assets: 101. Explicit staff-reviewed assets: 27.
- Distinct recorded attributes: 15. Activities: 40.
- Transit snapshot: 7,877 served stops/stations and 1,163 route shapes.
- All four supplied GIS ZIPs were read and their CRS reported as EPSG:26986; final eligibility counts remain to be calculated.

## External data acquired

- Official MBTA feed at https://cdn.mbta.com/MBTA_GTFS.zip.
- Cached ZIP: cache/transit/da552d2330c9b85c2ad7ddb5d71012bb9539b2ba5b822d7000d7a3606ec79296.zip.
- Reported size: 24,684,859 bytes. Feed Fall 2026 version D, feed dates 2026-09-22 through 2026-12-12. JSON provenance and active snapshot pointer are saved.
- Official MAPC ArcGIS metadata for four network types and official MAPC trail-map JavaScript label tables are saved. Bicycle domain integration was interrupted: config still has an empty bicycle domain mapping. Do not classify numeric bicycle statuses until the cached official evidence is verified and mapped.

## Known warnings and incomplete verification

- Original assets have no stable MAPC IDs. Deterministic name-based fallback identifiers have rename/collision limitations documented in README and asset notes.
- Missing tags stay Unknown, not No. Source field-guide interpretation of transit walking routes is intentionally separate from the user's required radial half-mile calculation.
- Earlier pytest attempts encountered Windows temporary-folder permissions. Some residual pytest-cache-files directories remain; no source files were removed.
- Configuration and module interfaces were written in parallel and need integration validation. Site access rule naming was aligned before interruption; remaining inconsistencies must be tested.
- Files may have been interrupted near final write. Syntax/YAML/JSON/ZIP/checksum verification is the next action; existence alone is not treated as proof of correctness.

## Unfinished master requirements

1. Verify all saved modules, config, caches and original checksums; repair only confirmed defects.
2. Complete verified bicycle coded-value mappings and GIS eligibility processing.
3. Run integrated parser/reconciliation/GIS/transit/site/analysis processing using the existing cached feed.
4. Generate and reconcile cleaned datasets, dictionaries, audits, GIS GeoPackage, web layers, workbooks, findings, charts and documentation.
5. Generate and visually inspect interactive/static maps; run actual browser interaction and offline checks with screenshots.
6. Complete meaningful tests, workbook validation, QC, structured logs and full provenance manifest.
7. Perform a clean rebuild from immutable sources/config/code and frozen transit cache; verify canonical CSV checksums and all acceptance requirements.
8. Build and inspect the release ZIP, document exclusions, update this progress file with actual results, and provide the user with final artifact links.

## Resumption verification and first integration (2026-09-30)

- Verified SHA-256 of all 13 original files and all 13 organized copies: all match original inventory.
- Verified cached GTFS SHA-256 and every ZIP member CRC: intact; no re-download performed.
- Parsed all 42 initially saved source/test modules and all five YAML configs successfully; no truncated source/config files found.
- Reconfirmed 213 rows, 211 accepted, 2 blank quarantine, 101 finished, 27 staff-reviewed, 15 attributes, 40 activities; 171 valid coordinates and 42 missing (including the two blank records).
- Verified dependency installation with pip check: no broken requirements.
- Initial complete test suite passed 67 tests after granting the Windows temporary-folder access needed by fixtures. Additional meaningful regression tests are being added for integration issues.
- Official MAPC MapcTrails MapServer metadata resolved bicycle coded domains. All original GIS geometry remains preserved. Final eligible counts after excluding unknown facility types and landline gaps: bicycle 9,707; shared-use 4,665; public walking 54,089; landline 2,723.
- First integrated build completed source/schema parsing, 1,278 long-form audit rows, GIS loading, full-line indexed spatial calculations, cached official transit calculation, analysis tables and eight PNG/SVG chart pairs. It stopped at Excel export because pandas re-coerced blank numeric cells to NaN; the writer now normalizes at the actual cell-write boundary and a regression test passes.
- The failed-run manifest and run_failure.json correctly record that incomplete build. The repaired integrated build is now in progress. A final successful run must supersede that failure and undergo clean rebuild before delivery.

## Exact next recommended step

Verify the three saved workbook ZIPs and the latest source syntax; finish the interrupted downstream workbook/documentation stage using existing cleaned data. Implement already-identified output/provenance safeguards (archive prior outputs, detect removed baseline CSVs, no root-copy dependency in handoff, complete failure manifest). Generate maps and perform browser/visual checks. Then establish a fully checked baseline, perform required clean rebuild, verify canonical CSV equality and acceptance, and create the release. Do not refresh GTFS or re-ingest preserved root files.

## Second resumption disk findings

- Pipeline log ends at workbook read-back failure caused by substring matching `share` inside `shared_use_path`. Source now contains the fix using whole underscore-delimited tokens; nullable numeric fix also remains intact.
- Existing saved workbooks: assets_clean.xlsx, sites_summary.xlsx and analysis_workbook.xlsx. Data dictionary and methodology output are still absent; their module exists but the downstream authoring command was interrupted or failed before completion.
- Eight chart pairs and 24 analysis CSV tables/findings exist. All four network layers are saved in a 92 MB GeoPackage, with local web layers and official transit outputs.
- New meaningful tests/test_analysis.py and tests/test_provenance_release.py survived. Full-suite results after those additions have not yet been recorded.
- Source/config/cache/original counts and official feed details above remain applicable; no original/reference files were modified by the repair runs.

## Latest verification checkpoint

- Four Excel workbooks now open and pass typed-cell/OOXML checks (assets, sites, 13-sheet analysis, 3-sheet dictionary). Numeric grouping/NaN handling defects were corrected and tested. Site totals: 131 across all accepted assets, 68 represented by the 101 validated assets.
- Maps generated from saved verified outputs. All 171 usable-coordinate assets mapped: 101 validated on by default, 70 unvalidated in a separate off-by-default layer. Forty accepted rows omitted for missing coordinates remain in the clean data and explicit omission list.
- Real browser smoke test passed map initialization, expected markers, full tooltip/popup content, all network/transit/validation toggles, and network-blocked offline reload, with no fatal JavaScript errors. Esri basemap loaded 42 tiles with zero tile errors. Screenshots saved. Test harness object-serialization issue was corrected.
- Full expanded unit suite: 92 passed. Original file preservation, official metadata/cache, and existing geometry remain intact.
- Visual review found two source municipality values containing postal code 02176. They are retained and now flagged in schema type diagnostics; numeric postal labels are suppressed on the static map without guessing municipality names.
- Output archival, complete failure manifests, baseline removed-file detection, previous-input provenance and release-name collision protection have been implemented. Next: finish workbook visual layout check, run one complete integrated checked baseline, then clean rebuild and release acceptance.
