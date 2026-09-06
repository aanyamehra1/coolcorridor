import geopandas as gpd
import pytest
from shapely.geometry import Polygon, box

from utils.geo import compute_area_and_perimeter, drop_invalid_geometries, suggest_utm_epsg


def _square_gdf():
    # A 100m x 100m square in UTM 12N (Phoenix), area = 10,000 m^2, perimeter = 400m
    poly = box(500000, 3700000, 500100, 3700100)
    return gpd.GeoDataFrame({"id": [1]}, geometry=[poly], crs="EPSG:32612")


def test_compute_area_and_perimeter_square():
    gdf = _square_gdf()
    out = compute_area_and_perimeter(gdf, projected_epsg=32612)
    assert out["roof_area_m2"].iloc[0] == pytest.approx(10000.0, rel=1e-6)
    assert out["perimeter_m"].iloc[0] == pytest.approx(400.0, rel=1e-6)
    # A square's compactness is pi/4 ~= 0.785
    assert out["compactness"].iloc[0] == pytest.approx(0.7854, rel=1e-3)


def test_drop_invalid_geometries_removes_none_and_empty():
    good = box(0, 0, 1, 1)
    gdf = gpd.GeoDataFrame(
        {"id": [1, 2, 3]},
        geometry=[good, None, Polygon()],
        crs="EPSG:4326",
    )
    cleaned, n_dropped = drop_invalid_geometries(gdf)
    assert n_dropped == 2
    assert len(cleaned) == 1


def test_compute_area_requires_crs():
    gdf = gpd.GeoDataFrame({"id": [1]}, geometry=[box(0, 0, 1, 1)])
    gdf.crs = None
    with pytest.raises(ValueError):
        compute_area_and_perimeter(gdf, projected_epsg=32612)


def test_suggest_utm_epsg_phoenix():
    gdf = gpd.GeoDataFrame(
        {"id": [1]}, geometry=[box(-112.08, 33.44, -112.07, 33.45)], crs="EPSG:4326"
    )
    # Phoenix is UTM zone 12N -> EPSG 32612
    assert suggest_utm_epsg(gdf) == 32612
