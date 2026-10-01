# GIS and transit methodology

## Source hierarchy and reproducibility

Geometry comes exclusively from the four immutable local MAPC Shapefile ZIPs under `input/gis/`. The parser reads ZIP members directly through GDAL/pyogrio and checks for a single `.shp` plus its `.shx`, `.dbf`, and `.prj` companions. The original ZIP, attributes, and every feature remain preserved. A missing CRS is an error; the parser never assigns a presumed CRS.

The supplied packages each declare **EPSG:26986, NAD83 / Massachusetts Mainland**, confirmed from their actual projection metadata. Full geometry is retained in normalized in-memory GeoDataFrames in the configured projected metre CRS (default EPSG:26986). Display geometry is transformed to EPSG:4326 and embedded in the final HTML. WGS84 asset and transit coordinates are transformed by GeoPandas/PROJ. Distances are planar Euclidean distances suitable for regional proximity screening, subject to positional and datum accuracy; they are not surveyed measurements. No separate normalized GeoPackage or display GeoJSON files are generated.

Official metadata was researched and cached under `reference/gis_metadata/`, with URL, retrieval time, and SHA-256 recorded in `config/mapc_gis_codes.yaml`. Ordinary runs use this versioned configuration and never contact MAPC servers. The metadata sources are:

* [Bicycle facility domains: MAPC MapcTrails MapServer, layer 0](https://geo.mapc.org/server/rest/services/MapcTrails/MapServer/0?f=pjson)
* [Shared-use path domains: MAPC AllTrails FeatureServer, layer 8](https://geo.mapc.org/server/rest/services/Transportation/AllTrails/FeatureServer/8?f=pjson)
* [Walking-trail domains: MAPC AllTrails FeatureServer, layer 4](https://geo.mapc.org/server/rest/services/Transportation/AllTrails/FeatureServer/4?f=pjson)
* [LandLine domains: MAPC landlines FeatureServer, layer 0](https://geo.mapc.org/server/rest/services/transportation/landlines/FeatureServer/0?f=pjson)

The AllTrails bicycle FeatureServer omitted coded domains. The separate official MapcTrails MapServer publishes them; its response is the evidence used for bicycle decoding. Other layers' mappings were never substituted for the bicycle facility-type domain. The metadata acquisition utility in `notes/acquire_gis_metadata.py` is an explicit maintainer operation and is not called by the pipeline. Any refreshed mappings should be reviewed and versioned before a new analysis.

## Decoding and current infrastructure

All four official facility-status domains explicitly map 1 to Existing, 2 to Under Construction / In Design, and 3 to Envisioned / Planned. Only Existing features with valid, nonempty line geometry and known required facility type enter current proximity and web layers. Unknown status or required type is excluded from those layers and retained with an explanation. Unknown optional details, surface, and regional designations remain Unknown without disqualifying an otherwise known existing facility.

Walking `acc_status` is a free-text field in the authoritative schema, with Public as its template default. The pipeline does not use that default to fill blanks. It trims and normalizes case, allows explicitly recorded Public, and excludes Private, Closed, Lost, blank, and unrecognized access values. `gis.walking_public_access` defaults to `[Public]`. This field concerns public access and does **not** certify wheelchair access. The exact recorded value is always retained.

LandLine segment types explicitly named Gap are excluded even when their facility status says Existing. A mapped network gap is not a constructed facility. Unknown LandLine segment types are also excluded from the current layer. LandLine is a regional planning/reference network and is not used to compute bicycle or walking nearest distances.

`analysis_include`, `geometry_status`, `decoded_*`, and semicolon-separated `exclusion_reason` fields document these decisions in memory. The normalized layers retain every source feature, including missing geometry and excluded proposals; original packages remain unchanged on disk. `source_file`, `source_sha256`, and `source_feature_key` link each row to its source package and source global ID/object ID. Original shapefile field names, including GDAL's existing ten-character truncations, are retained rather than silently matched to unrelated fields.

The initial supplied-source counts after verified decoding are:

| Layer | Source features | Current eligible | Excluded from access/display |
|---|---:|---:|---:|
| Bicycle facilities | 16,212 | 9,707 | 6,505 |
| Shared-use paths | 6,402 | 4,665 | 1,737 |
| Walking trails | 54,715 | 54,089 | 626 |
| LandLine systems | 6,420 | 2,723 | 3,697 |

These are observed supplied-source counts, not processing constants. Processing recalculates counts and diagnostics in memory on each run. Exclusion categories overlap: for example, a proposed trail can also be private. Do not sum overlapping reason counts as though mutually exclusive.

## Analysis geometry and display geometry

Nearest distances use complete, unsimplified geometry through a Shapely STRtree spatial index. They measure a point's distance to the actual line, not its midpoint, vertices, or centroid. Equal-distance matches are broken deterministically by source feature order. Distances in metres are converted using exactly 0.3048 metres per foot and 1609.344 metres per statute mile.

The `nearest_bike_facility_*`, `nearest_shared_use_path_*`, and `nearest_walking_trail_*` fields give the selected source feature, name, and feet/miles distances; bike type is also recorded. Baseline flags use `<= 0.25` and `<= 0.5` mile before any display rounding. `gis.proximity_thresholds_miles` may add threshold flags. `near_existing_bike` and `near_shared_use_path` use `gis.proximity_radius_miles`, default 0.5 mile. All proximity flags are YES, NO, or UNKNOWN.

Only accepted asset records with usable coordinates receive distances. The parser's explicit `coordinate_usable` flag governs repaired reversed coordinates and accepted outside-study-area exceptions. Quarantined records remain in the dataset but do not receive spatial measurements. Missing/invalid coordinates, absent networks, or networks with zero eligible features produce null distances and UNKNOWN flags.

Display GeoJSON is built in memory and embedded in the HTML. Douglas-Peucker simplification runs in projected metres with `preserve_topology=True`, controlled by `gis.web_simplification_tolerance_m` (initial setting: 5 metres), followed by transformation to WGS84. No clipping occurs in this display preparation step. Feature and vertex counts before and after simplification are retained in the in-memory diagnostics. Display geometry never feeds the distance calculations. Planned features remain in the authoritative packages and normalized in-memory layers, but not the eligible display data.

Proximity does not establish a legal entrance connection, safe crossing, continuous bicycle route, pedestrian route, or wheelchair-accessible route. A nearer line across a river, fence, or highway can still be the nearest geometric feature.

## Official transit acquisition

The official source is [MBTA's published GTFS ZIP](https://cdn.mbta.com/MBTA_GTFS.zip), confirmed by [MBTA's maintained GTFS documentation](https://github.com/mbta/gtfs-documentation/blob/master/reference/gtfs.md). Downloads require an authoritative HTTPS MBTA/MassDOT host, and redirected hosts are checked. The ZIP must contain stops, routes, trips, and stop_times tables.

Snapshots are stored as `cache/transit/<full-sha256>.zip`, with a matching immutable JSON provenance sidecar and an `active_snapshot.json` pointer. Files are never overwritten with a different feed under the same name. The pipeline rehashes a cached snapshot before use. Provenance includes the feed's URL, retrieval timestamp, file size, checksum, response metadata, feed version, and validity dates; it accompanies the in-memory transit result and embedded map metadata. The initial cached feed is 24,684,859 bytes, SHA-256 `da552d2330c9b85c2ad7ddb5d71012bb9539b2ba5b822d7000d7a3606ec79296`, MBTA Fall 2026 version D, covering September 22 through December 12, 2026.

Normal runs reuse the verified cached snapshot. Setting `transit.refresh_gtfs` in configuration explicitly refreshes it; if refresh fails, the verified cache may be reused when allowed. Setting `transit.snapshot_sha256` pins a historical snapshot. A missing pinned version produces unavailable transit rather than substituting a newer feed. Preserve the cache for reproducibility; metadata alone cannot reconstruct a ZIP removed from disk. Expired validity periods are flagged for review, without silently changing historical inputs.

The pipeline continues building the management map if transit download or parsing fails. Transit measurements are null, the calculated classification is UNKNOWN, `transit_calculation_status` states the limitation, and original MAPC evidence is preserved. Internal diagnostics distinguish absence of official data from an ordinary calculated NO.

## Transit stop eligibility and half-mile calculation

Routes are joined to trips, then chunked stop_times records establish which boarding stops occur on a scheduled route. Eligible records are served `location_type=0` stops (blank also means 0) and their `location_type=1` parent stations. Unserved stops and entrance-only locations are excluded. Stop coordinates must pass numeric/global-range validation. The initial feed yields 7,877 eligible stops/stations and 1,163 route shapes.

The calculation covers scheduled service anywhere in the cached feed's validity period. It does not filter by a particular day, departure time, headway, direction, service frequency, or disruption. Seasonal/limited service may therefore qualify. Parent-station points are included because the user definition permits a stop **or station**; they are not assumed to be accessible entrances.

Modes derive from the official route type: bus, rapid transit, light rail, commuter rail, ferry, and trolleybus where present. Silver Line routes are identified by official route short names beginning SL or long names containing Silver Line. Multi-route stations retain all linked mode and route labels. Shapes are taken from official GTFS shapes/trips for map display; simplified display route lines are not used in stop-distance classification.

Distances are indexed Euclidean point-to-point distances in EPSG:26986, converted to miles. **Near public transit is YES if and only if the unrounded distance is less than or equal to exactly 0.5 mile.** A configuration value other than 0.5 is rejected. This is straight-line proximity, not a walkable or accessible route length.

Derived fields are `nearest_transit_stop`, `nearest_transit_stop_id`, `nearest_transit_mode`, `nearest_transit_route_if_practical`, `nearest_transit_distance_miles`, `near_public_transit_calculated`, `transit_calculation_status`, and `transit_snapshot_sha256`. `transit_comparison_status` records agreement, disagreement, or not_comparable against the original MAPC three-state value. UNKNOWN is not treated as NO; only opposite explicit YES/NO pairs count as discrepancies. The spatial module does not overwrite recorded values. Final evidence reconciliation is an explicit downstream step that preserves the original value and adds final value, verification status, evidence and source for the HTML details. No standalone discrepancy table is written.

## Verification

Automated tests exercise direct ZIP loading, observed CRS detection, missing CRS rejection, verified domain mapping, unknown-code handling, planned/private/closed/lost exclusions, retention of full geometry, network gaps, true point-to-line distance, deterministic ties, rejection of degree-based distances, empty-network behavior, coordinate repairs/quarantine, exact half-mile boundaries, stop/parent eligibility, modal classification, feed failure, source-value preservation, checksum tampering, and historical snapshot pinning. Tests use small synthetic fixtures and do not require a live internet connection.
