"""Publication map with local geography and no external tile dependency."""
from pathlib import Path
import numpy as np
import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from .make_map import marker_radius, PROFILES

def make_static_map(assets, layers, root, config):
    data=assets.copy()
    if "record_status" in data: data=data[data.record_status.eq("accepted")]
    data=data[data.field_validated.eq(True)&data.latitude.notna()&data.longitude.notna()]
    if "coordinate_usable" in data:data=data[data.coordinate_usable.eq(True)]
    points=gpd.GeoDataFrame(data,geometry=gpd.points_from_xy(data.longitude,data.latitude),crs=4326).to_crs(config["gis"]["analysis_crs"])
    plt.rcParams.update({"font.family":"DejaVu Sans","font.size":10,"svg.fonttype":"none"})
    fig,ax=plt.subplots(figsize=(12,11));fig.patch.set_facecolor("white");ax.set_facecolor("#eef3f4")
    if len(points):
        minx,miny,maxx,maxy=points.total_bounds;pad=max(maxx-minx,maxy-miny)*.07
        ax.set_xlim(minx-pad,maxx+pad);ax.set_ylim(miny-pad,maxy+pad)
        for name,color,lw in [("walking_trails","#c8cebf",.3),("shared_use_paths","#b8a878",.6),("bicycle_facilities","#72a3a3",.6)]:
            layer=layers.get(name)
            if layer is not None and len(layer):
                d=layer[layer.analysis_include.eq(True)].to_crs(points.crs)
                d=d.cx[minx-pad:maxx+pad,miny-pad:maxy+pad]
                if len(d): d.plot(ax=ax,color=color,linewidth=lw,zorder=1)
        for profile in PROFILES:
            d=points[points.transportation_access_profile.eq(profile)]
            if len(d):ax.scatter(d.geometry.x,d.geometry.y,s=[marker_radius(c,config)**2*1.5 for c in d[config["map"]["size_metric"]]],c=config["map"]["colors"][profile],edgecolors="#263f4c",linewidths=.7,alpha=.85,zorder=3)
        centers=points.groupby("municipality",dropna=False).apply(lambda g:(g.geometry.x.mean(),g.geometry.y.mean()))
        # Municipal labels are descriptive centroids of sampled assets, not town boundaries.
        for name,(x,y) in centers.items():
            if isinstance(name,str) and name.strip() and not name.strip().isdigit():ax.annotate(name,(x,y),xytext=(4,5),textcoords="offset points",fontsize=7,color="#425b69",zorder=2)
        length=10000; x=minx; y=miny-pad*.55
        ax.plot([x,x+length],[y,y],color="#153b50",lw=3);ax.text(x+length/2,y+pad*.15,"10 km",ha="center",fontsize=8)
    ax.set_aspect("equal");ax.set_axis_off()
    ax.annotate('N',xy=(.965,.92),xytext=(.965,.98),xycoords='axes fraction',ha='center',va='center',fontsize=10,arrowprops={'arrowstyle':'<-','color':'#153b50'},color='#153b50')
    fig.suptitle("Recreation access across the MAPC inventory",fontsize=21,fontweight="bold",x=.06,ha="left",y=.965,color="#153b50")
    fig.text(.06,.928,f"Field-validated assets with usable coordinates · n = {len(points):,}",fontsize=12,color="#536773")
    handles=[Line2D([0],[0],marker="o",color="none",markerfacecolor=config["map"]["colors"][p],markeredgecolor="#263f4c",markersize=8,label=p) for p in PROFILES]
    ax.legend(handles=handles,loc="lower right",title="Transportation access",framealpha=.95,fontsize=9,title_fontsize=10)
    metric="recorded MAPC attributes/features" if config["map"]["size_metric"]=="attribute_count" else "classified physical amenities"
    thresholds=config["map"]["size_thresholds"]
    size_handles=[Line2D([0],[0],marker="o",color="none",markerfacecolor="#7195a7",markeredgecolor="#345",markersize=marker_radius(v,config)*np.sqrt(1.5),label=f'{v}–{thresholds[i+1]-1}' if i<len(thresholds)-1 else f'{v}+') for i,v in enumerate(thresholds)]
    fig.legend(handles=size_handles,loc="lower left",bbox_to_anchor=(.06,.065),ncol=5,title="Marker size: "+metric,frameon=False)
    fig.text(.06,.04,"Near public transit = MBTA stop/station within 0.5 mile. Distances indicate proximity, not accessible routes.\nSource: MAPC asset inventory and existing/public network layers; MBTA GTFS when available. Labels locate sampled assets.\nMissing structured tags remain Unknown. Assets at the same site are clustered observations.",fontsize=8,color="#536773")
    fig.subplots_adjust(left=.035,right=.97,bottom=.15,top=.9)
    dest=Path(root)/"output/maps";dest.mkdir(parents=True,exist_ok=True)
    paths=[]
    for ext in ("png","svg"):
        p=dest/f"MAPC_access_map_static.{ext}";fig.savefig(p,dpi=240,facecolor="white");paths.append(p)
    plt.close(fig);return paths
