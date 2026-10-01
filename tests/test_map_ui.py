"""Small browser fixtures for management-only interactions and provenance."""
import json
from pathlib import Path
import re

import pytest


@pytest.fixture(scope="module")
def browser():
    playwright = pytest.importorskip("playwright.sync_api")
    with playwright.sync_playwright() as engine:
        launched = None
        errors = []
        for channel in ("msedge", "chrome", None):
            try:
                launched = engine.chromium.launch(headless=True, **({"channel": channel} if channel else {}))
                break
            except Exception as exc:
                errors.append(str(exc).splitlines()[0])
        if launched is None:
            pytest.skip("No supported browser for focused UI fixture: " + "; ".join(errors))
        yield launched
        launched.close()


def fixture_html(online=False):
    root = Path(__file__).resolve().parents[1]
    records = []
    for key, validated in [("a", True), ("b", False)]:
        records.append({"key": key, "site_id": "s", "site_name": "Test site", "asset_name": key, "municipality": "Town",
                        "field_validated": validated, "staff_reviewed": True, "source_line_start": 12, "source_line_end": 14,
                        "attribute_list": [], "amenity_list": [], "activity_list": [],
                        "issue_categories": [] if validated else ["field_incomplete"],
                        "issue_reasons": [] if validated else ["Field incomplete"],
                        "management_status": "complete" if validated else "field_incomplete"})
    data = {"markers": [{"key": row["key"], "validated": row["field_validated"], "lat": 42. + index * .01, "lon": -71.,
                         "radius": 8, "color": "#0077C8", "tooltip": "test"} for index, row in enumerate(records)],
            "networks": {}, "stops": [], "routes": {"type": "FeatureCollection", "features": []},
            "management": {"records": records, "sites": [], "rules": [],
                           "summary": {"total_accepted": 2, "field_validated": 1, "awaiting_field": 1, "staff_reviewed": 2, "missing_coordinates": 0},
                           "changes": {"enabled": False},
                           "snapshot": {"gtfs": {"retrieved_utc": "2026-09-30T04:00:15Z", "feed_info": [{"feed_start_date": "20260922"}]}}}}
    config = {"online_basemap": online, "size_radii": [5, 8, 12, 17, 23], "size_thresholds": [0, 3, 6, 9, 12],
              "colors": {"Transit + free parking": "#0077C8"}}
    replacements = {"__LEAFLET_CSS__": (root / "src/vendor/leaflet.css").read_text(encoding="utf-8"),
                    "__LEAFLET_JS__": (root / "src/vendor/leaflet.js").read_text(encoding="utf-8"),
                    "__MAP_DATA__": json.dumps(data), "__MAP_CONFIG__": json.dumps(config)}
    return re.sub("|".join(replacements), lambda match: replacements[match.group()], (root / "src/map_ui.html").read_text(encoding="utf-8"))


@pytest.fixture
def page(browser):
    page = browser.new_page(viewport={"width": 1500, "height": 1000})
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.set_content(fixture_html(), wait_until="load")
    page.wait_for_function("window.mapReady === true")
    yield page
    page.close()
    assert not errors


def visible(page, key="b"):
    return page.evaluate("key => map.hasLayer(managementUI.markerLookup.get(key))", key)


def show_layers(page):
    if not page.locator("#layers-panel").is_visible():
        page.click("#layers-button")
    return page.locator('#layer-options input[data-layer="Unvalidated / unfinished assets"]')


def test_queue_and_base_layer_union_survives_changes(page):
    assert not visible(page)
    page.select_option("#issue-select", "field_incomplete")
    assert visible(page)
    layer = show_layers(page)
    layer.check()
    page.select_option("#issue-select", "all")
    assert page.evaluate("map.hasLayer(mapLayers['Unvalidated / unfinished assets'])")
    assert visible(page), "Clearing temporary queue markers must preserve the enabled base layer"
    page.select_option("#issue-select", "field_incomplete")
    layer.uncheck()
    assert visible(page), "The active queue must still reveal matching assets when the base layer is off"
    page.select_option("#issue-select", "all")
    assert not visible(page)


def test_selected_reveal_close_preserves_enabled_base_layer(page):
    page.evaluate("managementUI.selectRecord('b')")
    assert visible(page)
    layer = show_layers(page)
    layer.check()
    page.click("#drawer-close")
    assert visible(page), "Closing temporary selected-record reveal must preserve the enabled base layer"
    layer.uncheck()
    assert not visible(page)


