import pandas as pd
from src.compare_versions import compare_versions


def test_stable_id_detects_attribute_coordinate_access_and_validation_changes():
    old = {"source_record_key": "A", "asset_name": "Old", "site_name": "Park", "latitude": 42.0, "longitude": -71.0,
           "attribute_list": ["Near Public Transit"], "amenity_list": [], "activity_list": ["Hiking"], "field_validated": False, "near_public_transit": "UNKNOWN"}
    new = {**old, "asset_name": "New", "latitude": 42.1, "attribute_list": [], "field_validated": True, "near_public_transit": "YES"}
    changes = compare_versions(pd.DataFrame([new]), pd.DataFrame([old]))
    assert set(changes.change_type) == {"potential_rename", "coordinate_change", "attribute_change", "validation_change", "access_change"}


def test_fallback_rename_candidate_retains_added_removed():
    old = {"source_record_key": "old", "asset_name": "Old", "site_id": "site", "site_name": "Park", "municipality": "Town", "latitude": 42., "longitude": -71., "coordinate_usable": True}
    new = {**old, "source_record_key": "new", "asset_name": "New"}
    changes = compare_versions(pd.DataFrame([new]), pd.DataFrame([old]))
    assert set(changes.change_type) == {"added_asset", "removed_asset", "potential_rename"}


def test_attribute_reordering_is_not_change():
    old = {"source_record_key": "a", "attribute_list": ["One", "Two"]}
    new = {"source_record_key": "a", "attribute_list": ["Two", "One"]}
    assert compare_versions(pd.DataFrame([new]), pd.DataFrame([old])).empty
