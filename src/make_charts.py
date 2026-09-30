"""Publication charts regenerated from validated asset/site analysis tables."""
from pathlib import Path
import textwrap

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
import numpy as np
import pandas as pd

from .analysis import PROFILES, ACCESS, validated_population

PALETTE = {"Transit + free parking": "#0072B2", "Transit only": "#E69F00", "Free parking only": "#CC79A7",
           "Neither": "#4A4A4A", "Unknown / unresolved": "#AEB8C2"}
SHORT = {"Transit + free parking": "Transit + free\nentry/parking", "Transit only": "Transit only",
         "Free parking only": "Free entry/parking\nonly", "Neither": "Neither", "Unknown / unresolved": "Unknown /\nunresolved"}
ACCESS_NAMES = {"accessible_parking": "Accessible parking", "accessible_restroom": "Accessible restroom",
                "wheelchair_stroller_friendly_trail": "Wheelchair/stroller-\nfriendly trail"}


def make_charts(tables, assets, sites, root, config):
    out = Path(root) / "output" / "charts"
    out.mkdir(parents=True, exist_ok=True)
    frame = validated_population(assets)
    n, n_sites = len(frame), len(tables["validated_sites"])
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.titlesize": 15,
                         "axes.labelsize": 11, "axes.spines.top": False, "axes.spines.right": False,
                         "svg.fonttype": "none", "savefig.facecolor": "white", "axes.edgecolor": "#AAB3BE"})
    index = []
    def finish(fig, ax, slug, title, source, note):
        ax.set_title(title, loc="left", pad=43 if slug == "access_evidence_completeness" else 16, color="#17324D", weight="bold")
        fig.text(.10, .025, "\n".join(textwrap.wrap(
            f"MAPC recreation inventory. Validated assets n={n}, sites n={n_sites}. {note}", 125)),
            fontsize=8.2, color="#485664", va="bottom")
        fig.subplots_adjust(bottom=.23, left=.12, right=.96, top=.87)
        for ext in ("png", "svg"):
            fig.savefig(out / f"{slug}.{ext}", dpi=220, bbox_inches="tight")
        plt.close(fig)
        index.append({"figure": slug, "title": title, "source_table": source,
                      "population": f"{n} validated assets at {n_sites} sites", "method_note": note})
    profiles = [p for p in PROFILES if (frame.get("transportation_access_profile", pd.Series(dtype=object)) == p).any()]
    for metric, slug, title, ylabel in [
        ("attribute_count", "feature_counts_by_transport", "Recorded features by transportation profile", "Recorded MAPC attributes/features per asset"),
        ("activity_count", "activity_counts_by_transport", "Recorded activities by transportation profile", "Recorded activity types per asset")]:
        fig, ax = plt.subplots(figsize=(10, 6.5))
        if profiles:
            arrays = [frame.loc[frame.transportation_access_profile == p, metric].astype(float) for p in profiles]
            box = ax.boxplot(arrays, tick_labels=[SHORT[p] + f"\n(n={len(a)})" for p, a in zip(profiles, arrays)],
                             patch_artist=True, widths=.56, medianprops={"color": "#172C40", "linewidth": 2})
            for patch, p in zip(box["boxes"], profiles):
                patch.set_facecolor(PALETTE[p]); patch.set_alpha(.65)
            ax.yaxis.set_major_locator(MaxNLocator(integer=True))
            ax.set_ylim(bottom=-.3)
        else:
            ax.text(.5, .5, "No validated assets available", transform=ax.transAxes, ha="center")
        ax.set_xlabel("Audited transportation profile")
        ax.set_ylabel(ylabel)
        ax.grid(axis="y", alpha=.17)
        finish(fig, ax, slug, title, "asset_profiles.csv; chart_scatter.csv",
               "Boxes show median and interquartile range; whiskers extend to 1.5 IQR. Unknown retains incomplete evidence. Assets within sites are clustered.")
    fig, ax = plt.subplots(figsize=(9, 6.5))
    scatter = tables["chart_scatter"]
    if len(scatter):
        pairs = scatter.groupby(["attribute_count", "activity_count"]).size().reset_index(name="n_assets")
        points = ax.scatter(pairs.attribute_count, pairs.activity_count, s=30 + pairs.n_assets * 30, alpha=.65,
                            c="#0072B2", edgecolors="white", linewidth=.7)
        for size in sorted({1, int(pairs.n_assets.max())}):
            ax.scatter([], [], s=30 + size * 30, c="#0072B2", alpha=.65, label=f"{size} asset" + ("s" if size != 1 else ""))
        ax.legend(title="Assets at identical values", loc="upper left", frameon=False)
    ax.set_xlabel("Number of recorded MAPC attributes/features")
    ax.set_ylabel("Number of recorded activity types")
    ax.xaxis.set_major_locator(MaxNLocator(integer=True)); ax.yaxis.set_major_locator(MaxNLocator(integer=True))
    ax.grid(alpha=.15)
    rho = tables["correlations"].iloc[0].spearman_rho
    finish(fig, ax, "activities_vs_features", "Activity breadth and recorded features", "chart_scatter.csv; correlations.csv",
           f"Bubble area indicates repeated observations. Descriptive Spearman rho={rho:.2f}. No p-value; no causal interpretation.")
    fig, ax = plt.subplots(figsize=(9, 6.8))
    co = tables["accessibility_cooccurrence"]
    matrix = co.pivot(index="feature_a", columns="feature_b", values="both_yes").reindex(index=ACCESS, columns=ACCESS).fillna(0).to_numpy()
    ax.imshow(matrix, cmap="Blues", vmin=0, vmax=max(1, matrix.max()))
    for i in range(3):
        for j in range(3):
            ax.text(j, i, f"{int(matrix[i,j])}\n({100 * matrix[i,j] / n:.1f}%)" if n else "0", ha="center", va="center",
                    color="white" if matrix[i,j] > matrix.max() * .55 else "#17324D", fontsize=13)
    ax.set_xticks(range(3), [ACCESS_NAMES[k] for k in ACCESS], fontsize=9)
    ax.set_yticks(range(3), [ACCESS_NAMES[k] for k in ACCESS], fontsize=9)
    ax.set_xlabel("Accessibility feature recorded YES"); ax.set_ylabel("Accessibility feature recorded YES")
    finish(fig, ax, "accessibility_cooccurrence", "Accessibility features recorded together", "accessibility_cooccurrence.csv",
           "Cells show count and share of all validated assets with both features YES. Diagonal counts show each feature. Unknown does not mean No.")
    fig, ax = plt.subplots(figsize=(10, 6.5))
    access = tables["accessibility"].copy()
    names = [ACCESS_NAMES.get(v, v.replace("_", " ").capitalize()) for v in access.field]
    left = np.zeros(len(access))
    for field, color, label in [("yes", "#0072B2", "Yes"), ("no", "#E69F00", "No"), ("unknown", "#CED5DC", "Unknown")]:
        ax.barh(names, access[field], left=left, color=color, label=label, height=.64)
        left += access[field].to_numpy()
    ax.invert_yaxis(); ax.set_xlabel("Number of validated assets"); ax.legend(ncols=3, frameon=False, loc="lower center", bbox_to_anchor=(.5, 1.00))
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    finish(fig, ax, "access_evidence_completeness", "Transportation and accessibility evidence", "accessibility.csv",
           "Every row uses all validated assets. No requires explicit evidence; a missing structured tag remains Unknown.")
    fig, ax = plt.subplots(figsize=(9, 6.5))
    bike = tables["bike_transit"]
    base = np.zeros(3)
    for bike_state, color in [("YES", "#0072B2"), ("NO", "#E69F00"), ("UNKNOWN", "#CED5DC")]:
        vals = [int(bike.loc[bike.state_a.eq(t) & bike.state_b.eq(bike_state), "n"].sum()) for t in ["YES", "NO", "UNKNOWN"]]
        ax.bar(["Transit: Yes", "Transit: No", "Transit: Unknown"], vals, bottom=base, color=color, label="Bike proximity: " + bike_state.title(), width=.64)
        base += vals
    ax.set_xlabel("Audited public transit proximity"); ax.set_ylabel("Number of validated assets")
    ax.yaxis.set_major_locator(MaxNLocator(integer=True)); ax.legend(frameon=False, fontsize=9)
    radius = config.get("gis", {}).get("proximity_radius_miles", .5)
    finish(fig, ax, "bike_and_transit", "Existing bike infrastructure and transit proximity", "bike_transit.csv",
           f"Bike proximity uses <= {radius:g} mile to existing line geometry. Near transit uses <= 0.5 mile to an MBTA stop. Neither establishes route connectivity.")
    fig, ax = plt.subplots(figsize=(10, 6.5))
    sub = tables["subregions"].sort_values("attribute_count_mean", ascending=True)
    if len(sub):
        labels = [f"{row.subregion} (n={row.n})" for row in sub.itertuples()]
        ax.barh(labels, sub.attribute_count_mean, color="#0072B2", height=.58)
        for i, value in enumerate(sub.attribute_count_mean):
            ax.text(value + .08, i, f"{value:.1f}", va="center", fontsize=10)
        ax.set_xlim(0, max(1, sub.attribute_count_mean.max()) * 1.20)
    ax.set_xlabel("Mean number of recorded MAPC attributes/features per validated asset")
    ax.set_ylabel("MAPC subregion")
    finish(fig, ax, "subregion_features", "Recorded feature counts across subregions", "subregions.csv",
           "Uneven sample sizes and validation coverage limit regional comparisons. Full descriptive statistics accompany this figure.")
    fig, ax = plt.subplots(figsize=(10, 6.5))
    a = tables["asset_profiles"].set_index("transportation_access_profile")
    s = tables["site_profiles"].set_index("transportation_access_profile")
    order = [p for p in PROFILES if p in a.index or p in s.index]
    xs = np.arange(len(order))
    ax.bar(xs - .18, [a.at[p, "activity_count_mean"] if p in a.index else np.nan for p in order], .36, label="Per asset", color="#0072B2")
    ax.bar(xs + .18, [s.at[p, "activity_count_mean"] if p in s.index else np.nan for p in order], .36, label="Per site (union)", color="#E69F00")
    ax.set_xticks(xs, [SHORT[p] for p in order]); ax.set_xlabel("Transportation profile at the stated unit")
    ax.set_ylabel("Mean recorded activity types"); ax.legend(frameon=False)
    finish(fig, ax, "asset_site_comparison", "Activity breadth at asset and site level", "asset_profiles.csv; site_profiles.csv",
           "Sites union validated member activities; any member YES yields site YES. Site transit and parking may describe different members. Units are not interchangeable.")
    pd.DataFrame(index).to_csv(out / "chart_index.csv", index=False, encoding="utf-8-sig")
    return [str(out / (v["figure"] + ".png")) for v in index]
