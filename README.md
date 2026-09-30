# MAPC Recreation Data Analysis

Version 1.0.0 · WPI student handoff · Python 3.12+

This project rebuilds a traceable recreation inventory, descriptive analyses, Excel workbooks, GIS layers, charts, interactive and static maps, and a versioned release from current MAPC inputs. Authoritative source bytes are preserved in `input/` and `reference/`; redundant loose root copies were removed only after matching SHA-256 checksums. Start with `output/reports/QC_report.html` to understand each analytical run's coverage and limitations.

## Quick start on Windows

1. Install Python 3.12 or newer if Python is not already available.
2. Double-click **run_pipeline.bat**. The launcher creates a local `.venv`, installs the pinned requirements when needed, and runs the pipeline.
3. Read **output/reports/QC_report.html**.
4. Open **output/maps/MAPC_access_map.html** and **output/analysis/analysis_workbook.xlsx**.

The current project already includes its local environment. On another computer, the first run requires internet access to install Python packages. Chromium, Chrome or Edge is needed for automated browser checks. Edge is tried first on Windows; alternatively run `.venv\Scripts\python -m playwright install chromium`.

For an activated Python environment:

```powershell
python -m pip install -r requirements.txt
python -m src.pipeline
```

The equivalent PowerShell launcher is `powershell -ExecutionPolicy Bypass -File .\run_pipeline.ps1`. All data paths are relative to this project; moving the project does not require editing Python source.

## macOS / Linux and opening the management map

Run `sh ./run_pipeline.sh` to build the complete project. The launcher resolves its own folder, uses `.venv/bin/python`, creates the environment if needed, and installs requirements only when its successful-install checksum stamp is missing or changed. It forwards arguments to **`python -m src.pipeline`**; do not execute `src/pipeline.py` directly. Python 3.12+ is required. The launcher has been syntax- and stub-tested on Windows Bash; native macOS/Linux execution has not been tested.

For an existing saved map, activate the environment and run **`python -m src.serve_map`**. This opens the map through a server bound only to `127.0.0.1`, allowing the browser to send the HTTP Referer required by the street-map provider. No inventory is uploaded. Windows can use `.venv\Scripts\python -m src.serve_map`; macOS/Linux can use `.venv/bin/python -m src.serve_map`. Stop the server with Ctrl+C.

Opening `output/maps/MAPC_access_map.html` directly works in local/offline mode. Its inventory, review queue, evidence, GIS and transit overlays are embedded. Street labels and online street tiles require the local HTTP viewer and an internet connection.

To update **only presentation**, run `python -m src.rebuild_map`. This verifies the successful saved analytical manifest, source, cleaned data and display-layer checksums, then renders only the HTML and map build reports. It does not run the parser, spatial analysis, transit acquisition, workbooks, charts, static map, release packaging or full test suite. A separate `output/reports/map_build_manifest.json` links the UI build to its original analytical manifest. Historical releases and `run_manifest.json` remain unchanged; their original HTML/config hashes describe their original build. Current map test evidence is `output/reports/map_management_test_results.json`.

## Updating the inventory

Replace the CSV in `input/assets/` with the new full MAPC export. Keep exactly one current CSV there, or set `paths.asset_file` in `config/config.yaml`. Preserve the previous export outside that directory for comparison. Replace the four GIS ZIPs in `input/gis/` only when newer exports are available. Run the launcher again.

The parser discovers records, attributes and activities from the new export; no row counts or particular assets are hardcoded. Add new header aliases in `config/column_aliases.yaml` if the export changes terminology. Missing required fields, duplicate headers and alias collisions fail clearly in the schema report rather than silently shifting columns.

Optional root ingestion inventories recognized new root files, copies them into the project, and preserves replaced same-named inputs by checksum under `cache/input_versions/`:

```powershell
python -m src.bootstrap_project
python -m src.pipeline --ingest-root
```

Do not use root-ingest after updating only `input/assets/` while leaving an older same-named CSV in the root: root-ingest deliberately copies the root version. Normal updates do not re-ingest root files.

## Folder structure

