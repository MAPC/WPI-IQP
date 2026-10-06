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


def fixture_html(online=False, transit_difference=False):
    root = Path(__file__).resolve().parents[1]
    records = []
    for key, validated in [("a", True), ("b", False)]:
        records.append({"key": key, "site_id": "s", "site_name": "Test site", "asset_name": "Validated court" if validated else "Unfinished trail", "municipality": "Town",
                        "coordinate_usable": True,
                        "field_validated": validated, "staff_reviewed": True, "source_line_start": 12, "source_line_end": 14,
                        "attribute_list": ["Accessible Parking", "Family Friendly", "Lower Visitation", "Free Entry / Parking", "Leashed Dogs Allowed", "Restrooms Available"],
                        "attribute_count": 6, "accessibility_feature_list": ["Accessible Parking"], "accessibility_feature_count": 1,
                        "site_characteristic_list": ["Family Friendly", "Lower Visitation"],
                        "amenity_list": ["Accessible Parking", "Restrooms Available"], "amenity_count": 2, "activity_list": ["Hiking"], "activity_count": 1,
                        "near_public_transit_original_value": "UNKNOWN", "near_public_transit_calculated": "NO", "near_public_transit_audited_value": "NO",
                        "transit_calculation_status": "calculated_official_gtfs",
                        "free_entry_parking": "YES", "near_t_rail_calculated": "NO",
                        "transportation_profile_all_mbta": "Free parking only", "transportation_profile_t_rail": "Free parking only",
                        "t_rail_calculation_status": "calculated_official_gtfs",
                        "issue_categories": [] if validated else ["field_incomplete"],
                        "issue_reasons": [] if validated else ["Field incomplete"],
                        "management_status": "complete" if validated else "field_incomplete"})
    if transit_difference:
        records[1].update(near_public_transit_calculated="YES", transportation_profile_all_mbta="Transit + free parking",
                          nearest_transit_stop="Nearby bus", nearest_transit_mode="Bus", nearest_transit_distance_miles=.1,
                          nearest_t_rail_stop="Distant subway", nearest_t_rail_mode="Rapid transit", nearest_t_rail_distance_miles=1.2)
    markers = [{"key": row["key"], "validated": row["field_validated"], "lat": 42. + index * .01, "lon": -71.,
                "radius": 8, "color": "#0077C8", "tooltip": "test"} for index, row in enumerate(records)]
    records.append({"key": "unmapped", "site_id": "s", "site_name": "Test site", "asset_name": "Unmapped asset", "municipality": "Town",
                    "field_validated": False, "staff_reviewed": True, "coordinate_usable": False,
                    "coordinate_status": "Missing usable coordinates", "attribute_list": [], "amenity_list": [], "activity_list": [],
                    "issue_categories": ["missing_coordinates", "field_incomplete"],
                    "issue_reasons": ["No usable coordinates", "Field incomplete"], "management_status": "multiple"})
    data = {"markers": markers,
            "networks": {}, "stops": [], "routes": {"type": "FeatureCollection", "features": []},
            "management": {"records": records, "sites": [], "rules": [],
                           "summary": {"total_accepted": 3, "field_validated": 1, "awaiting_field": 2, "staff_reviewed": 3, "missing_coordinates": 1},
                           "changes": {"enabled": False},
                           "snapshot": {"gtfs": {"available": True, "retrieved_utc": "2026-09-30T04:00:15Z", "feed_info": [{"feed_start_date": "20260922"}]},
                                        "gis": {"layers": {"bicycle_facilities": {}, "shared_use_paths": {}, "walking_trails": {}}}}}}
    config = {"online_basemap": online, "size_metric": "accessibility_feature_count", "size_radii": [5, 8, 12, 17, 23], "size_thresholds": [0, 1, 2, 3, 5],
              "general_size_thresholds": [0, 3, 6, 9, 12],
              "colors": {"Transit + free parking": "#0077C8", "Transit only": "#FFB000", "Free parking only": "#C2187A", "Neither": "#3D4650", "Unknown / unresolved": "#AAB4BE"}}
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


