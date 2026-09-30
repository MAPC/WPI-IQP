"""Activities are discovered from source values, never a fixed vocabulary."""
from collections import Counter
import pandas as pd
from .parse_attributes import parse_multivalue


def parse_activities(raw):
    values = parse_multivalue(raw)
    return {"activity_list": values, "activity_count": len(values)}


def build_activity_dictionary(df):
    subset = df[df["record_status"].eq("accepted")] if "record_status" in df else df
    counts = Counter(value for values in subset["activity_list"] for value in values)
    return pd.DataFrame([{"activity": value, "frequency": counts[value],
                          "notes": "Recorded source activity; frequency is accepted asset records."}
                         for value in sorted(counts, key=str.casefold)], columns=["activity", "frequency", "notes"])