| Folder | Role |
|---|---|
| `bootstrap/` | Original root inventory, SHA-256 checksums, copy destinations and explanations |
| `input/assets/` | Current authoritative full MAPC CSV |
| `input/gis/` | Original zipped MAPC Shapefiles, including projection and attribute files |
| `input/gis_reference/` | Original basecols CSV exports; reference, not geometry substitutes |
| `input/transit/` | Reserved for supplied official transit packages |
| `reference/` | Field guides, project requirements, previous audits and authoritative GIS metadata |
| `legacy/` | Prior processed datasets, old maps or scripts; never source truth |
| `config/` | Schema, aliases, taxonomy, verified GIS codes and run settings |
| `src/` | Executable processing modules and vendored Leaflet library/license |
| `tests/` | Parser, GIS, transit, analysis, map and integration regression tests |
| `cache/` | Exact GTFS snapshots, external-source copies, archived inputs and rebuild baselines |
| `output/` | Regenerated datasets, maps, charts, documentation and reports |
| `releases/` | Versioned ZIP archives and latest archive checksum |

## Source hierarchy and bootstrap

The current asset CSV is authoritative for recorded MAPC values. Its schema and content identify it, rather than its filename alone. Local MAPC ZIPs supply geometry. Official MBTA GTFS supplies independently calculated transit proximity. Field guides clarify definitions. Previous fact-check audits provide evidence to re-evaluate; they never overwrite the current record simply because a name matches.

`bootstrap/root_inventory.csv` was written before copying or transformation. It records every original root file's name, size, checksum, classification and destination. `bootstrap/bootstrap_report.html` explains initial placement. The subsequent `bootstrap/root_cleanup_report.csv` and `.json` record removal of 13 redundant loose files after each source/destination pair matched both each other and the original inventory. No mismatches occurred. Original bytes and filenames remain in organized destinations: one asset CSV in `input/assets/`, four geometry ZIPs in `input/gis/`, four base-column references in `input/gis_reference/`, two guides in `reference/field_guides/`, and two audits in `reference/previous_audits/`. `input/input_bak` was absent. Historical bootstrap evidence was not rewritten. Additional ingests create timestamped inventories rather than replacing the original inventory. See `notes/project_organization.md` for the cleanup, ignored-folder placeholders and launcher checks.

## Data contract and traceability

`config/schema.yaml` declares required and optional canonical fields. `config/column_aliases.yaml` maps export headers. Parsing uses header names, never fixed source column positions. The schema report includes missing, unexpected and duplicate headers, applied aliases, type issues and changes from the preceding run when available.

Source IDs are preserved when supplied. Without them, asset identities hash normalized site name, asset name and municipality; site identities hash normalized site name. **These are fallback identities, not authoritative MAPC identifiers.** Renames may change them; unrelated sites with the same name can be conflated. Cross-town sites intentionally retain one site identity. Version comparisons flag uncertain rename candidates for review without applying fuzzy matches.

Every source record retains its source filename/checksum, CSV record number, physical line start/end, raw record JSON and source-row UID. CSV record numbers differ from physical line numbers when descriptions contain newlines. Blank records, malformed rows and duplicate identity conflicts are retained and quarantined. Accepted exact duplicates contribute one analytical observation; the other rows remain traceable.

## Attributes, physical amenities and activities

All structured attributes are preserved in `attribute_list` and counted in `attribute_count`. The taxonomy assigns each tag to physical amenity, accessibility, transportation access, policy/rule, site characteristic or other. A separate `is_amenity` flag marks tags describing physical facilities or equipment, including accessible parking/restrooms whose primary group is accessibility. `amenity_count` counts these tags; it is not the number of unique facilities or pieces of equipment. Two tags can describe the same restroom. Unknown new tags are preserved as other and appear in dictionaries for review.

Activities are discovered from the source without a fixed vocabulary. Lists preserve source wording while normalizing whitespace and accidental duplicates. Raw cells remain available. JSON arrays are used in CSV/Excel list fields so commas inside labels are unambiguous.

## Coordinates and validation

Coordinate parsing handles separated latitude/longitude and combined location strings, validates geographic ranges, identifies reversed values, and flags suspicious locations outside the study region. Records with unusable coordinates remain in the data and QC but do not receive invented distances or map positions.

Explicit finished/checked/true/yes values mean field validated. Explicit unchecked/false/no values mean unfinished. Blank or unrecognized statuses mean Unknown. The configured interpretation and unrecognized values are reported. Staff review remains independent from collection completion. The map defaults to validated assets on and unfinished/unknown assets off. The latter have dashed outlines and lower opacity.

## Three-state fact-checking

Access fields use **YES / NO / UNKNOWN**. An absent structured tag is Unknown. Each field retains original and audited values, verification status, evidence and source. Narrow explicit statements in the current finished-record narrative can resolve missing tags; source contradictions stay flagged. Prior audits are matched by stable ID when possible or unique exact normalized identity, with possible fuzzy matches retained only as review candidates.

