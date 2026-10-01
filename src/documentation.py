"""Field-level data dictionary and reproducible methodology documentation."""
from __future__ import annotations

from pathlib import Path
import json
import re

import pandas as pd
import yaml


BASE = {
    "asset_id": ("Asset identifier preserved from MAPC or generated from normalized site name, asset name and municipality.", "Preserve supplied ID; otherwise SHA-256 prefix of normalized identifying strings. Identity changes after a rename require review."),
    "site_id": ("Site identifier preserved from MAPC or generated from normalized site name.", "Preserve supplied ID; otherwise hash normalized site name only so a named cross-town reservation remains one site. Same-name site collisions require review."),
    "source_record_key": ("Stable logical asset key used for comparison and tracing.", "Equals asset_id. Does not use source row position."),
    "source_row_uid": ("Snapshot-specific identifier for one exact source record.", "Hash of source checksum and source record ordinal. Changes when snapshot bytes or record position change; not a permanent asset ID."),
    "source_file": ("Project-relative path of the authoritative input CSV.", "Record selected input path without changing source bytes."),
    "source_sha256": ("SHA-256 digest of exact authoritative CSV bytes.", "Hash input before parsing."),
    "source_row_number": ("Logical CSV record number including the header as row 1.", "Source record ordinal + 1. Embedded newlines mean this can differ from physical line numbers."),
    "source_record_index": ("One-based data-record ordinal, excluding the header.", "Increment for every parsed CSV record including blank quarantined records; used only for traceability."),
    "source_line_start": ("First physical source-file line occupied by this CSV record.", "Previous CSV reader line count + 1."),
    "source_line_end": ("Last physical source-file line occupied by this CSV record.", "CSV reader line count after parsing the record; includes quoted multiline fields."),
    "source_record_json": ("Original source row mapped to exact input header strings.", "JSON serialization of the original header/value mapping before cleaning."),
    "source_cells_json": ("Original source row cells, preserving extra cells on malformed rows.", "JSON serialization of all parsed cells in source order."),
    "record_status": ("Whether a source record is eligible for downstream use.", "Accepted requires identity and well-formed columns; blank/malformed/duplicate-conflicting records are quarantined but retained."),
    "record_issue": ("Reason a retained source row was quarantined.", "Parser and duplicate checks assign machine-readable issue text; empty for accepted records."),
    "duplicate_status": ("Result of grouping accepted candidates by logical asset key.", "Unique; exact_duplicate for identical repeat content; identity_conflict for different rows sharing a logical identity. Later exact copies and all conflicting copies are quarantined."),
    "asset_identity_basis": ("How asset_id was obtained.", "source_asset_id, normalized_site_asset_municipality, or unidentified_payload_digest."),
    "site_identity_basis": ("How site_id was obtained.", "source_site_id, normalized_site_name_only, or unidentified. Site summaries retain member basis values."),
    "asset_name": ("Current MAPC asset name.", "Read by configured header alias and trim surrounding whitespace."),
    "site_name": ("Current MAPC parent-site name.", "Read by configured header alias and trim surrounding whitespace."),
    "site_name_lookup": ("Additional parent-site lookup label retained from the export.", "Preserve Name (from Site); the primary site_name field controls identity."),
    "municipality": ("Recorded municipality; site rows join the distinct member municipalities.", "Trim source text at asset level; pipe-join unique accepted member labels at site level."),
    "subregion": ("Recorded MAPC subregion; site rows join distinct member subregions.", "Trim source text at asset level; pipe-join unique accepted member labels at site level."),
    "latitude": ("Latitude in WGS84 decimal degrees, positive north.", "Parse Location or latitude/longitude fields; repair reversed pairs only when the swapped pair is inside the configured study bounds."),
    "longitude": ("Longitude in WGS84 decimal degrees, negative west.", "Parse Location or latitude/longitude fields; retain reviewed out-of-study-area numeric values but exclude from geometry by default."),
    "coordinates_raw": ("Original source coordinate text.", "Retain exact canonical source value before coordinate parsing."),
    "coordinate_status": ("Coordinate parse, repair and plausibility result.", "Global range check plus configured Massachusetts bounding rectangle; valid/reversed values may be usable, other statuses remain explicit."),
    "coordinate_issue": ("Readable coordinate exception or repair explanation.", "Empty for valid coordinates; reports parse error, range violation, reversal or study-area warning."),
    "coordinate_usable": ("Whether coordinates may enter spatial analysis and mapping.", "True for valid or permitted reversed repairs; false for missing/malformed/global-range errors and outside-study-area points unless explicitly configured."),
    "attributes_raw": ("Original structured Attributes field.", "Retain exact source field before list parsing and classification."),
    "activities_raw": ("Original structured Activities field.", "Retain exact source field before discovering activity vocabulary."),
    "field_description": ("Current asset description used as a possible field-narrative evidence source.", "Preserve source description exactly; only narrowly explicit statements on finished records can reconcile access."),
    "accessibility_description": ("Current accessibility narrative used as a possible evidence source.", "Preserve source field exactly; contradictions become unresolved, not automatically overwritten."),
    "field_validated": ("MAPC field-collection completion state.", "Configured explicit completion tokens map to true, explicit incomplete tokens to false, blank/unrecognized tokens to null. Site state is true only when all accepted members are true, false if any is explicitly false, otherwise null."),
    "staff_reviewed": ("MAPC staff-review completion state.", "Configured explicit tokens map to true/false; blank/unrecognized tokens are null. Site state is true only when all accepted members are true, false if any is explicitly false, otherwise null."),
    "all_assets_field_validated": ("Whether every accepted member of a site is explicitly field-validated.", "Boolean all(member field_validated == true); missing states do not satisfy this coverage indicator."),
    "all_assets_staff_reviewed": ("Whether every accepted member of a site is explicitly staff-reviewed.", "Boolean all(member staff_reviewed == true); missing states do not satisfy this coverage indicator."),
    "any_asset_field_validated": ("Whether at least one accepted site member is explicitly field-validated.", "Boolean any(member field_validated == true); useful for finding sites represented in validated-only analysis."),
    "field_validated_raw": ("Original field-collection checkbox/text value.", "Retain source value before Boolean interpretation."),
    "staff_reviewed_raw": ("Original staff-review checkbox/text value.", "Retain source value before Boolean interpretation."),
    "seo_description": ("Source search-engine description retained for provenance.", "Alias-based ingestion and surrounding whitespace trim; not independent access evidence."),
    "street": ("Recorded street address.", "Alias-based ingestion and surrounding whitespace trim; no geocoding inferred."),
    "zip_code": ("Recorded postal code, retained as text including leading zeroes.", "Read as text; do not convert to numeric."),
    "rental_equipment_raw": ("Original rental equipment response.", "Retain source response; not automatically counted as a physical amenity."),
    "seasonal_raw": ("Original seasonal-use response.", "Retain source response without inferring current opening hours."),
    "field_visitor_notes": ("Source notes for field visitors.", "Retain original field; does not independently establish completed field verification."),
    "photos_done_raw": ("Original photo-completion response.", "Retain source value without conflating photos with finished field collection."),
    "attribute_list": ("Complete unique recorded MAPC attributes/features, including policies and characteristics.", "Parse JSON or CSV/semicolon/newline values, normalize Unicode/whitespace, remove empty/case-insensitive duplicate entries and sort deterministically."),
    "attribute_count": ("Number of distinct recorded MAPC attribute/feature tags.", "Length of attribute_list. At site level count the union across accepted members; not a count of individual fixtures."),
    "amenity_list": ("Recorded attribute tags classified as physical amenities by the versioned taxonomy.", "Filter attribute_list using is_amenity in config/attribute_taxonomy.yaml. Accessibility grouping and physical amenity membership may overlap."),
    "amenity_count": ("Number of distinct recorded amenity tags.", "Length of amenity_list; multiple tags may describe one physical facility, so this does not count fixtures."),
    "activity_list": ("All distinct recorded recreation activity types, discovered from source values.", "Use the same lossless multivalue parser as attributes; no fixed vocabulary. Site level uses set union."),
    "activity_count": ("Number of distinct recorded recreation activity types.", "Length of activity_list; measures recorded breadth, not participation or frequency."),
    "transportation_access_profile": ("Combined audited transit and free entry/parking evidence.", "YES/YES = Transit + free parking; YES/NO = Transit only; NO/YES = Free parking only; NO/NO = Neither; any unknown = Unknown / unresolved. The label free parking abbreviates the combined free-entry/parking tag."),
    "previous_audit_match_status": ("Cautious exact-match result against previous audit references.", "Stable ID or normalized asset/site/municipality match; exact_unique_match, ambiguous_exact_match, no_match. Matching does not authorize reuse of corrections."),
    "previous_audit_candidate_names": ("Similar prior asset names offered only for manual review.", "Restricted same-site/same-municipality name similarity candidates; never apply fuzzy-match values automatically."),
    "asset_count": ("Number of accepted member assets represented in a site summary.", "Count accepted rows in the site_id group; quarantined records excluded."),
    "validated_asset_count": ("Number of accepted site members explicitly field-validated.", "Count member field_validated == true."),
    "staff_reviewed_asset_count": ("Number of accepted site members explicitly staff-reviewed.", "Count member staff_reviewed == true."),
    "coordinate_usable_asset_count": ("Number of accepted site members with usable point coordinates.", "Count member coordinate_usable == true."),
    "site_aggregation_rule": ("Readable aggregation definition attached to each site.", "Any YES, NO only if every accepted member is NO, otherwise UNKNOWN; lists are unions."),
    "site_access_interpretation": ("Scope limitation for a site's aggregated access states.", "A feature can apply to one entrance or member only. Separate features can occur at different entrances; no whole-site route claim."),
    "co_located_transit_free_parking_asset_count": ("Member assets where transit and free entry/parking are both YES on the same record.", "Count accepted member rows satisfying both states. Helps distinguish same-asset presence from a union across different entrances."),
    "near_public_transit_calculated": ("Independent official-MBTA stop/station proximity result.", "YES when nearest service-linked MBTA stop/station distance <= exactly 0.5 mile; NO if farther; UNKNOWN when official feed, geometry or calculation is unavailable."),
    "nearest_transit_stop": ("Name of the nearest eligible MBTA stop or parent station.", "Spatial nearest-point calculation against service-linked GTFS boarding stops and their parent stations."),
    "nearest_transit_stop_id": ("GTFS stop_id for nearest eligible transit point, retained as text.", "Copy the identifier of the nearest service-linked official MBTA stop/station."),
    "nearest_transit_mode": ("Mode(s) associated with the nearest MBTA stop or station.", "Join GTFS stop_times, trips and routes and decode route_type; preserve multiple modes when applicable."),
    "nearest_transit_route_if_practical": ("Route labels serving the nearest eligible MBTA transit point.", "Join official static GTFS stop_times/trips/routes; does not describe departures at the current time."),
    "nearest_transit_distance_miles": ("Straight-line distance from asset point to nearest eligible MBTA stop/station in miles.", "Project WGS84 asset and transit coordinates to EPSG:26986, calculate Euclidean nearest-point distance in meters, divide by 1609.344."),
    "transit_calculation_status": ("Whether independent transit calculation could be completed and why.", "Assigned by transit analysis from official-feed availability, coordinate usability and eligible stop availability."),
    "transit_snapshot_sha256": ("Checksum identifying the exact GTFS ZIP used for this record's independent calculation.", "SHA-256 of cached official transit ZIP; same snapshot provenance is recorded in run_manifest.json."),
    "nearest_stop_status": ("Status or eligibility information for the nearest transit stop.", "Derived from the official GTFS stop selection and nearest-point result; retain unavailable status when calculation cannot be performed."),
    "near_existing_bike": ("Proximity to an eligible existing bicycle facility within the configured radius.", "Compare unsimplified nearest line distance to gis.proximity_radius_miles, default 0.5 mile; UNKNOWN if geometry or eligible network is unavailable."),
    "near_shared_use_path": ("Proximity to an eligible existing shared-use path within the configured radius.", "Compare unsimplified nearest line distance to gis.proximity_radius_miles, default 0.5 mile; UNKNOWN if geometry or eligible network is unavailable."),
    "transit_comparison_status": ("Agreement between original structured transit evidence and independent official GTFS calculation.", "agreement/disagreement only when both original and calculated values are known YES/NO; otherwise not_comparable. Original missing tags remain UNKNOWN."),
    "field": ("Canonical access dimension assessed by an audit row.", "One audit row per retained asset and each of the six audited access fields."),
    "original_value": ("Access value from the current source's structured tag before reconciliation.", "YES for present tag, UNKNOWN otherwise; absence is not NO."),
    "audited_value": ("Final reconciled access state for the audit row's named field.", "Apply current finished-record narrative rules and available official transit proximity evidence, retaining the original value and exact evidence."),
    "verification_status": ("Evidence category for the audit row's final state.", "Record structured-tag, narrative, official external, unknown or conflict status according to the actual evidence used."),
    "evidence": ("Current evidence supporting the final audit state.", "Retain structured-tag statement, quoted narrative, external transit distance, unresolved contradiction or explicit unknown explanation."),
    "source": ("Current source reference supporting an audit row.", "Record source file/record for tags/narratives or official MBTA URL and exact snapshot digest for external transit verification."),
    "narrative_candidate_value": ("State suggested by narrowly explicit current field-narrative patterns.", "YES, NO, UNKNOWN or CONFLICT; only finished-record candidates can alter source-tag evidence. Final transit can separately use official calculation."),
    "prior_match_status": ("Cautious match result against prior reference audit records.", "Unique exact ID or normalized asset/site/municipality match, ambiguous exact match or no match. Fuzzy candidates are review-only."),
    "prior_audited_value": ("Previous audit's value retained strictly as reference evidence.", "Copy only from a unique exact prior match. Do not automatically apply it to the current inventory."),
    "prior_verification_status": ("Previous audit's asserted verification status.", "Retain prior reference claim; this is not a new independent verification."),
    "prior_evidence": ("Previous audit's evidence text.", "Retain reference wording for review and comparison with current evidence; do not assume current validity."),
    "prior_source": ("Source citation supplied by the previous audit.", "Retain previous citation for review. Prior links are not automatically reverified or accepted as current evidence."),
    "prior_audit_file": ("Project-relative file supplying the matched prior audit record.", "Prefer prior CSV over alternative XLSX representation to avoid double-counting matching references."),
    "prior_reassessment": ("Outcome of comparing current evidence with the prior audit value.", "agrees_with_current_evidence, not_applied_requires_current_evidence or no_matching_prior_reference; previous claims never override by matching alone."),
    "prior_fuzzy_candidates_review_only": ("Potential previous asset-name matches requiring human review.", "Same-site/same-municipality similar-name candidates; names are reported but never applied automatically."),
}

