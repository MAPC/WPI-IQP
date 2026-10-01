"""Development-only browser checks of the generated, self-contained map.

Run with the project Python: tests/browser_map_qa.py --headed --online.
--online permits public tiles only in a visible browser. Optional --artifacts
stores screenshots/results in an internal cache folder, never in output/.
No source data is reprocessed and no product launch invokes this test.
"""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import argparse
import json
import threading


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def run_browser_qa(root, *, headed=False, online=False, artifacts=None):
    root = Path(root).resolve()
    if online and not headed:
        raise ValueError("Online tile checks require --headed for visible browser viewing.")
    if artifacts:
        artifacts = Path(artifacts).resolve()
        if not artifacts.is_relative_to(root / "cache"):
            raise ValueError("Browser artifacts must be under the internal cache/ folder.")
        artifacts.mkdir(parents=True, exist_ok=True)
    report = {"status": "not_run", "checks": [], "errors": [], "screenshots": [],
              "headed": headed, "online": online}
    server = browser = None
    step = "Browser launch"
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as engine:
            launch_errors = []
            for channel in ("msedge", "chrome", None):
                try:
                    browser = engine.chromium.launch(headless=not headed, **({"channel": channel} if channel else {}))
                    report["browser"] = channel or "chromium"
                    break
                except Exception as error:
                    launch_errors.append(str(error).splitlines()[0])
            if browser is None:
                raise RuntimeError("No supported browser: " + "; ".join(launch_errors))
            context = browser.new_context(viewport={"width": 1440, "height": 960}, device_scale_factor=1)
            if not online:
                context.route("https://**/*", lambda route: route.abort())
            page = context.new_page()
            page.on("pageerror", lambda error: report["errors"].append(str(error)))
            server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=str(root / "output/maps")))
            threading.Thread(target=server.serve_forever, daemon=True).start()
            step = "Map initialization"
            page.goto(f"http://127.0.0.1:{server.server_port}/MAPC_access_map.html", wait_until="load", timeout=120000)
            page.wait_for_function("window.mapReady === true", timeout=90000)
            ev = page.evaluate
            records, sites, summary = ev("[managementUI.records, managementUI.sites, managementUI.summary]")
            mapped = {str(row["key"]) for row in records if row["coordinate_usable"]}
            missing = [row for row in records if not row["coordinate_usable"]]
            issue_select = page.locator("#issue-select")
            search = page.locator("#record-search")
            metric = page.locator('#summary-grid .metric[data-count="missing_coordinates"]')
            styles = "assetMarkers.map(m=>({key:m.recordKey,color:m.options.color,fillColor:m.options.fillColor,radius:m.getRadius(),weight:m.options.weight,dashArray:m.options.dashArray,opacity:m.options.opacity,fillOpacity:m.options.fillOpacity}))"
            ev("() => {window.browserQA={map,document,records:managementUI.records,json:JSON.stringify(DATA),home:{center:map.getCenter(),zoom:map.getZoom()}};}")

            def passed(name):
                report["checks"].append(name)

            def shot(name):
                if not artifacts:
                    return
                page.wait_for_timeout(180)
                path = artifacts / f"{name}.png"
                page.screenshot(path=str(path), full_page=False)
                report["screenshots"].append(path.relative_to(root).as_posix())

            def wanted(issue="all", query=""):
                return {str(row["key"]) for row in records
                        if (issue == "all" or issue in row["issue_categories"] or
                            issue == "complete" and row["management_status"] == "complete")
                        and query.lower() in " ".join(str(row.get(key) or "") for key in
                                                       ("site_name", "asset_name", "municipality")).lower()}

            def assert_filter(issue="all", query=""):
                expected = wanted(issue, query)
                visible = set(ev("assetMarkers.filter(m=>map.hasLayer(m)).map(m=>String(m.recordKey))"))
                queued = set(ev("managementUI.state.queue.map(r=>String(r.key))"))
                listed = set(page.locator("#queue-list .record-row").evaluate_all("rows=>rows.map(r=>r.dataset.key)"))
                assert visible == expected & mapped, (issue, query, len(visible), len(expected & mapped))
                assert queued == listed == expected, (issue, query, "queue/list mismatch")
                assert issue_select.input_value() == ev("managementUI.state.issue") == issue
                assert ev("assetMarkers.every(m=>m.options.opacity===1 && m.options.fillOpacity===(m.data.validated?.95:.58))"), "Filtering changed marker semantics"
                assert ev("assetMarkers.every(m=>map.hasLayer(m) || !m.getElement() || !m.getElement().isConnected)"), "A nonmatch remains rendered"
                return visible

            assert len(records) == summary["total_accepted"]
            assert len(mapped) == summary["mapped_assets"] == ev("mapCounts.total")
            assert len(missing) == summary["missing_coordinates"]
            assert sum(row["field_validated"] is True for row in records) == summary["field_validated"]
            assert sum(row["staff_reviewed"] is True for row in records) == summary["staff_reviewed"]
            for site in sites:
                members = [row for row in records if row["site_id"] == site["site_id"]]
                assert site["asset_count"] == len(members)
                for field, source in (("validated_asset_count", "field_validated"),
                                      ("staff_reviewed_asset_count", "staff_reviewed"),
                                      ("coordinate_usable_asset_count", "coordinate_usable")):
                    assert site[field] == sum(row[source] is True for row in members)
            report["counts"] = {"accepted": len(records), "mapped": len(mapped), "missing_coordinates": len(missing), "sites": len(sites)}
            assert_filter()
            baseline = ev(styles)
            passed("Embedded assets, site totals, workflow counts and initial visible markers reconcile")

            step = "Simplified controls"
            assert "Assets without coordinates" in metric.inner_text()
            assert metric.evaluate("el=>el.tagName==='DIV' && !el.hasAttribute('tabindex') && !el.hasAttribute('role') && !el.onclick")
            assert metric.locator("button, a, [tabindex], [role=button]").count() == 0
            assert page.locator("#missing-records-button, #snapshot-button, #queue-export, #clear-review-queue").count() == 0
            assert ev("typeof exportQueue==='undefined' && typeof managementUI.openDialog==='undefined'")
            metric.click()
            assert_filter()
            assert ev(styles) == baseline
            page.locator(".more-summary summary").click()
            assert page.locator(".more-summary").get_attribute("open") is not None
            page.locator(".more-summary summary").click()
            page.locator("#about-button").click()
            assert "0.5 mile" in page.locator("#dialog-body").inner_text()
            page.keyboard.press("Escape")
            passed("Missing-coordinate metric is passive; Snapshot/export are absent; workflow summary and About work")
            if online:
                step = "Online street basemap"
                page.wait_for_function("tileStats.loaded>0", timeout=45000)
                report["basemap"] = ev("tileStats")
                passed("Street basemap loads in a real visible browser")
            shot("01_management")

            step = "Review queues and searches"
            for issue in issue_select.locator("option:not([disabled])").evaluate_all("items=>items.map(item=>item.value)"):
                issue_select.select_option(issue)
                assert_filter(issue)
                assert ev(styles) == baseline
            issue_select.select_option("missing_coordinates")
            assert not assert_filter("missing_coordinates")
            assert "cannot be displayed on the map" in page.locator("#queue-caption").inner_text()
            metric.click()
            assert not assert_filter("missing_coordinates")
            shot("02_missing_coordinates")
            if missing:
                page.locator("#queue-list .record-row").first.click()
                assert "No location has been inferred" in page.locator("#drawer-body").inner_text()
                assert not ev("assetMarkers.some(m=>map.hasLayer(m))")
                page.locator("#drawer-close").click()
            issue_select.select_option("all")
            assert_filter()
            for field in ("site_name", "asset_name", "municipality"):
                term = next((row[field] for row in records if row.get(field)), None)
                if term:
                    search.fill(term)
                    assert_filter("all", term)
                    search.fill("")
                    assert_filter()
            search.fill("__no_inventory_record_matches__")
            assert not assert_filter("all", "__no_inventory_record_matches__")
            search.fill("")
            issue_select.select_option("field_incomplete")
            original_queue = assert_filter("field_incomplete")
            record = next((row for row in records if str(row["key"]) in original_queue), None)
            if record:
                query = record["site_name"]
                search.fill(query)
                assert_filter("field_incomplete", query)
                search.fill("")
                assert assert_filter("field_incomplete") == original_queue
            issue_select.select_option("all")
            assert_filter()
            assert ev(styles) == baseline
            passed("Every queue/search removes nonmatching markers; missing queue has no markers; clearing restores the active queue without refresh")

            step = "Details, evidence and coincident records"
            if records:
                evidence = next((row for row in records if "access_conflict" in row["issue_categories"]), records[0])
                ev("key=>managementUI.selectRecord(key)", evidence["key"])
                assert "staff review" in page.locator("#drawer-body").inner_text().lower(), "Staff review is missing from details"
                assert "site collection progress" in page.locator("#drawer-body").inner_text().lower(), "Site progress is missing from details"
                for item in evidence["access_evidence"]:
                    card = page.locator(f'[data-access-field="{item["field"]}"]')
                    assert card.locator('[data-value="source"]').inner_text() == str(item["original_value"] or "Unknown")
                    assert card.locator('[data-value="audited"]').inner_text() == str(item["audited_value"] or "Unknown")
                shot("03_details_evidence")
                page.locator("#drawer-close").click()
            colocated = ev("() => {const m=assetMarkers.find(a=>assetMarkers.some(b=>b!==a&&a.getLatLng().distanceTo(b.getLatLng())<1));return m?m.recordKey:null;}")
            if colocated:
                ev("key=>managementUI.selectRecord(key)", colocated)
                choices = page.locator("[data-colocated]")
                assert choices.count() > 1
                key = choices.nth(1).get_attribute("data-colocated")
                choices.nth(1).click()
                assert ev("managementUI.state.selected") == key
                page.locator("#radius-toggle").check()
                assert ev("Math.abs(managementUI.verificationLayer.getLayers()[0].getRadius()-804.672)<.001")
                issue_select.select_option("missing_coordinates")
                assert not assert_filter("missing_coordinates")
                assert ev("managementUI.verificationLayer.getLayers().length") == 0
                page.locator("#drawer-close").click()
                issue_select.select_option("all")
                assert_filter()
            passed("Details preserve source/audited evidence, site progress and coincident selection; filtered selection cannot leak a map radius")

            step = "GIS, transit, views, Home and legend"
            page.locator("#layers-button").click()
            names = ev("Object.keys(mapLayers)")
            for name in names:
                checkbox = page.locator(f'#layer-options input[data-layer="{name}"]')
                checkbox.uncheck()
                assert not ev("name=>map.hasLayer(mapLayers[name])", name)
                checkbox.check()
                assert ev("name=>map.hasLayer(mapLayers[name])", name)
                if name not in ("Field-validated assets", "Unvalidated / unfinished assets"):
                    checkbox.uncheck()
            page.locator("#layers-close").click()
            for mode in ("transport", "management"):
                page.locator(f"#mode-{mode}").click()
                mode_style = ev(styles)
                if mode == "transport":
                    assert ev("assetMarkers.every(m=>m.options.fillColor===m.data.color)")
                    shot("04_transportation")
                issue_select.select_option("field_incomplete")
                assert_filter("field_incomplete")
                assert ev(styles) == mode_style
                issue_select.select_option("all")
                assert_filter()
            zooms = ev("() => {const old=map.options.zoomSnap;map.options.zoomSnap=.1;map.setZoom(10.1,{animate:false});const tenth=map.getZoom();map.options.zoomSnap=.25;map.setZoom(10.25,{animate:false});const quarter=map.getZoom();map.options.zoomSnap=old;return {tenth,quarter};}")
            assert abs(zooms["tenth"] - 10.1) < .001 and abs(zooms["quarter"] - 10.25) < .001
            page.locator("#home-button").click()
            assert ev("map.project(map.getCenter()).distanceTo(map.project(browserQA.home.center)) <= 1 && Math.abs(map.getZoom()-browserQA.home.zoom)<.001")
            page.locator("#legend-button").click()
            assert not page.locator("#legend").is_visible()
            page.locator("#legend-button").click()
            passed("Both color views, every GIS/transit/asset layer, fractional zoom, Home and legend remain functional")

            step = "Scrollable hover and immediate pointer exit"
            if mapped:
                hover = max((row for row in records if str(row["key"]) in mapped), key=lambda row: row.get("attribute_count", 0) + row.get("activity_count", 0))
                ev("key=>{const m=managementUI.markerLookup.get(key),p=m.getLatLng();map.stop();map.setView([p.lat,p.lng+.005],14,{animate:false});window.qaHoverMarker=m;}", hover["key"])
                ev("() => new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))")
                point = ev("() => {const p=map.latLngToContainerPoint(qaHoverMarker.getLatLng());return {x:p.x,y:p.y};}")
                page.mouse.move(point["x"], point["y"])
                preview = page.locator(".asset-tip:visible")
                preview.wait_for(state="visible")
                preview.hover()
                page.wait_for_timeout(300)
                assert preview.is_visible()
                ev("() => {window.qaHoverMarker=assetMarkers.find(m=>m.isTooltipOpen());}")
                lists = preview.locator(".tip-lists")
                lists.hover()
                zoom = ev("map.getZoom()")
                can_scroll = lists.evaluate("el=>el.scrollHeight>el.clientHeight")
                page.mouse.wheel(0, 360)
                page.wait_for_timeout(200)
                assert ev("map.getZoom()") == zoom
                if can_scroll:
                    assert lists.evaluate("el=>el.scrollTop") > 0
                shot("05_hover_scroll")
                page.mouse.move(720, 20)
                assert ev("() => {const m=qaHoverMarker,n=m.getTooltip().getElement();return !m.isTooltipOpen() && (!n.isConnected || n.hidden || getComputedStyle(n).display==='none' || getComputedStyle(n).visibility==='hidden');}")
                assert preview.count() == 0
                # Canvas hit-testing has a 32 ms move throttle. This pause is
                # only for deliberate re-entry, after immediate exit was checked.
                page.wait_for_timeout(50)
                page.mouse.move(point["x"], point["y"])
                preview.wait_for(state="visible")
                preview.hover()
                page.wait_for_timeout(300)
                ev("() => {window.qaTooltipOpens=0;qaHoverMarker.on('tooltipopen',()=>window.qaTooltipOpens++);}")
                # Return directly from the card to its underlying marker. The
                # incidental mouseover must not reopen the dismissed card.
                page.mouse.move(point["x"], point["y"])
                assert preview.count() == 0
                for delta in (1, -1, 0):
                    page.mouse.move(point["x"] + delta, point["y"])
                    page.wait_for_timeout(70)
                ev("() => {qaHoverMarker.fire('mouseover');}")
                page.wait_for_timeout(300)
                assert preview.count() == 0
                assert ev("!qaHoverMarker.isTooltipOpen() && qaTooltipOpens===0")
                page.mouse.move(720, 20)
                page.wait_for_timeout(50)
                page.mouse.move(point["x"], point["y"])
                preview.wait_for(state="visible")
                assert ev("qaTooltipOpens===1")
                page.mouse.move(720, 20)
                passed("Hover survives marker-to-card crossing, scrolls without map zoom, closes immediately, rejects accidental/stale reopening and permits later intentional hover")

            step = "Mobile and standalone offline map"
            page.locator("#home-button").click()
            for size in ({"width": 390, "height": 844}, {"width": 360, "height": 640}):
                page.set_viewport_size(size)
                page.wait_for_timeout(250)
                if page.locator("#inventory-panel").evaluate("el=>el.classList.contains('collapsed')"):
                    page.locator("#panel-toggle").click()
                assert ev("document.documentElement.scrollWidth<=innerWidth")
                panel = page.locator("#inventory-panel").bounding_box()
                zoom = page.locator(".leaflet-control-zoom").bounding_box()
                assert panel["y"] + panel["height"] <= zoom["y"], (panel, zoom)
                issue_select.select_option("missing_coordinates")
                assert not assert_filter("missing_coordinates")
                issue_select.select_option("all")
                assert_filter()
            shot("06_mobile_expanded")
            assert ev("map===browserQA.map && document===browserQA.document && managementUI.records===browserQA.records && JSON.stringify(DATA)===browserQA.json")
            passed("All queue/search/view interactions preserve the same map/document and unmodified embedded records")
            context.route("https://**/*", lambda route: route.abort())
            page.goto((root / "output/maps/MAPC_access_map.html").as_uri(), wait_until="load", timeout=120000)
            page.wait_for_function("window.mapReady===true")
            assert ev("map.hasLayer(offlineLayer) && !map.hasLayer(streetLayer)")
            assert ev("mapCounts.total") == len(mapped)
            page.locator("#panel-toggle").click()
            issue_select.select_option("missing_coordinates")
            assert not assert_filter("missing_coordinates")
            if missing:
                page.locator("#queue-list .record-row").first.click()
                assert "No location has been inferred" in page.locator("#drawer-body").inner_text()
                shot("07_offline_mobile_details")
            passed("Mobile panels do not cover zoom; mobile queues restore markers; offline HTML retains map, list and details")
            assert not report["errors"], report["errors"]
            passed("No JavaScript errors during desktop, mobile, online/offline interaction")
            report["status"] = "passed"
            browser.close()
            browser = None
    except Exception as error:
        import traceback
        report["status"] = "failed"
        report["errors"].append(f"{step}: {type(error).__name__}: {error}")
        report["failure_traceback"] = traceback.format_exc()
    finally:
        if server:
            server.shutdown()
            server.server_close()
    if artifacts:
        (artifacts / "results.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--online", action="store_true")
    parser.add_argument("--artifacts", type=Path, help="Optional screenshots/results under cache/validation/.")
    args = parser.parse_args()
    result = run_browser_qa(Path(__file__).resolve().parents[1], headed=args.headed,
                            online=args.online, artifacts=args.artifacts)
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["status"] == "passed" else 1)
