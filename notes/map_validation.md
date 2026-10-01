# Final product validation — 2026-10-01

The product is the interactive HTML map and its shared Windows/macOS launch workflow. Development checks do not run during staff launches. No chart, workbook, static-map or release generator was run for this task.

## Checks actually run

| Check | Result |
| --- | --- |
| Core map, pipeline, management, GIS, transit and parser tests during the refactor | 54 passed in 1.27 s |
| Retained parser/coordinate/access/site/GIS/spatial/schema/version tests after dependency cleanup | 59 passed in 0.83 s; overlaps the core selection |
| Shared launcher, dependency setup, friendly errors, real localhost HTTP and macOS shell stub tests | 7 passed in 0.91 s |
| Final renderer/product-entrypoint tests after dead-code removal and friendly-warning changes | 13 passed in 1.93 s |
| Final focused UI tests in Windows Edge | 16 passed in 17.41 s |
| Fresh real Windows BAT product launch with the current CSV | Passed; parsing through browser/server completed |
| Fresh generated-map browser QA in visible Windows Edge | 10 check groups passed; zero JavaScript errors |
| Source/record/site/marker parity check against the preserved pre-refactor map | Passed, no record/site field differences |
| Dependency integrity | pip check: no broken requirements |
| macOS launcher | POSIX syntax and shared-entry stub passed on Windows; Git executable mode 100755 |

These are separate targeted test selections, not an additive count of unique tests. The restricted Windows environment initially blocked some pytest temporary folders/browser pipes; reruns with normal Windows access passed. The new full-data browser helper initially returned circular Leaflet objects and compared a heading without accounting for CSS uppercase. Those test-harness defects were corrected; the final complete browser pass passed.

The accidental hover reopening case was reproduced by a failing real-pointer regression before the fix. It now verifies card-to-underlying-marker exit, intra-marker movement, stale mouseover events, the expired crossing timer, and deliberate later hover. Long lists scroll without zooming the map; leaving the card closes it immediately. Mobile tests cover 390×844 and 360×640 with unobstructed zoom controls.

## Fresh Windows workflow

`cmd.exe /d /c .\Run_MAPC_Tool.bat` used the shared bootstrap and existing project environment. It accepted the arbitrary filename `input/assets/Assets-By subregion.csv`, recalculated the required evidence and generated the HTML in about 20 seconds. It printed both requested success messages, invoked the Windows default-browser API successfully, and entered the local server loop. The launcher-produced URL returned HTTP 200 and bytes identical to the saved current HTML. No separate server command was used.

The output tree contained exactly one file after this fresh run: `output/maps/MAPC_access_map.html` (42,628,861 bytes). No obsolete directories or partial `.tmp` map were recreated. The server uses an available loopback port, serves only the map folder, and remains running until stopped. Setup of a completely new physical machine and native macOS execution were not performed here; setup/error paths have focused tests.

## Data preservation

- 213 source rows: 211 accepted and 2 blank quarantined in memory.
- All 211 accepted records and all 131 site records match the pre-refactor embedded records field for field.
- All 171 marker identities, coordinates, validation flags, transportation colors and sizes match the baseline. All management summary counts match.
- 101 field validated, 27 staff reviewed, 40 accepted records without usable coordinates, 4 access-conflict records, 2 source-warning records, 24 records without known management issues.
- Display networks: 9,707 bicycle, 4,665 shared-use and 54,089 walking features; full-line calculations remain unchanged, including 2,723 eligible LandLine features.
- Transit: 7,877 stops and 1,163 route shapes, from the unchanged official feed SHA-256 `da552d2330c9b85c2ad7ddb5d71012bb9539b2ba5b822d7000d7a3606ec79296`.
- All 26 protected input/reference/feed files retained their SHA-256 hashes. The fresh launch reused the verified cached feed.

## Browser and visual review

The ten browser groups cover embedded counts; passive metric/removed controls; online streets; every queue and search; source/audited details and coincident selection; both views and every asset/GIS/transit layer; hover lifecycle; unchanged document/data without refresh; mobile/offline operation; and JavaScript errors.

The missing-coordinate queue retained 40 list records and zero asset circles. Selecting All inventory records restored all 171 mapped records; clearing search restored the active queue. Visible markers kept their normal color/size/outline/fill styling. The normal unfinished-record fill style remains a validation encoding, never a filter-mismatch encoding.

Online Edge loaded 24 street tiles with zero errors and no fallback in the recorded initial view. The same generated HTML passed a network-blocked standalone-file check. Seven screenshots were reviewed: management, missing-coordinate queue, evidence drawer, transportation, scrolled hover, expanded mobile panel, and offline mobile details. Layouts remained usable, controls were present, and mobile zoom buttons were clear.

Task-only evidence is under ignored `cache/validation/` (parity/source-preservation/cleanup JSON and seven browser screenshots/results). These files were created by maintenance validation, not by the product launcher, and are not required to run the tool. Disposable test fixtures and baseline copies were removed after validation.

## Remaining limits

Native macOS/Finder execution is unvalidated on this Windows host. A new computer needs Python 3.12+, a default browser and the institutional data bundle; the launcher installs Python packages. Initial package installation needs internet. Online street tiles need internet, while embedded inventory/layers work offline. Missing coordinates, source warning cells, unresolved evidence and fallback identifier limitations remain source review items, not software failures.
