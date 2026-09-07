"""Streamlit main body controls and top-level KPI dashboard."""

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


def render_about_section() -> None:
    with st.expander("INTRODUCTION TO COOLCORRIDOR", expanded=False):
        st.markdown(
            """
            <div class="cc-intro">
            <p>
            CoolCorridor helps a city decide <b>which rooftops to coat with
            reflective ("cool-roof") paint first</b>, given a limited
            budget. Reflective coatings bounce sunlight away instead of
            absorbing it, which lowers the building's temperature and its
            air-conditioning bill.
            </p>
            <p>
            Every rooftop in the study area is scored and ranked, and the
            tool picks the combination of roofs that fits the budget and
            delivers the most overall benefit. A few terms you'll see:
            </p>
            <ul>
                <li><b>Thermal anomaly</b> — how much hotter a roof's
                surface is than the surrounding area, estimated from
                satellite imagery. A bigger number means more to gain from
                cooling it.</li>
                <li><b>Benefit score</b> — a single 0–1 ranking that blends
                heat reduction, estimated energy savings, and neighborhood
                equity.</li>
                <li><b>Equity / SVI</b> — a social-vulnerability signal, so
                the tool can favor neighborhoods that are more exposed to
                heat-related harm.</li>
            </ul>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_sidebar(defaults: AppConfig) -> UserInputs:
    """
    Previously rendered in a crowded sidebar. Now integrated natively into 
    the scroll-based presentation layer to preserve layout harmony.
    """
    st.markdown("---")
    st.markdown("### Analysis Parameters")
    st.caption("Adjust investment limits and weighting parameters below.")
    st.write("")

    col_budget, col_controls = st.columns([1.2, 1], gap="large")

    with col_budget:
        st.markdown("#### Municipal Budget")
        budget = st.slider(
            "Available Budget ($)", min_value=25_000, max_value=2_000_000,
            value=int(defaults.default_budget_usd), step=25_000, format="$%d",
            help="Total municipal dollars available to spend on cool-roof coatings.",
        )
        
        st.write("")
        st.markdown("#### Benefit Score Weights")
        heat_weight = st.slider(
            "Heat weight", 0.0, 1.0, defaults.weights.w_heat, 0.05,
            help="How much a roof's thermal anomaly counts toward its overall benefit score.",
        )
        energy_weight = st.slider(
            "Energy weight", 0.0, 1.0, defaults.weights.w_energy, 0.05,
            help="How much estimated energy-cost savings counts toward the benefit score.",
        )
        equity_weight = st.slider(
            "Equity weight", 0.0, 1.0, defaults.weights.w_equity, 0.05,
            help="How much neighborhood social-vulnerability counts toward the benefit score.",
        )

    with col_controls:
        with st.expander("Candidate Filters", expanded=True):
            min_roof_area = st.number_input(
                "Minimum roof area (m²)", min_value=0.0, value=defaults.filters.min_roof_area_m2, step=50.0,
            )
            min_anomaly = st.number_input(
                "Minimum thermal anomaly (°C)", min_value=0.0,
                value=defaults.filters.min_thermal_anomaly_c, step=0.5,
            )

        with st.expander("Economic Assumptions", expanded=False):
            coating_cost = st.number_input(
                "Coating cost ($/m²)", min_value=1.0, max_value=100.0,
                value=defaults.economics.coating_cost_per_m2, step=1.0,
            )
            electricity_rate = st.number_input(
                "Electricity rate ($/kWh)", min_value=0.01, max_value=1.0,
                value=defaults.economics.electricity_rate_per_kwh, step=0.01,
            )
            cooling_factor = st.number_input(
                "Annual cooling factor (kWh/m²/yr)", min_value=0.0, max_value=100.0,
                value=defaults.economics.annual_cooling_factor_kwh_per_m2, step=1.0,
            )

    st.markdown("---")

    return UserInputs(
        budget=budget, min_roof_area=min_roof_area, min_anomaly=min_anomaly,
        coating_cost=coating_cost, electricity_rate=electricity_rate,
        cooling_factor=cooling_factor, heat_weight=heat_weight,
        energy_weight=energy_weight, equity_weight=equity_weight,
    )


def to_app_config(base: AppConfig, inputs: UserInputs) -> AppConfig:
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
        st.warning("No thermal data available. Thermal data shown is synthetic for UI testing.")
    elif used_live_satellite:
        n_scenes = len(satellite_scenes) if satellite_scenes else 0
        scene_note = ""
        if n_scenes == 1:
            scene = satellite_scenes[0]
            acq = scene.acquisition_datetime.split("T")[0] if scene.acquisition_datetime else "unknown date"
            scene_note = f" (scene acquired {acq}, {scene.cloud_cover_pct:.0f}% cloud cover)"
        elif n_scenes > 1:
            scene_note = f" ({n_scenes} scenes combined)"
        st.success(f"Thermal data retrieved live: {thermal_source}{scene_note}.")
        if thermal_limitations:
            with st.expander("Satellite Data Limitations"):
                for note in thermal_limitations:
                    st.write(f"- {note}")
    if used_mock_vulnerability:
        st.info("No social vulnerability dataset provided — equity scores shown are placeholders.")
    if warnings:
        with st.expander("Data Quality Notes"):
            for w in warnings:
                st.write(f"- {w}")


def render_kpis(result: OptimizationResult, n_candidates: int) -> None:
    st.markdown("### Results & Insights")
    
    if not result.feasible:
        st.error(
            f"The optimizer did not find a feasible solution (solver status: {result.status}). "
            "No buildings were selected. Try increasing the budget or relaxing the filters."
        )
        return

    col1, col2, col3 = st.columns(3)
    col1.metric("Selected Buildings", f"{result.buildings_selected} / {n_candidates}")
    col2.metric("Area Treated", f"{result.total_area_m2:,.0f} m²")
    col3.metric("Avg. Thermal Anomaly", f"+{result.avg_thermal_anomaly_c:.1f}°C")

    total_budget = result.total_cost_usd + result.remaining_budget_usd
    used_fraction = (result.total_cost_usd / total_budget) if total_budget > 0 else 0.0
    used_fraction = max(0.0, min(1.0, used_fraction))
    
    st.write("")
    st.progress(
        used_fraction,
        text=(
            f"Budget utilized: ${result.total_cost_usd:,.0f} of "
            f"${total_budget:,.0f}  ·  ${result.remaining_budget_usd:,.0f} remaining"
        ),
    )
    st.write("")

    with st.expander("FINANCIAL DETAILS — SAVINGS & PAYBACK", expanded=True):
        col6, col7, col8 = st.columns(3)
        col6.metric("Annual Energy Savings", f"{result.total_annual_energy_savings_kwh:,.0f} kWh")
        col7.metric("Annual Cost Savings", f"${result.total_annual_savings_usd:,.0f}")
        
        payback = (
            result.total_cost_usd / result.total_annual_savings_usd
            if result.total_annual_savings_usd > 0 else float("nan")
        )
        col8.metric("Est. Payback Period", f"{payback:.1f} yrs" if payback == payback else "N/A")


def render_selection_table(gdf: pd.DataFrame) -> None:
    selected = gdf[gdf["selected"] == 1]
    
    st.markdown("### Comprehensive Data")
    
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
    
    # Render with native Streamlit dataframe, relying on our CSS for wrapping long cells
    st.dataframe(table, use_container_width=True, hide_index=True)