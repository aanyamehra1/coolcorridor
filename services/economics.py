"""
Economic model: intervention cost, estimated energy savings, payback.

Every number this module produces is a MODEL ESTIMATE derived from the
configurable assumptions in config.EconomicConfig (coating cost per m²,
electricity rate, an assumed annual cooling benefit per m²). These are not
measured savings for any real building -- actual savings depend on HVAC
system, occupancy, insulation, climate, and roof condition, none of which
this prototype models. The UI must label these as estimates, never as
guaranteed savings.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from config.settings import EconomicConfig
from utils.validation import require_columns


def apply_economic_model(gdf: pd.DataFrame, econ: EconomicConfig) -> pd.DataFrame:
    require_columns(gdf, ["roof_area_m2"], "apply_economic_model")
    out = gdf.copy()

    out["intervention_cost_usd"] = out["roof_area_m2"] * econ.coating_cost_per_m2
    out["annual_energy_savings_kwh"] = (
        out["roof_area_m2"] * econ.annual_cooling_factor_kwh_per_m2
    )
    out["annual_savings_usd"] = (
        out["annual_energy_savings_kwh"] * econ.electricity_rate_per_kwh
    )

    with np.errstate(divide="ignore", invalid="ignore"):
        payback = out["intervention_cost_usd"] / out["annual_savings_usd"]
    out["payback_years"] = payback.replace([np.inf, -np.inf], np.nan)

    return out
