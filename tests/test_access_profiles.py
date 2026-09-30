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
    assert narrative_evidence("accessible_parking", "There are accessible parking spaces without marked access aisles.")[0] == "NO"
    assert narrative_evidence("near_public_transit", "A bus passes nearby.")[0] == "UNKNOWN"
    assert narrative_evidence("restrooms_available", "A portable restroom is available.")[0] == "UNKNOWN"
    assert narrative_evidence("accessible_restroom", "An accessible restroom is a portable restroom.")[0] == "UNKNOWN"


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
