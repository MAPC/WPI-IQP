import pandas as pd
from src.build_site_summary import build_site_summary, aggregate_states


def test_unknown_and_no_site_rules():
    assert aggregate_states(["NO", "UNKNOWN"]) == "UNKNOWN"
    assert aggregate_states(["NO", "NO"]) == "NO"
    assert aggregate_states(["YES", "UNKNOWN"]) == "YES"


def test_site_unions_do_not_sum_overlapping_tags_or_claim_same_entrance():
    base = {"site_id": "s", "site_name": "Park", "municipality": "Town", "subregion": "Region", "record_status": "accepted",
            "field_validated": True, "staff_reviewed": None, "coordinate_usable": True,
            "attribute_list": ["Restrooms Available"], "attribute_count": 1, "amenity_list": ["Restrooms Available"], "amenity_count": 1,
            "activity_list": ["Hiking"], "activity_count": 1}
    frame = pd.DataFrame([{**base, "asset_id": "a", "source_record_key": "a", "near_public_transit": "YES", "free_entry_parking": "UNKNOWN"},
                          {**base, "asset_id": "b", "source_record_key": "b", "near_public_transit": "UNKNOWN", "free_entry_parking": "YES"}])
    site = build_site_summary(frame).iloc[0]
    assert site.asset_count == 2 and site.attribute_count == 1
    assert site.transportation_access_profile == "Transit + free parking"
    assert site.co_located_transit_free_parking_asset_count == 0
    assert site.near_public_transit_unknown_count == 1
    assert site.staff_reviewed is None
    assert not site.all_assets_staff_reviewed
