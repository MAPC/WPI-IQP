# Project organization

Updated 2026-10-01 for the single management-map product. The active workspace is `C:\Users\Jaeyun\Desktop\MAPC Ultimate Deliverables`.

## Staff-facing workflow

Staff replace the sole current CSV in `input/assets/`, then double-click `Run_MAPC_Tool.bat` on Windows or `Run_MAPC_Tool.command` in macOS Finder. The export can have any filename. Both launchers call the same `launch_mapc.py` setup entry point and `src.pipeline` product workflow.

The shared setup requires Python 3.12+, creates or reuses `.venv`, checks pinned installed package versions and installs missing application dependencies. The pipeline calculates the current inventory in memory, writes `output/maps/MAPC_access_map.html`, starts a loopback-only server on an available port, and opens the default browser. The launcher window stays open until the server is stopped. Normal use requires no separate environment activation or server command.

Tests remain source code for maintainers. They are not a product mode and are not run during staff launches. Additional test dependencies are in `requirements-dev.txt`; launchers use `requirements.txt` only. No executable/application packaging is required.

## Required local inputs

| Source group | Supplied files | Location |
| --- | ---: | --- |
| Current full asset export | 1 | `input/assets/` |
| Zipped GIS geometry | 4 | `input/gis/` |
| GIS attribute references | 4 | `input/gis_reference/` |
| Data-collection guides | 2 | `reference/field_guides/` |
| Prior audit references | 2 | `reference/previous_audits/` |
| Verified GIS code metadata | Versioned reference set | `reference/gis_metadata/` and `config/mapc_gis_codes.yaml` |
| Official transit feed and provenance | Reusable cached feed | `cache/transit/` |

The raw/reference material and caches are ignored by Git. Provide the complete institutional data bundle alongside a fresh source clone; do not assume a clone includes those inputs. Preserve source filenames and bytes. A previous asset export, when explicitly configured for comparison, belongs outside the current `input/assets/` directory.

## Generated product and internal files

The staff-facing generated tree is:

```text
output/
  maps/
    MAPC_access_map.html
```

Required asset, site, access-evidence, spatial and management calculations are passed in memory. The HTML includes its local inventory, GIS/transit display data and vendored Leaflet resources. It does not depend on separately generated tables or layer files.

`cache/transit/` retains the exact official GTFS ZIP and checksum/provenance metadata so future launches can reproduce the same transit evidence. `cache/runtime/` contains small internal setup/processing logs for actionable errors. Source archives under `cache/input_versions/`, if present, are original inputs rather than disposable output. `.venv/` and Python/test caches are machine-local runtime files.

Obsolete chart, workbook, static-map, generated-documentation, standalone-table/report and release-archive outputs do not belong in the normal product tree. Dependency checks must precede removal of a legacy generator; computation still needed by the HTML is retained. The final cleanup inventory and validation evidence are maintained in `notes/WORK_PROGRESS.md` and `notes/MAP_HANDOFF.md`.

## Earlier verified root cleanup

Before the management-map revision, all 13 loose original root files had organized copies with identical SHA-256 hashes. Each loose file and retained copy also matched the historical `bootstrap/root_inventory.csv` checksum. Only the 13 redundant root copies were removed. No source file was rewritten, and no checksum discrepancies occurred.

`input/input_bak` was absent. Historical bootstrap evidence was not rewritten; full paths, sizes, source hashes, actions and verification results remain in `bootstrap/root_cleanup_report.csv` and `.json`. That earlier source organization is complete and does not need to be repeated for a normal product update.

## Git and platform behavior

Ignore rules keep raw/reference data, generated output, transit caches, virtual environments and disposable test files local. Folder placeholders only establish expected layout; they contain no input data. `.gitattributes` preserves LF for shell launchers. The macOS `.command` also needs an executable repository mode; maintain that when copying or distributing the project.

The Windows BAT and macOS COMMAND wrappers are deliberately thin. Environment preparation and application behavior live in shared Python code. Native macOS execution must not be inferred from shell syntax or stub testing on Windows. See `notes/map_validation.md` for the exact platforms and checks actually exercised.
