# MAPC Recreation Inventory Tool

A read-only, interactive management map for the WPI / MAPC recreation inventory. Staff can review fieldwork, missing locations, source evidence, site progress and transportation proximity in one map.

## Quick Start

**Windows**

1. Put the newest full Airtable CSV in `input/assets/`. Keep exactly one CSV there; any filename is accepted.
2. Double-click **Run_MAPC_Tool.bat**.
3. Wait for processing. Your default browser opens the updated map automatically.

**macOS**

1. Put the newest full Airtable CSV in `input/assets/`. Keep exactly one CSV there; any filename is accepted.
2. Double-click **Run_MAPC_Tool.command** in Finder.
3. Wait for processing. Your default browser opens the updated map automatically.

Keep the launcher window open while using the map. Press **Ctrl+C** in that window to stop the local server. Each launch rebuilds the inventory from the current inputs before opening it.

**First-time prerequisites:** Python **3.12 or newer**, a default web browser, and the complete project data folder. The launcher creates a local `.venv` and installs the pinned application dependencies when needed. Package installation needs internet access; ordinary use can reuse installed packages and the verified transit cache. On Windows, include the Python launcher when installing Python. On macOS, use a supported Python installation discoverable as `python3`.

Raw GIS packages, the asset export, reference material and transit cache are intentionally not stored in Git. A source-code clone alone is not the complete MAPC data bundle; obtain those inputs from the project custodian. Do not copy another computer's `.venv`.

The macOS launcher is implemented for Finder use and checked from Windows; **native macOS execution has not been validated**. The repository must preserve its executable permission. If an archive or download removes that permission, a maintainer must restore it before distributing the folder to staff.

## Updating the Airtable inventory

Replace the existing CSV in `input/assets/` with the newest **full inventory export**, then double-click the launcher again. Move older exports outside that folder. The filename does not need to match the example below.

```text
input/
  assets/
    Newest full Airtable export.csv
```

The tool rejects zero or multiple CSVs with a clear message. It does not choose a file by date or silently select one filename. The export must include asset name, site name, attributes, activities, field-validation status, and either a combined location column or separate latitude/longitude columns. A required location column can contain blank values; those accepted records remain available without map positions.

`config/schema.yaml` declares the data contract and `config/column_aliases.yaml` maps known Airtable headers. Header order does not matter. Missing required columns, duplicate headers and alias collisions stop processing with an explanation. Maintainers should add aliases only when the new header's meaning is established.

The current source CSV is authoritative for recorded values. Prior audits are evidence references; they do not automatically replace current observations. Original input and reference files are read without modification.

## Using the map

- **Inventory management** colors records by explicit workflow and evidence issues. **Transportation profile** colors them by final reconciled transit and combined free entry / parking values.
- **Circle size** defaults to recorded accessibility features. Switch to **All recorded attributes** for the broader tag count. This is independent of color mode, search and review queues; the legend and details counts follow your choice.
- **Search** covers site, asset and municipality. It intersects with the selected **Review Queue**. Nonmatching asset markers are removed from the display completely; opacity does not represent a filter mismatch.
- The **Review Queue dropdown** is the only queue selector. Select **All inventory records** and clear search to restore every mapped record immediately, without refreshing. Clearing search alone restores records allowed by the current queue.
- **Assets without coordinates** is a display-only summary metric. Select its queue in the dropdown to inspect those records in the list and details drawer. No positions are invented, and no unrelated asset markers remain on the map.
- **Workflow & site summary** shows field-validation and staff-review coverage separately, calculated from all accepted member assets.
- Hover over a marker for complete attribute, amenity and activity lists. Move into the card to scroll long lists. Leaving the card closes it promptly; later intentional marker hover opens it again.
- Select a marker or list record to open the **details drawer**. It includes source and final access values, evidence, spatial context, site progress and provenance. Records at coincident locations can be selected individually.
- **Layers**, **Legend**, **Home** and **About** provide map controls and methodology. GIS networks, eligible MBTA stops and available route modes can be displayed independently.

All mapped records are shown initially. Visible markers retain their management/transportation colors, count-based sizes and validation styling: solid outlines for field-validated records, dashed outlines and lower normal fill opacity for unfinished/unknown records. These encodings never change merely because a record matches a search or queue. Selecting a queue enables both asset groups; explicit layer choices remain available independently of GIS/transit layers.

