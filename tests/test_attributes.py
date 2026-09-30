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
