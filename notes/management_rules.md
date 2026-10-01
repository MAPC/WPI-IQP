# Inventory management display rules

This is an internal inventory, fieldwork-status, and data-QC view. All labels are deterministic descriptions of the recorded workflow. They are not park quality, safety, accessibility, or recreation recommendations. The view is read-only and does not change the accepted analytical datasets, source values, field validation, or staff review.

`src/map_management.py` receives accepted asset records, the site summary, current-source schema diagnostics and source/provenance metadata directly from the pipeline in memory. It retains every original asset and site field in the display payload, adds management fields, and writes no files. `src/make_map.py` embeds that payload in the one HTML product. Browser tests are maintenance code and are never run by the staff launcher.

| Category | Exact rule |
| --- | --- |
| Field collection incomplete | `field_validated` is not explicitly true. Blank/unknown and explicit false remain distinguishable in the details panel. |
| Staff review pending | `staff_reviewed` is not explicitly true, independently of field validation. |
| Missing usable coordinates | `coordinate_usable` is not explicitly true. Keep the accepted record available without inventing a map position. |
| Access evidence conflict / unresolved | Any access field has verification status `conflict_needs_review`, `conflict`, `unresolved`, `needs_review`, `unresolved_needs_review`, `evidence_conflict`, or `unresolved_conflict`. |
| Source / data-quality warning | A current-source schema row diagnostic, a nonempty `record_issue`, an explicit non-unique `duplicate_status`, or a usable-coordinate warning/correction exists. Schema row diagnostics are applied only when the source path and SHA-256 match the current records. |
| Changed since previous snapshot | An in-memory comparison with an explicitly configured historical export passes the provenance checks below and includes the accepted record's source-record key. |
| No known management issues | None of the six issue categories applies. This is a statement about recorded workflow and QC evidence only. |
| Multiple issues | Two or more distinct issue categories apply. All category counts and exact record-level reasons remain available; no issue is suppressed by this display label. |

There are six independently reported access fields: near public transit, combined free entry / parking, accessible parking, accessible restroom, restrooms available, and wheelchair / stroller friendly trail. A plain `UNKNOWN` access value or `unknown` verification state is not a conflict. Resolved corrections also do not create a conflict merely because the source and final values differ. The details retain source value, audited/final value, verification status, evidence, and source separately. Opposite known YES/NO values receive a disagreement flag; any source-to-final difference also has a separate display flag.

Issue counts are overlapping counts of accepted records, not a sum that should equal the accepted total. Access-conflict record counts and unresolved access-field counts are separate because one record can have several unresolved fields. The two quarantined rows in the supplied export remain preserved in the original CSV and parser memory; they are not accepted management assets or missing-coordinate management items.

## Queue and map interaction

The Review Queue dropdown is the only queue selector. Summary metrics, including Assets without coordinates, are display-only and have no click action. Search by site, asset or municipality intersects with the current queue. Nonmatching asset markers are removed from their map layers completely, not faded; visible markers retain normal management/transportation colors, sizes, validation outlines and opacity.

Selecting All inventory records restores all mapped records that match any remaining search. Clearing search restores the marker set allowed by the current queue. Both changes apply immediately without a page refresh. Queue selection enables both asset groups, while GIS/transit choices remain independent. A missing-coordinate queue contains accepted records in the list/details and no invented or unrelated asset markers.

Hover cards allow a short marker-to-card transition and scrolling of long lists. Leaving a card closes it promptly without opening it again just because the marker is underneath; intentional later marker hover remains available. Selection opens details without altering the queue predicate. No Snapshot dialog or CSV-export controls form part of the product.

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

The model never runs a historical comparison itself. The pipeline optionally calculates one in memory when `paths.previous_asset_file` identifies a distinct historical export outside the current CSV folder. The model exposes that comparison only when:

1. The supplied metadata identifies the previous input with its source checksum.
2. The comparison frame has the expected schema and supported change types.
3. The current authoritative source checksum equals the accepted asset source checksum.
4. The run has a timestamp and an explicit `comparison_status: complete` from the completed comparison calculation.

The supported comparison types are new, removed, coordinate, attribute, amenity, activity, access-field, and validation changes, possible rename/review candidates, and ambiguous identities. Removed rows remain separate comparison metadata and never become present-day map markers. Previous/current values, match method, and review note remain available. The pipeline compares source-reconciled values before current GTFS reconciliation, so current transit results do not become false historical source changes. A missing, malformed or unverifiable comparison disables change review with an explanation. No comparison report is read from or written to `output/`.

The current configuration has no previous-input comparison. Its change view is therefore disabled, with “No comparison snapshot is currently loaded.”

## Supplied inventory counts

These are observed verification results, not implementation constants: 211 accepted assets; 101 field validated and 110 awaiting field completion; 27 staff reviewed and 184 awaiting review; 171 mapped and 40 without usable coordinates; 4 records with 4 unresolved access fields; 2 records with current schema warnings; 24 records with no known management issues. There are 131 sites: 68 fully field validated, 0 partially field validated, 63 with no recorded field validation, 112 needing staff review, and 16 with no known management issues. Category counts overlap.

The two current source warnings are the postal-code-like municipality value `02176` in schema source rows 75 and 76. It is displayed unchanged; no municipality is guessed.

The focused management tests cover unknown semantics, independent workflows, source/final disagreements, all-asset site counts, schema provenance, valid and invalid comparisons, removed records, JSON serialization, deterministic output, duplicate identities, and non-mutation of the input data. UI tests cover queue/search intersections, complete marker hiding/restoration, the passive missing-coordinate metric, hover-card behavior and the details interface. Actual validation results and limitations are recorded in `notes/map_validation.md`.
