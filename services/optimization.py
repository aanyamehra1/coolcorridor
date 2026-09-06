"""
Benefit scoring and budget-constrained selection.

Benefit score (transparent, weighted, normalized -- NOT an opaque black box):

    benefit_i = w_heat * norm(anomaly_i)
              + w_energy * norm(annual_savings_usd_i)
              + w_equity * norm(svi_score_i)

Each component is min-max normalized to [0, 1] across the candidate set
before combining, since raw anomaly (a few degrees C), dollars (thousands),
and SVI (already 0-1) live on very different scales -- combining them
unnormalized would let whichever has the largest numbers dominate the score
regardless of the configured weights.

Optimization: a 0/1 integer linear program (not a greedy heuristic and not a
generic knapsack DP), solved with PuLP's bundled CBC solver:

    maximize   sum(benefit_i * x_i)
    subject to sum(cost_i * x_i) <= budget
               x_i in {0, 1}

Using an ILP solver here is equivalent to 0/1 knapsack for a single budget
constraint, but keeps the formulation extensible (e.g. adding a second
constraint such as a minimum-equity-share requirement later) without
switching data structures.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd
import pulp

from config.settings import BenefitWeights
from utils.validation import require_columns

logger = logging.getLogger(__name__)


def _normalize(series: pd.Series) -> pd.Series:
    lo, hi = series.min(), series.max()
    if hi - lo < 1e-9:
        # All candidates identical on this dimension -- normalizing would
        # divide by ~zero. Treat as a flat contribution rather than crash
        # or produce inf/NaN.
        return pd.Series(0.5, index=series.index)
    return (series - lo) / (hi - lo)


def compute_benefit_score(gdf: pd.DataFrame, weights: BenefitWeights) -> pd.DataFrame:
    require_columns(
        gdf,
        ["lst_anomaly_c", "annual_savings_usd", "svi_score"],
        "compute_benefit_score",
    )
    w = weights.normalized()
    out = gdf.copy()

    out["norm_heat"] = _normalize(out["lst_anomaly_c"])
    out["norm_energy"] = _normalize(out["annual_savings_usd"])
    out["norm_equity"] = _normalize(out["svi_score"])

    out["benefit_score"] = (
        w.w_heat * out["norm_heat"]
        + w.w_energy * out["norm_energy"]
        + w.w_equity * out["norm_equity"]
    )
    return out


@dataclass
class OptimizationResult:
    gdf: pd.DataFrame
    status: str
    feasible: bool
    buildings_selected: int
    total_cost_usd: float
    remaining_budget_usd: float
    total_area_m2: float
    total_annual_energy_savings_kwh: float
    total_annual_savings_usd: float
    total_benefit_score: float
    avg_thermal_anomaly_c: float


def optimize_selection(
    gdf: pd.DataFrame, budget: float
) -> OptimizationResult:
    """Solve the 0/1 ILP and return a fully-populated result object.

    Never falls back to a greedy heuristic on solver failure -- if the
    solver can't find/prove an optimum, that is reported explicitly via
    `feasible=False` / `status`, not papered over.
    """
    require_columns(
        gdf, ["intervention_cost_usd", "benefit_score"], "optimize_selection"
    )
    out = gdf.reset_index(drop=True).copy()
    n = len(out)

    if n == 0:
        return OptimizationResult(
            gdf=out, status="No candidates", feasible=False,
            buildings_selected=0, total_cost_usd=0.0, remaining_budget_usd=budget,
            total_area_m2=0.0, total_annual_energy_savings_kwh=0.0,
            total_annual_savings_usd=0.0, total_benefit_score=0.0,
            avg_thermal_anomaly_c=0.0,
        )

    prob = pulp.LpProblem("CoolCorridor_Selection", pulp.LpMaximize)
    x = [pulp.LpVariable(f"x_{i}", cat=pulp.LpBinary) for i in range(n)]

    prob += pulp.lpSum(x[i] * out.loc[i, "benefit_score"] for i in range(n))
    prob += (
        pulp.lpSum(x[i] * out.loc[i, "intervention_cost_usd"] for i in range(n))
        <= budget,
        "Budget_Ceiling",
    )

    solver = pulp.PULP_CBC_CMD(msg=False)
    prob.solve(solver)
    status = pulp.LpStatus[prob.status]
    feasible = status == "Optimal"

    if not feasible:
        logger.warning("Optimizer did not find an optimal solution: %s", status)
        out["selected"] = 0
    else:
        out["selected"] = [int(round(pulp.value(x[i]) or 0)) for i in range(n)]

    selected = out[out["selected"] == 1]
    return OptimizationResult(
        gdf=out,
        status=status,
        feasible=feasible,
        buildings_selected=int(len(selected)),
        total_cost_usd=float(selected["intervention_cost_usd"].sum()),
        remaining_budget_usd=float(budget - selected["intervention_cost_usd"].sum()),
        total_area_m2=float(selected["roof_area_m2"].sum()),
        total_annual_energy_savings_kwh=float(
            selected["annual_energy_savings_kwh"].sum()
        ),
        total_annual_savings_usd=float(selected["annual_savings_usd"].sum()),
        total_benefit_score=float(selected["benefit_score"].sum()),
        avg_thermal_anomaly_c=float(selected["lst_anomaly_c"].mean()) if len(selected) else 0.0,
    )
