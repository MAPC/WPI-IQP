"""Descriptive analysis with explicit populations and unknown denominators.

No hypothesis tests are performed: MAPC assets are clustered within sites and
the inventory is not a random sample. Every saved result is recomputed.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path
import json

import numpy as np
import pandas as pd


ACCESS = ["accessible_parking", "accessible_restroom", "wheelchair_stroller_friendly_trail"]
PROFILES = ["Transit + free parking", "Transit only", "Free parking only", "Neither", "Unknown / unresolved"]
COUNTS = ["attribute_count", "amenity_count", "activity_count"]


def as_list(value):
    if isinstance(value, (list, tuple, set)):
        return list(value)
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return []
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return parsed
        except (ValueError, TypeError):
            pass
        return [v.strip() for v in value.split(";") if v.strip()]
    return []


def truth(value):
    return value is True or str(value).strip().lower() in {"true", "1", "yes"}


def state_series(df, field):
    """Prefer the named audit output; unknown never becomes an absence."""
    name = field + "_audited_value" if field + "_audited_value" in df else field
    if name not in df:
        return pd.Series("UNKNOWN", index=df.index, dtype="object")
    return df[name].map(lambda v: str(v).upper() if str(v).upper() in {"YES", "NO"} else "UNKNOWN")


def validated_population(assets):
    frame = assets.copy()
    if "record_status" in frame:
        frame = frame[frame.record_status.eq("accepted")]
    if "field_validated" in frame:
        frame = frame[frame.field_validated.map(truth)]
    else:
        frame = frame.iloc[0:0]
    if "source_record_key" in frame:
        frame = frame.drop_duplicates("source_record_key", keep="first")
    return frame.copy()


def grouped_counts(df, by, unit="asset"):
    cols = [by, "unit", "n"] + [f"{c}_{s}" for c in COUNTS for s in ["mean", "median", "q1", "q3"]]
    if df.empty:
        return pd.DataFrame(columns=cols)
    records = []
    for group, g in df.groupby(by, dropna=False, sort=True):
        row = {by: "Unknown" if pd.isna(group) else group, "unit": unit, "n": len(g)}
        for c in COUNTS:
            vals = pd.to_numeric(g[c], errors="coerce") if c in g else pd.Series(dtype=float)
            row.update({f"{c}_mean": vals.mean(), f"{c}_median": vals.median(),
                        f"{c}_q1": vals.quantile(.25), f"{c}_q3": vals.quantile(.75)})
        records.append(row)
    return pd.DataFrame(records, columns=cols)


def cross_states(df, left, right):
    a, b = state_series(df, left), state_series(df, right)
    records = []
    for x in ["YES", "NO", "UNKNOWN"]:
        for y in ["YES", "NO", "UNKNOWN"]:
            n = int(((a == x) & (b == y)).sum())
            records.append({"dimension_a": left, "dimension_b": right, "state_a": x, "state_b": y,
                            "n": n, "denominator_all_validated": len(df),
                            "share_all_validated": n / len(df) if len(df) else np.nan})
    return pd.DataFrame(records)


def frequency_table(df, column, label):
    counts = Counter(v for values in df.get(column, pd.Series(dtype=object)) for v in set(as_list(values)))
    return pd.DataFrame([{label: key, "n_assets": n, "denominator_validated_assets": len(df),
                          "share_validated_assets": n / len(df) if len(df) else np.nan}
                         for key, n in sorted(counts.items(), key=lambda x: (-x[1], x[0]))],
                        columns=[label, "n_assets", "denominator_validated_assets", "share_validated_assets"])


def site_sensitivity(frame):
    """One row per site, recomputed using validated member assets only."""
    records = []
    for sid, g in frame.groupby("site_id", dropna=False, sort=True):
        row = {"site_id": sid, "site_name": g.iloc[0].get("site_name", ""), "n_validated_assets": len(g),
               "subregion": " | ".join(sorted({str(v).strip() for v in g.get("subregion",pd.Series(dtype=str)).dropna() if str(v).strip()})) or "Unknown"}
        for field in COUNTS:
            row[field] = len(set(v for values in g[field.replace("_count", "_list")] for v in as_list(values)))
            row["mean_asset_" + field] = pd.to_numeric(g[field], errors="coerce").mean()
        for field in ["near_public_transit", "free_entry_parking"] + ACCESS:
            values = state_series(g, field)
            row[field] = "YES" if values.eq("YES").any() else "NO" if values.eq("NO").all() else "UNKNOWN"
        t, p = row["near_public_transit"], row["free_entry_parking"]
        row["transportation_access_profile"] = ({("YES", "YES"): PROFILES[0], ("YES", "NO"): PROFILES[1],
                                                  ("NO", "YES"): PROFILES[2], ("NO", "NO"): PROFILES[3]}).get((t, p), PROFILES[4])
        records.append(row)
    return pd.DataFrame(records, columns=["site_id", "site_name", "n_validated_assets", "subregion"] +
                        COUNTS + ["mean_asset_" + c for c in COUNTS] +
                        ["near_public_transit", "free_entry_parking"] + ACCESS + ["transportation_access_profile"])


def correlation_table(df, site=False):
    records = []
    pairs = [("attribute_count", "activity_count"), ("amenity_count", "activity_count")]
    for x, y in pairs:
        pair = df[[x, y]].apply(pd.to_numeric, errors="coerce").dropna()
        r = pair[x].rank().corr(pair[y].rank()) if len(pair) > 1 and pair[x].nunique() > 1 and pair[y].nunique() > 1 else np.nan
        records.append({"unit": "site" if site else "asset", "measure_x": x, "measure_y": y,
                        "n_complete_pairs": len(pair), "spearman_rho": r,
                        "method": "Pearson correlation of average ranks; descriptive only; no p-value"})
    return pd.DataFrame(records)


def run_analysis(assets, sites, root, config):
    root = Path(root)
    out = root / "output" / "analysis"
    out.mkdir(parents=True, exist_ok=True)
    df = validated_population(assets)
    df["near_public_transit"] = state_series(df, "near_public_transit")
    df["free_entry_parking"] = state_series(df, "free_entry_parking")
    df["near_existing_bike"] = state_series(df, "near_existing_bike")
    df["near_shared_use_path"] = state_series(df, "near_shared_use_path")
    def core_group(value):
        label = str(value).strip().casefold()
        if pd.isna(value) or not label:
            return "Unknown subregion"
        if label == "inner core":
            return "Inner Core"
        if "inner core" in [token.strip() for token in label.split("/")]:
            return "Multiple subregions including Inner Core"
        return "Other subregions"
    df["core_comparison"] = df.get("subregion", pd.Series(index=df.index, dtype=object)).map(core_group)
    df["accessibility_yes_count"] = sum(state_series(df, f).eq("YES").astype(int) for f in ACCESS)
    df["accessibility_unknown_count"] = sum(state_series(df, f).eq("UNKNOWN").astype(int) for f in ACCESS)
    # The three focus attributes overlap the feature total; remove them for a
    # complementary descriptive richness measure, avoiding an automatic relation.
    focus_labels = {"accessible parking", "accessible restroom", "wheelchair / stroller friendly trail",
                    "wheelchair/stroller friendly trail", "wheelchair / stroller-friendly trail",
                    "wheelchair/stroller-friendly trail"}
    df["other_attribute_count"] = df.attribute_list.map(lambda values: sum(str(v).casefold().strip() not in focus_labels for v in as_list(values)))
    validated_sites = site_sensitivity(df)
    accepted = assets[assets.record_status.eq("accepted")] if "record_status" in assets else assets
    quality = [
        ("Source records retained", len(assets)), ("Accepted records", len(accepted)),
        ("Quarantined records", len(assets) - len(accepted)),
        ("Validated unique assets analyzed", len(df)),
        ("Sites with validated assets", len(validated_sites)),
        ("Staff-reviewed accepted records", int(accepted.get("staff_reviewed", pd.Series(dtype=object)).map(truth).sum())),
        ("Validated assets with usable coordinates", int(df.get("coordinate_usable", pd.Series(dtype=object)).map(truth).sum())),
        ("Validated assets with unknown transport profile", int(df.get("transportation_access_profile", pd.Series(dtype=object)).eq(PROFILES[-1]).sum())),
        ("Validated assets without independent transit result", int(state_series(df, "near_public_transit_calculated").eq("UNKNOWN").sum())),
    ]
    tables = {"quality": pd.DataFrame(quality, columns=["metric", "count"]),
              "asset_profiles": grouped_counts(df, "transportation_access_profile"),
              "site_profiles": grouped_counts(validated_sites, "transportation_access_profile", "site"),
              "validated_sites": validated_sites,
              "transit_groups": grouped_counts(df, "near_public_transit"),
              "free_parking_transit": cross_states(df, "near_public_transit", "free_entry_parking"),
              "bike_transit": cross_states(df, "near_public_transit", "near_existing_bike"),
              "shared_use_groups": grouped_counts(df, "near_shared_use_path"),
              "subregions": grouped_counts(df, "subregion"),
              "core_comparison": grouped_counts(df, "core_comparison"),
              "correlations": pd.concat([correlation_table(df), correlation_table(validated_sites, True)], ignore_index=True),
              "attributes": frequency_table(df, "attribute_list", "attribute"),
              "amenities": frequency_table(df, "amenity_list", "amenity"),
              "activities": frequency_table(df, "activity_list", "activity")}
    access_rows, cooccur = [], []
    for f in ACCESS + ["restrooms_available", "free_entry_parking", "near_public_transit"]:
        values = state_series(df, f)
        yes, no, unk = (int(values.eq(s).sum()) for s in ["YES", "NO", "UNKNOWN"])
        access_rows.append({"field": f, "yes": yes, "no": no, "unknown": unk, "n_all": len(df),
                            "n_known": yes + no, "yes_share_known": yes / (yes + no) if yes + no else np.nan,
                            "yes_share_all": yes / len(df) if len(df) else np.nan})
    for f in ACCESS:
        for h in ACCESS:
            a, b = state_series(df, f), state_series(df, h)
            known = a.ne("UNKNOWN") & b.ne("UNKNOWN")
            both = int((a.eq("YES") & b.eq("YES")).sum())
            cooccur.append({"feature_a": f, "feature_b": h, "both_yes": both,
                            "n_both_known": int(known.sum()), "n_all": len(df),
                            "both_yes_share_known": both / known.sum() if known.sum() else np.nan,
                            "both_yes_share_all": both / len(df) if len(df) else np.nan})
    tables["accessibility"] = pd.DataFrame(access_rows)
    tables["accessibility_cooccurrence"] = pd.DataFrame(cooccur)
    rich = grouped_counts(df, "accessibility_yes_count")
    if not df.empty:
        extra = df.groupby("accessibility_yes_count").agg(other_attribute_count_mean=("other_attribute_count", "mean"),
              other_attribute_count_median=("other_attribute_count", "median"),
              unknown_access_fields_mean=("accessibility_unknown_count", "mean")).reset_index()
        rich = rich.merge(extra, on="accessibility_yes_count", how="left")
    tables["accessibility_richness"] = rich
    activity_rows = []
    for profile, group in df.groupby("transportation_access_profile", dropna=False):
        for item in tables["activities"].activity:
            n = int(group.activity_list.map(lambda v: item in as_list(v)).sum())
            activity_rows.append({"activity": item, "transportation_access_profile": profile,
                                  "n_assets": n, "n_profile_assets": len(group), "share_within_profile": n / len(group)})
    tables["activity_profiles"] = pd.DataFrame(activity_rows, columns=["activity", "transportation_access_profile", "n_assets", "n_profile_assets", "share_within_profile"])
    dimensions = ["near_public_transit", "free_entry_parking", "near_existing_bike", "near_shared_use_path"]
    patterns = pd.DataFrame({c: state_series(df, c) for c in dimensions})
    tables["transport_combinations"] = patterns.value_counts(dropna=False).reset_index(name="n_assets")
    if not tables["transport_combinations"].empty:
        tables["transport_combinations"]["denominator_validated_assets"] = len(df)
        tables["transport_combinations"]["share_validated_assets"] = tables["transport_combinations"].n_assets / len(df)
    original = state_series(df, "near_public_transit_original_value")
    calculated = state_series(df, "near_public_transit_calculated")
    compare = pd.DataFrame({"recorded_transit": original, "calculated_transit": calculated})
    tables["transit_comparison"] = compare.value_counts(dropna=False).reset_index(name="n_assets")
    tables["chart_scatter"] = df[[c for c in ["asset_id", "site_id", "asset_name", "transportation_access_profile", "attribute_count", "amenity_count", "activity_count"] if c in df]].copy()
    tables["findings"] = build_findings(tables, df, config)
    for name, frame in tables.items():
        frame.to_csv(out / (name + ".csv"), index=False, encoding="utf-8-sig")
    lines = ["# Recreation inventory analysis", "", f"Population: {len(df)} field-validated, accepted, unique assets at {len(validated_sites)} sites.",
             "", "All findings are descriptive. Assets from the same site are clustered. Unknown is retained separately from No. No inferential significance tests or causal claims are made.", ""]
    for row in tables["findings"].to_dict("records"):
        lines += [f"## {row['question_number']}. {row['question']}", "", row["finding"], "", "Evidence: " + row["source_table"] + ". " + row["limitation"], ""]
    (out / "findings.md").write_text("\n".join(lines), encoding="utf-8")
    return tables


def build_findings(tables, df, config):
    result = []
    def add(q, title, finding, table, limitation):
        result.append({"question_number": q, "question": title, "finding": finding, "source_table": table, "limitation": limitation})
    def extremes(table, group, measure):
        t = tables[table].dropna(subset=[measure])
        if len(t) < 2:
            return "Fewer than two observed groups permit a comparison."
        low, high = t.loc[t[measure].idxmin()], t.loc[t[measure].idxmax()]
        return f"Observed group means range from {low[measure]:.2f} ({low[group]}, n={low['n']}) to {high[measure]:.2f} ({high[group]}, n={high['n']})."
    add(1, "Do recorded feature counts differ by transport profile?", extremes("asset_profiles", "transportation_access_profile", "attribute_count_mean"), "asset_profiles.csv; site_profiles.csv", "All attributes/features are counted, including policies and access tags. Profile tags partly overlap this total; groups are not independent random samples.")
    add(2, "Do activity counts differ by transport profile?", extremes("asset_profiles", "transportation_access_profile", "activity_count_mean"), "asset_profiles.csv", "Differences describe inventory coverage and may reflect recording completeness and site clustering.")
    corr = tables["correlations"].iloc[0]
    rho = corr.spearman_rho
    direction = "undefined (insufficient variation)" if pd.isna(rho) else f"{rho:.2f}"
    strength = "" if pd.isna(rho) else " The rank association is weak in magnitude (|rho| < 0.3)." if abs(rho) < .3 else " The rank association is moderate in magnitude (0.3 <= |rho| < 0.6)." if abs(rho) < .6 else " The rank association is strong in magnitude (|rho| >= 0.6)."
    add(3, "Are activity and feature counts related?", f"Asset-level descriptive Spearman rho is {direction} across {corr.n_complete_pairs} complete pairs.{strength}", "correlations.csv; chart_scatter.csv", "Magnitude labels are descriptive conventions, not inferential significance. Compare the separate site-union correlation, where each site has one observation.")
    add(4, "How do transit groups differ?", extremes("transit_groups", "near_public_transit", "attribute_count_mean"), "transit_groups.csv; transit_comparison.csv", "Audited transit states are used; independent GTFS agreement is shown separately. Missing tags alone do not establish No.")
    cross = tables["free_parking_transit"]
    both = int(cross.loc[cross.state_a.eq("YES") & cross.state_b.eq("YES"), "n"].sum())
    known = int(cross.loc[cross.state_a.ne("UNKNOWN") & cross.state_b.ne("UNKNOWN"), "n"].sum())
    add(5, "How does free entry/parking relate to transit?", f"{both} validated assets record both transit proximity and free entry/parking; {known} have known values for both dimensions out of {len(df)}.", "free_parking_transit.csv", "The combined MAPC tag is free entry/parking, not an independently measured parking-only variable. Unknown states remain visible.")
    joint = sum((state_series(df, f).eq("YES").astype(int) for f in ACCESS)).eq(3).sum()
    add(6, "Do the three accessibility features co-occur?", f"{int(joint)} of {len(df)} validated assets have YES for all three focus accessibility features.", "accessibility_cooccurrence.csv; accessibility.csv", "Pairwise complete denominators differ. Low observed co-occurrence can reflect missing evidence, not confirmed absence.")
    add(7, "Is accessibility related to broader feature richness?", extremes("accessibility_richness", "accessibility_yes_count", "attribute_count_mean"), "accessibility_richness.csv", "The table also removes the three focus accessibility tags from feature richness to expose part-whole overlap. YES counts are lower bounds when access fields are unknown.")
    bike = tables["bike_transit"]
    candidate = int(bike.loc[bike.state_a.eq("NO") & bike.state_b.eq("YES"), "n"].sum())
    unknown_transit = int(bike.loc[bike.state_a.eq("UNKNOWN") & bike.state_b.eq("YES"), "n"].sum())
    add(8, "Could existing bike infrastructure complement weak transit access?", f"{candidate} validated assets have confirmed NO transit proximity and nearby existing bike infrastructure; another {unknown_transit} have nearby bike infrastructure but unknown transit status.", "bike_transit.csv", "Straight-line proximity indicates a candidate alternative. It does not demonstrate a safe, connected or accessible cycling route.")
    add(9, "Do shared-use paths coincide with different recreation opportunities?", extremes("shared_use_groups", "near_shared_use_path", "activity_count_mean"), "shared_use_groups.csv", "Compare mean and median activity counts with n. Proximity to an existing path is not proof of an entrance or connected route.")
    add(10, "Do patterns vary by subregion?", extremes("subregions", "subregion", "attribute_count_mean"), "subregions.csv", "Uneven inventory size, validation coverage and clustered sites limit regional comparisons.")
    add(11, "Does Inner Core differ from other subregions?", extremes("core_comparison", "core_comparison", "attribute_count_mean"), "core_comparison.csv", "Only the explicit Inner Core source label defines the core; mixed labels containing Inner Core form a separate group. Other subregions are not a measured distance-from-center classification.")
    ap = tables["activity_profiles"]
    if ap.empty:
        activity_finding = "No validated activity-profile combinations are available."
    else:
        spread = ap.groupby("activity").share_within_profile.agg(["min", "max"])
        spread["spread"] = spread["max"] - spread["min"]
        strongest = spread.sort_values(["spread"], ascending=False).iloc[0]
        activity_finding = f"The largest observed difference in within-profile activity shares is {100 * strongest['spread']:.1f} percentage points for {strongest.name}."
    add(12, "Are activity types associated with different access profiles?", activity_finding, "activity_profiles.csv", "Profiles may have very small n; the table gives every activity, numerator and denominator. This exploratory maximum is not a multiple-testing-adjusted result.")
    patterns = tables["transport_combinations"]
    fully_known = patterns[patterns[["near_public_transit", "free_entry_parking", "near_existing_bike", "near_shared_use_path"]].ne("UNKNOWN").all(axis=1)]
    complete = int(fully_known.n_assets.sum()) if len(fully_known) else 0
    add(13, "Are transport access dimensions complementary or fragmented?", f"{complete} of {len(df)} validated assets have known values across all four transport dimensions; {len(patterns)} distinct observed YES/NO/UNKNOWN combinations occur.", "transport_combinations.csv", "Evidence gaps are reported separately from fragmentation. Do not equate unknown access with unavailable access.")
    return pd.DataFrame(result)