ACCESS_DESCRIPTIONS = {
    "near_public_transit": "An MBTA stop or station within 0.5 mile of the asset; recorded/audited evidence is separate from independent calculation.",
    "free_entry_parking": "Combined free entry and designated parking policy; the supplied WPI guide requires both to be always fully free.",
    "restrooms_available": "Recorded permanent restroom availability under the supplied field-guide definition.",
    "accessible_parking": "Recorded designated accessible parking; generic parking alone does not establish accessible parking.",
    "accessible_restroom": "Recorded accessible restroom facility; ordinary restroom presence alone does not establish accessibility.",
    "wheelchair_stroller_friendly_trail": "Recorded wheelchair/stroller-friendly trail characteristic; flat pavement alone is not sufficient evidence.",
}


def definition(field, dataset):
    """Return specific descriptions/rules for each exported canonical field."""
    if field in BASE:
        return BASE[field]
    for access, desc in ACCESS_DESCRIPTIONS.items():
        if field == access:
            return desc, "Alias of the final audited value at asset level. Site level uses any-YES, all-NO, otherwise UNKNOWN across accepted members."
        if field.startswith(access + "_"):
            suffix = field[len(access) + 1:]
            definitions = {
                "original_value": ("Original structured-tag presence for " + desc, "YES when the corresponding current MAPC attribute tag is present; otherwise UNKNOWN, never automatically NO."),
                "audited_value": ("Final reconciled evidence state for " + desc, "Use structured/current finished-record narrative evidence; conflicts and quarantine remain UNKNOWN. For transit only, an available official GTFS calculation establishes the audited state, with original and calculated fields and explicit external audit evidence retained."),
                "verification_status": ("Evidence provenance/verification category for " + desc, "structured_tag_only, unknown, field_narrative_verified, corrected_from_field_narrative, conflict_needs_review; external statuses only when supported by cited external evidence."),
                "evidence": ("Quoted or summarized evidence supporting the access audit for " + desc, "Preserve current structured tag, exact field-narrative sentence, unresolved contradiction, or explicit absence-of-evidence explanation."),
                "source": ("Traceable current source for the access audit for " + desc, "Project-relative source filename, CSV record ordinal and evidence type; prior reference values are not silently applied."),
            }
            if suffix in definitions:
                return definitions[suffix]
            if suffix in {"yes_count", "no_count", "unknown_count"}:
                state = suffix.split("_")[0].upper()
                return f"Number of site member assets with {state} for {desc}", f"Count accepted members whose final audited state is {state}; the three state counts sum to asset_count."
    if field.startswith("mean_asset_"):
        metric = field[len("mean_asset_"):]
        return f"Arithmetic mean of member-asset {metric} within a site.", f"Sum {metric} over accepted member assets divided by asset_count; distinct from site-union counts."
    if field in {"asset_id_list", "source_record_key_list", "municipality_list", "subregion_list"}:
        return "Distinct member " + field[:-5].replace("_", " ") + " values represented in a site.", "Sorted unique values across accepted member assets; serialized as a JSON array."
    if field.startswith("nearest_") and any(t in field for t in ["bike_facility", "shared_use_path", "walking_trail"]):
        network = "bicycle facility" if "bike_facility" in field else "shared-use path" if "shared_use_path" in field else "public walking trail"
        if field.endswith("_name"):
            return f"Recorded name of the nearest eligible {network} line feature.", "Spatial-index nearest unsimplified eligible line; retain network source name, including unknown names."
        if field.endswith("_type"):
            return f"Decoded facility type of the nearest eligible {network}.", "Use locally preserved MAPC field coding metadata; undecoded codes remain Unknown."
        if field.endswith("_source_feature_key"):
            return f"Traceable key of the nearest eligible {network} source feature.", "Copy the selected line feature's source_feature_key from the processed GeoPackage; joins proximity result to original MAPC geometry and source-row provenance."
        if field.endswith("_distance_ft") or field.endswith("_distance_miles"):
            unit = "feet" if field.endswith("_ft") else "miles"
            divisor = "0.3048" if unit == "feet" else "1609.344"
            return f"Shortest straight-line point-to-line distance to an eligible {network}, in {unit}.", f"Use full unsimplified line geometry projected to EPSG:26986; compute meters and divide by {divisor}. Never use a centroid."
    if "_within_0_" in field:
        radius = "0.25" if "0_25" in field else "0.5"
        return f"Whether an eligible existing bicycle/shared-use line or public walking trail is within {radius} mile of the asset.", f"YES if nearest full line geometry distance <= {radius} mile, NO if farther, UNKNOWN when usable asset geometry or eligible lines are unavailable."
    if field == "map_marker_radius":
        return "Configured marker radius in display pixels.", "Apply production size thresholds to the map size metric; visualization scale only, not a distance in the real world."
    if field == "map_size_metric":
        return "Attribute/amenity metric controlling map marker size.", "Read map.size_metric; default attribute_count."
    # Newly introduced source columns remain explicitly source-defined, not silently interpreted.
    return "Preserved source/export field: " + field.replace("_", " ") + ".", "Retained by the owning ingestion/derivation module; review new field semantics before including it in substantive analysis."