The map is read-only. It does not rank parks, recommend destinations, calculate routes or claim an overall quality, safety or accessibility score.

## Product files and architecture

```text
Run_MAPC_Tool.bat        Windows launcher
Run_MAPC_Tool.command    macOS Finder launcher
launch_mapc.py           Shared Python environment setup
requirements.txt        Pinned application dependencies
requirements-dev.txt    Additional maintenance/test dependencies
config/                 Schema, aliases, taxonomy, GIS codes and settings
input/assets/           Exactly one current full Airtable CSV
input/gis/              Supplied MAPC geometry ZIPs
input/gis_reference/    Original GIS attribute references
reference/              Field guides, prior audits and GIS metadata
src/                    Processing, map UI and vendored Leaflet
tests/                  Development-time regression tests
notes/                  Methodology and maintenance handoff
cache/transit/          Verified official GTFS feed and provenance
cache/runtime/          Small internal setup/processing logs
output/
  maps/
    MAPC_access_map.html
```

Both launchers resolve their own folder and call `launch_mapc.py`. It finds or creates the project environment, verifies installed dependency versions and installs missing requirements. It then invokes the same `src.pipeline` entry point on both systems.

The pipeline parses and reconciles the current CSV, calculates GIS and transit proximity, aggregates sites, derives management records, and passes those results directly to the map generator in memory. `src.make_map` embeds the inventory, management model, GIS/transit display geometry, styles and Leaflet resources into one HTML file. A temporary file is replaced atomically so an interrupted generation does not replace the previous map with partially written HTML.

After generation, `src.serve_map` binds a server to **127.0.0.1** on an available port and opens the default browser automatically. Only the map directory is served. The server stays running until stopped; no additional command is required. The inventory is not uploaded to a map-hosting service.

The only visible generated product is `output/maps/MAPC_access_map.html`. Intermediate dataframes, audit evidence, site summaries and display GeoJSON stay in memory. Runtime logs in `cache/runtime/` support troubleshooting. The reusable `cache/transit/` feed and its checksum metadata supply the actual transit evidence. Tests are repository maintenance code, not an alternate product mode or part of staff launches.

## Analytical definitions

### Accepted records, source identity and validation

Every parsed source record retains its filename/checksum, CSV record number, physical source line range, raw values and source-row identifier. Blank or malformed records and conflicting duplicate identities are quarantined in memory and excluded from accepted management records. Exact duplicates contribute one accepted record. The source CSV remains the complete original record of excluded rows.

Source asset/site IDs are preserved when supplied. Fallback asset IDs hash normalized site, asset name and municipality; fallback site IDs hash normalized site name. These are deterministic fallback identities, not official MAPC IDs. Renames can change them, and unrelated same-name sites can collide. Cross-town sites intentionally retain one site identity.

The current export contains checked and blank checkbox values only: checked means complete; blank means not confirmed complete. For other compatible exports, explicit checked/true/yes/finished values mean field validated. Explicit unchecked/false/no values mean unfinished; blanks and unrecognized values remain Unknown. Staff review is independent of field completion. All accepted records contribute to the management view and site progress, including unfinished records.

### Coordinates, attributes and activities

Coordinate parsing supports combined or separate fields and finite global geographic ranges. Missing, malformed and impossible coordinates receive no invented position. Valid locations outside the expected study area remain mapped with a review warning. `coordinates.study_area_bounds` is an explicit advisory rectangle; change it for another region or set it to `null`. Reversal repair requires a globally impossible supplied order with a valid reversed order, or a reversed pair uniquely inside that explicit rectangle. Without either signal, the supplied order is retained. Raw source coordinates are preserved.

`attribute_count` counts every recorded structured MAPC tag. `amenity_count` counts the physical facility/equipment subset identified by `config/attribute_taxonomy.yaml`; two tags can describe the same facility. Activities come from the current source rather than a fixed vocabulary. New labels are preserved. Marker size defaults to `accessibility_feature_count`, with bins **0, 1, 2, 3–4, 5+** and radii **5, 8, 12, 17, 23 CSS pixels**. It counts distinct Attributes tags classified `accessibility` in the taxonomy: Accessible / Adaptive Device Trail; Accessible Parking; Accessible Restroom; Adaptive Trails (Mt Biking / XC Skiing); Adaptive Water Access (Boating/Fishing/Beach); Sensory Guide Features; Wheelchair / Stroller Friendly Trail. General characteristics, activities, cost/pet policies and general amenity tags do not enlarge this default size. The optional all-attributes view uses **0–2, 3–5, 6–8, 9–11, 12+** bins. Counts come from recorded tags, not inferred facilities or a quality score; a low count can indicate incomplete documentation. Both counts are retained regardless of the selected view.