The combined MAPC **Free Entry / Parking** tag means both entry and designated parking meet the guide's free-access definition. It is not a separately surveyed parking-only field. Generic admission statements do not establish free parking. Accessibility features are separate evidence dimensions, not a universal site accessibility score.

With official transit data, final audited transit uses the documented calculation. Disagreements retain the structured original and appear in `transit_discrepancies.csv` and the long fact-check audit; corrections are explicitly labeled. Without transit data, the MAPC evidence is preserved and calculated results stay Unknown.

## Transit definition, download and caching

**Near public transit = an MBTA stop or station within 0.5 mile of the asset.** The pipeline enforces exactly 0.5 mile, including the boundary. It includes served bus, subway, light rail, Silver Line, commuter rail and ferry stops/stations represented in the feed. This is radial proximity, not proof of a walkable or accessible route, reliable service frequency, or an open entrance.

The official feed source is `https://cdn.mbta.com/MBTA_GTFS.zip`. Snapshots are cached with retrieval time, feed dates/version, byte size and SHA-256. The cached version is reused by default and the manifest records the exact snapshot. Set `transit.refresh_gtfs` or run:

```powershell
python -m src.pipeline --refresh-transit
```

Failed downloads do not destroy unrelated processing. QC prominently reports unavailability and the map still builds. Keep the full `cache/transit/` folder for historical reproducibility. Updating the live feed intentionally changes analysis evidence; a current feed is not a reconstruction of historical service on the unknown collection dates.

## GIS processing

The ZIP reader verifies the presence of SHP, SHX, DBF and PRJ, reads directly from the preserved package and verifies its CRS. Full-fidelity geometries are transformed to the configured projected metre CRS (EPSG:26986 for this study). Spatial indexes compute nearest **point-to-line** distances, never centroid distances or degree-based approximations.

Numeric codes are decoded only from verified authoritative MAPC metadata recorded in `config/mapc_gis_codes.yaml`. Unknown codes remain Unknown. Only confirmed Existing infrastructure is eligible. Walking trails also require confirmed public access. Planned, private, closed, lost, unknown and invalid features remain in the GeoPackage with exclusion reasons. The land-line layer is retained as context but is not used as a fourth access mode because it overlaps the other network systems.

Web layers use topology-preserving Douglas–Peucker simplification in projected metres, then WGS84; the configured tolerance and feature counts are reported. Analytical distances always use the full-resolution lines. Local GeoJSON is embedded in the interactive map, with no live MAPC geometry service dependency.

## Map encoding and reliability

- Marker **size** defaults to `attribute_count`, labeled **Number of recorded MAPC attributes/features**. Change `map.size_metric` to `amenity_count` for the documented physical-amenity subset. Fixed thresholds and radii are configured for comparable future releases.
- The default **Inventory management** view colors records by transparent workflow/QC rules. **Transportation profile** preserves the final audited transportation encoding. Its colors are blue `#0077C8` (transit + free parking), amber `#FFB000` (transit only), magenta `#C2187A` (free parking only), charcoal `#3D4650` (neither), and `#AAB4BE` (unknown/unresolved).
- Attribute bins remain 0–2, 3–5, 6–8, 9–11 and 12+. Radii are now 5, 8, 12, 17 and 23 CSS pixels, drawn at those exact sizes in the legend. Field-validated markers use solid outlines; unfinished markers are dashed and less opaque. The validated layer starts on and the unfinished layer starts off. Operational queue selections can reveal relevant unfinished records.
- Hover shows site, asset, municipality, separate field/staff states and complete feature, amenity and activity lists in a responsive wide card. Click opens a right-side details drawer (bottom sheet on small screens) with the same inventory, separate source/final access values, evidence, distances, exact issue reasons, site progress and collapsed provenance. Nearby coincident records are individually selectable. No values are edited.
- Toggle existing bike facilities, existing shared-use paths, public walking trails, unvalidated assets, transit stops and available transit route modes independently. Transit/GIS layers are initially off for readability.

Leaflet and local data are bundled into the HTML. The full-viewport map has floating controls, an extent-based Home button, collapsible legend and compact About/methods panel. Fractional zoom uses `zoomSnap=0.25`, `zoomDelta=0.25`, `wheelPxPerZoomLevel=120`, `wheelDebounceTime=40`, and zoom/fade/marker animations. No Apple Maps resources are used.

