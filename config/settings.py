"""
Central configuration for CoolCorridor.

Every tunable assumption used by the pipeline lives here, in one place,
instead of being hard-coded inside individual functions. Values here are
*defaults* — the Streamlit UI lets a user override the economic and
optimization-weight parameters at run time; the rest (study area, filenames,
CRS) are project-level settings a developer would change when adapting the
app to a new city.

None of these numbers are measured facts about any real city. They are
starting assumptions for a prototype and are labelled as such everywhere
they surface in the UI.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


# ---------------------------------------------------------------------------
# Study area / data sources
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class StudyAreaConfig:
    place_name: str = "Downtown, Phoenix, Arizona, USA"
    # (west, south, east, north) in EPSG:4326. Preferred over geocoding
    # `place_name` -- see services/osm.py's module docstring for why:
    # Nominatim can't resolve many descriptive names like "Downtown, X" to a
    # polygon boundary, even though the area and its OSM buildings exist.
    # This default is a ~1.7km x 1.4km box over downtown Phoenix (roughly
    # Van Buren St to the north, 7th Ave to 7th St, south to the rail yard).
    # Set to None to force place_name geocoding instead.
    bbox: tuple[float, float, float, float] | None = (-112.0836, 33.4444, -112.0637, 33.4590)
    # Local projected CRS (metres) used for area/perimeter calculations.
    # Phoenix sits in UTM zone 12N. This MUST be re-checked when the study
    # area changes -- see utils.geo.suggest_utm_epsg for an automatic
    # alternative that derives the zone from the data's own centroid.
    projected_epsg: int = 32612
    raster_path: str = "data/raw/phoenix_landsat_lst.tif"
    osm_cache_path: str = "data/processed/buildings_raw.geojson"
    processed_path: str = "data/processed/buildings_scored.geojson"
    # OSM building tags to retrieve. `True` pulls every tagged building;
    # narrowing this (e.g. to commercial/industrial/retail) trims the
    # candidate set for a faster prototype but will silently exclude
    # everything else, so keep this visible rather than buried in code.
    osm_building_tags: dict = field(default_factory=lambda: {"building": True})
    # Bounds a single Overpass/Nominatim HTTP request (see services/osm.py
    # docstring for why this is lowered from OSMnx's 180s default).
    osm_timeout_s: int = 60


# ---------------------------------------------------------------------------
# Satellite acquisition -- services.satellite.fetch_thermal_raster
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SatelliteConfig:
    """Configuration for live Landsat 8/9 Collection 2 L2 Surface Temperature
    acquisition (see services/satellite.py for the full implementation and
    the accuracy notes baked into it -- read those before changing defaults
    here, especially anything that could make the UI imply "real-time").

    `use_remote_satellite_data` and `subscription_key` can be overridden via
    environment variables (e.g. in a local .env file) without touching code:
      USE_REMOTE_SATELLITE_DATA=false   -- skip the network call entirely and
                                            fall back to the local raster file
                                            / mock data (see services.pipeline)
      PC_SDK_SUBSCRIPTION_KEY=...       -- raises Planetary Computer's
                                            anonymous rate limit; never
                                            required for normal use
    """
    use_remote_satellite_data: bool = field(
        default_factory=lambda: _env_bool("USE_REMOTE_SATELLITE_DATA", True)
    )
    mode: str = "latest"  # "latest" | "date_range"
    date_range: tuple[str, str] | None = None  # (start_iso, end_iso) -- "date_range" mode only
    lookback_days: int = 30  # how far back "latest" searches before giving up
    max_cloud_cover_pct: float = 20.0
    platforms: tuple[str, ...] = ("landsat-8", "landsat-9")
    collection: str = "landsat-c2-l2"
    stac_api_url: str = "https://planetarycomputer.microsoft.com/api/stac/v1"
    subscription_key: str | None = field(
        default_factory=lambda: os.environ.get("PC_SDK_SUBSCRIPTION_KEY")
    )
    request_timeout_s: int = 30
    composite: bool = False  # median composite across scenes -- "date_range" mode only
    max_scenes_for_composite: int = 5
    cache_dir: str = "data/processed/satellite_cache"


# ---------------------------------------------------------------------------
# Candidate filtering
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FilterConfig:
    min_roof_area_m2: float = 400.0
    min_thermal_anomaly_c: float = 0.0
    max_thermal_anomaly_c: float | None = None  # None = no upper bound
    require_thermal_data: bool = True  # drop buildings with no usable LST pixels


# ---------------------------------------------------------------------------
# Economic model -- explicitly labelled assumptions, not measured facts
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class EconomicConfig:
    coating_cost_per_m2: float = 15.0       # USD / m^2, ASSUMPTION
    electricity_rate_per_kwh: float = 0.16  # USD / kWh, ASSUMPTION
    annual_cooling_factor_kwh_per_m2: float = 18.0  # kWh / m^2 / yr, ASSUMPTION
    solar_reflectance_delta: float = 0.50   # delta-albedo from coating, ASSUMPTION


# ---------------------------------------------------------------------------
# Benefit-score weights (optimization objective)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BenefitWeights:
    w_heat: float = 0.35
    w_energy: float = 0.25
    w_equity: float = 0.20
    w_urgency: float = 0.20

    def normalized(self) -> "BenefitWeights":
        total = self.w_heat + self.w_energy + self.w_equity + self.w_urgency
        if total <= 0:
            raise ValueError("Benefit weights must sum to a positive number.")
        return BenefitWeights(
            w_heat=self.w_heat / total,
            w_energy=self.w_energy / total,
            w_equity=self.w_equity / total,
            w_urgency=self.w_urgency / total,
        )


# ---------------------------------------------------------------------------
# Machine Learning trajectory configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MLConfig:
    historical_panel_path: str = "data/raw/phoenix_neighborhood_history.geojson"
    enable_ml_urgency: bool = True
    lookback_years: int = 5
    current_year: int = 2023
    ridge_alpha: float = 1.0


# ---------------------------------------------------------------------------
# Aggregate config bundle
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AppConfig:
    study_area: StudyAreaConfig = field(default_factory=StudyAreaConfig)
    satellite: SatelliteConfig = field(default_factory=SatelliteConfig)
    filters: FilterConfig = field(default_factory=FilterConfig)
    economics: EconomicConfig = field(default_factory=EconomicConfig)
    weights: BenefitWeights = field(default_factory=BenefitWeights)
    ml: MLConfig = field(default_factory=MLConfig)
    default_budget_usd: float = 250_000.0


DEFAULT_CONFIG = AppConfig()

