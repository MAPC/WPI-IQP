# Work progress — transit definitions complete

Updated 2026-10-06. This checkpoint supersedes the transit-policy question in the historical interpretation checkpoint below. Version 1.2.0, completed cleanup, accessibility sizing, evidence fixes and the map-only launcher remain intact.

## Completed transit implementation

- The user explicitly selected subway / rapid transit and light rail only for **T / rail**, excluding commuter rail. Eligible GTFS route types are 0 and 1; served parent stations inherit those qualifying routes.
- **All MBTA modes** remains the default and retains the existing served-stop eligibility. The current snapshot represents Bus, Silver Line, Rapid transit, Light rail, Commuter rail and Ferry; trolleybus remains eligible if present. Other providers are not added.
- Both nearest-stop calculations and transportation profiles are embedded in the single HTML. The selector immediately updates transportation colors, legend, hover, calculated evidence and spatial details. Management colors, source tags, queue/search, size selection, GIS layers, selected record and the existing page/map are preserved.
- Both definitions retain the same projected-distance method, inclusive 0.5-mile threshold, cached feed and coverage rules. Missing coordinates or unavailable/out-of-coverage evidence stay UNKNOWN. The selected profile uses calculated transit with unchanged assessed free entry / parking, without substituting the recorded transit tag.

## Current counts and preservation

211 accepted records, 171 mapped and 40 without usable coordinates remain unchanged. T / rail: **35 YES, 136 NO, 40 UNKNOWN**. All MBTA: **96 YES, 75 NO, 40 UNKNOWN**. There are 61 differing transit results and 38 differing transportation profiles.

Compared with the saved pre-generation HTML, accepted identities, original transit tag values, existing all-mode results and nearest distances, feed checksum, coordinates, attribute lists, parking values, accessibility counts and management statuses are unchanged. The source CSV checksum also matches. No external feed refresh was performed; both definitions use cached GTFS SHA-256 `da552d2330c9b85c2ad7ddb5d71012bb9539b2ba5b822d7000d7a3606ec79296`.

## Changed files and validation

- Implementation: `src/transit_data.py`, `src/transit_analysis.py`, `src/map_ui.html`.
- Tests: `tests/test_transit_definitions.py` (new), `tests/test_map_ui.py`.
- Documentation: `README.md`, `notes/INTERPRETATION_REVIEW.md`, this progress note and `notes/MAP_HANDOFF.md`.
- Product regenerated once through the real Windows `Run_MAPC_Tool.bat`: `output/maps/MAPC_access_map.html`. The launcher completed generation, invoked the default browser and served the exact generated HTML. No historical report/workbook/release workflow ran.
- Targeted pytest selection: transit parsing/cache and new definition cases; half-mile boundary; transit reconciliation and HTML-only product tests; selector preservation in both color modes; recorded/calculated labels; mobile zoom controls. Initial selection had 29 passing tests and two new browser cases failing because the test fixture redeclared the global DATA on the same page. The fixture now opens a fresh document before loading its alternate content; the two failed cases passed on rerun. **31 unique focused tests passed across these runs.** No full repository audit was rerun.
- Real generated-map browser pass: four focused groups passed, **zero JavaScript errors**. Both transit views and their colors/details restore correctly; filters, size, management colors and layers persist without refresh. Mobile selector and zoom controls pass. Online tiles: 28 loaded, zero errors.
- All five final screenshots were visually reviewed: both full-map definitions, both details states and mobile. No additional visual correction was needed.
- Internal validation evidence: `cache/validation/transit_definitions/comparison.json`, `browser_results.json`, and five screenshots. These maintenance artifacts are outside product output.

## Remaining limitations and next step

No transit-definition implementation or policy decision remains pending. Use **Calculated transit** in the expanded management panel to compare definitions. Other transit providers require additional integration; straight-line proximity is not a walking route, frequency or accessible-entrance guarantee. Native macOS and a fresh-machine dependency install were not tested in this Windows task. Output remains only the generated HTML.

---

# Historical checkpoint — interpretation fixes (before the transit selector)

Updated 2026-10-06, version 1.2.0. Implementation, targeted tests, generated-map browser QA and final repository tests are complete. This checkpoint supersedes the 2026-10-01 progress entry; the previous map-only product and cleanup were preserved.

## Completed before resumption

The shared Windows/macOS launcher, in-memory map-only pipeline, management redesign, marker-hiding filters, passive missing-coordinate metric, immediate hover dismissal, mobile zoom layout and previous browser tests were already complete. The only initial untracked file was `notes/INTERPRETATION_REVIEW.md`; no unfinished earlier implementation was discarded.

## Completed now