def build_data_dictionary(assets, sites, config, root):
    root = Path(root)
    alias_file = root / "config/column_aliases.yaml"
    aliases = yaml.safe_load(alias_file.read_text(encoding="utf-8")) if alias_file.exists() else {}
    rows = []
    frames = [("assets_clean", assets), ("sites_summary", sites)]
    audit_path = root / "output/data/factcheck_audit.csv"
    if audit_path.exists():
        frames.append(("factcheck_audit", pd.read_csv(audit_path, keep_default_na=False)))
    for dataset, frame in frames:
        for field in frame.columns:
            values = frame[field].dropna()
            first = next((v for v in values if v is not None), None)
            kind = "JSON array" if isinstance(first, list) else "Boolean or null" if isinstance(first, bool) else "integer" if pd.api.types.is_integer_dtype(values) else "number" if pd.api.types.is_numeric_dtype(values) else "text"
            desc, rule = definition(field, dataset)
            is_access = field in ACCESS_DESCRIPTIONS or field in {"original_value", "audited_value"} or (not field.startswith("prior_") and field.endswith(("_original_value", "_audited_value", "_calculated"))) or field.startswith("near_") or "_within_0_" in field
            if is_access:
                allowed = "YES; NO; UNKNOWN"
                missing = "UNKNOWN is insufficient or conflicting evidence, not confirmed absence."
                verification = "Consult the associated verification_status, evidence and source. Spatial proximity does not establish route accessibility."
            elif field in {"field_validated", "staff_reviewed"}:
                allowed = "true; false; null"
                missing = "Null means source status is blank/unrecognized; excluded from validated-only analyses."
                verification = "Self-reported workflow status from current MAPC export, not independent verification."
            elif field in {"attribute_count", "amenity_count", "activity_count"}:
                allowed = "Nonnegative integer"
                missing = "Empty structured list becomes 0 recorded tags, not proof no facilities/activities exist."
                verification = "Records source tagging breadth only."
            elif field == "coordinate_status":
                allowed = "valid; missing; malformed; reversed; out_of_range; suspicious_outside_study_area"
                missing = "missing status retains a source row with null parsed coordinates."
                verification = "Syntactic and geographic plausibility check; not field verification of an entrance."
            elif field == "record_status":
                allowed = "accepted; quarantined"
                missing = "Always assigned."
                verification = "Parser eligibility classification only."
            elif "verification_status" in field:
                allowed = "externally_verified; field_narrative_verified; corrected_from_field_narrative; corrected_from_external_source; structured_tag_only; unknown; conflict_needs_review"
                missing = "unknown when no adequate evidence; conflict_needs_review for unresolved disagreement."
                verification = "Evidence strength/source category, not a calibrated confidence score."
            elif "distance" in field:
                allowed = "Nonnegative number in units named by field"
                missing = "Null if coordinate, source network/feed or eligible geometry is unavailable; never substitute zero."
                verification = "Calculated geometric proximity, not network route length."
            else:
                allowed = "Source text" if kind == "text" else "Nonnegative integer" if kind == "integer" else "Finite number or null" if kind == "number" else "JSON array" if kind == "JSON array" else "true; false; null"
                missing = "Empty string/null means not supplied or not applicable; see derivation for eligibility."
                verification = "Source-derived or processing metadata; no independent verification implied."
            source_field = field.replace("_raw", "") if field in {"field_validated_raw", "staff_reviewed_raw"} else field
            source = "; ".join(aliases.get(source_field, []))
            if not source:
                source = "Attributes" if any(field.startswith(a) for a in ACCESS_DESCRIPTIONS) or field.startswith(("attribute", "amenity")) else "Activities" if field.startswith("activity") else "MAPC GIS ZIP / official cached MBTA GTFS" if field.startswith(("nearest_", "near_existing", "near_shared", "transit_", "bike_facility_", "shared_use_path_")) else "Current source record / accepted site members"
            role = "raw" if field.endswith("_raw") or field in {"source_record_json", "source_cells_json"} else "cleaned" if field in aliases and field not in {"latitude", "longitude", "field_validated", "staff_reviewed", "asset_id", "site_id"} else "derived"
            notes = "Sites aggregate all accepted assets, including unfinished members. Primary analysis recomputes sites using only validated assets." if dataset == "sites_summary" else "One source asset per row; primary analytical population is accepted and field_validated true, unique source_record_key." if dataset == "assets_clean" else "One access-field audit per retained source record. Includes quarantine and unvalidated records for traceability."
            if field == "attribute_count":
                notes += " Default map marker size is number of recorded MAPC attributes/features, not solely physical amenities."
            if field == "site_id":
                notes += " Fallback site-name identity may merge distinct same-name sites; inspect site identity QC."
            rows.append({"dataset": dataset, "field_name": field, "data_type": kind, "description": desc,
                         "allowed_values": allowed, "source_column": source, "raw_cleaned_or_derived": role,
                         "derivation_rule": rule, "missing_value_rule": missing, "verification_meaning": verification,
                         "analysis_notes": notes})
    return pd.DataFrame(rows)


