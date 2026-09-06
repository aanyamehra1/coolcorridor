"""
CRS and geometry utilities.

Design intent: never let a metric calculation (area, perimeter) run silently
on unprojected lat/lon degrees, and never assume one UTM zone works for every
city. Every CRS transform in this project should be traceable to a call in
this module.
"""

from __future__ import annotations

import logging
import math

import geopandas as gpd

logger = logging.getLogger(__name__)

WGS84 = "EPSG:4326"


def suggest_utm_epsg(gdf: gpd.GeoDataFrame) -> int:
    """Derive a reasonable UTM EPSG code from the data's own centroid.

    This is a fallback/sanity-check, not a replacement for a study-area
    specific value in config -- a fixed UTM zone can be wrong near zone
    boundaries or for study areas spanning multiple zones. Use this to
    validate config.study_area.projected_epsg rather than to silently
    override it.
    """
    if gdf.crs is None:
        raise ValueError(
            "GeoDataFrame has no CRS set; cannot infer a UTM zone. "
            "Set the source CRS explicitly before calling this."
        )
    wgs84 = gdf.to_crs(WGS84)
    centroid = wgs84.geometry.union_all().centroid
    lon, lat = centroid.x, centroid.y
    zone = int(math.floor((lon + 180) / 6) + 1)
    is_northern = lat >= 0
    return (32600 if is_northern else 32700) + zone


def ensure_crs(gdf: gpd.GeoDataFrame, expected_crs: str | int) -> gpd.GeoDataFrame:
    """Return a copy of gdf guaranteed to be in expected_crs.

    If gdf has no CRS at all, we cannot safely assume one -- that would be
    silently fabricating spatial metadata -- so we raise instead of guessing.
    """
    if gdf.crs is None:
        raise ValueError(
            "Input GeoDataFrame has no CRS. Refusing to assume one; "
            "set gdf.crs explicitly based on the data's known source."
        )
    if str(gdf.crs) == str(expected_crs):
        return gdf
    return gdf.to_crs(expected_crs)


def compute_area_and_perimeter(
    gdf: gpd.GeoDataFrame, projected_epsg: int
) -> gpd.GeoDataFrame:
    """Compute area (m^2), perimeter (m), and compactness on a projected copy.

    Compactness = 4*pi*Area / Perimeter^2 (1.0 for a perfect circle, lower
    for elongated/irregular shapes). Returned GeoDataFrame is in the
    projected CRS -- reproject back to WGS84 separately for mapping.
    """
    projected = ensure_crs(gdf, f"EPSG:{projected_epsg}")
    out = projected.copy()
    out["roof_area_m2"] = out.geometry.area
    out["perimeter_m"] = out.geometry.length
    with_perimeter = out["perimeter_m"] > 0
    out["compactness"] = float("nan")
    out.loc[with_perimeter, "compactness"] = (
        4 * math.pi * out.loc[with_perimeter, "roof_area_m2"]
        / out.loc[with_perimeter, "perimeter_m"] ** 2
    )
    return out


def drop_invalid_geometries(gdf: gpd.GeoDataFrame) -> tuple[gpd.GeoDataFrame, int]:
    """Remove null/empty/invalid geometries. Returns (clean_gdf, n_dropped)."""
    n_before = len(gdf)
    mask = ~gdf.geometry.is_empty & gdf.geometry.notna()
    mask &= gdf.geometry.is_valid
    cleaned = gdf[mask].copy()
    n_dropped = n_before - len(cleaned)
    if n_dropped:
        logger.warning("Dropped %d invalid/empty geometries.", n_dropped)
    return cleaned, n_dropped
