# MAPC work progress

Updated: 2026-09-30, after successful clean rebuild. Earlier checkpoint sections below are a historical work log.

## Inventory management map update — in progress (2026-09-30)

Active root: C:/Users/Jaeyun/Desktop/MAPC Ultimate Deliverables. Documents/WPI-IQP is an identical Git/main commit 55cb526 copy with the same analytical manifest checksum; the current Desktop workspace includes the working environment. Both started clean. The completed analytical build below remains verified historical evidence. This new task covers safe root cleanup, macOS/Linux launcher, management map UI, and targeted tests only. No new analytical processing is required. Counts remain 211 accepted assets, 131 sites, 171 mapped (101 field validated, 70 unfinished), 40 without coordinates, and 27 staff reviewed. External MAPC GIS and frozen MBTA cache are retained. Known source warnings remain unchanged.

Next: verify cleanup hashes, build the display-only management model from saved outputs, render the redesigned map, and run targeted unit/browser checks. Baseline hashes of source/reference, analytical CSVs/workbooks/GIS/charts, static maps, frozen transit, original manifest/QC and release are in notes/map_redesign_baseline.json. The existing release remains the pre-redesign analytical release; current UI provenance will be recorded separately.

## Previously completed analytical state

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
