"""Reconciled quality report from generated datasets and measured test results."""
import html
import json
from pathlib import Path
import pandas as pd
from .utils import html_page, write_json, json_default
from .reconcile_access_fields import ACCESS_TAGS

def counts(series):
    return {str(k):int(v) for k,v in series.fillna("Unknown").value_counts(dropna=False).sort_index(key=lambda x:x.astype(str)).items()}

def build_qc(assets,sites,schema,gis,transit,map_report,test_report,root,warnings=None,errors=None):
    eligible=assets[assets.record_status.eq("accepted")]
    qc={"source_rows":len(assets),"parsed_rows":len(assets),"accepted_rows":len(eligible),"quarantined_rows":int(assets.record_status.eq("quarantined").sum()),"unique_assets":int(eligible.asset_id.nunique()),"unique_sites":int(eligible.site_id.nunique()),"duplicate_status":counts(assets.duplicate_status),"coordinate_status":counts(assets.coordinate_status),"validation":{"field_validated":counts(eligible.field_validated),"staff_reviewed":counts(eligible.staff_reviewed)},"attributes":{"unique":len(set(x for a in eligible.attribute_list for x in a)),"distribution":counts(eligible.attribute_count)},"amenities":{"unique":len(set(x for a in eligible.amenity_list for x in a)),"distribution":counts(eligible.amenity_count)},"activities":{"unique":len(set(x for a in eligible.activity_list for x in a)),"distribution":counts(eligible.activity_count)},"access":{},"transit":transit,"gis":gis,"map":map_report,"tests":test_report,"warnings":warnings or [],"errors":errors or []}
    for f in ACCESS_TAGS:
        qc["access"][f]={"states":counts(eligible[f+"_audited_value"]),"verification":counts(eligible[f+"_verification_status"])}
    qc["transit_calculated_records"]=int(eligible.get("near_public_transit_calculated",pd.Series(dtype=str)).isin(["YES","NO"]).sum())
    qc["transit_unavailable_records"]=len(eligible)-qc["transit_calculated_records"]
    assertions={"all_source_rows_accounted_for":len(assets)==schema["source_row_count"],"accepted_plus_quarantined_equals_source":len(eligible)+qc["quarantined_rows"]==len(assets),"unique_accepted_identities":eligible.asset_id.is_unique,"site_summary_matches_unique_sites":len(sites)==eligible.site_id.nunique(),"map_counts_reconcile":map_report["marker_count"]+map_report["omitted_count"]==len(eligible),"map_validation_counts_reconcile":map_report["validated_marker_count"]+map_report["unvalidated_marker_count"]==map_report["marker_count"],"attribute_counts_match_lists":all(len(x)==n for x,n in zip(assets.attribute_list,assets.attribute_count)),"activity_counts_match_lists":all(len(x)==n for x,n in zip(assets.activity_list,assets.activity_count)),"amenity_counts_match_lists":all(len(x)==n for x,n in zip(assets.amenity_list,assets.amenity_count))}
    qc["reconciliation_checks"]=assertions
    write_json(Path(root)/"output/reports/QC_summary.json",qc)
    headline=f'<p><b>{len(eligible):,}</b> accepted assets · <b>{len(sites):,}</b> sites · <b>{qc["quarantined_rows"]}</b> quarantined source records · <b>{map_report["validated_marker_count"]}</b> validated map markers</p>'
    links='<p><a href="../maps/MAPC_access_map.html">Interactive map</a> · <a href="../analysis/analysis_workbook.xlsx">Analysis workbook</a> · <a href="schema_report.html">Schema report</a> · <a href="run_manifest.json">Run manifest</a> · <a href="map_test_results.txt">Browser test results</a> · <a href="../analysis/findings.md">Findings</a></p>'
    alert=''.join('<p class="warning">'+html.escape(str(w))+'</p>' for w in qc["warnings"]+qc["errors"])
    sections=''
    for name,content in qc.items():
        if name in ("warnings","errors"):continue
        sections+=f'<h2>{html.escape(name.replace("_"," ").title())}</h2>'
        if isinstance(content,dict):
            sections+='<pre>'+html.escape(json.dumps(content,indent=2,ensure_ascii=False,default=json_default))+'</pre>'
        else: sections+='<p>'+html.escape(str(content))+'</p>'
    for label,col in [("Attribute frequency","attribute_list"),("Amenity frequency","amenity_list"),("Activity frequency","activity_list")]:
        freq=eligible[col].explode().dropna().value_counts().rename_axis("value").reset_index(name="frequency")
        sections+=f'<h2>{label}</h2>'+freq.to_html(index=False,escape=True)
    (Path(root)/"output/reports/QC_report.html").write_text(html_page("MAPC recreation data quality",headline+links+alert+sections),encoding="utf-8")
    if not all(assertions.values()):raise AssertionError("QC reconciliation failed: "+str({k:v for k,v in assertions.items() if not v}))
    return qc
