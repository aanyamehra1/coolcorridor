"""Streamlit sidebar controls and top-level KPI dashboard.

Frontend-only module. `UserInputs`, `to_app_config`, and every widget's
type/min/max/step/default value are unchanged from the original — only
grouping, icons, help text, and table/banner presentation were added.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import streamlit as st

from config.settings import AppConfig, BenefitWeights, EconomicConfig, FilterConfig
from services.optimization import OptimizationResult


@dataclass
class UserInputs:
    budget: float
    min_roof_area: float
    min_anomaly: float
    coating_cost: float
    electricity_rate: float
    cooling_factor: float
    heat_weight: float
    energy_weight: float
    equity_weight: float


def render_sidebar(defaults: AppConfig) -> UserInputs:
    st.sidebar.markdown(
        "<div class='cc-section-title' style='margin-top:0;'>"
        "🏛️ Municipal Investment Parameters</div>",
        unsafe_allow_html=True,
    )

    with st.sidebar.container(border=True):
        st.markdown("**💰 Budget**")
        budget = st.slider(
            "Available budget ($)", min_value=25_000, max_value=2_000_000,
            value=int(defaults.default_budget_usd), step=25_000, format="$%d",
            help="Total municipal funds available for cool-roof interventions. "
                 "The optimizer selects the combination of buildings that "
                 "maximizes benefit without exceeding this amount.",
        )

    with st.sidebar.container(border=True):
        st.markdown("**🏢 Candidate filters**")
        min_roof_area = st.number_input(
            "Minimum roof area (m²)", min_value=0.0,
            value=defaults.filters.min_roof_area_m2, step=50.0,
            help="Buildings with a smaller roof than this are excluded "
                 "before scoring — very small roofs rarely justify "
                 "coating costs.",
        )
        min_anomaly = st.number_input(
            "Minimum thermal anomaly (°C)", min_value=0.0,
            value=defaults.filters.min_thermal_anomaly_c, step=0.5,
            help="Only consider buildings at least this many degrees "
                 "hotter than the district's median surface temperature.",
        )

    with st.sidebar.container(border=True):
        st.markdown("**⚡ Economic assumptions**")
        coating_cost = st.number_input(
            "Coating cost ($/m²)", min_value=1.0, max_value=100.0,
            value=defaults.economics.coating_cost_per_m2, step=1.0,
            help="Estimated material + labor cost per square meter of "
                 "reflective coating applied.",
        )
        electricity_rate = st.number_input(
            "Electricity rate ($/kWh)", min_value=0.01, max_value=1.0,
            value=defaults.economics.electricity_rate_per_kwh, step=0.01,
            help="Local electricity price, used to convert estimated "
                 "energy savings into dollar savings.",
        )
        cooling_factor = st.number_input(
            "Annual cooling factor (kWh/m²/yr)", min_value=0.0, max_value=100.0,
            value=defaults.economics.annual_cooling_factor_kwh_per_m2, step=1.0,
            help="Assumed annual energy-savings yield per square meter of "
                 "coated roof, from reduced cooling demand.",
        )
        st.caption(
            "These are model assumptions, not measured values for any "
            "specific building. Adjust them to match local costs and climate."
        )

    with st.sidebar.container(border=True):
        st.markdown("**⚖️ Benefit score weights**")
        heat_weight = st.slider(
            "Heat weight", 0.0, 1.0, defaults.weights.w_heat, 0.05,
            help="How much priority to give buildings with a larger "
                 "surface-temperature anomaly.",
        )
        energy_weight = st.slider(
            "Energy weight", 0.0, 1.0, defaults.weights.w_energy, 0.05,
            help="How much priority to give buildings with larger "
                 "estimated energy-cost savings.",
        )
        equity_weight = st.slider(
            "Equity weight", 0.0, 1.0, defaults.weights.w_equity, 0.05,
            help="How much priority to give buildings in more socially "
                 "vulnerable areas (SVI).",
        )
        st.caption(
            "Weights are re-normalized to sum to 1 automatically. "
            "benefit = w_heat·norm(anomaly) + w_energy·norm(savings) + w_equity·norm(SVI)"
        )

    return UserInputs(
        budget=budget, min_roof_area=min_roof_area, min_anomaly=min_anomaly,
        coating_cost=coating_cost, electricity_rate=electricity_rate,
        cooling_factor=cooling_factor, heat_weight=heat_weight,
        energy_weight=energy_weight, equity_weight=equity_weight,
    )


def to_app_config(base: AppConfig, inputs: UserInputs) -> AppConfig:
    """Build a fresh AppConfig reflecting the user's sidebar choices."""
    return AppConfig(
        study_area=base.study_area,
        satellite=base.satellite,
        filters=FilterConfig(
            min_roof_area_m2=inputs.min_roof_area,
            min_thermal_anomaly_c=inputs.min_anomaly,
            max_thermal_anomaly_c=base.filters.max_thermal_anomaly_c,
            require_thermal_data=base.filters.require_thermal_data,
        ),
        economics=EconomicConfig(
            coating_cost_per_m2=inputs.coating_cost,
            electricity_rate_per_kwh=inputs.electricity_rate,
            annual_cooling_factor_kwh_per_m2=inputs.cooling_factor,
            solar_reflectance_delta=base.economics.solar_reflectance_delta,
        ),
        weights=BenefitWeights(
            w_heat=inputs.heat_weight, w_energy=inputs.energy_weight,
            w_equity=inputs.equity_weight,
        ),
        default_budget_usd=inputs.budget,
    )


