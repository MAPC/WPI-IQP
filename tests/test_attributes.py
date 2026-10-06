from src.parse_attributes import parse_attributes, parse_multivalue


def test_complete_attributes_retained_but_policies_not_amenities():
    parsed = parse_attributes(" Free Entry / Parking, Accessible Restroom, Leashed Dogs Allowed, Near Public Transit,Accessible Restroom,, New Feature ")
    assert parsed["attribute_count"] == 5
    assert parsed["amenity_list"] == ["Accessible Restroom"]
    assert "New Feature" in parsed["attribute_list"]


def test_json_delimiters_case_duplicates_and_original_wording():
    assert parse_multivalue('["Birding", " Birding ", "NEW Sport"]') == ["Birding", "NEW Sport"]
    assert parse_multivalue("Birding; birding\nHiking") == ["Birding", "Hiking"]
    assert parse_multivalue('"Fishing, catch and release",Hiking') == ["Fishing, catch and release", "Hiking"]


def test_primitive_is_not_a_physical_amenity():
    parsed = parse_attributes("Primitive (Few / No Amenities)")
    assert parsed["attribute_count"] == 1 and parsed["amenity_count"] == 0


def test_accessibility_size_excludes_general_characteristics_policies_and_activities():
    from src.make_map import marker_radius
    from src.config import load_config
    from pathlib import Path
    config = load_config(Path(__file__).resolve().parents[1])
    base = parse_attributes("Accessible Parking")
    general = parse_attributes("Accessible Parking, Family Friendly, Lower Visitation, Primitive (Few / No Amenities), Free Entry / Parking, Restrooms Available, Hiking")
    accessible = parse_attributes("Accessible Parking, Accessible Restroom")
    assert base["accessibility_feature_count"] == general["accessibility_feature_count"] == 1
    assert marker_radius(base["accessibility_feature_count"], config) == marker_radius(general["accessibility_feature_count"], config)
    assert marker_radius(accessible["accessibility_feature_count"], config) > marker_radius(base["accessibility_feature_count"], config)
    assert len(general["site_characteristic_list"]) == 3
    assert general["amenity_count"] == 2


def test_accessibility_taxonomy_has_seven_explicit_tags_and_deduplicates():
    from src.parse_attributes import load_taxonomy
    tags = [tag for tag, rules in load_taxonomy()["attributes"].items() if rules["classification"] == "accessibility"]
    assert len(tags) == 7
    parsed = parse_attributes(tags + [tags[0].upper()])
    assert parsed["accessibility_feature_count"] == 7
