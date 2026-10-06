"""Evidence coverage is independent of whether an inventory location can be mapped."""
import pandas as pd

# Compatibility default for programmatic callers of the supplied Massachusetts datasets.
DEFAULT_EVIDENCE_BOUNDS = {"min_lat": 41.0, "max_lat": 43.0, "min_lon": -73.6, "max_lon": -69.8}


def coverage_mask(frame, options):
    bounds = options.get("coverage_bounds", DEFAULT_EVIDENCE_BOUNDS)
    if bounds is None:
        return pd.Series(False, index=frame.index)
    lat = pd.to_numeric(frame["latitude"], errors="coerce")
    lon = pd.to_numeric(frame["longitude"], errors="coerce")
    return lat.between(bounds["min_lat"], bounds["max_lat"]) & lon.between(bounds["min_lon"], bounds["max_lon"])
