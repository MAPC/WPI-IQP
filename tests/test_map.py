from src.make_map import marker_radius, _json
import json

def test_marker_radius_bins():
    config={"map":{"size_thresholds":[0,3,6],"size_radii":[4,8,12]}}
    assert [marker_radius(x,config) for x in [0,2,3,5,6,19]]==[4,4,8,8,12,12]

def test_embedded_source_cannot_close_script_or_create_markup():
    source={"name":"</script><script>alert('source')</script>","separator":"\u2028"}
    embedded=_json(source)
    assert "<" not in embedded
    assert json.loads(embedded)==source


def test_missing_size_value_uses_lowest_bin_without_changing_metric():
    config={"map":{"size_thresholds":[0,3,6,9,12],"size_radii":[5,8,12,17,23]}}
    assert marker_radius(float('nan'),config)==5
    assert [marker_radius(n,config) for n in [2,3,8,9,12]]==[5,8,12,17,23]
