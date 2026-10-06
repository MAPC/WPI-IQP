import pandas as pd
import pytest
from src.reconcile_access_fields import transportation_profile, narrative_evidence, reconcile_access_fields


@pytest.mark.parametrize("transit,parking,expected", [("YES", "YES", "Transit + free parking"), ("YES", "NO", "Transit only"), ("NO", "YES", "Free parking only"), ("NO", "NO", "Neither"), ("YES", "UNKNOWN", "Unknown / unresolved"), ("UNKNOWN", "NO", "Unknown / unresolved")])
def test_profiles_do_not_collapse_unknown(transit, parking, expected):
    assert transportation_profile(transit, parking) == expected


def record(attributes, description="", finished=True):
    return {"asset_id": "id", "site_id": "site", "source_record_key": "id", "source_row_uid": "row", "source_row_number": 2,
            "asset_name": "Entrance", "site_name": "Park", "municipality": "Town", "record_status": "accepted", "record_issue": "",
            "field_validated": finished, "attribute_list": attributes, "field_description": description, "accessibility_description": ""}


def test_missing_tag_is_unknown_and_current_explicit_field_statement_can_correct(tmp_path):
    result, audit = reconcile_access_fields(pd.DataFrame([record([], "No restrooms are available.")]), tmp_path)
    assert result.iloc[0].restrooms_available == "NO"
    assert result.iloc[0].free_entry_parking == "UNKNOWN"
    assert len(audit) == 6


def test_conflicting_current_sources_require_review(tmp_path):
    result, _ = reconcile_access_fields(pd.DataFrame([record(["Restrooms Available"], "No restrooms are available.")]), tmp_path)
    assert result.iloc[0].restrooms_available == "UNKNOWN"
    assert result.iloc[0].restrooms_available_verification_status == "conflict_needs_review"


def test_unfinished_narrative_and_prior_audit_do_not_override(tmp_path):
    directory = tmp_path / "reference/previous_audits"
    directory.mkdir(parents=True)
    pd.DataFrame([{"asset_name": "Entrance", "site_name": "Park", "municipality": "Town", "near_public_transit_audited": 1,
                   "near_public_transit_verification_status": "corrected_external_verification"}]).to_csv(directory / "audit.csv", index=False)
    result, audit = reconcile_access_fields(pd.DataFrame([record([], "No restrooms are available.", False)]), tmp_path)
    assert result.iloc[0].near_public_transit == "UNKNOWN"
    assert result.iloc[0].restrooms_available == "UNKNOWN"
    transit = audit[audit.field.eq("near_public_transit")].iloc[0]
    assert transit.prior_match_status == "exact_unique_match"
    assert transit.prior_reassessment == "not_applied_requires_current_evidence"


def test_conservative_narrative_rules():
    assert narrative_evidence("free_entry_parking", "Admission is free.")[0] == "UNKNOWN"
    assert narrative_evidence("wheelchair_stroller_friendly_trail", "The path is flat and paved.")[0] == "UNKNOWN"
    assert narrative_evidence("accessible_parking", "There are marked accessible parking spaces without marked access aisles.")[0] == "YES"
    assert narrative_evidence("near_public_transit", "A bus passes nearby.")[0] == "UNKNOWN"
    assert narrative_evidence("restrooms_available", "A portable restroom is available.")[0] == "UNKNOWN"
    assert narrative_evidence("accessible_restroom", "An accessible restroom is a portable restroom.")[0] == "UNKNOWN"


@pytest.mark.parametrize("narrative", [
    "There are marked accessible parking spaces, though no marked access aisle is present.",
    "There are designated accessible parking spaces without marked access aisles.",
])
def test_designated_spaces_and_access_aisles_are_separate(tmp_path, narrative):
    result, _ = reconcile_access_fields(pd.DataFrame([record(["Accessible Parking"], narrative)]), tmp_path)
    row = result.iloc[0]
    assert row.accessible_parking == "YES"
    assert row.accessible_parking_verification_status == "field_narrative_verified"
    assert narrative in row.accessible_parking_qualification
    assert narrative_evidence("accessible_parking", "No access aisles are marked.")[0] == "UNKNOWN"


def test_absent_designated_spaces_still_conflict_with_recorded_tag(tmp_path):
    result, _ = reconcile_access_fields(pd.DataFrame([record(["Accessible Parking"], "There are no designated handicap parking spaces.")]), tmp_path)
    assert result.iloc[0].accessible_parking_verification_status == "conflict_needs_review"


@pytest.mark.parametrize("description", [
    "An unpaved parking area without designated accessible parking spaces.",
    "The parking lot does not have a designated handicap spot.",
    "An unpaved lot without designated handicap spots.",
    "The parking area does not include designated accessible parking spaces.",
])
def test_explicit_absence_of_designated_spaces_cannot_be_positive(description):
    assert narrative_evidence("accessible_parking", description)[0] == "NO"


def test_gilbert_remote_restrooms_do_not_conflict_with_explicit_local_absence(tmp_path):
    narrative = "There are no facilities available at this section of the park; however, several miles-long trails lead to the main entrance of the park, which offers restrooms and a picnic area. No restroom facilities are available either."
    result, _ = reconcile_access_fields(pd.DataFrame([record([], narrative)]), tmp_path)
    row = result.iloc[0]
    assert row.restrooms_available_original_value == "UNKNOWN"
    assert row.restrooms_available == "NO"
    assert row.restrooms_available_verification_status == "corrected_from_field_narrative"
    assert "Other-location" in row.restrooms_available_context_note


def test_remote_absence_does_not_negate_local_facility_and_true_local_conflicts_remain():
    assert narrative_evidence("restrooms_available", "Restrooms are available here; no restrooms are available at another entrance.")[0] == "YES"
    assert narrative_evidence("restrooms_available", "Restrooms are available. No restrooms are available.")[0] == "CONFLICT"
    assert narrative_evidence("restrooms_available", "Trails lead to the main entrance, which offers restrooms.")[0] == "UNKNOWN"


def test_negation_and_no_parking_fees_do_not_create_false_assertions():
    assert narrative_evidence("free_entry_parking", "There are no parking fees.")[0] == "UNKNOWN"
    assert narrative_evidence("accessible_restroom", "There is not an accessible restroom at this entrance.")[0] == "NO"
    assert narrative_evidence("restrooms_available", "There is not a restroom at this entrance.")[0] == "NO"


def test_prior_ambiguous_matches_and_fuzzy_candidates_are_review_only(tmp_path):
    directory = tmp_path / "reference/previous_audits"
    directory.mkdir(parents=True)
    pd.DataFrame([
        {"asset_name": "Entrance", "site_name": "Park", "municipality": "Town", "free_entry_parking_audited": 1},
        {"asset_name": "Entrance", "site_name": "Park", "municipality": "Town", "free_entry_parking_audited": 0},
        {"asset_name": "North Entrance", "site_name": "Park", "municipality": "Town", "free_entry_parking_audited": 1},
    ]).to_csv(directory / "audit.csv", index=False)
    exact = record([])
    fuzzy = {**record([]), "asset_name": "North Entrance!", "asset_id": "other", "source_record_key": "other", "source_row_uid": "otherrow"}
    result, audit = reconcile_access_fields(pd.DataFrame([exact, fuzzy]), tmp_path)
    assert result.iloc[0].previous_audit_match_status == "ambiguous_exact_match"
    assert result.iloc[1].previous_audit_candidate_names == ["North Entrance"]
    assert set(result.free_entry_parking) == {"UNKNOWN"}