### Access evidence and transportation profile

Access fields retain **YES / NO / UNKNOWN**, the tag-derived original value, assessed value, verification status, evidence and source separately. The drawer labels the source as **Recorded Attributes tag: Present / Not recorded**. These are derived from the Attributes cell, not a separate Airtable Yes/No field. An absent tag is Unknown, never an explicit No. Narrow explicit narrative evidence from field-validated records can resolve missing information; contradictions remain flagged. Previous audits are matched cautiously and never transfer their old values automatically. Designated accessible parking presence is separate from access-aisle conditions: a missing aisle alone does not negate the spaces, and the aisle observation remains visible without a compliance claim. Explicit restroom statements about another location are excluded from this asset’s assessment; local contradictions still require review.

The source's **Free Entry / Parking** tag combines admission and designated parking being fully free. It is not a separately surveyed generic parking field. Transit plus that combined field gives the transportation colors: blue for both, amber for transit only, magenta for free entry / parking only, charcoal for neither, and gray for unknown/unresolved.

Site attribute/amenity/activity lists are unions. Site access is YES if any accepted member is YES, NO only when all accepted members are explicitly NO, and UNKNOWN otherwise. Field and staff completion each require every accepted member to be explicitly complete. Coverage percentages describe inventory workflow rather than place quality.

### Geographic evidence coverage

Mapping a valid inventory location does not establish GIS or transit coverage there. `gis.coverage_bounds` and `transit.coverage_bounds` separately define where the supplied datasets may support calculations. The current Massachusetts rectangles preserve existing calculations; they are not municipal boundaries or proof of comprehensive coverage. Outside the relevant rectangle, distances and proximity flags stay UNKNOWN with an explicit reason. `null` means no established coverage, so calculations remain UNKNOWN. To use other regional GIS inputs, supply verified compatible layers, set the evidence bounds to their supported area and choose an appropriate projected metre `gis.analysis_crs`. Merely widening the inventory study area does not extend MBTA or MAPC evidence coverage. The built-in transit provider is still MBTA; other providers require an additional feed integration.

### GIS proximity

MAPC geometry comes from the supplied ZIPs, whose SHP, SHX, DBF and PRJ members are verified. The tool reads the declared CRS and transforms full line geometry to the configured projected metre CRS, **EPSG:26986** for this study. Nearest distances use actual complete lines and a spatial index, not centroids or degree distances.

Only verified Existing infrastructure with eligible geometry and known required type enters proximity calculations. Walking trails additionally require explicit public access. Planned, private, closed, lost and unknown features remain in the source packages and are excluded as appropriate. LandLine is contextual and is not an additional access mode. Display lines use topology-preserving simplification in projected metres before WGS84 conversion; display geometry never feeds distance calculations.

### Transit proximity and cache

**Near public transit = an eligible served MBTA stop or station within exactly 0.5 mile**, including the boundary. Distances are unrounded EPSG:26986 point-to-point distances before classification. This is radial proximity, not a walking route, entrance-accessibility check or service-frequency guarantee.

The official source is `https://cdn.mbta.com/MBTA_GTFS.zip`. The cache keeps the exact feed ZIP, SHA-256, retrieval details and feed validity metadata. Normal runs reuse a verified cached feed. Maintainers can deliberately refresh with `transit.refresh_gtfs` or pin a feed with `transit.snapshot_sha256` in `config/config.yaml`; a feed update changes the evidence. Preserve `cache/transit/` when moving the complete project.

Scheduled boarding stops and their parent stations are eligible across the feed's validity period. Modes include represented bus, rapid transit, light rail, Silver Line, commuter rail and ferry service. The drawer shows **Calculated MBTA proximity** separately from the recorded tag. The broader all-mode calculation is not labeled a correction to MAPC’s tagging policy. Whether the intended MAPC tag is rail-only remains a policy question; the existing all-mode calculation has been preserved pending that decision. If official data is unavailable or the location is outside evidence coverage, calculated transit remains UNKNOWN and recorded MAPC evidence is preserved. The transportation profile continues to use calculated proximity where known and retained recorded evidence otherwise. An unavailable feed is not a calculated NO.

