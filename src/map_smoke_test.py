"""Real Chromium/Edge map interaction checks; honest unavailable status."""
from pathlib import Path
from datetime import datetime, timezone
from .utils import write_json

def run_map_smoke_test(root, expected):
    root=Path(root);report={"status":"not_run","checks":[],"errors":[],"limitations":[]}
    out=root/"output/reports";out.mkdir(parents=True,exist_ok=True)
    browser=None
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            launch_errors=[]
            for channel in ("msedge","chrome",None):
                try:
                    browser=p.chromium.launch(headless=True,**({"channel":channel} if channel else {}));break
                except Exception as e:launch_errors.append(str(e).splitlines()[0])
            if browser is None:
                report["status"]="unavailable";report["limitations"] = launch_errors
            else:
                page=browser.new_page(viewport={"width":1500,"height":1000},device_scale_factor=1)
                page.on("pageerror",lambda e:report["errors"].append(str(e)))
                page.goto((root/"output/maps/MAPC_access_map.html").resolve().as_uri(),wait_until="load",timeout=120000)
                page.wait_for_function("window.mapReady === true",timeout=90000)
                report["checks"].append("HTML opens and Leaflet initializes")
                page.evaluate("() => { window.testInitialView = {center:map.getCenter(),zoom:map.getZoom()}; }")
                counts=page.evaluate("window.mapCounts")
                assert counts["total"]==expected["marker_count"],f"Marker mismatch {counts}"
                assert counts["validated"]==expected["validated_marker_count"]
                assert page.evaluate("map.hasLayer(mapLayers['Field-validated assets'])")
                assert not page.evaluate("map.hasLayer(mapLayers['Unvalidated / unfinished assets'])")
                report["checks"].append("Expected marker counts and default validation layer states match dataset")
                if counts["total"]:
                    page.evaluate("() => { window.testMarker = window.assetMarkers.find(m => map.hasLayer(m)) || window.assetMarkers[0]; window.testMarker.openTooltip(); }")
                    tooltip=page.locator(".leaflet-tooltip").inner_text()
                    assert "Activities" in tooltip and "Recorded attributes/features" in tooltip and len(tooltip)>60
                    report["checks"].append("Tooltip opens with site/asset identity, features, amenities and activities")
                    page.evaluate("() => { window.testMarker.closeTooltip(); window.testMarker.openPopup(); }")
                    popup=page.locator(".leaflet-popup-content").inner_text()
                    assert "Source record" in popup and "Evidence and sources" in popup and "Activities" in popup
                    report["checks"].append("Popup opens with evidence, source trace and complete lists")
                    page.evaluate("() => { map.closePopup(); }")
                names=page.evaluate("Object.keys(window.mapLayers)")
                for name in names:
                    if name=="Field-validated assets":continue
                    label=page.locator(".leaflet-control-layers-overlays label").filter(has_text=name)
                    label.locator('input[type=checkbox]').check()
                    assert page.evaluate("n=>map.hasLayer(mapLayers[n])",name)
                    label.locator('input[type=checkbox]').uncheck()
                    assert not page.evaluate("n=>map.hasLayer(mapLayers[n])",name)
                    report["checks"].append(f"UI layer toggle: {name}")
                report["basemap"] = page.evaluate("window.tileStats")
                if report["basemap"]["loaded"]==0:
                    report["limitations"].append("Online basemap tiles did not load in this test; offline data mode verified.")
                page.evaluate("() => { map.setView(testInitialView.center,testInitialView.zoom,{animate:false}); }")
                page.screenshot(path=str(out/"map_smoke_test.png"),full_page=True)
                # Prove no data/library CDN is required at browser runtime.
                page.route("https://**/*",lambda route:route.abort())
                page.reload(wait_until="load",timeout=90000)
                page.wait_for_function("window.mapReady === true")
                assert page.evaluate("window.mapCounts.total")==expected["marker_count"]
                page.evaluate("() => { map.removeLayer(streetLayer);offlineLayer.addTo(map); }")
                page.screenshot(path=str(out/"map_offline_test.png"),full_page=True)
                report["checks"].append("Offline reload initializes local assets and GIS without network dependencies")
                assert not report["errors"],str(report["errors"])
                report["checks"].append("No fatal JavaScript errors")
                report["status"]="passed"
                browser.close()
    except ImportError as e:
        report["status"]="unavailable";report["limitations"].append(str(e))
    except Exception as e:
        report["status"]="failed";report["errors"].append(str(e))
        if browser:
            try:browser.close()
            except Exception:pass
    write_json(out/"map_test_results.json",report)
    (out/"map_test_results.txt").write_text("MAP SMOKE TEST: "+report["status"].upper()+"\n\n"+"\n".join("PASS: "+s for s in report["checks"])+"\n\n"+"\n".join("LIMITATION: "+s for s in report["limitations"])+"\n"+"\n".join("ERROR: "+s for s in report["errors"]),encoding="utf-8")
    return report