def render_data_quality_banner(
    used_mock_thermal: bool,
    used_mock_vulnerability: bool,
    warnings: list[str],
    used_live_satellite: bool = False,
    thermal_source: str | None = None,
    thermal_limitations: list[str] | None = None,
    satellite_scenes: list | None = None,
) -> None:
    if used_mock_thermal:
        st.warning(
            "🌡 No thermal data available (live satellite acquisition and "
            "local raster both unavailable) — thermal data shown is "
            "**synthetic (mock)** for UI testing only, not a real heat "
            "measurement.",
            icon="⚠️",
        )
    elif used_live_satellite:
        n_scenes = len(satellite_scenes) if satellite_scenes else 0
        scene_note = ""
        if n_scenes == 1:
            scene = satellite_scenes[0]
            acq = scene.acquisition_datetime.split("T")[0] if scene.acquisition_datetime else "unknown date"
            scene_note = f" (scene acquired {acq}, {scene.cloud_cover_pct:.0f}% cloud cover)"
        elif n_scenes > 1:
            scene_note = f" ({n_scenes} scenes combined)"
        st.success(
            f"🛰️ Thermal data retrieved live: {thermal_source}{scene_note}. "
            "This is the most recent suitable overpass, not real-time or "
            "continuous imagery.",
            icon="🛰️",
        )
        if thermal_limitations:
            with st.expander("📋 Satellite data limitations"):
                for note in thermal_limitations:
                    st.write(f"- {note}")
    if used_mock_vulnerability:
        st.info(
            "🧭 No social vulnerability dataset provided — equity scores "
            "shown are **synthetic (mock)** placeholders.",
        )
    if warnings:
        with st.expander("📋 Data quality notes"):
            for w in warnings:
                st.write(f"- {w}")


def render_kpis(result: OptimizationResult, n_candidates: int) -> None:
    if not result.feasible:
        st.error(
            f"⚠️ The optimizer did not find a feasible solution "
            f"(solver status: {result.status}). No buildings were selected.\n\n"
            "**Try:** increasing the budget, lowering the minimum roof area, "
            "or lowering the minimum thermal anomaly filter."
        )
        return

    st.markdown("<div class='cc-section-title'>📊 Optimization results</div>", unsafe_allow_html=True)

    col1, col2, col3, col4, col5 = st.columns(5, gap="medium")
    col1.metric("Selected", f"{result.buildings_selected} / {n_candidates}",
                help="Buildings chosen by the optimizer out of all eligible candidates.")
    col2.metric("Area treated", f"{result.total_area_m2:,.0f} m²",
                help="Total roof area recommended for cool-roof coating.")
    col3.metric("Budget used", f"${result.total_cost_usd:,.0f}",
                help="Total estimated cost of the recommended interventions.")
    col4.metric("Budget remaining", f"${result.remaining_budget_usd:,.0f}",
                help="Budget left unspent after the optimal selection.")
    col5.metric("Avg. thermal anomaly", f"+{result.avg_thermal_anomaly_c:.1f}°C",
                help="Average surface-temperature anomaly among selected buildings, "
                     "relative to the district median.")

    col6, col7, col8 = st.columns(3, gap="medium")
    col6.metric("Est. annual energy savings", f"{result.total_annual_energy_savings_kwh:,.0f} kWh")
    col7.metric("Est. annual $ savings", f"${result.total_annual_savings_usd:,.0f}")
    payback = (
        result.total_cost_usd / result.total_annual_savings_usd
        if result.total_annual_savings_usd > 0 else float("nan")
    )
    col8.metric("Est. payback", f"{payback:.1f} yrs" if payback == payback else "N/A",
                help="Years to recoup the coating investment through estimated energy savings.")

    st.caption(
        "Energy and monetary savings are model estimates based on the "
        "configured assumptions, not guaranteed or measured savings."
    )