def test_queue_controls_show_matching_groups_and_asset_switches_remain_independent(page):
    assert visible(page, "a") and visible(page, "b")
    layer = show_layers(page)
    layer.uncheck()
    assert visible(page, "a") and not visible(page, "b")
    page.select_option("#issue-select", "field_incomplete")
    assert layer.is_checked(), "Selecting a queue enables both asset groups so its matches are shown"
    assert not visible(page, "a") and visible(page, "b")
    layer.uncheck()
    assert not visible(page, "a") and not visible(page, "b")
    page.select_option("#issue-select", "all")
    assert layer.is_checked()
    assert visible(page, "a") and visible(page, "b")


def marker_snapshot(page):
    return page.evaluate("""() => assetMarkers.map(marker => ({
        key: marker.recordKey, visible: map.hasLayer(marker),
        style: Object.fromEntries(['radius','color','weight','dashArray','fillColor','fillOpacity','opacity']
            .map(key => [key, marker.options[key]]))
    }))""")


@pytest.mark.parametrize("mode", ["management", "transport"])
def test_missing_coordinate_queue_hides_all_asset_markers_and_dropdown_restores_without_refresh(page, mode):
    page.evaluate("mode => managementUI.setMode(mode)", mode)
    before = marker_snapshot(page)
    assert all(marker["visible"] for marker in before)
    summary = page.locator('#summary-grid .metric[data-count="missing_coordinates"]')
    assert "Assets without coordinates" in summary.inner_text()
    assert summary.evaluate("el => el.tagName === 'DIV' && !el.hasAttribute('tabindex') && !el.hasAttribute('role') && !el.onclick")
    assert summary.locator("button, a, [tabindex], [role=button]").count() == 0
    assert page.locator("#missing-records-button").count() == 0
    assert page.locator("#clear-review-queue").count() == 0
    page.evaluate("window.queueResetDocumentToken = 'same-document'")
    navigations = []
    page.on("framenavigated", lambda frame: navigations.append(frame.url))

    summary.click()
    assert page.locator("#issue-select").input_value() == "all"
    assert page.evaluate("managementUI.state.issue") == "all"
    assert marker_snapshot(page) == before, "The summary is information only"
    page.select_option("#issue-select", "missing_coordinates")
    assert page.locator("#issue-select").input_value() == "missing_coordinates"
    assert page.evaluate("managementUI.state.issue") == "missing_coordinates"
    assert page.locator("#queue-list .record-row").count() == 1
    assert page.locator('#queue-list [data-key="unmapped"]').is_visible()
    assert page.locator("#queue-map-count").inner_text() == "0 mapped · 1 omitted"
    hidden = marker_snapshot(page)
    assert len(hidden) == 2
    assert not any(marker["visible"] for marker in hidden)
    assert [marker["style"] for marker in hidden] == [marker["style"] for marker in before], "Filtering must change membership, not data styling"
    assert "cannot be displayed on the map" in page.locator("#queue-caption").inner_text()
    assert not page.evaluate("managementUI.markerLookup.has('unmapped')")

    summary.click()
    assert page.locator("#issue-select").input_value() == "missing_coordinates"
    assert page.evaluate("managementUI.state.issue") == "missing_coordinates"
    assert marker_snapshot(page) == hidden, "The summary must not change the selected queue"

    page.click('#queue-list [data-key="unmapped"]')
    assert "No location has been inferred" in page.locator("#drawer-body .omission-note").inner_text()
    assert page.locator('#issue-select option[value="all"]').inner_text().startswith("All inventory records")
    page.select_option("#issue-select", "all")
    assert page.locator("#issue-select").input_value() == "all"
    assert page.evaluate("managementUI.state.issue") == "all"
    assert page.locator("#queue-list .record-row").count() == 3
    assert marker_snapshot(page) == before
    assert page.evaluate("managementUI.state.selected") == "unmapped", "Queue reset should retain the selected details"
    assert page.evaluate("window.queueResetDocumentToken") == "same-document"
    assert navigations == []


