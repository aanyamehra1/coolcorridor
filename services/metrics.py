"""
Building-level metrics: thermal anomaly and candidate filtering.

What goes in: a GeoDataFrame with `lst_median_c` (from services.raster) and
geometric columns (from utils.geo.compute_area_and_perimeter).
What comes out: the same GeoDataFrame plus `lst_baseline_c`,
`lst_anomaly_c`, and (after filter_candidates) a reduced set of rows that
meet the configured eligibility criteria.

Baseline choice: we use the MEDIAN building LST across the study area as the
local baseline, not the mean, so a handful of extremely hot or cold
buildings don't drag the reference point around. Anomaly is clipped at zero
-- a building cooler than the baseline is not scored as "negatively hot".
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from config.settings import FilterConfig
from utils.validation import QualityReport, require_columns


def compute_thermal_anomaly(gdf: pd.DataFrame) -> pd.DataFrame:
    require_columns(gdf, ["lst_median_c"], "compute_thermal_anomaly")
    out = gdf.copy()
    baseline = float(np.nanmedian(out["lst_median_c"]))
    out["lst_baseline_c"] = baseline
    out["lst_anomaly_c"] = (out["lst_median_c"] - baseline).clip(lower=0)
    return out


def filter_candidates(
    gdf: pd.DataFrame,
    filters: FilterConfig,
    report: QualityReport | None = None,
) -> pd.DataFrame:
    """Apply the configured eligibility filters and log why rows were dropped.

    Filters are read from one FilterConfig object (see config/settings.py)
    rather than hard-coded thresholds scattered through the codebase.
    """
    report = report if report is not None else QualityReport()
    out = gdf.copy()
    n_start = len(out)

    if filters.require_thermal_data:
        has_lst = out["lst_median_c"].notna()
        if (~has_lst).any():
            report.add(
                f"Excluded {(~has_lst).sum()} building(s) with no usable "
                "thermal data."
            )
        out = out[has_lst]

    area_ok = out["roof_area_m2"] >= filters.min_roof_area_m2
    if (~area_ok).any():
        report.add(
            f"Excluded {(~area_ok).sum()} building(s) below the minimum "
            f"roof area of {filters.min_roof_area_m2:.0f} m²."
        )
    out = out[area_ok]

    if "lst_anomaly_c" in out.columns:
        anomaly_ok = out["lst_anomaly_c"] >= filters.min_thermal_anomaly_c
        if filters.max_thermal_anomaly_c is not None:
            anomaly_ok &= out["lst_anomaly_c"] <= filters.max_thermal_anomaly_c
        if (~anomaly_ok).any():
            report.add(
                f"Excluded {(~anomaly_ok).sum()} building(s) outside the "
                "configured thermal-anomaly range."
            )
        out = out[anomaly_ok]

    out = out.reset_index(drop=True)
    report.add(
        f"{len(out)} of {n_start} buildings are eligible candidates after filtering."
    )
    return out