Online streets use **OpenStreetMap Standard** (`https://tile.openstreetmap.org/{z}/{x}/{y}.png`) with visible linked © OpenStreetMap contributors attribution. Normal browser caching and Referer behavior are retained; there is no tile downloader or offline tile archive. Use is subject to the [OSMF tile policy](https://operations.osmfoundation.org/policies/tiles/) and [OSM copyright/license](https://www.openstreetmap.org/copyright). CARTO was considered, but its [current service terms](https://www.carto.com/legal/basemap-terms/) require an issued API key. The configurable provider can be changed for an institutional licensed service later. A tile failure triggers a temporary warning and local fallback; normal successful loading shows no developer status banner.

The static PNG/SVG retains the earlier analytical release styling and was not regenerated for this UI change. It uses local geometry and never needs online tiles. This project does not publish the inventory to a public service.

## Inventory management rules

This read-only map supports internal inventory QA and fieldwork review. It has no park recommendations, ranking, routing, activity discovery filters or overall accessibility/quality score. Unknown access evidence remains Unknown; Free Entry / Parking retains the combined source concept; the 0.5-mile transit rule and full-line GIS calculations remain unchanged.

| Queue / status | Exact display rule |
|---|---|
| Field collection incomplete | `field_validated` is not explicitly true |
| Staff review pending | `staff_reviewed` is not explicitly true, independently of field status |
| Missing usable coordinates | `coordinate_usable` is not explicitly true |
| Access conflict / unresolved | An access verification status is one of the explicit unresolved/conflict statuses in `notes/management_rules.md`; plain Unknown and resolved corrections alone do not qualify |
| Source / data-quality warning | Current-source schema row diagnostic, nonempty record issue, non-unique duplicate status, or explicit usable-coordinate warning |
| Changed since previous snapshot | A change row belongs to the current run's checksummed comparison with an identified previous input; no comparison is fabricated |
| Multiple issues | At least two distinct issue categories apply; all reasons remain visible |
| No known management issues | None of those issue categories applies; this is about recorded workflow/evidence, not place quality |

The summary and queue are calculated from all accepted records. Search covers site, asset and municipality for record lookup. Selecting a queue reveals its affected mapped records and retains unmapped records in the list. Queue CSV downloads are labelled management/QC extracts, not authoritative datasets. Records without usable coordinates expose identity, validation, staff review, omission reason and full details without inventing positions.

Site progress reconciles every accepted member against the existing site dataset: all field validated = fully field complete; some = partial; none = not started. Staff review counts and the need for review remain separate. Percentages mean field/staff coverage only. Source value, audited/final value, verification, evidence and evidence source remain separate for every access dimension. Snapshot metadata identifies the analytical run, source hash, MBTA snapshot, GIS sources and QC state. No valid previous-input comparison is loaded for the current snapshot, so change review is disabled with an explanation. Future verified comparisons can show additions, removals, coordinate/list/access/validation changes and review-only rename candidates.

See `notes/management_rules.md`, `notes/map_validation.md`, and `notes/MAP_HANDOFF.md` for detailed rules, targeted validation and this revision's handoff.

## Analysis and statistical limits

Primary analysis uses accepted, field-validated assets. All cleaned records remain available. Asset summaries are descriptive because assets within a site are clustered. Separate site comparisons give each represented site one observation and aggregate validated members only. The all-record site summary is also supplied.

Site feature/activity sets are unions. An access field is YES if any contributing asset is YES, NO only if all are NO, otherwise Unknown. Transit and parking may be evidenced at different entrances; the site summary explicitly records their co-location count. Site field_validated/staff_reviewed are True when all members are explicitly True, False when any is explicitly False, and otherwise Unknown. Separate member counts and all/any completeness flags permit other views without converting missing evidence to No.

The analysis investigates all 13 requested relationships, including transportation, feature richness, activities, physical accessibility, bike/trail proximity, subregion and Inner Core comparisons. Counts, known denominators and Unknown states accompany results. Spearman coefficients describe rank association; no p-values or significance claims are made. Feature richness partly contains the same access tags used to form groups, so an adjusted richness view removes the three focus accessibility tags. Small and uneven groups, recording completeness and unknown evidence limit interpretation. See `output/analysis/findings.md` and the Methodology notes worksheet.

## Outputs

| Location | Contents |
|---|---|
| `output/data/` | Assets and sites CSV/XLSX, map dataset, all dictionaries, fact-check audit, discrepancies, quarantine and omissions |
| `output/analysis/` | Analysis workbook, chart source CSVs, findings for the 13 research questions |
| `output/gis/` | Normalized `mapc_networks.gpkg`, web GeoJSON, available transit layers |
| `output/maps/` | Interactive `MAPC_access_map.html`, static PNG and SVG |
| `output/charts/` | Report/poster figures in PNG and SVG |
| `output/documentation/` | Data dictionary workbook/CSV and methodology |
| `output/reports/` | QC, schema report, manifest, test logs/screenshots, workbook validation, optional change report and clean-rebuild acceptance |
| `output/logs/` | Pipeline event log |

The manifest identifies input/reference/config/code checksums, dependency versions, processed counts, GIS feature counts, GTFS provenance, command-line options, optional previous-input provenance, warnings/errors and every generated artifact. Each new run archives previous generated outputs in `cache/run_history/` (or `cache/rebuilds/` for a clean rebuild), preventing stale optional reports from entering a new release. Each release's checksum is recorded in `releases/release_index.json`.

## Tests, clean rebuild and version comparison

```powershell
python -m pytest -q
python -m src.pipeline --clean-rebuild
python -m src.pipeline --previous "reference/project_docs/older_assets.csv"
```

Normal runs execute unit/integration tests and a real browser smoke test. The browser checks initialization, counts, tooltips, the management drawer/queue, GIS/transit/validation layer toggles, JavaScript errors and offline reload, and saves screenshots. If no supported browser is available, QC states that limitation instead of claiming a pass. An actual test failure blocks release creation. Presentation-only revisions run relevant unit and browser tests without repeating the analytical build. Historical full-build test results remain distinct from current UI test reports.

Clean rebuild moves previous outputs into a timestamped `cache/rebuilds/` folder, regenerates from input/reference/config/source and the frozen transit cache, then compares canonical CSV checksums. Output timestamps, Excel archive metadata and binary GIS internals need not be byte-identical. Source raw checksums and canonical CSV equality are the reproducibility controls. A changed input/config is expected to change those CSVs and is reported.

Version comparison detects source-based additions/removals, coordinate, attribute/amenity/activity, access and validation changes. Possible renames are review-only. Transit comparisons do not falsely apply today's feed to a historical export. `--skip-tests` is for development and disables release generation; `--no-release` runs all checks without a ZIP.

## Release and institutional archival handoff

A successful checked run creates `releases/MAPC_Recreation_Analysis_<date>_<version>.zip`. It contains code/config/tests, README/dependency files, processed outputs, GIS layers, map, charts, workbooks, methodology, QC and manifest. Earlier same-day releases are retained with a timestamp suffix.

The distributable ZIP conservatively excludes original raw MAPC files, prior audits, field guides and the GTFS snapshot because redistribution permissions were not provided. Keep **input/, reference/, cache/transit/** with the release in the institutional project archive for exact reproduction. The ZIP contains derived data and map geometry; confirm permission before public distribution. Exclusions are explicitly documented inside the ZIP. Nothing is uploaded by this pipeline.

## Troubleshooting

**Python unavailable:** Install Python 3.12+ and enable its Windows launcher. The `.venv` directory is machine-specific; create a fresh environment after moving to another computer.

**Multiple current CSVs:** Move older exports to reference or configure the exact authoritative file. Do not substitute an old processed dataset.

**Schema failure:** Open schema_report.html, inspect missing fields/aliases, and update configuration only when the new meaning is known. The pipeline writes run_failure.json and does not produce a successful release.

**GTFS unavailable:** Use the cached official snapshot or restore network access and refresh. Do not interpret unknown calculated distances as No.

**Unknown GIS codes:** Inspect the cached official metadata and code mapping. Do not guess; unknown-status infrastructure is excluded from access calculations.

**Excel file in use:** Close the output workbook before rerunning so Windows permits replacement.

**Browser unavailable:** Install Edge/Chrome or the Playwright Chromium browser, then rerun. If map tiles are blocked, choose Local data (offline) and toggle local networks, or use the static map.

**Unexpected QC counts:** Check quarantine, duplicate identity conflicts, validation interpretation and map_omissions.csv before changing analytical filters. Unvalidated records are deliberately retained but excluded from primary findings.

**Reproducing a past release:** Restore exact input/config/code and cached transit snapshot identified by the manifest. Do not refresh transit. Run the clean rebuild and compare canonical dataset checksums.