@pytest.mark.parametrize("issue", ["missing_coordinates", "field_incomplete"])
def test_dropdown_queue_reset_restores_both_asset_groups_and_preserves_search_without_refresh(page, issue):
    before = marker_snapshot(page)
    assert [marker["visible"] for marker in before] == [True, True]
    page.evaluate("window.queueResetDocumentToken = 'same-document'")
    navigations = []
    page.on("framenavigated", lambda frame: navigations.append(frame.url))
    page.select_option("#issue-select", issue)
    assert page.locator("#issue-select").input_value() == issue
    assert page.evaluate("managementUI.state.issue") == issue
    assert page.locator("#clear-review-queue").count() == 0
    if issue == "field_incomplete":
        assert visible(page, "b") and not visible(page, "a")
    else:
        assert not visible(page, "a") and not visible(page, "b")
    assert page.locator('#issue-select option[value="all"]').inner_text().startswith("All inventory records")
    page.select_option("#issue-select", "all")
    assert page.locator("#issue-select").input_value() == "all"
    assert page.evaluate("managementUI.state.issue") == "all"
    assert page.locator("#record-search").input_value() == ""
    assert marker_snapshot(page) == before
    assert not page.evaluate("managementUI.markerLookup.has('unmapped')")

    # Clearing only the issue category must preserve an independent text search.
    page.fill("#record-search", "Unmapped asset")
    search_styles = marker_snapshot(page)
    assert not any(marker["visible"] for marker in search_styles)
    page.select_option("#issue-select", issue)
    assert page.locator("#issue-select").input_value() == issue
    assert page.evaluate("managementUI.state.issue") == issue
    page.select_option("#issue-select", "all")
    assert page.locator("#issue-select").input_value() == "all"
    assert page.evaluate("managementUI.state.issue") == "all"
    assert page.locator("#record-search").input_value() == "Unmapped asset"
    assert page.locator("#queue-list .record-row").count() == 1
    assert marker_snapshot(page) == search_styles
    page.fill("#record-search", "")
    assert marker_snapshot(page) == before
    assert page.evaluate("window.queueResetDocumentToken") == "same-document"
    assert navigations == []


@pytest.mark.parametrize("mode", ["management", "transport"])
def test_search_and_queue_intersection_hides_nonmatches_and_clearing_search_restores_queue(page, mode):
    page.evaluate("mode => managementUI.setMode(mode)", mode)
    before = marker_snapshot(page)
    page.evaluate("window.filterDocumentToken = 'same-document'")
    navigations = []
    page.on("framenavigated", lambda frame: navigations.append(frame.url))
    page.fill("#record-search", "Validated court")
    assert visible(page, "a") and not visible(page, "b")
    assert page.locator("#queue-list .record-row").count() == 1
    page.locator('#summary-grid .metric[data-count="missing_coordinates"]').click()
    assert page.locator("#issue-select").input_value() == "all"
    assert page.locator("#record-search").input_value() == "Validated court"
    assert visible(page, "a") and not visible(page, "b"), "Static summary clicks must preserve the current search and map"
    assert [marker["style"] for marker in marker_snapshot(page)] == [marker["style"] for marker in before]
    page.select_option("#issue-select", "field_incomplete")
    assert not visible(page, "a") and not visible(page, "b"), "Search and queue must intersect"
    assert page.locator("#queue-list .record-row").count() == 0
    page.fill("#record-search", "")
    assert page.locator("#issue-select").input_value() == "field_incomplete"
    assert not visible(page, "a") and visible(page, "b")
    assert page.locator("#queue-list .record-row").count() == 2
    assert [marker["style"] for marker in marker_snapshot(page)] == [marker["style"] for marker in before]
    page.fill("#record-search", "Unfinished trail")
    assert not visible(page, "a") and visible(page, "b")
    page.fill("#record-search", "no matching asset")
    assert not visible(page, "a") and not visible(page, "b")
    page.fill("#record-search", "")
    assert not visible(page, "a") and visible(page, "b")
    page.select_option("#issue-select", "all")
    assert marker_snapshot(page) == before
    assert page.evaluate("window.filterDocumentToken") == "same-document"
    assert navigations == []


