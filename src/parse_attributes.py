"""Lossless vocabulary discovery and explicitly configured amenity taxonomy."""
from __future__ import annotations

from collections import Counter
import csv
import json
from pathlib import Path
import re
import unicodedata
import pandas as pd
import yaml


def clean_token(value):
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", str(value))).strip()


def parse_multivalue(raw):
    """Recognize JSON lists or CSV/semicolon/newline lists; retain source wording."""
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return []
    if isinstance(raw, (list, tuple, set)):
        values = list(raw)
    else:
        text = str(raw).strip()
        if not text:
            return []
        if text.startswith("["):
            try:
                decoded = json.loads(text)
                values = decoded if isinstance(decoded, list) else [text]
            except (ValueError, TypeError):
                values = [item for row in csv.reader([re.sub(r"[;\r\n]+", ",", text)]) for item in row]
        else:
            values = [item for row in csv.reader([re.sub(r"[;\r\n]+", ",", text)]) for item in row]
    # Formatting-only duplicates collapse; first spelling retained and output sorted.
    unique = {}
    for value in values:
        token = clean_token(value)
        if token:
            unique.setdefault(token.casefold(), token)
    return sorted(unique.values(), key=lambda value: (value.casefold(), value))


def load_taxonomy(root=None, config=None):
    root = Path(root or Path(__file__).resolve().parents[1])
    path = (config or {}).get("paths", {}).get("attribute_taxonomy", "config/attribute_taxonomy.yaml")
    with (root / path).open(encoding="utf-8") as stream:
        return yaml.safe_load(stream)


def classify_attribute(attribute, taxonomy):
    entries = {clean_token(key).casefold(): value for key, value in taxonomy.get("attributes", {}).items()}
    return entries.get(clean_token(attribute).casefold(), taxonomy.get("default", {
        "classification": "other", "is_amenity": False, "notes": "Unmapped attribute; review required."}))


def parse_attributes(raw, taxonomy=None):
    attributes = parse_multivalue(raw)
    taxonomy = taxonomy or load_taxonomy()
    amenities = [attribute for attribute in attributes if classify_attribute(attribute, taxonomy).get("is_amenity", False)]
    return {"attribute_list": attributes, "attribute_count": len(attributes),
            "amenity_list": amenities, "amenity_count": len(amenities)}


def build_attribute_dictionary(df, config=None, root=None):
    taxonomy = load_taxonomy(root, config)
    subset = df[df["record_status"].eq("accepted")] if "record_status" in df else df
    counts = Counter(value for values in subset["attribute_list"] for value in values)
    rows = []
    for attribute in sorted(counts, key=str.casefold):
        classification = classify_attribute(attribute, taxonomy)
        rows.append({"attribute": attribute, "frequency": counts[attribute],
                     "classification": classification["classification"],
                     "is_amenity": classification.get("is_amenity", False),
                     "notes": classification.get("notes", "")})
    return pd.DataFrame(rows, columns=["attribute", "frequency", "classification", "is_amenity", "notes"])


def build_amenity_dictionary(df, config=None, root=None):
    dictionary = build_attribute_dictionary(df, config, root)
    return dictionary[dictionary["is_amenity"].eq(True)].reset_index(drop=True)
