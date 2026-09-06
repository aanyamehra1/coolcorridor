"""
Landsat 8/9 Level-2 Land Surface Temperature (LST) handling.

What goes in: a path to a GeoTIFF (typically the ST_B10 / surface-temperature
band of a USGS Landsat Collection 2 Level-2 product).
What comes out: per-building median LST (deg C) via zonal statistics.

CRITICAL SCIENTIFIC NOTE -- read before changing this file:
Land Surface Temperature is the temperature of the physical surface (a roof,
the ground, vegetation), NOT the air temperature. A roof can read 15-25 C
hotter than the surrounding air on a sunny day. Never present LST values in
the UI as "air temperature".

Landsat's thermal sensor (TIRS) has a native ground sample distance of
~100 m; the USGS Level-2 product resamples this to a 30 m grid to align with
the optical bands. Resampling does NOT create new 30 m-resolution thermal
information -- a 30 m pixel does not mean the sensor actually resolved
30 m of real-world thermal detail. For a building smaller than roughly
100 m x 100 m (i.e. most individual buildings), the "per-building LST" this
pipeline computes is a *neighborhood-scale thermal signal*, not a
measurement of that one roof in isolation. This module's outputs are
labelled "representative" / "neighborhood-scale" for that reason, and the
UI should not claim roof-level thermal precision.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import geopandas as gpd
import numpy as np
import rasterio
import rasterstats

from utils.validation import DataQualityError

logger = logging.getLogger(__name__)

# USGS Landsat Collection 2 Level-2 scale/offset for the ST_B10 band,
# converting the stored digital number to Kelvin. This is specific to the
# Collection 2 Level-2 *surface temperature* product -- a different Landsat
# product (e.g. raw Level-1 thermal bands, or a different collection) would
# need different constants. Do not reuse these blindly for other rasters.
LANDSAT_C2_L2_ST_SCALE = 0.00341802
LANDSAT_C2_L2_ST_OFFSET = 149.0


@dataclass
class RasterInfo:
    crs: object
    bounds: tuple
    width: int
    height: int
    nodata: float | None


def inspect_raster(raster_path: str) -> RasterInfo:
    """Open a raster and report its key spatial metadata without loading pixels."""
    with rasterio.open(raster_path) as src:
        if src.crs is None:
            raise DataQualityError(
                f"Raster at '{raster_path}' has no CRS defined. Refusing to "
                "guess one -- fix the source file's metadata."
            )
        return RasterInfo(
            crs=src.crs,
            bounds=tuple(src.bounds),
            width=src.width,
            height=src.height,
            nodata=src.nodata,
        )


def digital_number_to_celsius(
    dn: np.ndarray,
    scale: float = LANDSAT_C2_L2_ST_SCALE,
    offset: float = LANDSAT_C2_L2_ST_OFFSET,
) -> np.ndarray:
    """Convert Landsat Collection 2 Level-2 ST digital numbers to Celsius.

    kelvin = dn * scale + offset; celsius = kelvin - 273.15
    Values are NOT assumed to already be in Celsius -- see module docstring.
    """
    kelvin = dn.astype("float64") * scale + offset
    return kelvin - 273.15


def compute_zonal_lst(
    buildings: gpd.GeoDataFrame,
    raster_path: str,
    raster_is_raw_dn: bool = True,
    band: int = 1,
) -> gpd.GeoDataFrame:
    """Attach a `lst_median_c` (deg C) column via zonal statistics.

    buildings must already share the raster's CRS (see services.spatial) --
    this function does not reproject, so mismatched CRSs will silently
    produce wrong (or all-nodata) results if skipped upstream. We check the
    CRS explicitly and raise rather than assume alignment.

    raster_is_raw_dn: if True (the default, matching a Landsat C2 L2
    ST_B10.TIF straight from USGS), pixel values are converted from Kelvin
    digital numbers to Celsius using LANDSAT_C2_L2_ST_SCALE/OFFSET before
    the zonal median is computed. Set False if the raster has already been
    converted to Celsius upstream.
    """
    info = inspect_raster(raster_path)
    # Compare CRS by value, not by string representation -- rasterio and
    # geopandas/pyproj often stringify the *same* CRS differently (e.g.
    # "EPSG:32612" vs. the full WKT), so a naive string comparison here
    # would raise false-positive mismatches. pyproj.CRS defines proper
    # equality regardless of how each library represents it.
    from pyproj import CRS as _CRS
    buildings_crs = _CRS.from_user_input(buildings.crs) if buildings.crs else None
    raster_crs = _CRS.from_user_input(info.crs)
    if buildings_crs is None or buildings_crs != raster_crs:
        raise DataQualityError(
            "Building geometries are not in the raster's CRS "
            f"(buildings: {buildings.crs}, raster: {info.crs}). "
            "Reproject buildings to the raster CRS before computing zonal "
            "statistics (see services.spatial.align_to_raster_crs)."
        )

    with rasterio.open(raster_path) as src:
        array = src.read(band)
        nodata = src.nodata
        affine = src.transform

        if raster_is_raw_dn:
            valid = array != nodata if nodata is not None else np.ones_like(array, dtype=bool)
            converted = array.astype("float64")
            converted[valid] = digital_number_to_celsius(array[valid])
            if nodata is not None:
                converted[~valid] = np.nan
            array = converted
            zonal_nodata = np.nan
        else:
            zonal_nodata = nodata if nodata is not None else -9999

        stats = rasterstats.zonal_stats(
            buildings,
            array,
            affine=affine,
            stats=["median", "count"],
            nodata=zonal_nodata,
        )

    medians = [s["median"] for s in stats]
    pixel_counts = [s["count"] for s in stats]

    n_no_data = sum(1 for m in medians if m is None)
    if n_no_data:
        logger.warning(
            "%d of %d buildings had no valid thermal pixels overlapping "
            "their footprint (cloud, nodata, or off raster extent).",
            n_no_data, len(buildings),
        )

    out = buildings.copy()
    out["lst_median_c"] = medians  # may contain None -> becomes NaN downstream
    out["lst_pixel_count"] = pixel_counts
    out["lst_is_mock"] = False
    return out


def attach_mock_lst(buildings: gpd.GeoDataFrame, seed: int = 42) -> gpd.GeoDataFrame:
    """Fallback path when no real Landsat raster is available.

    This generates a plausible-looking but entirely synthetic distribution
    of surface temperatures so the rest of the pipeline (scoring,
    optimization, UI) can be exercised end-to-end without real satellite
    data. It is explicitly flagged via the `lst_is_mock` column, and the
    UI must surface that flag rather than presenting these numbers as
    measured data. This is a development/demo aid, not a scientific
    fallback -- do not use its output to make real intervention decisions.
    """
    logger.warning(
        "No raster available -- generating MOCK thermal data for %d "
        "buildings. Do not treat this as real measurement data.",
        len(buildings),
    )
    rng = np.random.default_rng(seed)
    out = buildings.copy()
    out["lst_median_c"] = rng.uniform(32.0, 55.0, len(out))
    out["lst_pixel_count"] = np.nan
    out["lst_is_mock"] = True
    return out
