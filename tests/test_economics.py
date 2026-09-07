import pandas as pd
import pytest

from config.settings import EconomicConfig
from services.economics import apply_economic_model


def test_apply_economic_model_basic_math():
    df = pd.DataFrame({"roof_area_m2": [10000.0]})
    econ = EconomicConfig(
        coating_cost_per_m2=15.0, electricity_rate_per_kwh=0.16,
        annual_cooling_factor_kwh_per_m2=18.0,
    )
    out = apply_economic_model(df, econ)
    assert out["intervention_cost_usd"].iloc[0] == pytest.approx(150000.0)
    assert out["annual_energy_savings_kwh"].iloc[0] == pytest.approx(180000.0)
    assert out["annual_savings_usd"].iloc[0] == pytest.approx(28800.0)
    assert out["payback_years"].iloc[0] == pytest.approx(150000.0 / 28800.0)


def test_apply_economic_model_zero_area_no_div_by_zero():
    df = pd.DataFrame({"roof_area_m2": [0.0]})
    econ = EconomicConfig()
    out = apply_economic_model(df, econ)
    assert pd.isna(out["payback_years"].iloc[0])


def test_apply_economic_model_scales_savings_with_reflectance_delta():
    df = pd.DataFrame({"roof_area_m2": [10000.0]})
    econ = EconomicConfig(solar_reflectance_delta=0.25)

    out = apply_economic_model(df, econ)

    assert out["annual_energy_savings_kwh"].iloc[0] == pytest.approx(90000.0)