def test_retained_source_lines_snapshot_date_and_staff_badge_are_visible(page):
    page.evaluate("() => { assetMarkers[0].openTooltip(); }")
    assert "Staff reviewed" in page.locator(".leaflet-tooltip").inner_text()
    page.evaluate("managementUI.selectRecord('a')")
    source_lines = page.locator("#drawer-body dt").filter(has_text="Physical source lines").locator("xpath=following-sibling::dd[1]")
    assert source_lines.text_content() == "12–14"
    page.evaluate("managementUI.openDialog('snapshot')")
    date = page.locator("#dialog-body dt").filter(has_text="MBTA snapshot date").locator("xpath=following-sibling::dd[1]")
    assert date.text_content() == "2026-09-30T04:00:15Z"


def test_file_copy_disables_online_tiles_and_preserves_offline_data(browser, tmp_path):
    saved = tmp_path / "fixture.html"
    saved.write_text(fixture_html(online=True), encoding="utf-8")
    page = browser.new_page(viewport={"width": 1500, "height": 1000})
    remote_requests = []
    page.on("request", lambda request: remote_requests.append(request.url) if request.url.startswith(("https://", "http://")) else None)
    try:
        page.goto(saved.as_uri(), wait_until="load")
        page.wait_for_function("window.mapReady === true")
        assert page.evaluate("map.hasLayer(offlineLayer) && !map.hasLayer(streetLayer)")
        page.click("#layers-button")
        assert page.locator('#layer-options input[data-layer="Bright street map (online)"]').is_disabled()
        assert remote_requests == []
    finally:
        page.close()


def test_hover_preview_accepts_pointer_and_scrolls_every_recorded_activity(page):
    page.evaluate("""() => {
        const record = managementUI.records[0];
        record.activity_list = Array.from({length:40}, (_, i) => 'Recorded activity ' + (i+1));
        record.activity_count = 40;
        managementUI.setMode('management');
        map.setView([42, -71.015],14,{animate:false});
    }""")
    page.evaluate("() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))")
    point = page.evaluate("() => { const p=map.latLngToContainerPoint(assetMarkers[0].getLatLng()); return {x:p.x,y:p.y}; }")
    page.mouse.move(point["x"], point["y"])
    preview = page.locator(".asset-tip")
    preview.wait_for(state="visible")
    scroller = page.locator(".asset-tip .tip-lists")
    box = scroller.bounding_box()
    assert box is not None
    assert scroller.evaluate("el => el.scrollHeight > el.clientHeight")
    zoom = page.evaluate("map.getZoom()")
    page.mouse.move(box["x"] + box["width"] - 25, box["y"] + box["height"] / 2, steps=8)
    # The card must survive the marker-leave timer while the pointer stays in it.
    page.wait_for_timeout(300)
    assert preview.is_visible()
    page.mouse.wheel(0, 1500)
    page.wait_for_function("document.querySelector('.asset-tip .tip-lists').scrollTop > 0")
    assert scroller.evaluate("el => el.scrollTop + el.clientHeight >= el.scrollHeight - 2")
    assert "Recorded activity 40" in scroller.inner_text()
    assert page.evaluate("map.getZoom()") == zoom, "Scrolling preview content must not zoom the map"
    page.mouse.move(1100, 200)
    preview.wait_for(state="hidden")


@pytest.mark.parametrize("viewport", [{"width": 390, "height": 844}, {"width": 360, "height": 640}])
def test_expanded_mobile_inventory_keeps_both_zoom_buttons_clear(page, viewport):
    page.set_viewport_size(viewport)
    page.set_content(fixture_html(), wait_until="load")
    page.wait_for_function("window.mapReady === true")
    page.click("#panel-toggle")
    page.click(".more-summary summary")
    panel = page.locator("#inventory-panel").bounding_box()
    for selector in (".leaflet-control-zoom-in", ".leaflet-control-zoom-out"):
        button = page.locator(selector)
        assert button.is_visible()
        box = button.bounding_box()
        assert panel["y"] + panel["height"] <= box["y"]
        assert button.evaluate("el => { const b=el.getBoundingClientRect(); const top=document.elementFromPoint(b.x+b.width/2,b.y+b.height/2); return el===top || el.contains(top); }")
    before = page.evaluate("map.getZoom()")
    page.click(".leaflet-control-zoom-in")
    page.wait_for_function("value => map.getZoom() > value", before)
    page.click(".leaflet-control-zoom-out")
    page.wait_for_function("value => map.getZoom() === value", before)
