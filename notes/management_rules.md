# Inventory management display rules

This is an internal inventory, fieldwork-status, and data-QC view. All labels are deterministic descriptions of the recorded workflow. They are not park quality, safety, accessibility, or recreation recommendations. The view is read-only and does not change the accepted analytical datasets, source values, field validation, or staff review.

`src/map_management.py` reads the existing accepted asset records, site summary, current source schema diagnostics, and analytical run manifest. It retains every original asset and site field in the display payload, adds management fields, and writes no files. The map build and browser reporting are separate steps.

| Category | Exact rule |
| --- | --- |
| Field collection incomplete | `field_validated` is not explicitly true. Blank/unknown and explicit false remain distinguishable in the details panel. |
| Staff review pending | `staff_reviewed` is not explicitly true, independently of field validation. |
| Missing usable coordinates | `coordinate_usable` is not explicitly true. Keep the accepted record available without inventing a map position. |
| Access evidence conflict / unresolved | Any access field has verification status `conflict_needs_review`, `conflict`, `unresolved`, `needs_review`, `unresolved_needs_review`, `evidence_conflict`, or `unresolved_conflict`. |
| Source / data-quality warning | A current-source schema row diagnostic, a nonempty `record_issue`, an explicit non-unique `duplicate_status`, or a usable-coordinate warning/correction exists. Schema row diagnostics are applied only when the source path and SHA-256 match the current records. |
| Changed since previous snapshot | A change report for the current source passes the provenance checks below and includes the accepted record's source-record key. |
| No known management issues | None of the six issue categories applies. This is a statement about recorded workflow and QC evidence only. |
| Multiple issues | Two or more distinct issue categories apply. All category counts and exact record-level reasons remain available; no issue is suppressed by this display label. |

There are six independently reported access fields: near public transit, combined free entry / parking, accessible parking, accessible restroom, restrooms available, and wheelchair / stroller friendly trail. A plain `UNKNOWN` access value or `unknown` verification state is not a conflict. Resolved corrections also do not create a conflict merely because the source and final values differ. The details retain source value, audited/final value, verification status, evidence, and source separately. Opposite known YES/NO values receive a disagreement flag; any source-to-final difference also has a separate display flag.

Issue counts are overlapping counts of accepted records, not a sum that should equal the accepted total. Access-conflict record counts and unresolved access-field counts are separate because one record can have several unresolved fields. The two quarantined source rows are preserved in the analytical output but are not accepted management assets or missing-coordinate management items.

## Site progress

The model reconciles the site IDs and the existing asset, validated, reviewed, and usable-coordinate counts against every accepted member asset. Mismatched membership or counts fail explicitly.

- Field collection complete: every accepted member asset is explicitly field validated.
- Field collection partial: at least one, but fewer than all, accepted members is explicitly field validated.
- Field collection not started: no accepted member is explicitly field validated. This describes recorded validation, not whether any real-world visit happened.
- Needs staff review: at least one accepted member is not explicitly staff reviewed.
- No known site management issues: every accepted member has no known management issue.
- Field-validation coverage: validated member count divided by all accepted member assets, expressed as a percentage. Staff-review coverage is calculated independently.

No coverage value is used as a place-quality or accessibility score. “Fully field complete” and “no known management issues” are different counts. A field-complete site may still need staff review or have an evidence conflict.

## Comparison provenance

The model never runs a historical comparison. It exposes an existing `output/reports/change_report.csv` only when:

1. The manifest identifies a previous input with a checksum.
2. The report exists, has the expected comparison schema and supported change types, and its SHA-256 equals the current manifest's generated-file entry.
3. The current authoritative source checksum equals the accepted asset source checksum.
4. The run has a timestamp and is successful. During a new pipeline run, an explicit `comparison_status: complete` may instead confirm the completed comparison stage before final QC; the snapshot still shows the actual pending QC status.

The supported comparison types are new, removed, coordinate, attribute, amenity, activity, access-field, and validation changes, possible rename/review candidates, and ambiguous identities. Removed rows remain separate comparison metadata and never become present-day map markers. Previous/current values, match method, and review note remain available. A missing, stale, malformed, or unverifiable report disables change review with an explanation.

The current analytical snapshot has no previous-input comparison. Its change view is therefore disabled, with “No comparison snapshot is currently loaded.”

## Snapshot checked during this interface update

These are observed verification results, not implementation constants: 211 accepted assets; 101 field validated and 110 awaiting field completion; 27 staff reviewed and 184 awaiting review; 171 mapped and 40 without usable coordinates; 4 records with 4 unresolved access fields; 2 records with current schema warnings; 24 records with no known management issues. There are 131 sites: 68 fully field validated, 0 partially field validated, 63 with no recorded field validation, 112 needing staff review, and 16 with no known management issues. Category counts overlap.

The two current source warnings are the postal-code-like municipality value `02176` in schema source rows 75 and 76. It is displayed unchanged; no municipality is guessed.

The focused management tests cover unknown semantics, independent workflows, source/final disagreements, all-asset site counts, schema provenance, valid and invalid comparisons, removed records, JSON serialization, deterministic output, duplicate identities, and non-mutation of the input data. They do not rerun GIS, transit, source parsing, analysis, or workbooks.
