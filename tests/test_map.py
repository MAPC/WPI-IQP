from src.make_map import marker_radius, marker_content

def test_marker_radius_bins():
    config={"map":{"size_thresholds":[0,3,6],"size_radii":[4,8,12]}}
    assert [marker_radius(x,config) for x in [0,2,3,5,6,19]]==[4,4,8,8,12,12]

def test_marker_content_escapes_source_and_exposes_lists():
    tip,popup=marker_content({"site_name":"<script>","asset_name":"Entrance","attribute_count":1,"attribute_list":["Near Public Transit"],"amenity_list":[],"activity_list":["Walking"],"activity_count":1})
    assert "<script>" not in tip and "&lt;script&gt;" in tip
    assert "Walking" in tip and "Near Public Transit" in tip
    assert "Source record" in popup