def test_selection_modes_and_radius_cannot_reveal_nonmatching_markers(page):
    page.evaluate("managementUI.selectRecord('a')")
    page.locator("#radius-toggle").check()
    assert page.evaluate("managementUI.verificationLayer.getLayers().length") == 1
    page.evaluate("managementUI.markerLookup.get('a').fire('mouseover')")
    page.evaluate("""() => {
        window.fixtureHoverHalos = [];
        map.eachLayer(layer => {
            if (layer instanceof L.CircleMarker && !(layer instanceof L.Circle) && !layer.recordKey)
                window.fixtureHoverHalos.push(layer);
        });
    }""")
    assert page.evaluate("window.fixtureHoverHalos.length") == 1
    page.select_option("#issue-select", "field_incomplete")
    assert not visible(page, "a") and visible(page, "b")
    assert page.evaluate("managementUI.verificationLayer.getLayers().length") == 0
    assert not page.evaluate("window.fixtureHoverHalos.some(layer => map.hasLayer(layer))")
    assert page.evaluate("managementUI.state.selected") == "a", "Details stay readable even when their map marker is filtered out"
    page.evaluate("managementUI.setMode('transport')")
    assert not visible(page, "a") and visible(page, "b")
    page.evaluate("managementUI.selectRecord('a')")
    page.locator("#radius-toggle").check()
    assert not visible(page, "a") and visible(page, "b")
    assert page.evaluate("managementUI.verificationLayer.getLayers().length") == 0
    page.click("#drawer-close")
    assert not visible(page, "a") and visible(page, "b")
    page.select_option("#issue-select", "all")
    assert visible(page, "a") and visible(page, "b")
    assert [marker["style"]["opacity"] for marker in marker_snapshot(page)] == [1, 1]


def test_selected_details_respect_asset_layer_switch_and_closing_preserves_visible_set(page):
    page.evaluate("managementUI.selectRecord('b')")
    assert visible(page)
    layer = show_layers(page)
    page.click("#drawer-close")
    assert visible(page), "Closing selected details must preserve the enabled asset layer"
    layer.uncheck()
    assert not visible(page)
    page.evaluate("managementUI.selectRecord('b')")
    assert not visible(page), "The details drawer must not bypass an asset layer switch"


def test_retained_source_lines_staff_badge_and_about_methods_are_visible(page):
    page.evaluate("() => { assetMarkers[0].openTooltip(); }")
    assert "Staff reviewed" in page.locator(".leaflet-tooltip").inner_text()
    page.evaluate("managementUI.selectRecord('a')")
    source_lines = page.locator("#drawer-body dt").filter(has_text="Physical source lines").locator("xpath=following-sibling::dd[1]")
    assert source_lines.text_content() == "12–14"
    page.click("#about-button")
    assert page.locator("#dialog-title").inner_text() == "About this management map"
    assert "0.5 mile" in page.locator("#dialog-body").inner_text()
    assert "MAPC launcher" in page.locator("#dialog-body").inner_text()
    assert "Official MBTA transit data is loaded (retrieved 2026-09-30T04:00:15Z)" in page.locator("#dialog-body").inner_text()
    assert "All three MAPC GIS source layers are loaded" in page.locator("#dialog-body").inner_text()
    assert page.locator("#snapshot-button, #queue-export").count() == 0
    assert page.get_by_role("button", name="Snapshot").count() == 0
    assert page.get_by_role("button", name="Export CSV").count() == 0
    assert page.evaluate("typeof managementUI.openDialog") == "undefined"
    assert page.evaluate("typeof exportQueue") == "undefined"
    page.click("#dialog-close")
    assert page.locator("#dialog-backdrop").is_hidden()


def test_about_explains_missing_transit_and_gis_data_without_snapshot_dialog(page):
    page.evaluate("""() => {
        DATA.management.snapshot.gtfs.available = false;
        delete DATA.management.snapshot.gis.layers.walking_trails;
    }""")
    page.click("#about-button")
    body = page.locator("#dialog-body").inner_text()
    assert "Calculated transit distances remain Unknown; recorded transit evidence is preserved" in body
    assert "GIS data is unavailable for Public Walking Trails. Related proximity remains Unknown" in body
    assert page.locator("#snapshot-button").count() == 0


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


def test_hover_preview_scrolls_then_closes_immediately_on_pointer_leave_and_reopens(page):
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
    # Inspect the very next browser turn: no polling may mask an exit timer or fade.
    assert page.evaluate("""() => {
        const marker = assetMarkers[0], node = marker.getTooltip().getElement();
        return !marker.isTooltipOpen() && (!node.isConnected || getComputedStyle(node).visibility === 'hidden');
    }"""), "Leaving the card must close it immediately, without a visible delayed fade"
    assert not preview.is_visible()
    # Leaflet's canvas hit-testing throttles moves for 32 ms after card exit.
    # The immediate-close assertion above runs before this natural re-entry pause.
    page.wait_for_timeout(50)
    page.mouse.move(point["x"], point["y"])
    preview.wait_for(state="visible")
    assert page.evaluate("assetMarkers[0].isTooltipOpen() && getComputedStyle(assetMarkers[0].getTooltip().getElement()).visibility !== 'hidden'")


