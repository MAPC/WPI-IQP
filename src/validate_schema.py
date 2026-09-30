"""Header-first, alias-aware data contract checks; never positional parsing."""
from __future__ import annotations

from collections import Counter
from pathlib import Path
import re
import unicodedata
import yaml


def normalize_header(value: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", str(value)).strip()).casefold()


def load_contract(root: Path):
    root = Path(root)
    with (root / "config/schema.yaml").open(encoding="utf-8") as stream:
        schema = yaml.safe_load(stream)
    with (root / "config/column_aliases.yaml").open(encoding="utf-8") as stream:
        aliases = yaml.safe_load(stream)
    return schema, aliases


class SchemaValidationError(ValueError):
    def __init__(self, message: str, report: dict):
        self.report = report
        super().__init__(message)


def validate_schema(headers, schema=None, aliases=None, root=None, previous_headers=None):
    """Return a serializable report, raising with that report for critical changes."""
    if schema is None or aliases is None:
        loaded_schema, loaded_aliases = load_contract(Path(root or Path(__file__).resolve().parents[1]))
        schema = schema or loaded_schema
        aliases = aliases or loaded_aliases
    headers = list(headers)
    lookup = {}
    for canonical, variants in aliases.items():
        for variant in [canonical, *variants]:
            normalized = normalize_header(variant)
            if normalized in lookup and lookup[normalized] != canonical:
                raise ValueError(f"Alias configuration conflict for {variant!r}")
            lookup[normalized] = canonical
    counts = Counter(normalize_header(header) for header in headers)
    duplicates = [name for name, count in counts.items() if count > 1]
    mappings = {header: lookup[normalize_header(header)] for header in headers if normalize_header(header) in lookup}
    canonical_counts = Counter(mappings.values())
    collisions = [name for name, count in canonical_counts.items() if count > 1]
    present = set(mappings.values())
    required = schema.get("required", [])
    missing_groups = [label for label, alternatives in schema.get("required_any", {}).items()
                      if not any(set(option) <= present for option in alternatives)]
    report = {
        "input_columns": headers,
        "required_present": [field for field in required if field in present],
        "required_missing": [field for field in required if field not in present],
        "required_alternative_groups_missing": missing_groups,
        "optional_present": [field for field in schema.get("optional", []) if field in present],
        "unexpected_columns": [header for header in headers if header not in mappings],
        "duplicate_columns": duplicates,
        "alias_collisions": collisions,
        "aliases_applied": {raw: canonical for raw, canonical in mappings.items() if raw != canonical},
        "column_mapping": mappings,
        "type_inconsistencies": [],
        "schema_changes": {"status": "no_previous_schema"},
    }
    if previous_headers is not None:
        report["schema_changes"] = {
            "status": "compared", "added_columns": sorted(set(headers) - set(previous_headers)),
            "removed_columns": sorted(set(previous_headers) - set(headers)),
        }
    errors = []
    if report["required_missing"]:
        errors.append("missing required columns: " + ", ".join(report["required_missing"]))
    if missing_groups:
        errors.append("missing coordinate columns (provide Location/Coordinates or Latitude and Longitude)")
    if duplicates:
        errors.append("duplicated column names: " + ", ".join(duplicates))
    if collisions:
        errors.append("multiple source columns map to the same canonical field: " + ", ".join(collisions))
    report["valid"] = not errors
    report["errors"] = errors
    if errors:
        raise SchemaValidationError("Asset schema validation failed: " + "; ".join(errors), report)
    return report
