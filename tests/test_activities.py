from src.parse_activities import parse_activities


def test_unknown_future_activity_is_kept():
    parsed = parse_activities("Hiking, Future Sport,Hiking, Rail Trail/ Shared Use Path")
    assert parsed["activity_count"] == 3
    assert "Future Sport" in parsed["activity_list"]
    assert "Rail Trail/ Shared Use Path" in parsed["activity_list"]