### Management rules and optional historical evidence

Queues identify incomplete field collection, pending staff review, missing coordinates, explicit unresolved access conflicts, current-source warnings and verified historical changes when available. Unknown access evidence alone is not an unresolved conflict. Two or more categories produce the multiple-issues display; all reasons remain visible. No known issues means none of these record-level categories applies.

An optional `paths.previous_asset_file` reference can identify a distinct historical export outside `input/assets/`. Both inputs are checksummed and compared in memory before current transit reconciliation. It does not introduce a second current CSV or copy historical values into current records. With no previous export configured, change review is disabled. Full rules and limits are in [management rules](notes/management_rules.md), [asset methodology](notes/assets_methodology.md) and [GIS/transit methodology](notes/gis_transit_methodology.md).

The supplied inventory has **211 accepted assets at 131 sites**, with **171 mapped assets**, **40 accepted records without usable coordinates**, **101 field-validated records** and **27 staff-reviewed records**. These are observed source counts, not constants or acceptance targets for future exports.

## Local data and online streets

Inventory, details, management queues and local GIS/transit display data are embedded in the HTML. They remain usable without online map tiles. Street labels and online streets need internet access. The default provider is OpenStreetMap Standard, with linked attribution; use must comply with its [tile policy](https://operations.osmfoundation.org/policies/tiles/) and [copyright/license](https://www.openstreetmap.org/copyright). The tool does not download an offline tile archive. Tile failure triggers a local-data fallback.

The localhost workflow supplies normal browser HTTP behavior for online tiles. The server is local-only; the street provider receives ordinary tile requests, not an uploaded inventory dataset. Leaflet is vendored with its license. Fractional raster zoom defaults to 0.25 steps and does not imply continuous vector detail.

## Development and maintenance

Runtime dependencies are pinned in `requirements.txt`: pandas/numpy for tabular calculations, GeoPandas/pyogrio/Shapely/pyproj for geometry, PyYAML for configuration, requests for official GTFS acquisition, and openpyxl for reading existing audit reference workbooks. The application does not generate workbooks. `requirements-dev.txt` adds pytest and Playwright for maintenance testing; staff launchers do not install or run those tests.

Developers can use the project environment to install the additional test dependencies and run focused tests:

```text
python -m pip install -r requirements-dev.txt
python -m pytest -q tests/test_pipeline.py tests/test_launcher.py tests/test_map.py tests/test_map_management.py
python -m pytest -q tests/test_map_ui.py
```

Browser tests need a supported local browser or a Playwright browser installation. They use synthetic fixtures unless explicitly validating the generated map. Keep test artifacts out of `output/`; the normal launcher never runs tests or creates test reports/screenshots. See [current validation scope](notes/map_validation.md) and [handoff](notes/MAP_HANDOFF.md) for checks actually performed and platform limitations.

Additional tests cover schema changes, malformed rows, coordinate repairs, three-state access, site aggregation, GIS eligibility, full-line distances, GTFS eligibility/cache integrity and the exact half-mile boundary. Update those tests alongside any intentional methodology change. Do not change analytical meanings simply to alter a display.

## Troubleshooting

| Message or symptom | Action |
| --- | --- |
| Python missing or too old | Install Python 3.12+; keep the Python launcher available on Windows or `python3` on macOS. |
| No CSV or multiple CSVs | Keep exactly one full current Airtable export in `input/assets/`. |
| Required columns missing | Export the full inventory; ask a maintainer to review schema/aliases if Airtable headers changed. |
| Package setup failed | Check internet access and folder write permission. Internal details are in `cache/runtime/setup.log`. |
| Processing failed | Check the concise launcher message and required project inputs. A maintainer can inspect `cache/runtime/last_run.log`. |
| Browser did not open | Set a default browser in the computer's settings and launch again. |
| No asset circles after filtering | Select All inventory records and clear search; also check asset layers. Missing-coordinate records intentionally have no markers. |
| Street tiles unavailable | Embedded inventory and local layers remain available. Restore internet access for street labels. |
| Transit calculation unavailable | Restore a verified transit cache or network access; UNKNOWN does not mean no nearby service. |
| Project moved to a new computer | Bring the required data/cache folders and allow the launcher to create a new local environment. |
