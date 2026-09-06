import pandas as pd

from config.settings import FilterConfig
from services.metrics import compute_thermal_anomaly, filter_candidates
from utils.validation import QualityReport


def _sample_df():
    return pd.DataFrame({
        "lst_median_c": [40.0, 45.0, 50.0, None],
        "roof_area_m2": [500.0, 100.0, 600.0, 700.0],
    })


def test_compute_thermal_anomaly_clips_at_zero():
    df = _sample_df()
    out = compute_thermal_anomaly(df)
    # median of [40, 45, 50] ignoring NaN = 45
    assert out["lst_baseline_c"].iloc[0] == 45.0
    assert (out["lst_anomaly_c"].dropna() >= 0).all()
    assert out["lst_anomaly_c"].iloc[0] == 0.0   # 40 - 45 clipped to 0
    assert out["lst_anomaly_c"].iloc[2] == 5.0   # 50 - 45


def test_filter_candidates_drops_small_and_missing_thermal():
    df = _sample_df()
    df = compute_thermal_anomaly(df)
    filters = FilterConfig(min_roof_area_m2=400.0, require_thermal_data=True)
    report = QualityReport()
    out = filter_candidates(df, filters, report)
    # Row 1 (area 100) and row 3 (NaN LST) should be dropped
    assert len(out) == 2
    assert report.has_warnings
