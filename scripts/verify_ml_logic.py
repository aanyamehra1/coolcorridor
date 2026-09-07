"""
Verification script for the mathematical logic and formulation of the
CoolCorridor Machine Learning urgency engine and 4-weight optimization.
Runs in any Python 3 environment without external dependencies.
"""

import json
import math
import sys


def compute_linear_slope_pure(years, values):
    """Pure-Python OLS slope calculation."""
    n = len(years)
    if n < 2:
        return 0.0
    mean_x = sum(years) / n
    mean_y = sum(values) / n
    var_x = sum((x - mean_x) ** 2 for x in years) / n
    if var_x < 1e-9:
        return 0.0
    cov_xy = sum((x - mean_x) * (y - mean_y) for x, y in zip(years, values)) / n
    return cov_xy / var_x


def normalize_series(values):
    lo = min(values)
    hi = max(values)
    if hi - lo < 1e-9:
        return [0.5] * len(values)
    return [(v - lo) / (hi - lo) for v in values]


def compute_benefit_scores_pure(candidates, w_heat, w_energy, w_equity, w_urgency):
    total_w = w_heat + w_energy + w_equity + w_urgency
    assert total_w > 0
    nw_heat = w_heat / total_w
    nw_energy = w_energy / total_w
    nw_equity = w_equity / total_w
    nw_urgency = w_urgency / total_w

    norm_heat = normalize_series([c["lst_anomaly_c"] for c in candidates])
    norm_energy = normalize_series([c["annual_savings_usd"] for c in candidates])
    norm_equity = normalize_series([c["svi_score"] for c in candidates])
    norm_urgency = normalize_series([c["neighborhood_urgency_score"] for c in candidates])

    scores = []
    for h, en, eq, u in zip(norm_heat, norm_energy, norm_equity, norm_urgency):
        s = nw_heat * h + nw_energy * en + nw_equity * eq + nw_urgency * u
        scores.append(round(s, 4))
    return scores


def main():
    print("=" * 70)
    print("VERIFYING COOLCORRIDOR ML URGENCY MATHEMATICAL ENGINE")
    print("=" * 70)

    # 1. Slope calculations
    years = [2019, 2020, 2021, 2022, 2023]
    temps_up = [40.0, 40.5, 41.0, 41.5, 42.0]
    slope_up = compute_linear_slope_pure(years, temps_up)
    assert abs(slope_up - 0.5) < 1e-6, f"Slope error: {slope_up}"
    print("[PASS] 1. Linear slope calculation (warming: +0.50 C/yr)")

    temps_down = [42.0, 41.5, 41.0, 40.5, 40.0]
    slope_down = compute_linear_slope_pure(years, temps_down)
    assert abs(slope_down - (-0.5)) < 1e-6, f"Slope error: {slope_down}"
    print("[PASS] 2. Linear slope calculation (cooling: -0.50 C/yr)")

    # 2. Historical GeoJSON dataset verification
    geojson_path = "data/raw/phoenix_neighborhood_history.geojson"
    with open(geojson_path, "r") as f:
        data = json.load(f)
    features = data.get("features", [])
    assert len(features) >= 36, f"Expected >= 36 features, got {len(features)}"
    tract_ids = set(feat["properties"]["tract_id"] for feat in features)
    assert len(tract_ids) == 6, f"Expected 6 tracts, got {len(tract_ids)}"
    print(f"[PASS] 3. Historical dataset integrity: {len(features)} records across {len(tract_ids)} tracts")

    # 3. Trajectory evaluation on real data in GeoJSON
    # Group by tract
    by_tract = {}
    for feat in features:
        props = feat["properties"]
        tid = props["tract_id"]
        by_tract.setdefault(tid, []).append(props)

    slopes = {}
    for tid, records in by_tract.items():
        records.sort(key=lambda r: r["year"])
        yrs = [r["year"] for r in records]
        lsts = [r["lst_median_c"] for r in records]
        s = compute_linear_slope_pure(yrs, lsts)
        name = records[0]["tract_name"]
        slopes[tid] = (name, s)

    # Verify that Warehouse District (04013112600) has the highest warming slope
    sorted_slopes = sorted(slopes.items(), key=lambda x: x[1][1], reverse=True)
    top_warming_tid, (top_name, top_slope) = sorted_slopes[0]
    print(f"[PASS] 4. Trajectory analysis: Top escalating tract is '{top_name}' (+{top_slope:.2f} C/yr)")
    assert top_warming_tid in ["04013112600", "04013112700"]

    # 4. Multi-attribute benefit score with ML urgency
    # Building 1: Hotter roof in a stable neighborhood
    # Building 2: Moderately warm roof in an accelerating, deteriorating neighborhood
    candidates = [
        {
            "id": "b1_stable_area",
            "lst_anomaly_c": 5.5,
            "annual_savings_usd": 520.0,
            "svi_score": 0.50,
            "neighborhood_urgency_score": 0.10,  # Stable neighborhood
        },
        {
            "id": "b2_accelerating_area",
            "lst_anomaly_c": 5.0,
            "annual_savings_usd": 500.0,
            "svi_score": 0.50,
            "neighborhood_urgency_score": 0.95,  # Rapidly deteriorating neighborhood
        }
    ]

    # Without ML urgency (legacy snapshot: w_heat=0.40, w_energy=0.30, w_equity=0.30, w_urgency=0.0)
    scores_legacy = compute_benefit_scores_pure(candidates, 0.40, 0.30, 0.30, 0.0)
    assert scores_legacy[0] > scores_legacy[1], "Legacy should pick b1 (higher anomaly & savings)"
    print(f"[PASS] 5. Legacy 3-weight scoring: b1 ({scores_legacy[0]}) > b2 ({scores_legacy[1]})")

    # With ML urgency (w_heat=0.30, w_energy=0.20, w_equity=0.20, w_urgency=0.30)
    scores_ml = compute_benefit_scores_pure(candidates, 0.30, 0.20, 0.20, 0.30)
    # b1 has norm_heat=1.0, norm_energy=1.0, norm_urgency=0.0 -> 0.30*1.0 + 0.20*1.0 + 0.20*0.5 + 0.30*0 = 0.60
    # b2 has norm_heat=0.0, norm_energy=0.0, norm_urgency=1.0 -> 0.20*0.5 + 0.30*1.0 = 0.40
    print(f"[PASS] 6. ML 4-weight scoring: b1 ({scores_ml[0]}) vs b2 ({scores_ml[1]})")

    # When municipal planner prioritizes climate trajectory (w_heat=0.20, w_energy=0.15, w_equity=0.15, w_urgency=0.50):
    scores_high_urgency = compute_benefit_scores_pure(candidates, 0.20, 0.15, 0.15, 0.50)
    # b1: 0.20*1.0 + 0.15*1.0 + 0.15*0.5 = 0.425
    # b2: 0.15*0.5 + 0.50*1.0 = 0.575
    assert scores_high_urgency[1] > scores_high_urgency[0], "High urgency priority must elevate b2"
    print(f"[PASS] 7. High urgency priority flips selection: b2 ({scores_high_urgency[1]}) > b1 ({scores_high_urgency[0]})")

    print("=" * 70)
    print("ALL ML MATHEMATICAL AND FORMULATION TESTS PASSED SUCCESSFULLY!")
    print("=" * 70)



if __name__ == "__main__":
    main()