- Default circle size counts seven explicitly classified accessibility tag types, excluding general characteristics, activities and unrelated amenity/policy tags. An independent Circle size selector switches to all Attributes. Legend, hover and drawer counts update without refreshing or changing filters, colors, selection or source records.
- Added explicit accessibility and site-characteristic subsets in the drawer; clarified amenity tags, activities, tag absence, checkbox completion and ZIP-code-like municipality warnings.
- Designated accessible parking and access-aisle conditions are assessed separately. Original observations remain visible; no compliance determination is inferred. Missing aisles alone no longer negate designated spaces.
- Restroom evidence explicitly describing another entrance/location is excluded from the local assessment. F. Gilbert Hills OHV Parking now has assessed restrooms NO from its local narrative, with the remote-main-entrance evidence explained separately.
- Valid global coordinates outside the advisory study area remain mapped. Without an explicit expected area, ambiguous globally valid coordinate orders are not swapped. Separate GIS/transit coverage settings prevent out-of-coverage locations from receiving a false proximity NO.
- Recorded Attributes tag presence is distinct from assessed values and calculated MBTA proximity. The existing all-MBTA-mode calculation is retained; it is no longer described as a correction to the source tagging policy.

## Files/modules changed

- Map/config: `src/map_ui.html`, `src/make_map.py`, `src/config.py`, `config/config.yaml`.
- Parsing/evidence/coverage: `src/parse_attributes.py`, `src/parse_coordinates.py`, `src/geographic_coverage.py` (new), `src/parse_assets.py`, `src/reconcile_access_fields.py`, `src/spatial_analysis.py`, `src/transit_analysis.py`, `src/pipeline.py`.
- Version: `src/__init__.py`, `pyproject.toml` (1.2.0).
- Tests: `tests/test_attributes.py`, `test_coordinates.py`, `test_access_profiles.py`, `test_spatial.py`, `test_transit.py`, `test_map_ui.py`, `browser_map_qa.py`.
- Documentation: README, CHANGELOG and the interpretation, asset-methodology, GIS/transit-methodology, management-rules, progress, validation and handoff notes.
- Regenerated product: `output/maps/MAPC_access_map.html`.

## Current data and evidence

213 source rows; 211 accepted; 2 blank quarantined; 131 sites; 171 mapped; 40 without coordinates; 101 field validated; 27 staff reviewed. Access-conflict records changed from 4 to 1, records with no known management issues from 24 to 26, and sites with no known issues from 16 to 18. Two municipality warnings remain. The remaining conflict is the recorded Accessible Parking tag versus explicit absence of designated spaces at Daniel Webster Wildlife Sanctuary Parking Lot.

The corrected rules changed 15 assessed parking values and 1 assessed restroom value. Raw source fields and all tag-derived original access values are unchanged. All current coordinates, GIS/transit distances and flags, transportation profiles, identities, recorded tags and workflow fields match the saved pre-change baseline. Forty protected input/reference/feed files have unchanged SHA-256 checksums. The corrected rule applies consistently across records, including World's End and other locations describing spaces without aisles; it is not a hard-coded name override.

Existing GIS evidence was reused: full-resolution source geometry; eligible bicycle 9,707, shared-use 4,665 and walking 54,089 features. Cached MBTA evidence remains 7,877 eligible stops and 1,163 shapes, feed SHA-256 `da552d2330c9b85c2ad7ddb5d71012bb9539b2ba5b822d7000d7a3606ec79296`. No feed refresh or external acquisition was needed.

## Tests and current stage

- Focused regressions for counts, coordinates, coverage, evidence and browser UI passed. Final focused UI run: 19 passed.
- Final complete fixture-based repository suite: `python -m pytest -q --tb=short` — 151 passed in 11.82 seconds.
- Regenerated the single map once with `src.pipeline.generate_map`; no legacy reporting/workbook/release workflow ran.
- Visible Edge generated-map QA: 12 groups passed, no JavaScript errors. Online street tiles loaded; offline HTML, mobile 390x844/360x640, hidden-marker queues/search, all layers, both color/size views, hover scrolling/dismissal and new evidence cards passed.
- All 10 screenshots reviewed. Text, counts, active sizing legends, parking/restroom explanations and mobile zoom controls are readable and unobstructed.
- Internal evidence: `cache/validation/interpretation/browser/results.json`, its 10 screenshots, and `cache/validation/interpretation/preservation.json`.
- Generated HTML: 42,804,139 bytes; no partial map file remains. Only the single map product is in output.

Initial restricted-environment test attempts were blocked by Windows temporary-directory/browser permissions; normal-access runs passed. A test-file encoding problem and two new test expectations (search case and CSS-uppercase labels) were corrected before the final pass. No unresolved product test failure remains.

## Open decisions and limitations

- Transit policy: the user was asked whether the calculated measure should remain all MBTA modes or become rail-only. No answer was received during implementation. Existing all-mode behavior is preserved and clearly labeled separately from recorded tags. This policy choice is still pending; no assumption that the MAPC source tag has identical scope is made.
- Mapping supports locations outside the original area, but supplied GIS and MBTA are regional evidence. Other transit providers require a feed integration; configuring wider inventory bounds alone does not establish evidence coverage. GIS coverage/metric CRS must match supplied regional data.
- Narrative matching remains conservative phrase-based logic; arbitrary descriptions can still require human review.
- Native macOS validation and a fresh physical-machine dependency install were not performed in this Windows session. Existing launcher implementation was not changed.

## Exact next step

Use the current map through the existing launcher. Resolve the outstanding transit scope choice before changing which service modes qualify; no other implementation step from the interpretation fixes remains pending. No commit, push, source overwrite, cleanup rerun or history reset was performed.
