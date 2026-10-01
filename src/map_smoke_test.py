"""Browser acceptance for the management drawer, custom controls and local data.

Headless checks block tile requests. Use --headed for a normal interactive
online check; public tiles are never downloaded for offline distribution.
"""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import argparse
import json
import threading
import pandas as pd
from .utils import write_json


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def run_map_smoke_test(root, expected, *, headed=False, report_name="map_test_results"):
    root=Path(root).resolve(); out=root/"output/reports"
    shots=out/"map_screenshots"; shots.mkdir(parents=True,exist_ok=True)
    report={"status":"not_run","checks":[],"errors":[],"limitations":[],"screenshots":[],"headed":headed}
    server=None
    step="Browser launch"
    def passed(name): report["checks"].append(name)
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser=None; launch_errors=[]
            for channel in ("msedge","chrome",None):
                try:
                    browser=p.chromium.launch(headless=not headed,**({"channel":channel} if channel else {}))
                    report["browser"]=channel or "chromium"; break
                except Exception as exc: launch_errors.append(str(exc).splitlines()[0])
            if browser is None:
                report["status"]="unavailable"; report["limitations"]=launch_errors
            else:
                context=browser.new_context(viewport={"width":1440,"height":960},device_scale_factor=1,accept_downloads=True)
                page=context.new_page(); page.on("pageerror",lambda err:report["errors"].append(str(err)))
                requests=[]; page.on("request",lambda req:requests.append(req.url))
                if not headed: context.route("https://**/*",lambda route:route.abort())
                server=ThreadingHTTPServer(("127.0.0.1",0),partial(QuietHandler,directory=str(root/"output/maps")))
                threading.Thread(target=server.serve_forever,daemon=True).start()
                url=f"http://127.0.0.1:{server.server_port}/MAPC_access_map.html"
                step="Map initialization"
                page.goto(url,wait_until="load",timeout=120000)
                page.wait_for_function("window.mapReady===true",timeout=90000)
                def ev(script,arg=None): return page.evaluate(script,arg)
                def shot(name):
                    # Capture settled views, including raster tiles for the current viewport.
                    page.wait_for_timeout(180)
                    page.wait_for_function("!map.hasLayer(streetLayer)||!streetLayer.isLoading()",timeout=20000)
                    path=shots/f"{name}.png"; page.screenshot(path=str(path),full_page=False)
                    report["screenshots"].append(path.relative_to(root).as_posix())
                counts=ev("mapCounts")
                assert counts=={"total":expected["marker_count"],"validated":expected["validated_marker_count"],"unvalidated":expected["unvalidated_marker_count"]},counts
                assert ev("map.hasLayer(mapLayers['Field-validated assets']) && !map.hasLayer(mapLayers['Unvalidated / unfinished assets'])")
                assert page.locator("header").count()==0
                rect=page.locator("#map").bounding_box()
                assert abs(rect["x"])<.5 and abs(rect["y"])<.5 and abs(rect["width"]-1440)<.5 and abs(rect["height"]-960)<.5,rect
                passed("Map initializes with expected marker/default-layer counts, no banner and full viewport")
                ev("() => {window.qaOriginal=JSON.stringify(managementUI.records);window.qaHome={center:map.getCenter(),zoom:map.getZoom()};}")
                records=ev("managementUI.records"); summary=ev("managementUI.summary"); sites=ev("managementUI.sites")
                assets=pd.read_csv(root/"output/data/assets_clean.csv",keep_default_na=False,dtype=str)
                accepted=assets[assets.record_status.eq("accepted")]
                source_sites=pd.read_csv(root/"output/data/sites_summary.csv",keep_default_na=False,dtype=str).set_index("site_id")
                assert len(records)==len(accepted)==summary["total_accepted"]
                assert summary["field_validated"]==int(accepted.field_validated.str.lower().eq("true").sum())
                assert summary["staff_reviewed"]==int(accepted.staff_reviewed.str.lower().eq("true").sum())
                for site in sites:
                    for field in ("asset_count","validated_asset_count","staff_reviewed_asset_count","coordinate_usable_asset_count"):
                        assert site[field]==int(source_sites.loc[site["site_id"],field]),(site["site_id"],field)
                for field in ("total_accepted","field_validated","staff_reviewed","missing_coordinates"):
                    assert int(page.locator(f'[data-count="{field}"] strong').inner_text())==summary[field]
                missing=[r for r in records if "missing_coordinates" in r["issue_categories"]]
                omissions=pd.read_csv(root/"output/data/map_omissions.csv",keep_default_na=False)
                assert {r["source_record_key"] for r in missing}==set(omissions.source_record_key)
                assert len(missing)==expected["omitted_count"]==summary["missing_coordinates"]
                passed("Summary, every site's counts and missing-coordinate list reconcile to saved datasets")
                if headed:
                    step="Online basemap"
                    page.wait_for_function("tileStats.loaded>0",timeout=45000)
                    report["basemap"]=ev("tileStats"); assert any("tile.openstreetmap.org/" in u for u in requests)
                    passed("Bright OpenStreetMap street tiles load during headed browser viewing")
                else: report["limitations"].append("Headless tests deliberately block public street tiles; use the headed check for online QA.")
                shot("01_regional_management")
                page.screenshot(path=str(out/"map_smoke_test.png"),full_page=False)
                ev("() => {map.setView([42.365,-71.095],12.25,{animate:false});}")
                page.wait_for_timeout(500); shot("02_boston_cambridge")
                step="Fractional zoom and home"
                zooms=ev("() => {const old=map.options.zoomSnap;map.options.zoomSnap=.1;map.setZoom(10.1,{animate:false});const tenth=map.getZoom();map.options.zoomSnap=.25;map.setZoom(10.25,{animate:false});const quarter=map.getZoom();map.options.zoomSnap=old;return {tenth,quarter,snap:old,delta:map.options.zoomDelta,wheel:map.options.wheelPxPerZoomLevel,debounce:map.options.wheelDebounceTime};}")
                assert abs(zooms["tenth"]-10.1)<.001 and abs(zooms["quarter"]-10.25)<.001 and zooms["snap"]==.25
                report["fractional_zoom"]=zooms
                page.locator("#home-button").click()
                home=ev("({pixelDistance:map.project(map.getCenter()).distanceTo(map.project(qaHome.center)),zoom:map.getZoom(),initialZoom:qaHome.zoom})")
                # Leaflet rounds pixel origins; a sub-pixel offset is the same view.
                assert home["pixelDistance"]<=1 and abs(home["zoom"]-home["initialZoom"])<.001,home
                radii=ev("Array.from(document.querySelectorAll('#size-legend .sizeitem')).map(e=>({r:Number(e.dataset.radius),width:e.querySelector('b').getBoundingClientRect().width,height:e.querySelector('b').getBoundingClientRect().height}))")
                assert all(abs(v["width"]-v["r"]*2)<.01 and abs(v["height"]-v["r"]*2)<.01 for v in radii),radii
                passed("Both fractional zoom candidates work; 0.25 retains 10.25; Home restores actual extent; legend circles match radii")
                step="Inventory hover and drawer"
                if counts["total"]:
                    ev("() => {window.qaMarker=assetMarkers.find(m=>map.hasLayer(m));qaMarker.fire('mouseover');qaMarker.openTooltip();}")
                    tip=page.locator(".leaflet-tooltip").text_content()
                    assert "Activities" in tip and "Recorded attributes / features" in tip
                    shot("03_inventory_hover")
                    ev("() => {qaMarker.fire('mouseout');qaMarker.closeTooltip();qaMarker.fire('click');}")
                    page.locator("#details-drawer").wait_for(state="visible")
                    body=page.locator("#drawer-body").text_content()
                    assert "Staff review" in body and "Source value" in body and "Audited / final value" in body and "Recorded inventory" in body
                    shot("04_validated_details")
                    ev("() => {managementUI.closeRecord();}")
                unfinished=next((r for r in records if not r["field_validated"] and r["coordinate_usable"]),None)
                if unfinished:
                    ev("key=>{managementUI.selectRecord(key);}",unfinished["key"]); shot("05_unfinished_details")
                evidence=next((r for r in records if "access_conflict" in r["issue_categories"]),records[0] if records else None)
                if evidence:
                    ev("key=>{managementUI.selectRecord(key);}",evidence["key"])
                    for item in evidence["access_evidence"]:
                        card=page.locator(f'[data-access-field="{item["field"]}"]')
                        assert card.locator('[data-value="source"]').inner_text()==str(item["original_value"] or "Unknown")
                        assert card.locator('[data-value="audited"]').inner_text()==str(item["audited_value"] or "Unknown")
                    evidence_card=page.locator(".evidence-card.conflict").first if page.locator(".evidence-card.conflict").count() else page.locator(".evidence-card").first
                    evidence_card.locator("summary").click()
                    evidence_card.scroll_into_view_if_needed()
                    shot("06_access_evidence")
                passed("Marker click opens management drawer; complete hover, workflow and independent source/audited evidence work")
                ev("() => {managementUI.closeRecord();}")
                overlapping=ev("() => {const m=assetMarkers.find(a=>assetMarkers.some(b=>b!==a&&a.getLatLng().distanceTo(b.getLatLng())<1));return m?m.recordKey:null;}")
                if overlapping:
                    ev("key=>{managementUI.selectRecord(key);}",overlapping)
                    choices=page.locator("[data-colocated]"); assert choices.count()>1
                    next_key=choices.nth(1).get_attribute("data-colocated")
                    choices.nth(1).click(); assert ev("managementUI.state.selected")==next_key
                    page.locator("#radius-toggle").check()
                    assert ev("Math.abs(managementUI.verificationLayer.getLayers()[0].getRadius()-804.672)<.001")
                    passed("Coincident assets can be selected individually; optional radius is the straight-line half-mile threshold")
                    page.locator("#drawer-close").click()
                page.locator("#mode-transport").click()
                assert ev("assetMarkers.every(m=>m.options.fillColor===m.data.color)")
                shot("07_transportation_profile")
                page.locator("#mode-management").click(); assert ev("managementUI.state.mode==='management'")
                passed("Both view buttons work and transportation colors remain faithful to audited profiles")
                step="Custom layers and queue"
                page.locator("#layers-button").click()
                names=ev("Object.keys(mapLayers)")
                for name in names:
                    if name=="Field-validated assets": continue
                    checkbox=page.locator(f'#layer-options input[data-layer="{name}"]')
                    checkbox.check(); assert ev("n=>map.hasLayer(mapLayers[n])",name)
                    checkbox.uncheck(); assert not ev("n=>map.hasLayer(mapLayers[n])",name)
                page.locator("#layers-close").click()
                passed("Every custom GIS/transit/unfinished layer checkbox toggles its actual Leaflet layer")
                for issue,count in summary["issue_counts"].items():
                    option=page.locator(f'#issue-select option[value="{issue}"]')
                    if option.is_disabled(): continue
                    page.locator("#issue-select").select_option(issue)
                    assert ev("managementUI.state.queue.length")==count,issue
                    assert page.locator("#queue-list .record-row").count()==count
                page.locator("#issue-select").select_option("source_warning"); shot("08_issue_queue")
                page.locator("#issue-select").select_option("missing_coordinates"); shot("09_missing_coordinates")
                if missing:
                    page.locator("#queue-list .record-row").first.click()
                    assert "Not shown on the map" in page.locator("#drawer-body").inner_text()
                    assert ev("key=>!managementUI.markerLookup.has(key)",missing[0]["key"])
                    shot("10_unmapped_details"); page.locator("#drawer-close").click()
                    with page.expect_download() as download_info: page.locator("#queue-export").click()
                    download=download_info.value; path=out/"management_queue_QA.csv"; download.save_as(path)
                    exported=pd.read_csv(path,skiprows=1,keep_default_na=False)
                    assert len(exported)==len(missing) and set(exported.source_record_key)==set(omissions.source_record_key)
                passed("Issue queues reconcile, missing-location records open without invented markers, and QC CSV export matches queue")
                page.locator("#issue-select").select_option("field_incomplete")
                page.locator("#layers-button").click()
                unfinished_box=page.locator('#layer-options input[data-layer="Unvalidated / unfinished assets"]')
                unfinished_box.check(); page.locator("#layers-close").click()
                page.locator("#issue-select").select_option("all")
                assert ev("assetMarkers.every(m=>map.hasLayer(m))"),"Clearing a temporary queue hid a checked base-layer marker"
                passed("Clearing a queue preserves markers belonging to a checked validation layer")
                if records:
                    lookup=records[0]["site_name"]
                    page.locator("#record-search").fill(lookup)
                    expected_lookup=sum(lookup.lower() in ' '.join(str(r.get(k) or '') for k in ('site_name','asset_name','municipality')).lower() for r in records)
                    assert ev("managementUI.state.queue.length")==expected_lookup
                    page.locator("#record-search").fill("")
                    passed("Operational identity lookup filters the queue without changing inventory values")
                page.locator("#about-button").click(); assert page.get_by_role("dialog").is_visible()
                assert "0.5 mile" in page.locator("#dialog-body").inner_text(); page.keyboard.press("Escape")
                page.locator("#snapshot-button").click(); assert "SHA" in page.locator("#dialog-body").inner_text(); page.keyboard.press("Escape")
                assert ev("JSON.stringify(managementUI.records)===qaOriginal")
                assert not any("apple.com" in u or "apple-map" in u for u in requests)
                passed("About/snapshot dialogs work; interactions preserve all record values; no Apple resources are requested")
                step="Mobile and offline"
                page.set_viewport_size({"width":390,"height":844}); page.wait_for_timeout(400)
                assert ev("document.documentElement.scrollWidth<=innerWidth")
                shot("11_mobile_management")
                if missing:
                    ev("key=>{managementUI.selectRecord(key);}",missing[0]["key"]); shot("12_mobile_details")
                context.route("https://**/*",lambda route:route.abort())
                page.goto((root/"output/maps/MAPC_access_map.html").as_uri(),wait_until="load",timeout=90000)
                page.wait_for_function("window.mapReady===true")
                assert ev("mapCounts.total")==expected["marker_count"]
                assert ev("map.hasLayer(offlineLayer)&&!map.hasLayer(streetLayer)")
                shot("13_offline_mobile")
                page.screenshot(path=str(out/"map_offline_test.png"),full_page=False)
                passed("Responsive mobile layout, details sheet and standalone offline map initialize correctly")
                assert not report["errors"],report["errors"]
                passed("No fatal JavaScript errors across desktop, mobile and offline interactions")
                report["status"]="passed"; browser.close()
    except ImportError as exc:
        report["status"]="unavailable"; report["limitations"].append(str(exc))
    except Exception as exc:
        report["status"]="failed"; report["errors"].append(f"{step}: {type(exc).__name__}: {exc}")
    finally:
        if server: server.shutdown(); server.server_close()
    write_json(out/f"{report_name}.json",report)
    (out/f"{report_name}.txt").write_text("MAP SMOKE TEST: "+report["status"].upper()+"\n\n"+"\n".join("PASS: "+s for s in report["checks"])+"\n\n"+"\n".join("LIMITATION: "+s for s in report["limitations"])+"\n"+"\n".join("ERROR: "+s for s in report["errors"]),encoding="utf-8")
    return report


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument("--headed",action="store_true"); args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    expected=json.loads((root/"output/reports/map_management_generation.json").read_text())
    result=run_map_smoke_test(root,expected,headed=args.headed,report_name="map_management_test_results")
    print(json.dumps(result,indent=2))
    raise SystemExit(0 if result["status"]=="passed" else 1)
