# Project organization and launcher verification

Updated 2026-09-30 for the inventory-management map revision.

The active workspace is `C:\Users\Jaeyun\Desktop\MAPC Ultimate Deliverables`.
Git was clean on `main`, tracking `origin/main`, before this revision. No commit,
push, or history rewrite was performed.

## Verified source cleanup

All 13 loose original files had organized copies with identical SHA-256 hashes.
Each loose file and retained copy also matched the historical
`bootstrap/root_inventory.csv` checksum. Only the 13 redundant root copies were
removed. No source file was rewritten or overwritten; no file needed to be
moved, and there were no checksum discrepancies.

Retained authoritative locations:

| Source group | Files | Location |
| --- | ---: | --- |
| Current asset export | 1 | `input/assets/` |
| Zipped GIS geometry | 4 | `input/gis/` |
| GIS attribute references | 4 | `input/gis_reference/` |
| Data-collection guides | 2 | `reference/field_guides/` |
| Prior audit references | 2 | `reference/previous_audits/` |

`input/input_bak` was absent, so no backup folder was removed. The historical
bootstrap inventory was not changed. Full absolute paths, file sizes, source
hashes, actions, and verification results are recorded in
`bootstrap/root_cleanup_report.csv` and `.json`.

Six disposable runtime directories were removed: the root `.pytest_cache`, two
root `pytest-cache-files-*` directories, and `__pycache__` under `src`, `tests`,
and `notes`. Absolute resolved targets were checked to remain inside this
workspace before removal. `cache/transit`, `cache/rebuilds`, `cache/run_history`,
and all other reproducibility cache contents were retained. Later test execution
may recreate ignored runtime files.

## Clone layout and ignored files

The ignore rules exclude virtual environments, bytecode, pytest runtime files,
`.DS_Store`, raw/reference content, generated outputs, caches, and release
archives. Empty `.gitkeep` files make expected input, reference, cache, output,
release, and legacy folders visible in a clone. Git ignore checks verified both
that representative source/generated files remain ignored and that placeholders
can be tracked. The placeholders contain no data.
`.gitattributes` preserves LF line endings for shell scripts on every platform.

## macOS and Linux launcher

Run `sh ./run_pipeline.sh` from the project folder, or pass the full launcher
path from another folder. The launcher resolves its own project root, uses
`.venv/bin/python`, and creates that environment with `python3` when necessary.
Python 3.12 or newer is required. An alternative Python executable can be
selected with the `MAPC_PYTHON` environment variable when creating the environment.

Dependencies are installed only when the SHA-256 of `requirements.txt` differs
from the successful-install stamp in `.venv/requirements.sha256`, or when that
stamp is absent. The stamp is written only after installation succeeds.
Arguments are forwarded unchanged to `python -m src.pipeline`. Direct execution
of `src/pipeline.py` is unsupported because the package uses relative imports.

The launcher passed Bash syntax validation using Git for Windows. The isolated
`notes/launcher_smoke_test.sh` harness passed seven scenarios and 18 assertions:
environment reuse/creation, stamp-based installation, failure handling, root
resolution, arguments containing spaces, and exit-code propagation. It used fake
Python commands and saved `output/reports/launcher_test_results.json`.

One focused release-packaging unit test passed with the new launcher included in
its miniature fixture; future releases now include `run_pipeline.sh`. The real
release archive and index were left unchanged. Windows sandbox restrictions
initially blocked Bash's signal pipe and pytest's temporary directory; these
checks passed outside that sandbox. No full pipeline run, dependency
installation, or actual macOS/Linux execution was performed for this revision.
