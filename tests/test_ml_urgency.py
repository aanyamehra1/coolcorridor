import numpy as np
import pandas as pd
import pytest

from services.ml_urgency import (
    FEATURE_COLUMNS,
    NeighborhoodUrgencyEngine,
    compute_linear_slope,
    extract_trajectory_features,
    run_neighborhood_urgency_pipeline,
)
from services.vulnerability import attach_neighborhood_urgency


def test_compute_linear_slope_positive_and_negative():
    years = np.array([2019, 2020, 2021, 2022, 2023])
    temps_up = np.array([40.0, 40.5, 41.0, 41.5, 42.0])
    slope_up = compute_linear_slope(years, temps_up)
    assert pytest.approx(slope_up, 0.001) == 0.5

    temps_down = np.array([42.0, 41.5, 41.0, 40.5, 40.0])
    slope_down = compute_linear_slope(years, temps_down)
    assert pytest.approx(slope_down, 0.001) == -0.5

    flat = np.array([40.0, 40.0, 40.0, 40.0, 40.0])
    assert compute_linear_slope(years, flat) == 0.0


def _sample_panel_df():
    records = []
    # Tract A: Accelerating heat, canopy loss, high poverty (urgent)
    for i, yr in enumerate([2019, 2020, 2021, 2022, 2023]):
        records.append({
            "tract_id": "TRACT_A",
            "tract_name": "Hot Urban Core",
            "year": yr,
            "lst_median_c": 42.0 + i * 0.8,
            "lst_anomaly_c": 3.0 + i * 0.5,
            "ndvi_mean": max(0.02, 0.15 - i * 0.02),
            "svi_score": 0.80 + i * 0.02,
            "poverty_rate": 0.35 + i * 0.01,
            "elderly_pct": 0.16,
            "extreme_heat_days": 40 + i * 2,
        })
    # Tract B: Stable / cooling, expanding canopy, low poverty (low urgency)
    for i, yr in enumerate([2019, 2020, 2021, 2022, 2023]):
        records.append({
            "tract_id": "TRACT_B",
            "tract_name": "Green Suburb",
            "year": yr,
            "lst_median_c": 38.0 - i * 0.1,
            "lst_anomaly_c": 0.5 - i * 0.1,
            "ndvi_mean": 0.25 + i * 0.02,
            "svi_score": 0.30 - i * 0.01,
            "poverty_rate": 0.10,
            "elderly_pct": 0.10,
            "extreme_heat_days": 25,
        })
    return pd.DataFrame(records)


def test_extract_trajectory_features():
    df = _sample_panel_df()
    feats = extract_trajectory_features(df, current_year=2023, lookback_years=5)

    assert len(feats) == 2
    for col in FEATURE_COLUMNS:
        assert col in feats.columns

    tract_a = feats[feats["tract_id"] == "TRACT_A"].iloc[0]
    tract_b = feats[feats["tract_id"] == "TRACT_B"].iloc[0]

    assert tract_a["lst_slope_5yr"] > tract_b["lst_slope_5yr"]
    assert tract_a["ndvi_delta_pct"] < tract_b["ndvi_delta_pct"]
    assert tract_a["heat_poverty_interaction"] > tract_b["heat_poverty_interaction"]


def test_neighborhood_urgency_engine_scoring_and_attribution():
    df = _sample_panel_df()
    feats = extract_trajectory_features(df, current_year=2023, lookback_years=5)

    engine = NeighborhoodUrgencyEngine()
    scored_df, attributions = engine.predict_urgency(feats)

    assert len(scored_df) == 2
    assert "neighborhood_urgency_score" in scored_df.columns
    scores = scored_df["neighborhood_urgency_score"].to_numpy()
    assert (scores >= 0.0).all() and (scores <= 1.0).all()

    # Tract A must score higher in urgency than Tract B
    tract_a_score = scored_df.loc[scored_df["tract_id"] == "TRACT_A", "neighborhood_urgency_score"].iloc[0]
    tract_b_score = scored_df.loc[scored_df["tract_id"] == "TRACT_B", "neighborhood_urgency_score"].iloc[0]
    assert tract_a_score > tract_b_score

    assert len(attributions) == 2
    assert attributions[0].primary_driver != ""
    assert attributions[0].urgency_level in ["High", "Moderate", "Low"]


def test_attach_neighborhood_urgency():
    buildings = pd.DataFrame({
        "osm_building_id": ["b1", "b2"],
        "roof_area_m2": [500.0, 800.0],
    })
    tract_df = pd.DataFrame([{
        "tract_id": "TRACT_A",
        "tract_name": "Hot Urban Core",
        "neighborhood_urgency_score": 0.88,
        "urgency_level": "High",
        "primary_driver": "Accelerating surface temperature",
        "secondary_driver": "Loss of cooling canopy & vegetation",
    }])

    enriched = attach_neighborhood_urgency(buildings, tract_df)
    assert "neighborhood_urgency_score" in enriched.columns
    assert "tract_name" in enriched.columns
    assert enriched["neighborhood_urgency_score"].iloc[0] == 0.88
    assert enriched["tract_name"].iloc[0] == "Hot Urban Core"
    assert enriched["urgency_is_ml"].iloc[0] is True


def test_run_neighborhood_urgency_pipeline_on_phoenix_history():
    geojson_path = "data/raw/phoenix_neighborhood_history.geojson"
    scored_df, summary = run_neighborhood_urgency_pipeline(geojson_path)

    assert len(scored_df) > 0
    assert len(summary) == len(scored_df)
    assert "neighborhood_urgency_score" in scored_df.columns
    assert summary[0]["urgency_score"] >= summary[-1]["urgency_score"]