def test_leaving_hover_card_over_its_marker_stays_closed_until_pointer_moves_away(page):
    page.evaluate("""() => {
        map.setView([42, -71.015],14,{animate:false});
        window.fixtureTooltipOpens = 0;
        assetMarkers[0].on('tooltipopen', () => window.fixtureTooltipOpens++);
    }""")
    page.evaluate("() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))")
    point = page.evaluate("() => { const p=map.latLngToContainerPoint(assetMarkers[0].getLatLng()); return {x:p.x,y:p.y}; }")
    page.mouse.move(point["x"], point["y"])
    preview = page.locator(".asset-tip")
    preview.wait_for(state="visible")
    box = preview.bounding_box()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2, steps=8)
    page.wait_for_timeout(300)
    assert preview.is_visible(), "The marker-to-card grace must preserve the preview"
    opens = page.evaluate("window.fixtureTooltipOpens")

    # The departing card exposes the same marker underneath the pointer. That
    # browser-generated mouseover must not immediately reopen the dismissed card.
    page.mouse.move(point["x"], point["y"])
    assert not preview.is_visible(), "Leaving the card must close it immediately"
    for delta in (1, -1, 0):
        page.mouse.move(point["x"] + delta, point["y"])
        page.wait_for_timeout(70)
    # Include a stale canvas hover event and the expired crossing timer.
    page.evaluate("assetMarkers[0].fire('mouseover')")
    page.wait_for_timeout(300)
    assert not preview.is_visible()
    assert page.evaluate("!assetMarkers[0].isTooltipOpen()")
    assert page.evaluate("window.fixtureTooltipOpens") == opens

    page.mouse.move(1100, 200)
    page.wait_for_timeout(50)
    page.mouse.move(point["x"], point["y"])
    preview.wait_for(state="visible")
    assert page.evaluate("window.fixtureTooltipOpens") == opens + 1


@pytest.mark.parametrize("viewport", [{"width": 390, "height": 844}, {"width": 360, "height": 640}])
def test_expanded_mobile_inventory_keeps_both_zoom_buttons_clear(page, viewport):
    page.set_viewport_size(viewport)
    # A fresh document is needed: document.write preserves prior global consts.
    page.goto("about:blank")
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
    page.wait_for_function("value => map.getZoom() > value && !map._animatingZoom", arg=before, timeout=5000)
    page.click(".leaflet-control-zoom-out")
    page.wait_for_function("value => Math.abs(map.getZoom()-value)<0.001 && !map._animatingZoom", arg=before, timeout=5000)


@pytest.mark.parametrize("mode", ["management", "transport"])
def test_accessibility_size_toggle_preserves_color_filters_selection_and_source(page, mode):
    page.evaluate("mode=>managementUI.setMode(mode)", mode)
    page.select_option("#issue-select", "field_incomplete")
    page.fill("#record-search", "Unfinished")
    page.evaluate("() => {window.originalRecords=JSON.stringify(managementUI.records);window.originalMap=map;managementUI.selectRecord('b');}")
    page.locator("#radius-toggle").check()
    baseline = marker_snapshot(page)
    assert page.locator("#size-select").input_value() == "accessibility_feature_count"
    assert page.locator("#size-metric-label").inner_text() == "Recorded accessibility features"
    assert page.locator("[data-size-count]").inner_text() == "1"
    assert "Site characteristics" in page.locator("#recorded-inventory").inner_text()
    assert "Family Friendly" in page.locator("#recorded-inventory").inner_text()
    page.select_option("#size-select", "attribute_count")
    after = marker_snapshot(page)
    assert page.locator("#size-metric-label").inner_text() == "All recorded attributes"
    assert page.locator("[data-size-count]").inner_text() == "6"
    assert page.locator("[data-size-label]").inner_text() == "All recorded attributes"
    for a, b in zip(baseline, after):
        assert a["visible"] == b["visible"]
        assert b["style"]["radius"] > a["style"]["radius"]
        assert {k: v for k, v in a["style"].items() if k != "radius"} == {k: v for k, v in b["style"].items() if k != "radius"}
    assert page.evaluate("managementUI.state.issue==='field_incomplete' && managementUI.state.search==='Unfinished' && managementUI.state.selected==='b' && managementUI.state.radius")
    assert page.locator("#radius-toggle").is_checked()
    assert page.evaluate("assetMarkers[1].getTooltip().getContent().includes('All recorded attributes')")
    page.select_option("#size-select", "accessibility_feature_count")
    assert marker_snapshot(page) == baseline
    assert page.evaluate("JSON.stringify(managementUI.records)===originalRecords && map===originalMap")


