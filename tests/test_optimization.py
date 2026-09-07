import pandas as pd

from config.settings import BenefitWeights
from services.optimization import compute_benefit_score, optimize_selection


def _sample_df():
    return pd.DataFrame({
        "lst_anomaly_c": [1.0, 5.0, 10.0],
        "annual_savings_usd": [100.0, 500.0, 1000.0],
        "svi_score": [0.1, 0.5, 0.9],
        "roof_area_m2": [400.0, 400.0, 400.0],
        "intervention_cost_usd": [6000.0, 6000.0, 6000.0],
        "annual_energy_savings_kwh": [1000.0, 1000.0, 1000.0],
    })


def test_compute_benefit_score_ranks_hottest_highest_with_equal_weights():
    df = _sample_df()
    weights = BenefitWeights(w_heat=1.0, w_energy=0.0, w_equity=0.0)
    out = compute_benefit_score(df, weights)
    # With heat-only weighting, row with highest anomaly should score highest
    assert out["benefit_score"].idxmax() == 2


def test_optimize_selection_respects_budget():
    df = _sample_df()
    scored = compute_benefit_score(df, BenefitWeights())
    result = optimize_selection(scored, budget=12000.0)
    assert result.feasible
    # Only 2 of 3 buildings ($6000 each) fit in a $12000 budget
    assert result.buildings_selected == 2
    assert result.total_cost_usd <= 12000.0


def test_optimize_selection_empty_candidates():
    df = pd.DataFrame({
        "intervention_cost_usd": [], "benefit_score": [], "roof_area_m2": [],
        "annual_energy_savings_kwh": [], "annual_savings_usd": [], "lst_anomaly_c": [],
    })
    result = optimize_selection(df, budget=1000.0)
    assert result.buildings_selected == 0
    assert result.status == "No candidates"


def test_optimize_selection_zero_budget_selects_nothing():
    df = _sample_df()
    scored = compute_benefit_score(df, BenefitWeights())
    result = optimize_selection(scored, budget=0.0)
    assert result.feasible
    assert result.buildings_selected == 0


def test_compute_benefit_score_incorporates_urgency():
    df = pd.DataFrame({
        "lst_anomaly_c": [5.0, 5.0],
        "annual_savings_usd": [500.0, 500.0],
        "svi_score": [0.5, 0.5],
        "neighborhood_urgency_score": [0.1, 0.9],
        "roof_area_m2": [400.0, 400.0],
        "intervention_cost_usd": [6000.0, 6000.0],
        "annual_energy_savings_kwh": [1000.0, 1000.0],
    })
    # Equal heat, energy, and equity; difference is purely driven by ML urgency
    weights = BenefitWeights(w_heat=0.25, w_energy=0.25, w_equity=0.25, w_urgency=0.25)
    out = compute_benefit_score(df, weights)
    assert out.loc[1, "benefit_score"] > out.loc[0, "benefit_score"]
    assert out["benefit_score"].idxmax() == 1


def test_compute_benefit_score_backward_compatible_without_urgency_column():
    df = _sample_df()  # has no neighborhood_urgency_score column
    weights = BenefitWeights(w_heat=0.35, w_energy=0.25, w_equity=0.20, w_urgency=0.20)
    out = compute_benefit_score(df, weights)
    assert "benefit_score" in out.columns
    assert not out["benefit_score"].isna().any()
    assert out["benefit_score"].idxmax() == 2

