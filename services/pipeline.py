"""
Orchestrates the full CoolCorridor data pipeline, independent of Streamlit.

Kept framework-agnostic on purpose: the UI layer wraps `build_candidate_dataset`
in `st.cache_data` so expensive steps (OSM download, raster zonal stats) run
once per parameter set instead of on every widget interaction, but the
pipeline itself has no Streamlit import and can be unit tested directly.

Pipeline stages:
  1. OSM building footprints              (services.osm)
  2. Thermal data acquisition:
       a. Live Landsat 8/9 acquisition    (services.satellite)
       b. Local static raster fallback    (services.raster)
       c. Explicitly-flagged mock data    (services.raster)
     then reproject to raster CRS + clip  (services.spatial)
     and compute zonal LST statistics     (services.raster)
  3. Reproject to UTM, compute area/perim (utils.geo)
  4. Thermal anomaly vs. district median  (services.metrics)
  5. Candidate filtering                  (services.metrics)
  6. Social vulnerability (real or mock)  (services.vulnerability)
  7. Economic model (cost, savings)       (services.economics)
  8. Benefit score                        (services.optimization)

Thermal data tiering (step 2) is a deliberate fallback chain, not a silent
substitution: whichever tier actually ran is recorded on PipelineResult
(`used_mock_thermal`, `thermal_source`, `thermal_limitations`,
`satellite_scenes`) and surfaced in the UI, so a user never mistakes a mock
or stale local file for a live satellite read, or a live read for something
more real-time than it is (see services/satellite.py's module docstring).
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field

import geopandas as gpd

from config.settings import AppConfig
from services import metrics, osm, raster, satellite, spatial, vulnerability
from services.optimization import compute_benefit_score
from utils.geo import compute_area_and_perimeter, drop_invalid_geometries
from utils.validation import QualityReport

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    candidates: gpd.GeoDataFrame
    report: QualityReport
    used_mock_thermal: bool
    used_mock_vulnerability: bool
    thermal_baseline_c: float
    # Populated regardless of which thermal tier ran (live satellite, local
    # raster file, or mock), so the UI always has something accurate to show.
    thermal_source: str = "Synthetic (mock)"
    thermal_limitations: list = field(default_factory=list)
    used_live_satellite: bool = False
    satellite_scenes: list = field(default_factory=list)  # list[satellite.SceneMetadata]
    used_ml_urgency: bool = False
    neighborhood_urgency_summary: list = field(default_factory=list)



def build_candidate_dataset(config: AppConfig, on_progress=None) -> PipelineResult:
    """
    `on_progress`, if given, is called with a short human-readable string at
    the start of each major stage (OSM fetch, satellite fetch, zonal stats,
    etc.). It exists so a UI (see app.py) can show *which* stage is running
    instead of a single opaque spinner -- OSM's Overpass API and a live
    satellite fetch can each legitimately take up to a minute, and without
    stage-level feedback that's indistinguishable from a genuine hang.
    """
    def progress(msg: str) -> None:
        logger.info(msg)
        if on_progress is not None:
            on_progress(msg)

    report = QualityReport()
    sa = config.study_area

    # 1. Building footprints
    progress("Fetching building footprints from OpenStreetMap...")
    buildings = osm.fetch_building_footprints(
        sa.place_name, sa.osm_building_tags, sa.bbox, timeout_s=sa.osm_timeout_s
    )
    buildings, n_dropped = drop_invalid_geometries(buildings)
    if n_dropped:
        report.add(f"Dropped {n_dropped} invalid/empty OSM geometries.")

    # 2. Thermal data acquisition -- tiered fallback: live Landsat scene(s)
    #    via Planetary Computer, then a local static raster file, then
    #    explicitly-flagged mock data. Each tier that actually runs is
    #    recorded below rather than silently swapped in.
    used_mock_thermal = False
    used_live_satellite = False
    thermal_source = "Synthetic (mock)"
    thermal_limitations: list = []
    satellite_scenes: list = []
    raster_path = sa.raster_path
    raster_is_raw_dn = True  # local files are raw DN; satellite cache tiles are already Celsius

    bbox_wgs84 = tuple(buildings.total_bounds)  # (minx, miny, maxx, maxy), buildings are EPSG:4326

    fetched = None
    if config.satellite.use_remote_satellite_data:
        progress(
            f"Searching Planetary Computer for a live Landsat scene "
            f"(mode={config.satellite.mode}, max cloud cover "
            f"{config.satellite.max_cloud_cover_pct:.0f}%)..."
        )
        try:
            fetched = satellite.fetch_thermal_raster(bbox_wgs84, config.satellite)
        except satellite.RemoteDataDisabled:
            fetched = None  # caller-facing no-op: fall through to the local/mock tiers below
        except satellite.NoScenesFoundError as exc:
            report.add(
                f"Live satellite acquisition found no usable scenes: {exc} "
                "Falling back to local raster / mock thermal data."
            )
        except satellite.AllPixelsMaskedError as exc:
            report.add(
                f"Live satellite acquisition returned only cloud/shadow-masked "
                f"pixels: {exc} Falling back to local raster / mock thermal data."
            )
        except satellite.SatelliteServiceError as exc:
            report.add(
                f"Live satellite acquisition failed ({exc}). Falling back to "
                "local raster / mock thermal data."
            )

    if fetched is not None:
        raster_path = fetched.raster_path
        raster_is_raw_dn = False  # services.satellite already converts to Celsius + QA-masks
        thermal_source = fetched.source
        thermal_limitations = list(fetched.limitations)
        satellite_scenes = fetched.scenes
        used_live_satellite = True
        report.add(
            f"Thermal data source: {fetched.source} "
            f"({'reused from cache' if fetched.is_cached else 'freshly retrieved'})."
        )

    have_raster = fetched is not None or os.path.exists(raster_path)
    aligned = spatial.align_to_raster_crs(buildings, raster_path) if have_raster else buildings.iloc[0:0]

    if len(aligned) == 0:
        if fetched is not None:
            report.add(
                "All buildings fell outside the fetched satellite scene's "
                "coverage; falling back to MOCK thermal data."
            )
        elif os.path.exists(raster_path):
            report.add(
                "All buildings fell outside the local raster extent; falling "
                "back to MOCK thermal data."
            )
        else:
            report.add(
                f"No Landsat raster found at '{raster_path}'. Using MOCK thermal "
                "data -- results are for UI/workflow testing only, not a real "
                "heat assessment."
            )
        with_thermal = raster.attach_mock_lst(buildings)
        with_thermal = with_thermal.set_crs(buildings.crs)
        used_mock_thermal = True
        used_live_satellite = False
        thermal_source = "Synthetic (mock)"
        thermal_limitations = []
        satellite_scenes = []
    else:
        progress("Computing zonal surface-temperature statistics per building...")
        with_thermal = raster.compute_zonal_lst(aligned, raster_path, raster_is_raw_dn=raster_is_raw_dn)

    # 3. Projected geometry metrics (area, perimeter, compactness)
    progress("Computing building geometry, thermal anomaly, and candidate filters...")
    projected = compute_area_and_perimeter(with_thermal, sa.projected_epsg)

    # 4. Thermal anomaly vs. district baseline (median)
    with_anomaly = metrics.compute_thermal_anomaly(projected)
    baseline = float(with_anomaly["lst_baseline_c"].iloc[0]) if len(with_anomaly) else float("nan")

    # 5. Candidate filtering
    candidates = metrics.filter_candidates(with_anomaly, config.filters, report)

    # 6. Social vulnerability (mock unless a real column was already joined in)
    progress("Scoring social vulnerability, economics, and benefit...")
    used_mock_vulnerability = "svi_score" not in candidates.columns
    if used_mock_vulnerability:
        report.add(
            "No social vulnerability dataset provided. Using MOCK equity "
            "scores -- not a real vulnerability measurement."
        )
        candidates = vulnerability.attach_mock_vulnerability(candidates)
    else:
        candidates = vulnerability.attach_vulnerability(candidates)

    # 6b. Machine Learning Neighborhood Urgency
    used_ml_urgency = False
    neighborhood_urgency_summary = []
    if getattr(config, "ml", None) and config.ml.enable_ml_urgency:
        progress("Running ML historical trajectory model to forecast neighborhood urgency...")
        try:
            from services.ml_urgency import run_neighborhood_urgency_pipeline
            tract_urgency_df, neighborhood_urgency_summary = run_neighborhood_urgency_pipeline(
                config.ml.historical_panel_path,
                current_year=config.ml.current_year,
                lookback_years=config.ml.lookback_years,
            )
            candidates = vulnerability.attach_neighborhood_urgency(candidates, tract_urgency_df)
            used_ml_urgency = True
            report.add(
                f"ML Neighborhood Urgency: Evaluated {len(tract_urgency_df)} census tracts over {config.ml.lookback_years}-year historical trajectory."
            )
        except Exception as exc:
            logger.warning("ML Neighborhood Urgency model failed (%s); using default urgency.", exc)
            report.add(f"ML Neighborhood Urgency fallback: {exc}")
            candidates = vulnerability.attach_neighborhood_urgency(candidates, None)
    else:
        candidates = vulnerability.attach_neighborhood_urgency(candidates, None)

    # 7. Economic model
    from services.economics import apply_economic_model
    candidates = apply_economic_model(candidates, config.economics)

    # 8. Benefit score
    candidates = compute_benefit_score(candidates, config.weights)

    return PipelineResult(
        candidates=candidates,
        report=report,
        used_mock_thermal=used_mock_thermal,
        used_mock_vulnerability=used_mock_vulnerability,
        thermal_baseline_c=baseline,
        thermal_source=thermal_source,
        thermal_limitations=thermal_limitations,
        used_live_satellite=used_live_satellite,
        satellite_scenes=satellite_scenes,
        used_ml_urgency=used_ml_urgency,
        neighborhood_urgency_summary=neighborhood_urgency_summary,
    )

