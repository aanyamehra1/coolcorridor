"""
CoolCorridor: municipal cool-roof intervention decision-support prototype.

Run with:  streamlit run app.py
"""

from __future__ import annotations

import streamlit as st

from config.settings import DEFAULT_CONFIG
from services.pipeline import build_candidate_dataset
from services.optimization import optimize_selection
from ui.dashboard import (
    render_sidebar, to_app_config, render_data_quality_banner,
    render_kpis, render_selection_table,
)
from ui.map import build_deck
from utils.logging import setup_logging
from utils.validation import DataQualityError

setup_logging()

st.set_page_config(page_title="CoolCorridor", page_icon="🏙️", layout="wide")
st.title("🏙️ CoolCorridor")
st.caption(
    "Decision support for prioritizing reflective cool-roof interventions "
    "under a limited municipal budget."
)


@st.cache_data(show_spinner=False)
def _cached_candidates(config_key: tuple):
    """Cache key is the tuple of parameters that actually change the fetched
    dataset (study area + filters + economics + weights). Streamlit's
    cache_data hashes arguments, so we pass the AppConfig back in via
    closure-free reconstruction to keep this cacheable and side-effect-free.

    Satellite acquisition settings (config.satellite) are intentionally not
    part of this cache key -- they're a project-level setting like study_area
    rather than something the sidebar exposes, and services.satellite has its
    own on-disk, day-bucketed cache for "latest" mode, so this doesn't risk
    silently serving a stale live-satellite read.

    show_spinner is disabled here (rather than a single static message) so
    build_candidate_dataset's on_progress callback can drive a live,
    stage-by-stage status widget instead -- OSM's Overpass API and a live
    satellite fetch can each legitimately take up to a minute, and a single
    unchanging spinner label is indistinguishable from an actual hang.
    """
    from config.settings import AppConfig, FilterConfig, EconomicConfig, BenefitWeights
    (place_name, epsg, raster_path, tags_frozen,
     min_area, min_anom, max_anom, require_thermal,
     cost, rate, cooling, w_heat, w_energy, w_equity, budget) = config_key

    from config.settings import StudyAreaConfig
    cfg = AppConfig(
        study_area=StudyAreaConfig(
            place_name=place_name, projected_epsg=epsg, raster_path=raster_path,
            osm_building_tags=dict(tags_frozen),
        ),
        # Satellite acquisition settings aren't exposed in the sidebar (they're
        # project-level, like study_area) -- carry DEFAULT_CONFIG's through
        # rather than resetting to SatelliteConfig() defaults on every rerun.
        satellite=DEFAULT_CONFIG.satellite,
        filters=FilterConfig(
            min_roof_area_m2=min_area, min_thermal_anomaly_c=min_anom,
            max_thermal_anomaly_c=max_anom, require_thermal_data=require_thermal,
        ),
        economics=EconomicConfig(
            coating_cost_per_m2=cost, electricity_rate_per_kwh=rate,
            annual_cooling_factor_kwh_per_m2=cooling,
        ),
        weights=BenefitWeights(w_heat=w_heat, w_energy=w_energy, w_equity=w_equity),
        default_budget_usd=budget,
    )
    with st.status("Building candidate dataset...", expanded=True) as status:
        def on_progress(msg: str) -> None:
            status.write(msg)

        try:
            result = build_candidate_dataset(cfg, on_progress=on_progress)
        except Exception:
            status.update(label="Failed to build candidate dataset.", state="error")
            raise
        status.update(label="Candidate dataset ready.", state="complete", expanded=False)
        return result


def main() -> None:
    inputs = render_sidebar(DEFAULT_CONFIG)
    config = to_app_config(DEFAULT_CONFIG, inputs)

    cache_key = (
        config.study_area.place_name, config.study_area.projected_epsg,
        config.study_area.raster_path, tuple(sorted(config.study_area.osm_building_tags.items())),
        config.filters.min_roof_area_m2, config.filters.min_thermal_anomaly_c,
        config.filters.max_thermal_anomaly_c, config.filters.require_thermal_data,
        config.economics.coating_cost_per_m2, config.economics.electricity_rate_per_kwh,
        config.economics.annual_cooling_factor_kwh_per_m2,
        config.weights.w_heat, config.weights.w_energy, config.weights.w_equity,
        config.default_budget_usd,
    )

    try:
        pipeline_result = _cached_candidates(cache_key)
    except DataQualityError as exc:
        st.error(f"Could not build the candidate dataset: {exc}")
        st.stop()

    candidates = pipeline_result.candidates
    render_data_quality_banner(
        pipeline_result.used_mock_thermal,
        pipeline_result.used_mock_vulnerability,
        pipeline_result.report.warnings,
        used_live_satellite=pipeline_result.used_live_satellite,
        thermal_source=pipeline_result.thermal_source,
        thermal_limitations=pipeline_result.thermal_limitations,
        satellite_scenes=pipeline_result.satellite_scenes,
    )

    if len(candidates) == 0:
        st.warning("No candidate buildings meet the current filters.")
        st.stop()

    st.caption(
        f"District thermal baseline (median LST): "
        f"{pipeline_result.thermal_baseline_c:.1f}°C. "
        "LST is surface temperature, not air temperature, and reflects a "
        "neighborhood-scale thermal signal rather than precise roof-level "
        "measurement (see raster resolution note in services/raster.py)."
    )

    result = optimize_selection(candidates, budget=inputs.budget)
    render_kpis(result, n_candidates=len(candidates))

    st.markdown("### Interactive 3D map")
    gdf_wgs84 = result.gdf.to_crs(epsg=4326)
    st.pydeck_chart(build_deck(gdf_wgs84))

    render_selection_table(result.gdf)


if __name__ == "__main__":
    main()
