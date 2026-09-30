"""Local Leaflet map: inline data, vendored library, external tiles optional."""
from pathlib import Path
import bisect
import html
import json
import math
import pandas as pd
from . import __version__
from .utils import write_csv

PROFILES = ["Transit + free parking", "Transit only", "Free parking only", "Neither", "Unknown / unresolved"]

def marker_radius(count, config):
    m=config["map"]
    return m["size_radii"][max(0,bisect.bisect_right(m["size_thresholds"],float(count or 0))-1)]

def safe(value):
    if value is None: return "Unknown"
    if not isinstance(value,(list,dict)) and pd.isna(value): return "Unknown"
    return html.escape(str(value))

def list_html(values):
    if not isinstance(values,list) or not values: return "None recorded"
    return ", ".join(safe(x) for x in values)

def field(r,name):
    return r.get(name+"_audited_value",r.get(name,"UNKNOWN"))

def marker_content(r):
    ident=f'<strong>{safe(r.get("site_name"))}</strong><br>{safe(r.get("asset_name"))}<br>{safe(r.get("municipality"))}'
    lists=f'<p><b>Recorded attributes/features ({r.get("attribute_count",0)}):</b> {list_html(r.get("attribute_list"))}</p><p><b>Classified amenities ({r.get("amenity_count",0)}):</b> {list_html(r.get("amenity_list"))}</p><p><b>Activities ({r.get("activity_count",0)}):</b> {list_html(r.get("activity_list"))}</p>'
    tooltip=ident+lists
    details=[("Subregion",r.get("subregion")),("Field validated",r.get("field_validated")),("Staff reviewed",r.get("staff_reviewed")),("Transportation profile",r.get("transportation_access_profile")),("Near public transit (audited)",field(r,"near_public_transit")),("Transit within 0.5 mile (calculated)",r.get("near_public_transit_calculated","UNKNOWN")),("Nearest transit stop",r.get("nearest_transit_stop")),("Transit mode",r.get("nearest_transit_mode")),("Transit distance (miles)",r.get("nearest_transit_distance_miles")),("Free entry / parking",field(r,"free_entry_parking")),("Accessible parking",field(r,"accessible_parking")),("Accessible restroom",field(r,"accessible_restroom")),("Wheelchair / stroller friendly trail",field(r,"wheelchair_stroller_friendly_trail")),("Restrooms available",field(r,"restrooms_available")),("Nearest bike facility",r.get("nearest_bike_facility_name")),("Bike distance (miles)",r.get("nearest_bike_facility_distance_miles")),("Nearest shared-use path",r.get("nearest_shared_use_path_name")),("Path distance (miles)",r.get("nearest_shared_use_path_distance_miles")),("Source record",r.get("source_record_key")),("CSV record",r.get("source_row_number"))]
    table=''.join(f'<tr><th>{safe(k)}</th><td>{safe(round(v,3) if isinstance(v,float) and math.isfinite(v) else v)}</td></tr>' for k,v in details)
    evidence=''.join(f'<p><b>{safe(k.replace("_"," "))}:</b> {safe(v)}</p>' for k,v in r.items() if k.endswith(("_verification_status","_evidence","_source")) and v is not None and str(v).strip() and str(v)!="nan")
    return tooltip, ident+lists+f'<table>{table}</table><details><summary>Evidence and sources</summary>{evidence}</details>'

