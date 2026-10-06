# Interpretation questions and requested corrections

Recorded 2026-10-06 from the user's map review. These requirements are being implemented on 2026-10-06. Implementation and validation are complete: 151 repository tests, 12 generated-map browser QA groups and 10 reviewed screenshots. Transit scope remains the one open policy choice. See WORK_PROGRESS.md for the final checkpoint.

## Urgent: use across municipalities and configurable geographic coverage

User explicitly requires the final tool to work for municipalities beyond Boston. The existing rectangle is a broad Massachusetts plausibility area, not a Boston boundary; many other municipalities already work. Nevertheless, legitimate locations outside that fixed rectangle are currently excluded from mapping when `allow_outside_study_area` is false.

Requirements implemented:

- Separate invalid coordinates (missing, unreadable, impossible latitude/longitude) from valid coordinates outside the configured study area.
- Make the intended study area an explicit, adjustable project setting; do not silently exclude legitimate locations because of the original Massachusetts defaults.
- Review reversed-coordinate detection, which currently also relies on the same rectangle, when supporting additional regions.
- Treat inventory mapping coverage separately from GIS/transit evidence coverage. MBTA and supplied MAPC layers do not provide universal coverage; unavailable/out-of-coverage evidence must not be presented as a confirmed absence of local transit or facilities.
- Add regression cases for Boston, other Massachusetts municipalities, valid locations beyond the original bounds, reversed pairs, and genuinely invalid coordinates. Preserve current inventory results where applicable.

Status: implemented. Globally valid locations remain mapped; expected-region checks are advisory, and separate GIS/transit coverage gates leave unsupported proximity UNKNOWN. Regression tests cover multiple municipalities, other regions, explicit region changes and coordinate reversals.

## Required: accessibility-focused circle size and optional general-features view

User clarification recorded 2026-10-06: the original purpose of circle size is to show how many accessibility features an asset has and help staff identify assets to investigate for improvement. Counting every Attributes tag does not satisfy that purpose.

Requirements implemented:

- Default circle size must use an explicitly defined accessibility-feature count, not the current total attribute_count.
- Exclude general site characteristics such as Family Friendly, Lower Visitation and Primitive (Few / No Amenities) from the default size. Activities and unrelated policy/general amenity tags must not inflate the accessibility count.
- Define and document which tags qualify as accessibility features. Do not automatically substitute the current amenity_count: its taxonomy measures a different concept and excludes some accessibility characteristics.
- Add an optional user toggle for a general-features sizing view, allowing a broader overview of the asset's recorded offerings. This must remain separate from the default accessibility-focused view and from the existing management/transportation color modes.
- Update the size legend, hover/drawer count labels and explanatory text when the sizing view changes. Make the active sizing measure obvious.
- Support the user's improvement-review goal while distinguishing missing/unknown documentation from confirmed absence. Fewer recorded features can prompt review but must not automatically mean worse accessibility or a proven need for physical improvements. The optional general-features count likewise describes recorded offerings, not a validated site-quality score.
- Add focused tests showing that adding Family Friendly, Lower Visitation, Primitive or activity tags does not enlarge a circle in the default view; eligible accessibility features do affect its size; switching the optional sizing view updates sizes/legend without altering records, filters or color meanings.

Status: implemented. Default accessibility-only size and optional all-attributes size are independent of colors/filters. Seven explicit taxonomy tags qualify; both counts and subset lists remain visible. Focused browser regressions pass.

## Other interpretation and evidence corrections

- Accessible parking: distinguish the recorded presence of designated accessible parking from a description of missing access aisles. Do not present missing aisles alone as proof that no designated spaces exist. User specifically questioned Ames Long Pond. Review the operational field definition before changing the evidence rule; do not infer regulatory compliance.
- Restrooms at another location: F. Gilbert Hills State Forest OHV Parking describes no restrooms here but restrooms at the main entrance reached by trails. Current narrative matching wrongly combines these locations. A future fix should separate local absence from remote facilities, with regression coverage and no invented evidence.
- Transit definition: user says MAPC tags near transit for nearby T stops. Current software includes all eligible served modes in the cached MBTA static GTFS, including buses and shuttles. Resolve whether the intended MAPC definition is rail-only before calling broader calculated values corrections to the source tag.
- Terminology: source YES/UNKNOWN is generated from presence/absence of the Attributes tag; Airtable has no separate source-value field. Clarify that absence is not an explicit negative under the present rule. Consider clearer labels such as recorded tag and calculated proximity.
- Inventory labels: features means recorded Attributes; Activities do not control circle size. Site-characteristic tags are displayed under Recorded attributes/features, with no separate characteristics panel. Classified amenities is a configured subset of Attributes, not a scan of description paragraphs or a count of unique facilities.
- Current checkbox export contains checked and blank values only; generic parser support for explicit false does not mean the current export contains explicit negatives.

Implementation now changes the requested coordinate acceptance, accessibility sizing, narrative evidence and display terminology. Source data is unchanged. The transit-policy decision remains open; the existing all-mode calculation is retained and labeled separately instead of asserting corrections to the source tagging policy.

## Final disposition — 2026-10-06

Parking/aisle separation, location-aware restroom evidence, source/tag terminology, inventory subsets and checked/blank explanations are implemented. The original problem descriptions above are retained as request history. Transit mode policy is the only open decision: preserve all MBTA modes unless the user explicitly selects rail-only. Other providers and arbitrary language understanding are limitations, not silently claimed capabilities. Full results and file list are in WORK_PROGRESS.md.