def test_drawer_distinguishes_unrecorded_tag_from_calculated_no(page):
    page.evaluate("managementUI.selectRecord('a')")
    card = page.locator('[data-access-field="near_public_transit"]')
    assert card.locator('[data-value="source"]').inner_text() == "Not recorded"
    assert card.locator('[data-value="audited"]').inner_text() == "NO"
    assert "calculated all-mbta proximity" in card.inner_text().lower()
    assert "not a live service check" in card.inner_text()


@pytest.mark.parametrize("color_mode", ["management", "transport"])
def test_transit_selector_preserves_inventory_filters_size_and_layers_without_refresh(page, color_mode):
    page.goto("about:blank")
    page.set_content(fixture_html(transit_difference=True), wait_until="load")
    page.wait_for_function("window.mapReady===true")
    page.evaluate("mode=>managementUI.setMode(mode)", color_mode)
    page.select_option("#issue-select", "field_incomplete")
    page.fill("#record-search", "Unfinished")
    page.select_option("#size-select", "attribute_count")
    page.evaluate("managementUI.selectRecord('b')")
    page.locator("#radius-toggle").check()
    page.evaluate("""() => {
      Object.values(mapLayers).forEach(l=>l.addTo(map));
      window.transitBefore={map,document,records:JSON.stringify(DATA),queue:JSON.stringify(managementUI.state.queue),
        layers:Object.values(mapLayers).map(l=>map.hasLayer(l))};
    }""")
    before = marker_snapshot(page)
    card = page.locator('[data-access-field="near_public_transit"]')
    assert card.locator('[data-value="source"]').inner_text() == "Not recorded"
    assert card.locator('[data-value="audited"]').inner_text() == "YES"
    navigations=[]
    page.on("framenavigated", lambda frame:navigations.append(frame.url))
    page.select_option("#transit-select", "t_rail")
    assert card.locator('[data-value="source"]').inner_text() == "Not recorded"
    assert card.locator('[data-value="audited"]').inner_text() == "NO"
    assert "Calculated T / rail proximity" in card.text_content()
    assert "commuter rail excluded" in page.locator("#transit-definition-note").inner_text()
    assert "Distant subway" in page.locator("#transit-spatial").inner_text()
    assert "Free parking only" in page.locator("#transit-spatial").inner_text()
    assert page.evaluate("managementUI.markerLookup.get('b').getTooltip().getContent().includes('Calculated T / rail proximity: NO')")
    after = marker_snapshot(page)
    if color_mode == "transport":
        assert before[1]["style"]["fillColor"] == "#0077C8"
        assert after[1]["style"]["fillColor"] == "#C2187A"
        assert "T / rail" in page.locator("#legend-explanation").inner_text()
    else:
        assert before == after
    assert [r["visible"] for r in before] == [r["visible"] for r in after]
    assert [r["style"]["radius"] for r in before] == [r["style"]["radius"] for r in after]
    assert page.locator("#issue-select").input_value() == "field_incomplete"
    assert page.locator("#record-search").input_value() == "Unfinished"
    assert page.locator("#size-select").input_value() == "attribute_count"
    assert page.locator("#radius-toggle").is_checked()
    assert page.evaluate("""map===transitBefore.map && document===transitBefore.document && JSON.stringify(DATA)===transitBefore.records &&
      JSON.stringify(managementUI.state.queue)===transitBefore.queue &&
      JSON.stringify(Object.values(mapLayers).map(l=>map.hasLayer(l)))===JSON.stringify(transitBefore.layers)""")
    page.select_option("#transit-select", "all_mbta")
    assert marker_snapshot(page) == before
    assert card.locator('[data-value="audited"]').inner_text() == "YES"
    assert "Nearby bus" in page.locator("#transit-spatial").inner_text()
    assert navigations == []