def make_map(assets, layers, transit, root, config, run_timestamp=""):
    root=Path(root); dest=root/"output/maps";dest.mkdir(parents=True,exist_ok=True)
    accepted=assets[assets["record_status"].eq("accepted")] if "record_status" in assets else assets
    markers=[];omitted=[];map_rows=[]
    for _,r in accepted.iterrows():
        if pd.isna(r.get("latitude")) or pd.isna(r.get("longitude")) or ("coordinate_usable" in r and not r.get("coordinate_usable")):
            omitted.append({"source_record_key":r.get("source_record_key"),"reason":str(r.get("coordinate_status"))});continue
        tip,popup=marker_content(r)
        valid=r.get("field_validated") is True or r.get("field_validated")==True
        profile=r.get("transportation_access_profile","Unknown / unresolved")
        markers.append(dict(lat=float(r.latitude),lon=float(r.longitude),validated=bool(valid),radius=marker_radius(r.get(config["map"]["size_metric"],0),config),color=config["map"]["colors"].get(profile,"#B7BEC7"),tooltip=tip,popup=popup,key=str(r.get("source_record_key"))))
        map_rows.append(r.to_dict())
    write_csv(pd.DataFrame(map_rows),root/"output/data/map_dataset.csv")
    write_csv(pd.DataFrame(omitted,columns=["source_record_key","reason"]),root/"output/data/map_omissions.csv")
    network_data={}
    for key in ("bicycle_facilities","shared_use_paths","walking_trails"):
        p=root/f"output/gis/{key}_web.geojson"
        network_data[key]=json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"type":"FeatureCollection","features":[]}
    stops=[]; routes={"type":"FeatureCollection","features":[]}
    if transit:
        st=transit.get("stops")
        if st is not None and len(st):
            for _,r in st.iterrows():
                lat=r.get("stop_lat",r.get("latitude"));lon=r.get("stop_lon",r.get("longitude"))
                if lat is None and hasattr(r.get("geometry"),"y"): lat=r.geometry.y;lon=r.geometry.x
                if lat is not None and lon is not None and not pd.isna(lat) and not pd.isna(lon):
                    stops.append([float(lat),float(lon),str(r.get("stop_name","MBTA stop")),str(r.get("mode",r.get("modes","MBTA")))])
        rt=transit.get("routes")
        if rt is not None and hasattr(rt,"geometry") and len(rt):
            routes=json.loads(rt.to_crs(4326).to_json(drop_id=True))
    vendor=root/"src/vendor"; js=(vendor/"leaflet.js").read_text(encoding="utf-8");css=(vendor/"leaflet.css").read_text(encoding="utf-8")
    metric_label="Number of recorded MAPC attributes/features" if config["map"]["size_metric"]=="attribute_count" else "Number of classified physical amenities"
    colors=''.join(f'<div><i style="background:{config["map"]["colors"][p]}"></i>{p}</div>' for p in PROFILES)
    sizelegend=''
    thresholds=config["map"]["size_thresholds"]
    for i,(t,r) in enumerate(zip(thresholds,config["map"]["size_radii"])):
        label=f'{t}–{thresholds[i+1]-1}' if i<len(thresholds)-1 else f'{t}+'
        sizelegend+=f'<span class="sizeitem"><b style="width:{r*2}px;height:{r*2}px"></b>{label}</span>'
    payload=json.dumps({"markers":markers,"networks":network_data,"stops":stops,"routes":routes},ensure_ascii=False).replace("</","<\\/")
    page='''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>MAPC Recreation Access</title><style>'''+css+'''\nhtml,body{height:100%;margin:0;font-family:Arial,sans-serif;color:#173344}*{box-sizing:border-box}header{height:76px;padding:14px 24px;background:#153b50;color:white}h1{font-size:23px;margin:0 0 5px}header p{font-size:13px;margin:0}#map{height:calc(100% - 76px);background:#e9eff1}.legend{position:absolute;bottom:28px;left:12px;z-index:900;background:white;padding:14px 17px;border-radius:6px;box-shadow:0 2px 14px #0003;width:318px;font-size:12px;line-height:1.5}.legend h2{font-size:14px;margin:0 0 6px}.legend i{display:inline-block;width:13px;height:13px;border:1px solid #334;margin-right:8px;border-radius:50%;vertical-align:middle}.sizes{display:flex;gap:14px;align-items:flex-end;margin:7px 0}.sizeitem{display:flex;flex-direction:column;align-items:center;min-width:28px}.sizeitem b{background:#7195a7;border:1px solid #345;border-radius:50%;display:block}.details-panel{position:absolute;top:87px;left:12px;z-index:950;max-width:365px;background:white;padding:11px 14px;border-radius:6px;box-shadow:0 2px 12px #0003;font-size:12px;max-height:45vh;overflow:auto}.details-panel summary{cursor:pointer;font-weight:bold}.details-panel p{line-height:1.5}.asset-tip{max-width:360px;white-space:normal;max-height:60vh;overflow:auto;line-height:1.45}.leaflet-popup-content{line-height:1.45;max-height:62vh;overflow:auto;margin:16px}.leaflet-popup-content table{border-collapse:collapse;width:100%;font-size:11px}.leaflet-popup-content th,.leaflet-popup-content td{text-align:left;vertical-align:top;border-bottom:1px solid #ddd;padding:5px}.leaflet-popup-content th{width:45%}.leaflet-control-layers{max-height:60vh;overflow:auto}.city-label{font-size:10px;color:#536876;white-space:nowrap;font-weight:bold;pointer-events:none;text-shadow:0 0 3px white}#tile-status{font-size:11px;color:#715023}#fatal{display:none;background:#ffe2ce;padding:12px} @media(max-width:650px){.legend{width:240px;font-size:10px}.details-panel{max-width:230px}header{padding-left:14px}h1{font-size:19px}.leaflet-control-layers{max-width:180px}} @media print{header{height:75px;print-color-adjust:exact}#map{height:850px}.legend{bottom:25px;print-color-adjust:exact}.leaflet-control-zoom,.details-panel,.leaflet-control-layers{display:none}.leaflet-container{print-color-adjust:exact}}</style></head><body><header><h1>MAPC Recreation Access</h1><p>Recorded features, recreation activities, and transportation proximity · WPI / MAPC</p></header><div id="fatal"></div><div id="map"></div><aside class="details-panel"><details><summary>About this map &amp; methods</summary><p><b>Data:</b> Current MAPC asset export and supplied official MAPC line packages. MBTA stops/routes use the cached official GTFS snapshot when available.</p><p><b>Attributes vs amenities:</b> Attributes include accessibility, transport, policies and site characteristics. Amenities are only the physical_amenity taxonomy subset. Activities are all recorded source activities. Missing tags are Unknown.</p><p><b>Transportation profile:</b> Final reconciled transit and free entry/parking values; unresolved evidence remains Unknown. An absent tag alone is never No. Prior audits are reference material.</p><p><b>Validation:</b> Explicit finished values are on by default. Unfinished or unknown records use dashed outlines when enabled. Staff review is a separate field.</p><p><b>Distances:</b> Straight-line proximity to transit stops and full-resolution network lines; no routing or guarantee of a usable entrance or accessible pedestrian path. Near transit means at most 0.5 mile.</p><p><b>GIS:</b> Only verified existing infrastructure and eligible public walking trails enter access layers. Exclusions remain in the GeoPackage. Web lines are simplified in the projected CRS; analytical geometry is never simplified.</p><p><b>Limitations:</b> Recorded attributes reflect collection completeness. Assets within a site are clustered. This map shows evidence and proximity, not a universal accessibility rating. Offline mode preserves assets and local GIS layers. Online tiles may be unavailable.</p><p>Version '''+__version__+''' · '''+safe(run_timestamp)+'''</p><p>Credits: MAPC recreation inventory, Bicycle Facilities, Shared Use Paths, Walking Trails; MBTA / MassDOT GTFS; Esri World Street Map (Esri and contributors). Leaflet © Vladimir Agafonkin and contributors, BSD-2-Clause.</p></details></aside><aside class="legend"><h2>Transportation access</h2>'''+colors+'''<h2 style="margin-top:9px">Marker size</h2><div>'''+metric_label+'''</div><div class="sizes">'''+sizelegend+'''</div><div><b>Near public transit</b> = an MBTA stop or station within <b>0.5 mile</b> of the asset.</div><div style="margin-top:6px">Solid = field validated; dashed = unfinished/unknown. Bike and trail networks are separate switchable line layers.</div><div id="tile-status">Local assets and GIS work without online tiles.</div></aside><script>'''+js+'''</script><script>
const DATA='''+payload+''';
try {
const map=L.map('map',{preferCanvas:true,zoomControl:true}).setView([42.30,-71.25],10); window.map=map;
document.querySelector('.details-panel').style.left='58px';
map.attributionControl.addAttribution('MAPC recreation inventory and network data; MBTA/MassDOT GTFS');
const offline=L.layerGroup();const street=L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}',{attribution:'Tiles © Esri, Esri contributors',maxZoom:19});
window.tileStats={loaded:0,errors:0};street.on('tileload',()=>{window.tileStats.loaded++;document.getElementById('tile-status').textContent='Online basemap loaded. Local data are independent of tiles.'});street.on('tileerror',()=>{window.tileStats.errors++;document.getElementById('tile-status').textContent='Some basemap tiles unavailable. Local asset and network layers remain usable.'});
'''+('street.addTo(map);' if config["map"].get("online_basemap",True) else 'offline.addTo(map);')+'''
const validated=L.featureGroup().addTo(map),unvalidated=L.featureGroup();
window.assetMarkers=[];DATA.markers.forEach(d=>{const m=L.circleMarker([d.lat,d.lon],{radius:d.radius,color:d.validated?'#233d4b':'#57616a',weight:d.validated?1.3:2,dashArray:d.validated?null:'3 3',fillColor:d.color,fillOpacity:d.validated?.88:.42}).bindTooltip(d.tooltip,{className:'asset-tip',sticky:true,direction:'top'}).bindPopup(d.popup,{maxWidth:440,minWidth:310});m.addTo(d.validated?validated:unvalidated);window.assetMarkers.push(m)});
const networkStyles={bicycle_facilities:{color:'#276871',weight:2},shared_use_paths:{color:'#8b650e',weight:3},walking_trails:{color:'#71764f',weight:1.4}};
const names={bicycle_facilities:'Existing Bicycle Facilities',shared_use_paths:'Existing Shared Use Paths',walking_trails:'Public Walking Trails'};
const textLabel=s=>{const el=document.createElement('span');el.textContent=String(s);return el;};
const overlays={'Field-validated assets':validated,'Unvalidated / unfinished assets':unvalidated};
Object.keys(names).forEach(k=>{overlays[names[k]]=L.geoJSON(DATA.networks[k],{style:networkStyles[k],onEachFeature:(f,l)=>{const p=f.properties||{};let name=p.feature_name||p.local_name||p.prop_name||p.reg_name||p.name||'MAPC network segment';l.bindTooltip(textLabel(name));}})});
L.geoJSON(DATA.networks.shared_use_paths,{style:{color:'#b8c9cc',weight:1,opacity:.65},interactive:false}).addTo(offline);
if(DATA.stops.length){const stops=L.layerGroup();DATA.stops.forEach(s=>L.circleMarker([s[0],s[1]],{radius:2,color:'#65548a',weight:.8,fillOpacity:.55}).bindTooltip(textLabel(s[2]+' · '+s[3])).addTo(stops));overlays['Transit Stops / Stations']=stops;}
if(DATA.routes.features.length){const groups={'Rapid Transit':L.layerGroup(),'Commuter Rail':L.layerGroup(),'Bus Routes':L.layerGroup(),'Ferry':L.layerGroup()};DATA.routes.features.forEach(f=>{let p=f.properties||{},t=String(p.route_type??''),mode=String(p.mode||'').toLowerCase(),g=t==='2'||mode.includes('commuter')?'Commuter Rail':t==='3'||mode.includes('bus')?'Bus Routes':t==='4'||mode.includes('ferry')?'Ferry':'Rapid Transit';L.geoJSON(f,{style:{color:g==='Bus Routes'?'#888':g==='Commuter Rail'?'#80276c':'#446c8d',weight:g==='Bus Routes'?1:2,opacity:.55}}).addTo(groups[g]);});Object.assign(overlays,groups);}
L.control.layers({'Street basemap (online)':street,'Local data (offline)':offline},overlays,{collapsed:false}).addTo(map);L.control.scale({imperial:true,metric:true}).addTo(map);
const bounds=validated.getBounds();if(bounds.isValid())map.fitBounds(bounds.pad(.12));
window.mapLayers=overlays;window.mapReady=true;window.mapCounts={validated:validated.getLayers().length,unvalidated:unvalidated.getLayers().length,total:DATA.markers.length};window.offlineLayer=offline;window.streetLayer=street;
}catch(e){document.getElementById('fatal').style.display='block';document.getElementById('fatal').textContent='Map initialization failed: '+e.message;window.mapError=e.message;throw e;}
</script></body></html>'''
    (dest/"MAPC_access_map.html").write_text(page,encoding="utf-8")
    return {"marker_count":len(markers),"validated_marker_count":sum(m["validated"] for m in markers),"unvalidated_marker_count":sum(not m["validated"] for m in markers),"omitted_count":len(omitted),"omissions":omitted,"size_metric":config["map"]["size_metric"],"network_feature_counts":{k:len(v["features"]) for k,v in network_data.items()},"transit_stops":len(stops),"transit_routes":len(routes["features"])}