_COLUMN_LABELS = {
    "osm_building_id": "Building ID",
    "roof_area_m2": "Roof Area (m²)",
    "lst_median_c": "Surface Temp (°C)",
    "lst_anomaly_c": "Heat Anomaly (°C)",
    "intervention_cost_usd": "Est. Cost ($)",
    "annual_savings_usd": "Est. Annual Savings ($)",
    "payback_years": "Payback (yrs)",
    "svi_score": "Vulnerability (SVI)",
    "benefit_score": "Benefit Score",
}


def render_selection_table(gdf: pd.DataFrame) -> None:
    selected = gdf[gdf["selected"] == 1]
    with st.expander("📋 Selected buildings — detail", expanded=False):
        if len(selected) == 0:
            st.write("No buildings were selected.")
            return
        cols = [
            "osm_building_id", "roof_area_m2", "lst_median_c", "lst_anomaly_c",
            "intervention_cost_usd", "annual_savings_usd", "payback_years",
            "svi_score", "benefit_score",
        ]
        cols = [c for c in cols if c in selected.columns]
        table = selected[cols].copy()
        table = table.sort_values("benefit_score", ascending=False)

        # Display-only formatting: renames/number formats are cosmetic and
        # do not alter the underlying values used elsewhere in the app.
        column_config = {}
        if "roof_area_m2" in cols:
            column_config["roof_area_m2"] = st.column_config.NumberColumn(
                _COLUMN_LABELS["roof_area_m2"], format="%.0f")
        if "lst_median_c" in cols:
            column_config["lst_median_c"] = st.column_config.NumberColumn(
                _COLUMN_LABELS["lst_median_c"], format="%.1f°C")
        if "lst_anomaly_c" in cols:
            column_config["lst_anomaly_c"] = st.column_config.NumberColumn(
                _COLUMN_LABELS["lst_anomaly_c"], format="+%.1f°C")
        if "intervention_cost_usd" in cols:
            column_config["intervention_cost_usd"] = st.column_config.NumberColumn(
                _COLUMN_LABELS["intervention_cost_usd"], format="$%.0f")
        if "annual_savings_usd" in cols:
            column_config["annual_savings_usd"] = st.column_config.NumberColumn(
                _COLUMN_LABELS["annual_savings_usd"], format="$%.0f")
        if "payback_years" in cols:
            column_config["payback_years"] = st.column_config.NumberColumn(
                _COLUMN_LABELS["payback_years"], format="%.1f")
        if "svi_score" in cols:
            column_config["svi_score"] = st.column_config.ProgressColumn(
                _COLUMN_LABELS["svi_score"], min_value=0.0, max_value=1.0, format="%.2f")
        if "benefit_score" in cols:
            column_config["benefit_score"] = st.column_config.ProgressColumn(
                _COLUMN_LABELS["benefit_score"], min_value=0.0, max_value=1.0, format="%.2f")
        if "osm_building_id" in cols:
            column_config["osm_building_id"] = st.column_config.TextColumn(
                _COLUMN_LABELS["osm_building_id"])

        st.dataframe(
            table, use_container_width=True, hide_index=True,
            column_config=column_config,
        )