def write_documentation(assets, sites, root, config):
    root = Path(root)
    out = root / "output/documentation"
    out.mkdir(parents=True, exist_ok=True)
    dictionary = build_data_dictionary(assets, sites, config, root)
    dictionary.to_csv(out / "data_dictionary.csv", index=False, encoding="utf-8-sig")
    metric = config.get("map", {}).get("size_metric", "attribute_count")
    text = f'''# MAPC recreation inventory methodology

## Sources and reproducibility

The current full MAPC recreation inventory CSV in `input/assets/` is the primary source. Local official MAPC zipped Shapefiles in `input/gis/` supply authoritative line geometry. Their base-column CSVs are reference material, not geometry substitutes. Supplied field guides inform definitions. Previous fact-check workbooks/CSVs are review references and are never treated as authoritative current inventory. Official MBTA GTFS supports an independently calculated transit comparison when available.

Authoritative source bytes are preserved in the organized input/reference folders. `bootstrap/root_inventory.csv` records original filenames, sizes, SHA-256 and placement; `bootstrap/root_cleanup_report.csv` records the later removal of checksum-identical loose root copies. Each run manifest records source, configuration, code and GTFS checksums. Generated outputs are written under `output/`; downloaded/extracted inputs are cached. The same source and cached transit snapshot, configuration and software version reproduce analytical values; run timestamps and package metadata naturally change.

## Schema, records and identities

`config/schema.yaml` defines required/optional canonical fields and `config/column_aliases.yaml` defines name-based header aliases. Missing critical columns cause a clear failure. Schema reports retain unexpected columns, duplicate headers, mapped aliases, type exceptions and schema changes. Parsers use column names, never hardcoded source positions.

All source records are retained, including blanks and malformed rows. `record_status` distinguishes accepted and quarantined records. Later exact duplicate copies are quarantined; all rows sharing a conflicting identity are quarantined for review. The cleaned dataset retains source filename/checksum, logical record ordinal, physical line span, original row JSON and source-row UID. A quoted multiline CSV record is one record but can occupy several physical lines.

Supplied asset/site IDs are preserved. When absent, an asset key hashes normalized site name, asset name and municipality; a site key hashes normalized site name alone. Name-only site keys retain named cross-town reservations as one site, but can merge unrelated same-name sites. Name/municipality changes can create a new fallback asset key. Version comparison reports rather than silently resolving these cases. Source-row UID is snapshot-specific and is not the permanent asset identity.

## Attributes, amenities and activities

All structured attributes are retained in `attribute_list`. Lists parse JSON or CSV/semicolon/newline forms, normalize Unicode and whitespace, remove empty and formatting/case duplicates, retain wording and sort deterministically. `attribute_count` is the complete number of recorded attribute/feature tags, including access characteristics, policies and site characteristics. It is not a count of physical equipment.

`config/attribute_taxonomy.yaml` assigns the primary groups physical_amenity, accessibility, transportation_access, policy_or_rule, site_characteristic and other. A separate `is_amenity` flag selects physical amenity tags for `amenity_list` and `amenity_count`. An accessible restroom is both accessibility-classified and an amenity; it can describe the same physical facility as Restrooms Available. Counts are tag counts, not unique fixture counts. Future unmapped tags remain present as other and enter review.

Activities use the same multivalue parser and are discovered from every source value; the pipeline has no fixed activity vocabulary. Activity count measures recorded recreation breadth, not participation or visitation. Empty lists mean nothing was recorded, not confirmed absence. Vocabulary dictionaries use all accepted records; primary analytical frequency tables use only validated accepted records, so their counts intentionally differ.

## Coordinates and validation

Coordinates use WGS84 longitude/latitude. Parsed values must be finite and satisfy global latitude/longitude bounds. A configured Massachusetts plausibility rectangle identifies suspicious points. A reversed pair is repaired only when the swapped pair fits that rectangle and the original does not; the raw source and reversal flag are retained. Missing, malformed, out-of-range or outside-study-area points remain in cleaned data and are excluded from spatial use unless configuration explicitly permits an outside point. The plausibility rectangle is not an exact MAPC administrative boundary.

Field-completion and staff-review source values are separately retained and mapped using configured explicit true/false tokens. Blank or unknown values remain null. Checked/completed/finished indicate true; unchecked/incomplete/unfinished indicate false. Field-completion is an inventory workflow label, not proof of independent professional accessibility certification. Maps enable validated assets by default and keep unfinished/unknown-completion assets in a visually distinct layer that starts off.

## Access fact-checking and prior audits

Important access dimensions use YES, NO and UNKNOWN. Structured tag presence establishes recorded YES with `structured_tag_only` status. Missing structured tags alone establish UNKNOWN. Each dimension retains original_value, audited_value, verification_status, evidence and source. The combined free-entry/parking tag follows the supplied WPI field-guide definition that designated parking and entry are always fully free. It is not a separately measured parking-only indicator.

Only narrowly explicit current descriptions on finished records support narrative reconciliation. Generic flat pavement is not enough to establish a wheelchair/stroller-friendly trail; generic restroom or parking presence is not enough to establish its accessibility. Explicit negative and positive evidence that conflict produce UNKNOWN and a review flag. Narrative patterns are deliberately conservative: language not recognized by the parser remains evidence for manual review. This is an auditable rule-based review, not exhaustive external validation of every asset.

Prior audits match by stable ID when possible or an exact normalized asset/site/municipality combination. Ambiguous exact and potential fuzzy matches are flagged; fuzzy matches never apply corrections. Every prior correction is compared against current evidence, and unmatched/outdated claims are not imported as truth. `factcheck_audit.csv` exposes these decisions.

## Transit snapshot and the 0.5-mile definition

Near public transit means an MBTA stop or station within **exactly 0.5 mile** of an asset. The inclusive rule is distance <= 0.5 mile. Official source: [MBTA static GTFS](https://cdn.mbta.com/MBTA_GTFS.zip). The pipeline downloads and caches the feed ZIP, records its URL, retrieval timestamp, size and SHA-256, and reuses the cached snapshot by default. Refresh uses `--refresh-transit`. The exact snapshot digest is preserved in the run manifest and calculated asset fields.

The calculation uses stop_times-linked boarding stops and their parent stations, joined through trips/routes for modes and practical route labels. This is whole-feed static service presence, not a promise of service at the current time or a selected analysis date. Bus, rail/light rail, commuter rail and ferry may be represented according to official feed contents. Eligible stop/station coordinates and asset coordinates are projected to Massachusetts Mainland NAD83, **EPSG:26986**, in meters. Nearest-point planar distance is converted using **1 mile = 1609.344 meters**. This local projection is suitable for study-area proximity; values near the threshold should be interpreted as point-location measures, not surveyed walking distance.

The independent calculated result and original structured value remain separate fields and disagreements are exported. When a calculation is available, the final audited transit value uses that official spatial evidence and its status becomes externally_verified or corrected_from_external_source, with the source checksum and measured distance recorded in the audit. This explicitly documented correction never erases the original structured evidence. No distance is invented if official transit acquisition or geometry is unavailable: calculated fields are null/UNKNOWN, existing recorded/narrative audit states are preserved, the problem appears in QC, and unrelated analysis continues. Transit proximity is not a pedestrian route, an accessible route, an entrance connection or a departure-frequency measure.

## MAPC GIS processing

Local ZIP packages retain all Shapefile sidecars and original line geometry. Source `.prj` metadata determines CRS, and missing/unusable CRS is reported rather than assumed. Full geometry is reprojected to EPSG:26986 for analysis and GeoPackage storage. Web layers use EPSG:4326 with configured simplification only for presentation. Nearest-feature calculations always use unsimplified full lines, never centroids or naive latitude/longitude-degree distances.

MAPC coded fields are interpreted using verified metadata saved with the project; unmapped codes are explicitly Unknown. Existing infrastructure is separate from proposed infrastructure. Current-bike/shared-use proximity excludes proposed/unknown status by default. Public-walking-trail proximity excludes private, closed, lost and unknown-access features by default. Land Line systems are contextual where useful and not substituted for verified transport infrastructure.

Nearest full eligible line distance uses a spatial index and is converted to feet by dividing meters by 0.3048, and miles by 1609.344. Threshold indicators use inclusive <=0.25 and <=0.5-mile tests; missing coordinates or eligible networks give UNKNOWN. The configured general proximity radius defaults to 0.5 mile. Straight-line proximity does not prove safe cycling, a public entrance, a connected route or permission to cross intervening land.

## Site summaries and statistical units

`sites_summary` groups all accepted assets by site_id. Attribute, amenity and activity lists are unions, with separate mean-asset counts. Site access is YES if any member is YES, NO only if all members are NO, and UNKNOWN otherwise. Site field_validated/staff_reviewed are true only if every accepted member is true, false if any member is explicitly false, and null otherwise. Separate all-member/any-member Boolean indicators and counts of finished/reviewed members describe coverage without converting unknown workflow status into false.

Site transit and parking YES can describe different entrances; the co-located member count distinguishes when they apply to the same asset. A site's feature union does not make every entrance accessible. No shared representative point is used to manufacture site proximity. Primary site analytical tables are **recomputed from the validated accepted subset**, so unfinished records do not contribute features to validated-site results.

## Analysis and charts

Primary analyses use all accepted, explicitly field-validated unique assets in the current inventory, not an earlier subset. All thirteen requested questions have dynamically generated findings and source tables in `output/analysis/`. Asset results show group n, means, medians and interquartile ranges. Access tables report YES/NO/UNKNOWN and both known-state (YES+NO) and all-validated denominators. Activity-by-profile rates explicitly report numerator and group denominator.

Assets within a site are clustered. The pipeline provides separate one-row-per-site descriptive sensitivity summaries and rank correlations rather than treating asset rows as independent experimental observations. Spearman rho is the Pearson correlation of average ranks and is undefined without enough variation. Magnitude labels use |rho| <0.3 weak, 0.3–<0.6 moderate, >=0.6 strong as descriptive conventions only. **No hypothesis tests, p-values, claims of statistical significance or causal effects are produced.** Multiple exploratory comparisons, uneven geography, inventory selection and unequal validation coverage limit generalization.

Feature-richness totals include access tags, producing part-whole overlap when compared to accessibility. An additional measure removes the three focus accessibility attribute tags before comparing broader richness. Inner Core is defined only from an explicit source subregion label; other subregions are not a measured distance-from-center category. Near-bike/shared-use groups identify geometric opportunities, not verified route alternatives. Evidence gaps must not be called fragmented access.

Charts export PNG and SVG with titles, units, population sizes and method notes. Source tables remain available as CSV and in the analysis workbook. Excel tables retain numeric counts, numeric shares, text identifiers and JSON lists. The workbooks are saved analytical outputs regenerated by Python, not editable spreadsheet calculation models.

## Map encoding and limitations

Configured marker size metric: **{metric}**. Default `attribute_count` is labelled “Number of recorded MAPC attributes/features.” Size uses fixed production thresholds/radii stored in configuration so newer snapshots remain comparable. Transportation view uses five audited profiles; any unresolved dimension produces the unknown profile, not Neither. The inventory-management view separately displays deterministic workflow/QC categories. Field validation and staff review remain independent. Missing-coordinate records remain in the management queue. The drawer keeps source values, audited/final values, verification, evidence and provenance separate. Site coverage uses every accepted member, without a place-quality score. Bicycle/shared-use/walking networks remain separate layers. See README.md and notes/management_rules.md for the exact display rules and map controls.

The interactive map embeds local overlays independently of online MAPC services. A static map and chart exports support report/poster use if online tiles fail. Internet basemaps, map libraries and static transit snapshots have separate availability/date limitations identified by the build and smoke test. Always inspect the current QC report, run manifest, workbook validation report and map smoke-test results before using a release.
'''
    (out / "methodology.md").write_text(text, encoding="utf-8")
    return dictionary
