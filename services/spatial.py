"""
Alignment between the vector building layer and the raster thermal layer.

Rule of thumb followed throughout this project: use the *raster's* CRS for
raster/vector overlay (zonal stats), and a *local projected CRS* (UTM) for
metric geometry calculations (area, perimeter). These are usually not the
same CRS, so buildings get reprojected twice over the pipeline -- once to
match the raster for zonal stats, once to a UTM zone for area/perimeter.
That's expected, not a bug.
"""

from __future__ import annotations

import logging

import geopandas as gpd
import rasterio

logger = logging.getLogger(__name__)


def align_to_raster_crs(
    buildings: gpd.GeoDataFrame, raster_path: str
) -> gpd.GeoDataFrame:
    """Reproject buildings into the raster's CRS so zonal stats are valid.

    Also drops any buildings entirely outside the raster's spatial extent,
    since zonal stats over them would be meaningless (all-nodata) anyway.
    """
    with rasterio.open(raster_path) as src:
        raster_crs = src.crs
        raster_bounds = src.bounds

    if buildings.crs is None:
        raise ValueError("Buildings have no CRS; cannot align to raster.")

    reprojected = buildings.to_crs(raster_crs)

    from shapely.geometry import box
    raster_bbox = box(*raster_bounds)
    within_extent = reprojected.geometry.intersects(raster_bbox)
    n_outside = (~within_extent).sum()
    if n_outside:
        logger.warning(
            "%d building(s) fall outside the raster's spatial extent and "
            "will be excluded from thermal analysis.", n_outside,
        )

    return reprojected[within_extent].reset_index(drop=True)
