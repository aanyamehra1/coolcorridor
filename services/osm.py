"""
Building footprint retrieval from OpenStreetMap via OSMnx.

What goes in: EITHER a lat/lon bounding box (preferred -- see below) OR a
place name string (e.g. "Phoenix, Arizona, USA"), plus a tag filter dict.
What comes out: a GeoDataFrame of building polygons in WGS84 (EPSG:4326),
with non-polygon geometries (points, lines -- OSM sometimes tags a single
node as a "building") removed.

Why bbox is preferred over place name: `features_from_place` depends on
Nominatim successfully geocoding the string to an administrative/place
*polygon* boundary. Many perfectly reasonable-sounding descriptions --
e.g. "Downtown, Phoenix, Arizona, USA" -- have no such boundary in OSM and
raise "did not geocode query ... to a geometry of type (Multi)Polygon",
even though the underlying area and its buildings exist and are mapped.
A bounding box has no such dependency: it always resolves to the same
rectangle. `config.settings.StudyAreaConfig` carries both `place_name`
(for display/logging) and `bbox`; this module uses `bbox` whenever it's
provided and only geocodes `place_name` as a fallback.

Important: OSMnx's API changed between major versions. `geometries_from_place`
was removed in osmnx 2.0 in favour of `features_from_place`/`features_from_bbox`,
and as of 2.0 `features_from_bbox`'s `bbox` argument is `(left, bottom, right,
top)` i.e. `(west, south, east, north)` -- the old separate `north, south,
east, west` keyword arguments were removed. Pin osmnx>=2.0 in
requirements.txt and use the current call signature so this doesn't break
on a fresh environment.
"""

from __future__ import annotations

import logging

import geopandas as gpd
import osmnx as ox

from utils.validation import DataQualityError

logger = logging.getLogger(__name__)


def fetch_building_footprints(
    place_name: str,
    building_tags: dict | None = None,
    bbox: tuple[float, float, float, float] | None = None,
    timeout_s: int = 60,
) -> gpd.GeoDataFrame:
    """Fetch building footprints from OpenStreetMap.

    If `bbox` is given -- (west, south, east, north) in EPSG:4326 -- it is
    used directly via `features_from_bbox` and `place_name` is only used for
    logging/error messages. Otherwise falls back to geocoding `place_name`
    via `features_from_place`, which requires Nominatim to resolve it to a
    polygon boundary (see module docstring for why that's the less robust
    path).

    `timeout_s` bounds how long OSMnx will wait on a single Overpass/Nominatim
    HTTP request. OSMnx's own default (`ox.settings.requests_timeout`) is
    180 seconds, which on a slow or oversized query can look indistinguishable
    from a genuine hang in a Streamlit spinner with no intermediate feedback.
    Lowering it means a real network problem surfaces as an actionable error
    well within a minute instead of leaving the UI stuck silently.

    Raises DataQualityError if OSM returns no usable polygon geometries, or
    if geocoding `place_name` fails -- callers should catch this and show
    the user an actionable message rather than crash on an empty/missing
    later column.
    """
    tags = building_tags if building_tags is not None else {"building": True}
    ox.settings.requests_timeout = timeout_s

    if bbox is not None:
        logger.info(
            "Fetching OSM building footprints for bbox %s (%r) ...", bbox, place_name
        )
        try:
            raw = ox.features_from_bbox(bbox, tags=tags)
        except Exception as exc:  # OSMnx raises several distinct exception types
            # (InsufficientResponseError, network errors, Overpass timeouts).
            # We deliberately catch broadly here because *any* failure at this
            # boundary means "no data", which the caller needs to know about
            # regardless of the specific cause -- but we re-raise as our own
            # typed error so callers don't need to know about OSMnx internals.
            raise DataQualityError(
                f"Could not retrieve OSM data for bbox {bbox} ({place_name!r}): {exc}"
            ) from exc
        location_label = f"bbox {bbox}"
    else:
        logger.info("Fetching OSM building footprints for %r ...", place_name)
        try:
            raw = ox.features_from_place(place_name, tags=tags)
        except Exception as exc:
            raise DataQualityError(
                f"Could not retrieve OSM data for '{place_name}': {exc} "
                "(consider setting StudyAreaConfig.bbox instead -- place-name "
                "geocoding requires Nominatim to resolve the string to an "
                "administrative/place polygon, which many descriptive names "
                "like 'Downtown, X' don't have)."
            ) from exc
        location_label = f"'{place_name}'"

    if raw is None or len(raw) == 0:
        raise DataQualityError(
            f"OpenStreetMap returned no features for {location_label}. "
            "Check the place name/bbox, or that the area actually has tagged "
            "buildings."
        )

    # OSM sometimes tags a single node (not a footprint) as a "building".
    # Keep polygons and multipolygons only.
    polygon_mask = raw.geometry.type.isin(["Polygon", "MultiPolygon"])
    buildings = raw[polygon_mask].reset_index(drop=True)

    if len(buildings) == 0:
        raise DataQualityError(
            f"OSM returned {len(raw)} feature(s) for {location_label} but none "
            "were polygon footprints (only points/lines)."
        )

    if buildings.crs is None:
        # OSMnx always returns EPSG:4326, but don't take that for granted --
        # a naive assumption here is exactly the kind of silent CRS bug this
        # project is trying to avoid.
        buildings = buildings.set_crs("EPSG:4326")

    logger.info(
        "Retrieved %d building polygon(s) (dropped %d non-polygon feature(s)).",
        len(buildings), len(raw) - len(buildings),
    )

    # Keep a manageable, explicit column set; OSM tag columns are highly
    # variable and mostly irrelevant downstream.
    keep_cols = [c for c in ["geometry", "building", "name", "addr:housenumber",
                              "addr:street", "height", "building:levels"]
                 if c in buildings.columns]
    buildings = buildings[keep_cols].copy()
    buildings["osm_building_id"] = [f"BLD_{i:05d}" for i in range(len(buildings))]

    return buildings

